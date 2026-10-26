"""Rule-driven alert, escalation, API and demo-time tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.core.clock import SimulatedClock
from app.core.config import Settings
from app.db.session import SessionLocal
from app.main import create_app
from app.models.alert import Alert, AlertRule, AlertTriggerCatalogue
from app.models.application import Application
from app.models.audit import AuditLog
from app.models.deadline import DeadlineRule, Timer
from app.models.deficiency import Deficiency
from app.models.document import Document
from app.models.enums import (
    AlertChannel,
    AlertStatus,
    ApplicationStatus,
    ApplicationType,
    DeficiencyStatus,
    InspectionStatus,
    Severity,
    TimerStatus,
    WorkflowStage,
)
from app.models.inspection import Inspection
from app.models.user import User
from app.models.workflow import WorkflowEvent
from app.services.alert_engine import (
    SEVERITY_RAISED,
    AlertEngine,
    EmailProvider,
    NotificationService,
    render_template,
)
from app.services.alert_triggers import rules_for_handler
from tests.support import TestData, TestUser, auth_headers


@pytest.fixture(autouse=True)
def cleanup_alert_test_data() -> None:
    """Remove scans and alert artifacts created by this module after each test.

    The scan is system-wide, so it can also touch the session-scoped overdue
    application used by other suites. Snapshotting the relevant tables keeps
    this module's alerts, escalation events and audits from skewing later
    recipient-scoped assertions.
    """
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
            "apps": set(
                db.scalars(
                    select(Application.id).where(
                        Application.data["reference"].astext.like("TEST-ALERT-%")
                    )
                ).all()
            ),
        }

    yield

    with SessionLocal() as db:
        new_alerts = set(db.scalars(select(Alert.id)).all()) - before["alerts"]
        new_events = set(db.scalars(select(WorkflowEvent.id)).all()) - before["events"]
        new_audits = set(db.scalars(select(AuditLog.id)).all()) - before["audits"]
        app_ids = set(
            db.scalars(
                select(Application.id).where(
                    Application.data["reference"].astext.like("TEST-ALERT-%")
                )
            ).all()
        ) - before["apps"]

        if new_audits:
            db.execute(delete(AuditLog).where(AuditLog.id.in_(new_audits)))
        if new_alerts:
            db.execute(delete(Alert).where(Alert.id.in_(new_alerts)))
        if new_events:
            db.execute(
                delete(WorkflowEvent).where(WorkflowEvent.id.in_(new_events))
            )
        if app_ids:
            db.execute(delete(Inspection).where(Inspection.application_id.in_(app_ids)))
            db.execute(
                delete(Deficiency).where(Deficiency.application_id.in_(app_ids))
            )
            db.execute(delete(Document).where(Document.application_id.in_(app_ids)))
            db.execute(delete(Application).where(Application.id.in_(app_ids)))

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


def _make_application(
    db,
    test_data: TestData,
    *,
    due_days: int,
    status: ApplicationStatus = ApplicationStatus.SCRUTINY,
    stage: WorkflowStage = WorkflowStage.SCRUTINY,
    officer: TestUser | None = None,
) -> Application:
    now = datetime.now(UTC)
    application = Application(
        institution_id=test_data.institutions["west"],
        application_type=ApplicationType.NEW_INSTITUTION,
        academic_year="2026-27",
        status=status,
        current_stage=stage,
        assigned_officer_id=(officer or test_data.users["scrutiny"]).id,
        submitted_at=now,
        stage_entered_at=now,
        sla_due_at=now + timedelta(days=due_days),
        data={"reference": f"TEST-ALERT-{uuid.uuid4().hex[:8]}", "demo": True},
    )
    db.add(application)
    db.flush()
    return application


def _offline_settings() -> Settings:
    return Settings(
        environment="test",
        notifications_enabled=False,
        alert_scan_enabled=False,
    )


def _scan(db, clock: SimulatedClock):
    engine = AlertEngine(db, clock, settings=_offline_settings())
    result = engine.scan()
    db.commit()
    return result


def test_deadline_scan_is_idempotent_and_uses_one_threshold_window(
    test_data: TestData,
) -> None:
    clock = SimulatedClock()
    with SessionLocal() as db:
        application = _make_application(db, test_data, due_days=6)
        db.commit()

        first = _scan(db, clock)
        first_count = db.scalar(
            select(func.count())
            .select_from(Alert)
            .where(
                Alert.application_id == application.id,
                Alert.type == "DEADLINE_APPROACHING",
            )
        )
        _scan(db, clock)
        second_count = db.scalar(
            select(func.count())
            .select_from(Alert)
            .where(
                Alert.application_id == application.id,
                Alert.type == "DEADLINE_APPROACHING",
            )
        )
        alert = db.scalar(
            select(Alert).where(
                Alert.application_id == application.id,
                Alert.type == "DEADLINE_APPROACHING",
            )
        )

    assert first.alerts_created >= 1
    assert first_count == 1
    assert second_count == 1
    assert alert is not None
    assert "T-7" in alert.title
    assert alert.channel == AlertChannel.IN_APP
    assert alert.dedupe_key is not None


def test_periodic_scans_create_each_trigger_once(test_data: TestData) -> None:
    clock = SimulatedClock()
    now = clock.now()
    with SessionLocal() as db:
        application = _make_application(db, test_data, due_days=2)
        db.add_all(
            [
                Deficiency(
                    application_id=application.id,
                    category="Faculty",
                    description="Missing faculty declaration for the demo case.",
                    raised_by=test_data.users["scrutiny"].id,
                    status=DeficiencyStatus.OPEN,
                    due_date=(now + timedelta(days=2)).date(),
                ),
                Deficiency(
                    application_id=application.id,
                    category="Finance",
                    description="Outstanding financial statement clarification.",
                    raised_by=test_data.users["scrutiny"].id,
                    status=DeficiencyStatus.OPEN,
                    due_date=(now - timedelta(days=1)).date(),
                ),
                Document(
                    application_id=application.id,
                    doc_type="AFFILIATION_CERTIFICATE",
                    filename="fictional-affiliation.pdf",
                    storage_path="/tmp/fictional-affiliation.pdf",
                    uploaded_by=test_data.users["institution_admin_west"].id,
                    expiry_date=(now + timedelta(days=20)).date(),
                ),
                Inspection(
                    application_id=application.id,
                    committee_id=test_data.users["inspection"].id,
                    scheduled_on=now + timedelta(days=5),
                    status=InspectionStatus.SCHEDULED,
                ),
            ]
        )
        db.commit()
        application_id = application.id

        first = _scan(db, clock)
        rows = db.execute(
            select(Alert.type, func.count())
            .where(Alert.application_id == application_id)
            .group_by(Alert.type)
        ).all()
        counts = dict(rows)
        _scan(db, clock)
        rows_again = db.execute(
            select(Alert.type, func.count())
            .where(Alert.application_id == application_id)
            .group_by(Alert.type)
        ).all()
        counts_again = dict(rows_again)
        dedupe_rows = db.scalars(
            select(Alert.dedupe_key).where(Alert.application_id == application_id)
        ).all()

    assert first.alerts_created >= 4
    assert counts["DEADLINE_APPROACHING"] == 1
    assert counts["DEFICIENCY_DUE"] == 1
    assert counts["DEFICIENCY_OVERDUE"] == 1
    assert counts["DOCUMENT_EXPIRING"] == 1
    assert counts["INSPECTION_SCHEDULED"] == 1
    assert counts_again == counts
    assert len(dedupe_rows) == len(set(dedupe_rows))


def test_appeal_and_deposit_timers_warn_the_institution(
    test_data: TestData,
) -> None:
    """The statutory clocks use their own triggers and reach the applicant.

    The appeal window (APH 1.11a) and the Security Deposit clock (APH 2.25f)
    are ``Timer`` rows started by the decision letter, not the stage SLA, so
    they must not be reported as a deadline-approaching alert.
    """
    clock = SimulatedClock()
    now = clock.now()
    with SessionLocal() as db:
        application = _make_application(
            db,
            test_data,
            due_days=10,
            status=ApplicationStatus.APPEAL_WINDOW,
            stage=WorkflowStage.DECISION,
        )
        appeal_rule = db.scalar(
            select(DeadlineRule).where(DeadlineRule.code == "APPEAL_WINDOW")
        )
        deposit_rule = db.scalar(
            select(DeadlineRule).where(DeadlineRule.code == "SECURITY_DEPOSIT")
        )
        assert appeal_rule is not None
        assert deposit_rule is not None
        db.add_all(
            [
                Timer(
                    application_id=application.id,
                    deadline_rule_id=appeal_rule.id,
                    started_at=now,
                    due_at=now + timedelta(days=2),
                    status=TimerStatus.PENDING,
                ),
                Timer(
                    application_id=application.id,
                    deadline_rule_id=deposit_rule.id,
                    started_at=now,
                    due_at=now + timedelta(days=5),
                    status=TimerStatus.PENDING,
                ),
            ]
        )
        db.commit()
        application_id = application.id

        first = _scan(db, clock)
        counts = dict(
            db.execute(
                select(Alert.type, func.count())
                .where(Alert.application_id == application_id)
                .group_by(Alert.type)
            ).all()
        )
        _scan(db, clock)
        counts_again = dict(
            db.execute(
                select(Alert.type, func.count())
                .where(Alert.application_id == application_id)
                .group_by(Alert.type)
            ).all()
        )
        appeal_alert = db.scalar(
            select(Alert).where(
                Alert.application_id == application_id,
                Alert.type == "APPEAL_WINDOW_CLOSING",
            )
        )
        deposit_alert = db.scalar(
            select(Alert).where(
                Alert.application_id == application_id,
                Alert.type == "DEPOSIT_DUE",
            )
        )

    assert first.alerts_created >= 2
    assert counts["APPEAL_WINDOW_CLOSING"] == 1
    assert counts["DEPOSIT_DUE"] == 1
    assert "DEADLINE_APPROACHING" not in counts
    assert counts_again == counts
    assert appeal_alert is not None
    assert deposit_alert is not None
    assert appeal_alert.title.startswith("Appeal window closing")
    assert "7 day" in deposit_alert.message or "Security Deposit" in deposit_alert.message
    expected_admin = test_data.users["institution_admin_west"].id
    assert appeal_alert.recipient_user_id == expected_admin
    assert deposit_alert.recipient_user_id == expected_admin


def test_escalation_chain_raises_severity_and_records_workflow_events(
    test_data: TestData,
) -> None:
    clock = SimulatedClock()
    now = clock.now()
    with SessionLocal() as db:
        application = _make_application(db, test_data, due_days=30)
        rule = db.scalar(select(AlertRule).where(AlertRule.code == "DEADLINE-3"))
        assert rule is not None
        source = Alert(
            recipient_user_id=test_data.users["scrutiny"].id,
            application_id=application.id,
            rule_id=rule.id,
            type="DEADLINE_APPROACHING",
            severity=Severity.MEDIUM,
            title="Old unacknowledged demo alert",
            message="This fictional alert is older than the escalation window.",
            channel=AlertChannel.IN_APP,
            status=AlertStatus.SENT,
            sent_at=now - timedelta(days=20),
            dedupe_key=f"manual:{uuid.uuid4().hex}",
            created_at=now - timedelta(days=20),
            updated_at=now - timedelta(days=20),
        )
        db.add(source)
        db.commit()
        application_id = application.id
        source_id = source.id

        first = _scan(db, clock)
        level_one = db.scalar(
            select(Alert).where(
                Alert.application_id == application_id,
                Alert.escalation_level == 1,
            )
        )
        db.refresh(application)
        first_events = db.scalar(
            select(func.count())
            .select_from(WorkflowEvent)
            .where(
                WorkflowEvent.application_id == application_id,
                WorkflowEvent.action == "escalate",
            )
        )

        assert first.escalations >= 1
        assert level_one is not None
        assert level_one.recipient_user_id == test_data.users["regional"].id
        assert level_one.severity == Severity.HIGH
        assert level_one.parent_alert_id == source_id
        assert application.is_escalated is True
        assert first_events == 1

        level_one.created_at = now - timedelta(days=20)
        level_one.updated_at = now - timedelta(days=20)
        db.commit()

        second = _scan(db, clock)
        level_twos = db.scalars(
            select(Alert).where(
                Alert.application_id == application_id,
                Alert.escalation_level == 2,
            )
        ).all()
        second_events = db.scalar(
            select(func.count())
            .select_from(WorkflowEvent)
            .where(
                WorkflowEvent.application_id == application_id,
                WorkflowEvent.action == "escalate",
            )
        )

    assert second.escalations >= 1
    assert level_twos
    assert any(
        alert.recipient_user_id == test_data.users["super"].id
        for alert in level_twos
    )
    assert any(alert.severity == Severity.CRITICAL for alert in level_twos)
    assert second_events == 2
    assert SEVERITY_RAISED[Severity.MEDIUM] == Severity.HIGH
    assert SEVERITY_RAISED[Severity.HIGH] == Severity.CRITICAL


def test_acknowledging_the_escalation_stops_the_next_chain_step(
    test_data: TestData,
) -> None:
    """An acknowledged level-one alert must not escalate to the super admin.

    The in-app row is the acknowledgement record. Outbound EMAIL/SMS rows can
    share the same escalation level but are delivery receipts, so they must not
    keep the chain alive.
    """
    from app.services.alert_engine import acknowledge_alert

    clock = SimulatedClock()
    now = clock.now()
    with SessionLocal() as db:
        application = _make_application(db, test_data, due_days=30)
        rule = db.scalar(select(AlertRule).where(AlertRule.code == "DEADLINE-3"))
        assert rule is not None
        source = Alert(
            recipient_user_id=test_data.users["scrutiny"].id,
            application_id=application.id,
            rule_id=rule.id,
            type="DEADLINE_APPROACHING",
            severity=Severity.MEDIUM,
            title="Old unacknowledged demo alert",
            message="This fictional alert is older than the escalation window.",
            channel=AlertChannel.IN_APP,
            status=AlertStatus.SENT,
            sent_at=now - timedelta(days=20),
            dedupe_key=f"manual:{uuid.uuid4().hex}",
            created_at=now - timedelta(days=20),
            updated_at=now - timedelta(days=20),
        )
        db.add(source)
        db.commit()

        _scan(db, clock)
        level_one = db.scalar(
            select(Alert).where(
                Alert.application_id == application.id,
                Alert.escalation_level == 1,
                Alert.channel == AlertChannel.IN_APP,
            )
        )
        assert level_one is not None

        # A delivery receipt from the same escalation must not count as the
        # escalations acknowledgement record.
        db.add(
            Alert(
                recipient_user_id=test_data.users["regional"].id,
                application_id=application.id,
                rule_id=rule.id,
                parent_alert_id=source.id,
                type="ESCALATION",
                severity=Severity.HIGH,
                title="Fictional escalation email",
                message="Fictional delivery receipt.",
                channel=AlertChannel.EMAIL,
                status=AlertStatus.SENT,
                escalation_level=1,
                dedupe_key=f"manual-email:{uuid.uuid4().hex}",
                created_at=now - timedelta(days=20),
                updated_at=now - timedelta(days=20),
            )
        )
        acknowledge_alert(
            db,
            level_one,
            db.get(User, test_data.users["regional"].id),
            now=now,
        )
        level_one.created_at = now - timedelta(days=20)
        db.commit()

        _scan(db, clock)
        level_two_count = db.scalar(
            select(func.count())
            .select_from(Alert)
            .where(
                Alert.application_id == application.id,
                Alert.escalation_level == 2,
            )
        )
        escalation_events = db.scalar(
            select(func.count())
            .select_from(WorkflowEvent)
            .where(
                WorkflowEvent.application_id == application.id,
                WorkflowEvent.action == "escalate",
            )
        )

    assert level_two_count == 0
    assert escalation_events == 1


def test_workflow_notifier_creates_status_and_inspection_alerts_once(
    test_data: TestData,
) -> None:
    from app.services.alert_engine import notify_workflow_event

    clock = SimulatedClock()
    notifications = NotificationService.from_settings(_offline_settings())
    with SessionLocal() as db:
        application = _make_application(db, test_data, due_days=10)
        actor = db.get(User, test_data.users["super"].id)
        submit_event = WorkflowEvent(
            application_id=application.id,
            from_status=ApplicationStatus.DRAFT,
            to_status=ApplicationStatus.SUBMITTED,
            actor_id=actor.id,
            action="submit",
            comment="Fictional submission",
            details={},
            apH_clause="APH 1.4.3",
            created_at=clock.now(),
        )
        inspection = Inspection(
            application_id=application.id,
            committee_id=test_data.users["inspection"].id,
            scheduled_on=clock.now() + timedelta(days=5),
            status=InspectionStatus.SCHEDULED,
        )
        db.add_all([submit_event, inspection])
        db.commit()
        inspection_event = WorkflowEvent(
            application_id=application.id,
            from_status=ApplicationStatus.SCRUTINY,
            to_status=ApplicationStatus.EVC_CONSTITUTED,
            actor_id=actor.id,
            action="constitute_evc",
            comment="Fictional inspection",
            details={"inspection_id": str(inspection.id)},
            apH_clause="APH 1.8a",
            created_at=clock.now(),
        )
        db.add(inspection_event)
        db.commit()

        notify_workflow_event(db, submit_event, application, actor, notifications, clock)
        notify_workflow_event(db, submit_event, application, actor, notifications, clock)
        status_count = db.scalar(
            select(func.count())
            .select_from(Alert)
            .where(
                Alert.application_id == application.id,
                Alert.type == "APPLICATION_STATUS_CHANGED",
            )
        )
        status_alert = db.scalar(
            select(Alert).where(
                Alert.application_id == application.id,
                Alert.type == "APPLICATION_STATUS_CHANGED",
            )
        )

        notify_workflow_event(db, inspection_event, application, actor, notifications, clock)
        inspection_count = db.scalar(
            select(func.count())
            .select_from(Alert)
            .where(
                Alert.application_id == application.id,
                Alert.type == "INSPECTION_SCHEDULED",
            )
        )
        inspection_alert = db.scalar(
            select(Alert).where(
                Alert.application_id == application.id,
                Alert.type == "INSPECTION_SCHEDULED",
            )
        )

    assert status_count == 1
    assert status_alert is not None
    assert status_alert.recipient_user_id == test_data.users["scrutiny"].id
    assert inspection_count == 1
    assert inspection_alert is not None
    assert inspection_alert.recipient_user_id == test_data.users["inspection"].id


def test_template_rendering_and_email_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    assert (
        render_template("Hello {institution} {unknown}", {"institution": "Fictional"})
        == "Hello Fictional {unknown}"
    )

    sent: list[object] = []

    class FakeSMTP:
        def __init__(self, host: str, port: int, timeout: float) -> None:
            assert host == "mailpit"
            assert port == 1025
            assert timeout > 0

        def __enter__(self) -> FakeSMTP:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def send_message(self, message: object) -> None:
            sent.append(message)

    monkeypatch.setattr("app.services.alert_engine.smtplib.SMTP", FakeSMTP)
    provider = EmailProvider(host="mailpit", port=1025, sender="no-reply@aicte.local")
    alert = Alert(
        recipient_user_id=uuid.uuid4(),
        type="TEST",
        severity=Severity.LOW,
        title="Fictional email subject",
        message="Fictional email body",
        channel=AlertChannel.EMAIL,
        status=AlertStatus.PENDING,
    )
    recipient = SimpleNamespace(email="recipient@example.edu")

    assert provider.deliver(alert, recipient) is True
    assert len(sent) == 1


def test_alert_api_filters_summary_and_acknowledgement(
    api_client: TestClient,
    test_data: TestData,
) -> None:
    super_user = test_data.users["institution_admin_east"]
    west_admin = test_data.users["institution_admin_west"]
    with SessionLocal() as db:
        pending = Alert(
            recipient_user_id=super_user.id,
            application_id=test_data.applications["west"],
            type="DEADLINE_APPROACHING",
            severity=Severity.HIGH,
            title="Fictional pending alert",
            message="Fictional pending message",
            channel=AlertChannel.IN_APP,
            status=AlertStatus.PENDING,
        )
        acknowledged = Alert(
            recipient_user_id=super_user.id,
            application_id=None,
            type="STATUS_CHANGED",
            severity=Severity.LOW,
            title="Fictional acknowledged alert",
            message="Fictional acknowledged message",
            channel=AlertChannel.IN_APP,
            status=AlertStatus.ACKED,
        )
        email_copy = Alert(
            recipient_user_id=super_user.id,
            application_id=test_data.applications["west"],
            type="SLA_BREACHED",
            severity=Severity.CRITICAL,
            title="Fictional email delivery row",
            message="Fictional email message",
            channel=AlertChannel.EMAIL,
            status=AlertStatus.SENT,
        )
        db.add_all([pending, acknowledged, email_copy])
        db.commit()
        pending_id = str(pending.id)
        alert_ids = [pending.id, acknowledged.id, email_copy.id]

    try:
        headers = auth_headers(api_client, super_user, test_data.password)
        west_headers = auth_headers(api_client, west_admin, test_data.password)

        listing = api_client.get("/alerts", headers=headers)
        assert listing.status_code == 200
        if listing.json()["total"] != 2:
            print("DEBUG ALERTS", listing.json())
        assert listing.json()["total"] == 2

        high = api_client.get("/alerts", params={"severity": "HIGH"}, headers=headers)
        assert high.json()["total"] == 1
        assert high.json()["items"][0]["id"] == pending_id

        acked = api_client.get("/alerts", params={"status": "ACKED"}, headers=headers)
        assert acked.json()["total"] == 1
        assert acked.json()["items"][0]["title"] == "Fictional acknowledged alert"

        summary = api_client.get("/alerts/summary", headers=headers)
        assert summary.status_code == 200
        assert summary.json()["total"] == 2
        assert summary.json()["unread"] == 1
        assert summary.json()["acknowledged"] == 1

        forbidden = api_client.post(f"/alerts/{pending_id}/ack", headers=west_headers)
        assert forbidden.status_code == 404

        ack = api_client.post(f"/alerts/{pending_id}/ack", headers=headers)
        assert ack.status_code == 200
        assert ack.json()["status"] == "ACKED"
        assert ack.json()["acknowledged_at"] is not None

        again = api_client.post(f"/alerts/{pending_id}/ack", headers=headers)
        assert again.status_code == 200
        assert again.json()["status"] == "ACKED"
    finally:
        with SessionLocal() as db:
            db.execute(delete(Alert).where(Alert.id.in_(alert_ids)))
            db.commit()


def test_alert_rule_admin_crud_and_role_guard(
    api_client: TestClient,
    test_data: TestData,
) -> None:
    suffix = uuid.uuid4().hex[:8].upper()
    code = f"TEST-RULE-{suffix}"
    days_before = 80 + (uuid.uuid4().int % 100)
    payload = {
        "code": code,
        "name": "Fictional test alert rule",
        "description": "Created by the alert engine test suite.",
        "trigger_type": "DOCUMENT_EXPIRING",
        "days_before": days_before,
        "severity": "MEDIUM",
        "channel_list": ["IN_APP", "EMAIL"],
        "template": "Fictional {institution} expires on {due_date}.",
        "escalation_role": "REGIONAL_OFFICER",
        "is_active": True,
    }
    super_headers = auth_headers(api_client, test_data.users["super"], test_data.password)
    regional_headers = auth_headers(
        api_client, test_data.users["regional"], test_data.password
    )
    rule_id: str | None = None
    try:
        forbidden = api_client.post("/alert-rules", json=payload, headers=regional_headers)
        assert forbidden.status_code == 403

        created = api_client.post("/alert-rules", json=payload, headers=super_headers)
        assert created.status_code == 201, created.text
        rule_id = created.json()["id"]
        assert created.json()["code"] == code

        duplicate = api_client.post("/alert-rules", json=payload, headers=super_headers)
        assert duplicate.status_code == 409

        updated = api_client.patch(
            f"/alert-rules/{rule_id}",
            json={"severity": "HIGH", "name": "Updated fictional rule"},
            headers=super_headers,
        )
        assert updated.status_code == 200
        assert updated.json()["severity"] == "HIGH"
        assert updated.json()["name"] == "Updated fictional rule"

        listing = api_client.get("/alert-rules", headers=super_headers)
        assert listing.status_code == 200
        assert any(item["id"] == rule_id for item in listing.json()["items"])

        deleted = api_client.delete(f"/alert-rules/{rule_id}", headers=super_headers)
        assert deleted.status_code == 204
        missing = api_client.get(f"/alert-rules/{rule_id}", headers=super_headers)
        assert missing.status_code == 404
        rule_id = None
    finally:
        if rule_id is not None:
            with SessionLocal() as db:
                rule = db.get(AlertRule, uuid.UUID(rule_id))
                if rule is not None:
                    db.delete(rule)
                    db.commit()


def test_debug_time_replays_deadline_breach_and_escalation(
    test_data: TestData,
) -> None:
    before = {}
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
        application = _make_application(db, test_data, due_days=7)
        db.commit()
        application_id = application.id

    settings = Settings(
        environment="test",
        debug=True,
        notifications_enabled=False,
        alert_scan_enabled=False,
    )
    try:
        with TestClient(create_app(settings)) as client:
            headers = auth_headers(client, test_data.users["super"], test_data.password)
            response = client.get(
                "/dev/simulate-time",
                params={"days": 8},
                headers=headers,
            )
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["offset_days"] == 8
            assert body["scan"] is not None
            assert body["scan"]["alerts_created"] >= 4
            assert body["scan"]["escalations"] >= 1

        with SessionLocal() as db:
            application = db.get(Application, application_id)
            assert application is not None
            assert application.is_escalated is True
            types = db.execute(
                select(Alert.type, func.count())
                .where(Alert.application_id == application_id)
                .group_by(Alert.type)
            ).all()
            counts = dict(types)
            escalations = db.scalars(
                select(Alert)
                .where(Alert.application_id == application_id)
                .order_by(Alert.escalation_level)
            ).all()
            events = db.scalar(
                select(func.count())
                .select_from(WorkflowEvent)
                .where(
                    WorkflowEvent.application_id == application_id,
                    WorkflowEvent.action == "escalate",
                )
            )

        assert counts["DEADLINE_APPROACHING"] == 3
        assert counts["SLA_BREACHED"] == 1
        assert counts["ESCALATION"] >= 1
        assert any(alert.escalation_level == 1 for alert in escalations)
        assert events >= 1
    finally:
        with SessionLocal() as db:
            new_alert_ids = set(db.scalars(select(Alert.id)).all()) - before["alerts"]
            new_event_ids = (
                set(db.scalars(select(WorkflowEvent.id)).all()) - before["events"]
            )
            new_audit_ids = set(db.scalars(select(AuditLog.id)).all()) - before["audits"]
            if new_alert_ids:
                db.execute(delete(Alert).where(Alert.id.in_(new_alert_ids)))
            if new_event_ids:
                db.execute(delete(WorkflowEvent).where(WorkflowEvent.id.in_(new_event_ids)))
            if new_audit_ids:
                db.execute(delete(AuditLog).where(AuditLog.id.in_(new_audit_ids)))
            now_escalated = set(
                db.scalars(
                    select(Application.id).where(Application.is_escalated.is_(True))
                ).all()
            )
            for escalated_id in now_escalated - before["escalated"]:
                application = db.get(Application, escalated_id)
                if application is not None:
                    application.is_escalated = False
            db.commit()


def test_existing_alert_rules_resolve_through_trigger_catalogue() -> None:
    """Every seeded trigger code keeps a handler and at least one rule."""
    expected = {
        "DEADLINE_APPROACHING",
        "SLA_BREACHED",
        "DEFICIENCY_DUE",
        "DEFICIENCY_OVERDUE",
        "DOCUMENT_EXPIRING",
        "COMPLIANCE_RED",
        "APPLICATION_STATUS_CHANGED",
        "INSPECTION_SCHEDULED",
        "APPEAL_WINDOW_CLOSING",
        "DEPOSIT_DUE",
    }
    with SessionLocal() as db:
        catalogue = {
            row.code: row
            for row in db.scalars(select(AlertTriggerCatalogue)).all()
        }
        assert expected <= set(catalogue)
        for code in expected:
            assert catalogue[code].handler_key == code
            assert rules_for_handler(db, code), f"no active rule for {code}"


def test_new_catalogue_trigger_can_back_a_rule_without_migration(
    api_client: TestClient,
    test_data: TestData,
) -> None:
    """A data-only trigger code can drive an existing engine handler."""
    suffix = uuid.uuid4().hex[:8].upper()
    trigger_code = f"TEST-TRIGGER-{suffix}"
    rule_code = f"TEST-CATALOGUE-RULE-{suffix}"
    payload = {
        "code": rule_code,
        "name": "Fictional catalogue-driven rule",
        "description": "Created by the alert engine test suite.",
        "trigger_type": trigger_code,
        "days_before": 0,
        "severity": "LOW",
        "channel_list": ["IN_APP"],
        "template": "Fictional catalogue trigger for {institution}.",
        "escalation_role": "REGIONAL_OFFICER",
        "is_active": True,
    }
    headers = auth_headers(api_client, test_data.users["super"], test_data.password)
    try:
        with SessionLocal() as db:
            db.add(
                AlertTriggerCatalogue(
                    code=trigger_code,
                    handler_key="APPLICATION_STATUS_CHANGED",
                    description="Test-only trigger.",
                    apH_clause="APH 1.4.3",
                )
            )
            db.commit()

        created = api_client.post("/alert-rules", json=payload, headers=headers)
        assert created.status_code == 201, created.text
        assert created.json()["trigger_type"] == trigger_code

        with SessionLocal() as db:
            rules = rules_for_handler(db, "APPLICATION_STATUS_CHANGED")
            assert any(rule.code == rule_code for rule in rules)
    finally:
        with SessionLocal() as db:
            db.execute(delete(AlertRule).where(AlertRule.code == rule_code))
            db.execute(
                delete(AlertTriggerCatalogue).where(
                    AlertTriggerCatalogue.code == trigger_code
                )
            )
            db.commit()


def test_unknown_alert_trigger_is_rejected(
    api_client: TestClient,
    test_data: TestData,
) -> None:
    """Creating or editing a rule with an uncatalogued trigger returns 422."""
    suffix = uuid.uuid4().hex[:8].upper()
    rule_code = f"TEST-UNKNOWN-TRIGGER-{suffix}"
    headers = auth_headers(api_client, test_data.users["super"], test_data.password)
    payload = {
        "code": rule_code,
        "name": "Fictional unknown trigger rule",
        "description": "Created by the alert engine test suite.",
        "trigger_type": "NOT_A_REAL_TRIGGER",
        "days_before": 0,
        "severity": "LOW",
        "channel_list": ["IN_APP"],
        "template": "Fictional unknown trigger for {institution}.",
        "escalation_role": "REGIONAL_OFFICER",
        "is_active": True,
    }
    try:
        rejected = api_client.post("/alert-rules", json=payload, headers=headers)
        assert rejected.status_code == 422
        assert "alert_trigger_catalogue" in rejected.json()["detail"]

        payload["trigger_type"] = "DOCUMENT_EXPIRING"
        created = api_client.post("/alert-rules", json=payload, headers=headers)
        assert created.status_code == 201, created.text
        rule_id = created.json()["id"]

        updated = api_client.patch(
            f"/alert-rules/{rule_id}",
            json={"trigger_type": "NOT_A_REAL_TRIGGER"},
            headers=headers,
        )
        assert updated.status_code == 422
    finally:
        with SessionLocal() as db:
            db.execute(delete(AlertRule).where(AlertRule.code == rule_code))
            db.commit()
