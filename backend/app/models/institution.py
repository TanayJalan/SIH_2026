"""Institution model."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, SmallInteger, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    InstitutionClass,
    InstitutionRegion,
    InstitutionStatus,
    LandOwnership,
)
from app.models.types import enum_type
from app.schemas.aph_profiles import validate_profile

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.complaint import Complaint, PenalAction
    from app.models.compliance import ComplianceResult, ComplianceSnapshot
    from app.models.faculty import Faculty
    from app.models.programme import Programme
    from app.models.security_deposit import SecurityDeposit
    from app.models.user import User


class Institution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A technical institution applying for AICTE approval."""

    __tablename__ = "institutions"
    __table_args__ = (
        CheckConstraint(
            "established_year BETWEEN 1800 AND 2100",
            name="established_year_range",
        ),
        CheckConstraint(
            "lease_years_total IS NULL OR lease_years_total >= 0",
            name="lease_years_total_non_negative",
        ),
        CheckConstraint(
            "lease_years_live IS NULL OR lease_years_live >= 0",
            name="lease_years_live_non_negative",
        ),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    aicte_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    pid: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    """Permanent institution identifier used by the APH portal."""
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    region: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    """Legacy free-text region kept for existing users and display."""
    aicte_region: Mapped[InstitutionRegion] = mapped_column(
        enum_type(InstitutionRegion, "aicte_region", length=32),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    """Legacy free-text institution type kept for existing rows and display."""
    institution_type: Mapped[str] = mapped_column(String(64), nullable=False)
    institution_class: Mapped[InstitutionClass] = mapped_column(
        enum_type(InstitutionClass, "institution_class", length=16),
        nullable=False,
        index=True,
    )
    is_women_only: Mapped[bool] = mapped_column(
        default=False, server_default=text("false"), nullable=False
    )
    is_pwbd: Mapped[bool] = mapped_column(
        default=False, server_default=text("false"), nullable=False
    )
    in_jk_ladakh_ne: Mapped[bool] = mapped_column(
        default=False, server_default=text("false"), nullable=False
    )
    affiliating_body: Mapped[str | None] = mapped_column(String(255), nullable=True)
    land_ownership: Mapped[LandOwnership] = mapped_column(
        enum_type(LandOwnership, "land_ownership", length=16),
        nullable=False,
        default=LandOwnership.OWNED,
        server_default=LandOwnership.OWNED.value,
    )
    lease_years_total: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    lease_years_live: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    building_leased: Mapped[bool] = mapped_column(
        default=False, server_default=text("false"), nullable=False
    )
    status: Mapped[InstitutionStatus] = mapped_column(
        enum_type(InstitutionStatus, "institution_status", length=32),
        nullable=False,
        default=InstitutionStatus.ACTIVE,
        server_default=InstitutionStatus.ACTIVE.value,
        index=True,
    )
    last_eoa_year: Mapped[str | None] = mapped_column(String(9), nullable=True)
    established_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    naac_grade: Mapped[str | None] = mapped_column(String(10), nullable=True)
    nba_status: Mapped[str | None] = mapped_column(String(50), nullable=True)

    accreditation: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    infra_profile: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    library_profile: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    computing_profile: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    essential_requirements: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    campus: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )

    users: Mapped[list[User]] = relationship(back_populates="institution")
    applications: Mapped[list[Application]] = relationship(back_populates="institution")
    programmes: Mapped[list[Programme]] = relationship(
        back_populates="institution", cascade="all, delete-orphan"
    )
    faculty: Mapped[list[Faculty]] = relationship(
        back_populates="institution", cascade="all, delete-orphan"
    )
    security_deposits: Mapped[list[SecurityDeposit]] = relationship(
        back_populates="institution", cascade="all, delete-orphan"
    )
    complaints: Mapped[list[Complaint]] = relationship(
        back_populates="institution", cascade="all, delete-orphan"
    )
    penal_actions: Mapped[list[PenalAction]] = relationship(
        back_populates="institution", cascade="all, delete-orphan"
    )
    compliance_results: Mapped[list[ComplianceResult]] = relationship(back_populates="institution")
    compliance_snapshots: Mapped[list[ComplianceSnapshot]] = relationship(
        back_populates="institution"
    )

    @validates(
        "accreditation",
        "infra_profile",
        "library_profile",
        "computing_profile",
        "essential_requirements",
        "campus",
    )
    def _validate_profile(self, key: str, value: object) -> dict[str, object]:
        """Validate an APH JSONB profile on assignment.

        Rows loaded from the database are not re-validated; this guard applies
        to writes made through the ORM, including the seed loader.
        """
        return validate_profile(key, value)
