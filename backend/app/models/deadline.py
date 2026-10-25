"""Deadline rules and per-application timers.

``DeadlineRule`` is configuration data: the start event, duration, owner and
penalty ladder can be changed without a code change. ``Timer`` records one
started clock for an application so escalation can be driven from the database
(APH_SPEC section 5).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import Role, TimerStatus
from app.models.types import enum_type

if TYPE_CHECKING:
    from app.models.application import Application


class DeadlineRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A statutory or configured deadline that can be started for an application."""

    __tablename__ = "deadline_rules"
    __table_args__ = (
        UniqueConstraint("code", name="uq_deadline_rules_code"),
        CheckConstraint("duration_days >= 0", name="deadline_duration_non_negative"),
    )

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    start_event: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    owner_role: Mapped[Role] = mapped_column(
        enum_type(Role, "user_role", length=32), nullable=False
    )
    penalty_ladder: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    apH_clause: Mapped[str] = mapped_column(String(64), nullable=False)
    start_event_configurable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    """True when APH leaves the start event ambiguous (for example the appeal clock)."""
    needs_verification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    timers: Mapped[list[Timer]] = relationship(back_populates="deadline_rule")


class Timer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One running deadline for one application."""

    __tablename__ = "timers"
    __table_args__ = (
        Index("ix_timers_application_status", "application_id", "status"),
        Index("ix_timers_status_due", "status", "due_at"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    deadline_rule_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("deadline_rules.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[TimerStatus] = mapped_column(
        enum_type(TimerStatus, "timer_status", length=16),
        nullable=False,
        default=TimerStatus.PENDING,
        server_default=TimerStatus.PENDING.value,
        index=True,
    )
    fired_levels: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )

    application: Mapped[Application] = relationship(back_populates="timers")
    deadline_rule: Mapped[DeadlineRule] = relationship(back_populates="timers")
