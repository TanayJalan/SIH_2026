"""APH calculators, rule-library invariants and Nil Deficiency behaviour.

The calculators are pure functions built from the worked examples in
``docs/reference/APH_SPEC.md``. The rule library is data in
``backend/seeds/aph/compliance_rules.json``; these tests fail the build when a
row loses its clause, invents an operator or claims a verified AICTE norm while
still being an illustrative project threshold.
"""

from __future__ import annotations

import json
import string
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.models.compliance import ComplianceRule
from app.models.enums import ComplianceHealth, PenalActionType, Severity
from app.schemas.compliance import ComplianceRulePreview
from app.services import compliance_calculators as calc
from app.services import penal_actions
from app.services.compliance import (
    _evaluate_rule,
    _nil_deficiency,
    _rag_status,
    _resolve_observed,
)

SEED_DIR = Path(__file__).resolve().parents[1] / "seeds" / "aph"
KNOWN_OPERATORS = {
    "<",
    "<=",
    ">=",
    ">",
    "=",
    "==",
    "!=",
    "BETWEEN",
    "EXISTS",
    "RATIO",
    "SUM",
    "COUNT",
    "DATE_NOT_EXPIRED",
}


def _seed_rules() -> list[dict[str, object]]:
    return json.loads((SEED_DIR / "compliance_rules.json").read_text())


def _seed_config() -> dict[str, object]:
    return json.loads((SEED_DIR / "compliance_config.json").read_text())


def _engineering_ug() -> calc.ProgrammeInput:
    return calc.ProgrammeInput(
        family="ENGINEERING_TECHNOLOGY",
        level="UG",
        intake=60,
        duration_years=4,
        divisions=1,
        course_name="B.Tech Computer Science and Engineering",
    )


def _management_pg() -> calc.ProgrammeInput:
    return calc.ProgrammeInput(
        family="MANAGEMENT",
        level="PG",
        intake=120,
        duration_years=2,
        divisions=2,
        course_name="Master of Business Administration",
    )


def _rule(
    *,
    metric_key: str,
    operator: str,
    threshold: str,
    threshold_max: str | None = None,
    severity: Severity = Severity.HIGH,
    mandatory: bool = True,
    illustrative: bool = False,
    metric_params: dict[str, object] | None = None,
) -> ComplianceRule:
    return ComplianceRule(
        code="TEST-RULE",
        name="Test rule",
        category="Test",
        description="Test-only rule.",
        metric_key=metric_key,
        operator=operator,
        threshold=Decimal(threshold),
        threshold_max=Decimal(threshold_max) if threshold_max else None,
        severity=severity,
        applies_to="ALL",
        apH_clause="APH 6.14",
        needs_verification=False,
        mandatory=mandatory,
        illustrative=illustrative,
        metric_params=dict(metric_params or {}),
        is_active=True,
    )


def _preview(
    *,
    status: str,
    mandatory: bool = True,
    illustrative: bool = False,
    severity: Severity = Severity.HIGH,
) -> ComplianceRulePreview:
    return ComplianceRulePreview(
        code="TEST-RULE",
        name="Test rule",
        category="Test",
        description="Test-only rule.",
        severity=severity,
        metric_key="faculty.total",
        operator=">=",
        threshold=1.0,
        unit="faculty",
        observed_value=1.0,
        status=status,  # type: ignore[arg-type]
        message="test",
        mandatory=mandatory,
        illustrative=illustrative,
    )


# ---------------------------------------------------------------------------
# Faculty (APH 6.14, Annexure-5)
# ---------------------------------------------------------------------------


def test_ug_engineering_240_students_needs_12_faculty_on_1_2_6() -> None:
    """S = 60 intake x 4 years = 240; 240 / 20 = 12 faculty, split 1:2:9."""
    requirement = calc.faculty_requirement([_engineering_ug()])

    assert requirement.total_required == 12
    assert requirement.required_by_group == {"ENGINEERING_TECHNOLOGY|UG": 12}
    assert (requirement.professors, requirement.associate_professors) == (1, 2)
    assert requirement.assistant_professors == 9
    assert requirement.principal_director == 1
    assert requirement.heads_of_department == 0
    assert requirement.reduced is False


