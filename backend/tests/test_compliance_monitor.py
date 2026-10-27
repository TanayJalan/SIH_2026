"""Integration tests for the compliance monitor: persistence and alerts."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.alert import Alert
from app.models.application import Application, ApplicationProgram
from app.models.compliance import (
    ComplianceResult,
    ComplianceRule,
    ComplianceSnapshot,
)
from app.models.document import Document
from app.models.enums import (
    ApplicationCategory,
    ApplicationStatus,
    ApplicationTrack,
    ApplicationType,
    ComplianceHealth,
    DocumentVerificationStatus,
    InstitutionClass,
    InstitutionRegion,
    Role,
    Severity,
    WorkflowStage,
)
from app.models.institution import Institution
from app.models.required_document import RequiredDocument
from app.models.user import User
from app.services.compliance import (
    evaluate_application,
    evaluate_institution,
    run_nightly_evaluation,
)
from tests.support import TestData

GOOD_DATA: dict[str, Any] = {
    "infrastructure": {
        "land_area": 12000,
        "built_up_area": 8500,
        "labs": 18,
        "library": 24000,
        "hostel": 300,
    },
    "faculty": {
        "total": 120,
        "professors": 15,
        "associate_professors": 35,
        "assistant_professors": 70,
        "student_faculty_ratio": 12.0,
        "phd_faculty_ratio": 42,
    },
    "finance": {
        "tuition_fee": 90000,
        "development_fee": 40000,
        "other_fees": 12000,
        "balance": 1250000,
    },
    "accreditation": {"naac_grade": "A", "nba_status": "ACCREDITED"},
    "mandatory_disclosure_url": "https://example.edu/mandatory-disclosure",
}

BAD_DATA: dict[str, Any] = {
    "infrastructure": {
        "land_area": 500,
        "built_up_area": 900,
        "labs": 2,
        "library": 800,
        "hostel": 0,
    },
    "faculty": {
        "total": 4,
        "professors": 0,
        "associate_professors": 1,
        "assistant_professors": 1,
        "student_faculty_ratio": 220.0,
        "phd_faculty_ratio": 0,
    },
    "finance": {
        "tuition_fee": 400000,
        "development_fee": 100000,
        "other_fees": 25000,
        "balance": -90000,
    },
    "accreditation": {"naac_grade": "NOT_ACCREDITED", "nba_status": "NOT_ACCREDITED"},
}

TEST_AICTE_ID = "TEST-COMP-INST-1"
TEST_RULE_CODE = "TEST-ENGINE-RULE"


def _delete_monitored_data(db: Session, aicte_id: str) -> None:
    """Delete every fictional record tied to the monitored institution.

    Rows are removed child-first because the application/institution FKs are
    not declared with ON DELETE CASCADE on this relationship.
    """
    institution = db.scalar(select(Institution).where(Institution.aicte_id == aicte_id))
    if institution is None:
        return
    application_ids = list(
        db.scalars(
            select(Application.id).where(Application.institution_id == institution.id)
        ).all()
    )
    db.execute(
        delete(Alert).where(
            Alert.title.contains(aicte_id)
            | Alert.application_id.in_(application_ids)
        )
    )
    db.execute(
        delete(ComplianceResult).where(
            ComplianceResult.institution_id == institution.id
        )
    )
    db.execute(
        delete(ComplianceSnapshot).where(
            ComplianceSnapshot.institution_id == institution.id
        )
    )
    if application_ids:
        db.execute(
            delete(Document).where(Document.application_id.in_(application_ids))
        )
        db.execute(
            delete(ApplicationProgram).where(
                ApplicationProgram.application_id.in_(application_ids)
            )
        )
        db.execute(delete(Application).where(Application.id.in_(application_ids)))
    db.execute(delete(Institution).where(Institution.id == institution.id))
    db.commit()


@pytest.fixture
def monitored_institution(
    test_data: TestData,
) -> Generator[dict[str, Any], None, None]:
    """Create a fictional institution with one application, cleaned up after."""
    cleanup_alert_message = f"Test Compliance Institute ({TEST_AICTE_ID})"
    with SessionLocal() as db:
        # Remove leftovers from an earlier failed run of these tests.
        _delete_monitored_data(db, TEST_AICTE_ID)
        institution = Institution(
            name=cleanup_alert_message,
            aicte_id=TEST_AICTE_ID,
            pid=f"TEST-PID-{TEST_AICTE_ID}",
            state="Test State",
            region=test_data.users["regional"].region,
            aicte_region=InstitutionRegion.WESTERN,
            institution_class=InstitutionClass.OTHER,
            type="Engineering",
            institution_type="Engineering",
            established_year=2001,
            naac_grade=None,
            nba_status=None,
        )
        db.add(institution)
        db.flush()
        application = Application(
            institution_id=institution.id,
            track=ApplicationTrack.NEW_INSTITUTION,
            application_type=ApplicationType.NEW_INSTITUTION,
            category=ApplicationCategory.CAT1_CUTOFF,
            academic_year="2026-27",
            status=ApplicationStatus.APPROVED,
            current_stage=WorkflowStage.COMPLETED,
            data=GOOD_DATA,
        )
        db.add(application)
        db.flush()
        db.add_all(
            ApplicationProgram(
                application_id=application.id,
                program_name=program,
                level="UG",
                intake=200,
                faculty_count=20,
                lab_count=3,
            )
            for program in ("CSE", "ECE")
        )
        # Upload every mandatory Annexure-2 document so the baseline evaluation
        # has no document deficiency. Without this the institution would be RED
        # before the test changes any data, and the AMBER->RED flip below could
        # not be observed.
        required_documents = db.scalars(
            select(RequiredDocument).where(
                RequiredDocument.application_type == ApplicationType.NEW_INSTITUTION,
                RequiredDocument.mandatory.is_(True),
            )
        ).all()
        db.add_all(
            Document(
                application_id=application.id,
                doc_type=requirement.doc_type,
                doc_code=requirement.doc_code,
                filename=f"{requirement.doc_code}.pdf",
                content_type="application/pdf",
                size_bytes=10,
                storage_path=f"tests/{requirement.doc_code}.pdf",
                uploaded_by=test_data.users["institution_admin_west"].id,
                verification_status=DocumentVerificationStatus.PENDING,
                signed_with_dsc=True,
                version=1,
            )
            for requirement in required_documents
        )
        # A newer year-round request without any programme detail. The monitor
        # must evaluate the institution's programme application, not this one.
        change_request = Application(
            institution_id=institution.id,
            track=ApplicationTrack.EXISTING,
            application_type=ApplicationType.CHANGE_OF_SITE,
            category=ApplicationCategory.CAT2_YEAR_ROUND,
            academic_year="2026-27",
            status=ApplicationStatus.SUBMITTED,
            current_stage=WorkflowStage.APPLICATION,
            data={},
        )
        db.add(change_request)
        # A stray legacy closure case that does carry a programme row, but whose
        # application type is marked not_implemented. The monitor must not build
        # its snapshot from a case the workflow refuses to process.
        closure_request = Application(
            institution_id=institution.id,
            track=ApplicationTrack.NEW_INSTITUTION,
            application_type=ApplicationType.CLOSURE_AND_NEW_INSTITUTION,
            category=ApplicationCategory.CAT1_CUTOFF,
            academic_year="2026-27",
            status=ApplicationStatus.DRAFT,
            current_stage=WorkflowStage.APPLICATION,
            data={},
        )
        db.add(closure_request)
        db.flush()
        db.add(
            ApplicationProgram(
                application_id=closure_request.id,
                program_name="Legacy",
                level="UG",
                intake=60,
                faculty_count=4,
                lab_count=1,
            )
        )
        db.commit()
        context = {
            "institution_id": institution.id,
            "application_id": application.id,
            "change_request_id": change_request.id,
            "closure_request_id": closure_request.id,
        }
    try:
        yield context
    finally:
        with SessionLocal() as db:
            _delete_monitored_data(db, TEST_AICTE_ID)


def _application(db: Session, application_id: uuid.UUID) -> Application:
    application = db.get(Application, application_id)
    assert application is not None
    return application


def test_monitor_evaluates_the_programme_application(monitored_institution) -> None:
    """A newer year-round or unimplemented case must not replace the live case."""
    with SessionLocal() as db:
        institution = db.get(Institution, monitored_institution["institution_id"])
        assert institution is not None
        preview = evaluate_institution(
            db, institution, evaluated_at=datetime.now(UTC)
        )
        assert preview is not None
        assert preview.application_id == monitored_institution["application_id"]
        assert preview.application_id != monitored_institution["change_request_id"]
        assert preview.application_id != monitored_institution["closure_request_id"]


def test_evaluate_application_persists_results_score_and_snapshot(
    monitored_institution,
) -> None:
    now = datetime.now(UTC)
    with SessionLocal() as db:
        preview = evaluate_application(
            db,
            _application(db, monitored_institution["application_id"]),
            evaluated_at=now,
            trigger="application_update",
        )
        results = db.scalars(
            select(ComplianceResult).where(
                ComplianceResult.application_id == monitored_institution["application_id"]
            )
        ).all()
        assert results, "Per-rule results must be persisted"
        missing = [
            result for result in results if result.status == "NOT_ASSESSED"
        ]
        assert missing, "Metrics that cannot be derived must be persisted as data missing"
        assert missing[0].observed_value is None
        assert missing[0].message is not None
        assert missing[0].message.startswith("Data missing: ")
        assessed = [result for result in results if result.status != "NOT_ASSESSED"]
        assert assessed
        assert all(result.message for result in assessed)
        assert all(result.explanation["criteria"] for result in assessed)
        assert all(result.explanation["apH_clause"] for result in assessed)
        assert all(result.explanation["status"] == result.status for result in assessed)
        assert all(result.evidence["metric_key"] for result in assessed)
        assert missing[0].explanation["passed"] is None
        assert {result.status for result in assessed} <= {"PASS", "FAIL"}
        snapshot = cast(
            ComplianceSnapshot | None,
            db.scalar(
                select(ComplianceSnapshot)
                .where(
                    ComplianceSnapshot.institution_id
                    == monitored_institution["institution_id"]
                )
                .order_by(ComplianceSnapshot.evaluated_at.desc())
                .limit(1)
            ),
        )
        refreshed = _application(db, monitored_institution["application_id"])
        assert refreshed.compliance_score is not None
    # Every assessed rule passes, so the weighted score is 100. Yet the fixture
    # has no faculty roster, library or computing profile: mandatory evidence is
    # missing, so the result is AMBER and not a Nil Deficiency. A Nil Deficiency
    # requires every mandatory rule to be assessed and passing.
    assert preview.score == 100.0
    assert preview.mandatory_missing_count > 0
    assert preview.nil_deficiency is False
    assert preview.status == "AMBER"
    assert snapshot is not None
    assert snapshot.trigger == "application_update"
    assert snapshot.score == Decimal("100.00")
    assert snapshot.status == ComplianceHealth.AMBER


def test_red_flip_creates_alerts_for_regional_heads_and_admins(
    monitored_institution,
) -> None:
    with SessionLocal() as db:
        app = _application(db, monitored_institution["application_id"])
        evaluate_application(
            db, app, evaluated_at=datetime.now(UTC), trigger="application_update"
        )
        app = _application(db, monitored_institution["application_id"])
        app.data = BAD_DATA
        db.commit()
        evaluate_application(
            db, app, evaluated_at=datetime.now(UTC), trigger="nightly"
        )
        alerts = db.scalars(
            select(Alert).where(
                Alert.type == "COMPLIANCE_RAG_RED",
                Alert.title.contains(TEST_AICTE_ID),
            )
        ).all()
        assert alerts, "A RED flip must raise in-app alerts"
        recipient_roles = set(
            db.scalars(
                select(User.role).where(
                    User.id.in_([alert.recipient_user_id for alert in alerts])
                )
            ).all()
        )
    assert Role.SUPER_ADMIN in recipient_roles
    assert Role.REGIONAL_OFFICER in recipient_roles
    assert alerts[0].severity == Severity.CRITICAL


def test_nightly_evaluation_records_snapshots_for_all_institutions(
    monitored_institution,
) -> None:
    with SessionLocal() as db:
        results = run_nightly_evaluation()
        rows = {row["institution"]: row for row in results}
        assert TEST_AICTE_ID in rows
        latest = db.scalar(
            select(ComplianceSnapshot)
            .where(
                ComplianceSnapshot.institution_id
                == monitored_institution["institution_id"]
            )
            .order_by(ComplianceSnapshot.evaluated_at.desc())
            .limit(1)
        )
        snapshots = db.scalars(
            select(ComplianceSnapshot)
            .where(
                ComplianceSnapshot.institution_id
                == monitored_institution["institution_id"]
            )
            .order_by(ComplianceSnapshot.evaluated_at.desc())
        ).all()
    assert latest is not None
    # The nightly run reports the same status it persisted for the institution.
    assert rows[TEST_AICTE_ID]["status"] == latest.status.value
    assert len(snapshots) >= 1
    assert any(snapshot.trigger == "nightly" for snapshot in snapshots)


def test_rule_edit_changes_result_without_code_change(
    monitored_institution,
) -> None:
    """Acceptance: editing a threshold flips the outcome with no code change."""
    with SessionLocal() as db:
        rule = ComplianceRule(
            code=TEST_RULE_CODE,
            name="Test editable threshold",
            category="Test",
            description="Test-only threshold edit rule.",
            metric_key="faculty.total",
            operator=">=",
            threshold=Decimal("500"),
            severity=Severity.HIGH,
            applies_to="ALL",
            apH_clause="DEMO",
            needs_verification=True,
            is_active=True,
        )
        db.add(rule)
        db.commit()

        try:
            first = evaluate_application(
                db,
                _application(db, monitored_institution["application_id"]),
                evaluated_at=datetime.now(UTC),
                trigger="application_update",
            )

            # The admin edit path writes the same stored threshold; the
            # re-evaluation below therefore uses a data-driven change only.
            stored = db.scalar(
                select(ComplianceRule).where(ComplianceRule.code == TEST_RULE_CODE)
            )
            assert stored is not None
            stored.threshold = Decimal("10")
            db.commit()

            second = evaluate_application(
                db,
                _application(db, monitored_institution["application_id"]),
                evaluated_at=datetime.now(UTC),
                trigger="application_update",
            )
        finally:
            rule_result_ids = db.scalars(
                select(ComplianceResult.id).where(
                    ComplianceResult.rule_id == rule.id
                )
            ).all()
            if rule_result_ids:
                db.execute(
                    delete(ComplianceResult).where(
                        ComplianceResult.id.in_(rule_result_ids)
                    )
                )
                db.commit()
            db.execute(delete(ComplianceRule).where(ComplianceRule.id == rule.id))
            db.commit()

    assert _rule_status(first) == "FAIL"
    assert _rule_status(second) == "PASS"
    assert second.failed_count < first.failed_count
    assert second.score > first.score


def _rule_status(preview, code: str = TEST_RULE_CODE) -> str | None:
    for rule in preview.rules:
        if rule.code == code:
            return rule.status
    return None
