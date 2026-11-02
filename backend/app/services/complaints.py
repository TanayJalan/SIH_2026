"""Complaint lifecycle from PGRC to the Executive Committee (APH 7.10).

The handbook runs one complaint through five bodies:

* PGRC receives and verifies it (APH 7.10b);
* SCSC decides on a warning, a show-cause notice or an EVC (APH 7.10c);
* the EVC report or show-cause reply goes to the SHC (APH 7.10d-e);
* the SHC recommends, and the EC approves (APH 7.10f);
* the EC decision is published as a Speaking Order with an appeal right
  (APH 7.10g).

Anonymous and pseudonymous complaints stop at intake: APH 7.10h adopts the CVC
rule that they shall not be processed.

Every write is recorded through :class:`~app.services.audit.AuditService`; the
caller owns the transaction.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.models.application import Application
from app.models.complaint import Complaint
from app.models.enums import ComplaintStatus
from app.models.institution import Institution
from app.models.user import User
from app.services.audit import AuditService

#: APH 7.10 does not fix a reply window for a show-cause notice. The value is a
#: demo parameter recorded in ``docs/OPEN_QUESTIONS.md`` and never presented as
#: a handbook date.
SHOW_CAUSE_RESPONSE_DAYS = 15

ANONYMITY_CLAUSE = "APH 7.10h"
ANONYMITY_REASON = (
    "Not processed: as per CVC guidelines, anonymous and pseudonymous "
    "complaints shall not be processed (APH 7.10h)."
)
"""The CVC rule adopted by APH 7.10h, shown verbatim on a rejected intake."""

SCSC_DECISIONS = {
    "WARNING": "Warning issued to the institution",
    "SHOW_CAUSE": "Show-cause notice issued to the institution",
    "EVC": "Expert Visit Committee conducted through the Regulation Bureau",
}
EC_DECISIONS = {
    "WARNING": "Complaint closed with a warning",
    "PENAL_ACTION": "Penal action approved with a Speaking Order",
    "CLOSE": "Complaint closed with no further action",
}


class ComplaintError(ValueError):
    """Raised when a complaint step is not allowed in its current state."""


@dataclass(frozen=True)
class ComplaintStep:
    """One visible lifecycle step with its handbook citation."""

    key: str
    label: str
    apH_clause: str


_STEPS = (
    ComplaintStep("receive", "Complaint received by PGRC", "APH 7.10b"),
    ComplaintStep("verify", "Verified and placed before SCSC", "APH 7.10c"),
    ComplaintStep("scsc", "SCSC recommends warning, show-cause or EVC", "APH 7.10c"),
    ComplaintStep("show_cause", "Show-cause reply recorded", "APH 7.10d"),
    ComplaintStep("hearing", "Standing Hearing Committee hearing", "APH 7.10d-e"),
    ComplaintStep("ec", "Executive Committee decision", "APH 7.10f"),
    ComplaintStep("speaking_order", "Speaking Order on the portal", "APH 7.10g"),
)


def lifecycle() -> list[dict[str, str]]:
    """Return the complaint lifecycle for the case-file UI."""
    return [
        {"key": step.key, "label": step.label, "apH_clause": step.apH_clause} for step in _STEPS
    ]


def is_pseudonymous(
    *, is_anonymous: bool, complainant_name: str | None, complainant_contact: str | None
) -> bool:
    """Return whether the complaint must be rejected at intake (APH 7.10h).

    A complaint is processed only when it carries both an identity and a
    verifiable contact. A missing name is anonymous; a name without a contact
    is treated as pseudonymous, mirroring the CVC rule APH 7.10h adopts.
    """
    if is_anonymous:
        return True
    return not (complainant_name and complainant_contact)


def _assert_status(complaint: Complaint, *allowed: ComplaintStatus) -> None:
    if complaint.status not in allowed:
        expected = ", ".join(status.value for status in allowed)
        raise ComplaintError(
            f"The complaint is {complaint.status.value}; this step requires {expected}."
        )


def _snapshot(complaint: Complaint) -> dict[str, Any]:
    return {
        "status": complaint.status.value,
        "scsc_decision": complaint.scsc_decision,
        "ec_decision": complaint.ec_decision,
        "complainant_verified": complaint.complainant_verified,
        "rejection_reason": complaint.rejection_reason,
    }


def _log(
    audit: AuditService,
    actor: User | None,
    action: str,
    complaint: Complaint,
    before: dict[str, Any],
    request: Request | None,
    after: dict[str, Any] | None = None,
) -> None:
    audit.log(
        actor,
        action,
        entity_type="Complaint",
        entity_id=complaint.id,
        before=before,
        after=after or _snapshot(complaint),
        request=request,
    )


def create_complaint(
    db: Session,
    *,
    institution: Institution,
    application: Application | None,
    source: str,
    category: str,
    description: str,
    received_on: date,
    complainant_name: str | None,
    complainant_contact: str | None,
    is_anonymous: bool,
    actor: User | None,
    audit: AuditService,
    request: Request | None = None,
) -> Complaint:
    """Record a complaint and immediately reject it if it is anonymous (APH 7.10h).

    A verified complaint starts at ``PGRC``; an anonymous or pseudonymous one is
    stored at ``RECEIVED`` with ``rejection_reason`` and ``rejection_clause`` so
    the demo can show the CVC rule without pretending to process it.
    """
    rejected = is_pseudonymous(
        is_anonymous=is_anonymous,
        complainant_name=complainant_name,
        complainant_contact=complainant_contact,
    )
    complaint = Complaint(
        institution_id=institution.id,
        application_id=application.id if application is not None else None,
        source=source,
        category=category,
        description=description,
        received_on=received_on,
        complainant_name=complainant_name,
        complainant_contact=complainant_contact,
        complainant_verified=False,
        is_anonymous=rejected,
        status=ComplaintStatus.RECEIVED if rejected else ComplaintStatus.PGRC,
        rejection_reason=ANONYMITY_REASON if rejected else None,
        rejection_clause=ANONYMITY_CLAUSE if rejected else None,
        apH_clause=ANONYMITY_CLAUSE if rejected else "APH 7.10b",
    )
    db.add(complaint)
    db.flush()
    _log(
        audit,
        actor,
        "complaint.rejected" if rejected else "complaint.received",
        complaint,
        before={},
        request=request,
    )
    return complaint


def verify_complaint(
    db: Session,
    complaint: Complaint,
    *,
    actor: User | None,
    audit: AuditService,
    request: Request | None = None,
) -> Complaint:
    """Mark the complaint verified and place it before the SCSC (APH 7.10c)."""
    _assert_status(complaint, ComplaintStatus.RECEIVED, ComplaintStatus.PGRC)
    if complaint.is_anonymous:
        raise ComplaintError(ANONYMITY_REASON)
    before = _snapshot(complaint)
    complaint.complainant_verified = True
    complaint.status = ComplaintStatus.SCSC
    _log(audit, actor, "complaint.verified", complaint, before, request)
    return complaint


def record_scsc_decision(
    db: Session,
    complaint: Complaint,
    *,
    decision: str,
    notes: str | None,
    decided_on: date,
    actor: User | None,
    audit: AuditService,
    request: Request | None = None,
) -> Complaint:
    """Record the SCSC recommendation: WARNING, SHOW_CAUSE or EVC (APH 7.10c)."""
    _assert_status(complaint, ComplaintStatus.SCSC)
    key = decision.strip().upper()
    if key not in SCSC_DECISIONS:
        raise ComplaintError(
            "SCSC may only issue a WARNING, a SHOW_CAUSE notice or an EVC (APH 7.10c)."
        )
    before = _snapshot(complaint)
    complaint.scsc_decision = key
    complaint.scsc_decided_on = decided_on
    complaint.scsc_notes = notes
    if key == "WARNING":
        # A warning needs no SHC report; the EC records it as the final action.
        complaint.status = ComplaintStatus.DECIDED
        complaint.ec_decision = "WARNING"
        complaint.decided_on = decided_on
        complaint.speaking_order = (
            notes or "Warning issued to the institution after SCSC scrutiny (APH 7.10c)."
        )
    elif key == "SHOW_CAUSE":
        complaint.status = ComplaintStatus.SHOW_CAUSE
        complaint.show_cause_issued_on = decided_on
        complaint.show_cause_due_on = decided_on + timedelta(days=SHOW_CAUSE_RESPONSE_DAYS)
    else:
        # The EVC report is placed before the SHC (APH 7.10d).
        complaint.status = ComplaintStatus.HEARING
    _log(audit, actor, f"complaint.scsc.{key.lower()}", complaint, before, request)
    return complaint


def record_show_cause_reply(
    db: Session,
    complaint: Complaint,
    *,
    reply: str,
    replied_on: date,
    actor: User | None,
    audit: AuditService,
    request: Request | None = None,
) -> Complaint:
    """Record the institution's reply and refer the file to the SHC (APH 7.10d)."""
    _assert_status(complaint, ComplaintStatus.SHOW_CAUSE)
    before = _snapshot(complaint)
    complaint.show_cause_reply = reply
    complaint.show_cause_replied_on = replied_on
    complaint.status = ComplaintStatus.HEARING
    _log(audit, actor, "complaint.show_cause_reply", complaint, before, request)
    return complaint