def test_management_pg_240_students_needs_12_faculty_on_1_2_6() -> None:
    """MBA: 120 intake x 2 years = 240; 240 / 20 = 12 faculty."""
    requirement = calc.faculty_requirement([_management_pg()])

    assert requirement.total_required == 12
    assert requirement.professors == 1
    assert requirement.associate_professors == 2
    assert requirement.assistant_professors == 9
    assert requirement.principal_director == 1


def test_diploma_uses_intake_over_25_with_principal_and_hods() -> None:
    """Diploma: S/25 plus one Principal and one HoD per department."""
    programme = calc.ProgrammeInput(
        family="ENGINEERING_TECHNOLOGY",
        level="DIPLOMA",
        intake=100,
        duration_years=3,
        divisions=2,
        course_name="Diploma in Mechanical Engineering",
    )
    requirement = calc.faculty_requirement([programme])

    # 300 / 25 = 12 posts: 1 Principal, 2 HoDs and 9 Assistant Professors.
    assert requirement.total_required == 12
    assert requirement.principal_director == 0  # counted inside the S/25 batch
    assert requirement.heads_of_department == 2
    assert requirement.groups["ENGINEERING_TECHNOLOGY|DIPLOMA"]["principal"] == 1
    assert requirement.assistant_professors == 9


def test_reduced_enrolment_cuts_the_establishment_by_25_percent() -> None:
    """A three-year average admission at or below 50% reduces the requirement."""
    reduced = calc.faculty_requirement(
        [_engineering_ug()], average_admission_pct=40.0
    )
    normal = calc.faculty_requirement(
        [_engineering_ug()], average_admission_pct=72.5
    )

    assert normal.total_required == 12
    assert reduced.total_required == 9
    assert reduced.reduced is True


def test_cadre_split_rounds_senior_tiers_down_to_fill_assistant_posts() -> None:
    assert calc.cadre_split(12, (1, 2, 6)) == (1, 2, 9)
    assert calc.cadre_split(8, (1, 2, 6)) == (1, 1, 6)
    assert calc.cadre_split(2, (1, 2, 6)) == (1, 0, 1)
    assert calc.cadre_split(0, (1, 2, 6)) == (0, 0, 0)


def test_cadre_compliance_allows_upward_substitution_only() -> None:
    # 1:2:9 matches the 1:2:6 requirement for 12 posts.
    assert calc.cadre_compliance(1, 2, 9, 12) is True
    # A senior surplus may cover an Associate Professor gap.
    assert calc.cadre_compliance(2, 1, 9, 12) is True
    # Junior-only establishment fails even when the total is met.
    assert calc.cadre_compliance(1, 0, 11, 12) is False
    assert calc.cadre_compliance(0, 0, 0, 12) is False


def test_adjunct_cap_varies_by_family() -> None:
    # The cap is rounded up so the mandatory 10% Professor-of-Practice share is
    # achievable at a 12-post establishment (15% of 12 is 1.8 posts).
    assert calc.adjunct_cap(12, "ENGINEERING_TECHNOLOGY", "UG")["cap"] == 2
    assert calc.adjunct_cap(12, "PLANNING", "UG")["cap"] == 4
    assert calc.adjunct_cap(12, "DESIGN", "UG")["cap"] == 3
    assert calc.adjunct_cap(12, "ENGINEERING_TECHNOLOGY", "UG")[
        "min_professors_of_practice"
    ] == 2


def test_adjunct_cap_never_falls_below_the_professor_of_practice_minimum() -> None:
    for required in range(1, 250):
        info = calc.adjunct_cap(required, "ENGINEERING_TECHNOLOGY", "UG")
        assert info["cap"] >= info["min_professors_of_practice"], required


