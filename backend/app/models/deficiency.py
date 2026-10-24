"""Deficiency raised during scrutiny."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.application import Application
from app.models.enums import DeficiencyStatus
from app.models.types import enum_type
from app.models.user import User

if TYPE_CHECKING:
    from app.models.document import Document


class Deficiency(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A compliance or documentation gap requiring an institution response."""

    __tablename__ = "deficiencies"
    __table_args__ = (Index("ix_deficiencies_application_status", "application_id", "status"),)

    application_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    raised_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    status: Mapped[DeficiencyStatus] = mapped_column(
        enum_type(DeficiencyStatus, "deficiency_status", length=16),
        nullable=False,
        default=DeficiencyStatus.OPEN,
        server_default=DeficiencyStatus.OPEN.value,
        index=True,
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_document_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    application: Mapped[Application] = relationship(back_populates="deficiencies")
    raised_by_user: Mapped[User] = relationship(back_populates="raised_deficiencies")
    response_document: Mapped[Document | None] = relationship("Document")

    @property
    def raised_by_name(self) -> str | None:
        """Return the officer name for API and timeline rendering."""
        return self.raised_by_user.name if self.raised_by_user is not None else None

    @property
    def response_document_filename(self) -> str | None:
        """Return the attached response document name, when present."""
        return self.response_document.filename if self.response_document is not None else None
