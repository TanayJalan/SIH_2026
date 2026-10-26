"""Database-driven approval workflow state machine.

The legal state machine is **data**: ``workflow_definitions``,
``workflow_states`` and ``workflow_transitions`` hold every state, every edge,
the roles allowed to take it, the guards that must pass and the side effects it
triggers (APH Annexure-7, 1.8-1.11, 2.23-2.25). This module only interprets
that data:

1. load the definition that the application's routing row points at;
2. resolve the candidate edges for ``(current status, action)`` by priority;
3. check the role, the record-level scope and the named guards;
4. run the named side effects;
5. move the status, refresh the SLA clock, and write exactly one
   :class:`~app.models.workflow.WorkflowEvent` plus one ``AuditLog`` row.

No endpoint assigns ``Application.status`` directly, and no guard or effect is
looked up by anything other than the registered name in seed data, so an
administrator can re-order or disable an edge without a deployment while a
malicious database row cannot execute arbitrary code.

SLA durations, committee compositions, deadlines and alert templates are read
from their own configuration tables; nothing in this module hard-codes an APH
duration.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.core.clock import SimulatedClock
from app.core.config import get_settings
from app.models.application import Application
from app.models.application_type_route import ApplicationTypeRoute
from app.models.enums import (
    ApplicationStatus,
    Role,
    WorkflowAction,
    WorkflowStage,
)
from app.models.inspection import Inspection
from app.models.sla import SLAConfig
from app.models.user import User
from app.models.workflow import WorkflowEvent
from app.models.workflow_definition import (
    WorkflowDefinition,
    WorkflowState,
    WorkflowTransition,
)
from app.schemas.workflow import WorkflowActionRequest
from app.services import alerts
from app.services.audit import AuditService
from app.services.workflow_context import (
    ActionRequirement,
    AssignmentStrategy,
    Transition,
    TransitionContext,
)
from app.services.workflow_errors import (
    InvalidWorkflowTransition,
    WorkflowConfigurationError,
    WorkflowError,
    WorkflowNotFoundError,
    WorkflowPermissionError,
    WorkflowValidationError,
)
from app.services.workflow_guards import PAYLOAD_GUARDS, evaluate_guard

__all__ = [
    "AssignmentStrategy",
    "InvalidWorkflowTransition",
    "LowestLoadAssignmentStrategy",
    "Transition",
    "WorkflowConfigurationError",
    "WorkflowError",
    "WorkflowNotFoundError",
    "WorkflowPermissionError",
    "WorkflowResult",
    "WorkflowService",
    "WorkflowValidationError",
]

_TERMINAL_STATUSES = frozenset(
    {
        ApplicationStatus.ACTIVE_LOA,
        ApplicationStatus.ACTIVE_EOA,
        ApplicationStatus.CANCELLED,
        ApplicationStatus.FINAL_LOD,
        ApplicationStatus.FINAL_LOR,
        ApplicationStatus.WITHDRAWN,
        # Legacy pre-APH outcomes kept for historical rows.
        ApplicationStatus.APPROVED,
        ApplicationStatus.REJECTED,
    }
)

_OPEN_STATUSES = frozenset(
    status for status in ApplicationStatus if status not in _TERMINAL_STATUSES
)

# Scrutiny actions that only the officer actually assigned to the file may take.
_ASSIGNED_SCRUTINY_ACTIONS = frozenset(
    {
        WorkflowAction.SCRUTINY_RECOMMEND,
        WorkflowAction.COMMUNICATE_DEFICIENCY,
        WorkflowAction.RE_SCRUTINY_VERIFY,
    }
)

# Committees that are constituted nationally and read every case file referred
# to them; the transition rows still limit which actions each one may perform.
_NATIONAL_ROLES = frozenset(
    {
        Role.SHC_MEMBER,
        Role.SAC_MEMBER,
        Role.EXECUTIVE_COMMITTEE_MEMBER,
        Role.COMPLAINT_SCRUTINY_MEMBER,
    }
)


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


@dataclass(frozen=True, slots=True)
class _LoadedDefinition:
    """One workflow definition with its states and edges, loaded once."""

    definition: WorkflowDefinition
    states: dict[str, WorkflowState]
    transitions: tuple[WorkflowTransition, ...]

    def rows(self, action: WorkflowAction, status: ApplicationStatus) -> list[WorkflowTransition]:
        """Return the candidate edges for one action, highest priority first."""
        candidates = [
            row
            for row in self.transitions
            if row.action == action.value and row.from_state == status.value
        ]
        candidates.sort(key=lambda row: row.priority)
        return candidates


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
        settings: Any | None = None,
    ) -> None:
        self._db = db
        self._audit = audit
        self._clock = clock
        self._assignment_strategy = assignment_strategy or LowestLoadAssignmentStrategy()
        self._notifier = notifier
        self._notifications = notifications
        self._settings = settings

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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
        :class:`WorkflowPermissionError` (HTTP 403), bad payloads raise
        :class:`WorkflowValidationError` (HTTP 422) and missing configuration
        raises :class:`WorkflowConfigurationError` (HTTP 503).
        """
        payload = payload or WorkflowActionRequest()
        self._ensure_active(application)
        definition = self._load(application)
        rows = definition.rows(action, application.status)
        if not rows:
            raise InvalidWorkflowTransition(
                f"Action '{action.value}' is not allowed while the application is "
                f"{application.status.value}"
            )

        self._authorize_scope(application, actor, action)
        if enforce_role and not self._role_allowed(actor, rows):
            raise WorkflowPermissionError(
                f"{action.value} is not permitted for the {actor.role.value} role"
            )

        row, context = self._select(definition, rows, application, actor, payload, request)
        before = self._snapshot(application)
        previous_status = application.status
        events: list[WorkflowEvent] = []

        try:
            self._run_effects(row, context)
            now = self._clock.now()
            target = definition.states.get(row.to_state)
            if target is None:
                raise WorkflowConfigurationError(
                    f"Workflow {definition.definition.key} has no state {row.to_state!r}."
                )
            application.status = ApplicationStatus(row.to_state)
            application.current_stage = WorkflowStage(target.stage)
            application.stage_entered_at = now
            application.sla_due_at = (
                None
                if target.is_terminal
                else self._sla_due_at(
                    WorkflowStage(row.sla_stage or target.stage),
                    now,
                )
            )

            message = self._message(row, context)
            event = WorkflowEvent(
                application_id=application.id,
                from_status=previous_status,
                to_status=application.status,
                actor_id=actor.id,
                action=action.value,
                comment=message,
                details=context.details or None,
                apH_clause=row.apH_clause,
                created_at=now,
            )
            self._db.add(event)
            self._db.flush()
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
        """Return one transition per action the actor may perform right now.

        Guards that need the action payload are skipped: the point of this call
        is to tell the UI which buttons to render, not to pre-validate a form.
        """
        if application.is_withdrawn:
            return []

        definition = self._load(application)
        allowed: list[Transition] = []
        seen: set[str] = set()
        for row in sorted(definition.transitions, key=lambda item: item.priority):
            if row.from_state != application.status.value or row.action in seen:
                continue
            try:
                action = WorkflowAction(row.action)
            except ValueError:  # pragma: no cover - seed data is validated
                continue
            if actor.role.value not in (row.allowed_roles or []):
                continue
            if not self._scope_ok(application, actor, action):
                continue
            transition = self._transition(definition, row)
            context = self._context(
                application,
                actor,
                transition,
                WorkflowActionRequest(),
                None,
                definition.definition,
            )
            if any(
                evaluate_guard(name, context)
                for name in row.guard_expr
                if name not in PAYLOAD_GUARDS
            ):
                continue
            seen.add(row.action)
            allowed.append(transition)
        return allowed

    # ------------------------------------------------------------------
    # Definition loading
    # ------------------------------------------------------------------

    def _load(self, application: Application) -> _LoadedDefinition:
        route = self._db.scalar(
            select(ApplicationTypeRoute).where(
                ApplicationTypeRoute.type == application.application_type
            )
        )
        if route is None:
            raise WorkflowConfigurationError(
                f"Application type {application.application_type!r} is not configured."
            )
        if route.not_implemented:
            raise WorkflowConfigurationError(
                route.not_implemented_note
                or f"Application type {application.application_type!r} is not implemented."
            )
        if not route.workflow_key:
            raise WorkflowConfigurationError(
                f"Application type {application.application_type!r} has no workflow."
            )

        definition = self._db.scalar(
            select(WorkflowDefinition).where(
                WorkflowDefinition.key == route.workflow_key,
                WorkflowDefinition.is_active.is_(True),
            )
        )
        if definition is None:
            raise WorkflowConfigurationError(
                f"Workflow {route.workflow_key!r} is not configured or is inactive."
            )

        states = {
            state.code: state
            for state in self._db.scalars(
                select(WorkflowState).where(WorkflowState.definition_id == definition.id)
            )
        }
        transitions = tuple(
            self._db.scalars(
                select(WorkflowTransition)
                .where(WorkflowTransition.definition_id == definition.id)
                .order_by(
                    WorkflowTransition.priority.asc(),
                    WorkflowTransition.created_at.asc(),
                )
            )
        )
        return _LoadedDefinition(
            definition=definition,
            states=states,
            transitions=transitions,
        )

    def _transition(self, definition: _LoadedDefinition, row: WorkflowTransition) -> Transition:
        state = definition.states.get(row.to_state)
        return Transition(
            action=WorkflowAction(row.action),
            from_statuses=frozenset({ApplicationStatus(row.from_state)}),
            to_status=ApplicationStatus(row.to_state),
            roles=frozenset(Role(name) for name in (row.allowed_roles or [])),
            stage=WorkflowStage(state.stage) if state is not None else None,
            label=row.label,
            description=row.description,
            apH_clause=row.apH_clause,
            guards=tuple(row.guard_expr or ()),
            effects=tuple(row.side_effects or ()),
            requires=_requirement(row.requires),
            tone=_tone(row.tone),
            priority=row.priority,
            needs_verification=row.needs_verification,
        )

    def _context(
        self,
        application: Application,
        actor: User,
        transition: Transition,
        payload: WorkflowActionRequest,
        request: Any | None = None,
        definition: WorkflowDefinition | None = None,
    ) -> TransitionContext:
        settings = self._settings
        if settings is None and request is not None:
            settings = getattr(
                getattr(getattr(request, "app", None), "state", None),
                "settings",
                None,
            )
        return TransitionContext(
            db=self._db,
            application=application,
            actor=actor,
            transition=transition,
            payload=payload,
            clock=self._clock,
            audit=self._audit,
            request=request,
            definition=definition,
            settings=settings or get_settings(),
            assignment_strategy=self._assignment_strategy,
            notifications=self._notifications,
        )

    # ------------------------------------------------------------------
    # Candidate selection
    # ------------------------------------------------------------------

    def _select(
        self,
        definition: _LoadedDefinition,
        rows: list[WorkflowTransition],
        application: Application,
        actor: User,
        payload: WorkflowActionRequest,
        request: Any | None,
    ) -> tuple[WorkflowTransition, TransitionContext]:
        """Return the first edge whose role and guards all pass.

        Edges are ordered by ``priority`` so the data decides which variant of
        an action applies (for example the four ``ec_decide`` outcomes or the
        EVC / no-EVC branch).
        """
        failures: list[str] = []
        for row in rows:
            transition = self._transition(definition, row)
            if actor.role not in transition.roles:
                failures.append(
                    f"{row.action} is not permitted for the {actor.role.value} role"
                )
                continue
            context = self._context(
                application,
                actor,
                transition,
                payload,
                request,
                definition.definition,
            )
            reason = None
            for name in transition.guards:
                reason = evaluate_guard(name, context)
                if reason:
                    break
            if reason is None:
                return row, context
            failures.append(reason)

        message = failures[0] if failures else f"Action '{rows[0].action}' cannot be applied."
        raise InvalidWorkflowTransition(message, detail={"reasons": failures})

    def _run_effects(self, row: WorkflowTransition, context: TransitionContext) -> None:
        # Imported lazily: the effect registry depends on the fee service, which
        # in turn imports this module.
        from app.services.workflow_effects import apply_effect

        for name in row.side_effects or ():
            message = apply_effect(name, context)
            if message:
                context.messages.append(message)

    @staticmethod
    def _message(row: WorkflowTransition, context: TransitionContext) -> str:
        if context.payload.comment:
            return context.payload.comment
        if context.messages:
            return " ".join(context.messages)
        return row.label

    @staticmethod
    def _role_allowed(actor: User, rows: Sequence[WorkflowTransition]) -> bool:
        return any(actor.role.value in (row.allowed_roles or []) for row in rows)

    @staticmethod
    def _ensure_active(application: Application) -> None:
        if application.is_withdrawn:
            raise InvalidWorkflowTransition("A withdrawn application cannot be changed")

    # ------------------------------------------------------------------
    # Authorization
    # ------------------------------------------------------------------

    def _authorize_scope(
        self,
        application: Application,
        actor: User,
        action: WorkflowAction,
    ) -> None:
        if not self._scope_ok(application, actor, action):
            if actor.role == Role.EVC_MEMBER:
                raise WorkflowPermissionError(
                    "No Expert Visit Committee visit is assigned to you for this application"
                )
            if actor.role == Role.SCRUTINY_COMMITTEE_MEMBER and (
                action in _ASSIGNED_SCRUTINY_ACTIONS
            ):
                raise WorkflowPermissionError(
                    "Only the assigned scrutiny officer can perform this action"
                )
            raise WorkflowPermissionError("You do not have access to this application")

    def _scope_ok(
        self,
        application: Application,
        actor: User,
        action: WorkflowAction,
    ) -> bool:
        """Return whether the actor may touch this record at all."""
        role = actor.role
        if role == Role.SUPER_ADMIN or role in _NATIONAL_ROLES:
            return True

        if role == Role.INSTITUTION_ADMIN:
            return (
                actor.institution_id is not None
                and application.institution_id == actor.institution_id
            )

        region = application.institution.region
        if role == Role.REGULATION_BUREAU_OFFICER:
            return actor.region is None or actor.region == region

        if role == Role.REGIONAL_OFFICER:
            return actor.region is not None and actor.region == region

        if role == Role.SCRUTINY_COMMITTEE_MEMBER:
            assigned = application.assigned_officer_id == actor.id
            in_region = actor.region is not None and actor.region == region
            if not assigned and not in_region:
                return False
            if action in _ASSIGNED_SCRUTINY_ACTIONS and not assigned:
                return False
            return True

        if role == Role.EVC_MEMBER:
            if action not in {
                WorkflowAction.EVC_REPORT,
                WorkflowAction.SUBMIT_EVC_VIDEO,
            }:
                return False
            inspection_id = self._db.scalar(
                select(Inspection.id)
                .where(
                    Inspection.application_id == application.id,
                    Inspection.committee_id == actor.id,
                )
                .limit(1)
            )
            return inspection_id is not None

        return False

    # ------------------------------------------------------------------
    # Event and audit primitives
    # ------------------------------------------------------------------

    def _sla_due_at(self, stage: WorkflowStage, now: datetime) -> datetime | None:
        if stage == WorkflowStage.COMPLETED:
            return None
        config = self._db.scalar(select(SLAConfig).where(SLAConfig.stage == stage))
        if config is None:
            raise WorkflowConfigurationError(
                f"SLA configuration for the {stage.value} stage is missing"
            )
        return now + timedelta(days=config.duration_days)

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
            "final_outcome": data.get("final_outcome"),
        }


def _requirement(value: str | None) -> ActionRequirement:
    """Cast a stored ``requires`` value to the schema literal."""
    if value in {
        "none",
        "deficiencies",
        "responses",
        "deficiency_id",
        "inspection_schedule",
        "inspection_report",
        "video",
        "decision",
        "shc_outcome",
        "deposit",
    }:
        return value  # type: ignore[return-value]
    return "none"


def _tone(value: str | None) -> str:
    """Cast a stored tone to the schema literal."""
    return value if value in {"primary", "secondary", "danger"} else "secondary"