def test_adjunct_allowance_sums_the_programme_groups() -> None:
    requirement = calc.faculty_requirement([_engineering_ug(), _management_pg()])
    allowance = calc.adjunct_allowance(requirement)
    assert allowance["cap"] >= allowance["min_professors_of_practice"]
    assert allowance["cap"] == 2 + 2


# ---------------------------------------------------------------------------
# Land and building (APH 6.17, Annexure-3)
# ---------------------------------------------------------------------------


def test_owned_land_needs_no_lease_term() -> None:
    result = calc.lease_compliance(
        land_ownership="OWNED",
        lease_years_total=None,
        lease_years_live=None,
        longest_course_years=4,
    )
    assert result == {"title_ok": True, "lease_ok": True, "tenure_ok": True}


def test_leased_land_needs_30_years_total_and_a_live_lease() -> None:
    ok = calc.lease_compliance(
        land_ownership="LEASED",
        lease_years_total=30,
        lease_years_live=12,
        longest_course_years=4,
    )
    assert ok["lease_ok"] is True
    assert ok["tenure_ok"] is True

    short_total = calc.lease_compliance(
        land_ownership="LEASED",
        lease_years_total=20,
        lease_years_live=12,
        longest_course_years=4,
    )
    assert short_total["lease_ok"] is False

    short_live = calc.lease_compliance(
        land_ownership="LEASED",
        lease_years_total=30,
        lease_years_live=3,
        longest_course_years=4,
    )
    assert short_live["lease_ok"] is False


def test_lease_checks_report_each_constraint_separately() -> None:
    owned = calc.lease_checks(
        land_ownership="OWNED",
        lease_years_total=None,
        lease_years_live=None,
        longest_course_years=4,
    )
    assert owned["total_ok"] is True
    assert owned["live_ok"] is True

    short_total = calc.lease_checks(
        land_ownership="LEASED",
        lease_years_total=20,
        lease_years_live=12,
        longest_course_years=4,
    )
    assert short_total["total_ok"] is False
    assert short_total["live_ok"] is True

    short_live = calc.lease_checks(
        land_ownership="LEASED",
        lease_years_total=30,
        lease_years_live=3,
        longest_course_years=4,
    )
    assert short_live["total_ok"] is True
    assert short_live["live_ok"] is False


def test_land_parcels_are_capped_and_must_be_close() -> None:
    ok = calc.plot_compliance(
        [
            {"area_sqm": 9000, "distance_km": 0},
            {"area_sqm": 4000, "distance_km": 1.5},
        ]
    )
    assert ok["plots_ok"] is True
    assert ok["distance_ok"] is True
    assert ok["plot_count"] == 2

    too_many = calc.plot_compliance(
        [{"area_sqm": 1000, "distance_km": 0}] * 4
    )
    assert too_many["plots_ok"] is False

    too_far = calc.plot_compliance([{"area_sqm": 1000, "distance_km": 5}])
    assert too_far["distance_ok"] is False


def test_instructional_and_built_up_area_follow_annexure_3() -> None:
    instructional = calc.instructional_area([_engineering_ug()])
    # 2 classrooms at 66 sqm and 1 tutorial room at 33 sqm for a 60-seat division.
    assert instructional["classrooms"] == 132.0
    assert instructional["tutorial_rooms"] == 33.0
    assert instructional["workshops"] == 200.0
    assert instructional["total"] > 0

    built = calc.required_built_up_area(instructional["total"])
    assert built["administrative"] == 750.0
    assert built["amenities"] == 500.0
    assert built["total"] == pytest.approx(
        (instructional["total"] + 750.0 + 500.0) * 1.25, abs=0.01
    )
    # Circulation is the 25% component on top of the base area.
    assert built["circulation"] == pytest.approx(built["total"] - built["base"], abs=0.01)


def test_built_up_area_uses_configurable_norms() -> None:
    built = calc.required_built_up_area(
        1000.0,
        administrative_sqm=600.0,
        amenities_sqm=400.0,
        circulation_factor=1.3,
    )
    assert built["base"] == 2000.0
    assert built["total"] == 2600.0


