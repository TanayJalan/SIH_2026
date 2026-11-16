"""Eligibility advisor tests: APH boundaries, missing evidence and the endpoint.

The worked numbers below come from the handbook wording quoted in each test:
"minimum of 30%", "at least 80% (Avg)", "more than 80%", "minimum of 50%".
The boundary tests exist because those three phrasings differ by one seat.
"""

from __future__ import annotations

import re
from collections.abc import Generator
from dataclasses import replace
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.models import ApplicationType, Institution
from app.services.eligibility_advisor import (
    AdmissionYear,
    AdvisorResult,
    CourseFill,
    EligibilityEvidence,
    EligibilityPolicy,
    EligibilityStatus,
    RouteCode,
    evaluate_all,
    extended_eoa,
    fill_pct,
    fn_oci,
    off_campus,
    tfw,
    working_professional,
)
from tests.support import TestData, auth_headers

TODAY = date(2026, 11, 16)

ADMISSION_YEARS = ("2021-22", "2022-23", "2023-24", "2024-25", "2025-26")

CLAUSE_PATTERN = re.compile(r"^APH [0-9][0-9A-Za-z.()]*$")


def _years(*shares: int, intake: int = 100) -> tuple[AdmissionYear, ...]:
    """Return one admission year per share, oldest first."""
    return tuple(
        AdmissionYear(academic_year=year, approved_intake=intake, admitted=share)
        for year, share in zip(ADMISSION_YEARS, shares, strict=True)
    )


BASE_EVIDENCE = EligibilityEvidence(
    nirf_8th=False,
    qs_asia_2024=False,
    naac_score=2.5,
    nba_courses_pct=10.0,
    nba_valid_until=date(2030, 4, 30),
    autonomous=False,
    admissions=_years(60, 60, 60, 60, 60),
    courses=(CourseFill("Civil Engineering", "UNDERGRADUATE", approved_intake=60, admitted=20),),
    aspirational_district=False,
    established_year=1990,
    in_jk_ladakh_ne=False,
)


def _criterion(result: AdvisorResult, code: str):
    """Return the criterion called ``code`` from any route of ``result``."""
    for route in result.routes:
        for criterion in route.criteria:
            if criterion.code == code:
                return criterion
    raise AssertionError(f"no criterion {code} in {[r.code for r in result.routes]}")


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_fill_pct_stays_none_without_approved_intake() -> None:
    """A course with no approved seats has no fill rate, not a 0% one."""
    assert fill_pct(0, 0) is None
    assert fill_pct(30, 60) == 50.0
    assert fill_pct(281, 360) == 78.06


# ---------------------------------------------------------------------------
# Extended EoA (APH 2.1a): any one of six criteria
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("nirf_8th", True, "EXTENDED_EOA_NIRF"),
        ("qs_asia_2024", True, "EXTENDED_EOA_QS"),
        ("nba_courses_pct", 35.0, "EXTENDED_EOA_NBA"),
        ("naac_score", 3.05, "EXTENDED_EOA_NAAC"),
        ("autonomous", True, "EXTENDED_EOA_AUTONOMOUS"),
        (
            "admissions",
            _years(90, 90, 90, 90, 90),
            "EXTENDED_EOA_80_PERCENT_ADMISSIONS",
        ),
    ],
)
def test_extended_eoa_passes_on_any_single_criterion(
    field: str,
    value: object,
    code: str,
) -> None:
    """APH 2.1a gives three years' approval on ANY ONE of the six criteria."""
    evidence = replace(BASE_EVIDENCE, **{field: value})
    advice = extended_eoa(evidence, TODAY)

    assert advice.status is EligibilityStatus.PASS
    met = [criterion.code for criterion in advice.criteria if criterion.status is EligibilityStatus.PASS]
    assert met == [code], "only the supplied criterion should pass"


def test_extended_eoa_fails_when_no_criterion_is_met() -> None:
    """Every criterion is a failure, so the route fails rather than reporting amber."""
    advice = extended_eoa(BASE_EVIDENCE, TODAY)

    assert advice.status is EligibilityStatus.FAIL
    assert all(criterion.status is EligibilityStatus.FAIL for criterion in advice.criteria)
    assert advice.suggestions, "a failing route must say what would fix it"


def test_extended_eoa_reports_unknown_when_evidence_is_missing() -> None:
    """Absent evidence is UNKNOWN, never FAIL: the handbook test proves nothing either way."""
    advice = extended_eoa(EligibilityEvidence(), TODAY)

    assert advice.status is EligibilityStatus.UNKNOWN
    assert len(advice.missing) == 6
    assert "need evidence" in advice.summary


