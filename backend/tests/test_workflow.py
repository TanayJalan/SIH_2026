"""Workflow state machine, deficiency, inspection and decision tests."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import (
    Application,
    ApplicationCategory,
    ApplicationStatus,
    ApplicationTrack,
    ApplicationType,
    Role,
    SLAConfig,
    User,
    WorkflowEvent,
    WorkflowStage,
)
from app.models.audit import AuditLog
from tests.support import (
    COMPLETE_APPLICATION_DATA,
    TestData,
    TestUser,
    auth_headers,
    create_draft,
    pay_application_fee,
    upload_mandatory_documents,
)

DUE_DATE = (date.today() + timedelta(days=7)).isoformat()


def _headers(
    client: TestClient,
    test_data: TestData,
    key: str,
) -> dict[str, str]:
    return auth_headers(client, test_data.users[key], test_data.password)


def _start_application(
    client: TestClient,
    test_data: TestData,
    tracked: list[uuid.UUID],
    *,
    via_action: bool = False,
) -> tuple[str, dict[str, Any]]:
    """Create a complete draft and submit it through the real endpoint."""
    admin_headers = _headers(client, test_data, "institution_admin_west")
    created = create_draft(client, admin_headers, tracked)
    application_id = created["id"]

    update = client.patch(
        f"/applications/{application_id}",
        json={"data": COMPLETE_APPLICATION_DATA},
        headers=admin_headers,
    )
    assert update.status_code == 200, update.text
    upload_mandatory_documents(client, admin_headers, application_id)
    pay_application_fee(client, admin_headers, application_id)

    path = (
        f"/applications/{application_id}/actions/submit"
        if via_action
        else f"/applications/{application_id}/submit"
    )
    submitted = client.post(path, headers=admin_headers)
    assert submitted.status_code == 200, submitted.text
    body = submitted.json()
    return application_id, body["application"]


def _seed_application(
    db,
    test_data: TestData,
    tracked: list[uuid.UUID],
    *,
    status: ApplicationStatus,
    stage: WorkflowStage,
) -> uuid.UUID:
    now = datetime.now(UTC)
    application = Application(
        institution_id=test_data.institutions["west"],
        track=ApplicationTrack.NEW_INSTITUTION,
        application_type=ApplicationType.NEW_INSTITUTION,
        category=ApplicationCategory.CAT1_CUTOFF,
        academic_year="2026-27",
        status=status,
        current_stage=stage,
        assigned_officer_id=test_data.users["scrutiny"].id,
        submitted_at=now,
        stage_entered_at=now,
        sla_due_at=now + timedelta(days=10),
        data={"reference": f"TEST-WF-{uuid.uuid4().hex[:8]}", "demo": True},
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    tracked.append(application.id)
    return application.id


@pytest.fixture
def extra_officer(test_data: TestData):
    """Create a second scrutiny officer in the west region for load tests."""
    suffix = uuid.uuid4().hex[:10]
    with SessionLocal() as db:
        user = User(
            name=f"Extra Scrutiny Officer {suffix} (Test)",
            email=f"extra.officer.{suffix}@example.edu",
            password_hash=hash_password(test_data.password),
            role=Role.SCRUTINY_COMMITTEE_MEMBER,
            institution_id=test_data.institutions["west"],
            region=test_data.users["scrutiny"].region,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        info = TestUser(
            id=user.id,
            email=user.email,
            role=user.role,
            region=user.region,
            institution_id=user.institution_id,
        )

    yield info

    with SessionLocal() as db:
        db.execute(delete(AuditLog).where(AuditLog.actor_id == info.id))
        db.execute(delete(User).where(User.id == info.id))
        db.commit()


def test_application_travels_from_submission_to_approval_with_full_timeline(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    application_id, application = _start_application(
        api_client,
        test_data,
        workspace_applications,
        via_action=True,
    )
    assert application["status"] == "DOCUMENT_VERIFICATION"
    assert application["assigned_officer_id"] == str(test_data.users["scrutiny"].id)

    scrutiny_headers = _headers(api_client, test_data, "scrutiny")
    institution_headers = _headers(api_client, test_data, "institution_admin_west")
    inspection_headers = _headers(api_client, test_data, "inspection")
    regional_headers = _headers(api_client, test_data, "regional")
    regulation_headers = _headers(api_client, test_data, "regulation")
    ec_headers = _headers(api_client, test_data, "ec")

    allowed = api_client.get(
        f"/applications/{application_id}/allowed-actions",
        headers=scrutiny_headers,
    )
    assert allowed.status_code == 200, allowed.text
    action_values = {item["action"] for item in allowed.json()["actions"]}
    assert "verify_documents" in action_values
    assert "approve" not in action_values

    verified = api_client.post(
        f"/applications/{application_id}/actions/verify_documents",
        headers=scrutiny_headers,
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["application"]["status"] == "SCRUTINY"

    raised = api_client.post(
        f"/applications/{application_id}/actions/raise_deficiency",
        headers=scrutiny_headers,
        json={
            "deficiencies": [
                {
                    "category": "DOCUMENT",
                    "description": "Affiliation certificate is not legible.",
                    "due_date": DUE_DATE,
                }
            ]
        },
    )
    assert raised.status_code == 200, raised.text
    assert raised.json()["application"]["status"] == "DEFICIENCY_RAISED"

    deficiencies = api_client.get(
        f"/applications/{application_id}/deficiencies",
        headers=institution_headers,
    )
    assert deficiencies.status_code == 200, deficiencies.text
    deficiency_items = deficiencies.json()
    assert len(deficiency_items) == 1
    assert deficiency_items[0]["status"] == "OPEN"
    deficiency_id = deficiency_items[0]["id"]

    responded = api_client.post(
        f"/applications/{application_id}/actions/respond_deficiency",
        headers=institution_headers,
        json={
            "responses": [
                {
                    "deficiency_id": deficiency_id,
                    "response_text": "A signed, legible copy has been uploaded.",
                }
            ]
        },
    )
    assert responded.status_code == 200, responded.text
    assert responded.json()["application"]["status"] == "DEFICIENCY_RESPONDED"

    closed = api_client.post(
        f"/applications/{application_id}/actions/close_deficiency",
        headers=scrutiny_headers,
        json={"deficiency_id": deficiency_id},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["application"]["status"] == "SCRUTINY"

    scheduled_on = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    schedule = api_client.post(
        f"/applications/{application_id}/actions/schedule_inspection",
        headers=regional_headers,
        json={
            "committee_id": str(test_data.users["inspection"].id),
            "scheduled_on": scheduled_on,
        },
    )
    assert schedule.status_code == 200, schedule.text
    assert schedule.json()["application"]["status"] == "INSPECTION_SCHEDULED"

    report = api_client.post(
        f"/applications/{application_id}/actions/submit_inspection_report",
        headers=inspection_headers,
        json={
            "report": {
                "infrastructure_ok": True,
                "faculty_verified": True,
                "lab_verified": True,
                "observations": "Illustrative inspection completed; all demo checks passed.",
                "recommendation": "APPROVE",
            }
        },
    )
    assert report.status_code == 200, report.text
    assert report.json()["application"]["status"] == "INSPECTION_DONE"

    to_committee = api_client.post(
        f"/applications/{application_id}/actions/send_to_committee",
        headers=regulation_headers,
    )
    assert to_committee.status_code == 200, to_committee.text
    assert to_committee.json()["application"]["status"] == "COMMITTEE_REVIEW"

    approved = api_client.post(
        f"/applications/{application_id}/actions/approve",
        headers=ec_headers,
        json={"comment": "Approved after demo committee review."},
    )
    assert approved.status_code == 200, approved.text
    approved_body = approved.json()
    assert approved_body["application"]["status"] == "APPROVED"
    assert approved_body["application"]["sla_due_at"] is None
    assert approved_body["application"]["current_stage"] == "COMPLETED"

    timeline = api_client.get(
        f"/applications/{application_id}/timeline",
        headers=institution_headers,
    )
    assert timeline.status_code == 200, timeline.text
    timeline_body = timeline.json()
    assert timeline_body["status"] == "APPROVED"
    assert len(timeline_body["events"]) == 10
    assert [event["action"] for event in timeline_body["events"]] == [
        "submit",
        "auto_assign",
        "verify_documents",
        "raise_deficiency",
        "respond_deficiency",
        "close_deficiency",
        "schedule_inspection",
        "submit_inspection_report",
        "send_to_committee",
        "approve",
    ]
    assert timeline_body["events"][0]["from_status"] == "DRAFT"
    assert timeline_body["events"][-1]["to_status"] == "APPROVED"
    assert all(event["actor_name"] for event in timeline_body["events"])


def test_multiple_deficiencies_close_only_after_every_item(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    application_id, _ = _start_application(api_client, test_data, workspace_applications)
    scrutiny_headers = _headers(api_client, test_data, "scrutiny")
    institution_headers = _headers(api_client, test_data, "institution_admin_west")

    api_client.post(
        f"/applications/{application_id}/actions/verify_documents",
        headers=scrutiny_headers,
    )
    raised = api_client.post(
        f"/applications/{application_id}/actions/raise_deficiency",
        headers=scrutiny_headers,
        json={
            "deficiencies": [
                {
                    "category": "FACULTY",
                    "description": "Faculty list does not match the submitted profile.",
                    "due_date": DUE_DATE,
                },
                {
                    "category": "INFRASTRUCTURE",
                    "description": "Laboratory area requires clarification.",
                    "due_date": DUE_DATE,
                },
            ]
        },
    )
    assert raised.status_code == 200, raised.text

    deficiencies = api_client.get(
        f"/applications/{application_id}/deficiencies",
        headers=institution_headers,
    ).json()
    assert len(deficiencies) == 2
    response_payload = {
        "responses": [
            {
                "deficiency_id": item["id"],
                "response_text": f"Response for {item['category']}.",
            }
            for item in deficiencies
        ]
    }
    responded = api_client.post(
        f"/applications/{application_id}/actions/respond_deficiency",
        headers=institution_headers,
        json=response_payload,
    )
    assert responded.status_code == 200, responded.text
    assert responded.json()["application"]["status"] == "DEFICIENCY_RESPONDED"

    first_close = api_client.post(
        f"/applications/{application_id}/actions/close_deficiency",
        headers=scrutiny_headers,
        json={"deficiency_id": deficiencies[0]["id"]},
    )
    assert first_close.status_code == 200, first_close.text
    assert "1 item(s) still need review" in first_close.json()["message"]
    assert first_close.json()["application"]["status"] == "DEFICIENCY_RESPONDED"

    timeline = api_client.get(
        f"/applications/{application_id}/timeline",
        headers=institution_headers,
    ).json()
    assert timeline["events"][-1]["action"] == "close_deficiency"
    assert timeline["events"][-1]["from_status"] == "DEFICIENCY_RESPONDED"
    assert timeline["events"][-1]["to_status"] == "DEFICIENCY_RESPONDED"

    second_close = api_client.post(
        f"/applications/{application_id}/actions/close_deficiency",
        headers=scrutiny_headers,
        json={"deficiency_id": deficiencies[1]["id"]},
    )
    assert second_close.status_code == 200, second_close.text
    assert second_close.json()["application"]["status"] == "SCRUTINY"

    final_items = api_client.get(
        f"/applications/{application_id}/deficiencies",
        headers=institution_headers,
    ).json()
    assert {item["status"] for item in final_items} == {"CLOSED"}
    assert all(item["closed_at"] for item in final_items)


def test_illegal_transition_and_wrong_role_are_rejected(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    application_id, _ = _start_application(api_client, test_data, workspace_applications)
    scrutiny_headers = _headers(api_client, test_data, "scrutiny")
    institution_headers = _headers(api_client, test_data, "institution_admin_west")

    illegal = api_client.post(
        f"/applications/{application_id}/actions/approve",
        headers=scrutiny_headers,
    )
    assert illegal.status_code == 409
    assert "not allowed" in illegal.json()["detail"].lower()

    wrong_role = api_client.post(
        f"/applications/{application_id}/actions/verify_documents",
        headers=institution_headers,
    )
    assert wrong_role.status_code == 403
    assert "role" in wrong_role.json()["detail"].lower()


def test_each_transition_recalculates_sla_and_stage_timestamp(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    application_id, application = _start_application(
        api_client, test_data, workspace_applications
    )
    scrutiny_headers = _headers(api_client, test_data, "scrutiny")

    with SessionLocal() as db:
        stored = db.get(Application, uuid.UUID(application_id))
        assert stored is not None and stored.stage_entered_at is not None
        verification_sla = db.scalar(
            select(SLAConfig).where(
                SLAConfig.stage == WorkflowStage.DOCUMENT_VERIFICATION
            )
        )
        assert verification_sla is not None
        first_stage_entered = stored.stage_entered_at
        assert stored.sla_due_at == first_stage_entered + timedelta(
            days=verification_sla.duration_days
        )

    verified = api_client.post(
        f"/applications/{application_id}/actions/verify_documents",
        headers=scrutiny_headers,
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["application"]["current_stage"] == "SCRUTINY"

    with SessionLocal() as db:
        stored = db.get(Application, uuid.UUID(application_id))
        assert stored is not None and stored.stage_entered_at is not None
        scrutiny_sla = db.scalar(
            select(SLAConfig).where(SLAConfig.stage == WorkflowStage.SCRUTINY)
        )
        assert scrutiny_sla is not None
        assert stored.stage_entered_at >= first_stage_entered
        assert stored.sla_due_at == stored.stage_entered_at + timedelta(
            days=scrutiny_sla.duration_days
        )


def test_auto_assignment_uses_lowest_load_then_round_robin_tie_break(
    api_client: TestClient,
    test_data: TestData,
    extra_officer: TestUser,
    workspace_applications: list[uuid.UUID],
) -> None:
    _, first = _start_application(api_client, test_data, workspace_applications)
    assert first["assigned_officer_id"] == str(extra_officer.id)

    _, second = _start_application(api_client, test_data, workspace_applications)
    assert second["assigned_officer_id"] == str(test_data.users["scrutiny"].id)


def test_withdraw_is_an_overlay_and_blocks_further_actions(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    application_id, application = _start_application(
        api_client, test_data, workspace_applications
    )
    assert application["status"] == "DOCUMENT_VERIFICATION"
    institution_headers = _headers(api_client, test_data, "institution_admin_west")
    scrutiny_headers = _headers(api_client, test_data, "scrutiny")

    withdrawn = api_client.post(
        f"/applications/{application_id}/actions/withdraw",
        headers=institution_headers,
        json={"comment": "Institution chose not to continue this cycle."},
    )
    assert withdrawn.status_code == 200, withdrawn.text
    body = withdrawn.json()["application"]
    assert body["status"] == "DOCUMENT_VERIFICATION"
    assert body["is_withdrawn"] is True
    assert body["sla_due_at"] is None

    allowed = api_client.get(
        f"/applications/{application_id}/allowed-actions",
        headers=institution_headers,
    )
    assert allowed.status_code == 200
    assert allowed.json()["actions"] == []

    blocked = api_client.post(
        f"/applications/{application_id}/actions/verify_documents",
        headers=scrutiny_headers,
    )
    assert blocked.status_code == 409

    timeline = api_client.get(
        f"/applications/{application_id}/timeline",
        headers=institution_headers,
    ).json()
    assert timeline["is_withdrawn"] is True
    assert timeline["events"][-1]["action"] == "withdraw"
    assert timeline["events"][-1]["from_status"] == timeline["events"][-1]["to_status"]


def test_decision_actions_cover_conditional_approval_and_rejection(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    ec_headers = _headers(api_client, test_data, "ec")

    with SessionLocal() as db:
        conditional_id = _seed_application(
            db,
            test_data,
            workspace_applications,
            status=ApplicationStatus.COMMITTEE_REVIEW,
            stage=WorkflowStage.COMMITTEE_REVIEW,
        )

    missing_conditions = api_client.post(
        f"/applications/{conditional_id}/actions/conditionally_approve",
        headers=ec_headers,
        json={"comment": "Subject to conditions."},
    )
    assert missing_conditions.status_code == 422

    conditional = api_client.post(
        f"/applications/{conditional_id}/actions/conditionally_approve",
        headers=ec_headers,
        json={
            "comment": "Approved for one year.",
            "conditions": "Submit the revised faculty list within 30 days.",
        },
    )
    assert conditional.status_code == 200, conditional.text
    conditional_body = conditional.json()["application"]
    assert conditional_body["status"] == "CONDITIONALLY_APPROVED"
    assert (
        conditional_body["decision"]["conditions"]
        == "Submit the revised faculty list within 30 days."
    )

    with SessionLocal() as db:
        rejected_id = _seed_application(
            db,
            test_data,
            workspace_applications,
            status=ApplicationStatus.COMMITTEE_REVIEW,
            stage=WorkflowStage.COMMITTEE_REVIEW,
        )

    rejected = api_client.post(
        f"/applications/{rejected_id}/actions/reject",
        headers=ec_headers,
        json={"comment": "Illustrative rejection reason."},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["application"]["status"] == "REJECTED"

    with SessionLocal() as db:
        events = db.scalars(
            select(WorkflowEvent)
            .where(WorkflowEvent.application_id == rejected_id)
            .order_by(WorkflowEvent.created_at.asc())
        ).all()
        assert events[-1].action == "reject"
        assert events[-1].to_status == ApplicationStatus.REJECTED
