"""APH application-type routing table."""

from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ApplicationCategory
from app.models.types import enum_type


class ApplicationTypeRoute(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Which APH steps an application type must follow (Table 2.3).

    This table is the runtime authority for application types. The workflow and
    the document checklist read it instead of hard-coding a type list, so an
    administrator can correct a step without a code change.
    """

    __tablename__ = "application_type_routes"
    __table_args__ = (
        UniqueConstraint("type", name="uq_application_type_routes_type"),
        CheckConstraint(
            "year_round = (category = 'CAT2_YEAR_ROUND')",
            name="year_round_matches_category",
        ),
    )

    type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[ApplicationCategory] = mapped_column(
        enum_type(ApplicationCategory, "application_category", length=32),
        nullable=False,
        index=True,
    )
    requires_self_disclosure: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    requires_scrutiny: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    requires_evc: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    requires_hearing_aa: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    """SHC/SAC hearing where Table 2.3 shows "AA"."""
    nil_deficiency_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    """Clauses that require "Nil Deficiency based on Self-Disclosure"."""
    no_ter: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    year_round: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    workflow_key: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    """Workflow definition key (TRACK_A ...). ``NULL`` falls back to the track."""
    not_implemented: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    """True for APH types deliberately outside the prototype scope."""
    not_implemented_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    apH_clause: Mapped[str] = mapped_column(String(64), nullable=False)
    needs_verification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
