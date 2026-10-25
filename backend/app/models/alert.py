"""Alert and alert-rule models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
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
from app.models.application import Application
from app.models.enums import AlertChannel, AlertStatus, Role, Severity
from app.models.types import enum_type
from app.models.user import User


class Alert(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A notification delivered to a user through one channel.

    One logical notification produces one row per recipient and channel. The
    in-app row is the user's inbox entry; email and SMS rows are delivery
    records. ``dedupe_key`` makes periodic scans idempotent.
    """

    __tablename__ = "alerts"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_alerts_dedupe_key"),
        Index("ix_alerts_recipient_status", "recipient_user_id", "status"),
        Index("ix_alerts_application_created", "application_id", "created_at"),
        Index("ix_alerts_rule_id", "rule_id"),
    )

    recipient_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
    )
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("alert_rules.id", ondelete="SET NULL"),
        nullable=True,
    )
    parent_alert_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("alerts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[Severity] = mapped_column(
        enum_type(Severity, "severity", length=16), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[AlertChannel] = mapped_column(
        enum_type(AlertChannel, "alert_channel", length=16), nullable=False
    )
    status: Mapped[AlertStatus] = mapped_column(
        enum_type(AlertStatus, "alert_status", length=16),
        nullable=False,
        default=AlertStatus.PENDING,
        server_default=AlertStatus.PENDING.value,
        index=True,
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    acknowledged_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    escalation_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    dedupe_key: Mapped[str | None] = mapped_column(String(255), nullable=True)

    recipient: Mapped[User] = relationship(
        back_populates="alerts", foreign_keys=[recipient_user_id]
    )
    application: Mapped[Application | None] = relationship(back_populates="alerts")
    rule: Mapped[AlertRule | None] = relationship("AlertRule")


class AlertRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Configuration for when and how an alert is raised."""

    __tablename__ = "alert_rules"
    __table_args__ = (
        CheckConstraint("days_before >= 0", name="days_before_non_negative"),
        UniqueConstraint("code", name="uq_alert_rules_code"),
    )

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )
    trigger_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    days_before: Mapped[int] = mapped_column(Integer, nullable=False)
    severity: Mapped[Severity] = mapped_column(
        enum_type(Severity, "severity", length=16), nullable=False
    )
    channel_list: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    template: Mapped[str] = mapped_column(Text, nullable=False)
    escalation_role: Mapped[Role] = mapped_column(
        enum_type(Role, "user_role", length=32), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    apH_clause: Mapped[str] = mapped_column(String(64), nullable=False)
    # APH clause the alert supports, for example "APH 2.25f".
    needs_verification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    # Set when no clause exists in APH_SPEC; see OPEN_QUESTIONS.md.


class AlertTriggerCatalogue(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The data-driven list of alert triggers.

    ``code`` is the value stored in :attr:`AlertRule.trigger_type`.
    ``handler_key`` selects the engine handler that evaluates the trigger, so a
    new statutory trigger only needs a catalogue row and a rule, not a
    migration or a new branch in the engine.
    """

    __tablename__ = "alert_trigger_catalogue"
    __table_args__ = (
        UniqueConstraint("code", name="uq_alert_trigger_catalogue_code"),
    )

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    handler_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )
    apH_clause: Mapped[str] = mapped_column(String(64), nullable=False)
    needs_verification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