def test_nba_threshold_is_inclusive_at_thirty_percent() -> None:
    """APH 2.1a(iii) says "minimum of 30%", so exactly 30% qualifies."""
    below = _criterion(evaluate_all(replace(BASE_EVIDENCE, nba_courses_pct=29.99), TODAY),
                       "EXTENDED_EOA_NBA")
    at = _criterion(evaluate_all(replace(BASE_EVIDENCE, nba_courses_pct=30.0), TODAY),
                    "EXTENDED_EOA_NBA")

    assert below.status is EligibilityStatus.FAIL
    assert at.status is EligibilityStatus.PASS


def test_nba_suggestion_names_the_current_share_and_the_target() -> None:
    """The "what would it take" line is the sentence the advisor screen shows."""
    evidence = replace(BASE_EVIDENCE, nba_courses_pct=22.0)
    advice = extended_eoa(evidence, TODAY)
    nba = next(c for c in advice.criteria if c.code == "EXTENDED_EOA_NBA")

    assert nba.status is EligibilityStatus.FAIL
    assert nba.observed == "22%"
    assert nba.required is not None and nba.required.startswith("at least 30%")
    assert nba.suggestion == "Raise NBA-accredited courses from 22% to 30%."


def test_nba_accreditation_must_still_be_valid_on_the_reference_date() -> None:
    """APH 2.1a(iii) requires validity on the cut-off date, not just a share."""
    lapsed = replace(
        BASE_EVIDENCE,
        nba_courses_pct=40.0,
        nba_valid_until=date(2025, 4, 30),
    )
    undated = replace(BASE_EVIDENCE, nba_courses_pct=40.0, nba_valid_until=None)

    lapsed_criterion = _criterion(evaluate_all(lapsed, TODAY), "EXTENDED_EOA_NBA")
    undated_criterion = _criterion(evaluate_all(undated, TODAY), "EXTENDED_EOA_NBA")

    assert lapsed_criterion.status is EligibilityStatus.FAIL
    assert lapsed_criterion.suggestion is not None
    assert "renewed" in lapsed_criterion.suggestion
    assert undated_criterion.status is EligibilityStatus.UNKNOWN


def test_naac_threshold_is_inclusive_at_three_point_zero_one() -> None:
    """APH 2.1a(iv) says "3.01 and above"."""
    below = _criterion(evaluate_all(replace(BASE_EVIDENCE, naac_score=3.0), TODAY),
                       "EXTENDED_EOA_NAAC")
    at = _criterion(evaluate_all(replace(BASE_EVIDENCE, naac_score=3.01), TODAY),
                    "EXTENDED_EOA_NAAC")

    assert below.status is EligibilityStatus.FAIL
    assert at.status is EligibilityStatus.PASS


def test_five_year_admissions_are_strictly_above_eighty_percent() -> None:
    """APH 2.1a(vi) says "more than 80%", so a flat 80% does not qualify."""
    flat = replace(BASE_EVIDENCE, admissions=_years(80, 80, 80, 80, 80))
    above = replace(BASE_EVIDENCE, admissions=_years(81, 81, 81, 81, 81))
    dip = replace(BASE_EVIDENCE, admissions=_years(95, 95, 95, 79, 95))

    assert _criterion(evaluate_all(flat, TODAY), "EXTENDED_EOA_80_PERCENT_ADMISSIONS").status is (
        EligibilityStatus.FAIL
    )
    assert _criterion(evaluate_all(above, TODAY), "EXTENDED_EOA_80_PERCENT_ADMISSIONS").status is (
        EligibilityStatus.PASS
    )
    dip_criterion = _criterion(
        evaluate_all(dip, TODAY), "EXTENDED_EOA_80_PERCENT_ADMISSIONS"
    )
    assert dip_criterion.status is EligibilityStatus.FAIL
    assert "2024-25" in dip_criterion.observed
    assert "2024-25" in dip_criterion.suggestion


def test_five_year_admissions_need_five_years_of_evidence() -> None:
    """Four recorded years cannot answer a five-year test."""
    partial = replace(BASE_EVIDENCE, admissions=_years(90, 90, 90, 90, 90)[1:])
    criterion = _criterion(
        evaluate_all(partial, TODAY), "EXTENDED_EOA_80_PERCENT_ADMISSIONS"
    )

    assert criterion.status is EligibilityStatus.UNKNOWN
    assert "4 of the last five" in criterion.detail