# ---------------------------------------------------------------------------
# Library, computing and internet (APH Annexure-4)
# ---------------------------------------------------------------------------


def test_library_requirement_for_pg_management() -> None:
    library = calc.library_requirement([_management_pg()])
    # 100 first-year titles + 50 for the second year.
    assert library["titles"] == 150.0
    assert library["volumes"] == 1200.0
    assert library["journals"] == 6.0
    assert library["reading_seats"] == 60.0


def test_library_requirement_for_ug_engineering() -> None:
    library = calc.library_requirement([_engineering_ug()])
    # 100 first-year titles + 50 for each later year.
    assert library["titles"] == 250.0
    assert library["volumes"] == 1250.0


def test_computing_requirement_uses_family_ratio_and_a_floor() -> None:
    management = calc.pc_requirement([_management_pg()])
    assert management["pcs"] == 40

    engineering = calc.pc_requirement([_engineering_ug()])
    # 240 students / 10 = 24, above the configured minimum of 20.
    assert engineering["pcs"] == 24
    assert engineering["printers"] == 2


def test_bandwidth_tiers() -> None:
    assert calc.bandwidth_requirement(300) == 100
    assert calc.bandwidth_requirement(301) == 300
    assert calc.bandwidth_requirement(600) == 300
    assert calc.bandwidth_requirement(601) == 500
    assert calc.bandwidth_requirement(900) == 500
    assert calc.bandwidth_requirement(901) == 1000


# ---------------------------------------------------------------------------
# Documents, admission and enrolment
# ---------------------------------------------------------------------------


def test_structural_certificate_required_only_after_30_years() -> None:
    today = date(2026, 10, 27)
    assert calc.structural_certificate_required(1996, today) is True
    assert calc.structural_certificate_required(1997, today) is False
    assert calc.structural_certificate_required(None, today) is False


def test_certificate_validity_compares_with_the_reference_date() -> None:
    today = date(2026, 10, 27)
    assert calc.certificate_valid(date(2027, 3, 31), today) is True
    assert calc.certificate_valid(date(2025, 12, 31), today) is False
    assert calc.certificate_valid(None, today) is False


def test_reduced_enrolment_and_excess_admission_ledger_rules() -> None:
    low = [
        {"academic_year": year, "approved_intake": 100, "admitted_total": 20}
        for year in ("2021-22", "2022-23", "2023-24", "2024-25", "2025-26")
    ]
    assert calc.reduced_enrolment_trigger(low)["trigger"] is True

    healthy = [
        {"academic_year": year, "approved_intake": 100, "admitted_total": 80}
        for year in ("2021-22", "2022-23", "2023-24", "2024-25", "2025-26")
    ]
    assert calc.reduced_enrolment_trigger(healthy)["trigger"] is False

    excess = calc.excess_admission(
        [
            {"approved_intake": 60, "admitted_total": 60},
            {"approved_intake": 60, "admitted_total": 72},
        ]
    )
    assert excess == {"max_excess": 12, "exceeds": True}

    assert calc.excess_admission(
        [{"approved_intake": 60, "admitted_total": 55}]
    ) == {"max_excess": 0, "exceeds": False}


# ---------------------------------------------------------------------------
# Rule library data invariants
# ---------------------------------------------------------------------------


def test_rule_library_codes_are_unique() -> None:
    codes = [str(row["code"]) for row in _seed_rules()]
    assert len(codes) == len(set(codes))


def test_every_rule_cites_a_clause_or_is_flagged_for_verification() -> None:
    missing = [
        str(row["code"])
        for row in _seed_rules()
        if not str(row.get("apH_clause") or "").strip()
        and not row.get("needs_verification")
    ]
    assert not missing, f"rules without an APH clause or verification flag: {missing}"


