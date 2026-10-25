"""Unit tests for the compliance engine: operators, metrics and scoring."""

import uuid
from datetime import date
from decimal import Decimal

from app.models.application import Application, ApplicationProgram
from app.models.compliance import ComplianceRule
from app.models.document import Document
from app.models.enums import (
    ApplicationStatus,
    ApplicationType,
    ComplianceHealth,
    DocumentVerificationStatus,
    Severity,
    WorkflowStage,
)
from app.schemas.application_sections import ApplicationData
from app.services.compliance import (
    _applies_to_application,
    _document_validity,
    _evaluate_rule,
    _rag_status,
    _weighted_score,
    application_metric_values,
    available_metric_catalogue,
)
from tests.support import COMPLETE_APPLICATION_DATA


def _data(**overrides: object) -> ApplicationData:
    payload = {**COMPLETE_APPLICATION_DATA, **overrides}
    return ApplicationData.model_validate(payload)


def _rule(
    *,
    metric_key: str,
    operator: str,
    threshold: str,
    threshold_max: str | None = None,
    severity: Severity = Severity.MEDIUM,
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
        apH_clause="DEMO",
        needs_verification=True,
        is_active=True,
    )


# ``ApplicationProgram``/``Document`` constructors are exercised unsaved; the
# extractor only reads their scalar attributes.


def test_metric_extractor_raw_and_derived_values() -> None:
    metrics = application_metric_values(_data())
    assert metrics["infrastructure.land_area"] == 12000
    assert metrics["faculty.student_faculty_ratio"] == 18.5
    # 15+35+70 permanent-rank faculty of 120 total.
    assert metrics["derived.qualified_faculty_pct"] == 100.0
    assert metrics["finance.total_annual_fee"] == 185000.0
    assert metrics["derived.naac_grade_present"] == 1.0
    # accreditation.nba_status is ACCREDITED -> the NBA proxy is 100%.
    assert metrics["derived.nba_accredited_programs_pct"] == 100.0
    assert metrics["derived.mandatory_disclosure_published"] == 1.0


def test_metric_extractor_nba_proxy_uses_accreditation_status() -> None:
    metrics = application_metric_values(_data())
    assert metrics["derived.nba_accredited_programs_pct"] == 100.0


def test_metric_extractor_uses_program_proxies_for_per_student_values() -> None:
    programs = [
        ApplicationProgram(
            application_id=None,
            program_name="CSE",
            level="UG",
            intake=300,
            faculty_count=25,
            lab_count=2,
        ),
        ApplicationProgram(
            application_id=None,
            program_name="MECH",
            level="UG",
            intake=100,
            faculty_count=10,
            lab_count=4,
        ),
    ]
    metrics = application_metric_values(
        _data(),
        programs=programs,
    )
    assert metrics["derived.total_intake"] == 400.0
    # 8500 sq. m over 400 intake seats.
    assert metrics["derived.built_up_area_per_student"] == 21.25
    assert metrics["derived.library_books_per_student"] == 60.0
    assert metrics["derived.lab_count_per_program"] == 3.0


def test_metric_missing_programs_leaves_derived_metrics_missing() -> None:
    metrics = application_metric_values(_data())
    assert metrics["derived.total_intake"] is None
    assert metrics["derived.built_up_area_per_student"] is None
    assert metrics["derived.lab_count_per_program"] is None


def test_document_validity_flags_rejected_and_expired_documents() -> None:
    assert _document_validity([], None) is None  # no documents yet

    ok = Document(
        application_id=None,
        doc_type="AICTE_LAND_DOC",
        filename="land.pdf",
        content_type="application/pdf",
        size_bytes=10,
        storage_path="x",
        uploaded_by=None,
        verification_status=DocumentVerificationStatus.PENDING,
        version=1,
    )
    assert _document_validity([ok], None) == 1.0

    flagged = Document(
        application_id=None,
        doc_type="AICTE_LAND_DOC",
        filename="land.pdf",
        content_type="application/pdf",
        size_bytes=10,
        storage_path="x",
        uploaded_by=None,
        verification_status=DocumentVerificationStatus.FLAGGED,
        version=1,
    )
    assert _document_validity([flagged], None) == 0.0

    expired = Document(
        application_id=None,
        doc_type="AICTE_LAND_DOC",
        filename="land.pdf",
        content_type="application/pdf",
        size_bytes=10,
        storage_path="x",
        uploaded_by=None,
        verification_status=DocumentVerificationStatus.PENDING,
        expiry_date=date(2020, 1, 1),
        version=1,
    )
    assert _document_validity([expired], None) == 0.0
    assert _document_validity(
        [expired], reference_date=date(2019, 1, 1)
    ) == 1.0


