"""Pure eligibility advisors for the APH extended-approval routes.

Nothing here touches the database, the clock or the network. The caller passes
the evidence and the reference date, so every function is deterministic and
unit-testable.

Each criterion carries the clause it comes from, taken from
``docs/reference/APH_SPEC.md`` section 3.2 and from the handbook clauses quoted
below. The thresholds live in :class:`EligibilityPolicy`, whose defaults are the
handbook values, so an administrator can change them without editing logic.

A verdict is three-state on purpose. ``UNKNOWN`` means the evidence needed to
answer the question is missing; it is never reported as a failure, because the
handbook's tests are all "at least"/"more than" comparisons and an absent value
proves nothing either way.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------


class EligibilityStatus(StrEnum):
    """Outcome of one eligibility criterion."""

    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class RouteCode(StrEnum):
    """The five approval routes the advisor covers."""

    EXTENDED_EOA = "EXTENDED_EOA"
    FN_OCI = "FN_OCI"
    OFF_CAMPUS = "OFF_CAMPUS"
    WORKING_PROFESSIONAL = "WORKING_PROFESSIONAL"
    TFW = "TFW"


@dataclass(frozen=True, slots=True)
class EligibilityPolicy:
    """Thresholds the advisors apply, with the handbook values as defaults.

    ``admission_share_pct`` is shared by APH 2.1a(vi), 2.6(l)(i) and 2.9 because
    all three clauses use the same 80% admission test. ``extended_eoa`` applies it
    strictly ("more than 80%") and the other two inclusively ("at least 80%").
    """

    extended_eoa_cutoff_share_pct: float = 30.0
    """Minimum share of eligible courses with NBA accreditation (APH 2.1a(iii))."""
    off_campus_cutoff_share_pct: float = 50.0
    """Same test for off-campus, at a higher bar (APH 2.11a(iii))."""
    naac_min_score: float = 3.01
    """NAAC score on the 4-point scale (APH 2.1a(iv), 2.11a(iv))."""
    admission_share_pct: float = 80.0
    """Admission test shared by APH 2.1a(vi), 2.6(l)(i) and 2.9."""
    extended_eoa_admission_years: int = 5
    """Consecutive academic years for Extended EoA (APH 2.1a(vi))."""
    enrolment_average_years: int = 3
    """Years averaged for FN/OCI and working-professional seats (APH 2.9, 2.6l)."""
    off_campus_min_years: int = 10
    """Minimum years of existence before an off-campus may be introduced (APH 2.11a)."""
    tfw_min_fill_pct: float = 50.0
    """Minimum fill of approved intake in a course for TFW seats (APH 6.42d(i))."""


DEFAULT_POLICY = EligibilityPolicy()


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AdmissionYear:
    """Admissions against approved intake for one academic year."""

    academic_year: str
    """Academic year in ``YYYY-YY`` form, for example ``2025-26``."""
    approved_intake: int
    admitted: int


@dataclass(frozen=True, slots=True)
class CourseFill:
    """Fill rate of one course in the last academic year (APH 6.42d(i))."""

    course_name: str
    level: str
    approved_intake: int
    admitted: int


@dataclass(frozen=True, slots=True)
class EligibilityEvidence:
    """Everything the advisors may read about one institution.

    Every field is optional: a missing value produces an ``UNKNOWN`` criterion
    instead of a guess.
    """

    nirf_8th: bool | None = None
    qs_asia_2024: bool | None = None
    naac_score: float | None = None
    nba_courses_pct: float | None = None
    nba_valid_until: date | None = None
    autonomous: bool | None = None
    admissions: tuple[AdmissionYear, ...] = ()
    courses: tuple[CourseFill, ...] = ()
    aspirational_district: bool | None = None
    established_year: int | None = None
    in_jk_ladakh_ne: bool | None = None


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Criterion:
    """One test, its observed value and what it would take to pass."""

    code: str
    label: str
    clause: str
    """The APH clause the criterion comes from, for example ``APH 2.1a(iii)``."""
    status: EligibilityStatus
    observed: str | None
    """The recorded value in display form, ``None`` when nothing is on record."""
    required: str | None
    """The threshold in display form."""
    detail: str
    """One sentence explaining the verdict."""
    suggestion: str | None = None
    """What would take the institution over the line; only set when it fails."""


@dataclass(frozen=True, slots=True)
class RouteAdvice:
    """The verdict for one approval route, with the criteria behind it."""

    code: RouteCode
    label: str
    clause: str
    status: EligibilityStatus
    summary: str
    criteria: tuple[Criterion, ...] = ()
    application_type: str | None = None
    """The portal application type that starts this route, ``None`` when there is none."""
    notes: tuple[str, ...] = ()

    @property
    def suggestions(self) -> tuple[str, ...]:
        """Return the "what would it take" lines for the criteria that fail."""
        return tuple(criterion.suggestion for criterion in self.criteria if criterion.suggestion)

    @property
    def met(self) -> tuple[Criterion, ...]:
        """Return the criteria that already pass."""
        return tuple(c for c in self.criteria if c.status is EligibilityStatus.PASS)

    @property
    def missing(self) -> tuple[Criterion, ...]:
        """Return the criteria that cannot be answered from the evidence."""
        return tuple(c for c in self.criteria if c.status is EligibilityStatus.UNKNOWN)


@dataclass(frozen=True, slots=True)
class AdvisorResult:
    """All five route verdicts for one institution on one date."""

    as_of: date
    routes: tuple[RouteAdvice, ...] = field(default_factory=tuple)

    def route(self, code: RouteCode) -> RouteAdvice:
        """Return the advice for ``code``; every code is always present."""
        for advice in self.routes:
            if advice.code is code:
                return advice
        raise KeyError(code)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


_YEAR_WORDS = {
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
}


def _year_word(count: int) -> str:
    """Spell out a small count: prose reads better than "3-year"."""
    return _YEAR_WORDS.get(count, str(count))


def _trim(value: float) -> str:
    """Return ``value`` without trailing zeros (``30.0`` becomes ``30``)."""
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text or "0"


def _format(value: float, unit: str) -> str:
    """Render a number the way the handbook prints it."""
    if unit == "pct":
        return f"{_trim(value)}%"
    if unit == "score":
        return f"{_trim(value)} / 4.0"
    if unit == "years":
        whole = int(value)
        return f"{whole} year" if whole == 1 else f"{whole} years"
    return _trim(value)


def _requirement_label(threshold: float, unit: str, strict: bool) -> str:
    """Return ``at least 30%`` or ``more than 80%`` for the required column."""
    prefix = "more than " if strict else "at least "
    return prefix + _format(threshold, unit)


def _target_label(threshold: float, unit: str, strict: bool) -> str:
    """Return the bare target used inside a suggestion (``30%``)."""
    return ("more than " if strict else "") + _format(threshold, unit)


def fill_pct(admitted: int, approved_intake: int) -> float | None:
    """Return seats filled as a percentage of approved intake.

    ``None`` when there is no approved intake to fill: dividing by zero would
    claim a fill rate that does not exist.
    """
    if approved_intake <= 0:
        return None
    return round(admitted * 100 / approved_intake, 2)


# ---------------------------------------------------------------------------
# Criterion builders
# ---------------------------------------------------------------------------


def _criterion(
    code: str,
    label: str,
    clause: str,
    status: EligibilityStatus,
    *,
    observed: str | None,
    required: str | None,
    detail: str,
    suggestion: str | None = None,
) -> Criterion:
    """Build one criterion row."""
    return Criterion(
        code=code,
        label=label,
        clause=clause,
        status=status,
        observed=observed,
        required=required,
        detail=detail,
        suggestion=suggestion,
    )


def _minimum(
    code: str,
    label: str,
    clause: str,
    value: float | None,
    threshold: float,
    *,
    unit: str,
    subject: str,
    missing: str,
    strict: bool = False,
) -> Criterion:
    """Compare ``value`` with a minimum and phrase the shortfall as a suggestion."""
    required = _requirement_label(threshold, unit, strict)
    if value is None:
        return _criterion(
            code,
            label,
            clause,
            EligibilityStatus.UNKNOWN,
            observed=None,
            required=required,
            detail=missing,
            suggestion=f"Record the {subject} so this check can run.",
        )
    passed = value > threshold if strict else value >= threshold
    observed = _format(value, unit)
    if passed:
        return _criterion(
            code,
            label,
            clause,
            EligibilityStatus.PASS,
            observed=observed,
            required=required,
            detail=f"{observed} meets the requirement of {required}.",
        )
    return _criterion(
        code,
        label,
        clause,
        EligibilityStatus.FAIL,
        observed=observed,
        required=required,
        detail=f"{observed} is below the requirement of {required}.",
        suggestion=(
            f"Raise the {subject} from {observed} to "
            f"{_target_label(threshold, unit, strict)}."
        ),
    )


def _flag(
    code: str,
    label: str,
    clause: str,
    value: bool | None,
    *,
    pass_detail: str,
    fail_detail: str,
    suggestion: str | None,
    missing: str,
) -> Criterion:
    """Build a yes/no criterion."""
    if value is None:
        return _criterion(
            code,
            label,
            clause,
            EligibilityStatus.UNKNOWN,
            observed=None,
            required="Yes",
            detail=missing,
        )
    if value:
        return _criterion(
            code,
            label,
            clause,
            EligibilityStatus.PASS,
            observed="Yes",
            required="Yes",
            detail=pass_detail,
        )
    return _criterion(
        code,
        label,
        clause,
        EligibilityStatus.FAIL,
        observed="No",
        required="Yes",
        detail=fail_detail,
        suggestion=suggestion,
    )


def _disjunction(statuses: Sequence[EligibilityStatus]) -> EligibilityStatus:
    """Return PASS when any status passes, else UNKNOWN if one is missing."""
    seen = set(statuses)
    if EligibilityStatus.PASS in seen:
        return EligibilityStatus.PASS
    if EligibilityStatus.UNKNOWN in seen:
        return EligibilityStatus.UNKNOWN
    return EligibilityStatus.FAIL


def _conjunction(statuses: Sequence[EligibilityStatus]) -> EligibilityStatus:
    """Return FAIL as soon as one status fails, else UNKNOWN if one is missing."""
    seen = set(statuses)
    if EligibilityStatus.FAIL in seen:
        return EligibilityStatus.FAIL
    if EligibilityStatus.UNKNOWN in seen:
        return EligibilityStatus.UNKNOWN
    return EligibilityStatus.PASS


def _any_of(criteria: Sequence[Criterion]) -> EligibilityStatus:
    """Apply :func:`_disjunction` to the criteria of one route."""
    return _disjunction([criterion.status for criterion in criteria])


def _usable_admissions(
    evidence: EligibilityEvidence,
    count: int,
) -> list[tuple[AdmissionYear, float]]:
    """Return the most recent ``count`` years that have a fill rate, newest first."""
    ordered = sorted(evidence.admissions, key=lambda row: row.academic_year, reverse=True)
    usable: list[tuple[AdmissionYear, float]] = []
    for row in ordered:
        pct = fill_pct(row.admitted, row.approved_intake)
        if pct is None:
            continue
        usable.append((row, pct))
        if len(usable) == count:
            break
    return usable


def _nba_criterion(
    code: str,
    label: str,
    clause: str,
    evidence: EligibilityEvidence,
    *,
    threshold: float,
    reference_date: date,
) -> Criterion:
    """Apply the NBA share test and check the accreditation was valid on the day.

    APH 2.1a(iii) and 2.11a(iii) both require the share of eligible courses with
    NBA accreditation *having validity* on the cut-off date. The handbook prints
    30 April 2025 because that is the date for the 2024-25 cycle (see
    ``docs/reference/APH_SPEC.md`` section 12), so the caller supplies the date
    the check is run on.
    """
    required = f"at least {_format(threshold, 'pct')} with NBA validity current"
    pct = evidence.nba_courses_pct
    if pct is None:
        return _criterion(
            code,
            label,
            clause,
            EligibilityStatus.UNKNOWN,
            observed=None,
            required=required,
            detail="The share of eligible courses holding NBA accreditation is not recorded.",
            suggestion="Record the share of NBA-accredited courses so this check can run.",
        )
    observed = _format(pct, "pct")
    if pct < threshold:
        return _criterion(
            code,
            label,
            clause,
            EligibilityStatus.FAIL,
            observed=observed,
            required=required,
            detail=(
                f"{observed} of eligible courses are accredited, below the "
                f"{_format(threshold, 'pct')} minimum."
            ),
            suggestion=(
                f"Raise NBA-accredited courses from {observed} to "
                f"{_target_label(threshold, 'pct', False)}."
            ),
        )
    valid_until = evidence.nba_valid_until
    if valid_until is None:
        return _criterion(
            code,
            label,
            clause,
            EligibilityStatus.UNKNOWN,
            observed=observed,
            required=required,
            detail=(
                f"{observed} of eligible courses are accredited, but the validity date "
                "is not recorded."
            ),
            suggestion=(
                "Record the date the NBA accreditation runs to; it must still be valid "
                "on the day of application."
            ),
        )
    if valid_until < reference_date:
        return _criterion(
            code,
            label,
            clause,
            EligibilityStatus.FAIL,
            observed=observed,
            required=required,
            detail=(
                f"{observed} of eligible courses are accredited, but validity ended on "
                f"{valid_until.isoformat()}, before {reference_date.isoformat()}."
            ),
            suggestion=(
                f"Get NBA accreditation renewed for at least "
                f"{_target_label(threshold, 'pct', False)} of eligible courses before "
                "applying."
            ),
        )
    return _criterion(
        code,
        label,
        clause,
        EligibilityStatus.PASS,
        observed=observed,
        required=required,
        detail=(
            f"{observed} of eligible courses are accredited, valid until "
            f"{valid_until.isoformat()}."
        ),
    )


def _years_since(established_year: int | None, reference_date: date) -> int | None:
    """Return completed years of existence, or ``None`` when the year is unknown."""
    if established_year is None:
        return None
    return reference_date.year - established_year


# ---------------------------------------------------------------------------
# Route 1: Extended EoA (APH 2.1a)
# ---------------------------------------------------------------------------

def _fifth_year_admissions(
    evidence: EligibilityEvidence,
    policy: EligibilityPolicy,
    *,
    code: str,
    clause: str,
) -> Criterion:
    """Apply the "more than 80% in each of the last five years" test.

    APH 2.1a(vi) and APH 2.11a(vi) use identical wording, so both routes share
    this criterion and only the clause reference changes.
    """
    label = "Above 80% admissions in each of the last five academic years"
    years = policy.extended_eoa_admission_years
    threshold = policy.admission_share_pct
    required = (
        f"more than {_format(threshold, 'pct')} in each of the last "
        f"{_year_word(years)} academic years"
    )
    rows = _usable_admissions(evidence, years)
    if len(rows) < years:
        if not rows:
            detail = "No admissions against approved intake are on record."
        else:
            detail = (
                f"Only {len(rows)} of the last {_year_word(years)} academic years have admissions "
                "against approved intake on record."
            )
        return _criterion(
            code,
            label,
            clause,
            EligibilityStatus.UNKNOWN,
            observed=None,
            required=required,
            detail=detail,
            suggestion=(
                f"Record admissions against approved intake for {_year_word(years)} "
                "complete academic years so this check can run."
            ),
        )
    weakest_year, weakest_pct = min(rows, key=lambda item: item[1])
    observed = f"{_format(weakest_pct, 'pct')} in {weakest_year.academic_year}"
    if weakest_pct > threshold:
        return _criterion(
            code,
            label,
            clause,
            EligibilityStatus.PASS,
            observed=observed,
            required=required,
            detail=(
                f"Every year from {rows[-1][0].academic_year} to {rows[0][0].academic_year} "
                f"filled more than {_format(threshold, 'pct')} of approved intake; "
                f"{weakest_year.academic_year} was the weakest."
            ),
        )
    return _criterion(
        code,
        label,
        clause,
        EligibilityStatus.FAIL,
        observed=observed,
        required=required,
        detail=(
            f"{weakest_year.academic_year} filled {_format(weakest_pct, 'pct')} of approved "
            f"intake, which is the weakest of the last {_year_word(years)} academic years."
        ),
        suggestion=(
            f"Fill more than {_format(threshold, 'pct')} of approved intake in every academic "
            f"year; {weakest_year.academic_year} reached only {_format(weakest_pct, 'pct')}."
        ),
    )


def extended_eoa(
    evidence: EligibilityEvidence,
    reference_date: date,
    policy: EligibilityPolicy = DEFAULT_POLICY,
) -> RouteAdvice:
    """Apply the six Extended EoA criteria; any one of them is enough (APH 2.1a)."""
    criteria = (
        _flag(
            "EXTENDED_EOA_NIRF",
            "Figured in the 8th edition of NIRF",
            "APH 2.1a(i)",
            evidence.nirf_8th,
            pass_detail="The institution appears in the 8th NIRF rankings.",
            fail_detail="The institution does not appear in the 8th NIRF rankings.",
            suggestion="The 8th NIRF list is already published; plan for the next ranking cycle.",
            missing="No NIRF ranking is recorded for the institution.",
        ),
        _flag(
            "EXTENDED_EOA_QS",
            "Figured in the QS World Ranking Asia-2024",
            "APH 2.1a(ii)",
            evidence.qs_asia_2024,
            pass_detail="The institution appears in the QS Asia 2024 rankings.",
            fail_detail="The institution does not appear in the QS Asia 2024 rankings.",
            suggestion="The QS Asia 2024 list is already published; plan for the next QS cycle.",
            missing="No QS Asia 2024 ranking is recorded for the institution.",
        ),
        _nba_criterion(
            "EXTENDED_EOA_NBA",
            "At least 30% of eligible courses hold valid NBA accreditation",
            "APH 2.1a(iii)",
            evidence,
            threshold=policy.extended_eoa_cutoff_share_pct,
            reference_date=reference_date,
        ),
        _minimum(
            "EXTENDED_EOA_NAAC",
            "NAAC score of at least 3.01 on a scale of 4.0",
            "APH 2.1a(iv)",
            evidence.naac_score,
            policy.naac_min_score,
            unit="score",
            subject="NAAC score",
            missing="No NAAC score is recorded for the institution.",
        ),
        _flag(
            "EXTENDED_EOA_AUTONOMOUS",
            "Autonomous status conferred by UGC or AICTE",
            "APH 2.1a(v)",
            evidence.autonomous,
            pass_detail="The institution holds autonomous status.",
            fail_detail="The institution does not hold autonomous status.",
            suggestion=(
                "Apply for autonomous status with UGC or AICTE; the status alone qualifies."
            ),
            missing="Autonomous status is not recorded for the institution.",
        ),
        _fifth_year_admissions(
            evidence,
            policy,
            code="EXTENDED_EOA_80_PERCENT_ADMISSIONS",
            clause="APH 2.1a(vi)",
        ),
    )
    status = _any_of(criteria)
    met = [criterion.clause for criterion in criteria if criterion.status is EligibilityStatus.PASS]
    missing = sum(1 for criterion in criteria if criterion.status is EligibilityStatus.UNKNOWN)
    if status is EligibilityStatus.PASS:
        summary = f"Extended EoA is available under {', '.join(dict.fromkeys(met))}."
    elif status is EligibilityStatus.UNKNOWN:
        summary = (
            f"No APH 2.1a criterion is confirmed yet and {missing} still need evidence."
        )
    else:
        summary = "None of the six APH 2.1a criteria is met, so Extended EoA is not available."
    return RouteAdvice(
        code=RouteCode.EXTENDED_EOA,
        label="Three-year Extension of Approval",
        clause="APH 2.1a",
        status=status,
        summary=summary,
        criteria=criteria,
        application_type="EXTENDED_EOA",
        notes=(
            "Any one of the six criteria is enough for three years' approval (APH 2.1a).",
            "Extended EoA runs year round and still needs the annual TER charges "
            "(APH 2.1a, Table 2.1).",
        ),
    )


# ---------------------------------------------------------------------------
# Route 2: FN/OCI seats (APH 2.9)
# ---------------------------------------------------------------------------


def fn_oci(
    evidence: EligibilityEvidence,
    policy: EligibilityPolicy = DEFAULT_POLICY,
) -> RouteAdvice:
    """Apply the FN/OCI enrolment test: 80% average over three years (APH 2.9)."""
    years = policy.enrolment_average_years
    rows = _usable_admissions(evidence, years)
    required = (
        f"at least {_format(policy.admission_share_pct, 'pct')} average over the last "
        f"{_year_word(years)} academic years"
    )
    if len(rows) < years:
        criterion = _criterion(
            "FN_OCI_ENROLMENT",
            "At least 80% average enrolment over the last three years",
            "APH 2.9",
            EligibilityStatus.UNKNOWN,
            observed=None,
            required=required,
            detail=(
                "No admissions against approved intake are on record."
                if not rows
                else (
                    f"Only {len(rows)} of the last {_year_word(years)} academic years "
                    "have admissions on record."
                )
            ),
            suggestion=(
                f"Record admissions against approved intake for {_year_word(years)} "
                "complete years so this check can run."
            ),
        )
    else:
        average = round(sum(pct for _, pct in rows) / years, 2)
        passed = average >= policy.admission_share_pct
        observed = f"{_format(average, 'pct')} average"
        criterion = _criterion(
            "FN_OCI_ENROLMENT",
            "At least 80% average enrolment over the last three years",
            "APH 2.9",
            EligibilityStatus.PASS if passed else EligibilityStatus.FAIL,
            observed=observed,
            required=required,
            detail=(
                f"The {_year_word(years)}-year average of "
                f"{', '.join(row.academic_year for row, _ in rows)} is "
                f"{_format(average, 'pct')}."
            ),
            suggestion=(
                None
                if passed
                else (
                    f"Raise the {_year_word(years)}-year average enrolment from "
                    f"{_format(average, 'pct')} to "
                    f"{_target_label(policy.admission_share_pct, 'pct', False)}."
                )
            ),
        )
    criteria = (criterion,)
    status = criterion.status
    if status is EligibilityStatus.PASS:
        summary = "The three-year average enrolment meets the APH 2.9 test for FN/OCI seats."
    elif status is EligibilityStatus.UNKNOWN:
        summary = (
            "Three complete years of admissions are needed before FN/OCI seats can be checked."
        )
    else:
        summary = "The three-year average enrolment is below the 80% APH 2.9 threshold."
    return RouteAdvice(
        code=RouteCode.FN_OCI,
        label="Supernumerary seats for foreign nationals and OCI",
        clause="APH 2.9",
        status=status,
        summary=summary,
        criteria=criteria,
        application_type="SUPERNUMERARY_FN_OCI",
        notes=(
            "15% of the approved intake per course, over and above it, one third reserved "
            "for children of Indian workers in the Gulf countries (APH 2.9).",
            "The institution must also have nil deficiency based on self-disclosure (APH 2.9).",
        ),
    )


# ---------------------------------------------------------------------------
# Route 3: Off-campus (APH 2.11a)
# ---------------------------------------------------------------------------


def _tenure_criterion(
    evidence: EligibilityEvidence,
    reference_date: date,
    policy: EligibilityPolicy,
) -> Criterion:
    """Apply the ten-year existence test for off-campus (APH 2.11a)."""
    code = "OFF_CAMPUS_TENURE"
    label = "In existence for at least ten years"
    clause = "APH 2.11a"
    minimum = policy.off_campus_min_years
    required = _format(minimum, "years")
    years = _years_since(evidence.established_year, reference_date)
    if years is None:
        return _criterion(
            code,
            label,
            clause,
            EligibilityStatus.UNKNOWN,
            observed=None,
            required=required,
            detail="The year the institution was established is not recorded.",
            suggestion="Record the year the institution was established.",
        )
    observed = _format(years, "years")
    if years >= minimum:
        return _criterion(
            code,
            label,
            clause,
            EligibilityStatus.PASS,
            observed=observed,
            required=required,
            detail=(
                f"The institution was established in {evidence.established_year}, "
                f"{observed} before {reference_date.isoformat()}."
            ),
        )
    earliest = (evidence.established_year or 0) + minimum
    return _criterion(
        code,
        label,
        clause,
        EligibilityStatus.FAIL,
        observed=observed,
        required=required,
        detail=(
            f"The institution was established in {evidence.established_year}, so it is "
            f"{observed} old rather than {required}."
        ),
        suggestion=(
            f"An off-campus can be applied for from {earliest}, once the institution has "
            f"{required} of existence."
        ),
    )


def off_campus(
    evidence: EligibilityEvidence,
    reference_date: date,
    policy: EligibilityPolicy = DEFAULT_POLICY,
) -> RouteAdvice:
    """Apply the off-campus tests: ten years of existence plus one APH 2.11a criterion."""
    tenure = _tenure_criterion(evidence, reference_date, policy)
    criteria = (
        tenure,
        _flag(
            "OFF_CAMPUS_NIRF",
            "Figured in the 8th edition of NIRF",
            "APH 2.11a(i)",
            evidence.nirf_8th,
            pass_detail="The institution appears in the 8th NIRF rankings.",
            fail_detail="The institution does not appear in the 8th NIRF rankings.",
            suggestion="The 8th NIRF list is already published; plan for the next ranking cycle.",
            missing="No NIRF ranking is recorded for the institution.",
        ),
        _flag(
            "OFF_CAMPUS_QS",
            "Figured in the QS World Ranking Asia-2024",
            "APH 2.11a(ii)",
            evidence.qs_asia_2024,
            pass_detail="The institution appears in the QS Asia 2024 rankings.",
            fail_detail="The institution does not appear in the QS Asia 2024 rankings.",
            suggestion="The QS Asia 2024 list is already published; plan for the next QS cycle.",
            missing="No QS Asia 2024 ranking is recorded for the institution.",
        ),
        _nba_criterion(
            "OFF_CAMPUS_NBA",
            "At least 50% of eligible courses hold valid NBA accreditation",
            "APH 2.11a(iii)",
            evidence,
            threshold=policy.off_campus_cutoff_share_pct,
            reference_date=reference_date,
        ),
        _minimum(
            "OFF_CAMPUS_NAAC",
            "NAAC score of at least 3.01 on a scale of 4.0",
            "APH 2.11a(iv)",
            evidence.naac_score,
            policy.naac_min_score,
            unit="score",
            subject="NAAC score",
            missing="No NAAC score is recorded for the institution.",
        ),
        _flag(
            "OFF_CAMPUS_AUTONOMOUS",
            "Autonomous status conferred by UGC or AICTE",
            "APH 2.11a(v)",
            evidence.autonomous,
            pass_detail="The institution holds autonomous status.",
            fail_detail="The institution does not hold autonomous status.",
            suggestion=(
                "Apply for autonomous status with UGC or AICTE; the status alone qualifies."
            ),
            missing="Autonomous status is not recorded for the institution.",
        ),
        _fifth_year_admissions(
            evidence,
            policy,
            code="OFF_CAMPUS_80_PERCENT_ADMISSIONS",
            clause="APH 2.11a(vi)",
        ),
    )
    status = _conjunction((tenure.status, _any_of(criteria[1:])))
    if status is EligibilityStatus.PASS:
        summary = (
            "The institution can apply for one off-campus within its affiliating "
            "university's jurisdiction."
        )
    elif status is EligibilityStatus.UNKNOWN:
        summary = (
            "Off-campus eligibility cannot be confirmed until the missing evidence is recorded."
        )
    elif tenure.status is EligibilityStatus.FAIL:
        summary = (
            f"An off-campus needs at least {policy.off_campus_min_years} years of existence; "
            "this institution does not have them yet."
        )
    else:
        summary = (
            "None of the APH 2.11a criteria is met, so an off-campus cannot be introduced."
        )
    return RouteAdvice(
        code=RouteCode.OFF_CAMPUS,
        label="Introduction of an off-campus",
        clause="APH 2.11a",
        status=status,
        summary=summary,
        criteria=criteria,
        application_type="OFF_CAMPUS",
        notes=(
            "One off-campus only, within the jurisdiction of the affiliating university "
            "or the same city (APH 2.11a).",
            "Only affiliating institutions may apply (APH 2.11).",
        ),
    )


# ---------------------------------------------------------------------------
# Route 4: Working professionals (APH 2.6l)
# ---------------------------------------------------------------------------


def working_professional(
    evidence: EligibilityEvidence,
    policy: EligibilityPolicy = DEFAULT_POLICY,
) -> RouteAdvice:
    """Apply the three working-professional criteria; any one of them is enough (APH 2.6l)."""
    years = policy.enrolment_average_years
    rows = _usable_admissions(evidence, years)
    required = (
        f"more than {_format(policy.admission_share_pct, 'pct')} average over the last "
        f"{_year_word(years)} academic years"
    )
    if len(rows) < years:
        enrolment = _criterion(
            "WORKING_PROFESSIONAL_ENROLMENT",
            "More than 80% average enrolment over the last three years",
            "APH 2.6(l)(i)",
            EligibilityStatus.UNKNOWN,
            observed=None,
            required=required,
            detail=(
                "No admissions against approved intake are on record."
                if not rows
                else (
                    f"Only {len(rows)} of the last {_year_word(years)} academic years "
                    "have admissions on record."
                )
            ),
            suggestion=(
                f"Record admissions against approved intake for {_year_word(years)} "
                "complete years so this check can run."
            ),
        )
    else:
        average = round(sum(pct for _, pct in rows) / years, 2)
        passed = average > policy.admission_share_pct
        observed = f"{_format(average, 'pct')} average"
        enrolment = _criterion(
            "WORKING_PROFESSIONAL_ENROLMENT",
            "More than 80% average enrolment over the last three years",
            "APH 2.6(l)(i)",
            EligibilityStatus.PASS if passed else EligibilityStatus.FAIL,
            observed=observed,
            required=required,
            detail=(
                f"The {_year_word(years)}-year average of "
                f"{', '.join(row.academic_year for row, _ in rows)} is "
                f"{_format(average, 'pct')}."
            ),
            suggestion=(
                None
                if passed
                else (
                    f"Raise the {_year_word(years)}-year average enrolment from "
                    f"{_format(average, 'pct')} to "
                    f"{_target_label(policy.admission_share_pct, 'pct', True)}."
                )
            ),
        )
    criteria = (
        enrolment,
        _flag(
            "WORKING_PROFESSIONAL_ASPIRATIONAL",
            "Operating in an aspirational district",
            "APH 2.6(l)(ii)",
            evidence.aspirational_district,
            pass_detail="The institution is in an aspirational district listed by NITI Aayog.",
            fail_detail=(
                "The institution is not in an aspirational district listed by NITI Aayog."
            ),
            suggestion=None,
            missing="The aspirational-district status of the location is not recorded.",
        ),
        _flag(
            "WORKING_PROFESSIONAL_JK_NER",
            "Located in Jammu, Kashmir, Leh Ladakh or the North-East",
            "APH 2.6(l)(iii)",
            evidence.in_jk_ladakh_ne,
            pass_detail=(
                "The institution is in Jammu and Kashmir, Leh Ladakh or a North-East State."
            ),
            fail_detail=(
                "The institution is outside Jammu and Kashmir, Leh Ladakh and the North-East "
                "States covered by this criterion."
            ),
            suggestion=None,
            missing="The State or Union Territory group of the institution is not recorded.",
        ),
    )
    status = _any_of(criteria)
    if status is EligibilityStatus.PASS:
        summary = "An additional working-professional division is available (APH 2.6l)."
    elif status is EligibilityStatus.UNKNOWN:
        summary = (
            "Working-professional eligibility needs enrolment and location evidence before "
            "it can be confirmed."
        )
    else:
        summary = (
            "Working-professional divisions need high enrolment, an aspirational district or "
            "a J&K, Ladakh or North-East location."
        )
    return RouteAdvice(
        code=RouteCode.WORKING_PROFESSIONAL,
        label="Additional division for working professionals",
        clause="APH 2.6l",
        status=status,
        summary=summary,
        criteria=criteria,
        application_type="INCREASE_INTAKE",
        notes=(
            "One additional division of 15, 30 or 60 supernumerary seats in each course "
            "(APH 2.6l).",
            "AICTE's working-professional admission guidelines apply (APH 2.6l note 1).",
        ),
    )


# ---------------------------------------------------------------------------
# Route 5: TFW seats (APH 6.42)
# ---------------------------------------------------------------------------


def tfw(
    evidence: EligibilityEvidence,
    policy: EligibilityPolicy = DEFAULT_POLICY,
) -> RouteAdvice:
    """Apply the TFW fill test per course (APH 6.42d(i))."""
    required = f"at least {_format(policy.tfw_min_fill_pct, 'pct')} of approved intake filled"
    code = "TFW_COURSE_FILL"
    label = "At least 50% of approved intake filled in the course last year"
    clause = "APH 6.42(d)(i)"
    rates = [
        (course, pct)
        for course in evidence.courses
        if (pct := fill_pct(course.admitted, course.approved_intake)) is not None
    ]
    if not rates:
        criterion = _criterion(
            code,
            label,
            clause,
            EligibilityStatus.UNKNOWN,
            observed=None,
            required=required,
            detail="No course intake and admission figures are on record for last year.",
            suggestion="Record each course's approved intake and admissions for last year.",
        )
        status = EligibilityStatus.UNKNOWN
        summary = "Course intake and admission figures are needed to check TFW seats."
    else:
        eligible = sorted((item for item in rates if item[1] >= policy.tfw_min_fill_pct),
                          key=lambda item: item[1], reverse=True)
        best_course, best_pct = max(rates, key=lambda item: item[1])
        if eligible:
            names = ", ".join(course.course_name for course, _ in eligible)
            criterion = _criterion(
                code,
                label,
                clause,
                EligibilityStatus.PASS,
                observed=f"{_format(eligible[0][1], 'pct')} in {eligible[0][0].course_name}",
                required=required,
                detail=(
                    f"{len(eligible)} course(s) filled at least "
                    f"{_format(policy.tfw_min_fill_pct, 'pct')} of approved intake last year: "
                    f"{names}."
                ),
            )
            status = EligibilityStatus.PASS
            summary = (
                f"TFW seats are available in {len(eligible)} course(s) that filled at least "
                f"{_format(policy.tfw_min_fill_pct, 'pct')} of approved intake last year."
            )
        else:
            criterion = _criterion(
                code,
                label,
                clause,
                EligibilityStatus.FAIL,
                observed=f"{_format(best_pct, 'pct')} in {best_course.course_name}",
                required=required,
                detail=(
                    f"No course filled {_format(policy.tfw_min_fill_pct, 'pct')} of approved "
                    f"intake last year; the best was {best_course.course_name} at "
                    f"{_format(best_pct, 'pct')}."
                ),
                suggestion=(
                    f"Fill at least {_format(policy.tfw_min_fill_pct, 'pct')} of approved "
                    f"intake in one course; {best_course.course_name} reached "
                    f"{_format(best_pct, 'pct')} last year."
                ),
            )
            status = EligibilityStatus.FAIL
            summary = (
                f"No course filled at least {_format(policy.tfw_min_fill_pct, 'pct')} of "
                "approved intake last year, so TFW seats are not available."
            )
    return RouteAdvice(
        code=RouteCode.TFW,
        label="Tuition Fee Waiver seats",
        clause="APH 6.42",
        status=status,
        summary=summary,
        criteria=(criterion,),
        application_type=None,
        notes=(
            "TFW is mandatory for every approved institution, so it needs no separate "
            "application (APH 6.42b).",
            "Up to 5% of the approved intake per course, supernumerary, for students whose "
            "parents earn no more than Rs 8 lakh a year (APH 6.42a, 6.42d(i)).",
        ),
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def evaluate_all(
    evidence: EligibilityEvidence,
    reference_date: date,
    policy: EligibilityPolicy = DEFAULT_POLICY,
) -> AdvisorResult:
    """Run all five advisors and return them in the order the screen shows them."""
    return AdvisorResult(
        as_of=reference_date,
        routes=(
            extended_eoa(evidence, reference_date, policy),
            fn_oci(evidence, policy),
            off_campus(evidence, reference_date, policy),
            working_professional(evidence, policy),
            tfw(evidence, policy),
        ),
    )
