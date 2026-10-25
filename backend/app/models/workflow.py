"""Workflow transition history."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.application import Application
from app.models.enums import ApplicationStatus
from app.models.types import enum_type
from app.models.user import User


class WorkflowEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An immutable record of one workflow action or status transition."""

    __tablename__ = "workflow_events"
    __table_args__ = (
        Index("ix_workflow_events_application_created", "application_id", "created_at"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[ApplicationStatus | None] = mapped_column(
        enum_type(ApplicationStatus, "application_status_from", length=32), nullable=True
    )
    to_status: Mapped[ApplicationStatus] = mapped_column(
        enum_type(ApplicationStatus, "application_status_to", length=32), nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str | None] = mapped_column(String(64), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    apH_clause: Mapped[str] = mapped_column(String(64), nullable=False)
    """APH clause that authorised the transition, copied from the transition table."""

    application: Mapped[Application] = relationship(back_populates="workflow_events")
    actor: Mapped[User | None] = relationship(back_populates="workflow_events")

    @property
    def actor_name(self) -> str | None:
        """Return the acting user's name for timeline rendering."""
        return self.actor.name if self.actor is not None else None
