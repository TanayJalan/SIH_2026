"""Role and tenant scoping tests for application read endpoints."""

from fastapi.testclient import TestClient

from tests.support import TestData, auth_headers


def test_institution_admin_sees_only_own_institution(
    api_client: TestClient, test_data: TestData
) -> None:
    admin = test_data.users["institution_admin_west"]
    headers = auth_headers(api_client, admin, test_data.password)

    response = api_client.get("/applications", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["id"] for item in body["items"]] == [str(test_data.applications["west"])]
    assert body["items"][0]["institution"]["id"] == str(test_data.institutions["west"])


def test_cross_institution_application_access_returns_403(
    api_client: TestClient, test_data: TestData
) -> None:
    west_admin = test_data.users["institution_admin_west"]
    east_admin = test_data.users["institution_admin_east"]
    west_headers = auth_headers(api_client, west_admin, test_data.password)
    east_headers = auth_headers(api_client, east_admin, test_data.password)

    west_app = test_data.applications["west"]
    east_app = test_data.applications["east"]

    own = api_client.get(f"/applications/{west_app}", headers=west_headers)
    cross_tenant = api_client.get(f"/applications/{east_app}", headers=west_headers)
    reverse = api_client.get(f"/applications/{west_app}", headers=east_headers)

    assert own.status_code == 200
    assert cross_tenant.status_code == 403
    assert cross_tenant.json()["detail"] == "You do not have access to this application"
    assert reverse.status_code == 403


def test_regional_head_is_scoped_to_region(api_client: TestClient, test_data: TestData) -> None:
    regional = test_data.users["regional"]
    headers = auth_headers(api_client, regional, test_data.password)

    own_region = api_client.get(f"/applications/{test_data.applications['west']}", headers=headers)
    other_region = api_client.get(
        f"/applications/{test_data.applications['east']}", headers=headers
    )
    listing = api_client.get("/applications", headers=headers)

    assert own_region.status_code == 200
    assert other_region.status_code == 403
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["institution"]["region"] == regional.region


def test_scrutiny_officer_is_scoped_to_assignment_or_region(
    api_client: TestClient, test_data: TestData
) -> None:
    scrutiny = test_data.users["scrutiny"]
    headers = auth_headers(api_client, scrutiny, test_data.password)

    assigned = api_client.get(f"/applications/{test_data.applications['west']}", headers=headers)
    other_region = api_client.get(
        f"/applications/{test_data.applications['east']}", headers=headers
    )

    assert assigned.status_code == 200
    assert other_region.status_code == 403


def test_inspection_committee_is_scoped_to_assigned_inspections(
    api_client: TestClient, test_data: TestData
) -> None:
    inspection = test_data.users["inspection"]
    headers = auth_headers(api_client, inspection, test_data.password)

    assigned = api_client.get(f"/applications/{test_data.applications['west']}", headers=headers)
    other_region = api_client.get(
        f"/applications/{test_data.applications['east']}", headers=headers
    )
    listing = api_client.get("/applications", headers=headers)

    assert assigned.status_code == 200
    assert other_region.status_code == 403
    assert listing.status_code == 200
    assert listing.json()["total"] == 1


def test_super_admin_sees_all_applications(api_client: TestClient, test_data: TestData) -> None:
    super_admin = test_data.users["super"]
    headers = auth_headers(api_client, super_admin, test_data.password)

    listing = api_client.get("/applications", params={"page_size": 100}, headers=headers)
    other = api_client.get(f"/applications/{test_data.applications['east']}", headers=headers)

    assert listing.status_code == 200
    body = listing.json()
    visible_ids = {item["id"] for item in body["items"]}
    assert {str(app_id) for app_id in test_data.applications.values()} <= visible_ids
    assert body["total"] == len(body["items"])
    assert other.status_code == 200


def test_application_overdue_and_institution_filters(
    api_client: TestClient, test_data: TestData
) -> None:
    super_admin = test_data.users["super"]
    headers = auth_headers(api_client, super_admin, test_data.password)
    west_id = test_data.institutions["west"]
    east_id = test_data.institutions["east"]

    west_overdue = api_client.get(
        "/applications",
        params={"institution_id": str(west_id), "overdue": "true"},
        headers=headers,
    )
    east_overdue = api_client.get(
        "/applications",
        params={"institution_id": str(east_id), "overdue": "true"},
        headers=headers,
    )
    east_all = api_client.get(
        "/applications",
        params={"institution_id": str(east_id)},
        headers=headers,
    )

    assert west_overdue.status_code == 200
    assert [item["id"] for item in west_overdue.json()["items"]] == [
        str(test_data.applications["west"])
    ]
    assert east_overdue.status_code == 200
    assert east_overdue.json()["items"] == []
    assert east_all.status_code == 200
    assert [item["id"] for item in east_all.json()["items"]] == [
        str(test_data.applications["east"])
    ]


def test_institution_admin_cannot_read_audit_logs(
    api_client: TestClient, test_data: TestData
) -> None:
    admin = test_data.users["institution_admin_west"]
    headers = auth_headers(api_client, admin, test_data.password)

    response = api_client.get("/audit-logs", headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "You do not have permission to perform this action"


def test_unknown_application_returns_404(api_client: TestClient, test_data: TestData) -> None:
    super_admin = test_data.users["super"]
    headers = auth_headers(api_client, super_admin, test_data.password)

    response = api_client.get("/applications/00000000-0000-0000-0000-000000000000", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Application not found"


def test_application_endpoints_require_authentication(
    api_client: TestClient, test_data: TestData
) -> None:
    listing = api_client.get("/applications")
    detail = api_client.get(f"/applications/{test_data.applications['west']}")

    assert listing.status_code == 401
    assert detail.status_code == 401
