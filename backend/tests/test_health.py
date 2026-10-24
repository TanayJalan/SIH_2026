"""Smoke tests for the application factory and health endpoints."""

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_db
from app.main import create_app


def test_health_returns_service_metadata() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "AICTE Approval Workflow"
    assert response.json()["version"] == "0.1.0"


def test_request_id_is_echoed() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health", headers={"X-Request-ID": "test-request-id"})

    assert response.headers["X-Request-ID"] == "test-request-id"


def test_readiness_returns_503_when_database_is_unavailable() -> None:
    app = create_app()

    def unavailable_db() -> Generator[object, None, None]:
        class BrokenSession:
            def execute(self, *_: object, **__: object) -> None:
                raise SQLAlchemyError("database unavailable")

        yield BrokenSession()

    app.dependency_overrides[get_db] = unavailable_db
    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
