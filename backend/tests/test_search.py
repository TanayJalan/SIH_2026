"""Role-scoped global search tests."""

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.models import Application, Institution
from tests.support import TestData, auth_headers


def _institution_name(institution_id: object) -> str:
    with SessionLocal() as db:
        institution = db.get(Institution, institution_id)
        assert institution is not None
        return institution.name


def _application_reference(application_id: object) -> str:
    with SessionLocal() as db:
        application = db.get(Application, application_id)
        assert application is not None
        assert application.reference is not None
        return application.reference


def test_institution_admin_search_is_role_scoped(
    api_client: TestClient, test_data: TestData
) -> None:
    user = test_data.users["institution_admin_west"]
    headers = auth_headers(api_client, user, test_data.password)
    west_name = _institution_name(test_data.institutions["west"])

    response = api_client.get("/search", params={"q": west_name}, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["applications"]] == [
        str(test_data.applications["west"])
    ]
    assert [item["id"] for item in body["institutions"]] == [
        str(test_data.institutions["west"])
    ]

    pages_response = api_client.get("/search", params={"q": ""}, headers=headers)
    assert pages_response.status_code == 200
    page_paths = {item["path"] for item in pages_response.json()["pages"]}
    assert {"/", "/applications", "/alerts", "/profile"} <= page_paths
    assert "/audit-logs" not in page_paths


def test_search_finds_application_by_reference(api_client: TestClient, test_data: TestData) -> None:
    user = test_data.users["super"]
    headers = auth_headers(api_client, user, test_data.password)
    reference = _application_reference(test_data.applications["east"])

    response = api_client.get("/search", params={"q": reference}, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert [item["reference"] for item in body["applications"]] == [reference]
    assert body["applications"][0]["institution_name"]

    pages_response = api_client.get("/search", params={"q": ""}, headers=headers)
    page_paths = {item["path"] for item in pages_response.json()["pages"]}
    assert "/audit-logs" in page_paths
    assert "/alert-rules" in page_paths


def test_search_finds_application_by_id(api_client: TestClient, test_data: TestData) -> None:
    user = test_data.users["super"]
    headers = auth_headers(api_client, user, test_data.password)
    application_id = test_data.applications["east"]

    response = api_client.get(
        "/search",
        params={"q": str(application_id).split("-")[0]},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["applications"]] == [str(application_id)]


def test_search_does_not_leak_cross_tenant_records(
    api_client: TestClient, test_data: TestData
) -> None:
    user = test_data.users["institution_admin_west"]
    headers = auth_headers(api_client, user, test_data.password)
    east_name = _institution_name(test_data.institutions["east"])

    response = api_client.get("/search", params={"q": east_name}, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["applications"] == []
    assert body["institutions"] == []


def test_blank_search_returns_pages_only(api_client: TestClient, test_data: TestData) -> None:
    user = test_data.users["regional"]
    headers = auth_headers(api_client, user, test_data.password)

    response = api_client.get("/search", params={"q": "   "}, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["applications"] == []
    assert body["institutions"] == []
    assert body["pages"]


def test_search_requires_authentication(api_client: TestClient) -> None:
    response = api_client.get("/search", params={"q": "anything"})

    assert response.status_code == 401