# ---------------------------------------------------------------------------
# FN/OCI seats (APH 2.9): 80% average over three years, inclusive
# ---------------------------------------------------------------------------


def test_fn_oci_average_is_inclusive_at_eighty_percent() -> None:
    """APH 2.9 says "at least 80% (Avg) enrolment in last three years"."""
    assert fn_oci(BASE_EVIDENCE).status is EligibilityStatus.FAIL

    exactly = replace(BASE_EVIDENCE, admissions=_years(90, 90, 80, 80, 80))
    assert fn_oci(exactly).status is EligibilityStatus.PASS

    short = replace(BASE_EVIDENCE, admissions=_years(90, 90, 79, 79, 79))
    assert fn_oci(short).status is EligibilityStatus.FAIL


def test_fn_oci_needs_three_years_of_admissions() -> None:
    """Two years cannot produce a three-year average."""
    partial = replace(BASE_EVIDENCE, admissions=_years(90, 90, 90, 90, 90)[-2:])

    advice = fn_oci(partial)

    assert advice.status is EligibilityStatus.UNKNOWN
    assert "2 of the last three" in advice.criteria[0].detail


# ---------------------------------------------------------------------------
# Off-campus (APH 2.11a): ten years plus one criterion
# ---------------------------------------------------------------------------


def test_off_campus_needs_ten_years_and_one_criterion() -> None:
    """APH 2.11a: "existence for at least Ten (10) years" AND any one criterion."""
    strong = replace(BASE_EVIDENCE, naac_score=3.4)
    nine_years = replace(strong, established_year=2017)
    ten_years = replace(strong, established_year=2016)

    assert off_campus(nine_years, TODAY).status is EligibilityStatus.FAIL
    assert off_campus(ten_years, TODAY).status is EligibilityStatus.PASS


def test_off_campus_fails_when_tenure_passes_but_no_criterion_does() -> None:
    """A long-established institution still needs one APH 2.11a criterion."""
    advice = off_campus(BASE_EVIDENCE, TODAY)

    assert advice.status is EligibilityStatus.FAIL
    tenure = next(c for c in advice.criteria if c.code == "OFF_CAMPUS_TENURE")
    assert tenure.status is EligibilityStatus.PASS


def test_off_campus_unknown_tenure_is_not_a_failure() -> None:
    """An unknown establishment year keeps the route amber, it does not block it."""
    advice = off_campus(replace(BASE_EVIDENCE, established_year=None, naac_score=3.4), TODAY)

    assert advice.status is EligibilityStatus.UNKNOWN
    assert advice.criteria[0].status is EligibilityStatus.UNKNOWN


def test_off_campus_failure_wins_over_unknown_tenure() -> None:
    """A known blocker beats missing evidence: no criterion passes and none can."""
    advice = off_campus(replace(BASE_EVIDENCE, established_year=None), TODAY)

    assert advice.status is EligibilityStatus.FAIL
    assert advice.criteria[0].status is EligibilityStatus.UNKNOWN


def test_off_campus_nba_threshold_is_fifty_percent() -> None:
    """APH 2.11a(iii) raises the NBA bar to 50%."""
    below = _criterion(
        evaluate_all(replace(BASE_EVIDENCE, nba_courses_pct=45.0), TODAY),
        "OFF_CAMPUS_NBA",
    )
    at = _criterion(
        evaluate_all(replace(BASE_EVIDENCE, nba_courses_pct=50.0), TODAY),
        "OFF_CAMPUS_NBA",
    )

    assert below.status is EligibilityStatus.FAIL
    assert at.status is EligibilityStatus.PASS


# ---------------------------------------------------------------------------
# Working professionals (APH 2.6l): any one of three criteria
# ---------------------------------------------------------------------------


def test_working_professional_accepts_any_one_criterion() -> None:
    """APH 2.6l lists enrolment, aspirational district and J&K/NER as alternatives."""
    high_enrolment = replace(BASE_EVIDENCE, admissions=_years(90, 90, 90, 90, 90))
    district = replace(BASE_EVIDENCE, aspirational_district=True)
    northern = replace(BASE_EVIDENCE, in_jk_ladakh_ne=True)

    assert working_professional(high_enrolment).status is EligibilityStatus.PASS
    assert working_professional(district).status is EligibilityStatus.PASS
    assert working_professional(northern).status is EligibilityStatus.PASS
    assert working_professional(BASE_EVIDENCE).status is EligibilityStatus.FAIL


