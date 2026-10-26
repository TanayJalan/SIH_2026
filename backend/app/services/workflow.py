"""Database-driven approval workflow state machine.

``TRANSITIONS`` is the single authority for which action may move an
application from one status to another and which roles may perform it. API
routes and other services call :class:`WorkflowService`; none of them assign
``Application.status`` directly.

SLA durations are read from ``SLAConfig`` rows. Deficiency, inspection and
decision side effects are handled inside this service so every state change is
recorded once in ``WorkflowEvent`` and ``AuditLog`` and announced through
``alerts.notify``.
"""

from __future__ import annotations

import copy
import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.core.clock import SimulatedClock
from app.models.application import Application
from app.models.deficiency import Deficiency
from app.models.document import Document
from app.models.enums import (
    ApplicationStatus,
    DeficiencyStatus,
    InspectionStatus,
    Role,
    WorkflowAction,
    WorkflowStage,
)
from app.models.inspection import Inspection
from app.models.sla import SLAConfig
from app.models.user import User
from app.models.workflow import WorkflowEvent
from app.schemas.workflow import WorkflowActionRequest
from app.services import alerts
from app.services.audit import AuditService
from app.services.portal_number import next_portal_application_no

logger = logging.getLogger("app.workflow")

ActionRequirement = Literal[
    "none",
    "deficiencies",
    "responses",
    "deficiency_id",
    "inspection_schedule",
    "inspection_report",
    "conditions",
]
ActionTone = Literal["primary", "secondary", "danger"]

_TERMINAL_STATUSES = frozenset(
    {
        ApplicationStatus.APPROVED,
        ApplicationStatus.CONDITIONALLY_APPROVED,
        ApplicationStatus.REJECTED,
    }
)

_OPEN_STATUSES = frozenset(
    status for status in ApplicationStatus if status not in _TERMINAL_STATUSES
)

_ASSIGNED_SCRUTINY_ACTIONS = frozenset(
    {
        WorkflowAction.VERIFY_DOCUMENTS,
        WorkflowAction.RAISE_DEFICIENCY,
        WorkflowAction.CLOSE_DEFICIENCY,
        WorkflowAction.SCHEDULE_INSPECTION,
    }
)

_WITHDRAWABLE_STATUSES = frozenset(
    {
        ApplicationStatus.SUBMITTED,
        ApplicationStatus.DOCUMENT_VERIFICATION,
        ApplicationStatus.SCRUTINY,
        ApplicationStatus.DEFICIENCY_RAISED,
        ApplicationStatus.DEFICIENCY_RESPONDED,
        ApplicationStatus.INSPECTION_SCHEDULED,
        ApplicationStatus.INSPECTION_DONE,
        ApplicationStatus.COMMITTEE_REVIEW,
    }
)


class WorkflowError(Exception):
    """An expected workflow failure with an HTTP representation."""

    status_code = 409

    def __init__(self, message: str, *, detail: Any | None = None) -> None:
        super().__init__(message)
        self.detail = detail if detail is not None else message


class InvalidWorkflowTransition(WorkflowError):
    """Raised when an action is not legal for the current status."""


class WorkflowPermissionError(WorkflowError):
    """Raised when the current role may not perform an action."""

    status_code = 403


class WorkflowValidationError(WorkflowError):
    """Raised when an action payload is incomplete or inconsistent."""

    status_code = 422


class WorkflowConfigurationError(WorkflowError):
    """Raised when required database configuration is missing."""

    status_code = 503


class WorkflowNotFoundError(WorkflowError):
    """Raised when an action references a record outside the application."""

    status_code = 404


@dataclass(frozen=True, slots=True)
class Transition:
    """One row in the workflow transition table."""

    action: WorkflowAction
    from_statuses: frozenset[ApplicationStatus]
    to_status: ApplicationStatus | None
    roles: frozenset[Role]
    stage: WorkflowStage | None
    label: str
    description: str
    apH_clause: str
    requires: ActionRequirement = "none"
    tone: ActionTone = "secondary"
    needs_verification: bool = False
    """True when APH_SPEC does not clearly support this transition."""


def _statuses(*values: ApplicationStatus) -> frozenset[ApplicationStatus]:
    return frozenset(values)