def test_illustrative_rules_are_advisory_and_flagged() -> None:
    for row in _seed_rules():
        if row.get("illustrative"):
            assert row.get("mandatory") is False, row["code"]
            assert row.get("needs_verification") is True, row["code"]
            assert str(row["apH_clause"]).startswith("DEMO"), row["code"]


def test_real_rules_are_mandatory_and_do_not_claim_demo_clauses() -> None:
    """Every non-illustrative rule must block Nil Deficiency when it fails.

    An advisory flag on a real rule would silently weaken the Nil Deficiency
    result, so it fails the build.
    """
    for row in _seed_rules():
        if row.get("illustrative"):
            continue
        code = str(row["code"])
        assert str(row["apH_clause"]).startswith("APH "), code
        assert row.get("mandatory", True) is True, code


def test_every_real_rule_explains_itself_with_a_clause_quoting_template() -> None:
    """A rule a reviewer cannot explain is not shippable.

    Every real rule must carry an explanation template that quotes its APH
    clause, and the template may only use the placeholders the engine fills in.
    A stray placeholder would leave raw braces in the Deficiency Report.
    """
    allowed = {"observed", "threshold", "unit", "clause", "name", "code", "result"}
    missing: list[str] = []
    unknown: list[tuple[str, set[str]]] = []
    for row in _seed_rules():
        if row.get("illustrative"):
            continue
        code = str(row["code"])
        template = str(row.get("explanation_template") or "")
        if "{clause}" not in template:
            missing.append(code)
            continue
        fields = {
            field.split(".")[0].split("[")[0]
            for _, field, _, _ in string.Formatter().parse(template)
            if field
        }
        if fields - allowed:
            unknown.append((code, fields - allowed))
        rendered = template.format(
            observed="12",
            threshold="10",
            unit="count",
            clause=row["apH_clause"],
            name=row["name"],
            code=code,
            result="not compliant",
        )
        assert str(row["apH_clause"]) in rendered, code
    assert not missing, f"real rules without a clause-quoting template: {missing}"
    assert not unknown, f"templates using unsupported placeholders: {unknown}"


def test_rule_operators_and_aggregate_operands_are_known() -> None:
    for row in _seed_rules():
        operator = str(row["operator"])
        assert operator in KNOWN_OPERATORS, row["code"]
        params = row.get("metric_params") or {}
        assert isinstance(params, dict), row["code"]
        if operator == "RATIO":
            assert params.get("numerator") and params.get("denominator"), row["code"]
        if operator in {"SUM", "COUNT"}:
            metrics = params.get("metrics") or [row["metric_key"]]
            assert isinstance(metrics, list) and metrics, row["code"]


def test_rules_cite_a_norm_clause_not_the_penal_action_chapter() -> None:
    """Chapter VII is penal action, not a norm.

    ``7.1`` introduces penal actions, ``7.2`` covers unapproved programmes and
    ``7.3`` lists the actions themselves. A compliance rule must cite the norm
    it enforces (for example APH 6.14 for faculty, APH Annexure-4 for library
    and computing), never the chapter that punishes a breach. ``7.4a``-``7.4n``
    are allowed because some rules enforce those violations directly.
    """
    penal_chapter = ("APH 7.1", "APH 7.2", "APH 7.3")
    offenders = [
        (str(row["code"]), str(row["apH_clause"]))
        for row in _seed_rules()
        if str(row["apH_clause"]).startswith(penal_chapter)
    ]
    assert not offenders, f"rules citing the penal-action chapter: {offenders}"


def test_rule_penalty_codes_map_to_aph_7_3_actions() -> None:
    known = {entry["code"] for entry in penal_actions.catalogue()}
    for row in _seed_rules():
        for code in row.get("penalty_codes") or []:
            assert f"APH {code}" in known, (row["code"], code)


