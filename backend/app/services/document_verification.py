"""Deterministic document checks used as a local stand-in for AI extraction.

The checker only inspects what it can read from the uploaded file name and
plain-text fragments. It never rejects an upload for a weak reference; it records
a verification status and a human-readable reason so the institution can replace
a weak copy. The readability and certificate helpers below do block an upload
when the file cannot be used at all (APH 1.4.3).
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

from app.models.enums import DocumentVerificationStatus

_READABLE_RUN = re.compile(rb"[\x20-\x7e]{4,}")
_LETTER_RUN = re.compile(r"[A-Za-z]{4,}")
_SAMPLE_BYTES = 1024 * 1024

_CERTIFICATE_DOC_TYPES = (
    "FIRE",
    "OCCUPANCY",
    "STRUCTURAL",
)
"""Certificate families whose validity date must be supplied (APH Annexure-2.1)."""

_NAME_STOPWORDS = frozenset(
    {
        "institute",
        "institution",
        "college",
        "university",
        "technology",
        "engineering",
        "management",
        "the",
        "and",
        "for",
        "of",
        "school",
    }
)


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
    """Return the searchable text of a file name and any readable fragments.

    Separators in the file name are normalised so ``fsr_details.pdf`` matches
    the ``fsr details`` term a document type produces.
    """
    chunks = [filename.lower()]
    for match in _READABLE_RUN.findall(data[:_SAMPLE_BYTES]):
        chunks.append(match.decode("ascii", "ignore").lower())
    return " ".join(chunks).replace("_", " ").replace("-", " ")


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


def certificate_requires_validity(doc_type: str, doc_code: str | None = None) -> bool:
    """Return whether the certificate family must carry a validity date.

    APH Annexure-2.1(v) and Annexure-1 require current fire, occupancy and
    structural-safety certificates; an expired certificate cannot support the
    application.
    """
    probe = f"{doc_type} {doc_code or ''}".upper()
    return any(family in probe for family in _CERTIFICATE_DOC_TYPES)


def pdf_readability_error(data: bytes) -> str | None:
    """Return a message when a PDF has no readable text, otherwise ``None``.

    Scanned image-only pages cannot be verified or searched, so the institution
    is asked to upload a text-bearing or OCR'd copy. A parser failure falls back
    to the printable-run heuristic so a valid but unusual PDF is not blocked.
    """
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(data)) as pdf:
            text = " ".join((page.extract_text() or "") for page in pdf.pages)
        if len(_LETTER_RUN.findall(text)) > 0:
            return None
        return (
            "The PDF has no readable text (it is blank or an image-only scan). "
            "Upload a text-bearing or OCR'd copy so it can be verified (APH 1.4.3)."
        )
    except Exception:
        if _READABLE_RUN.search(data[:_SAMPLE_BYTES]):
            return None
        return (
            "The PDF has no readable content. Upload a legible copy "
            "(APH 1.4.3)."
        )


def name_mismatch_warning(
    institution_name: str,
    *,
    filename: str,
    data: bytes,
) -> str | None:
    """Warn when the document text never names the institution.

    This is advisory only: an extractable document can legitimately be a
    certificate issued in another party's name, so the upload is not blocked.
    """
    tokens = [
        token
        for token in re.findall(r"[a-z]{4,}", institution_name.lower())
        if token not in _NAME_STOPWORDS
    ]
    if not tokens:
        return None
    searchable = _readable_text(data, filename)
    if any(token in searchable for token in tokens):
        return None
    return (
        "The institution name could not be found in the document text. Check that "
        "this certificate names the right institution."
    )