TRANSITIONS: tuple[Transition, ...] = (
    Transition(
        action=WorkflowAction.SUBMIT,
        from_statuses=_statuses(ApplicationStatus.DRAFT),
        to_status=ApplicationStatus.SUBMITTED,
        roles=frozenset({Role.INSTITUTION_ADMIN}),
        stage=WorkflowStage.APPLICATION,
        label="Submit application",
        description=(
            "Send the completed, paid and DSC-signed application into the approval pipeline."
        ),
        apH_clause="APH 1.4.3",
        tone="primary",
    ),
    Transition(
        action=WorkflowAction.REOPEN,
        from_statuses=_statuses(
            ApplicationStatus.SUBMITTED,
            ApplicationStatus.DOCUMENT_VERIFICATION,
            ApplicationStatus.SCRUTINY,
            ApplicationStatus.DEFICIENCY_RAISED,
        ),
        to_status=ApplicationStatus.DRAFT,
        roles=frozenset({Role.REGULATION_BUREAU_OFFICER}),
        stage=WorkflowStage.APPLICATION,
        label="Reopen a wrongly submitted application (once)",
        description=(
            "Regulation Bureau reopens a submitted application once, after a fresh TER "
            "and the late penalty are paid and the Trust resolution (Format 3) is recorded."
        ),
        apH_clause="APH 2.3.3d-e",
        tone="danger",
    ),
    Transition(
        action=WorkflowAction.AUTO_ASSIGN,
        from_statuses=_statuses(ApplicationStatus.SUBMITTED),
        to_status=ApplicationStatus.DOCUMENT_VERIFICATION,
        roles=frozenset({Role.REGULATION_BUREAU_OFFICER}),
        stage=WorkflowStage.DOCUMENT_VERIFICATION,
        label="Assign scrutiny committee",
        description="Regulation Bureau assigns the least-loaded scrutiny member in the region.",
        apH_clause="APH 1.8a",
        tone="primary",
    ),
    Transition(
        action=WorkflowAction.VERIFY_DOCUMENTS,
        from_statuses=_statuses(ApplicationStatus.DOCUMENT_VERIFICATION),
        to_status=ApplicationStatus.SCRUTINY,
        roles=frozenset({Role.SCRUTINY_COMMITTEE_MEMBER}),
        stage=WorkflowStage.SCRUTINY,
        label="Verify documents and start scrutiny",
        description="Scrutiny Committee verifies the authenticity of the uploaded documents.",
        apH_clause="APH 1.8",
        tone="primary",
    ),
    Transition(
        action=WorkflowAction.START_SCRUTINY,
        from_statuses=_statuses(
            ApplicationStatus.SUBMITTED,
            ApplicationStatus.DOCUMENT_VERIFICATION,
        ),
        to_status=ApplicationStatus.SCRUTINY,
        roles=frozenset({Role.REGULATION_BUREAU_OFFICER}),
        stage=WorkflowStage.SCRUTINY,
        label="Start scrutiny",
        description="Regulation Bureau opens scrutiny and ensures a committee member is assigned.",
        apH_clause="APH 1.8",
        tone="secondary",
    ),
    Transition(
        action=WorkflowAction.RAISE_DEFICIENCY,
        from_statuses=_statuses(ApplicationStatus.SCRUTINY),
        to_status=ApplicationStatus.DEFICIENCY_RAISED,
        roles=frozenset({Role.SCRUTINY_COMMITTEE_MEMBER}),
        stage=WorkflowStage.DEFICIENCY,
        label="Raise deficiency",
        description="Record the Deficiency Report items and pause the application for a response.",
        apH_clause="APH 2.3.3b",
        requires="deficiencies",
        tone="primary",
    ),
    Transition(
        action=WorkflowAction.RESPOND_DEFICIENCY,
        from_statuses=_statuses(ApplicationStatus.DEFICIENCY_RAISED),
        to_status=ApplicationStatus.DEFICIENCY_RESPONDED,
        roles=frozenset({Role.INSTITUTION_ADMIN}),
        stage=WorkflowStage.DEFICIENCY,
        label="Respond to deficiencies",
        description="Answer every open deficiency item with text and supporting evidence.",
        apH_clause="APH 2.4",
        requires="responses",
        tone="primary",
    ),
    Transition(
        action=WorkflowAction.CLOSE_DEFICIENCY,
        from_statuses=_statuses(ApplicationStatus.DEFICIENCY_RESPONDED),
        to_status=ApplicationStatus.SCRUTINY,
        roles=frozenset({Role.SCRUTINY_COMMITTEE_MEMBER}),
        stage=WorkflowStage.SCRUTINY,
        label="Close deficiency (Re-Scrutiny)",
        description="Re-Scrutiny verifies only the listed deficiencies before the file moves on.",
        apH_clause="APH 1.8",
        requires="deficiency_id",
        tone="primary",
    ),
    Transition(
        action=WorkflowAction.SCHEDULE_INSPECTION,
        from_statuses=_statuses(ApplicationStatus.SCRUTINY),
        to_status=ApplicationStatus.INSPECTION_SCHEDULED,
        roles=frozenset({Role.REGIONAL_OFFICER, Role.REGULATION_BUREAU_OFFICER}),
        stage=WorkflowStage.INSPECTION,
        label="Schedule Expert Visit Committee",
        description="The Regional Officer constitutes the EVC and records the visit date.",
        apH_clause="APH 1.9a",
        requires="inspection_schedule",
        tone="primary",
    ),
    Transition(
        action=WorkflowAction.SUBMIT_INSPECTION_REPORT,
        from_statuses=_statuses(ApplicationStatus.INSPECTION_SCHEDULED),
        to_status=ApplicationStatus.INSPECTION_DONE,
        roles=frozenset({Role.EVC_MEMBER}),
        stage=WorkflowStage.INSPECTION,
        label="Submit EVC report",
        description="Record infrastructure, faculty and laboratory findings with a recommendation.",
        apH_clause="APH 1.9",
        requires="inspection_report",
        tone="primary",
    ),
    Transition(
        action=WorkflowAction.SEND_TO_COMMITTEE,
        from_statuses=_statuses(ApplicationStatus.INSPECTION_DONE),
        to_status=ApplicationStatus.COMMITTEE_REVIEW,
        roles=frozenset({Role.REGULATION_BUREAU_OFFICER}),
        stage=WorkflowStage.COMMITTEE_REVIEW,
        label="Place observations before the EC",
        description="Regulation Bureau places its observations before the Executive Committee.",
        apH_clause="APH 1.10",
        tone="primary",
    ),
    Transition(
        action=WorkflowAction.APPROVE,
        from_statuses=_statuses(ApplicationStatus.COMMITTEE_REVIEW),
        to_status=ApplicationStatus.APPROVED,
        roles=frozenset({Role.EXECUTIVE_COMMITTEE_MEMBER}),
        stage=WorkflowStage.COMPLETED,
        label="Approve (LoA)",
        description="The Executive Committee records an approval; the Council ratifies it.",
        apH_clause="APH 1.10a",
        tone="primary",
    ),
    Transition(
        action=WorkflowAction.CONDITIONALLY_APPROVE,
        from_statuses=_statuses(ApplicationStatus.COMMITTEE_REVIEW),
        to_status=ApplicationStatus.CONDITIONALLY_APPROVED,
        roles=frozenset({Role.EXECUTIVE_COMMITTEE_MEMBER}),
        stage=WorkflowStage.COMPLETED,
        label="Conditionally approve",
        description="Approve with written conditions the institution must satisfy.",
        apH_clause="APH 4.9c",
        needs_verification=True,
        requires="conditions",
        tone="secondary",
    ),
    Transition(
        action=WorkflowAction.REJECT,
        from_statuses=_statuses(ApplicationStatus.COMMITTEE_REVIEW),
        to_status=ApplicationStatus.REJECTED,
        roles=frozenset({Role.EXECUTIVE_COMMITTEE_MEMBER}),
        stage=WorkflowStage.COMPLETED,
        label="Reject (LoR)",
        description="The Executive Committee records a rejection with a speaking order.",
        apH_clause="APH 1.10",
        tone="danger",
    ),
    Transition(
        action=WorkflowAction.WITHDRAW,
        from_statuses=_WITHDRAWABLE_STATUSES,
        to_status=None,
        roles=frozenset({Role.INSTITUTION_ADMIN}),
        stage=None,
        label="Withdraw application",
        description="Withdraw the application without discarding its workflow history.",
        apH_clause="APH 2.3.3f-g",
        tone="danger",
    ),
)


