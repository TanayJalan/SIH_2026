"""Shared helpers and data containers for API tests."""

import uuid
from dataclasses import dataclass
from typing import Any, ClassVar

from fastapi.testclient import TestClient

from app.models.enums import ApplicationType, Role

COMPLETE_APPLICATION_DATA: dict[str, Any] = {
    "institution_profile": {
        "head_name": "Dr Demo Registrar",
        "address_line1": "1 Fictional Campus Road",
        "address_line2": "Demo Nagar",
        "city": "Pune",
        "state": "Maharashtra",
        "pin_code": "411001",
        "contact_email": "registrar@example.edu",
        "contact_phone": "+91 98765 43210",
        "website": "https://example.edu",
    },
    "infrastructure": {
        "land_area": 12000,
        "built_up_area": 8500,
        "labs": 18,
        "library": 24000,
        "hostel": 300,
    },
    "faculty": {
        "total": 120,
        "professors": 15,
        "associate_professors": 35,
        "assistant_professors": 70,
        "student_faculty_ratio": 18.5,
        "phd_faculty_ratio": 42,
    },
    "finance": {
        "tuition_fee": 150000,
        "development_fee": 25000,
        "other_fees": 10000,
        "balance": 1250000,
    },
    "accreditation": {
        "naac_grade": "A",
        "nba_status": "ACCREDITED",
        "last_validated_on": "2025-06-30",
    },
    "mandatory_disclosure_url": "https://example.edu/mandatory-disclosure",
}


@dataclass(frozen=True, slots=True)
class TestUser:
    __test__: ClassVar[bool] = False

    id: uuid.UUID
    email: str
    role: Role
    region: str | None
    institution_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class TestData:
    __test__: ClassVar[bool] = False

    password: str
    users: dict[str, TestUser]
    institutions: dict[str, uuid.UUID]
    applications: dict[str, uuid.UUID]
    inspection_id: uuid.UUID


def login(client: TestClient, email: str, password: str) -> dict[str, Any]:
    """Log in through the API and return the decoded JSON response."""
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def auth_headers(client: TestClient, user: TestUser, password: str) -> dict[str, str]:
    """Return an Authorization header for ``user``."""
    body = login(client, user.email, password)
    return {"Authorization": f"Bearer {body['access_token']}"}


def create_draft(
    client: TestClient,
    headers: dict[str, str],
    tracked: list[uuid.UUID],
    *,
    application_type: ApplicationType = ApplicationType.NEW,
) -> dict[str, Any]:
    """Create an institution draft and register it for fixture cleanup."""
    response = client.post(
        "/applications",
        json={"application_type": application_type.value, "academic_year": "2026-27"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    tracked.append(uuid.UUID(body["id"]))
    return body


def upload_mandatory_documents(
    client: TestClient,
    headers: dict[str, str],
    application_id: str,
) -> None:
    """Upload one fictional PDF for every mandatory document rule."""
    checklist = client.get(
        f"/applications/{application_id}/documents/checklist",
        headers=headers,
    )
    assert checklist.status_code == 200, checklist.text
    for document in checklist.json()["documents"]:
        if not document["mandatory"]:
            continue
        upload = client.post(
            f"/applications/{application_id}/documents",
            data={"doc_type": document["doc_type"]},
            files={
                "file": (
                    f"{document['doc_type'].lower()}.pdf",
                    b"%PDF-1.4\nfictional demo document\n",
                    "application/pdf",
                )
            },
            headers=headers,
        )
        assert upload.status_code == 201, upload.text