def test_norm_config_matches_the_calculators() -> None:
    config = _seed_config()

    for family, levels in config["fsr_ratios"].items():
        for level, ratio in levels.items():
            assert ratio > 0, (family, level)

    for key, weights in config["cadre_ratios"].items():
        assert len(weights) == 3, key
        assert sum(weights) > 0, key

    tiers = config["bandwidth_tiers"]
    assert tiers[-1]["max_intake"] is None
    intakes = [tier["max_intake"] for tier in tiers[:-1]]
    assert intakes == sorted(intakes)
    mbps = [tier["mbps"] for tier in tiers]
    assert mbps == sorted(mbps)

    assert config["area_norms"]["administrative_sqm"] == 750
    assert config["area_norms"]["amenities_sqm"] == 500
    assert config["area_norms"]["circulation_factor"] == 1.25


# ---------------------------------------------------------------------------
# Penal actions (APH 7.4 -> 7.3)
# ---------------------------------------------------------------------------


def test_penal_suggestions_are_advisory_and_require_a_hearing() -> None:
    suggestions = penal_actions.suggestions_for_codes(["7.4c"])
    assert suggestions
    for suggestion in suggestions:
        assert suggestion.suggests_only is True
        assert suggestion.hearing_required is True
        assert suggestion.apH_clause.startswith("APH 7.3")
        assert suggestion.action in set(PenalActionType)
    assert PenalActionType.INTAKE_REDUCTION in {item.action for item in suggestions}


def test_unknown_penalty_codes_are_ignored() -> None:
    assert penal_actions.suggestions_for_codes(["7.4z", "not-a-code"]) == []
    assert penal_actions.suggestions_for_codes([]) == []


def test_penalty_catalogue_and_process_steps_are_complete() -> None:
    catalogue = penal_actions.catalogue()
    assert len(catalogue) >= 10
    for entry in catalogue:
        assert entry["actions"], entry["code"]
        assert entry["hearing_required"] is True
    assert len(penal_actions.process_steps()) >= 2


# ---------------------------------------------------------------------------
# Nil Deficiency, scoring and the safe evaluator
# ---------------------------------------------------------------------------


def test_nil_deficiency_requires_every_mandatory_rule_to_pass() -> None:
    assert _nil_deficiency([_preview(status="PASS"), _preview(status="PASS")]) is True

    # An illustrative failure is advisory and cannot block Nil Deficiency.
    assert (
        _nil_deficiency(
            [
                _preview(status="PASS"),
                _preview(status="FAIL", mandatory=False, illustrative=True),
            ]
        )
        is True
    )

    # A mandatory failure blocks it.
    assert _nil_deficiency([_preview(status="PASS"), _preview(status="FAIL")]) is False

    # Unassessed mandatory evidence blocks it as well.
    assert (
        _nil_deficiency([_preview(status="PASS"), _preview(status="NOT_ASSESSED")])
        is False
    )


def test_mandatory_rules_dominate_the_rag_status() -> None:
    breakpoints = {"red_below": 70.0, "amber_below": 85.0}

    assert (
        _rag_status(
            failed_critical_count=0,
            score=100.0,
            breakpoints=breakpoints,
            mandatory_failed_count=1,
        )
        == ComplianceHealth.RED
    )
    assert (
        _rag_status(
            failed_critical_count=0,
            score=100.0,
            breakpoints=breakpoints,
            mandatory_missing_count=1,
        )
        == ComplianceHealth.AMBER
    )
    assert (
        _rag_status(failed_critical_count=0, score=100.0, breakpoints=breakpoints)
        == ComplianceHealth.GREEN
    )


