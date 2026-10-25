"""Committees, their members and reports (APH_SPEC section 1, Annexure-16)."""

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
from app.models.enums import CommitteeMode, CommitteeStatus, CommitteeType
from app.models.types import enum_type

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.complaint import Complaint
    from app.models.decision import Decision
    from app.models.user import User


class Committee(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A scheduled APH committee for one application or one complaint."""

    __tablename__ = "committees"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(application_id, complaint_id) = 1",
            name="committee_exactly_one_subject",
        ),
        Index("ix_committees_type_status", "type", "status"),
        Index("ix_committees_scheduled", "scheduled_at"),
    )

    application_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    complaint_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("complaints.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    type: Mapped[CommitteeType] = mapped_column(
        enum_type(CommitteeType, "committee_type", length=32), nullable=False, index=True
    )
    mode: Mapped[CommitteeMode] = mapped_column(
        enum_type(CommitteeMode, "committee_mode", length=16),
        nullable=False,
        default=CommitteeMode.ONLINE,
        server_default=CommitteeMode.ONLINE.value,
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    selection_seed: Mapped[str | None] = mapped_column(String(128), nullable=True)
    """Seed recorded for the automated random member selection (APH 1.8a, 1.9a)."""
    status: Mapped[CommitteeStatus] = mapped_column(
        enum_type(CommitteeStatus, "committee_status", length=16),
        nullable=False,
        default=CommitteeStatus.SCHEDULED,
        server_default=CommitteeStatus.SCHEDULED.value,
        index=True,
    )
    apH_clause: Mapped[str] = mapped_column(String(64), nullable=False)
    needs_verification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    application: Mapped[Application | None] = relationship(back_populates="committees")
    complaint: Mapped[Complaint | None] = relationship(back_populates="committees")
    members: Mapped[list[CommitteeMember]] = relationship(
        back_populates="committee", cascade="all, delete-orphan"
    )
    reports: Mapped[list[CommitteeReport]] = relationship(
        back_populates="committee", cascade="all, delete-orphan"
    )
    decisions: Mapped[list[Decision]] = relationship(back_populates="committee")


class CommitteeMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user appointed to a committee with a specific role."""

    __tablename__ = "committee_members"
    __table_args__ = (
        UniqueConstraint("committee_id", "user_id", name="uq_committee_members_committee_user"),
        Index("ix_committee_members_user", "user_id"),
    )

    committee_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("committees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    """CHAIR, MEMBER, MEMBER_SECRETARY or an expert seat label."""
    apH_clause: Mapped[str] = mapped_column(String(64), nullable=False)

    committee: Mapped[Committee] = relationship(back_populates="members")
    user: Mapped[User] = relationship()


class CommitteeReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The findings and recommendation recorded by a committee."""

    __tablename__ = "committee_reports"
    __table_args__ = (Index("ix_committee_reports_committee", "committee_id"),)

    committee_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("committees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    findings: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    deficiencies: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    recommendation: Mapped[str | None] = mapped_column(String(64), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    video_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    """EVC institutions upload a 30-minute video link (APH 1.9f-g)."""
    apH_clause: Mapped[str] = mapped_column(String(64), nullable=False)
    needs_verification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    committee: Mapped[Committee] = relationship(back_populates="reports")
