"""Complaints and penal actions (APH Chapter VII)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ComplaintStatus, PenalActionType
from app.models.types import enum_type

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.committee import Committee
    from app.models.institution import Institution


class Complaint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A complaint processed through PGRC, SCSC and SHC (APH 7.10)."""

    __tablename__ = "complaints"
    __table_args__ = (
        Index("ix_complaints_institution_status", "institution_id", "status"),
    )

    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    """Where the complaint came from, for example PORTAL, EMAIL or PGRC."""
    status: Mapped[ComplaintStatus] = mapped_column(
        enum_type(ComplaintStatus, "complaint_status", length=32),
        nullable=False,
        default=ComplaintStatus.RECEIVED,
        server_default=ComplaintStatus.RECEIVED.value,
        index=True,
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    received_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    show_cause_due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_anonymous: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    """Anonymous or pseudonymous complaints are not processed (APH 7.10, CVC guideline)."""
    apH_clause: Mapped[str] = mapped_column(String(64), nullable=False)
    needs_verification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    institution: Mapped[Institution] = relationship(back_populates="complaints")
    committees: Mapped[list[Committee]] = relationship(
        back_populates="complaint", cascade="all, delete-orphan"
    )
    penal_actions: Mapped[list[PenalAction]] = relationship(back_populates="complaint")


class PenalAction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A penal action with the violation code and hearing record (APH 7.3-7.4)."""

    __tablename__ = "penal_actions"
    __table_args__ = (
        CheckConstraint(
            "violation_code IN ('a','b','c','d','e','f','g','h','i','j','k','l','m','n')",
            name="penal_action_violation_code_allowed",
        ),
        Index("ix_penal_actions_institution_year", "institution_id", "effective_academic_year"),
    )

    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    complaint_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("complaints.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action_type: Mapped[PenalActionType] = mapped_column(
        enum_type(PenalActionType, "penal_action_type", length=32),
        nullable=False,
        index=True,
    )
    violation_code: Mapped[str] = mapped_column(String(2), nullable=False)
    """APH 7.4 clause letter a-n."""
    hearing_done: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    """A hearing must precede a penal action (APH 6.50h proviso)."""
    speaking_order: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_academic_year: Mapped[str | None] = mapped_column(String(9), nullable=True)
    apH_clause: Mapped[str] = mapped_column(String(64), nullable=False)
    needs_verification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    institution: Mapped[Institution] = relationship(back_populates="penal_actions")
    complaint: Mapped[Complaint | None] = relationship(back_populates="penal_actions")
    application: Mapped[Application | None] = relationship(back_populates="penal_actions")