def test_aggregate_operators_resolve_operands_without_eval() -> None:
    today = date(2026, 10, 27)
    metrics = {
        "faculty.total": 12.0,
        "faculty.required_total": 12.0,
        "library.titles": 250.0,
        "library.volumes": 1250.0,
        "document.affidavit2.present": 1.0,
        "document.fire_safety.valid": 0.0,
        "document.fire_valid_until": date(2025, 12, 31),
    }

    ratio_rule = _rule(
        metric_key="faculty.total",
        operator="RATIO",
        threshold="1",
        metric_params={
            "numerator": "faculty.total",
            "denominator": "faculty.required_total",
            "compare": ">=",
        },
    )
    value, evidence = _resolve_observed(ratio_rule, metrics, reference_date=today)
    assert value == 1.0
    assert evidence["numerator"] == 12.0
    assert _evaluate_rule(ratio_rule, value).status == "PASS"

    sum_rule = _rule(
        metric_key="library.volumes",
        operator="SUM",
        threshold="1000",
        metric_params={"metrics": ["library.titles", "library.volumes"]},
    )
    value, _ = _resolve_observed(sum_rule, metrics, reference_date=today)
    assert value == 1500.0
    assert _evaluate_rule(sum_rule, value).status == "PASS"

    count_rule = _rule(
        metric_key="document.affidavit2.present",
        operator="COUNT",
        threshold="1",
        metric_params={
            "metrics": ["document.affidavit2.present", "document.fire_safety.valid"],
            "equals": 1.0,
        },
    )
    value, _ = _resolve_observed(count_rule, metrics, reference_date=today)
    assert value == 1.0
    assert _evaluate_rule(count_rule, value).status == "PASS"

    expiry_rule = _rule(
        metric_key="document.fire_valid_until",
        operator="DATE_NOT_EXPIRED",
        threshold="0",
    )
    value, _ = _resolve_observed(expiry_rule, metrics, reference_date=today)
    assert value == date(2025, 12, 31)
    assert _evaluate_rule(expiry_rule, value, reference_date=today).status == "FAIL"
    assert (
        _evaluate_rule(expiry_rule, value, reference_date=date(2025, 1, 1)).status
        == "PASS"
    )


def test_exists_rules_report_a_value_and_a_plain_language_result() -> None:
    rule = _rule(metric_key="document.fire_safety.valid", operator="EXISTS", threshold="0")
    rule.explanation_template = (
        "Occupancy/Completion Certificate: {result}. {clause} requires a valid certificate."
    )

    passing = _evaluate_rule(rule, True)
    assert passing.status == "PASS"
    # Presence is surfaced as 1/0 so the evidence panel is never blank.
    assert passing.observed_value == 1.0
    assert passing.message == (
        "Occupancy/Completion Certificate: compliant. "
        "APH 6.14 requires a valid certificate."
    )

    failing = _evaluate_rule(rule, False)
    assert failing.status == "FAIL"
    assert failing.observed_value == 0.0
    assert failing.message.startswith("Occupancy/Completion Certificate: not compliant.")

    # No evidence at all stays unassessed and keeps the data-missing message.
    unassessed = _evaluate_rule(rule, None)
    assert unassessed.status == "NOT_ASSESSED"
    assert unassessed.observed_value is None
    assert unassessed.message.startswith("Data missing: ")


def test_missing_document_count_matches_codes_and_document_types() -> None:
    """A checklist row without a code must still match an upload by doc_type."""
    from app.models.document import Document
    from app.models.enums import DocumentVerificationStatus
    from app.models.required_document import RequiredDocument
    from app.services.compliance import _document_metrics

    required = [
        RequiredDocument(
            application_type="EOA_SELF_DISCLOSURE",
            doc_type=doc_type,
            doc_code=doc_code,
            mandatory=True,
            condition_expr=None,
            apH_clause="APH Annexure-2.1",
        )
        for doc_type, doc_code in (
            ("AFFIDAVIT_2", "AFFIDAVIT_2"),
            ("LEGACY_LETTER", None),
            ("FIRE_SAFETY_CERTIFICATE", "FIRE_SAFETY_CERTIFICATE"),
        )
    ]
    documents = [
        Document(
            doc_code=doc_code,
            doc_type=doc_type,
            verification_status=DocumentVerificationStatus.PENDING,
            signed_with_dsc=True,
        )
        for doc_code, doc_type in (
            ("AFFIDAVIT_2", "AFFIDAVIT_2"),
            (None, "LEGACY_LETTER"),
        )
    ]
    metrics = _document_metrics(documents, required, date(2026, 10, 27))
    assert metrics["document.annexure21.missing_count"] == 1.0
    assert metrics["document.annexure21.missing_codes"] == "FIRE_SAFETY_CERTIFICATE"


