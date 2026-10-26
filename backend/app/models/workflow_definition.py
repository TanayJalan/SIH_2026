"""Database-driven APH workflow definitions.

These three tables are the runtime authority for the approval state machine.
No Python module decides which action is legal in which state, which role may
perform it, or which clause applies: that is seed data in
``workflow_definitions`` / ``workflow_states`` / ``workflow_transitions``
(APH Annexure-7, 1.8-1.11, 2.23-2.25).

``guard_expr`` and ``side_effects`` are JSON arrays of *registered names*. The
workflow service evaluates only names in its registry, so administrators can
re-order or disable a guard without executing arbitrary code.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ApplicationStatus, WorkflowStage
from app.models.types import enum_type

if TYPE_CHECKING:
    pass


class WorkflowDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One named approval path (Track A, B, C or D)."""

    __tablename__ = "workflow_definitions"
    __table_args__ = (
        UniqueConstraint("key", name="uq_workflow_definitions_key"),
    )

    key: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    track: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    """APH track: TRACK_A, TRACK_B, TRACK_C or TRACK_D."""
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    """Track-level parameters (random EVC percentage, appeal start event, ...)."""
    apH_clause: Mapped[str] = mapped_column(String(64), nullable=False)
    needs_verification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    states: Mapped[list[WorkflowState]] = relationship(
        back_populates="definition", cascade="all, delete-orphan"
    )
    transitions: Mapped[list[WorkflowTransition]] = relationship(
        back_populates="definition", cascade="all, delete-orphan"
    )


class WorkflowState(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One state in a workflow definition."""

    __tablename__ = "workflow_states"
    __table_args__ = (
        UniqueConstraint("definition_id", "code", name="uq_workflow_states_definition_code"),
        Index("ix_workflow_states_definition_sort", "definition_id", "sort_order"),
        CheckConstraint("sort_order >= 0", name="workflow_state_sort_non_negative"),
    )

    definition_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workflow_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[ApplicationStatus] = mapped_column(
        enum_type(ApplicationStatus, "application_status", length=32), nullable=False
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    stage: Mapped[WorkflowStage] = mapped_column(
        enum_type(WorkflowStage, "workflow_stage", length=32), nullable=False
    )
    is_initial: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    is_terminal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    apH_clause: Mapped[str] = mapped_column(String(64), nullable=False)
    needs_verification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    definition: Mapped[WorkflowDefinition] = relationship(back_populates="states")


class WorkflowTransition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One legal action edge in a workflow definition.

    ``guard_expr`` is a JSON array of registered guard names (all must pass).
    ``side_effects`` is a JSON array of registered handler names executed in
    order. ``from_state`` and ``to_state`` store the APH status codes so the
    edge is readable without a join.
    """

    __tablename__ = "workflow_transitions"
    __table_args__ = (
        UniqueConstraint(
            "definition_id",
            "from_state",
            "action",
            "priority",
            name="uq_workflow_transitions_definition_edge",
        ),
        Index(
            "ix_workflow_transitions_lookup",
            "definition_id",
            "from_state",
            "action",
        ),
    )

    definition_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workflow_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_state: Mapped[ApplicationStatus] = mapped_column(
        enum_type(ApplicationStatus, "application_status_from", length=32), nullable=False
    )
    to_state: Mapped[ApplicationStatus] = mapped_column(
        enum_type(ApplicationStatus, "application_status_to", length=32), nullable=False
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    allowed_roles: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    guard_expr: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    side_effects: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    requires: Mapped[str] = mapped_column(
        String(32), nullable=False, default="none", server_default="none"
    )
    tone: Mapped[str] = mapped_column(
        String(16), nullable=False, default="secondary", server_default="secondary"
    )
    sla_stage: Mapped[WorkflowStage | None] = mapped_column(
        enum_type(WorkflowStage, "workflow_stage", length=32), nullable=True
    )
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    apH_clause: Mapped[str] = mapped_column(String(64), nullable=False)
    needs_verification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    definition: Mapped[WorkflowDefinition] = relationship(back_populates="transitions")

    @property
    def roles(self) -> list[str]:
        """Return the allowed role codes as a plain list."""
        value: Any = self.allowed_roles
        return [str(item) for item in value] if isinstance(value, list) else []
