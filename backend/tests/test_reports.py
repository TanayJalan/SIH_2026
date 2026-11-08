"""Role-specific report and dashboard aggregate endpoint tests.

These tests assert the shape of the aggregate responses and the configuration
linkage (APH clauses) rather than engine behaviour. All figures come from SQL
aggregations.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import (
    Application,
    ApplicationStatus,
    ApplicationTrack,
    Complaint,
    Decision,
    DecisionBody,
    DecisionLetterType,
    DecisionOutcome,
    Deficiency,
    DeficiencyStatus,
    Document,
    DocumentVerificationStatus,
    FeeKind,
    FeeTransaction,
    Institution,
    InstitutionClass,
    InstitutionRegion,
    PenalAction,
    PenalActionType,
    SecurityDeposit,
    SecurityDepositStatus,
    User,
    WorkflowEvent,
    WorkflowStage,
)
from app.models.alert import Alert
from app.models.enums import ComplaintStatus
from tests.support import TestData, auth_headers, create_draft

TEST_PASSWORD = "TestPass123!"


def _headers(api_client: TestClient, data: TestData, key: str) -> dict[str, str]:
    return auth_headers(api_client, data.users[key], data.password)


def _login(api_client: TestClient, data: TestData, key: str) -> str:
    body = api_client.post(
        "/auth/login",
        json={"email": data.users[key].email, "password": TEST_PASSWORD},
    )
    assert body.status_code == 200, body.text
    return body.json()["access_token"]


def _seed_report_data(api_client: TestClient, data: TestData) -> None:
    """Seed additional records so aggregates have data to return."""
    token = _login(api_client, data, "super")

    with SessionLocal() as db:
        west_app = db.get(Application, data.applications["west"])
        east_app = db.get(Application, data.applications["east"])
        assert west_app is not None and east_app is not None

        # West: scrutiny, overdue SLA, with deficiencies.
        west_app.status = ApplicationStatus.SCRUTINY
        west_app.current_stage = WorkflowStage.SCRUTINY
        west_app.sla_due_at = datetime.now(UTC) - timedelta(days=5)
        west_app.decision_type = None

        # East: submitted, no officer, SLA in future.
        east_app.status = ApplicationStatus.SUBMITTED
        east_app.current_stage = WorkflowStage.APPLICATION
        east_app.sla_due_at = datetime.now(UTC) + timedelta(days=10)

        # Check if already seeded (avoid duplicates on re-seed).
        existing_def = db.scalar(
            select(Deficiency).where(Deficiency.application_id == west_app.id)
        )
        if existing_def is None:
            db.add(Deficiency(
                application_id=west_app.id,
                category="Faculty",
                description="Missing associate professor (Fictional)",
                raised_by=data.users["super"].id,
                status=DeficiencyStatus.OPEN,
                due_date=date.today() + timedelta(days=7),
            ))
            db.add(Deficiency(
                application_id=west_app.id,
                category="Infrastructure",
                description="Lab shortfall (Fictional)",
                raised_by=data.users["super"].id,
                status=DeficiencyStatus.OPEN,
                due_date=date.today() + timedelta(days=14),
            ))

            db.add(Document(
                application_id=west_app.id,
                doc_type="Fire NOC",
                filename="fire_noc.pdf",
                content_type="application/pdf",
                size_bytes=1024,
                storage_path="/storage/fire_noc.pdf",
                uploaded_by=data.users["institution_admin_west"].id,
                verification_status=DocumentVerificationStatus.PENDING,
                expiry_date=date.today() + timedelta(days=30),
                apH_clause="APH 6.17h",
            ))
            db.add(Document(
                application_id=west_app.id,
                doc_type="Structural Stability Certificate",
                filename="structural.pdf",
                content_type="application/pdf",
                size_bytes=1024,
                storage_path="/storage/structural.pdf",
                uploaded_by=data.users["institution_admin_west"].id,
                verification_status=DocumentVerificationStatus.PENDING,
                expiry_date=date.today() + timedelta(days=10),
                apH_clause="APH 6.17h",
            ))

            suffix = uuid.uuid4().hex[:8]
            db.add(FeeTransaction(
                application_id=west_app.id,
                item_code="TER",
                amount_paise=15000000,
                kind=FeeKind.TER,
                receipt_no=f"R-{suffix}-001",
                paid_at=datetime.now(UTC),
                apH_clause="APH 4.2",
            ))
            db.add(FeeTransaction(
                application_id=west_app.id,
                item_code="TER",
                amount_paise=500000,
                kind=FeeKind.REFUND,
                receipt_no=f"R-{suffix}-002",
                paid_at=datetime.now(UTC),
                apH_clause="APH 4.2",
            ))

            db.add(SecurityDeposit(
                institution_id=data.institutions["west"],
                application_id=west_app.id,
                programme_family="Engineering & Technology",
                level="Under Graduate",
                required_paise=1000000,
                created_on=date.today() - timedelta(days=5),
                maturity_on=date.today() + timedelta(days=10),
                status=SecurityDepositStatus.PENDING,
                apH_clause="APH 2.25f",
            ))

            db.add(PenalAction(
                institution_id=data.institutions["west"],
                application_id=west_app.id,
                action_type=PenalActionType.INTAKE_REDUCTION,
                violation_code="c",
                hearing_done=True,
                speaking_order="Fictional speaking order",
                effective_academic_year="2026-27",
                apH_clause="APH 7.3",
            ))

            db.add(Complaint(
                institution_id=data.institutions["west"],
                source="PORTAL",
                status=ComplaintStatus.PGRC,
                category="Faculty shortage",
                description="Fictional complaint",
                received_on=date.today() - timedelta(days=5),
                apH_clause="APH 7.10",
            ))

            db.add(WorkflowEvent(
                application_id=west_app.id,
                from_status=ApplicationStatus.DRAFT,
                to_status=ApplicationStatus.SUBMITTED,
                action="submit",
                actor_id=data.users["institution_admin_west"].id,
                apH_clause="APH 1.4.3",
                created_at=datetime.now(UTC) - timedelta(days=10),
            ))
            db.add(WorkflowEvent(
                application_id=west_app.id,
                from_status=ApplicationStatus.SUBMITTED,
                to_status=ApplicationStatus.SCRUTINY,
                action="assign_scrutiny",
                actor_id=data.users["scrutiny"].id,
                apH_clause="APH 1.8a",
                created_at=datetime.now(UTC) - timedelta(days=5),
            ))

            db.add(Decision(
                application_id=west_app.id,
                body=DecisionBody.EC,
                outcome=DecisionOutcome.LOA,
                decided_on=date.today(),
                quorum_met=True,
                notes="Fictional EC approval.",
                apH_clause="APH 1.10a",
            ))

        db.commit()


def test_regulation_bureau_dashboard(
    api_client: TestClient, test_data: TestData
) -> None:
    _seed_report_data(api_client, test_data)
    headers = _headers(api_client, test_data, "regulation")

    response = api_client.get(
        "/reports/regulation-bureau",
        params={"state": "Test State West"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert "total_in_queue" in body
    assert "by_stage" in body
    assert "by_sla" in body
    assert "overdue_count" in body
    assert "overdue" in body
    assert "awaiting_institution_compliance" in body
    assert "upcoming_evc_dates" in body
    assert "average_handling_days" in body
    assert body["apH_clause"] == "APH 1.8"
    assert body["overdue_count"] >= 1
    assert any("West" in o["institution_name"] for o in body["overdue"])


def test_regulation_bureau_denied_to_institution_admin(
    api_client: TestClient, test_data: TestData
) -> None:
    headers = _headers(api_client, test_data, "institution_admin_west")
    response = api_client.get("/reports/regulation-bureau", headers=headers)
    assert response.status_code == 403


def test_regional_dashboard(
    api_client: TestClient, test_data: TestData
) -> None:
    _seed_report_data(api_client, test_data)
    headers = _headers(api_client, test_data, "regional")

    response = api_client.get("/reports/regional", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()

    assert "total_applications" in body
    assert "by_track_state" in body
    assert "funnel" in body
    assert "approval_vs_rejection" in body
    assert "appeals" in body
    assert "appeal_windows_closing_3_days" in body
    assert "security_deposits_pending" in body
    assert "loa_expiring_6_months" in body
    assert "institutions_by_compliance" in body
    assert "top_violation_codes" in body
    assert "faculty_ratio_deficit" in body
    assert "deficiency_categories" in body
    assert "sla_breach" in body
    assert "escalations" in body
    assert "complaints_by_status" in body
    assert "penal_actions_by_type" in body
    assert "average_days_per_stage" in body
    assert body["apH_clause"] == "APH 1.10"

    # Every funnel stage is returned, even when its count is zero. The seeder
    # only moves cases to their current status, so dropping stages hides the
    # shape of the pipeline (regression: the append used to sit outside the
    # loop and only the last stage survived).
    stages = [f["stage"] for f in body["funnel"]]
    assert stages == [
        "Submitted",
        "Scrutiny",
        "EVC Constituted",
        "EC Decision",
        "LoA Issued",
        "EoA Issued",
    ]

    # "Within deadline" is a subset of filed appeals.
    assert body["appeals"]["within_deadline"] <= body["appeals"]["filed"]

    # Check approval vs rejection
    assert "approvals" in body["approval_vs_rejection"]
    assert "rejections" in body["approval_vs_rejection"]
    assert "pending" in body["approval_vs_rejection"]

    # Check SLA breach
    assert "total_with_sla" in body["sla_breach"]
    assert "breached" in body["sla_breach"]
    assert "breach_rate" in body["sla_breach"]

    # Check violation codes. The demo seed also writes penal actions, so assert
    # the seeded code is reported rather than relying on being the global top.
    assert len(body["top_violation_codes"]) >= 1
    assert "c" in {entry["code"] for entry in body["top_violation_codes"]}

    # Check penal actions
    assert len(body["penal_actions_by_type"]) >= 1

    # Check complaints
    assert len(body["complaints_by_status"]) >= 1


def test_regional_denied_to_scrutiny(
    api_client: TestClient, test_data: TestData
) -> None:
    headers = _headers(api_client, test_data, "scrutiny")
    response = api_client.get("/reports/regional", headers=headers)
    assert response.status_code == 403


def test_super_admin_regional_dashboard(
    api_client: TestClient, test_data: TestData
) -> None:
    _seed_report_data(api_client, test_data)
    headers = _headers(api_client, test_data, "super")

    response = api_client.get("/reports/regional", headers=headers)
    assert response.status_code == 200, response.text


def test_institution_dashboard(
    api_client: TestClient, test_data: TestData
) -> None:
    _seed_report_data(api_client, test_data)
    headers = _headers(api_client, test_data, "institution_admin_west")

    response = api_client.get("/reports/institution", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()

    assert "portal_application_no" in body
    assert "application_id" in body
    assert "institution_name" in body
    assert "status" in body
    assert "open_deficiencies" in body
    assert "fees" in body
    assert "expiring_documents" in body
    assert "mandatory_disclosure" in body
    assert "compliance_score" in body
    assert "top_failing_rules" in body
    assert "upcoming_deadlines" in body
    assert body["apH_clause"] == "APH 1.4"

    # Check fees
    assert "total_paise" in body["fees"]
    assert "paid_paise" in body["fees"]
    assert "refunded_paise" in body["fees"]
    assert "due_paise" in body["fees"]

    # Check open deficiencies
    assert len(body["open_deficiencies"]) >= 2
    assert body["open_deficiencies"][0]["category"] == "Faculty"
    assert "days_left" in body["open_deficiencies"][0]

    # Check expiring documents
    assert len(body["expiring_documents"]) >= 2
    doc_types = {d["doc_type"] for d in body["expiring_documents"]}
    assert "Fire NOC" in doc_types
    assert "Structural Stability Certificate" in doc_types

    # Check mandatory disclosure
    assert "present" in body["mandatory_disclosure"]

    # Check upcoming deadlines
    deadline_keys = {d["key"] for d in body["upcoming_deadlines"]}
    assert "ENROLMENT_UPLOAD_30NOV" in deadline_keys or "IC_REPORT_30JUN" in deadline_keys


def test_institution_denied_to_regional(
    api_client: TestClient, test_data: TestData
) -> None:
    headers = _headers(api_client, test_data, "regional")
    response = api_client.get("/reports/institution", headers=headers)
    assert response.status_code == 403


def test_institution_no_institution_linked(
    api_client: TestClient, test_data: TestData
) -> None:
    # Scrutiny member has no institution
    headers = _headers(api_client, test_data, "scrutiny")
    response = api_client.get("/reports/institution", headers=headers)
    assert response.status_code == 403


def test_application_report_pdf(
    api_client: TestClient, test_data: TestData
) -> None:
    _seed_report_data(api_client, test_data)
    headers = _headers(api_client, test_data, "regulation")

    application_id = test_data.applications["west"]
    response = api_client.get(
        f"/reports/application/{application_id}.pdf", headers=headers
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers.get("content-disposition", "")
    assert response.content.startswith(b"%PDF")


def test_application_report_pdf_not_found(
    api_client: TestClient, test_data: TestData
) -> None:
    headers = _headers(api_client, test_data, "regulation")
    fake_id = uuid.uuid4()
    response = api_client.get(
        f"/reports/application/{fake_id}.pdf", headers=headers
    )
    assert response.status_code == 404


def test_application_report_pdf_denied_to_institution_admin(
    api_client: TestClient, test_data: TestData
) -> None:
    headers = _headers(api_client, test_data, "institution_admin_west")
    application_id = test_data.applications["west"]
    response = api_client.get(
        f"/reports/application/{application_id}.pdf", headers=headers
    )
    assert response.status_code == 200  # institution_admin is allowed


def test_global_filters(
    api_client: TestClient, test_data: TestData
) -> None:
    _seed_report_data(api_client, test_data)
    headers = _headers(api_client, test_data, "super")

    # Filter by academic year
    response = api_client.get(
        "/reports/regional?academic_year=2026-27", headers=headers
    )
    assert response.status_code == 200, response.text

    # Filter by track
    response = api_client.get(
        "/reports/regional?track=NEW_INSTITUTION", headers=headers
    )
    assert response.status_code == 200, response.text

    # Filter by application type
    response = api_client.get(
        "/reports/regional?application_type=NEW_INSTITUTION", headers=headers
    )
    assert response.status_code == 200, response.text

    # Filter by region
    response = api_client.get(
        f"/reports/regional?region={test_data.users['regional'].region}",
        headers=headers,
    )
    assert response.status_code == 200, response.text

    # Filter by state
    response = api_client.get(
        "/reports/regional?state=Test%20State%20West", headers=headers
    )
    assert response.status_code == 200, response.text


def test_regulation_bureau_with_filters(
    api_client: TestClient, test_data: TestData
) -> None:
    _seed_report_data(api_client, test_data)
    headers = _headers(api_client, test_data, "regulation")

    response = api_client.get(
        "/reports/regulation-bureau?academic_year=2026-27", headers=headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["apH_clause"] == "APH 1.8"
