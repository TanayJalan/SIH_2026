"""Completeness and required-document checklist calculations."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.document import Document
from app.models.enums import DocumentVerificationStatus
from app.models.required_document import RequiredDocument
from app.schemas.application import (
    ApplicationChecklistRead,
    ChecklistDocument,
    ChecklistSection,
    DocumentChecklistRead,
    MissingItem,
)
from app.services.document_verification import verification_reason

Validator = Callable[[Any], bool]

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PIN_RE = re.compile(r"^\d{6}$")
_PHONE_RE = re.compile(r"^[0-9+\-()\s]{7,24}$")

_DOCUMENT_LABELS = {
    "AFFILIATION_CERTIFICATE": "Affiliation certificate",
    "BUILDING_PLAN_APPROVAL": "Building plan approval",
    "EXISTING_APPROVAL_LETTER": "Existing approval letter",
    "FACULTY_DETAILS": "Faculty details",
    "FINANCIAL_STATEMENT": "Financial statement",
    "INFRASTRUCTURE_PLAN": "Infrastructure plan",
    "LAND_OWNERSHIP_DOCUMENT": "Land ownership document",
    "MANDATORY_DISCLOSURE": "Mandatory disclosure document",
    "NAAC_NBA_CERTIFICATE": "NAAC / NBA certificate",
}


@dataclass(frozen=True, slots=True)
class FieldRequirement:
    """One required field in a wizard section."""

    key: str
    label: str
    validator: Validator | None = None
    invalid_message: str | None = None


@dataclass(frozen=True, slots=True)
class SectionRequirement:
    """A section and the fields that must be present before submission."""

    key: str
    label: str
    fields: tuple[FieldRequirement, ...]
    top_level: bool = False


def _is_email(value: Any) -> bool:
    return isinstance(value, str) and bool(_EMAIL_RE.fullmatch(value.strip()))


def _is_pin(value: Any) -> bool:
    return isinstance(value, str) and bool(_PIN_RE.fullmatch(value.strip()))


def _is_phone(value: Any) -> bool:
    if not isinstance(value, str) or not _PHONE_RE.fullmatch(value.strip()):
        return False
    digits = re.sub(r"\D", "", value)
    return 7 <= len(digits) <= 15


def _is_http_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


SECTION_REQUIREMENTS: tuple[SectionRequirement, ...] = (
    SectionRequirement(
        key="institution_profile",
        label="Institution profile",
        fields=(
            FieldRequirement("head_name", "Head of institution"),
            FieldRequirement("address_line1", "Address line 1"),
            FieldRequirement("city", "City"),
            FieldRequirement("state", "State"),
            FieldRequirement("pin_code", "PIN code", _is_pin, "Enter a valid 6-digit PIN code."),
            FieldRequirement(
                "contact_email",
                "Contact email",
                _is_email,
                "Enter a valid contact email address.",
            ),
            FieldRequirement(
                "contact_phone",
                "Contact phone",
                _is_phone,
                "Enter a valid contact phone number.",
            ),
        ),
    ),
    SectionRequirement(
        key="infrastructure",
        label="Infrastructure",
        fields=(
            FieldRequirement("land_area", "Land area"),
            FieldRequirement("built_up_area", "Built-up area"),
            FieldRequirement("labs", "Laboratories"),
            FieldRequirement("library", "Library volumes"),
            FieldRequirement("hostel", "Hostel capacity"),
        ),
    ),
    SectionRequirement(
        key="faculty",
        label="Faculty",
        fields=(
            FieldRequirement("total", "Total faculty"),
            FieldRequirement("professors", "Professors"),
            FieldRequirement("associate_professors", "Associate professors"),
            FieldRequirement("assistant_professors", "Assistant professors"),
            FieldRequirement("student_faculty_ratio", "Student-faculty ratio"),
            FieldRequirement("phd_faculty_ratio", "Faculty with PhD (%)"),
        ),
    ),
    SectionRequirement(
        key="finance",
        label="Finance",
        fields=(
            FieldRequirement("tuition_fee", "Tuition fee"),
            FieldRequirement("development_fee", "Development fee"),
            FieldRequirement("other_fees", "Other fees"),
            FieldRequirement("balance", "Balance"),
        ),
    ),
    SectionRequirement(
        key="accreditation",
        label="Accreditation",
        fields=(
            FieldRequirement("naac_grade", "NAAC grade"),
            FieldRequirement("nba_status", "NBA status"),
        ),
    ),
    SectionRequirement(
        key="mandatory_disclosure_url",
        label="Mandatory disclosure",
        top_level=True,
        fields=(
            FieldRequirement(
                "mandatory_disclosure_url",
                "Mandatory disclosure URL",
                _is_http_url,
                "Enter a valid http(s) mandatory disclosure URL.",
            ),
        ),
    ),
)


def _is_filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _section_value(data: dict[str, Any], section: SectionRequirement, field_key: str) -> Any:
    if section.top_level:
        return data.get(field_key)
    raw_section = data.get(section.key)
    if not isinstance(raw_section, dict):
        return None
    return raw_section.get(field_key)


def _section_statuses(
    data: dict[str, Any],
) -> tuple[list[ChecklistSection], list[MissingItem], int, int]:
    sections: list[ChecklistSection] = []
    missing: list[MissingItem] = []
    required_count = 0
    completed_count = 0

    for section in SECTION_REQUIREMENTS:
        missing_labels: list[str] = []
        for field in section.fields:
            required_count += 1
            value = _section_value(data, section, field.key)
            if not _is_filled(value):
                missing_labels.append(field.label)
                missing.append(
                    MissingItem(
                        code=f"{section.key}.{field.key}",
                        section=section.label,
                        message=f"{field.label} is required.",
                    )
                )
                continue
            if field.validator is not None and not field.validator(value):
                missing_labels.append(field.label)
                missing.append(
                    MissingItem(
                        code=f"{section.key}.{field.key}",
                        section=section.label,
                        message=field.invalid_message or f"{field.label} is not valid.",
                    )
                )
                continue
            completed_count += 1

        sections.append(
            ChecklistSection(
                key=section.key,
                label=section.label,
                complete=not missing_labels,
                missing_fields=missing_labels,
            )
        )

    return sections, missing, required_count, completed_count


def document_label(doc_type: str) -> str:
    """Return a readable label for a document type."""
    return _DOCUMENT_LABELS.get(doc_type, doc_type.replace("_", " ").title())


def current_documents(db: Session, application_id: object) -> dict[str, Document]:
    """Return the latest uploaded version for each document type."""
    rows = db.scalars(
        select(Document)
        .where(Document.application_id == application_id)
        .order_by(Document.doc_type.asc(), Document.version.desc())
    ).all()
    latest: dict[str, Document] = {}
    for document in rows:
        latest.setdefault(document.doc_type, document)
    return latest


def _document_checklist(
    db: Session,
    application: Application,
) -> tuple[list[ChecklistDocument], int, int]:
    rules = db.scalars(
        select(RequiredDocument)
        .where(RequiredDocument.application_type == application.application_type)
        .order_by(RequiredDocument.mandatory.desc(), RequiredDocument.doc_type.asc())
    ).all()
    latest = current_documents(db, application.id)
    documents: list[ChecklistDocument] = []
    required_count = 0
    uploaded_count = 0

    for rule in rules:
        document = latest.get(rule.doc_type)
        complete = (
            document is not None
            and document.signed_with_dsc
            and document.verification_status
            not in {
                DocumentVerificationStatus.REJECTED,
                DocumentVerificationStatus.FLAGGED,
            }
        )
        if rule.mandatory:
            required_count += 1
            if complete:
                uploaded_count += 1
        documents.append(
            ChecklistDocument(
                doc_type=rule.doc_type,
                doc_code=rule.doc_code,
                label=document_label(rule.doc_type),
                mandatory=rule.mandatory,
                uploaded=document is not None,
                complete=complete,
                document_id=document.id if document is not None else None,
                filename=document.filename if document is not None else None,
                content_type=document.content_type if document is not None else None,
                size_bytes=document.size_bytes if document is not None else None,
                version=document.version if document is not None else None,
                signed_with_dsc=(
                    document.signed_with_dsc if document is not None else None
                ),
                signer_name=document.signer_name if document is not None else None,
                valid_until=document.valid_until if document is not None else None,
                verification_status=(
                    document.verification_status if document is not None else None
                ),
                verification_reason=(
                    verification_reason(document.verification_notes)
                    if document is not None
                    else None
                ),
                rejection_reason_code=(
                    document.rejection_reason_code if document is not None else None
                ),
                rejection_comment=(
                    document.rejection_comment if document is not None else None
                ),
                rejected_at=document.rejected_at if document is not None else None,
                apH_clause=document.apH_clause if document is not None else None,
                related_deficiency_id=(
                    document.related_deficiency_id if document is not None else None
                ),
                deficiency_status=(
                    document.related_deficiency.status.value
                    if document is not None and document.related_deficiency is not None
                    else None
                ),
                deficiency_due_date=(
                    document.related_deficiency.due_date
                    if document is not None and document.related_deficiency is not None
                    else None
                ),
                uploaded_at=document.created_at if document is not None else None,
                download_url=(
                    f"/applications/{application.id}/documents/{document.id}/download"
                    if document is not None
                    else None
                ),
            )
        )

    return documents, required_count, uploaded_count


def build_document_checklist(db: Session, application: Application) -> DocumentChecklistRead:
    """Return the required-document checklist with current upload status."""
    documents, required_count, uploaded_count = _document_checklist(db, application)
    percentage = round((uploaded_count / required_count) * 100) if required_count else 100
    return DocumentChecklistRead(
        application_id=application.id,
        documents=documents,
        required_count=required_count,
        uploaded_count=uploaded_count,
        percentage=percentage,
    )


def build_application_checklist(
    db: Session,
    application: Application,
) -> ApplicationChecklistRead:
    """Return section and document completeness for a draft."""
    data = application.data if isinstance(application.data, dict) else {}
    sections, missing, section_required, section_completed = _section_statuses(data)
    documents, required_docs, uploaded_docs = _document_checklist(db, application)

    for document in documents:
        if document.mandatory and not document.uploaded:
            missing.append(
                MissingItem(
                    code=f"document.{document.doc_type}",
                    section="Documents",
                    message=f"Upload the required document: {document.label}.",
                )
            )
        elif document.mandatory and document.uploaded and not document.signed_with_dsc:
            missing.append(
                MissingItem(
                    code=f"document.{document.doc_type}.dsc",
                    section="Documents",
                    message=(
                        f"Re-upload {document.label} with a valid digital signature (DSC). "
                        "APH 1.4.6 does not allow an unsigned document."
                    ),
                )
            )
        elif (
            document.mandatory
            and document.uploaded
            and document.verification_status == DocumentVerificationStatus.REJECTED
        ):
            reason = (
                document.rejection_comment
                or document.verification_reason
                or "a reviewer rejected this document"
            )
            missing.append(
                MissingItem(
                    code=f"document.{document.doc_type}.rejected",
                    section="Documents",
                    message=(
                        f"Replace {document.label}: {reason} "
                        f"({document.apH_clause or 'APH 1.8f'})."
                    ),
                )
            )
        elif (
            document.mandatory
            and document.uploaded
            and document.verification_status == DocumentVerificationStatus.FLAGGED
        ):
            missing.append(
                MissingItem(
                    code=f"document.{document.doc_type}.flagged",
                    section="Documents",
                    message=(
                        f"Replace {document.label} with a legible copy: "
                        f"{document.verification_reason or 'the document was flagged'} "
                        "(APH 1.8f)."
                    ),
                )
            )

    required_items = section_required + required_docs
    completed_items = section_completed + uploaded_docs
    percentage = round((completed_items / required_items) * 100) if required_items else 100

    return ApplicationChecklistRead(
        application_id=application.id,
        sections=sections,
        documents=documents,
        required_items=required_items,
        completed_items=completed_items,
        percentage=percentage,
        can_submit=not missing,
        missing=missing,
    )
