"""SLA configuration per workflow stage."""

from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import Role, WorkflowStage
from app.models.types import enum_type


class SLAConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Configurable SLA duration and escalation target for a stage."""

    __tablename__ = "sla_configs"
    __table_args__ = (
        CheckConstraint("duration_days > 0", name="duration_days_positive"),
        CheckConstraint("escalation_after_days >= 0", name="escalation_after_days_non_negative"),
    )

    stage: Mapped[WorkflowStage] = mapped_column(
        enum_type(WorkflowStage, "workflow_stage", length=32),
        nullable=False,
        unique=True,
        index=True,
    )
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    escalation_after_days: Mapped[int] = mapped_column(Integer, nullable=False)
    escalate_to_role: Mapped[Role] = mapped_column(
        enum_type(Role, "user_role", length=32), nullable=False
    )
    apH_clause: Mapped[str] = mapped_column(
        String(64), nullable=False, default="DEMO", server_default="DEMO"
    )
    """APH clause for the processing limit, or ``DEMO`` for illustrative SLA values."""
    needs_verification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    """SLA durations are project settings, so they stay flagged for review."""
