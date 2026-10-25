"""Integration tests for the compliance admin API (rules, config, monitor)."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.application import Application
from app.models.audit import AuditLog
from app.models.compliance import ComplianceConfig, ComplianceRule
from app.models.enums import Severity
from tests.support import COMPLETE_APPLICATION_DATA, TestData, auth_headers

TEST_RULE_CODE = "TEST-ADMIN-RULE"


@pytest.fixture
def admin_rule(test_data: TestData) -> Generator[dict[str, Any], None, None]:
    """Create a test rule and delete it after the test."""
    with SessionLocal() as db:
        rule = ComplianceRule(
            code=TEST_RULE_CODE,
            name="Test admin rule",
            category="Test",
            description="Test-only rule for admin endpoint tests.",
            metric_key="faculty.total",
            operator=">=",
            threshold=500,
            severity=Severity.HIGH,
            applies_to="ALL",
            apH_clause="DEMO",
            needs_verification=True,
            is_active=True,
        )
        db.add(rule)
        db.commit()
        rule_id = rule.id
    yield {"id": str(rule_id), "code": TEST_RULE_CODE}
    with SessionLocal() as db:
        stored = db.get(ComplianceRule, rule_id)
        if stored is not None:
            db.delete(stored)
            db.commit()


def test_admin_rule_endpoints_are_role_gated(
    api_client: TestClient, test_data: TestData, admin_rule
) -> None:
    institution_headers = auth_headers(
        api_client, test_data.users["institution_admin_west"], test_data.password
    )
    assert (
        api_client.get("/compliance/rules", headers=institution_headers).status_code
        == 403
    )
    officer_headers = auth_headers(
        api_client, test_data.users["scrutiny"], test_data.password
    )
    assert (
        api_client.get("/compliance/rules", headers=officer_headers).status_code == 403
    )

    super_admin_headers = auth_headers(
        api_client, test_data.users["super"], test_data.password
    )
    listing = api_client.get("/compliance/rules", headers=super_admin_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1
    assert any(
        item["code"] == TEST_RULE_CODE for item in listing.json()["items"]
    )


def test_regional_head_can_read_but_not_not_expected_to_write(
    api_client: TestClient, test_data: TestData, admin_rule
) -> None:
    regional_headers = auth_headers(
        api_client, test_data.users["regional"], test_data.password
    )
    listing = api_client.get("/compliance/rules", headers=regional_headers)
    assert listing.status_code == 200


def test_update_rule_threshold_is_audited(
    api_client: TestClient, test_data: TestData, admin_rule
) -> None:
    headers = auth_headers(
        api_client, test_data.users["super"], test_data.password
    )
    response = api_client.patch(
        f"/compliance/rules/{admin_rule['id']}",
        json={"threshold": 10, "description": "Edited by admin test."},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["threshold"] == 10.0

    with SessionLocal() as db:
        entries = db.scalars(
            select(AuditLog).where(
                AuditLog.action == "compliance.rule.update",
                AuditLog.entity_id == uuid.UUID(admin_rule["id"]),
            )
        ).all()
        assert entries, "Rule edits must be audited"
        before = entries[-1].before
        after = entries[-1].after
    assert before["threshold"] == 500.0
    assert after["threshold"] == 10.0
    assert after["description"] == "Edited by admin test."


def test_create_rule_and_duplicate_code_conflict(
    api_client: TestClient, test_data: TestData, admin_rule
) -> None:
    headers = auth_headers(
        api_client, test_data.users["super"], test_data.password
    )
    payload = {
        "code": "TEST-ADMIN-NEW",
        "name": "Test new rule",
        "category": "Test",
        "description": "Created by an admin endpoint test.",
        "metric_key": "infrastructure.labs",
        "operator": ">=",
        "threshold": 3,
        "severity": "LOW",
        "applies_to": "ALL",
        "is_active": True,
    }
    created = api_client.post("/compliance/rules", json=payload, headers=headers)
    assert created.status_code == 201, created.text

    duplicate = api_client.post("/compliance/rules", json=payload, headers=headers)
    assert duplicate.status_code == 409

    with SessionLocal() as db:
        rule = db.scalar(
            select(ComplianceRule).where(ComplianceRule.code == "TEST-ADMIN-NEW")
        )
        assert rule is not None
        entry = db.scalar(
            select(AuditLog).where(
                AuditLog.action == "compliance.rule.create",
                AuditLog.entity_id == rule.id,
            )
        )
        db.delete(rule)
        db.commit()
    assert entry is not None


def test_rule_impact_preview_reports_flips(
    api_client: TestClient, test_data: TestData, admin_rule
) -> None:
    """Tightening the threshold against full data must report red flips."""
    headers = auth_headers(
        api_client, test_data.users["super"], test_data.password
    )
    proposed = {
        "code": TEST_RULE_CODE,
        "name": "Test admin rule",
        "category": "Test",
        "description": "Test-only rule for admin endpoint tests.",
        "metric_key": "faculty.student_faculty_ratio",
        "operator": "<=",
        "threshold": 5,
        "severity": "CRITICAL",
        "applies_to": "ALL",
        "is_active": True,
    }
    preview = api_client.post(
        "/compliance/rules/impact",
        json={"rule_id": admin_rule["id"], "proposed": proposed},
        headers=headers,
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert isinstance(body["red_flips"], int)
    assert body["red_flips"] + body["amber_flips"] + body["improved"] + body[
        "unchanged"
    ] > 0
    assert "RED" in body["message"] or "AMBER" in body["message"] or "No" in body["message"]


def test_config_read_update_roundtrip_and_audit(
    api_client: TestClient, test_data: TestData
) -> None:
    headers = auth_headers(
        api_client, test_data.users["super"], test_data.password
    )
    initial = api_client.get("/compliance/config", headers=headers)
    assert initial.status_code == 200
    assert initial.json()["rag_breakpoints"]["red_below"] == 70.0

    updated = api_client.put(
        "/compliance/config",
        json={"rag_breakpoints": {"red_below": 60.0, "amber_below": 85.0}},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["rag_breakpoints"]["red_below"] == 60.0

    with SessionLocal() as db:
        entries = db.scalars(
            select(AuditLog).where(AuditLog.action == "compliance.config.update")
        ).all()
        assert entries
        # Restore defaults for other tests / the dev database.
        row = db.scalar(
            select(ComplianceConfig).where(ComplianceConfig.key == "rag_breakpoints")
        )
        assert row is not None
        row.value = {"red_below": 70.0, "amber_below": 85.0}
        db.commit()

    restored = api_client.get("/compliance/config", headers=headers)
    assert restored.json()["rag_breakpoints"]["red_below"] == 70.0


def test_monitor_lists_institutions_with_latest_status(
    api_client: TestClient, test_data: TestData
) -> None:
    headers = auth_headers(
        api_client, test_data.users["super"], test_data.password
    )
    response = api_client.get("/compliance/monitor", headers=headers)
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert len(items) >= 1
    for item in items:
        assert item["institution_name"]
        assert item["latest_status"] in ("GREEN", "AMBER", "RED", None)
        if item["latest_status"] is not None:
            assert item["latest_score"] is not None
            assert item["latest_evaluated_at"] is not None


def test_institution_trend_returns_snapshot_history(
    api_client: TestClient, test_data: TestData
) -> None:
    headers = auth_headers(
        api_client, test_data.users["super"], test_data.password
    )
    monitor = api_client.get("/compliance/monitor", headers=headers)
    items = monitor.json()["items"]
    institution_id = next(
        item["institution_id"] for item in items if item["latest_status"] is not None
    )
    trend = api_client.get(
        f"/compliance/institutions/{institution_id}/trend", headers=headers
    )
    assert trend.status_code == 200, trend.text
    body = trend.json()
    assert body["institution_id"] == institution_id
    assert len(body["points"]) >= 1
    point = body["points"][0]
    assert point["status"] in ("GREEN", "AMBER", "RED")
    assert 0 <= point["score"] <= 100


def test_metric_catalogue_endpoint_lists_editable_metrics(
    api_client: TestClient, test_data: TestData
) -> None:
    headers = auth_headers(
        api_client, test_data.users["super"], test_data.password
    )
    response = api_client.get("/compliance/metrics", headers=headers)
    assert response.status_code == 200, response.text
    keys = {item["key"] for item in response.json()["items"]}
    assert "faculty.student_faculty_ratio" in keys
    assert "derived.document_validity" in keys

    institution_headers = auth_headers(
        api_client, test_data.users["institution_admin_west"], test_data.password
    )
    denied = api_client.get("/compliance/metrics", headers=institution_headers)
    assert denied.status_code == 403


def test_rule_edit_via_api_changes_live_application_result(
    api_client: TestClient, test_data: TestData, admin_rule
) -> None:
    """Acceptance: an admin threshold edit flips the application outcome."""
    headers = auth_headers(
        api_client, test_data.users["super"], test_data.password
    )
    application_id = test_data.applications["west"]
    original_data: dict[str, Any] | None = None
    with SessionLocal() as db:
        application = db.get(Application, application_id)
        assert application is not None
        original_data = dict(application.data)
        application.data = {
            **COMPLETE_APPLICATION_DATA,
            "reference": original_data.get("reference"),
        }
        db.commit()

    try:
        before = api_client.get(
            f"/applications/{application_id}/compliance", headers=headers
        )
        assert before.status_code == 200, before.text
        before_rule = _rule_by_code(before.json(), TEST_RULE_CODE)
        assert before_rule is not None
        assert before_rule["status"] == "FAIL"

        edited = api_client.patch(
            f"/compliance/rules/{admin_rule['id']}",
            json={"threshold": 10},
            headers=headers,
        )
        assert edited.status_code == 200, edited.text

        after = api_client.get(
            f"/applications/{application_id}/compliance", headers=headers
        )
        assert after.status_code == 200, after.text
        after_rule = _rule_by_code(after.json(), TEST_RULE_CODE)
        assert after_rule is not None
        assert after_rule["status"] == "PASS"
        assert after.json()["score"] >= before.json()["score"]
    finally:
        with SessionLocal() as db:
            application = db.get(Application, application_id)
            if application is not None and original_data is not None:
                application.data = original_data
                db.commit()


def _rule_by_code(body: dict[str, Any], code: str) -> dict[str, Any] | None:
    for rule in body["rules"]:
        if rule["code"] == code:
            return rule
    return None
