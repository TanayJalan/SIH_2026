"""Role-scoped application read endpoints."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload, selectinload

from app.api.dependencies import ClockDep, CurrentUser, DbSession
from app.models.application import Application
from app.models.enums import ApplicationStatus
from app.schemas.application import ApplicationDetailRead, ApplicationPage, ApplicationRead
from app.schemas.application_sections import ApplicationData
from app.schemas.common import ErrorResponse
from app.schemas.compliance import CompliancePreviewRead
from app.services.authorization import application_scope, can_access_application
from app.services.compliance import evaluate_compliance

router = APIRouter(prefix="/applications", tags=["applications"])

_CLOSED_STATUSES = (
    ApplicationStatus.APPROVED,
    ApplicationStatus.CONDITIONALLY_APPROVED,
    ApplicationStatus.REJECTED,
)


@router.get(
    "",
    response_model=ApplicationPage,
    summary="List applications visible to the current role",
)
def list_applications(
    current_user: CurrentUser,
    db: DbSession,
    clock: ClockDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    institution_id: Annotated[uuid.UUID | None, Query()] = None,
    overdue: bool = False,
    assigned_to_me: bool = False,
    sort: Literal["recent", "due"] = "recent",
) -> ApplicationPage:
    """Return a paginated list scoped by institution, assignment or region."""
    conditions = list(application_scope(current_user))
    if institution_id is not None:
        conditions.append(Application.institution_id == institution_id)
    if assigned_to_me:
        conditions.append(Application.assigned_officer_id == current_user.id)
    if overdue:
        conditions.extend(
            [
                Application.sla_due_at.is_not(None),
                Application.sla_due_at < clock.now(),
                Application.status.not_in(_CLOSED_STATUSES),
                Application.is_withdrawn.is_(False),
            ]
        )

    total = db.scalar(select(func.count()).select_from(Application).where(*conditions)) or 0

    order_by = (
        Application.sla_due_at.asc().nullslast()
        if overdue or sort == "due"
        else Application.submitted_at.desc().nullslast()
    )
    applications = db.scalars(
        select(Application)
        .options(joinedload(Application.institution))
        .where(*conditions)
        .order_by(order_by, Application.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return ApplicationPage(
        items=[ApplicationRead.model_validate(item) for item in applications],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get(
    "/{application_id}",
    response_model=ApplicationDetailRead,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    summary="Get an application visible to the current role",
)
def get_application(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> ApplicationDetailRead:
    """Return one application or deny cross-tenant access."""
    application = db.scalar(
        select(Application)
        .options(
            joinedload(Application.institution),
            joinedload(Application.assigned_officer),
            selectinload(Application.programs),
        )
        .where(Application.id == application_id)
    )
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )
    if not can_access_application(db, current_user, application):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this application",
        )
    return ApplicationDetailRead.model_validate(application)


@router.get(
    "/{application_id}/compliance",
    response_model=CompliancePreviewRead,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    summary="Evaluate the configured compliance rules for a case file",
)
def get_application_compliance(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    clock: ClockDep,
) -> CompliancePreviewRead:
    """Return a read-only rule evaluation of the submitted application data."""
    application = db.scalar(select(Application).where(Application.id == application_id))
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )
    if not can_access_application(db, current_user, application):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this application",
        )
    return evaluate_compliance(
        db,
        application,
        ApplicationData.model_validate(application.data or {}),
        evaluated_at=clock.now(),
    )
