"""Workflow action, timeline, deficiency and inspection endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api.dependencies import (
    AuditDep,
    ClockDep,
    CurrentUser,
    DbSession,
    require_roles,
)
from app.models.application import Application
from app.models.deficiency import Deficiency
from app.models.enums import Role, WorkflowAction
from app.models.inspection import Inspection
from app.models.user import User
from app.models.workflow import WorkflowEvent
from app.schemas.application import ApplicationDetailRead
from app.schemas.common import ErrorResponse
from app.schemas.workflow import (
    AllowedActionRead,
    AllowedActionsRead,
    CommitteeMemberRead,
    DeficiencyRead,
    InspectionRead,
    WorkflowActionRead,
    WorkflowActionRequest,
    WorkflowEventRead,
    WorkflowTimelineRead,
)
from app.services.alert_engine import NotificationService
from app.services.application_workspace import ApplicationWorkspaceService
from app.services.authorization import can_access_application
from app.services.workflow import WorkflowService

router = APIRouter(prefix="/applications", tags=["workflow"])

SchedulerUser = Annotated[
    User,
    Depends(
        require_roles(
            Role.SCRUTINY_COMMITTEE_MEMBER,
            Role.REGIONAL_OFFICER,
            Role.REGULATION_BUREAU_OFFICER,
        )
    ),
]


def _load_application(db: Session, application_id: uuid.UUID) -> Application | None:
    return db.scalar(
        select(Application)
        .options(
            joinedload(Application.institution),
            joinedload(Application.assigned_officer),
            selectinload(Application.programs),
        )
        .where(Application.id == application_id)
    )


def _readable_application(db: Session, user: User, application_id: uuid.UUID) -> Application:
    application = _load_application(db, application_id)
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    if not can_access_application(db, user, application):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You do not have access to this application",
        )
    return application


def _reload_application(db: Session, application_id: uuid.UUID) -> Application:
    application = _load_application(db, application_id)
    if application is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "The workflow completed but the application could not be loaded",
        )
    return application


def _event_reads(
    db: Session,
    events: list[WorkflowEvent],
) -> list[WorkflowEventRead]:
    if not events:
        return []
    event_ids = [event.id for event in events]
    loaded = db.scalars(
        select(WorkflowEvent)
        .options(joinedload(WorkflowEvent.actor))
        .where(WorkflowEvent.id.in_(event_ids))
    ).all()
    by_id = {event.id: event for event in loaded}
    return [
        WorkflowEventRead.model_validate(by_id[event.id])
        for event in events
        if event.id in by_id
    ]


@router.post(
    "/{application_id}/actions/{action}",
    response_model=WorkflowActionRead,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
    summary="Perform one workflow action on an application",
)
def perform_action(
    application_id: uuid.UUID,
    action: WorkflowAction,
    request: Request,
    current_user: CurrentUser,
    db: DbSession,
    audit: AuditDep,
    clock: ClockDep,
    payload: WorkflowActionRequest | None = None,
) -> WorkflowActionRead:
    """Validate role, state and payload, then apply the transition once."""
    application = _readable_application(db, current_user, application_id)
    payload = payload or WorkflowActionRequest()

    if action == WorkflowAction.SUBMIT:
        settings = request.app.state.settings
        workspace = ApplicationWorkspaceService(db, audit, settings, clock)
        result = workspace.submit(current_user, application, request=request)
    else:
        service = WorkflowService(
            db,
            audit,
            clock,
            notifications=NotificationService.from_settings(request.app.state.settings),
        )
        result = service.execute(
            application,
            actor=current_user,
            action=action,
            payload=payload,
            request=request,
        )

    loaded = _reload_application(db, application_id)
    return WorkflowActionRead(
        application=ApplicationDetailRead.model_validate(loaded),
        events=_event_reads(db, list(result.events)),
        message=result.message,
    )


@router.get(
    "/{application_id}/timeline",
    response_model=WorkflowTimelineRead,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    summary="Get the full workflow timeline for an application",
)
def get_timeline(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> WorkflowTimelineRead:
    """Return every action and transition in chronological order."""
    application = _readable_application(db, current_user, application_id)
    events = db.scalars(
        select(WorkflowEvent)
        .options(joinedload(WorkflowEvent.actor))
        .where(WorkflowEvent.application_id == application.id)
        .order_by(WorkflowEvent.created_at.asc(), WorkflowEvent.id.asc())
    ).all()
    return WorkflowTimelineRead(
        application_id=application.id,
        status=application.status,
        current_stage=application.current_stage,
        stage_entered_at=application.stage_entered_at,
        sla_due_at=application.sla_due_at,
        is_withdrawn=application.is_withdrawn,
        is_escalated=application.is_escalated,
        events=[WorkflowEventRead.model_validate(event) for event in events],
    )


@router.get(
    "/{application_id}/allowed-actions",
    response_model=AllowedActionsRead,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    summary="List workflow actions available to the current user",
)
def get_allowed_actions(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    audit: AuditDep,
    clock: ClockDep,
) -> AllowedActionsRead:
    """Return role- and status-aware actions for UI button rendering."""
    application = _readable_application(db, current_user, application_id)
    service = WorkflowService(db, audit, clock)
    transitions = service.allowed_actions(application, current_user)
    return AllowedActionsRead(
        application_id=application.id,
        status=application.status,
        current_stage=application.current_stage,
        is_withdrawn=application.is_withdrawn,
        actions=[
            AllowedActionRead(
                action=transition.action,
                label=transition.label,
                description=transition.description,
                requires=transition.requires,
                tone=transition.tone,
            )
            for transition in transitions
        ],
    )


@router.get(
    "/{application_id}/deficiencies",
    response_model=list[DeficiencyRead],
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    summary="List deficiencies and institution responses",
)
def list_deficiencies(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> list[DeficiencyRead]:
    """Return deficiency lifecycle details for the application detail view."""
    application = _readable_application(db, current_user, application_id)
    deficiencies = db.scalars(
        select(Deficiency)
        .options(
            joinedload(Deficiency.raised_by_user),
            joinedload(Deficiency.response_document),
        )
        .where(Deficiency.application_id == application.id)
        .order_by(Deficiency.created_at.asc())
    ).all()
    return [DeficiencyRead.model_validate(item) for item in deficiencies]


@router.get(
    "/{application_id}/inspections",
    response_model=list[InspectionRead],
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    summary="List inspections and submitted reports",
)
def list_inspections(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> list[InspectionRead]:
    """Return scheduled and completed visits for the application."""
    application = _readable_application(db, current_user, application_id)
    inspections = db.scalars(
        select(Inspection)
        .options(joinedload(Inspection.committee_member))
        .where(Inspection.application_id == application.id)
        .order_by(Inspection.scheduled_on.asc())
    ).all()
    return [InspectionRead.model_validate(item) for item in inspections]


@router.get(
    "/{application_id}/committee-members",
    response_model=list[CommitteeMemberRead],
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    summary="List inspection committee members for scheduling",
)
def list_committee_members(
    application_id: uuid.UUID,
    current_user: SchedulerUser,
    db: DbSession,
) -> list[CommitteeMemberRead]:
    """Return active committee members in the institution's region."""
    application = _readable_application(db, current_user, application_id)
    if application.is_withdrawn:
        return []
    members = db.scalars(
        select(User)
        .where(
            User.role == Role.EVC_MEMBER,
            User.is_active.is_(True),
            User.region == application.institution.region,
        )
        .order_by(User.name.asc())
    ).all()
    return [CommitteeMemberRead.model_validate(member) for member in members]
