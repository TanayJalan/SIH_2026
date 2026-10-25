"""Security Deposit lifecycle (APH 1.12, 2.25f, 6.46)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import SecurityDepositStatus
from app.models.types import enum_type

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.institution import Institution


class SecurityDeposit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A deposit required by Table 1.4 after an LoA.

    ``required_paise`` is copied from the fee schedule when the deposit is
    created so a later rate change does not rewrite history. ``maturity_on`` is
    stored explicitly because APH 1.12 and Affidavit 6 disagree on the term.
    """

    __tablename__ = "security_deposits"
    __table_args__ = (
        CheckConstraint("required_paise >= 0", name="security_deposit_amount_non_negative"),
        CheckConstraint(
            "penalty_percent IS NULL OR penalty_percent IN (10, 20)",
            name="security_deposit_penalty_percent_allowed",
        ),
        CheckConstraint(
            "maturity_on >= created_on",
            name="security_deposit_maturity_after_creation",
        ),
        Index("ix_security_deposits_institution_status", "institution_id", "status"),
    )

    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    programme_family: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[str] = mapped_column(String(32), nullable=False)
    required_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    doubled_for_leased: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    """The deposit doubles for a private leased building or land (Table 1.4)."""
    created_on: Mapped[date] = mapped_column(Date, nullable=False)
    """Intimation date; proof and Affidavit 3 are due 15 days later (APH 2.25f)."""
    maturity_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[SecurityDepositStatus] = mapped_column(
        enum_type(SecurityDepositStatus, "security_deposit_status", length=16),
        nullable=False,
        default=SecurityDepositStatus.PENDING,
        server_default=SecurityDepositStatus.PENDING.value,
        index=True,
    )
    penalty_percent: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    apH_clause: Mapped[str] = mapped_column(String(64), nullable=False)
    needs_verification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    institution: Mapped[Institution] = relationship(back_populates="security_deposits")
    application: Mapped[Application | None] = relationship(back_populates="security_deposits")
