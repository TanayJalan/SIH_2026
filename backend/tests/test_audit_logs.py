"""Audit log access, scope, filtering and pagination tests."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from tests.support import TestData, auth_headers, login


def test_regional_head_only_sees_audit_entries_from_their_region(
    api_client: TestClient, test_data: TestData
) -> None:
    west_admin = test_data.users["institution_admin_west"]
    east_admin = test_data.users["institution_admin_east"]
    regional = test_data.users["regional"]
    super_admin = test_data.users["super"]

    login(api_client, west_admin.email, test_data.password)
    login(api_client, east_admin.email, test_data.password)
    regional_headers = auth_headers(api_client, regional, test_data.password)
    super_headers = auth_headers(api_client, super_admin, test_data.password)

    west_entries = api_client.get(
        "/audit-logs",
        params={"actor_id": str(west_admin.id), "page_size": 100},
        headers=regional_headers,
    )
    east_entries = api_client.get(
        "/audit-logs",
        params={"actor_id": str(east_admin.id), "page_size": 100},
        headers=regional_headers,
    )
    east_entries_for_super = api_client.get(
        "/audit-logs",
        params={"actor_id": str(east_admin.id), "page_size": 100},
        headers=super_headers,
    )

    assert west_entries.status_code == 200
    assert west_entries.json()["total"] >= 1
    assert all(item["actor_id"] == str(west_admin.id) for item in west_entries.json()["items"])

    assert east_entries.status_code == 200
    assert east_entries.json()["total"] == 0

    assert east_entries_for_super.status_code == 200
    assert east_entries_for_super.json()["total"] >= 1


def test_audit_log_entity_date_and_pagination_filters(
    api_client: TestClient, test_data: TestData
) -> None:
    west_admin = test_data.users["institution_admin_west"]
    regional = test_data.users["regional"]
    login(api_client, west_admin.email, test_data.password)
    headers = auth_headers(api_client, regional, test_data.password)

    entity_filter = api_client.get(
        "/audit-logs",
        params={
            "entity_type": "User",
            "entity_id": str(west_admin.id),
            "page_size": 100,
        },
        headers=headers,
    )
    assert entity_filter.status_code == 200
    assert entity_filter.json()["total"] >= 1
    assert all(
        item["entity_type"] == "User" and item["entity_id"] == str(west_admin.id)
        for item in entity_filter.json()["items"]
    )

    first_page = api_client.get(
        "/audit-logs",
        params={"actor_id": str(west_admin.id), "page": 1, "page_size": 1},
        headers=headers,
    )
    assert first_page.status_code == 200
    assert len(first_page.json()["items"]) == 1
    assert first_page.json()["pages"] >= 1

    today = datetime.now(UTC).date()
    tomorrow = today + timedelta(days=1)
    todays_entries = api_client.get(
        "/audit-logs",
        params={
            "actor_id": str(west_admin.id),
            "start_date": today.isoformat(),
            "end_date": today.isoformat(),
        },
        headers=headers,
    )
    future_entries = api_client.get(
        "/audit-logs",
        params={
            "actor_id": str(west_admin.id),
            "start_date": tomorrow.isoformat(),
        },
        headers=headers,
    )
    assert todays_entries.status_code == 200
    assert todays_entries.json()["total"] >= 1
    assert future_entries.status_code == 200
    assert future_entries.json()["total"] == 0

    invalid_range = api_client.get(
        "/audit-logs",
        params={
            "start_date": tomorrow.isoformat(),
            "end_date": today.isoformat(),
        },
        headers=headers,
    )
    assert invalid_range.status_code == 422
    assert invalid_range.json()["detail"] == "start_date must be on or before end_date"


def test_audit_log_response_includes_actor_and_snapshots(
    api_client: TestClient, test_data: TestData
) -> None:
    west_admin = test_data.users["institution_admin_west"]
    regional = test_data.users["regional"]
    login(api_client, west_admin.email, test_data.password)
    headers = auth_headers(api_client, regional, test_data.password)

    response = api_client.get(
        "/audit-logs",
        params={"actor_id": str(west_admin.id), "page_size": 1},
        headers=headers,
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["actor"]["id"] == str(west_admin.id)
    assert item["actor"]["email"] == west_admin.email
    assert item["action"] == "auth.login"
    assert item["after"]["email"] == west_admin.email
    assert item["ip"] is not None
    assert item["created_at"]


def test_audit_logs_require_authentication(
    api_client: TestClient,
) -> None:
    response = api_client.get("/audit-logs")

    assert response.status_code == 401