class AssignmentStrategy(Protocol):
    """Pluggable scrutiny-officer assignment policy."""

    def choose(self, db: Session, application: Application) -> User | None:
        """Return the officer to assign, or ``None`` when none is available."""


def _round_robin_tie_break(
    candidates: Sequence[User],
    db: Session,
    application: Application,
) -> User:
    """Choose the next candidate after the most recently assigned one."""
    ordered = sorted(candidates, key=lambda officer: str(officer.id))
    recent = db.scalar(
        select(Application.assigned_officer_id)
        .where(Application.assigned_officer_id.in_([officer.id for officer in ordered]))
        .order_by(Application.created_at.desc())
        .limit(1)
    )
    if recent is None:
        return ordered[0]
    index = next(
        (position for position, officer in enumerate(ordered) if officer.id == recent),
        0,
    )
    return ordered[(index + 1) % len(ordered)]


class LowestLoadAssignmentStrategy:
    """Assign the same-region officer with the fewest open applications.

    Ties are resolved round-robin using the most recent assignment among the
    tied officers, so repeated submissions spread evenly instead of always
    choosing the same person.
    """

    def __init__(self) -> None:
        self._tie_breaker = _round_robin_tie_break

    def choose(self, db: Session, application: Application) -> User | None:
        region = application.institution.region
        load = func.count(Application.id)
        rows = db.execute(
            select(User, load)
            .outerjoin(
                Application,
                and_(
                    Application.assigned_officer_id == User.id,
                    Application.status.in_(_OPEN_STATUSES),
                    Application.is_withdrawn.is_(False),
                ),
            )
            .where(
                User.role == Role.SCRUTINY_COMMITTEE_MEMBER,
                User.is_active.is_(True),
                User.region == region,
            )
            .group_by(User.id)
            .order_by(User.id)
        ).all()
        if not rows:
            return None

        smallest = min(load_value for _, load_value in rows)
        tied = [officer for officer, load_value in rows if load_value == smallest]
        return self._tie_breaker(tied, db, application)


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    """The application, newly created events and a user-facing message."""

    application: Application
    events: tuple[WorkflowEvent, ...]
    message: str


