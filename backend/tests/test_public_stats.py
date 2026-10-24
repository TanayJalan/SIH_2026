"""Public login statistics and demo-mode exposure tests."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.main import create_app
from app.models.enums import Role
from tests.support import TestData


def test_public_stats_reports_seeded_pipeline_figures(
    api_client: TestClient,
    test_data: TestData,
) -> None:
    response = api_client.get("/public/stats")

    assert response.status_code == 200
    body = response.json()
    assert body["applications_in_progress"] >= 2
    assert body["institutions_needing_attention"] >= 1
    assert body["average_days_to_decision"] is None or body["average_days_to_decision"] >= 0
    assert body["as_of"]
    assert isinstance(body["demo_mode"], bool)


def test_demo_accounts_are_one_per_role_when_demo_mode_is_enabled() -> None:
    settings = get_settings().model_copy(update={"demo_mode": True, "environment": "test"})
    with TestClient(create_app(settings)) as client:
        response = client.get("/public/stats")

    body = response.json()
    assert body["demo_mode"] is True
    assert {account["role"] for account in body["demo_accounts"]} == {role.value for role in Role}
    assert len(body["demo_accounts"]) == len(Role)
    assert all(account["email"] and account["password"] for account in body["demo_accounts"])


def test_demo_accounts_are_hidden_when_demo_mode_is_disabled() -> None:
    settings = get_settings().model_copy(update={"demo_mode": False, "environment": "test"})
    with TestClient(create_app(settings)) as client:
        response = client.get("/public/stats")

    body = response.json()
    assert body["demo_mode"] is False
    assert body["demo_accounts"] == []


def test_demo_mode_is_rejected_in_production() -> None:
    with pytest.raises(ValidationError, match="DEMO_MODE must be false in production"):
        Settings(
            environment="production",
            demo_mode=True,
            secret_key="a-production-secret",
        )
