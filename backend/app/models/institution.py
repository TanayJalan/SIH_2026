"""Institution model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.compliance import ComplianceResult, ComplianceSnapshot
    from app.models.user import User


class Institution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A technical institution applying for AICTE approval."""

    __tablename__ = "institutions"
    __table_args__ = (
        CheckConstraint(
            "established_year BETWEEN 1800 AND 2100",
            name="established_year_range",
        ),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    aicte_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    region: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    established_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    naac_grade: Mapped[str | None] = mapped_column(String(10), nullable=True)
    nba_status: Mapped[str | None] = mapped_column(String(50), nullable=True)

    users: Mapped[list[User]] = relationship(back_populates="institution")
    applications: Mapped[list[Application]] = relationship(back_populates="institution")
    compliance_results: Mapped[list[ComplianceResult]] = relationship(back_populates="institution")
    compliance_snapshots: Mapped[list[ComplianceSnapshot]] = relationship(
        back_populates="institution"
    )
