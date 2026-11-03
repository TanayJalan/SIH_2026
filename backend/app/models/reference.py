"""Reference tables transcribed from the APH annexures.

``NomenclatureCourse`` holds the approved course names from Annexure-11 so the
wizard can offer a controlled vocabulary instead of free text (APH 1.7.2).
``CompetentAuthority`` records the Annexure-14 land and building certificate
authorities by State and AICTE region.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import InstitutionRegion
from app.models.types import enum_type


class NomenclatureCourse(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An approved course name from APH Annexure-11.

    ``level`` uses the handbook wording (``Diploma``, ``Post Diploma``, ``UG``,
    ``PG``, ``PG Diploma``) and ``programme_family`` the programme family used by
    the wizard. Names are stored exactly as printed; the parser keeps fragmentary
    entries out so the list can be shown to an applicant.
    """

    __tablename__ = "nomenclature_courses"
    __table_args__ = (
        UniqueConstraint(
            "level", "programme_family", "course_name",
            name="uq_nomenclature_level_family_course",
        ),
        Index("ix_nomenclature_level_family", "level", "programme_family"),
    )

    level: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    programme_family: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    course_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_section: Mapped[str] = mapped_column(String(16), nullable=False)
    """Annexure-11 sub-section, for example ``11.1``."""
    is_emerging: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    """True for the Annexure-11 11.4 Emerging/Multidisciplinary areas."""
    apH_clause: Mapped[str] = mapped_column(String(64), nullable=False)
    needs_verification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )


class CompetentAuthority(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Annexure-14 certificate-issuing authorities for one State/UT.

    The handbook prints a five-column wrapped table. The seed keeps the four
    authority descriptions as extracted text plus the cleaned source block so a
    reviewer can check the transcription against the PDF.
    """

    __tablename__ = "competent_authorities"
    __table_args__ = (UniqueConstraint("state", name="uq_competent_authorities_state"),)

    state: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    aicte_region: Mapped[InstitutionRegion] = mapped_column(
        enum_type(InstitutionRegion, "aicte_region", length=32),
        nullable=False,
        index=True,
    )
    land_use_authority: Mapped[str | None] = mapped_column(Text, nullable=True)
    site_plan_authority: Mapped[str | None] = mapped_column(Text, nullable=True)
    building_plan_authority: Mapped[str | None] = mapped_column(Text, nullable=True)
    occupation_authority: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    """Normalised text of the handbook row, kept for verification."""
    apH_clause: Mapped[str] = mapped_column(String(64), nullable=False)
    needs_verification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
