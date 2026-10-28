"""DEBUG-only simulated time endpoint tests."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.core.config import Settings
from app.db.session import SessionLocal
from app.main import create_app
from app.models.alert import Alert
from app.models.application import Application
from app.models.audit import AuditLog
from app.models.deadline import DeadlineRule, Timer, TimerStatus
from app.models.decision import DecisionLetter
from app.models.enums import (
    ApplicationCategory,
    ApplicationStatus,
    ApplicationTrack,
    DecisionLetterType,
    WorkflowStage,
)
from app.models.user import User
from app.models.workflow import WorkflowEvent
from app.services import workflow_jobs
from tests.support import TestData, auth_headers


@pytest.fixture(autouse=True)
def cleanup_simulation_artifacts() -> Generator[None, None, None]:
    """Remove alerts and escalation state produced by a simulation test."""
    with SessionLocal() as db:
        before = {
            "alerts": set(db.scalars(select(Alert.id)).all()),
            "events": set(db.scalars(select(WorkflowEvent.id)).all()),
            "audits": set(db.scalars(select(AuditLog.id)).all()),
            "escalated": set(
                db.scalars(
                    select(Application.id).where(Application.is_escalated.is_(True))
                ).all()
            ),
        }

    yield

    with SessionLocal() as db:
        new_alerts = set(db.scalars(select(Alert.id)).all()) - before["alerts"]
        new_events = set(db.scalars(select(WorkflowEvent.id)).all()) - before["events"]
        new_audits = set(db.scalars(select(AuditLog.id)).all()) - before["audits"]
        if new_audits:
            db.execute(delete(AuditLog).where(AuditLog.id.in_(new_audits)))
        if new_alerts:
            db.execute(delete(Alert).where(Alert.id.in_(new_alerts)))
        if new_events:
            db.execute(delete(WorkflowEvent).where(WorkflowEvent.id.in_(new_events)))
        now_escalated = set(
            db.scalars(
                select(Application.id).where(Application.is_escalated.is_(True))
            ).all()
        )
        for application_id in now_escalated - before["escalated"]:
            application = db.get(Application, application_id)
            if application is not None:
                application.is_escalated = False
        db.commit()


@pytest.fixture
def debug_api_client() -> Generator[TestClient, None, None]:
    with TestClient(create_app(Settings(debug=True))) as client:
        yield client


@pytest.fixture
def appeal_window_case(test_data: TestData) -> Generator[uuid.UUID, None, None]:
    """Insert a fictional rejection with its seven-day appeal clock open."""
    now = datetime.now(UTC)
    deadline = now + timedelta(days=7)
    with SessionLocal() as db:
        application = Application(
            institution_id=test_data.institutions["west"],
            track=ApplicationTrack.NEW_INSTITUTION,
            application_type="NEW_INSTITUTION",
            category=ApplicationCategory.CAT1_CUTOFF,
            academic_year="2026-27",
            portal_application_no=f"DEMO/2026-27/{uuid.uuid4().hex[:4].upper()}",
            status=ApplicationStatus.APPEAL_WINDOW,
            current_stage=WorkflowStage.DECISION,
            assigned_officer_id=test_data.users["scrutiny"].id,
            submitted_at=now,
            stage_entered_at=now,
            sla_due_at=now + timedelta(days=30),
            appeal_deadline=deadline,
            data={
                "reference": f"TEST-DEV-{uuid.uuid4().hex[:8]}",
                "demo": True,
                "pending_outcome": "LOR",
            },
        )
        db.add(application)
        db.flush()
        db.add(
            DecisionLetter(
                application_id=application.id,
                letter_type=DecisionLetterType.LOR,
                letter_number=f"AICTE-DEMO/2026/{uuid.uuid4().hex[:8].upper()}",
                issued_on=now.date(),
                published_at=now,
                appeal_clock_start=now,
                appeal_deadline=deadline,
                body_text="Fictional Speaking Order used by the demo-time test.",
            )
        )
        rule = db.scalar(
            select(DeadlineRule).where(DeadlineRule.code == "APPEAL_WINDOW")
        )
        assert rule is not None
        db.add(
            Timer(
                application_id=application.id,
                deadline_rule_id=rule.id,
                started_at=now,
                due_at=deadline,
                status=TimerStatus.PENDING,
            )
        )
        db.commit()
        application_id = application.id

    try:
        yield application_id
    finally:
        with SessionLocal() as db:
            db.execute(delete(Application).where(Application.id == application_id))
            db.commit()


def test_debug_time_endpoint_is_absent_when_debug_is_disabled(test_data: TestData) -> None:
    with TestClient(create_app(Settings(debug=False))) as client:
        user = test_data.users["super"]
        headers = auth_headers(client, user, test_data.password)

        response = client.get("/dev/simulate-time", headers=headers)

    assert response.status_code == 404


def test_debug_time_advances_and_resets(
    debug_api_client: TestClient, test_data: TestData
) -> None:
    user = test_data.users["super"]
    headers = auth_headers(debug_api_client, user, test_data.password)

    initial = debug_api_client.get("/dev/simulate-time", headers=headers)
    assert initial.status_code == 200
    assert initial.json()["offset_days"] == 0

    advanced = debug_api_client.post(
        "/dev/simulate-time",
        json={"days": 7},
        headers=headers,
    )
    assert advanced.status_code == 200
    assert advanced.json()["offset_days"] == 7
    simulated = datetime.fromisoformat(advanced.json()["simulated_now"])
    assert simulated > datetime.now(UTC)

    reset = debug_api_client.post(
        "/dev/simulate-time",
        json={"reset": True},
        headers=headers,
    )
    assert reset.status_code == 200
    assert reset.json()["offset_days"] == 0


def test_debug_time_rejects_empty_update(
    debug_api_client: TestClient, test_data: TestData
) -> None:
    user = test_data.users["super"]
    headers = auth_headers(debug_api_client, user, test_data.password)

    response = debug_api_client.post("/dev/simulate-time", json={}, headers=headers)

    assert response.status_code == 422


def test_debug_time_requires_authentication(debug_api_client: TestClient) -> None:
    response = debug_api_client.get("/dev/simulate-time")

    assert response.status_code == 401


def test_simulating_eight_days_expires_and_finalises_the_appeal_window(
    test_data: TestData,
    appeal_window_case: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Acceptance: +8 days warns, expires and finalises an open appeal window.

    APH 1.11a: the institution gets one seven-day appeal window. Running the
    demo clock forward must show the closing warnings, the expiry alert to the
    Regulation Bureau and Regional Officer, and the final rejection status -
    all driven by the same scheduler scan.
    """
    regulation = test_data.users["regulation"]
    monkeypatch.setattr(
        workflow_jobs,
        "_system_actor",
        lambda db: db.get(User, regulation.id),
    )
    settings = Settings(
        debug=True,
        environment="test",
        notifications_enabled=False,
    )
    with TestClient(create_app(settings)) as client:
        headers = auth_headers(
            client, test_data.users["super"], test_data.password
        )
        response = client.get("/dev/simulate-time?days=8", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["offset_days"] == 8

    with SessionLocal() as db:
        application = db.get(Application, appeal_window_case)
        assert application is not None
        assert application.status == ApplicationStatus.FINAL_LOR
        assert application.data["final_outcome"] == "LOR"
        assert application.data["appeal_window_closed"]

        timer = db.scalar(
            select(Timer).where(Timer.application_id == appeal_window_case)
        )
        assert timer is not None
        assert timer.status == TimerStatus.BREACHED

        alert_types = dict(
            db.execute(
                select(Alert.type, func.count())
                .where(Alert.application_id == appeal_window_case)
                .group_by(Alert.type)
            ).all()
        )
        expired_recipients = set(
            db.scalars(
                select(Alert.recipient_user_id).where(
                    Alert.application_id == appeal_window_case,
                    Alert.type == "APPEAL_EXPIRED",
                )
            ).all()
        )
        events = set(
            db.scalars(
                select(WorkflowEvent.action).where(
                    WorkflowEvent.application_id == appeal_window_case
                )
            ).all()
        )
        audits = set(
            db.scalars(
                select(AuditLog.action).where(
                    AuditLog.entity_id.in_(
                        (appeal_window_case, timer.id)
                    )
                )
            ).all()
        )

    assert alert_types["APPEAL_WINDOW_CLOSING"] == 2
    assert alert_types["APPEAL_EXPIRED"] >= 2
    assert test_data.users["regulation"].id in expired_recipients
    assert test_data.users["regional"].id in expired_recipients
    assert len(expired_recipients) == alert_types["APPEAL_EXPIRED"]
    assert "timer_expire" in events
    assert "finalize_no_appeal" in events
    assert "timer.expire" in audits
    assert "workflow.finalize_no_appeal" in audits

