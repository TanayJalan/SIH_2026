"""Recipient-scoped alert inbox tests."""

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db.session import SessionLocal
from app.models.alert import Alert
from app.models.enums import AlertChannel, AlertStatus, Severity
from tests.support import TestData, auth_headers


def test_alerts_are_recipient_scoped_and_support_unread_filter(
    api_client: TestClient, test_data: TestData
) -> None:
    super_user = test_data.users["super"]
    west_admin = test_data.users["institution_admin_west"]

    with SessionLocal() as db:
        super_pending = Alert(
            recipient_user_id=super_user.id,
            application_id=test_data.applications["west"],
            type="sla.overdue",
            severity=Severity.HIGH,
            title="Illustrative SLA breach",
            message="Fictional application is past its illustrative SLA.",
            channel=AlertChannel.IN_APP,
            status=AlertStatus.PENDING,
        )
        super_read = Alert(
            recipient_user_id=super_user.id,
            application_id=None,
            type="workflow.notice",
            severity=Severity.LOW,
            title="Illustrative workflow notice",
            message="Fictional notice already acknowledged by the recipient.",
            channel=AlertChannel.IN_APP,
            status=AlertStatus.READ,
        )
        west_pending = Alert(
            recipient_user_id=west_admin.id,
            application_id=test_data.applications["west"],
            type="inspection.scheduled",
            severity=Severity.MEDIUM,
            title="Illustrative inspection notice",
            message="Fictional notice addressed to the institution administrator.",
            channel=AlertChannel.IN_APP,
            status=AlertStatus.PENDING,
        )
        db.add_all([super_pending, super_read, west_pending])
        db.commit()
        alert_ids = [super_pending.id, super_read.id, west_pending.id]
        super_pending_id = str(super_pending.id)

    try:
        super_headers = auth_headers(api_client, super_user, test_data.password)
        west_headers = auth_headers(api_client, west_admin, test_data.password)

        super_response = api_client.get("/alerts", headers=super_headers)
        unread_response = api_client.get(
            "/alerts", params={"unread": "true"}, headers=super_headers
        )
        west_response = api_client.get("/alerts", headers=west_headers)

        assert super_response.status_code == 200
        assert super_response.json()["total"] == 2
        assert unread_response.status_code == 200
        assert unread_response.json()["total"] == 1
        assert [item["id"] for item in unread_response.json()["items"]] == [super_pending_id]
        assert west_response.status_code == 200
        assert west_response.json()["total"] == 1
        assert west_response.json()["items"][0]["title"] == "Illustrative inspection notice"
    finally:
        with SessionLocal() as db:
            db.execute(delete(Alert).where(Alert.id.in_(alert_ids)))
            db.commit()


def test_alerts_require_authentication(api_client: TestClient) -> None:
    response = api_client.get("/alerts")

    assert response.status_code == 401
