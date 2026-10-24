"""DEBUG-only simulated time endpoint tests."""

from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import Settings
from app.db.session import SessionLocal
from app.main import create_app
from app.models.alert import Alert
from app.models.application import Application
from app.models.audit import AuditLog
from app.models.workflow import WorkflowEvent
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
