"""Generation of the AICTE portal application number.

The number is produced by the ``portal_application_no_seq`` database sequence,
so concurrent submissions can never collide. Keeping it in its own module lets
both the workspace service and the workflow engine use it without a circular
import.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def next_portal_application_no(db: Session, academic_year: str) -> str:
    """Return the next portal application number for an academic year.

    Format: ``AICTE/<academic year>/<7 digits>``. The sequence is global, so
    the counter never repeats even across academic years.
    """
    value = db.scalar(select(func.nextval("portal_application_no_seq")))
    return f"AICTE/{academic_year}/{int(value):07d}"