class WorkflowService:
    """Apply one workflow action inside a single database transaction."""

    def __init__(
        self,
        db: Session,
        audit: AuditService,
        clock: SimulatedClock,
        *,
        assignment_strategy: AssignmentStrategy | None = None,
        notifier: Any = alerts.notify,
        notifications: Any = None,
    ) -> None:
        self._db = db
        self._audit = audit
        self._clock = clock
        self._assignment_strategy = assignment_strategy or LowestLoadAssignmentStrategy()
        self._notifier = notifier
        self._notifications = notifications

    def execute(
        self,
        application: Application,
        *,
        actor: User,
        action: WorkflowAction,
        payload: WorkflowActionRequest | None = None,
        request: Any | None = None,
        enforce_role: bool = True,
    ) -> WorkflowResult:
        """Validate and apply ``action`` to ``application``.

        The transaction is committed by this method. Illegal transitions raise
        :class:`InvalidWorkflowTransition` (HTTP 409), role failures raise
        :class:`WorkflowPermissionError` (HTTP 403) and bad payloads raise
        :class:`WorkflowValidationError` (HTTP 422).
        """
        payload = payload or WorkflowActionRequest()
        transition = self._transition_for(action, application.status)
        self._ensure_active(application)
        if enforce_role and actor.role not in transition.roles:
            raise WorkflowPermissionError(
                f"{action.value} is not permitted for the {actor.role.value} role"
            )
        self._authorize_scope(application, actor, action)

        before = self._snapshot(application)
        events: list[WorkflowEvent] = []
        try:
            message = self._dispatch(
                application,
                actor,
                action,
                transition,
                payload,
                before,
                events,
                request,
            )
            self._db.flush()
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

        for event in events:
            self._notifier(
                event,
                db=self._db,
                application=application,
                actor=actor,
                notifications=self._notifications,
                clock=self._clock,
            )

        return WorkflowResult(application=application, events=tuple(events), message=message)

    def allowed_actions(self, application: Application, actor: User) -> list[Transition]:
        """Return transitions the actor may perform in the current state."""
        if application.is_withdrawn:
            return []

        allowed: list[Transition] = []
        for transition in TRANSITIONS:
            if application.status not in transition.from_statuses:
                continue
            if not self._may_perform(application, actor, transition):
                continue
            allowed.append(transition)
        return allowed

    # ------------------------------------------------------------------
    # Transition resolution and authorization
    # ------------------------------------------------------------------

    @staticmethod
    def _transition_for(action: WorkflowAction, status: ApplicationStatus) -> Transition:
        for transition in TRANSITIONS:
            if transition.action == action and status in transition.from_statuses:
                return transition
        raise InvalidWorkflowTransition(
            f"Action '{action.value}' is not allowed while the application is {status.value}"
        )

    @staticmethod
    def _ensure_active(application: Application) -> None:
        if application.is_withdrawn:
            raise InvalidWorkflowTransition("A withdrawn application cannot be changed")

    def _authorize_scope(
        self,
        application: Application,
        actor: User,
        action: WorkflowAction,
    ) -> None:
        if actor.role == Role.SUPER_ADMIN:
            return

        # APH committees are constituted nationally and read every case file
        # referred to them; the transition table still limits which actions
        # each committee may perform.
        if actor.role in {
            Role.SHC_MEMBER,
            Role.SAC_MEMBER,
            Role.EXECUTIVE_COMMITTEE_MEMBER,
            Role.COMPLAINT_SCRUTINY_MEMBER,
        }:
            return

        if actor.role == Role.INSTITUTION_ADMIN:
            if actor.institution_id is None or application.institution_id != actor.institution_id:
                raise WorkflowPermissionError(
                    "You do not have access to this application"
                )
            return

        if actor.role == Role.REGULATION_BUREAU_OFFICER:
            if actor.region is not None and application.institution.region != actor.region:
                raise WorkflowPermissionError(
                    "You do not have access to this application"
                )
            return

        if actor.role == Role.REGIONAL_OFFICER:
            if actor.region is None or application.institution.region != actor.region:
                raise WorkflowPermissionError(
                    "You do not have access to this application"
                )
            return

        if actor.role == Role.SCRUTINY_COMMITTEE_MEMBER:
            assigned = application.assigned_officer_id == actor.id
            in_region = (
                actor.region is not None and application.institution.region == actor.region
            )
            if not assigned and not in_region:
                raise WorkflowPermissionError(
                    "You do not have access to this application"
                )
            if action in _ASSIGNED_SCRUTINY_ACTIONS and not assigned:
                raise WorkflowPermissionError(
                    "Only the assigned scrutiny officer can perform this action"
                )
            return

        if actor.role == Role.EVC_MEMBER:
            if action != WorkflowAction.SUBMIT_INSPECTION_REPORT:
                raise WorkflowPermissionError(
                    "Inspection committee members can only submit an inspection report"
                )
            if not self._has_inspection_for(application.id, actor.id):
                raise WorkflowPermissionError(
                    "No inspection is assigned to you for this application"
                )
            return

        raise WorkflowPermissionError("You do not have permission to perform this action")

    def _may_perform(
        self,
        application: Application,
        actor: User,
        transition: Transition,
    ) -> bool:
        if actor.role not in transition.roles:
            return False

        if actor.role == Role.INSTITUTION_ADMIN:
            if actor.institution_id is None or application.institution_id != actor.institution_id:
                return False
        elif actor.role == Role.REGULATION_BUREAU_OFFICER:
            if actor.region is not None and application.institution.region != actor.region:
                return False
        elif actor.role == Role.REGIONAL_OFFICER:
            if actor.region is None or application.institution.region != actor.region:
                return False
        elif actor.role == Role.SCRUTINY_COMMITTEE_MEMBER:
            assigned = application.assigned_officer_id == actor.id
            in_region = (
                actor.region is not None and application.institution.region == actor.region
            )
            if not assigned and not in_region:
                return False
            if transition.action in _ASSIGNED_SCRUTINY_ACTIONS and not assigned:
                return False
        elif actor.role == Role.EVC_MEMBER:
            if transition.action != WorkflowAction.SUBMIT_INSPECTION_REPORT:
                return False
            if not self._has_inspection_for(application.id, actor.id):
                return False

        if transition.action == WorkflowAction.RESPOND_DEFICIENCY:
            return self._has_deficiency_with_status(
                application.id, DeficiencyStatus.OPEN
            )
        if transition.action == WorkflowAction.CLOSE_DEFICIENCY:
            return self._has_deficiency_with_status(
                application.id, DeficiencyStatus.RESPONDED
            )
        if transition.action == WorkflowAction.SCHEDULE_INSPECTION:
            return not self._has_inspection_with_status(
                application.id, InspectionStatus.SCHEDULED
            )
        if transition.action == WorkflowAction.SEND_TO_COMMITTEE:
            return self._has_inspection_with_status(
                application.id, InspectionStatus.COMPLETED
            )
        return True

    def _has_inspection_for(self, application_id: uuid.UUID, committee_id: uuid.UUID) -> bool:
        inspection_id = self._db.scalar(
            select(Inspection.id)
            .where(
                Inspection.application_id == application_id,
                Inspection.committee_id == committee_id,
            )
            .limit(1)
        )
        return inspection_id is not None

    def _has_inspection_with_status(
        self,
        application_id: uuid.UUID,
        status: InspectionStatus,
    ) -> bool:
        inspection_id = self._db.scalar(
            select(Inspection.id)
            .where(
                Inspection.application_id == application_id,
                Inspection.status == status,
            )
            .limit(1)
        )
        return inspection_id is not None

    def _has_deficiency_with_status(
        self,
        application_id: uuid.UUID,
        status: DeficiencyStatus,
    ) -> bool:
        deficiency_id = self._db.scalar(
            select(Deficiency.id)
            .where(
                Deficiency.application_id == application_id,
                Deficiency.status == status,
            )
            .limit(1)
        )
        return deficiency_id is not None

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def _dispatch(
        self,
        application: Application,
        actor: User,
        action: WorkflowAction,
        transition: Transition,
        payload: WorkflowActionRequest,
        before: dict[str, Any],
        events: list[WorkflowEvent],
        request: Any | None,
    ) -> str:
        handlers = {
            WorkflowAction.SUBMIT: self._apply_submit,
            WorkflowAction.AUTO_ASSIGN: self._apply_auto_assign,
            WorkflowAction.VERIFY_DOCUMENTS: self._apply_verify_documents,
            WorkflowAction.START_SCRUTINY: self._apply_start_scrutiny,
            WorkflowAction.RAISE_DEFICIENCY: self._apply_raise_deficiency,
            WorkflowAction.RESPOND_DEFICIENCY: self._apply_respond_deficiency,
            WorkflowAction.CLOSE_DEFICIENCY: self._apply_close_deficiency,
            WorkflowAction.SCHEDULE_INSPECTION: self._apply_schedule_inspection,
            WorkflowAction.SUBMIT_INSPECTION_REPORT: self._apply_submit_inspection_report,
            WorkflowAction.SEND_TO_COMMITTEE: self._apply_send_to_committee,
            WorkflowAction.APPROVE: self._apply_approve,
            WorkflowAction.CONDITIONALLY_APPROVE: self._apply_conditionally_approve,
            WorkflowAction.REJECT: self._apply_reject,
            WorkflowAction.WITHDRAW: self._apply_withdraw,
            WorkflowAction.REOPEN: self._apply_reopen,
        }
        return handlers[action](
            application,
            actor,
            transition,
            payload,
            before,
            events,
            request,
        )

    def _apply_submit(
        self,
        application: Application,
        actor: User,
        transition: Transition,
        payload: WorkflowActionRequest,
        before: dict[str, Any],
        events: list[WorkflowEvent],
        request: Any | None,
    ) -> str:
        comment = payload.comment or "Application submitted by the institution"
        if application.submitted_at is None:
            application.submitted_at = self._clock.now()
        application.locked_at = self._clock.now()
        if application.portal_application_no is None:
            application.portal_application_no = next_portal_application_no(
                self._db, application.academic_year
            )
        self._record_transition(
            application,
            actor,
            transition.action,
            transition,
            before=before,
            comment=comment,
            details=None,
            events=events,
            request=request,
        )

        officer = self._assignment_strategy.choose(self._db, application)
        if officer is None:
            return (
                "Application submitted. No scrutiny officer is currently available; "
                "a regional head can assign one when an officer is added."
            )

        auto_transition = self._transition_for(
            WorkflowAction.AUTO_ASSIGN, application.status
        )
        application.assigned_officer_id = officer.id
        auto_before = self._snapshot(application)
        self._record_transition(
            application,
            actor,
            WorkflowAction.AUTO_ASSIGN,
            auto_transition,
            before=auto_before,
            comment=f"Auto-assigned to {officer.name}",
            details={
                "officer_id": str(officer.id),
                "officer_name": officer.name,
                "strategy": type(self._assignment_strategy).__name__,
            },
            events=events,
            request=request,
        )
        return f"Application submitted and assigned to {officer.name}"

    def _apply_auto_assign(
        self,
        application: Application,
        actor: User,
        transition: Transition,
        payload: WorkflowActionRequest,
        before: dict[str, Any],
        events: list[WorkflowEvent],
        request: Any | None,
    ) -> str:
        officer = self._resolve_officer(application, payload.officer_id)
        if officer is None:
            raise WorkflowValidationError(
                "No active scrutiny officer is available in this institution's region"
            )

        application.assigned_officer_id = officer.id
        self._record_transition(
            application,
            actor,
            transition.action,
            transition,
            before=before,
            comment=payload.comment or f"Assigned to {officer.name}",
            details={
                "officer_id": str(officer.id),
                "officer_name": officer.name,
            },
            events=events,
            request=request,
        )
        return f"Application assigned to {officer.name}"

    def _apply_verify_documents(
        self,
        application: Application,
        actor: User,
        transition: Transition,
        payload: WorkflowActionRequest,
        before: dict[str, Any],
        events: list[WorkflowEvent],
        request: Any | None,
    ) -> str:
        self._record_transition(
            application,
            actor,
            transition.action,
            transition,
            before=before,
            comment=payload.comment or "Documents verified and scrutiny opened",
            details={"verified_by": str(actor.id)},
            events=events,
            request=request,
        )
        return "Documents verified. The application is now in scrutiny."

    def _apply_start_scrutiny(
        self,
        application: Application,
        actor: User,
        transition: Transition,
        payload: WorkflowActionRequest,
        before: dict[str, Any],
        events: list[WorkflowEvent],
        request: Any | None,
    ) -> str:
        assignment_note: str | None = None
        if application.assigned_officer_id is None:
            officer = self._resolve_officer(application, payload.officer_id)
            if officer is not None:
                application.assigned_officer_id = officer.id
                assignment_note = f" Assigned to {officer.name}."

        details: dict[str, Any] = {"started_by": str(actor.id)}
        if application.assigned_officer_id is not None:
            details["officer_id"] = str(application.assigned_officer_id)

        self._record_transition(
            application,
            actor,
            transition.action,
            transition,
            before=before,
            comment=payload.comment or "Scrutiny started",
            details=details,
            events=events,
            request=request,
        )
        return f"Scrutiny started.{assignment_note or ''}".strip()

    def _apply_raise_deficiency(
        self,
        application: Application,
        actor: User,
        transition: Transition,
        payload: WorkflowActionRequest,
        before: dict[str, Any],
        events: list[WorkflowEvent],
        request: Any | None,
    ) -> str:
        if not payload.deficiencies:
            raise WorkflowValidationError("At least one deficiency is required")

        today = self._clock.now().date()
        deficiencies: list[Deficiency] = []
        for item in payload.deficiencies:
            if item.due_date < today:
                raise WorkflowValidationError("Deficiency due dates must not be in the past")
            deficiency = Deficiency(
                application_id=application.id,
                category=item.category.strip(),
                description=item.description.strip(),
                raised_by=actor.id,
                status=DeficiencyStatus.OPEN,
                due_date=item.due_date,
            )
            self._db.add(deficiency)
            deficiencies.append(deficiency)

        self._db.flush()
        self._record_transition(
            application,
            actor,
            transition.action,
            transition,
            before=before,
            comment=payload.comment
            or f"{len(deficiencies)} deficiency item(s) raised",
            details={
                "deficiency_ids": [str(item.id) for item in deficiencies],
                "count": len(deficiencies),
            },
            events=events,
            request=request,
        )
        return f"{len(deficiencies)} deficiency item(s) raised. The institution has been notified."

    def _apply_respond_deficiency(
        self,
        application: Application,
        actor: User,
        transition: Transition,
        payload: WorkflowActionRequest,
        before: dict[str, Any],
        events: list[WorkflowEvent],
        request: Any | None,
    ) -> str:
        deficiencies = self._db.scalars(
            select(Deficiency)
            .where(Deficiency.application_id == application.id)
            .order_by(Deficiency.created_at.asc())
        ).all()
        open_items = {
            deficiency.id: deficiency
            for deficiency in deficiencies
            if deficiency.status == DeficiencyStatus.OPEN
        }
        if not open_items:
            raise WorkflowValidationError("There are no open deficiencies to respond to")
        if not payload.responses:
            raise WorkflowValidationError("A response is required for every open deficiency")

        response_map: dict[uuid.UUID, Any] = {}
        for response in payload.responses:
            if response.deficiency_id in response_map:
                raise WorkflowValidationError("Each deficiency can only be answered once")
            response_map[response.deficiency_id] = response

        missing = set(open_items) - set(response_map)
        extra = set(response_map) - set(open_items)
        if missing:
            raise WorkflowValidationError(
                "Respond to every open deficiency in one submission"
            )
        if extra:
            raise WorkflowValidationError(
                "One or more deficiencies are not open for this application"
            )

        responded_at = self._clock.now()
        document_ids: list[str] = []
        for deficiency_id, response in response_map.items():
            deficiency = open_items[deficiency_id]
            if response.document_id is not None:
                document = self._db.scalar(
                    select(Document).where(
                        Document.id == response.document_id,
                        Document.application_id == application.id,
                    )
                )
                if document is None:
                    raise WorkflowValidationError(
                        "The selected response document does not belong to this application"
                    )
                document_ids.append(str(document.id))
            deficiency.response_text = response.response_text.strip()
            deficiency.response_document_id = response.document_id
            deficiency.responded_at = responded_at
            deficiency.status = DeficiencyStatus.RESPONDED

        self._db.flush()
        self._record_transition(
            application,
            actor,
            transition.action,
            transition,
            before=before,
            comment=payload.comment
            or f"Institution responded to {len(response_map)} deficiency item(s)",
            details={
                "deficiency_ids": [str(item) for item in response_map],
                "document_ids": document_ids,
            },
            events=events,
            request=request,
        )
        return "Deficiency responses submitted. An officer will review them."

    def _apply_close_deficiency(
        self,
        application: Application,
        actor: User,
        transition: Transition,
        payload: WorkflowActionRequest,
        before: dict[str, Any],
        events: list[WorkflowEvent],
        request: Any | None,
    ) -> str:
        if payload.deficiency_id is None:
            raise WorkflowValidationError("Select the deficiency to close")

        deficiency = self._db.scalar(
            select(Deficiency).where(
                Deficiency.id == payload.deficiency_id,
                Deficiency.application_id == application.id,
            )
        )
        if deficiency is None:
            raise WorkflowNotFoundError("Deficiency not found for this application")
        if deficiency.status != DeficiencyStatus.RESPONDED:
            raise WorkflowValidationError("Only a responded deficiency can be closed")

        deficiency.status = DeficiencyStatus.CLOSED
        deficiency.closed_at = self._clock.now()
        self._db.flush()

        remaining = self._db.scalar(
            select(func.count(Deficiency.id)).where(
                Deficiency.application_id == application.id,
                Deficiency.status != DeficiencyStatus.CLOSED,
            )
        )
        remaining_count = int(remaining or 0)
        details = {
            "deficiency_id": str(deficiency.id),
            "remaining": remaining_count,
        }

        if remaining_count == 0:
            self._record_transition(
                application,
                actor,
                transition.action,
                transition,
                before=before,
                comment=payload.comment or "All deficiencies closed; returned to scrutiny",
                details=details,
                events=events,
                request=request,
            )
            return "All deficiencies closed. The application has returned to scrutiny."

        self._record_event_only(
            application,
            actor,
            transition.action,
            before=before,
            comment=payload.comment
            or f"Deficiency closed; {remaining_count} item(s) still open",
            details=details,
            events=events,
            request=request,
        )
        return f"Deficiency closed. {remaining_count} item(s) still need review."

    def _apply_schedule_inspection(
        self,
        application: Application,
        actor: User,
        transition: Transition,
        payload: WorkflowActionRequest,
        before: dict[str, Any],
        events: list[WorkflowEvent],
        request: Any | None,
    ) -> str:
        if payload.committee_id is None or payload.scheduled_on is None:
            raise WorkflowValidationError(
                "An inspection committee member and visit date are required"
            )
        if payload.scheduled_on.tzinfo is None:
            raise WorkflowValidationError("The inspection date must include a timezone")
        scheduled_on = payload.scheduled_on.astimezone(UTC)
        if scheduled_on <= self._clock.now():
            raise WorkflowValidationError("The inspection must be scheduled in the future")
        if self._has_inspection_with_status(application.id, InspectionStatus.SCHEDULED):
            raise InvalidWorkflowTransition("An inspection is already scheduled")

        committee = self._db.get(User, payload.committee_id)
        if (
            committee is None
            or not committee.is_active
            or committee.role != Role.EVC_MEMBER
        ):
            raise WorkflowValidationError(
                "Select an active inspection committee member"
            )
        if committee.region != application.institution.region:
            raise WorkflowValidationError(
                "The committee member must belong to the institution's region"
            )

        inspection = Inspection(
            application_id=application.id,
            committee_id=committee.id,
            scheduled_on=scheduled_on,
            status=InspectionStatus.SCHEDULED,
        )
        self._db.add(inspection)
        self._db.flush()

        self._record_transition(
            application,
            actor,
            transition.action,
            transition,
            before=before,
            comment=payload.comment or f"Inspection scheduled with {committee.name}",
            details={
                "inspection_id": str(inspection.id),
                "committee_id": str(committee.id),
                "committee_name": committee.name,
                "scheduled_on": scheduled_on.isoformat(),
            },
            events=events,
            request=request,
        )
        return f"Inspection scheduled with {committee.name}."

    def _apply_submit_inspection_report(
        self,
        application: Application,
        actor: User,
        transition: Transition,
        payload: WorkflowActionRequest,
        before: dict[str, Any],
        events: list[WorkflowEvent],
        request: Any | None,
    ) -> str:
        if payload.report is None:
            raise WorkflowValidationError("An inspection report is required")

        query = select(Inspection).where(
            Inspection.application_id == application.id,
            Inspection.status == InspectionStatus.SCHEDULED,
        )
        if actor.role == Role.EVC_MEMBER:
            query = query.where(Inspection.committee_id == actor.id)
        inspection = self._db.scalar(
            query.order_by(Inspection.scheduled_on.desc()).limit(1)
        )
        if inspection is None:
            if actor.role == Role.EVC_MEMBER:
                raise WorkflowPermissionError(
                    "No scheduled inspection is assigned to you for this application"
                )
            raise InvalidWorkflowTransition("No scheduled inspection is available")

        inspection.report = payload.report.model_dump(mode="json")
        inspection.recommendation = payload.report.recommendation.value
        inspection.status = InspectionStatus.COMPLETED
        self._db.flush()

        self._record_transition(
            application,
            actor,
            transition.action,
            transition,
            before=before,
            comment=payload.comment or "Inspection report submitted",
            details={
                "inspection_id": str(inspection.id),
                "recommendation": payload.report.recommendation.value,
            },
            events=events,
            request=request,
        )
        return (
            "Inspection report submitted. The regional head can now send the case "
            "to committee review."
        )

    def _apply_send_to_committee(
        self,
        application: Application,
        actor: User,
        transition: Transition,
        payload: WorkflowActionRequest,
        before: dict[str, Any],
        events: list[WorkflowEvent],
        request: Any | None,
    ) -> str:
        inspection = self._db.scalar(
            select(Inspection)
            .where(
                Inspection.application_id == application.id,
                Inspection.status == InspectionStatus.COMPLETED,
            )
            .order_by(Inspection.updated_at.desc())
            .limit(1)
        )
        if inspection is None:
            raise InvalidWorkflowTransition(
                "A completed inspection report is required before committee review"
            )

        self._record_transition(
            application,
            actor,
            transition.action,
            transition,
            before=before,
            comment=payload.comment or "Sent to committee review",
            details={"inspection_id": str(inspection.id)},
            events=events,
            request=request,
        )
        return "Application sent to committee review."

    def _apply_approve(
        self,
        application: Application,
        actor: User,
        transition: Transition,
        payload: WorkflowActionRequest,
        before: dict[str, Any],
        events: list[WorkflowEvent],
        request: Any | None,
    ) -> str:
        return self._apply_decision(
            application,
            actor,
            transition,
            payload,
            before,
            events,
            request,
            outcome=ApplicationStatus.APPROVED,
        )

    def _apply_conditionally_approve(
        self,
        application: Application,
        actor: User,
        transition: Transition,
        payload: WorkflowActionRequest,
        before: dict[str, Any],
        events: list[WorkflowEvent],
        request: Any | None,
    ) -> str:
        return self._apply_decision(
            application,
            actor,
            transition,
            payload,
            before,
            events,
            request,
            outcome=ApplicationStatus.CONDITIONALLY_APPROVED,
        )

    def _apply_reject(
        self,
        application: Application,
        actor: User,
        transition: Transition,
        payload: WorkflowActionRequest,
        before: dict[str, Any],
        events: list[WorkflowEvent],
        request: Any | None,
    ) -> str:
        return self._apply_decision(
            application,
            actor,
            transition,
            payload,
            before,
            events,
            request,
            outcome=ApplicationStatus.REJECTED,
        )

    def _apply_decision(
        self,
        application: Application,
        actor: User,
        transition: Transition,
        payload: WorkflowActionRequest,
        before: dict[str, Any],
        events: list[WorkflowEvent],
        request: Any | None,
        *,
        outcome: ApplicationStatus,
    ) -> str:
        if outcome == ApplicationStatus.CONDITIONALLY_APPROVED:
            if not payload.conditions or not payload.conditions.strip():
                raise WorkflowValidationError(
                    "Written conditions are required for conditional approval"
                )

        decided_at = self._clock.now()
        decision = {
            "outcome": outcome.value,
            "decided_by": str(actor.id),
            "decided_by_name": actor.name,
            "decided_at": decided_at.isoformat(),
            "comment": payload.comment,
            "conditions": (
                payload.conditions
                if outcome == ApplicationStatus.CONDITIONALLY_APPROVED
                else None
            ),
        }
        data = copy.deepcopy(application.data) if isinstance(application.data, dict) else {}
        data["decision"] = decision
        application.data = data

        label = {
            ApplicationStatus.APPROVED: "approved",
            ApplicationStatus.CONDITIONALLY_APPROVED: "conditionally approved",
            ApplicationStatus.REJECTED: "rejected",
        }[outcome]

        self._record_transition(
            application,
            actor,
            transition.action,
            transition,
            before=before,
            comment=payload.comment or f"Application {label}",
            details=decision,
            events=events,
            request=request,
        )
        return f"Application {label}."

    def _apply_withdraw(
        self,
        application: Application,
        actor: User,
        transition: Transition,
        payload: WorkflowActionRequest,
        before: dict[str, Any],
        events: list[WorkflowEvent],
        request: Any | None,
    ) -> str:
        application.is_withdrawn = True
        application.sla_due_at = None
        self._record_event_only(
            application,
            actor,
            transition.action,
            before=before,
            comment=payload.comment or "Application withdrawn by the institution",
            details={"reason": payload.comment},
            events=events,
            request=request,
        )
        return "Application withdrawn. The workflow history has been preserved."

    def _apply_reopen(
        self,
        application: Application,
        actor: User,
        transition: Transition,
        payload: WorkflowActionRequest,
        before: dict[str, Any],
        events: list[WorkflowEvent],
        request: Any | None,
    ) -> str:
        if application.reopen_count >= 1:
            raise WorkflowValidationError(
                "An application can be reopened only once (APH 2.3.3d-e)."
            )
        application.reopen_count += 1
        application.locked_at = None
        application.submitted_at = None
        application.assigned_officer_id = None
        self._record_transition(
            application,
            actor,
            transition.action,
            transition,
            before=before,
            comment=payload.comment or "Application reopened by the Regulation Bureau",
            details={
                "reopen_count": application.reopen_count,
                "trust_resolution_required": "Format 3",
            },
            events=events,
            request=request,
        )
        application.sla_due_at = None
        return (
            "Application reopened once. Correct the data, pay the new TER if required "
            "and resubmit before the Public Notice last date."
        )

    # ------------------------------------------------------------------
    # Event and audit primitives
    # ------------------------------------------------------------------
    def _record_transition(
        self,
        application: Application,
        actor: User,
        action: WorkflowAction,
        transition: Transition,
        *,
        before: dict[str, Any],
        comment: str | None,
        details: dict[str, Any] | None,
        events: list[WorkflowEvent],
        request: Any | None,
    ) -> WorkflowEvent:
        now = self._clock.now()
        previous_status = application.status
        if transition.to_status is not None:
            application.status = transition.to_status
            application.current_stage = transition.stage or _stage_for(transition.to_status)
            application.stage_entered_at = now
            application.sla_due_at = self._sla_due_at(application.current_stage, now)

        return self._write_event(
            application,
            actor,
            action,
            before=before,
            comment=comment,
            details=details,
            events=events,
            request=request,
            previous_status=previous_status,
        )

    def _record_event_only(
        self,
        application: Application,
        actor: User,
        action: WorkflowAction,
        *,
        before: dict[str, Any],
        comment: str | None,
        details: dict[str, Any] | None,
        events: list[WorkflowEvent],
        request: Any | None,
    ) -> WorkflowEvent:
        return self._write_event(
            application,
            actor,
            action,
            before=before,
            comment=comment,
            details=details,
            events=events,
            request=request,
            previous_status=application.status,
        )

    def _write_event(
        self,
        application: Application,
        actor: User,
        action: WorkflowAction,
        *,
        before: dict[str, Any],
        comment: str | None,
        details: dict[str, Any] | None,
        events: list[WorkflowEvent],
        request: Any | None,
        previous_status: ApplicationStatus,
    ) -> WorkflowEvent:
        event = WorkflowEvent(
            application_id=application.id,
            from_status=previous_status,
            to_status=application.status,
            actor_id=actor.id,
            action=action.value,
            comment=comment,
            details=details,
            apH_clause=self._transition_for(action, previous_status).apH_clause,
            created_at=self._clock.now(),
        )
        self._db.add(event)
        self._db.flush()
        self._db.refresh(event)
        events.append(event)
        self._audit.log(
            actor,
            f"workflow.{action.value}",
            "Application",
            application.id,
            before=before,
            after=self._snapshot(application),
            request=request,
        )
        return event

    def _sla_due_at(self, stage: WorkflowStage, now: datetime) -> datetime | None:
        if stage == WorkflowStage.COMPLETED:
            return None
        config = self._db.scalar(select(SLAConfig).where(SLAConfig.stage == stage))
        if config is None:
            raise WorkflowConfigurationError(
                f"SLA configuration for the {stage.value} stage is missing"
            )
        return now + timedelta(days=config.duration_days)

    def _resolve_officer(
        self,
        application: Application,
        officer_id: uuid.UUID | None,
    ) -> User | None:
        if officer_id is not None:
            officer = self._db.get(User, officer_id)
            if (
                officer is None
                or not officer.is_active
                or officer.role != Role.SCRUTINY_COMMITTEE_MEMBER
            ):
                raise WorkflowValidationError("Select an active scrutiny officer")
            if officer.region != application.institution.region:
                raise WorkflowValidationError(
                    "The scrutiny officer must belong to the institution's region"
                )
            return officer
        return self._assignment_strategy.choose(self._db, application)

    @staticmethod
    def _snapshot(application: Application) -> dict[str, Any]:
        data = application.data if isinstance(application.data, dict) else {}
        return {
            "status": application.status.value,
            "current_stage": application.current_stage.value,
            "assigned_officer_id": (
                str(application.assigned_officer_id)
                if application.assigned_officer_id is not None
                else None
            ),
            "stage_entered_at": (
                application.stage_entered_at.isoformat()
                if application.stage_entered_at is not None
                else None
            ),
            "sla_due_at": (
                application.sla_due_at.isoformat()
                if application.sla_due_at is not None
                else None
            ),
            "is_withdrawn": application.is_withdrawn,
            "is_escalated": application.is_escalated,
            "decision": data.get("decision"),
        }


def _stage_for(status: ApplicationStatus) -> WorkflowStage:
    """Map a primary status to the stage used for SLA lookup."""
    if status in {ApplicationStatus.DRAFT, ApplicationStatus.SUBMITTED}:
        return WorkflowStage.APPLICATION
    if status == ApplicationStatus.DOCUMENT_VERIFICATION:
        return WorkflowStage.DOCUMENT_VERIFICATION
    if status == ApplicationStatus.SCRUTINY:
        return WorkflowStage.SCRUTINY
    if status in {
        ApplicationStatus.DEFICIENCY_RAISED,
        ApplicationStatus.DEFICIENCY_RESPONDED,
    }:
        return WorkflowStage.DEFICIENCY
    if status in {
        ApplicationStatus.INSPECTION_SCHEDULED,
        ApplicationStatus.INSPECTION_DONE,
    }:
        return WorkflowStage.INSPECTION
    if status == ApplicationStatus.COMMITTEE_REVIEW:
        return WorkflowStage.COMMITTEE_REVIEW
    return WorkflowStage.COMPLETED
