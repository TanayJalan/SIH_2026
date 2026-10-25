"""Committee decisions, decision letters and Council ratification.

APH records decisions of the Executive Committee and Council, the
recommendations of the Standing Appellate/Heating Committees, the letters
published on the portal, and the Council ratification of EC decisions
(APH 1.10-1.11, 2.23.3-2.24a, 2.25a).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import DecisionBody, DecisionLetterType, DecisionOutcome
from app.models.types import enum_type

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.committee import Committee
    from app.models.user import User


class Decision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A decision or recommendation recorded by a committee or the Council."""

    __tablename__ = "decisions"
    __table_args__ = (
        Index("ix_decisions_application_decided", "application_id", "decided_on"),
        Index("ix_decisions_body_outcome", "body", "outcome"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    body: Mapped[DecisionBody] = mapped_column(
        enum_type(DecisionBody, "decision_body", length=16), nullable=False
    )
    outcome: Mapped[DecisionOutcome] = mapped_column(
        enum_type(DecisionOutcome, "decision_outcome", length=16), nullable=False
    )
    decided_on: Mapped[date] = mapped_column(Date, nullable=False)
    committee_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("committees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    quorum_met: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    notes: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )
    apH_clause: Mapped[str] = mapped_column(String(64), nullable=False)

    application: Mapped[Application] = relationship(back_populates="decisions")
    committee: Mapped[Committee | None] = relationship(back_populates="decisions")
    letters: Mapped[list[DecisionLetter]] = relationship(
        back_populates="decision", cascade="all, delete-orphan"
    )
    ratification: Mapped[CouncilRatification | None] = relationship(
        back_populates="decision", cascade="all, delete-orphan", uselist=False
    )


class DecisionLetter(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A letter published on the portal, with its appeal clock.

    ``appeal_clock_start`` and ``appeal_deadline`` are stored explicitly because
    APH counts the seven-day appeal window from either the issue of the LoD
    (1.11a) or the upload of the decision (2.24a).
    """

    __tablename__ = "decision_letters"
    __table_args__ = (
        UniqueConstraint("letter_number", name="uq_decision_letters_letter_number"),
        CheckConstraint(
            "appeal_clock_start IS NULL OR appeal_deadline IS NULL "
            "OR appeal_deadline >= appeal_clock_start",
            name="decision_letter_appeal_window_ordered",
        ),
        Index("ix_decision_letters_application_issued", "application_id", "issued_on"),
        Index("ix_decision_letters_appeal_deadline", "appeal_deadline"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    decision_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("decisions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    letter_type: Mapped[DecisionLetterType] = mapped_column(
        enum_type(DecisionLetterType, "decision_letter_type", length=32),
        nullable=False,
        index=True,
    )
    letter_number: Mapped[str] = mapped_column(String(64), nullable=False)
    issued_on: Mapped[date] = mapped_column(Date, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    appeal_clock_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    appeal_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    body_text: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )
    pdf_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    application: Mapped[Application] = relationship(back_populates="decision_letters")
    decision: Mapped[Decision | None] = relationship(back_populates="letters")
    acknowledged_by_user: Mapped[User | None] = relationship(
        back_populates="acknowledged_letters", foreign_keys=[acknowledged_by]
    )


class CouncilRatification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Council ratification of an EC decision (APH 2.25a)."""

    __tablename__ = "council_ratifications"
    __table_args__ = (
        UniqueConstraint(
            "decision_id", name="uq_council_ratifications_decision_id"
        ),
    )

    decision_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("decisions.id", ondelete="CASCADE"),
        nullable=False,
    )
    ratified_on: Mapped[date] = mapped_column(Date, nullable=False)
    ratified_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    ec_recommendation_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)

    decision: Mapped[Decision] = relationship(back_populates="ratification")
    ratified_by_user: Mapped[User | None] = relationship(
        back_populates="ratified_decisions", foreign_keys=[ratified_by]
    )
