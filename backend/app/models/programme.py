"""Approved programmes and the per-year approved-intake ledger."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ProgrammeMode, ProgrammeStatus
from app.models.types import enum_type

if TYPE_CHECKING:
    from app.models.faculty import Faculty
    from app.models.institution import Institution


class Programme(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An approved programme run by an institution."""

    __tablename__ = "programmes"
    __table_args__ = (
        UniqueConstraint(
            "institution_id",
            "course_name",
            "level",
            name="uq_programmes_institution_course_level",
        ),
        CheckConstraint("approved_intake >= 0", name="approved_intake_non_negative"),
        CheckConstraint("divisions >= 0", name="divisions_non_negative"),
        CheckConstraint("duration_years > 0", name="duration_years_positive"),
        Index("ix_programmes_institution_status", "institution_id", "status"),
    )

    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    programme_family: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    """Engineering & Technology, Planning, Design, HMCT, Computer Applications, Management."""
    level: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    course_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_core: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    mode: Mapped[ProgrammeMode] = mapped_column(
        enum_type(ProgrammeMode, "programme_mode", length=32),
        nullable=False,
        default=ProgrammeMode.REGULAR,
        server_default=ProgrammeMode.REGULAR.value,
    )
    duration_years: Mapped[Decimal] = mapped_column(Numeric(3, 1), nullable=False)
    approved_intake: Mapped[int] = mapped_column(Integer, nullable=False)
    divisions: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    status: Mapped[ProgrammeStatus] = mapped_column(
        enum_type(ProgrammeStatus, "programme_status", length=32),
        nullable=False,
        default=ProgrammeStatus.ACTIVE,
        server_default=ProgrammeStatus.ACTIVE.value,
        index=True,
    )
    apH_clause: Mapped[str] = mapped_column(String(64), nullable=False)
    needs_verification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    institution: Mapped[Institution] = relationship(back_populates="programmes")
    intake_ledger: Mapped[list[ApprovedIntakeLedger]] = relationship(
        back_populates="programme", cascade="all, delete-orphan"
    )
    faculty: Mapped[list[Faculty]] = relationship(back_populates="programme")


class ApprovedIntakeLedger(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The approved and admitted seats of one programme for one academic year.

    APH requires the approved intake and the category-wise admissions to be
    tracked per year (APH 2.25b, 6.12, 6.37-6.44).
    """

    __tablename__ = "approved_intake_ledger"
    __table_args__ = (
        UniqueConstraint(
            "programme_id",
            "academic_year",
            name="uq_approved_intake_ledger_programme_year",
        ),
        CheckConstraint("approved_intake >= 0", name="ledger_approved_intake_non_negative"),
        CheckConstraint("nri >= 0", name="ledger_nri_non_negative"),
        CheckConstraint("fn_oci >= 0", name="ledger_fn_oci_non_negative"),
        CheckConstraint('"lateral" >= 0', name="ledger_lateral_non_negative"),
        CheckConstraint("tfw >= 0", name="ledger_tfw_non_negative"),
        CheckConstraint("ews >= 0", name="ledger_ews_non_negative"),
        CheckConstraint("admitted_total >= 0", name="ledger_admitted_total_non_negative"),
    )

    programme_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("programmes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    academic_year: Mapped[str] = mapped_column(String(9), nullable=False, index=True)
    approved_intake: Mapped[int] = mapped_column(Integer, nullable=False)
    nri: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    """NRI seats are 5% within the approved intake (APH 2.8b)."""
    fn_oci: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    """FN/OCI/Gulf seats are 15% over the approved intake (APH 2.9)."""
    lateral: Mapped[int] = mapped_column(
        "lateral", Integer, nullable=False, default=0, server_default=text("0"), quote=True
    )
    """Lateral entry is at most 10% of the approved intake (APH 6.13a)."""
    tfw: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    """Tuition Fee Waiver seats are at most 5% per course (APH 6.42)."""
    ews: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    """EWS reservation raises the intake by 1.25 times (APH 6.37)."""
    admitted_total: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    admitted_by_category: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    apH_clause: Mapped[str] = mapped_column(String(64), nullable=False)
    needs_verification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    programme: Mapped[Programme] = relationship(back_populates="intake_ledger")
