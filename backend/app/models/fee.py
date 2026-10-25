"""Fee schedule and application fee transactions (APH_SPEC section 4)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import FeeKind, FeeUnit, InstitutionClass
from app.models.types import enum_type

if TYPE_CHECKING:
    from app.models.application import Application


class FeeSchedule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One TER, penalty or deposit rate.

    Amounts are integer paise. ``institution_class`` is ``None`` for items that
    apply to every class (for example the portal user-ID fee).
    """

    __tablename__ = "fee_schedules"
    __table_args__ = (
        CheckConstraint("amount_paise >= 0", name="fee_amount_paise_non_negative"),
        CheckConstraint(
            "annual_increase_pct >= 0",
            name="annual_increase_pct_non_negative",
        ),
        Index("ix_fee_schedules_item_class", "item_code", "institution_class"),
    )

    item_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    institution_class: Mapped[InstitutionClass | None] = mapped_column(
        enum_type(InstitutionClass, "institution_class", length=16), nullable=True
    )
    unit: Mapped[FeeUnit] = mapped_column(
        enum_type(FeeUnit, "fee_unit", length=32), nullable=False
    )
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    base_academic_year: Mapped[str] = mapped_column(String(9), nullable=False)
    annual_increase_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("10"),
        server_default=text("10"),
    )
    apH_clause: Mapped[str] = mapped_column(String(64), nullable=False)
    needs_verification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )


class FeeTransaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A TER payment, penalty, refund or deduction against an application."""

    __tablename__ = "fee_transactions"
    __table_args__ = (
        CheckConstraint("amount_paise >= 0", name="fee_transaction_amount_non_negative"),
        Index("ix_fee_transactions_application_kind", "application_id", "kind"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    kind: Mapped[FeeKind] = mapped_column(
        enum_type(FeeKind, "fee_kind", length=16), nullable=False
    )
    receipt_no: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    apH_clause: Mapped[str] = mapped_column(String(64), nullable=False)
    needs_verification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    application: Mapped[Application] = relationship(back_populates="fee_transactions")