def record_shc_hearing(
    db: Session,
    complaint: Complaint,
    *,
    hearing_on: date,
    findings: str,
    actor: User | None,
    audit: AuditService,
    request: Request | None = None,
) -> Complaint:
    """Record the SHC hearing and its findings (APH 7.10d-e)."""
    _assert_status(complaint, ComplaintStatus.HEARING)
    before = _snapshot(complaint)
    complaint.shc_hearing_on = hearing_on
    complaint.shc_findings = findings
    _log(audit, actor, "complaint.shc_hearing", complaint, before, request)
    return complaint


def record_ec_decision(
    db: Session,
    complaint: Complaint,
    *,
    decision: str,
    speaking_order: str,
    decided_on: date,
    actor: User | None,
    audit: AuditService,
    request: Request | None = None,
) -> Complaint:
    """Record the EC decision and publish it as a Speaking Order (APH 7.10f-g)."""
    _assert_status(complaint, ComplaintStatus.HEARING, ComplaintStatus.DECIDED)
    key = decision.strip().upper()
    if key not in EC_DECISIONS:
        raise ComplaintError(
            "The EC may record a WARNING, a PENAL_ACTION or CLOSE the complaint (APH 7.10f-g)."
        )
    if not speaking_order.strip():
        raise ComplaintError(
            "The EC decision must be published as a detailed Speaking Order (APH 7.10g)."
        )
    before = _snapshot(complaint)
    complaint.ec_decision = key
    complaint.speaking_order = speaking_order
    complaint.decided_on = decided_on
    complaint.status = ComplaintStatus.CLOSED if key == "CLOSE" else ComplaintStatus.DECIDED
    _log(audit, actor, f"complaint.ec.{key.lower()}", complaint, before, request)
    return complaint


def complaints_for_institution(db: Session, institution_id: uuid.UUID) -> list[Complaint]:
    """Return every complaint against one institution, newest first."""
    return list(
        db.scalars(
            select(Complaint)
            .where(Complaint.institution_id == institution_id)
            .order_by(Complaint.created_at.desc())
        ).all()
    )