def test_deficiency_report_accepts_penal_suggestions_from_the_engine(monkeypatch) -> None:
    """The report must serialise the suggestion models the engine already built."""
    from types import SimpleNamespace

    from app.schemas.compliance import (
        CompliancePreviewRead,
        PenalActionSuggestionRead,
    )
    from app.services import deficiency_report as report_service

    preview_rule = _preview(status="FAIL")
    preview_rule.unit = "count"
    preview_rule.penal_action_suggestions = [
        PenalActionSuggestionRead(
            violation_code="APH 7.4c",
            violation="Faculty deficiency",
            action=PenalActionType.PROGRAMME_WITHDRAWAL,
            action_label="Withdrawal of programme approval",
            apH_clause="APH 7.3, 7.4c",
        )
    ]
    preview = CompliancePreviewRead(
        application_id=uuid.uuid4(),
        evaluated_at=datetime(2026, 10, 27, tzinfo=UTC),
        rules=[preview_rule],
        passed_count=0,
        failed_count=1,
        not_assessed_count=0,
        assessed_count=1,
        score=0.0,
        outcome="ATTENTION",
        status="RED",
        mandatory_failed_count=1,
        nil_deficiency=False,
        banner="Not Nil Deficiency",
    )
    monkeypatch.setattr(report_service, "evaluate_compliance", lambda *a, **k: preview)
    report = report_service.build_deficiency_report(
        None,  # type: ignore[arg-type] - the engine is stubbed
        SimpleNamespace(
            id=uuid.uuid4(),
            data={},
            portal_application_no="TEST/DEFICIENCY/0001",
            academic_year="2026-27",
        ),
        evaluated_at=datetime(2026, 10, 27, tzinfo=UTC),
    )
    assert report.items[0].penal_action_suggestions[0].action == (
        PenalActionType.PROGRAMME_WITHDRAWAL
    )
    assert report.items[0].penal_action_suggestions[0].hearing_required is True

    pdf = report_service.render_deficiency_report_pdf(report)
    assert pdf.getvalue().startswith(b"%PDF")


def test_missing_data_is_not_assessed_never_a_crash() -> None:
    rule = _rule(metric_key="faculty.required_total", operator=">=", threshold="1")

    assert _resolve_observed(rule, {}, reference_date=date(2026, 10, 27))[0] is None
    preview = _evaluate_rule(rule, None)
    assert preview.status == "NOT_ASSESSED"
    assert preview.message.startswith("Data missing: ")

    # A ratio with a zero denominator is missing data, not a division error.
    ratio_rule = _rule(
        metric_key="faculty.total",
        operator="RATIO",
        threshold="1",
        metric_params={"numerator": "faculty.total", "denominator": "faculty.zero"},
    )
    value, _ = _resolve_observed(
        ratio_rule,
        {"faculty.total": 12.0, "faculty.zero": 0.0},
        reference_date=date(2026, 10, 27),
    )
    assert value is None
    assert _evaluate_rule(ratio_rule, value).status == "NOT_ASSESSED"


def test_scoped_metrics_do_not_fall_back_to_the_institution_value() -> None:
    from app.services.compliance import _metric_for_scope

    metrics = {
        "faculty.fsr": 30.0,
        "_scope": {"ENGINEERING_TECHNOLOGY|UG": {"fsr": 30.0, "required": 12.0}},
    }
    params = {"family": "ENGINEERING_TECHNOLOGY", "level": "UG"}
    assert _metric_for_scope(metrics, "faculty.fsr_for", params) == 30.0

    # A scope the institution does not run is unassessed, not the global value.
    missing_scope = {"family": "MANAGEMENT", "level": "PG"}
    assert _metric_for_scope(metrics, "faculty.fsr_for", missing_scope) is None
