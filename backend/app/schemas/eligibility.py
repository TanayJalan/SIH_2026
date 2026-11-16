"""Eligibility advisor response schemas.

The shapes mirror :mod:`app.services.eligibility_advisor` one for one; the only
rename is ``clause`` to ``apH_clause``, which is the name the rest of the API
uses for a handbook reference.
"""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, Field

from app.services.eligibility_advisor import EligibilityStatus, RouteCode


class EligibilityCriterionRead(BaseModel):
    """One test of one route, with the value observed and what would fix it."""

    code: str
    label: str
    apH_clause: str
    status: EligibilityStatus
    observed: str | None = None
    """The recorded value in display form, ``None`` when nothing is on record."""
    required: str | None = None
    detail: str
    suggestion: str | None = None


class EligibilityRouteRead(BaseModel):
    """The verdict for one approval route."""

    code: RouteCode
    label: str
    apH_clause: str
    status: EligibilityStatus
    summary: str
    criteria: list[EligibilityCriterionRead] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    application_type: str | None = None
    """Portal application type that starts this route, ``None`` when there is none."""
    notes: list[str] = Field(default_factory=list)


class EligibilityAdvisorRead(BaseModel):
    """All five route verdicts for the signed-in institution."""

    institution_id: uuid.UUID
    institution_name: str
    as_of: date
    """The date the checks were run, used for NBA validity and years of existence."""
    routes: list[EligibilityRouteRead] = Field(default_factory=list)
