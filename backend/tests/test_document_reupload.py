"""Document rejection, replacement and Re-Scrutiny verification tests.

APH 1.4.3 locks a submitted application, 1.8f communicates deficiencies through
the portal, 1.8g limits Re-Scrutiny to the listed deficiencies and 2.4 gives the
institution a chance to comply. These tests exercise the whole API so the review
policy, the deficiency linkage, the version trail, the guards and the alerts are
covered together.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import (
    Application,
    ApplicationStatus,
    Deficiency,
    Document,
    DocumentVerificationStatus,
    WorkflowEvent,
)
from tests.support import (
    COMPLETE_APPLICATION_DATA,
    TestData,
    auth_headers,
    create_draft,
    pay_application_fee,
    upload_mandatory_documents,
)

FIRE = "FIRE_SAFETY_CERTIFICATE"
NEXT_YEAR = (date.today() + timedelta(days=365)).isoformat()

# A structurally valid one-page PDF with an empty content stream, so the
# readability check has real text-free input to reject.
BLANK_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
    b"/Resources << >> /Contents 4 0 R >>\nendobj\n"
    b"4 0 obj\n<< /Length 0 >>\nstream\n\nendstream\nendobj\n"
    b"xref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n"
    b"0000000058 00000 n \n0000000115 00000 n \n0000000219 00000 n \n"
    b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n268\n%%EOF\n"
)
TEXT_PDF = b"%PDF-1.4\nCertificate of fire safety for the fictional institute\n"


def _detail_text(response: Any) -> str:
    """Return the readable message from a string or structured error detail."""
    detail = response.json().get("detail")
    if isinstance(detail, dict):
        return str(detail.get("message", detail))
    return str(detail)


def _headers(
    client: TestClient,
    test_data: TestData,
    key: str = "institution_admin_west",
) -> dict[str, str]:
    return auth_headers(client, test_data.users[key], test_data.password)


def _act(
    client: TestClient,
    application_id: str,
    action: str,
    headers: dict[str, str],
    **payload: Any,
) -> dict[str, Any]:
    response = client.post(
        f"/applications/{application_id}/actions/{action}",
        headers=headers,
        json=payload or None,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _create_draft_with_data(
    client: TestClient,
    test_data: TestData,
    tracked: list[uuid.UUID],
) -> tuple[str, dict[str, str]]:
    admin = _headers(client, test_data)
    created = create_draft(client, admin, tracked)
    application_id = created["id"]
    update = client.patch(
        f"/applications/{application_id}",
        json={"data": COMPLETE_APPLICATION_DATA},
        headers=admin,
    )
    assert update.status_code == 200, update.text
    upload_mandatory_documents(client, admin, application_id)
    return application_id, admin


def _submitted_in_scrutiny(
    client: TestClient,
    test_data: TestData,
    tracked: list[uuid.UUID],
) -> tuple[str, dict[str, str], dict[str, str]]:
    """Return an application sitting in Scrutiny with every document uploaded."""
    application_id, admin = _create_draft_with_data(client, test_data, tracked)
    pay_application_fee(client, admin, application_id)
    submitted = client.post(f"/applications/{application_id}/submit", headers=admin)
    assert submitted.status_code == 200, submitted.text

    regulation = _headers(client, test_data, "regulation")
    _act(client, application_id, "assign_scrutiny", regulation)
    scrutiny = _headers(client, test_data, "scrutiny")
    return application_id, admin, scrutiny


def _latest_document(
    client: TestClient,
    application_id: str,
    headers: dict[str, str],
    doc_type: str = FIRE,
) -> dict[str, Any]:
    response = client.get(f"/applications/{application_id}/documents", headers=headers)
    assert response.status_code == 200, response.text
    rows = [row for row in response.json() if row["doc_type"] == doc_type]
    assert rows, f"{doc_type} was never uploaded"
    return max(rows, key=lambda row: row["version"])


def _reject(
    client: TestClient,
    application_id: str,
    document_id: str,
    headers: dict[str, str],
    *,
    reason_code: str = "EXPIRED",
    comment: str = "The fire certificate expired on 2025-12-31.",
) -> Any:
    return client.post(
        f"/applications/{application_id}/documents/{document_id}/reject",
        json={"reason_code": reason_code, "comment": comment, "apH_clause": "APH 1.8f"},
        headers=headers,
    )


def _reupload(
    client: TestClient,
    application_id: str,
    document_id: str,
    headers: dict[str, str],
    *,
    data: bytes = TEXT_PDF,
    filename: str = "fire-safety-certificate.pdf",
    signed_with_dsc: bool = True,
    signer_name: str | None = "Dr Demo Registrar",
    valid_until: str | None = NEXT_YEAR,
) -> Any:
    form: dict[str, Any] = {"signed_with_dsc": str(signed_with_dsc).lower()}
    if signer_name is not None:
        form["signer_name"] = signer_name
    if valid_until is not None:
        form["valid_until"] = valid_until
    return client.post(
        f"/applications/{application_id}/documents/{document_id}/reupload",
        data=form,
        files={"file": (filename, data, "application/pdf")},
        headers=headers,
    )


def test_reject_and_reupload_creates_a_version_and_responds_to_the_deficiency(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    """A reviewer rejection opens a deficiency the institution answers by uploading."""
    application_id, admin, scrutiny = _submitted_in_scrutiny(
        api_client, test_data, workspace_applications
    )
    original = _latest_document(api_client, application_id, admin)
    assert original["version"] == 1
    assert original["allowed_actions"] == []

    rejected = _reject(api_client, application_id, original["id"], scrutiny)
    assert rejected.status_code == 200, rejected.text
    body = rejected.json()
    assert body["verification_status"] == "REJECTED"
    assert body["rejection_reason_code"] == "EXPIRED"
    assert body["apH_clause"] == "APH 1.8f"
    assert body["related_deficiency_id"] is not None
    assert body["deficiency_status"] == "OPEN"
    assert body["deficiency_due_date"] is not None

    # Rejecting during Scrutiny communicates the deficiency (APH 1.8f, 2.4).
    timeline = api_client.get(f"/applications/{application_id}/timeline", headers=admin)
    assert timeline.status_code == 200, timeline.text
    assert timeline.json()["status"] == "DEFICIENCY_COMMUNICATED"

    institution_view = _latest_document(api_client, application_id, admin)
    assert institution_view["rejection_reason_code"] == "EXPIRED"
    assert institution_view["rejection_comment"].startswith("The fire certificate expired")
    assert "reupload" in institution_view["allowed_actions"]
    assert institution_view["reupload_count"] == 0
    assert institution_view["max_reuploads"] >= 1

    replaced = _reupload(api_client, application_id, original["id"], admin)
    assert replaced.status_code == 201, replaced.text
    replacement = replaced.json()
    assert replacement["version"] == 2
    assert replacement["verification_status"] == "PENDING"
    assert replacement["signer_name"] == "Dr Demo Registrar"
    assert replacement["valid_until"] == NEXT_YEAR
    assert replacement["related_deficiency_id"] == body["related_deficiency_id"]
    assert replacement["deficiency_status"] == "RESPONDED"
    assert replacement["warnings"] == []

    # The earlier version is superseded but still downloadable (APH 1.4.3).
    history = api_client.get(
        f"/applications/{application_id}/documents/{original['id']}/versions",
        headers=admin,
    )
    assert history.status_code == 200, history.text
    versions = history.json()
    assert [row["version"] for row in versions] == [2, 1]
    assert versions[1]["superseded_by"] == replacement["id"]
    assert versions[1]["is_latest"] is False

    download = api_client.get(
        f"/applications/{application_id}/documents/{original['id']}/download",
        headers=admin,
    )
    assert download.status_code == 200, download.text
    assert download.content.startswith(b"%PDF-1.4")

    deficiencies = api_client.get(
        f"/applications/{application_id}/deficiencies", headers=admin
    )
    assert deficiencies.status_code == 200, deficiencies.text
    linked = [
        item
        for item in deficiencies.json()
        if item["id"] == replacement["related_deficiency_id"]
    ]
    assert linked and linked[0]["status"] == "RESPONDED"

    with SessionLocal() as db:
        application = db.get(Application, uuid.UUID(application_id))
        actions = {
            event.action
            for event in db.scalars(
                select(WorkflowEvent).where(
                    WorkflowEvent.application_id == application.id
                )
            ).all()
        }
    assert {"reject_document", "reupload_document"} <= actions
    assert application is not None


def test_reupload_is_allowed_in_draft_for_a_pending_document(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    """Nothing is locked before submission, so any document can be replaced."""
    application_id, admin = _create_draft_with_data(
        api_client, test_data, workspace_applications
    )
    original = _latest_document(api_client, application_id, admin)
    assert "reupload" in original["allowed_actions"]

    replaced = _reupload(
        api_client,
        application_id,
        original["id"],
        admin,
        data=TEXT_PDF,
        signer_name="Dr Demo Registrar",
    )
    assert replaced.status_code == 201, replaced.text
    assert replaced.json()["version"] == 2

    # The replacement contract always demands a DSC attestation (APH 1.4.3).
    unsigned = _reupload(
        api_client,
        application_id,
        replaced.json()["id"],
        admin,
        signed_with_dsc=False,
    )
    assert unsigned.status_code == 422, unsigned.text
    assert "signed_with_dsc" in unsigned.json()["detail"]["errors"]


def test_reupload_is_refused_for_verified_documents_and_locked_cases(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    """Every forbidden case returns 409 with a readable, clause-cited reason."""
    application_id, admin, scrutiny = _submitted_in_scrutiny(
        api_client, test_data, workspace_applications
    )
    original = _latest_document(api_client, application_id, admin)
    assert _reject(api_client, application_id, original["id"], scrutiny).status_code == 200

    replacement = _reupload(api_client, application_id, original["id"], admin)
    assert replacement.status_code == 201, replacement.text

    verified = api_client.post(
        f"/applications/{application_id}/documents/{replacement.json()['id']}/verify",
        json={"comment": "Readable and current.", "apH_clause": "APH 1.8g"},
        headers=scrutiny,
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["verification_status"] == "VERIFIED"

    refused_verified = _reupload(
        api_client, application_id, replacement.json()["id"], admin
    )
    assert refused_verified.status_code == 409, refused_verified.text
    assert "verified" in refused_verified.json()["detail"].lower()

    # Reject a different document, then lock the case outside a compliance window.
    other = _latest_document(
        api_client, application_id, admin, doc_type="AFFIDAVIT_2"
    )
    rejected = _reject(
        api_client,
        application_id,
        other["id"],
        scrutiny,
        reason_code="INCOMPLETE",
        comment="Page 2 is missing.",
    )
    assert rejected.status_code == 200, rejected.text

    with SessionLocal() as db:
        application = db.get(Application, uuid.UUID(application_id))
        assert application is not None
        application.status = ApplicationStatus.REGULATION_BUREAU_OBSERVATIONS
        db.commit()

    refused_locked = _reupload(api_client, application_id, other["id"], admin)
    assert refused_locked.status_code == 409, refused_locked.text
    assert "locked" in refused_locked.json()["detail"].lower()

    # Another institution and the super admin may not replace either.
    east = _headers(api_client, test_data, "institution_admin_east")
    refused_foreign = _reupload(api_client, application_id, other["id"], east)
    assert refused_foreign.status_code == 409, refused_foreign.text

    super_admin = _headers(api_client, test_data, "super")
    refused_super = _reupload(api_client, application_id, other["id"], super_admin)
    assert refused_super.status_code == 409, refused_super.text


def test_compliance_submission_waits_for_every_rejected_document(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    """Submit compliance is blocked until each rejected document is replaced."""
    application_id, admin, scrutiny = _submitted_in_scrutiny(
        api_client, test_data, workspace_applications
    )
    fire = _latest_document(api_client, application_id, admin)
    affidavit = _latest_document(
        api_client, application_id, admin, doc_type="AFFIDAVIT_2"
    )
    for document in (fire, affidavit):
        rejected = _reject(
            api_client,
            application_id,
            document["id"],
            scrutiny,
            reason_code="UNREADABLE",
            comment="The scan is illegible.",
        )
        assert rejected.status_code == 200, rejected.text

    with SessionLocal() as db:
        deficiencies = list(
            db.scalars(
                select(Deficiency).where(
                    Deficiency.application_id == uuid.UUID(application_id)
                )
            ).all()
        )
        assert len(deficiencies) == 2
        open_ids = [str(item.id) for item in deficiencies]

    blocked = api_client.post(
        f"/applications/{application_id}/actions/submit_compliance",
        headers=admin,
        json={
            "responses": [
                {
                    "deficiency_id": deficiency_id,
                    "response_text": "Replacement uploaded.",
                }
                for deficiency_id in open_ids
            ]
        },
    )
    assert blocked.status_code == 409, blocked.text
    assert "re-upload" in _detail_text(blocked).lower()

    replaced = _reupload(api_client, application_id, fire["id"], admin)
    assert replaced.status_code == 201, replaced.text

    still_blocked = api_client.post(
        f"/applications/{application_id}/actions/submit_compliance",
        headers=admin,
        json={
            "responses": [
                {
                    "deficiency_id": deficiency_id,
                    "response_text": "Replacement uploaded.",
                }
                for deficiency_id in open_ids
            ]
        },
    )
    assert still_blocked.status_code == 409, still_blocked.text

    replaced_two = _reupload(api_client, application_id, affidavit["id"], admin)
    assert replaced_two.status_code == 201, replaced_two.text

    # Both rejections are already answered, so no text response remains.
    submitted = api_client.post(
        f"/applications/{application_id}/actions/submit_compliance",
        headers=admin,
        json={"responses": []},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["application"]["status"] == "INSTITUTION_COMPLIANCE"


def test_only_reuploaded_documents_are_listed_for_re_scrutiny(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    """Re-Scrutiny re-checks exactly the documents that were replaced."""
    application_id, admin, scrutiny = _submitted_in_scrutiny(
        api_client, test_data, workspace_applications
    )
    fire = _latest_document(api_client, application_id, admin)
    rejected = _reject(api_client, application_id, fire["id"], scrutiny)
    assert rejected.status_code == 200, rejected.text
    replaced = _reupload(api_client, application_id, fire["id"], admin)
    assert replaced.status_code == 201, replaced.text

    to_recheck = api_client.get(
        f"/applications/{application_id}/documents",
        params={"only_to_recheck": "true"},
        headers=scrutiny,
    )
    assert to_recheck.status_code == 200, to_recheck.text
    rows = to_recheck.json()
    assert [row["id"] for row in rows] == [replaced.json()["id"]]
    assert rows[0]["version"] == 2
    assert rows[0]["verification_status"] == "PENDING"

    verified = api_client.post(
        f"/applications/{application_id}/documents/{replaced.json()['id']}/verify",
        json={"comment": "Current certificate received.", "apH_clause": "APH 1.8g"},
        headers=scrutiny,
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["verification_status"] == "VERIFIED"

    after = api_client.get(
        f"/applications/{application_id}/documents",
        params={"only_to_recheck": "true"},
        headers=scrutiny,
    )
    assert after.status_code == 200, after.text
    assert after.json() == []


def test_reupload_validation_reports_each_field(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    """Unsigned, expired, blank and oversized replacements are refused."""
    application_id, admin, scrutiny = _submitted_in_scrutiny(
        api_client, test_data, workspace_applications
    )
    fire = _latest_document(api_client, application_id, admin)
    rejected = _reject(api_client, application_id, fire["id"], scrutiny)
    assert rejected.status_code == 200, rejected.text

    unsigned = _reupload(
        api_client, application_id, fire["id"], admin, signed_with_dsc=False
    )
    assert unsigned.status_code == 422, unsigned.text
    assert "signed_with_dsc" in unsigned.json()["detail"]["errors"]

    unsigned_again = _reupload(
        api_client,
        application_id,
        fire["id"],
        admin,
        signer_name=None,
    )
    assert unsigned_again.status_code == 422, unsigned_again.text
    assert "signer_name" in unsigned_again.json()["detail"]["errors"]

    expired = _reupload(
        api_client,
        application_id,
        fire["id"],
        admin,
        valid_until=(date.today() - timedelta(days=1)).isoformat(),
    )
    assert expired.status_code == 422, expired.text
    assert "valid_until" in expired.json()["detail"]["errors"]

    missing_validity = _reupload(
        api_client, application_id, fire["id"], admin, valid_until=None
    )
    assert missing_validity.status_code == 422, missing_validity.text
    assert "valid_until" in missing_validity.json()["detail"]["errors"]

    blank = _reupload(api_client, application_id, fire["id"], admin, data=BLANK_PDF)
    assert blank.status_code == 422, blank.text
    assert "file" in blank.json()["detail"]["errors"]

    oversized = _reupload(
        api_client,
        application_id,
        fire["id"],
        admin,
        data=b"%PDF-1.4" + b"0" * (10 * 1024 * 1024),
    )
    assert oversized.status_code == 413, oversized.text

    wrong_type = api_client.post(
        f"/applications/{application_id}/documents/{fire['id']}/reupload",
        data={"signed_with_dsc": "true", "signer_name": "Dr Demo", "valid_until": NEXT_YEAR},
        files={"file": ("notes.txt", b"plain text", "text/plain")},
        headers=admin,
    )
    assert wrong_type.status_code == 415, wrong_type.text

    # Nothing was stored, so the rejected document is still the latest version.
    latest = _latest_document(api_client, application_id, admin)
    assert latest["version"] == 1
    assert latest["verification_status"] == "REJECTED"


def test_reupload_limit_is_enforced(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    """The configurable replacement cap stops an endless reject/upload loop."""
    settings = api_client.app.state.settings
    original_limit = settings.max_reuploads_per_document
    settings.max_reuploads_per_document = 1
    try:
        application_id, admin, scrutiny = _submitted_in_scrutiny(
            api_client, test_data, workspace_applications
        )
        fire = _latest_document(api_client, application_id, admin)
        assert _reject(api_client, application_id, fire["id"], scrutiny).status_code == 200

        first = _reupload(api_client, application_id, fire["id"], admin)
        assert first.status_code == 201, first.text

        second_rejection = _reject(
            api_client, application_id, first.json()["id"], scrutiny
        )
        assert second_rejection.status_code == 200, second_rejection.text

        blocked = _reupload(api_client, application_id, first.json()["id"], admin)
        assert blocked.status_code == 409, blocked.text
        assert "replacement limit" in blocked.json()["detail"].lower()
        assert "1" in blocked.json()["detail"]
    finally:
        settings.max_reuploads_per_document = original_limit


def test_non_reviewers_cannot_reject_or_verify(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    """Rejection and verification stay on the reviewer roles (403, not 409)."""
    application_id, admin, scrutiny = _submitted_in_scrutiny(
        api_client, test_data, workspace_applications
    )
    fire = _latest_document(api_client, application_id, admin)

    as_institution = _reject(api_client, application_id, fire["id"], admin)
    assert as_institution.status_code == 403, as_institution.text

    as_super_admin = _reject(
        api_client,
        application_id,
        fire["id"],
        _headers(api_client, test_data, "super"),
    )
    assert as_super_admin.status_code == 403, as_super_admin.text

    verified = api_client.post(
        f"/applications/{application_id}/documents/{fire['id']}/verify",
        json={"comment": "looks fine"},
        headers=admin,
    )
    assert verified.status_code == 403, verified.text


def test_flagged_and_rejected_mandatory_documents_make_the_checklist_incomplete(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    """A rejected mandatory document cannot be submitted from the draft wizard."""
    application_id, admin = _create_draft_with_data(
        api_client, test_data, workspace_applications
    )
    before = api_client.get(
        f"/applications/{application_id}/documents/checklist", headers=admin
    )
    assert before.status_code == 200, before.text
    assert before.json()["uploaded_count"] == before.json()["required_count"]

    fire = _latest_document(api_client, application_id, admin)
    with SessionLocal() as db:
        document = db.get(Document, uuid.UUID(fire["id"]))
        assert document is not None
        document.verification_status = DocumentVerificationStatus.REJECTED
        document.rejection_reason_code = "EXPIRED"
        document.rejection_comment = "Expired on 2025-12-31."
        document.apH_clause = "APH 1.8f"
        db.commit()

    after = api_client.get(
        f"/applications/{application_id}/documents/checklist", headers=admin
    )
    assert after.status_code == 200, after.text
    body = after.json()
    assert body["uploaded_count"] == body["required_count"] - 1
    fire_row = next(row for row in body["documents"] if row["doc_type"] == FIRE)
    assert fire_row["uploaded"] is True
    assert fire_row["complete"] is False
    assert fire_row["rejection_reason_code"] == "EXPIRED"
    assert fire_row["apH_clause"] == "APH 1.8f"

    checklist = api_client.get(f"/applications/{application_id}/checklist", headers=admin)
    assert checklist.status_code == 200, checklist.text
    assert checklist.json()["can_submit"] is False
    codes = {item["code"] for item in checklist.json()["missing"]}
    assert f"document.{FIRE}.rejected" in codes


def test_document_list_requires_authentication(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    """The new endpoints are not a way to read files anonymously."""
    application_id, admin = _create_draft_with_data(
        api_client, test_data, workspace_applications
    )
    fire = _latest_document(api_client, application_id, admin)

    anonymous_list = api_client.get(f"/applications/{application_id}/documents")
    assert anonymous_list.status_code == 401, anonymous_list.text

    anonymous_history = api_client.get(
        f"/applications/{application_id}/documents/{fire['id']}/versions"
    )
    assert anonymous_history.status_code == 401, anonymous_history.text

    anonymous_reject = api_client.post(
        f"/applications/{application_id}/documents/{fire['id']}/reject",
        json={"reason_code": "EXPIRED", "comment": "expired"},
    )
    assert anonymous_reject.status_code == 401, anonymous_reject.text


def test_future_due_date_is_used_for_the_deficiency(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    """The deficiency due date comes from the configurable SLA row (APH 2.4)."""
    application_id, admin, scrutiny = _submitted_in_scrutiny(
        api_client, test_data, workspace_applications
    )
    fire = _latest_document(api_client, application_id, admin)
    rejected = _reject(api_client, application_id, fire["id"], scrutiny)
    assert rejected.status_code == 200, rejected.text

    due = date.fromisoformat(rejected.json()["deficiency_due_date"])
    assert due >= date.today()
