"""Appeals to the Standing Appellate Committee (APH 1.11a-e, 2.24a)."""

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
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.application import Application


class Appeal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One appeal against an LoD/LoR, heard by the SAC.

    APH allows one appeal within seven days. The SAC may send the case back for
    Scrutiny or EVC once; the loop count records that (Annexure-7).
    """

    __tablename__ = "appeals"
    __table_args__ = (
        CheckConstraint("loop_no >= 1", name="appeal_loop_no_positive"),
        Index("ix_appeals_application_filed", "application_id", "filed_at"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    within_deadline: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    loop_no: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    sac_recommendation: Mapped[str | None] = mapped_column(String(64), nullable=True)
    """RECOMMEND, NOT_RECOMMEND or SEND_BACK (APH 1.11c-d)."""
    council_decision: Mapped[str | None] = mapped_column(Text, nullable=True)
    """The Council decision is final (APH 1.11e)."""
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    apH_clause: Mapped[str] = mapped_column(String(64), nullable=False)
    needs_verification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    application: Mapped[Application] = relationship(back_populates="appeals")
