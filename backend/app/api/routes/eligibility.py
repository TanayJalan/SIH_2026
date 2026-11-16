"""Eligibility advisor endpoint (APH 2.1a, 2.6l, 2.9, 2.11a, 6.42).

Read-only: the advisor explains which approval route an institution can take and
what stands in the way, so nothing is written and nothing is audited. The
checks themselves are pure functions in
:mod:`app.services.eligibility_advisor`; this module only assembles the evidence
from the institution row and shapes the response.
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from app.api.dependencies import ClockDep, DbSession, require_roles
from app.models.enums import Role
from app.models.institution import Institution
from app.models.user import User
from app.schemas.aph_profiles import AccreditationProfile
from app.schemas.common import ErrorResponse
from app.schemas.eligibility import (
    EligibilityAdvisorRead,
    EligibilityCriterionRead,
    EligibilityRouteRead,
)
from app.services import eligibility_advisor as advisor
from app.services.eligibility_advisor import (
    AdmissionYear,
    AdvisorResult,
    CourseFill,
    EligibilityEvidence,
)

logger = logging.getLogger("app.eligibility")

router = APIRouter(prefix="/eligibility", tags=["eligibility"])

InstitutionAdmin = Annotated[User, Depends(require_roles(Role.INSTITUTION_ADMIN))]


def _profile(institution: Institution) -> AccreditationProfile:
    """Read the institution's accreditation profile, degrading to empty on bad data.

    The JSONB column is validated on write, so a validation error here means a
    row predates the current schema. Returning an empty profile makes every
    criterion report ``UNKNOWN`` ("no evidence on record") instead of failing
    the screen.
    """
    raw = institution.accreditation or {}
    try:
        return AccreditationProfile.model_validate(raw)
    except ValidationError:
        logger.warning(
            "institution %s has an unreadable accreditation profile; treating it as empty",
            institution.aicte_id,
        )
        return AccreditationProfile()


def _evidence(institution: Institution) -> EligibilityEvidence:
    """Collect the evidence the five advisors read."""
    profile = _profile(institution)
    return EligibilityEvidence(
        nirf_8th=profile.nirf_8th,
        qs_asia_2024=profile.qs_asia_2024,
        naac_score=profile.naac_score,
        nba_courses_pct=profile.nba_courses_pct,
        nba_valid_until=profile.nba_valid_until,
        autonomous=profile.autonomous,
        admissions=tuple(
            AdmissionYear(
                academic_year=row.academic_year,
                approved_intake=row.approved_intake,
                admitted=row.admitted,
            )
            for row in profile.admissions
        ),
        courses=tuple(
            CourseFill(
                course_name=row.course_name,
                level=row.level,
                approved_intake=row.approved_intake,
                admitted=row.admitted,
            )
            for row in profile.courses
        ),
        aspirational_district=profile.aspirational_district,
        established_year=institution.established_year,
        in_jk_ladakh_ne=institution.in_jk_ladakh_ne,
    )


def _to_read(
    institution: Institution,
    result: AdvisorResult,
) -> EligibilityAdvisorRead:
    """Convert the pure-function result into the API response."""
    return EligibilityAdvisorRead(
        institution_id=institution.id,
        institution_name=institution.name,
        as_of=result.as_of,
        routes=[
            EligibilityRouteRead(
                code=route.code,
                label=route.label,
                apH_clause=route.clause,
                status=route.status,
                summary=route.summary,
                criteria=[
                    EligibilityCriterionRead(
                        code=criterion.code,
                        label=criterion.label,
                        apH_clause=criterion.clause,
                        status=criterion.status,
                        observed=criterion.observed,
                        required=criterion.required,
                        detail=criterion.detail,
                        suggestion=criterion.suggestion,
                    )
                    for criterion in route.criteria
                ],
                suggestions=list(route.suggestions),
                application_type=route.application_type,
                notes=list(route.notes),
            )
            for route in result.routes
        ],
    )


@router.get(
    "/advisor",
    response_model=EligibilityAdvisorRead,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    summary="Eligibility advisor for the signed-in institution",
)
def read_advisor(
    current_user: InstitutionAdmin,
    db: DbSession,
    clock: ClockDep,
) -> EligibilityAdvisorRead:
    """Return the five route verdicts and the evidence behind each one.

    The reference date comes from the simulated clock so the NBA validity test
    (APH 2.1a(iii), 2.11a(iii)) and years of existence (APH 2.11a) move with the
    demo time control.
    """
    institution_id: uuid.UUID | None = current_user.institution_id
    institution = db.get(Institution, institution_id) if institution_id else None
    if institution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No institution is linked to this account",
        )
    result = advisor.evaluate_all(_evidence(institution), clock.now().date())
    return _to_read(institution, result)
