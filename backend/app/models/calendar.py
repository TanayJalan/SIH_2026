"""Public notices and Academic Calendar events.

APH does not publish the actual dates in the handbook: cut-off dates come from
AICTE's Public Notice and the Academic Calendar. Both tables are therefore
admin-editable configuration seeded with clearly labelled demo values.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Date, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ApplicationCategory, CalendarEventKey
from app.models.types import enum_type

if TYPE_CHECKING:
    from app.models.application import Application


class PublicNotice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The submission window for one academic year and category."""

    __tablename__ = "public_notices"
    __table_args__ = (
        UniqueConstraint(
            "academic_year",
            "category",
            name="uq_public_notices_year_category",
        ),
        CheckConstraint("cutoff_on >= opens_on", name="public_notice_window_ordered"),
    )

    academic_year: Mapped[str] = mapped_column(String(9), nullable=False, index=True)
    category: Mapped[ApplicationCategory] = mapped_column(
        enum_type(ApplicationCategory, "application_category", length=32),
        nullable=False,
        index=True,
    )
    opens_on: Mapped[date] = mapped_column(Date, nullable=False)
    cutoff_on: Mapped[date] = mapped_column(Date, nullable=False)
    apH_clause: Mapped[str] = mapped_column(String(64), nullable=False)
    needs_verification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    is_demo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    applications: Mapped[list[Application]] = relationship(back_populates="public_notice")


class AcademicCalendarEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A dated APH event such as the EoA last date or the enrolment upload."""

    __tablename__ = "academic_calendar_events"
    __table_args__ = (
        UniqueConstraint(
            "academic_year",
            "event_key",
            name="uq_academic_calendar_events_year_key",
        ),
    )

    academic_year: Mapped[str] = mapped_column(String(9), nullable=False, index=True)
    event_key: Mapped[CalendarEventKey] = mapped_column(
        enum_type(CalendarEventKey, "calendar_event_key", length=32),
        nullable=False,
        index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    apH_clause: Mapped[str] = mapped_column(String(64), nullable=False)
    needs_verification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    is_demo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
