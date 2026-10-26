"""Application-type routing, fee flow, DSC, Deficiency Report and shell tests."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from tests.support import (
    COMPLETE_APPLICATION_DATA,
    TestData,
    auth_headers,
    create_draft,
    pay_application_fee,
    upload_mandatory_documents,
)


def _headers(
    client: TestClient,
    test_data: TestData,
    key: str = "institution_admin_west",
) -> dict[str, str]:
    return auth_headers(client, test_data.users[key], test_data.password)


def _complete_draft(
    client: TestClient,
    headers: dict[str, str],
    tracked: list[uuid.UUID],
    *,
    application_type: str = "EOA_SELF_DISCLOSURE",
) -> dict[str, Any]:
    """Create a filled draft with every mandatory document DSC-signed."""
    created = create_draft(
        client,
        headers,
        tracked,
        application_type=application_type,
    )
    application_id = created["id"]
    update = client.patch(
        f"/applications/{application_id}",
        json={"data": COMPLETE_APPLICATION_DATA},
        headers=headers,
    )
    assert update.status_code == 200, update.text
    upload_mandatory_documents(client, headers, application_id)
    return created


def test_type_routes_expose_steps_documents_and_ter(
    api_client: TestClient,
    test_data: TestData,
) -> None:
    headers = _headers(api_client, test_data)
    response = api_client.get(
        "/applications/type-routes?academic_year=2026-27",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    routes = {route["type"]: route for route in response.json()}

    eoa = routes["EOA_SELF_DISCLOSURE"]
    assert eoa["cutoff_applies"] is True
    steps = {step["key"]: step for step in eoa["steps"]}
    assert steps["SELF_DISCLOSURE"]["applies"] is True
    assert steps["SCRUTINY"]["applies"] is False
    assert steps["EVC"]["applies"] is False
    assert steps["SHC_SAC"]["applies"] is False
    document_codes = {document["doc_code"] for document in eoa["required_documents"]}
    assert "AFFIDAVIT_2" in document_codes
    assert eoa["ter_unit"] == "PER_DIVISION"
    assert eoa["ter_unit_amount_paise"] == 2_000_000

    new_institution = routes["NEW_INSTITUTION"]
    assert new_institution["cutoff_applies"] is True
    assert new_institution["ter_unit_amount_paise"] == 100_000_000


def test_submit_is_blocked_until_ter_is_paid(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    headers = _headers(api_client, test_data)
    created = _complete_draft(api_client, headers, workspace_applications)
    application_id = created["id"]

    quote = api_client.get(f"/applications/{application_id}/fee", headers=headers)
    assert quote.status_code == 200, quote.text
    quote_body = quote.json()
    assert quote_body["total_paise"] > 0
    assert quote_body["is_paid"] is False
    assert quote_body["due_paise"] == quote_body["total_paise"]
    assert quote_body["payment_required_for_submission"] is True
    assert all(line["apH_clause"] for line in quote_body["lines"])

    blocked = api_client.post(f"/applications/{application_id}/submit", headers=headers)
    assert blocked.status_code == 409, blocked.text
    detail = blocked.json()["detail"]
    assert "TER payment is required" in detail["message"]
    assert detail["due_paise"] == quote_body["total_paise"]

    paid = pay_application_fee(api_client, headers, application_id)
    assert paid["quote"]["is_paid"] is True
    assert paid["quote"]["due_paise"] == 0
    assert paid["transactions"]

    submitted = api_client.post(f"/applications/{application_id}/submit", headers=headers)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["application"]["portal_application_no"].startswith("AICTE/")


def test_refund_is_recorded_without_reducing_paid_ter(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    headers = _headers(api_client, test_data)
    created = _complete_draft(api_client, headers, workspace_applications)
    application_id = created["id"]
    paid = pay_application_fee(api_client, headers, application_id)
    total_paid = paid["quote"]["total_paise"]

    refund = api_client.post(
        f"/applications/{application_id}/fee/refund",
        json={"reason": "SCRUTINY_REJECTED_NO_APPEAL"},
        headers=headers,
    )
    assert refund.status_code == 200, refund.text
    body = refund.json()
    assert body["retained_paise"] == 6_000_000
    assert body["refundable_paise"] == max(0, total_paid - 6_000_000)
    assert body["transaction"]["kind"] == "REFUND"

    quote = api_client.get(f"/applications/{application_id}/fee", headers=headers)
    assert quote.status_code == 200, quote.text
    assert quote.json()["paid_paise"] == total_paid
    assert quote.json()["refunded_paise"] == body["refundable_paise"]


def test_regulation_bureau_can_reopen_only_once(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    admin_headers = _headers(api_client, test_data)
    regulation_headers = _headers(api_client, test_data, "regulation")
    created = _complete_draft(api_client, admin_headers, workspace_applications)
    application_id = created["id"]
    pay_application_fee(api_client, admin_headers, application_id)
    submitted = api_client.post(
        f"/applications/{application_id}/submit", headers=admin_headers
    )
    assert submitted.status_code == 200, submitted.text

    blocked = api_client.post(
        f"/applications/{application_id}/reopen",
        json={"reason": "Institution filed under the wrong trust resolution."},
        headers=admin_headers,
    )
    assert blocked.status_code == 403

    reopened = api_client.post(
        f"/applications/{application_id}/reopen",
        json={
            "reason": "Institution filed under the wrong trust resolution.",
            "trust_resolution_reference": "FORMAT-3-DEMO",
        },
        headers=regulation_headers,
    )
    assert reopened.status_code == 200, reopened.text
    reopened_body = reopened.json()
    assert reopened_body["status"] == "DRAFT"
    assert reopened_body["reopen_count"] == 1
    assert reopened_body["transactions"]

    second = api_client.post(
        f"/applications/{application_id}/reopen",
        json={"reason": "Trying to reopen the same application again."},
        headers=regulation_headers,
    )
    assert second.status_code == 409


def test_unsigned_upload_is_rejected_and_blocks_submit(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    headers = _headers(api_client, test_data)
    created = _complete_draft(api_client, headers, workspace_applications)
    application_id = created["id"]

    upload = api_client.post(
        f"/applications/{application_id}/documents",
        data={"doc_type": "AFFILIATION_CERTIFICATE", "signed_with_dsc": "false"},
        files={
            "file": (
                "affiliation-unsigned.pdf",
                b"%PDF-1.4\nAffiliation certificate fictional institution\n",
                "application/pdf",
            )
        },
        headers=headers,
    )
    assert upload.status_code == 201, upload.text
    upload_body = upload.json()
    assert upload_body["signed_with_dsc"] is False
    assert upload_body["verification_status"] == "REJECTED"

    checklist = api_client.get(
        f"/applications/{application_id}/documents/checklist", headers=headers
    )
    assert checklist.status_code == 200, checklist.text
    affiliation = next(
        item
        for item in checklist.json()["documents"]
        if item["doc_type"] == "AFFILIATION_CERTIFICATE"
    )
    assert affiliation["signed_with_dsc"] is False

    pay_application_fee(api_client, headers, application_id)
    blocked = api_client.post(f"/applications/{application_id}/submit", headers=headers)
    assert blocked.status_code == 422, blocked.text
    assert any(
        item["code"] == "document.AFFILIATION_CERTIFICATE.dsc"
        for item in blocked.json()["detail"]["missing"]
    )


def test_deficiency_report_lists_items_with_clauses(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    headers = _headers(api_client, test_data)
    created = _complete_draft(api_client, headers, workspace_applications)
    application_id = created["id"]

    before = api_client.get(
        f"/applications/{application_id}/deficiency-report", headers=headers
    )
    assert before.status_code == 200, before.text
    before_body = before.json()
    assert before_body["apH_clause"] == "APH 2.3.3b"
    assert isinstance(before_body["nil_deficiency"], bool)
    for item in before_body["items"]:
        assert item["apH_clause"]
        assert item["status"] in {"FAIL", "NOT_ASSESSED"}

    pay_application_fee(api_client, headers, application_id)
    submitted = api_client.post(f"/applications/{application_id}/submit", headers=headers)
    assert submitted.status_code == 200, submitted.text

    after = api_client.get(
        f"/applications/{application_id}/deficiency-report?include_not_assessed=false",
        headers=headers,
    )
    assert after.status_code == 200, after.text
    assert after.json()["include_not_assessed"] is False
    assert all(item["status"] == "FAIL" for item in after.json()["items"])


def test_generated_document_shells_are_downloadable(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    headers = _headers(api_client, test_data)
    created = _complete_draft(api_client, headers, workspace_applications)
    application_id = created["id"]

    listing = api_client.get(
        f"/applications/{application_id}/document-shells", headers=headers
    )
    assert listing.status_code == 200, listing.text
    assert "AFFIDAVIT_2" in listing.json()

    affidavit = api_client.get(
        f"/applications/{application_id}/document-shells/AFFIDAVIT_2",
        headers=headers,
    )
    assert affidavit.status_code == 200, affidavit.text
    assert affidavit.headers["content-type"].startswith("text/html")
    assert "FICTIONAL DEMO" in affidavit.text
    assert "33 declarations" not in affidavit.text
    assert affidavit.text.count("<li>") >= 33

    unknown = api_client.get(
        f"/applications/{application_id}/document-shells/NOT_A_SHELL",
        headers=headers,
    )
    assert unknown.status_code == 404
