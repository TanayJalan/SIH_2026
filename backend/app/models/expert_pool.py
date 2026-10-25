"""Expert pool model – candidate members for automated committee selection.

APH 1.8a, 1.9a: member selection is automated by the web portal from an
approved panel.  The ``ExpertPool`` table holds that panel.  Every row carries
the qualifications needed by ``CommitteeService`` to enforce the composition
rules in APH Annexure-16 sections 16.3–16.7.

All rows seeded by ``seed.py`` are clearly labelled fictional.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    pass


class ExpertPool(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A candidate member available for committee selection (APH 1.8a, 1.9a).

    Qualification fields map directly to the composition rules in APH
    Annexure-16 sections 16.3–16.7.  ``seat_tags`` is a list of strings that
    the committee service uses to match seats: for example
    ``["ACADEMIC", "ADVOCATE", "ARCHITECT", "CHAIR_SHC", "DTE_REGISTRAR"]``.
    """

    __tablename__ = "expert_pool"
    __table_args__ = (
        Index("ix_expert_pool_is_active", "is_active"),
        Index("ix_expert_pool_state", "state"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    """Full name. All demo entries are clearly labelled fictional."""

    designation: Mapped[str] = mapped_column(String(128), nullable=False)
    """E.g. 'Professor', 'Associate Professor', 'Advocate', 'Architect'."""

    institution_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    """Employing institution (IIT/IIM/NIT/Govt/Bar Council etc.)."""

    state: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    """Home state – used to enforce the state-conflict exclusion rule (APH 1.8a)."""

    aicte_region: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    """AICTE region string (matches ``InstitutionRegion`` values)."""

    email: Mapped[str | None] = mapped_column(String(320), nullable=True, unique=True, index=True)

    seat_tags: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    """Which composition seats this expert qualifies for.

    Valid tags (from APH Annexure-16 16.3–16.7):
    * ``ACADEMIC`` – Professor or Assoc. Prof at IIT/IIM/NIT/Govt institution
    * ``ADVOCATE`` – Advocate registered with Bar Council
    * ``ARCHITECT`` – Architect (or Prof/Assoc. Prof Structural/Civil)
    * ``CHAIR_SHC`` – Retired HC judge / VC / IIT/NIT/IIM Director (SHC/SAC chair seat)
    * ``INDUSTRY_EXPERT`` – Industry expert ≥ 5 years (EVC seat 2)
    * ``REVENUE_LAND`` – Deputy Director Revenue / land & revenue expert
    * ``DTE_REGISTRAR`` – DTE or Registrar (SCSC seat 5)
    * ``CO_OPT`` – State/UT/affiliating-university representative (optional co-opt)
    """

    years_experience: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    """Years of relevant experience – used for minimum seniority checks."""

    is_retired_hc_judge: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    """True if the expert is a retired High Court judge (SHC/SAC/SCSC chair seat)."""

    recent_assignment_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    """Rolling count of committee assignments (updated on each selection; used for load-balancing)."""

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    """Inactive experts are excluded from selection."""

    is_fictional: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    """All demo-seeded experts are fictional; real experts added by admins may set this False."""

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    """Free-text notes (qualifications, publications, etc.)."""

    apH_clause: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="APH 1.8a",
        server_default=text("'APH 1.8a'"),
    )
    needs_verification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
