"""Compliance preview endpoint tests."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models import (
    Application,
    ApplicationType,
    ComplianceRule,
    Severity,
)
from tests.support import (
    COMPLETE_APPLICATION_DATA,
    TestData,
    auth_headers,
    create_draft,
    upload_mandatory_documents,
)

PREVIEW_DATA = {
    "institution_profile": {
        "head_name": "Dr Preview Registrar",
        "address_line1": "1 Fictional Preview Road",
        "city": "Pune",
        "state": "Maharashtra",
        "pin_code": "411001",
        "contact_email": "preview@example.edu",
        "contact_phone": "+91 98765 43210",
    },
    "infrastructure": {
        "land_area": 12000,
        "built_up_area": 8500,
        "labs": 18,
        "library": 24000,
        "hostel": 0,
    },
    "faculty": {
        "total": 120,
        "professors": 15,
        "associate_professors": 35,
        "assistant_professors": 70,
        "student_faculty_ratio": 18.5,
        "phd_faculty_ratio": 42,
    },
    "finance": {
        "tuition_fee": 150000,
        "development_fee": 25000,
        "other_fees": 10000,
        "balance": 1250000,
    },
    "accreditation": {"naac_grade": "A", "nba_status": "ACCREDITED"},
    "mandatory_disclosure_url": "https://example.edu/mandatory-disclosure",
}

RULE_CODES = ("TEST-PREVIEW-LAND", "TEST-PREVIEW-RATIO", "TEST-PREVIEW-PHD")


@pytest.fixture
def preview_rules() -> Generator[None, None, None]:
    """Create isolated rules and remove them after the test."""
    with SessionLocal() as db:
        db.execute(delete(ComplianceRule).where(ComplianceRule.code.in_(RULE_CODES)))
        db.add_all(
            [
                ComplianceRule(
                    code="TEST-PREVIEW-LAND",
                    name="Test minimum land area",
                    category="Test infrastructure",
                    description="Test-only land threshold.",
                    metric_key="infrastructure.land_area",
                    operator=">=",
                    threshold=Decimal("1000"),
                    severity=Severity.HIGH,
                    applies_to="ALL",
                    apH_clause="DEMO",
                    needs_verification=True,
                    is_active=True,
                ),
                ComplianceRule(
                    code="TEST-PREVIEW-RATIO",
                    name="Test maximum student-faculty ratio",
                    category="Test faculty",
                    description="Test-only ratio threshold.",
                    metric_key="faculty.student_faculty_ratio",
                    operator="<=",
                    threshold=Decimal("20"),
                    severity=Severity.HIGH,
                    applies_to="ALL",
                    apH_clause="DEMO",
                    needs_verification=True,
                    is_active=True,
                ),
                ComplianceRule(
                    code="TEST-PREVIEW-PHD",
                    name="Test PhD faculty share",
                    category="Test faculty",
                    description="Test-only PhD threshold.",
                    metric_key="faculty.phd_faculty_ratio",
                    operator=">=",
                    threshold=Decimal("30"),
                    severity=Severity.MEDIUM,
                    applies_to="ALL",
                    apH_clause="DEMO",
                    needs_verification=True,
                    is_active=True,
                ),
            ]
        )
        db.commit()
    try:
        yield
    finally:
        with SessionLocal() as db:
            rule_ids = (
                db.scalars(
                    select(ComplianceRule.id).where(
                        ComplianceRule.code.in_(RULE_CODES)
                    )
                ).all()
            )
            if rule_ids:
                from app.models.compliance import ComplianceResult

                db.execute(
                    delete(ComplianceResult).where(
                        ComplianceResult.rule_id.in_(rule_ids)
                    )
                )
            db.execute(delete(ComplianceRule).where(ComplianceRule.code.in_(RULE_CODES)))
            db.commit()


def _headers(
    client: TestClient, test_data: TestData, key: str = "institution_admin_west"
) -> dict[str, str]:
    return auth_headers(client, test_data.users[key], test_data.password)


def _create_draft(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post(
        "/applications",
        json={"application_type": "NEW_INSTITUTION", "academic_year": "2026-27"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _prepare_submitted_application(
    client: TestClient,
    headers: dict[str, str],
    application_id: str,
    *,
    data: dict[str, Any],
) -> None:
    """Fill draft data, upload mandatory documents and submit."""
    update = client.patch(
        f"/applications/{application_id}", json={"data": data}, headers=headers
    )
    assert update.status_code == 200, update.text
    upload_mandatory_documents(client, headers, application_id)
    submitted = client.post(f"/applications/{application_id}/submit", headers=headers)
    assert submitted.status_code == 200, submitted.text


def test_compliance_preview_evaluates_unsaved_values_without_persisting(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
    preview_rules: None,
) -> None:
    headers = _headers(api_client, test_data)
    application_id = _create_draft(api_client, headers)
    workspace_applications.append(uuid.UUID(application_id))

    preview = api_client.post(
        f"/applications/{application_id}/compliance/preview",
        json={"data": PREVIEW_DATA},
        headers=headers,
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    by_code = {
        rule["code"]: rule
        for rule in body["rules"]
        if rule["code"] in RULE_CODES
    }
    assert by_code["TEST-PREVIEW-LAND"]["status"] == "PASS"
    assert by_code["TEST-PREVIEW-RATIO"]["status"] == "PASS"
    assert by_code["TEST-PREVIEW-PHD"]["status"] == "PASS"

    partial_data = {
        "infrastructure": {"land_area": 500, "built_up_area": 8500},
        "faculty": {"student_faculty_ratio": 25},
    }
    partial = api_client.post(
        f"/applications/{application_id}/compliance/preview",
        json={"data": partial_data},
        headers=headers,
    )
    assert partial.status_code == 200, partial.text
    partial_by_code = {
        rule["code"]: rule
        for rule in partial.json()["rules"]
        if rule["code"] in RULE_CODES
    }
    assert partial_by_code["TEST-PREVIEW-LAND"]["status"] == "FAIL"
    assert partial_by_code["TEST-PREVIEW-RATIO"]["status"] == "FAIL"
    assert partial_by_code["TEST-PREVIEW-PHD"]["status"] == "NOT_ASSESSED"
    assert partial_by_code["TEST-PREVIEW-PHD"]["message"].startswith("Data missing: ")

    detail = api_client.get(f"/applications/{application_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["infrastructure"] is None
    assert detail.json()["data"]["faculty"] is None

    with SessionLocal() as db:
        application = db.get(Application, uuid.UUID(application_id))
        assert application is not None
        assert application.application_type == ApplicationType.NEW_INSTITUTION


def test_compliance_preview_rejects_cross_tenant_access(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
    preview_rules: None,
) -> None:
    owner_headers = _headers(api_client, test_data)
    other_headers = _headers(api_client, test_data, "institution_admin_east")
    application_id = _create_draft(api_client, owner_headers)
    workspace_applications.append(uuid.UUID(application_id))

    response = api_client.post(
        f"/applications/{application_id}/compliance/preview",
        json={"data": PREVIEW_DATA},
        headers=other_headers,
    )

    assert response.status_code == 403


def test_case_file_compliance_evaluates_submitted_data_for_officers(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
    preview_rules: None,
) -> None:
    """Officers read the rule evaluation of the submitted data from the case file."""
    institution_headers = _headers(api_client, test_data)
    officer_headers = _headers(api_client, test_data, "scrutiny")
    created = create_draft(api_client, institution_headers, workspace_applications)
    application_id = created["id"]

    _prepare_submitted_application(
        api_client,
        institution_headers,
        application_id,
        data=COMPLETE_APPLICATION_DATA,
    )

    response = api_client.get(
        f"/applications/{application_id}/compliance", headers=officer_headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    by_code = {
        rule["code"]: rule for rule in body["rules"] if rule["code"] in RULE_CODES
    }
    assert by_code["TEST-PREVIEW-LAND"]["status"] == "PASS"
    assert by_code["TEST-PREVIEW-LAND"]["observed_value"] == 12000


def test_case_file_compliance_maps_failed_rule_to_deficiency_text(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
    preview_rules: None,
) -> None:
    """A failing rule yields a message an officer can draft as deficiency text."""
    institution_headers = _headers(api_client, test_data)
    created = create_draft(api_client, institution_headers, workspace_applications)
    application_id = created["id"]

    failing_data: dict[str, Any] = {
        **COMPLETE_APPLICATION_DATA,
        "infrastructure": {
            **COMPLETE_APPLICATION_DATA["infrastructure"],
            "land_area": 500,
        },
    }
    _prepare_submitted_application(
        api_client,
        institution_headers,
        application_id,
        data=failing_data,
    )

    response = api_client.get(
        f"/applications/{application_id}/compliance", headers=institution_headers
    )
    assert response.status_code == 200, response.text
    failed = [
        rule
        for rule in response.json()["rules"]
        if rule["code"] == "TEST-PREVIEW-LAND"
    ]
    assert len(failed) == 1
    assert failed[0]["status"] == "FAIL"
    assert "configured rule requires at least" in failed[0]["message"]
    assert failed[0]["message"].startswith("Land area: 500")


def test_case_file_compliance_rejects_cross_tenant_access(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
    preview_rules: None,
) -> None:
    owner_headers = _headers(api_client, test_data)
    other_headers = _headers(api_client, test_data, "institution_admin_east")
    application_id = _create_draft(api_client, owner_headers)
    workspace_applications.append(uuid.UUID(application_id))

    response = api_client.get(
        f"/applications/{application_id}/compliance", headers=other_headers
    )
    assert response.status_code == 403