def test_working_professional_enrolment_is_strictly_above_eighty_percent() -> None:
    """APH 2.6(l)(i) says "more than 80% average enrollment"."""
    exactly = replace(BASE_EVIDENCE, admissions=_years(90, 90, 80, 80, 80))
    above = replace(BASE_EVIDENCE, admissions=_years(90, 90, 90, 81, 81))

    assert working_professional(exactly).status is EligibilityStatus.FAIL
    assert working_professional(above).status is EligibilityStatus.PASS


# ---------------------------------------------------------------------------
# TFW seats (APH 6.42): 50% of approved intake, per course
# ---------------------------------------------------------------------------


def test_tfw_passes_when_one_course_fills_half_its_intake() -> None:
    """APH 6.42(d)(i) is per course and says "a minimum of 50%"."""
    evidence = replace(
        BASE_EVIDENCE,
        courses=(
            CourseFill("Civil Engineering", "UNDERGRADUATE", approved_intake=60, admitted=20),
            CourseFill("Computer Science", "UNDERGRADUATE", approved_intake=120, admitted=60),
        ),
    )

    advice = tfw(evidence)

    assert advice.status is EligibilityStatus.PASS
    assert advice.criteria[0].observed == "50% in Computer Science"


def test_tfw_fails_when_every_course_is_below_half_full() -> None:
    """No course clears 50%, so the scheme cannot be offered."""
    evidence = replace(
        BASE_EVIDENCE,
        courses=(
            CourseFill("Civil Engineering", "UNDERGRADUATE", approved_intake=60, admitted=29),
            CourseFill("Mechanical Engineering", "UNDERGRADUATE", approved_intake=60, admitted=18),
        ),
    )

    advice = tfw(evidence)

    assert advice.status is EligibilityStatus.FAIL
    assert advice.criteria[0].suggestion is not None
    assert "Civil Engineering reached 48.33%" in advice.criteria[0].suggestion


def test_tfw_without_course_data_is_unknown() -> None:
    """Course intake and admission figures are the evidence for APH 6.42(d)(i)."""
    advice = tfw(replace(BASE_EVIDENCE, courses=()))

    assert advice.status is EligibilityStatus.UNKNOWN


# ---------------------------------------------------------------------------
# Result shape and policy
# ---------------------------------------------------------------------------


def test_evaluate_all_returns_the_five_routes_in_screen_order() -> None:
    """The advisor screen shows the routes in handbook order."""
    result = evaluate_all(BASE_EVIDENCE, TODAY)

    assert [route.code for route in result.routes] == [
        RouteCode.EXTENDED_EOA,
        RouteCode.FN_OCI,
        RouteCode.OFF_CAMPUS,
        RouteCode.WORKING_PROFESSIONAL,
        RouteCode.TFW,
    ]
    assert result.as_of == TODAY
    assert result.route(RouteCode.TFW).code is RouteCode.TFW


def test_every_criterion_cites_an_aph_clause() -> None:
    """No advisor rule may ship without the clause it came from."""
    result = evaluate_all(BASE_EVIDENCE, TODAY)
    codes: set[str] = set()
    for route in result.routes:
        assert CLAUSE_PATTERN.match(route.clause), route.clause
        for criterion in route.criteria:
            assert CLAUSE_PATTERN.match(criterion.clause), criterion.clause
            assert criterion.code not in codes, f"duplicate criterion code {criterion.code}"
            codes.add(criterion.code)


def test_routes_link_to_an_implemented_application_type() -> None:
    """Every route with an application type names one the portal implements."""
    result = evaluate_all(BASE_EVIDENCE, TODAY)

    for route in result.routes:
        if route.application_type is not None:
            assert ApplicationType(route.application_type)
    assert result.route(RouteCode.TFW).application_type is None


def test_policy_can_override_thresholds_without_touching_logic() -> None:
    """Thresholds are data: a stricter NAAC bar changes the verdict on its own."""
    lenient = replace(BASE_EVIDENCE, naac_score=3.2)
    strict_policy = EligibilityPolicy(naac_min_score=3.5)

    assert extended_eoa(lenient, TODAY).status is EligibilityStatus.PASS
    strict = extended_eoa(lenient, TODAY, strict_policy)
    naac = next(c for c in strict.criteria if c.code == "EXTENDED_EOA_NAAC")
    assert naac.status is EligibilityStatus.FAIL
    assert naac.required == "at least 3.5 / 4.0"


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

