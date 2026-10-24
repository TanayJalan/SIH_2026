"""Inspection visit model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.application import Application
from app.models.enums import InspectionStatus
from app.models.types import enum_type
from app.models.user import User


class Inspection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A scheduled or completed inspection of an institution."""

    __tablename__ = "inspections"
    __table_args__ = (Index("ix_inspections_application_status", "application_id", "status"),)

    application_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    committee_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    scheduled_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[InspectionStatus] = mapped_column(
        enum_type(InspectionStatus, "inspection_status", length=16),
        nullable=False,
        default=InspectionStatus.SCHEDULED,
        server_default=InspectionStatus.SCHEDULED.value,
        index=True,
    )
    report: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(String(64), nullable=True)

    application: Mapped[Application] = relationship(back_populates="inspections")
    committee_member: Mapped[User] = relationship(back_populates="inspections")

    @property
    def committee_name(self) -> str | None:
        """Return the committee member name for API rendering."""
        return self.committee_member.name if self.committee_member is not None else None
