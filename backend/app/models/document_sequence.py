"""Monotonic document number sequences.

Portal application numbers and decision letter numbers must be unique and
readable. The sequence lives in the database so a restart cannot reuse a
number (``AICTE-DEMO/YYYY/NNNN``).
"""

from __future__ import annotations

from sqlalchemy import Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin


class DecisionLetterSequence(TimestampMixin, Base):
    """The last letter number issued for one academic year."""

    __tablename__ = "decision_letter_number_seq"

    academic_year: Mapped[str] = mapped_column(String(9), primary_key=True)
    last_value: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
