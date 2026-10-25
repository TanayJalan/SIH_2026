"""Faculty roster used by the FSR calculator (APH 6.14, Annexure-5)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import FacultyCadre
from app.models.types import enum_type

if TYPE_CHECKING:
    from app.models.institution import Institution
    from app.models.programme import Programme


class Faculty(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One faculty member as reported on the AICTE portal."""

    __tablename__ = "faculty"
    __table_args__ = (
        CheckConstraint(
            "left_on IS NULL OR joined_on IS NULL OR left_on >= joined_on",
            name="faculty_dates_ordered",
        ),
        Index("ix_faculty_institution_cadre", "institution_id", "cadre"),
        Index("ix_faculty_portal_id", "portal_faculty_id"),
    )

    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    programme_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("programmes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    portal_faculty_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    """AICTE portal faculty ID; add/remove in the same month as joining/leaving (APH 6.14c)."""
    cadre: Mapped[FacultyCadre] = mapped_column(
        enum_type(FacultyCadre, "faculty_cadre", length=32),
        nullable=False,
        index=True,
    )
    qualification: Mapped[str | None] = mapped_column(String(255), nullable=True)
    has_phd: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    regular: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    """Regular faculty are required; contractual appointments are exceptional (APH 6.14e)."""
    joined_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    left_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    portal_updated_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    biometric: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    """Biometric attendance is required (APH 6.14j)."""
    salary_via_ecs: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    """Salary must be paid through ECS via a nationalised bank (APH 6.14a)."""
    apH_clause: Mapped[str] = mapped_column(String(64), nullable=False)
    needs_verification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    institution: Mapped[Institution] = relationship(back_populates="faculty")
    programme: Mapped[Programme | None] = relationship(back_populates="faculty")
