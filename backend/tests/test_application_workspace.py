"""Institution-side draft, programme, document and submission tests."""

import uuid
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import (
    Application,
    ApplicationStatus,
    SLAConfig,
    WorkflowEvent,
    WorkflowStage,
)
from tests.support import (
    COMPLETE_APPLICATION_DATA as COMPLETE_DATA,
)
from tests.support import (
    TestData,
    auth_headers,
)
from tests.support import (
    create_draft as _create_draft,
)
from tests.support import (
    pay_application_fee as _pay_application_fee,
)
from tests.support import (
    upload_mandatory_documents as _upload_mandatory_documents,
)


def _headers(
    client: TestClient,
    test_data: TestData,
    key: str = "institution_admin_west",
) -> dict[str, str]:
    return auth_headers(client, test_data.users[key], test_data.password)


def test_create_and_update_draft_preserves_reference(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    headers = _headers(api_client, test_data)
    created = _create_draft(api_client, headers, workspace_applications)

    assert created["status"] == "DRAFT"
    assert created["reference"].startswith("APP-2026-")
    reference = created["reference"]

    sections = {
        "institution_profile": {
            "head_name": "Dr Demo Registrar",
            "address_line1": "1 Fictional Campus Road",
            "city": "Pune",
            "state": "Maharashtra",
            "pin_code": "411001",
            "contact_email": "registrar@example.edu",
            "contact_phone": "+91 98765 43210",
        }
    }
    response = api_client.patch(
        f"/applications/{created['id']}",
        json={"data": sections},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["reference"] == reference
    assert body["data"]["institution_profile"]["head_name"] == "Dr Demo Registrar"
    assert body["data"]["institution_profile"]["pin_code"] == "411001"

    checklist = api_client.get(
        f"/applications/{created['id']}/checklist",
        headers=headers,
    )
    assert checklist.status_code == 200
    checklist_body = checklist.json()
    assert checklist_body["can_submit"] is False
    assert checklist_body["percentage"] < 100
    profile_section = next(
        section
        for section in checklist_body["sections"]
        if section["key"] == "institution_profile"
    )
    assert profile_section["complete"] is True
    assert any(
        item["code"] == "document.AFFILIATION_CERTIFICATE"
        for item in checklist_body["missing"]
    )


def test_create_rejects_out_of_scope_application_type(
    api_client: TestClient,
    test_data: TestData,
) -> None:
    response = api_client.post(
        "/applications",
        json={
            "application_type": "NOT_AN_APH_TYPE",
            "academic_year": "2026-27",
        },
        headers=_headers(api_client, test_data),
    )

    assert response.status_code == 422
    assert "not configured" in response.text


def test_draft_writes_are_limited_to_the_owning_institution_admin(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    west_headers = _headers(api_client, test_data)
    east_headers = _headers(api_client, test_data, "institution_admin_east")
    scrutiny_headers = _headers(api_client, test_data, "scrutiny")
    created = _create_draft(api_client, west_headers, workspace_applications)

    cross_tenant = api_client.patch(
        f"/applications/{created['id']}",
        json={"data": {"mandatory_disclosure_url": "https://example.edu/disclosure"}},
        headers=east_headers,
    )
    officer = api_client.patch(
        f"/applications/{created['id']}",
        json={"data": {"mandatory_disclosure_url": "https://example.edu/disclosure"}},
        headers=scrutiny_headers,
    )
    officer_create = api_client.post(
        "/applications",
        json={"application_type": "NEW_INSTITUTION", "academic_year": "2026-27"},
        headers=scrutiny_headers,
    )

    assert cross_tenant.status_code == 403
    assert officer.status_code == 403
    assert officer_create.status_code == 403


def test_program_crud(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    headers = _headers(api_client, test_data)
    created = _create_draft(api_client, headers, workspace_applications)
    application_id = created["id"]

    added = api_client.post(
        f"/applications/{application_id}/programs",
        json={
            "program_name": "B.Tech Computer Science",
            "level": "UG",
            "intake": 120,
            "faculty_count": 18,
            "lab_count": 4,
        },
        headers=headers,
    )
    assert added.status_code == 201, added.text
    program = added.json()
    assert program["program_name"] == "B.Tech Computer Science"

    listing = api_client.get(f"/applications/{application_id}/programs", headers=headers)
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [program["id"]]

    updated = api_client.patch(
        f"/applications/{application_id}/programs/{program['id']}",
        json={"intake": 180, "faculty_count": 24},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["intake"] == 180
    assert updated.json()["faculty_count"] == 24

    detail = api_client.get(f"/applications/{application_id}", headers=headers)
    assert detail.status_code == 200
    assert [item["intake"] for item in detail.json()["programs"]] == [180]

    deleted = api_client.delete(
        f"/applications/{application_id}/programs/{program['id']}",
        headers=headers,
    )
    assert deleted.status_code == 204
    assert api_client.get(
        f"/applications/{application_id}/programs", headers=headers
    ).json() == []


def test_document_upload_validation_versioning_and_download(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    headers = _headers(api_client, test_data)
    other_headers = _headers(api_client, test_data, "institution_admin_east")
    created = _create_draft(api_client, headers, workspace_applications)
    application_id = created["id"]

    first = api_client.post(
        f"/applications/{application_id}/documents",
        data={"doc_type": "AFFILIATION_CERTIFICATE", "signed_with_dsc": "true"},
        files={"file": ("affiliation.pdf", b"%PDF-1.4\nfirst version\n", "application/pdf")},
        headers=headers,
    )
    assert first.status_code == 201, first.text
    first_body = first.json()
    assert first_body["version"] == 1
    assert first_body["content_type"] == "application/pdf"
    assert first_body["size_bytes"] > 0

    second = api_client.post(
        f"/applications/{application_id}/documents",
        data={"doc_type": "AFFILIATION_CERTIFICATE", "signed_with_dsc": "true"},
        files={"file": ("affiliation-v2.pdf", b"%PDF-1.4\nsecond version\n", "application/pdf")},
        headers=headers,
    )
    assert second.status_code == 201, second.text
    assert second.json()["version"] == 2

    document_list = api_client.get(
        f"/applications/{application_id}/documents", headers=headers
    )
    assert document_list.status_code == 200
    versions = [item["version"] for item in document_list.json()]
    assert versions == [2, 1]

    checklist = api_client.get(
        f"/applications/{application_id}/documents/checklist", headers=headers
    )
    assert checklist.status_code == 200
    affiliation = next(
        item
        for item in checklist.json()["documents"]
        if item["doc_type"] == "AFFILIATION_CERTIFICATE"
    )
    assert affiliation["uploaded"] is True
    assert affiliation["version"] == 2

    download = api_client.get(first_body["download_url"], headers=headers)
    assert download.status_code == 200
    assert download.content.startswith(b"%PDF-1.4")
    assert download.headers["content-type"].startswith("application/pdf")

    cross_tenant = api_client.get(first_body["download_url"], headers=other_headers)
    assert cross_tenant.status_code == 403

    unsupported = api_client.post(
        f"/applications/{application_id}/documents",
        data={"doc_type": "AFFILIATION_CERTIFICATE", "signed_with_dsc": "true"},
        files={"file": ("notes.txt", b"plain text", "text/plain")},
        headers=headers,
    )
    assert unsupported.status_code == 415

    oversized = api_client.post(
        f"/applications/{application_id}/documents",
        data={"doc_type": "AFFILIATION_CERTIFICATE", "signed_with_dsc": "true"},
        files={"file": ("large.pdf", b"%PDF-" + b"0" * (10 * 1024 * 1024), "application/pdf")},
        headers=headers,
    )
    assert oversized.status_code == 413

    unknown_type = api_client.post(
        f"/applications/{application_id}/documents",
        data={"doc_type": "NOT_A_REQUIRED_DOCUMENT"},
        files={"file": ("unknown.pdf", b"%PDF-1.4\nunknown\n", "application/pdf")},
        headers=headers,
    )
    assert unknown_type.status_code == 422


def test_document_upload_records_automated_verification(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    headers = _headers(api_client, test_data)
    created = _create_draft(api_client, headers, workspace_applications)
    application_id = created["id"]

    verified = api_client.post(
        f"/applications/{application_id}/documents",
        data={"doc_type": "AFFILIATION_CERTIFICATE", "signed_with_dsc": "true"},
        files={
            "file": (
                "affiliation_certificate.pdf",
                b"%PDF-1.4\nAffiliation certificate for a fictional institution\n",
                "application/pdf",
            )
        },
        headers=headers,
    )
    assert verified.status_code == 201, verified.text
    verified_body = verified.json()
    assert verified_body["verification_status"] == "VERIFIED"
    assert "affiliation" in verified_body["verification_reason"].lower()

    flagged = api_client.post(
        f"/applications/{application_id}/documents",
        data={"doc_type": "AFFILIATION_CERTIFICATE", "signed_with_dsc": "true"},
        files={
            "file": (
                "scan.pdf",
                b"%PDF-1.4\nunrelated fictional notes\n",
                "application/pdf",
            )
        },
        headers=headers,
    )
    assert flagged.status_code == 201, flagged.text
    flagged_body = flagged.json()
    assert flagged_body["version"] == 2
    assert flagged_body["verification_status"] == "FLAGGED"
    assert "affiliation" in flagged_body["verification_reason"].lower()

    checklist = api_client.get(
        f"/applications/{application_id}/documents/checklist", headers=headers
    )
    affiliation = next(
        document
        for document in checklist.json()["documents"]
        if document["doc_type"] == "AFFILIATION_CERTIFICATE"
    )
    assert affiliation["verification_status"] == "FLAGGED"
    assert "replace" in affiliation["verification_reason"].lower()


def test_submission_is_blocked_with_readable_missing_items(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    headers = _headers(api_client, test_data)
    created = _create_draft(api_client, headers, workspace_applications)
    application_id = created["id"]

    response = api_client.post(f"/applications/{application_id}/submit", headers=headers)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["message"].startswith("Application cannot be submitted yet")
    assert detail["percentage"] == 0
    assert any(
        item["code"] == "institution_profile.head_name" for item in detail["missing"]
    )
    assert any(
        item["code"] == "document.AFFILIATION_CERTIFICATE" for item in detail["missing"]
    )

    detail_response = api_client.get(f"/applications/{application_id}", headers=headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["status"] == "DRAFT"
    assert detail_response.json()["sla_due_at"] is None


def test_complete_application_submits_with_sla_and_workflow_event(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    headers = _headers(api_client, test_data)
    created = _create_draft(api_client, headers, workspace_applications)
    application_id = created["id"]

    update = api_client.patch(
        f"/applications/{application_id}",
        json={"data": COMPLETE_DATA},
        headers=headers,
    )
    assert update.status_code == 200, update.text
    _upload_mandatory_documents(api_client, headers, application_id)
    _pay_application_fee(api_client, headers, application_id)

    checklist = api_client.get(f"/applications/{application_id}/checklist", headers=headers)
    assert checklist.status_code == 200, checklist.text
    assert checklist.json()["percentage"] == 100
    assert checklist.json()["can_submit"] is True
    assert checklist.json()["missing"] == []

    submitted = api_client.post(f"/applications/{application_id}/submit", headers=headers)
    assert submitted.status_code == 200, submitted.text
    body = submitted.json()
    assert body["application"]["status"] == "SUBMITTED"
    assert body["application"]["assigned_officer_id"] == str(
        test_data.users["scrutiny"].id
    )
    assert body["submitted_at"]
    assert body["sla_due_at"]
    assert body["application"]["reference"] == created["reference"]

    with SessionLocal() as db:
        application = db.get(Application, uuid.UUID(application_id))
        assert application is not None
        assert application.status == ApplicationStatus.SUBMITTED
        assert application.assigned_officer_id == test_data.users["scrutiny"].id
        assert application.submitted_at is not None
        assert application.stage_entered_at is not None
        assert application.sla_due_at is not None
        sla = db.scalar(
            select(SLAConfig).where(SLAConfig.stage == WorkflowStage.APPLICATION)
        )
        assert sla is not None
        assert application.sla_due_at == application.stage_entered_at + timedelta(
            days=sla.duration_days
        )
        events = db.scalars(
            select(WorkflowEvent)
            .where(WorkflowEvent.application_id == application.id)
            .order_by(WorkflowEvent.created_at.asc())
        ).all()
        assert [event.to_status for event in events] == [
            ApplicationStatus.SUBMITTED,
        ]
        assert [event.action for event in events] == ["submit"]

    duplicate = api_client.post(f"/applications/{application_id}/submit", headers=headers)
    assert duplicate.status_code == 409

    edit_after_submit = api_client.patch(
        f"/applications/{application_id}",
        json={"data": COMPLETE_DATA},
        headers=headers,
    )
    assert edit_after_submit.status_code == 409


def test_delete_draft(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    headers = _headers(api_client, test_data)
    created = _create_draft(api_client, headers, workspace_applications)
    application_id = created["id"]

    deleted = api_client.delete(f"/applications/{application_id}", headers=headers)

    assert deleted.status_code == 204
    missing = api_client.get(f"/applications/{application_id}", headers=headers)
    assert missing.status_code == 404


def test_academic_year_must_span_consecutive_years(
    api_client: TestClient,
    test_data: TestData,
) -> None:
    headers = _headers(api_client, test_data)

    response = api_client.post(
        "/applications",
        json={"application_type": "NEW_INSTITUTION", "academic_year": "2026-29"},
        headers=headers,
    )

    assert response.status_code == 422