WEST_ACCREDITATION = {
    "nirf_8th": False,
    "qs_asia_2024": False,
    "naac_score": 3.12,
    "nba_courses_pct": 22.0,
    "nba_valid_until": "2027-04-30",
    "autonomous": False,
    "admissions": [
        {"academic_year": "2021-22", "approved_intake": 300, "admitted": 270},
        {"academic_year": "2022-23", "approved_intake": 300, "admitted": 264},
        {"academic_year": "2023-24", "approved_intake": 300, "admitted": 234},
        {"academic_year": "2024-25", "approved_intake": 300, "admitted": 237},
        {"academic_year": "2025-26", "approved_intake": 300, "admitted": 240},
    ],
    "courses": [
        {"course_name": "Civil Engineering", "level": "UNDERGRADUATE",
         "approved_intake": 60, "admitted": 41},
        {"course_name": "Computer Science", "level": "UNDERGRADUATE",
         "approved_intake": 120, "admitted": 96},
    ],
    "aspirational_district": False,
}


@pytest.fixture
def west_accreditation(test_data: TestData) -> Generator[None, None, None]:
    """Put advisor evidence on the west fixture institution and restore it after."""
    with SessionLocal() as db:
        institution = db.get(Institution, test_data.institutions["west"])
        assert institution is not None
        original = dict(institution.accreditation or {})
        institution.accreditation = WEST_ACCREDITATION
        db.commit()
    yield
    with SessionLocal() as db:
        institution = db.get(Institution, test_data.institutions["west"])
        assert institution is not None
        institution.accreditation = original
        db.commit()


def test_advisor_endpoint_returns_every_route_with_evidence(
    api_client: TestClient,
    test_data: TestData,
    west_accreditation: None,
) -> None:
    """The institution admin sees the five routes with values, clauses and next steps."""
    headers = auth_headers(
        api_client, test_data.users["institution_admin_west"], test_data.password
    )
    response = api_client.get("/eligibility/advisor", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["institution_id"] == str(test_data.institutions["west"])
    assert [route["code"] for route in body["routes"]] == [
        "EXTENDED_EOA",
        "FN_OCI",
        "OFF_CAMPUS",
        "WORKING_PROFESSIONAL",
        "TFW",
    ]

    by_code = {route["code"]: route for route in body["routes"]}
    assert by_code["EXTENDED_EOA"]["status"] == "PASS"
    assert by_code["EXTENDED_EOA"]["application_type"] == "EXTENDED_EOA"
    assert by_code["FN_OCI"]["application_type"] == "SUPERNUMERARY_FN_OCI"
    assert by_code["OFF_CAMPUS"]["application_type"] == "OFF_CAMPUS"
    assert by_code["TFW"]["application_type"] is None

    criteria = {row["code"]: row for row in by_code["EXTENDED_EOA"]["criteria"]}
    assert criteria["EXTENDED_EOA_NBA"]["apH_clause"] == "APH 2.1a(iii)"
    assert criteria["EXTENDED_EOA_NBA"]["observed"] == "22%"
    assert criteria["EXTENDED_EOA_NBA"]["suggestion"] == (
        "Raise NBA-accredited courses from 22% to 30%."
    )
    assert body["as_of"] == date.fromisoformat(body["as_of"]).isoformat()


def test_advisor_endpoint_without_evidence_reports_unknown(
    api_client: TestClient,
    test_data: TestData,
) -> None:
    """An institution with no evidence on file gets amber, not a false red."""
    headers = auth_headers(
        api_client, test_data.users["institution_admin_east"], test_data.password
    )
    response = api_client.get("/eligibility/advisor", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["institution_id"] == str(test_data.institutions["east"])
    statuses = {route["status"] for route in body["routes"]}
    assert statuses == {"UNKNOWN"}
    assert all(route["criteria"] for route in body["routes"])


@pytest.mark.parametrize(
    "user_key",
    ["scrutiny", "regional", "super", "regulation"],
)
def test_advisor_endpoint_is_restricted_to_institution_admins(
    api_client: TestClient,
    test_data: TestData,
    user_key: str,
) -> None:
    """Officers and super admins have no institution to advise."""
    headers = auth_headers(api_client, test_data.users[user_key], test_data.password)

    response = api_client.get("/eligibility/advisor", headers=headers)

    assert response.status_code == 403
