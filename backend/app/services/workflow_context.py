"""Shared types for the data-driven workflow engine.

``Transition`` is the in-memory view of one ``workflow_transitions`` row.
``TransitionContext`` is passed to every registered guard and side effect so
those functions never need the service instance or any global state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from sqlalchemy.orm import Session

from app.core.clock import SimulatedClock
from app.models.application import Application
from app.models.enums import ApplicationStatus, Role, WorkflowAction, WorkflowStage
from app.models.user import User
from app.models.workflow import WorkflowEvent
from app.models.workflow_definition import WorkflowDefinition
from app.schemas.workflow import WorkflowActionRequest
from app.services.audit import AuditService

ActionRequirement = Literal[
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
]
ActionTone = Literal["primary", "secondary", "danger"]


class AssignmentStrategy(Protocol):
    """Pluggable scrutiny-officer assignment policy."""

    def choose(self, db: Session, application: Application) -> User | None:
        """Return the officer to assign, or ``None`` when none is available."""


@dataclass(frozen=True, slots=True)
class Transition:
    """One legal action edge loaded from the workflow definition."""

    action: WorkflowAction
    from_statuses: frozenset[ApplicationStatus]
    to_status: ApplicationStatus
    roles: frozenset[Role]
    stage: WorkflowStage | None
    label: str
    description: str
    apH_clause: str
    guards: tuple[str, ...] = ()
    effects: tuple[str, ...] = ()
    requires: ActionRequirement = "none"
    tone: ActionTone = "secondary"
    priority: int = 0
    needs_verification: bool = False


@dataclass(slots=True)
class TransitionContext:
    """Everything a guard or side effect may read or write during one action."""

    db: Session
    application: Application
    actor: User
    transition: Transition
    payload: WorkflowActionRequest
    clock: SimulatedClock
    audit: AuditService
    request: Any | None
    definition: WorkflowDefinition
    events: list[WorkflowEvent] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    messages: list[str] = field(default_factory=list)
    settings: Any | None = None
    assignment_strategy: AssignmentStrategy | None = None
    notifications: Any | None = None

    @property
    def now(self):
        """Return the simulated current instant."""
        return self.clock.now()

    def add_detail(self, key: str, value: Any) -> None:
        """Record an extra field on the workflow event."""
        self.details[key] = value

    def add_message(self, message: str) -> None:
        """Append a user-facing sentence to the action result."""
        if message:
            self.messages.append(message)
