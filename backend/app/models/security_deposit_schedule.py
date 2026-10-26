"""Security Deposit rate table (APH Table 1.4)."""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, CheckConstraint, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class SecurityDepositSchedule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The base deposit for one programme family and level.

    Amounts are integer paise and copied onto a :class:`SecurityDeposit` when a
    deposit is created. ``doubled_for_leased`` records the Table 1.4 rule that a
    private leased building or land doubles the deposit; the calculator applies
    it from the institution's land/building tenure.
    """

    __tablename__ = "security_deposit_schedules"
    __table_args__ = (
        UniqueConstraint(
            "programme_family",
            "level",
            name="uq_security_deposit_schedules_family_level",
        ),
        CheckConstraint("amount_paise >= 0", name="security_deposit_schedule_amount_non_negative"),
    )

    programme_family: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    doubled_for_leased: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    apH_clause: Mapped[str] = mapped_column(String(64), nullable=False)
    needs_verification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
