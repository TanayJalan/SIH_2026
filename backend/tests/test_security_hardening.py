"""Security-control regression tests: throttling, headers, CORS and validation."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from app.core.config import Settings
from app.db.session import SessionLocal
from app.main import create_app
from app.models.audit import AuditLog
from tests.support import TestData, auth_headers


def _login(client: TestClient, email: str, password: str):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_login_is_rate_limited_after_repeated_failures(api_client: TestClient) -> None:
    email = f"rate.limit.{uuid.uuid4().hex[:8]}@example.edu"
    for _ in range(5):
        response = _login(api_client, email, "wrong-password")
        assert response.status_code == 401

    blocked = _login(api_client, email, "wrong-password")
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0
    assert "Too many failed sign-in attempts" in blocked.json()["detail"]

    with SessionLocal() as db:
        entry = db.scalars(
            select(AuditLog).where(AuditLog.action == "auth.rate_limited").order_by(
                AuditLog.created_at.desc()
            )
        ).first()
    assert entry is not None
    assert entry.entity_type == "Auth"
    assert entry.after is not None
    assert entry.after["email"] == email
    assert entry.after["retry_after_seconds"] > 0


def test_successful_login_clears_failed_attempts(
    api_client: TestClient, test_data: TestData
) -> None:
    user = test_data.users["institution_admin_west"]
    try:
        assert _login(api_client, user.email, "wrong-password").status_code == 401
        assert _login(api_client, user.email, "wrong-password").status_code == 401
        assert _login(api_client, user.email, test_data.password).status_code == 200

        # The successful login reset the window, so another run of four
        # failures must not be blocked yet.
        for _ in range(4):
            assert _login(api_client, user.email, "wrong-password").status_code == 401
    finally:
        api_client.app.state.login_rate_limiter.clear()


def test_security_headers_are_attached(api_client: TestClient) -> None:
    response = api_client.get("/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert "Strict-Transport-Security" not in response.headers


def test_auth_responses_are_not_cached(
    api_client: TestClient, test_data: TestData
) -> None:
    user = test_data.users["institution_admin_west"]
    response = _login(api_client, user.email, test_data.password)
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"


def test_hsts_is_emitted_for_production_https() -> None:
    settings = Settings(
        environment="production",
        secret_key="a-production-secret-that-is-long-enough",
        cors_origins="https://approvals.example.edu",
        demo_mode=False,
        debug=False,
        compliance_monitor_enabled=False,
        alert_scan_enabled=False,
        notifications_enabled=False,
    )
    with TestClient(create_app(settings)) as client:
        response = client.get("/health", headers={"X-Forwarded-Proto": "https"})

    assert response.headers["Strict-Transport-Security"].startswith("max-age=31536000")


def test_cors_allows_only_configured_origins(api_client: TestClient) -> None:
    allowed = api_client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert allowed.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"

    rejected = api_client.get("/health", headers={"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in rejected.headers


def test_cors_configuration_rejects_wildcards_and_localhost_in_production() -> None:
    with pytest.raises(ValidationError, match="explicit origins"):
        Settings(cors_origins="*")

    with pytest.raises(ValidationError, match="local development hosts"):
        Settings(
            environment="production",
            secret_key="a-production-secret-that-is-long-enough",
            cors_origins="http://localhost:5173",
            demo_mode=False,
        )

    with pytest.raises(ValidationError, match="DEBUG must be false"):
        Settings(
            environment="production",
            secret_key="a-production-secret-that-is-long-enough",
            cors_origins="https://approvals.example.edu",
            demo_mode=False,
            debug=True,
        )


def test_oversized_and_malformed_inputs_are_rejected(
    api_client: TestClient, test_data: TestData
) -> None:
    headers = auth_headers(
        api_client, test_data.users["institution_admin_west"], test_data.password
    )

    oversized_page = api_client.get("/applications?page_size=101", headers=headers)
    assert oversized_page.status_code == 422

    long_password = _login(
        api_client,
        f"long.password.{uuid.uuid4().hex[:8]}@example.edu",
        "x" * 129,
    )
    assert long_password.status_code == 422

    malformed = api_client.post(
        "/applications",
        content=b"not-json",
        headers={**headers, "Content-Type": "application/json"},
    )
    assert malformed.status_code == 422
