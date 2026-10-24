"""Deterministic document checks used as a local stand-in for AI extraction.

The checker only inspects what it can read from the uploaded file name and
plain-text fragments. It never rejects an upload; it records a verification
status and a human-readable reason so the institution can replace a weak copy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.enums import DocumentVerificationStatus

_READABLE_RUN = re.compile(rb"[\x20-\x7e]{4,}")
_SAMPLE_BYTES = 1024 * 1024

_DOCUMENT_TERMS: dict[str, tuple[str, ...]] = {
    "AFFILIATION_CERTIFICATE": ("affiliation", "aicte", "university"),
    "BUILDING_PLAN_APPROVAL": ("building", "plan approval", "sanction"),
    "EXISTING_APPROVAL_LETTER": ("approval", "aicte", "extension"),
    "FACULTY_DETAILS": ("faculty", "staff", "teacher"),
    "FINANCIAL_STATEMENT": ("financial", "balance sheet", "audit"),
    "INFRASTRUCTURE_PLAN": ("infrastructure", "campus", "master plan"),
    "LAND_OWNERSHIP_DOCUMENT": ("land", "ownership", "title deed", "sale deed"),
    "MANDATORY_DISCLOSURE": ("mandatory disclosure", "disclosure"),
    "NAAC_NBA_CERTIFICATE": ("naac", "nba", "accreditation"),
}

_LABELS: dict[str, str] = {
    "AFFILIATION_CERTIFICATE": "Affiliation certificate",
    "BUILDING_PLAN_APPROVAL": "Building plan approval",
    "EXISTING_APPROVAL_LETTER": "Existing approval letter",
    "FACULTY_DETAILS": "Faculty details",
    "FINANCIAL_STATEMENT": "Financial statement",
    "INFRASTRUCTURE_PLAN": "Infrastructure plan",
    "LAND_OWNERSHIP_DOCUMENT": "Land ownership document",
    "MANDATORY_DISCLOSURE": "Mandatory disclosure",
    "NAAC_NBA_CERTIFICATE": "NAAC / NBA certificate",
}


@dataclass(frozen=True, slots=True)
class DocumentCheck:
    """The persisted outcome of one upload check."""

    status: DocumentVerificationStatus
    reason: str
    matched_terms: tuple[str, ...]


def _readable_text(data: bytes, filename: str) -> str:
    chunks = [filename.lower()]
    for match in _READABLE_RUN.findall(data[:_SAMPLE_BYTES]):
        chunks.append(match.decode("ascii", "ignore").lower())
    return " ".join(chunks)


def _terms_for(doc_type: str) -> tuple[str, ...]:
    configured = _DOCUMENT_TERMS.get(doc_type)
    if configured:
        return configured
    words = tuple(
        word
        for word in doc_type.lower().split("_")
        if len(word) >= 4 and word not in {"document", "certificate", "details"}
    )
    return words or (doc_type.lower().replace("_", " "),)


def _label_for(doc_type: str) -> str:
    return _LABELS.get(doc_type, doc_type.replace("_", " ").title())


def verify_document(
    *,
    doc_type: str,
    filename: str,
    data: bytes,
) -> DocumentCheck:
    """Check for a recognizable document reference without blocking upload."""
    terms = _terms_for(doc_type)
    searchable = _readable_text(data, filename)
    matched = tuple(term for term in terms if term in searchable)
    label = _label_for(doc_type)

    if matched:
        return DocumentCheck(
            status=DocumentVerificationStatus.VERIFIED,
            reason=f"AI check found a recognizable {label.lower()} reference.",
            matched_terms=matched,
        )
    return DocumentCheck(
        status=DocumentVerificationStatus.FLAGGED,
        reason=(
            f"The file name and readable content do not show a recognizable "
            f"{label.lower()} reference. Replace it with a legible copy that names "
            "the document."
        ),
        matched_terms=(),
    )


def verification_reason(notes: dict[str, object] | None) -> str | None:
    """Read the reason stored in verification notes for API presentation."""
    if not notes:
        return None
    reason = notes.get("reason")
    if isinstance(reason, str) and reason.strip():
        return reason
    return None