def test_safe_operator_evaluation_and_between_bounds() -> None:
    land_ok = _evaluate_rule(
        _rule(metric_key="infrastructure.land_area", operator=">=", threshold="8000"),
        9500.0,
    )
    assert land_ok.status == "PASS"

    between_pass = _evaluate_rule(
        _rule(
            metric_key="faculty.student_faculty_ratio",
            operator="BETWEEN",
            threshold="10",
            threshold_max="20",
        ),
        14.0,
    )
    assert between_pass.status == "PASS"
    assert "expected between 10" in between_pass.message
    assert "20 students/faculty" in between_pass.message
    assert between_pass.evidence["observed_value"] == 14.0
    assert between_pass.explanation["criteria"] == "Test-only rule."
    assert between_pass.explanation["status"] == "PASS"
    assert between_pass.explanation["passed"] is True
    assert between_pass.explanation["apH_clause"] == "DEMO"
    assert between_pass.explanation["needs_verification"] is True

    between_fail = _evaluate_rule(
        _rule(
            metric_key="faculty.student_faculty_ratio",
            operator="BETWEEN",
            threshold="10",
            threshold_max="20",
        ),
        27.0,
    )
    assert between_fail.status == "FAIL"

    exists_rule = _rule(
        metric_key="faculty.student_faculty_ratio", operator="EXISTS", threshold="0"
    )
    assert _evaluate_rule(exists_rule, 27.0).status == "PASS"


def test_missing_metric_is_flagged_not_crashed() -> None:
    unknown = _evaluate_rule(
        _rule(metric_key="totals.we_do_not_collect", operator=">=", threshold="1"),
        None,
    )
    assert unknown.status == "NOT_ASSESSED"
    assert unknown.message.startswith("Data missing: ")
    assert unknown.explanation["passed"] is None
    assert unknown.explanation["status"] == "NOT_ASSESSED"
    known = _evaluate_rule(
        _rule(metric_key="infrastructure.labs", operator=">=", threshold="10"), None
    )
    assert known.status == "NOT_ASSESSED"
    assert "Laboratories" in known.message


def test_weighted_score_earns_passed_severity_weight() -> None:
    weights = {"CRITICAL": 25.0, "HIGH": 15.0, "MEDIUM": 8.0, "LOW": 4.0}
    results = [
        (Severity.CRITICAL, True),
        (Severity.HIGH, False),
        (Severity.MEDIUM, True),
        (Severity.LOW, True),
    ]
    # (25 + 8 + 4) / 52 * 100
    assert _weighted_score(results, weights) == 71.15  # rounded to 2dp
    assert _weighted_score([], weights) == 0.0


def test_rag_status_critical_failure_forces_red() -> None:
    breakpoints = {"red_below": 70.0, "amber_below": 85.0}
    assert (
        _rag_status(failed_critical_count=1, score=95.0, breakpoints=breakpoints)
        == ComplianceHealth.RED
    )
    assert (
        _rag_status(failed_critical_count=0, score=60.0, breakpoints=breakpoints)
        == ComplianceHealth.RED
    )
    assert (
        _rag_status(failed_critical_count=0, score=71.0, breakpoints=breakpoints)
        == ComplianceHealth.AMBER
    )
    assert (
        _rag_status(failed_critical_count=0, score=85.0, breakpoints=breakpoints)
        == ComplianceHealth.GREEN
    )


def test_equality_operator_aliases_work() -> None:
    """Both ``=`` and ``==`` compare equality without using eval()."""
    for operator in ("=", "=="):
        rule = _rule(
            metric_key="derived.naac_grade_present",
            operator=operator,
            threshold="1",
        )
        assert _evaluate_rule(rule, 1.0).status == "PASS"
        assert _evaluate_rule(rule, 0.0).status == "FAIL"


def _application_with_levels(*levels: str) -> Application:
    application = Application(
        institution_id=uuid.uuid4(),
        application_type=ApplicationType.NEW_INSTITUTION,
        academic_year="2026-27",
        status=ApplicationStatus.SUBMITTED,
        current_stage=WorkflowStage.SCRUTINY,
        data={},
    )
    application.programs = [
        ApplicationProgram(
            application_id=None,
            program_name=f"{level}-Programme",
            level=level,
            intake=60,
            faculty_count=5,
            lab_count=1,
        )
        for level in levels
    ]
    return application


def test_rule_scope_matches_application_type_and_programme_level() -> None:
    rule = _rule(metric_key="infrastructure.labs", operator=">=", threshold="10")

    ug_application = _application_with_levels("UG")
    pg_application = _application_with_levels("PG")

    rule.applies_to = "UG"
    assert _applies_to_application(rule, ug_application) is True
    assert _applies_to_application(rule, pg_application) is False

    rule.applies_to = "PG,EOA_SELF_DISCLOSURE"
    assert _applies_to_application(rule, pg_application) is True
    assert _applies_to_application(rule, ug_application) is False

    rule.applies_to = "NEW_INSTITUTION"
    assert _applies_to_application(rule, ug_application) is True

    rule.applies_to = "ALL"
    assert _applies_to_application(rule, pg_application) is True


def test_metric_catalogue_exposes_editor_labels() -> None:
    catalogue = {metric["key"]: metric for metric in available_metric_catalogue()}
    assert catalogue["faculty.student_faculty_ratio"]["label"] == "Student-faculty ratio"
    assert catalogue["derived.document_validity"]["unit"] is None
    assert "finance.total_annual_fee" in catalogue


def test_config_defaults_are_used_when_rows_missing() -> None:
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models.compliance import ComplianceConfig

    with SessionLocal() as db:
        # The seeded config rows must mirror the engine defaults.
        rows = db.scalars(select(ComplianceConfig)).all()
        by_key = {row.key: row.value for row in rows}
        assert by_key["severity_weights"]["CRITICAL"] == 25.0
        assert by_key["rag_breakpoints"]["red_below"] == 70.0
