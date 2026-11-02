"""Security Deposit request and release with clearances (APH 6.46).

APH 6.46a-lists the documents an institution uploads for release; 6.46b then
requires clearance from the Public Grievance Redressal Cell, the Vigilance Cell
and the other cells/bureaus that track grants. A NOC follows from the Approval
Bureau for an FDR, or a sanction order from the Council for an RTGS transfer
(6.46c-d). A pending complaint or disciplinary proceeding blocks a converted
university's release (6.46g).

The service keeps the clearance list on the deposit row so the case file can
render it. Every write is audited; the caller owns the transaction.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session
from starlette.requests import Request

from app.models.enums import SecurityDepositStatus
from app.models.security_deposit import SecurityDeposit
from app.models.user import User
from app.services.audit import AuditService

CLEARANCE_CLAUSE = "APH 6.46b"

#: The clearances APH 6.46b requires. ``mandatory=False`` marks the conditional
#: NOC under 6.46e, which only applies when a government body reports dues.
CLEARANCES: tuple[dict[str, Any], ...] = (
    {
        "code": "PGRC",
        "label": "Public Grievance Redressal Cell clearance",
        "mandatory": True,
        "apH_clause": "APH 6.46b",
    },
    {
        "code": "VIGILANCE",
        "label": "Vigilance Cell clearance",
        "mandatory": True,
        "apH_clause": "APH 6.46b",
    },
    {
        "code": "GRANTS",
        "label": "Grants and other cells/bureaus clearance",
        "mandatory": True,
        "apH_clause": "APH 6.46b",
    },
    {
        "code": "GOVT_BODY_NOC",
        "label": "NOC from a Government body/bank (if dues are reported)",
        "mandatory": False,
        "apH_clause": "APH 6.46e",
    },
)

_RELEASABLE = frozenset(
    {
        SecurityDepositStatus.PAID,
        SecurityDepositStatus.PENALTY_10,
        SecurityDepositStatus.PENALTY_20,
    }
)

_DOCUMENT_CHECKLIST = (
    ("Application/request letter of the institution", "APH 6.46a(i)"),
    ("Affidavit 6 with FDR/RTGS details", "APH 6.46a(ii)"),
    ("Copy of the FDR/RPGF/online payment proof", "APH 6.46a(iii)"),
    ("Copy of the latest LoA/EoA", "APH 6.46a(iv)"),
)


class DepositReleaseError(ValueError):
    """Raised when a release step is not allowed."""


def clearance_catalogue() -> list[dict[str, Any]]:
    """Return the clearances and documents for the case-file UI."""
    return [
        {
            "clearances": [
                {
                    "code": item["code"],
                    "label": item["label"],
                    "mandatory": item["mandatory"],
                    "apH_clause": item["apH_clause"],
                }
                for item in CLEARANCES
            ],
            "documents": [
                {"label": label, "apH_clause": clause} for label, clause in _DOCUMENT_CHECKLIST
            ],
        }
    ]


def _snapshot(deposit: SecurityDeposit) -> dict[str, Any]:
    return {
        "status": deposit.status.value,
        "release_requested_on": deposit.release_requested_on.isoformat()
        if deposit.release_requested_on
        else None,
        "released_on": deposit.released_on.isoformat() if deposit.released_on else None,
        "noc_number": deposit.noc_number,
    }


def _log(
    audit: AuditService,
    actor: User | None,
    action: str,
    deposit: SecurityDeposit,
    before: dict[str, Any],
    request: Request | None,
) -> None:
    audit.log(
        actor,
        action,
        entity_type="SecurityDeposit",
        entity_id=deposit.id,
        before=before,
        after=_snapshot(deposit),
        request=request,
    )


def request_release(
    db: Session,
    deposit: SecurityDeposit,
    *,
    requested_on: date,
    actor: User | None,
    audit: AuditService,
    request: Request | None = None,
) -> SecurityDeposit:
    """Start a release request and initialise every clearance as pending (APH 6.46)."""
    if deposit.status not in _RELEASABLE:
        raise DepositReleaseError("Only a paid Security Deposit can be released (APH 6.46).")
    if deposit.release_requested_on is not None:
        raise DepositReleaseError("A release request already exists for this deposit.")
    before = _snapshot(deposit)
    deposit.release_requested_on = requested_on
    deposit.release_clearances = [
        {
            "code": item["code"],
            "label": item["label"],
            "mandatory": item["mandatory"],
            "apH_clause": item["apH_clause"],
            "status": "PENDING",
            "remarks": None,
        }
        for item in CLEARANCES
    ]
    _log(audit, actor, "security_deposit.release_requested", deposit, before, request)
    return deposit


def record_clearance(
    db: Session,
    deposit: SecurityDeposit,
    *,
    code: str,
    cleared: bool,
    remarks: str | None,
    actor: User | None,
    audit: AuditService,
    request: Request | None = None,
) -> SecurityDeposit:
    """Record one clearance decision from PGRC, Vigilance or the grants cell."""
    if deposit.release_requested_on is None:
        raise DepositReleaseError("Start a release request before recording clearances.")
    target = str(code).strip().upper()
    if target not in {item["code"] for item in CLEARANCES}:
        raise DepositReleaseError(f"{code!r} is not an APH 6.46 clearance.")
    before = _snapshot(deposit)
    # JSONB columns are plain Python lists; copy each entry so the assigned list
    # compares unequal to the old value and SQLAlchemy issues the UPDATE.
    entries = [dict(entry) for entry in (deposit.release_clearances or [])]
    updated = False
    for entry in entries:
        if entry.get("code") == target:
            entry["status"] = "CLEARED" if cleared else "BLOCKED"
            entry["remarks"] = remarks
            updated = True
    if not updated:
        raise DepositReleaseError(
            "The clearance list is missing this code; re-start the release request."
        )
    # JSONB does not track in-place mutation, so assign a new list back.
    deposit.release_clearances = entries
    _log(audit, actor, f"security_deposit.clearance.{target.lower()}", deposit, before, request)
    return deposit


def missing_clearances(deposit: SecurityDeposit) -> list[str]:
    """Return the mandatory clearances that are not yet cleared (APH 6.46b)."""
    return [
        entry["code"]
        for entry in (deposit.release_clearances or [])
        if entry.get("mandatory") and entry.get("status") != "CLEARED"
    ]


def approve_release(
    db: Session,
    deposit: SecurityDeposit,
    *,
    released_on: date,
    noc_number: str,
    actor: User | None,
    audit: AuditService,
    request: Request | None = None,
) -> SecurityDeposit:
    """Release the deposit once every mandatory clearance is in place (APH 6.46c-d)."""
    if deposit.release_requested_on is None:
        raise DepositReleaseError("Start a release request before approving release.")
    missing = missing_clearances(deposit)
    if missing:
        raise DepositReleaseError(
            "APH 6.46b requires clearance from "
            + ", ".join(missing)
            + " before the deposit can be released."
        )
    before = _snapshot(deposit)
    deposit.status = SecurityDepositStatus.RELEASED
    deposit.released_on = released_on
    deposit.noc_number = noc_number
    _log(audit, actor, "security_deposit.released", deposit, before, request)
    return deposit


def withdraw_deposit(
    db: Session,
    deposit: SecurityDeposit,
    *,
    actor: User | None,
    audit: AuditService,
    request: Request | None = None,
) -> SecurityDeposit:
    """Mark the deposit withdrawn with the application (APH 2.25f ladder)."""
    if deposit.status == SecurityDepositStatus.RELEASED:
        raise DepositReleaseError("A released deposit cannot be withdrawn.")
    before = _snapshot(deposit)
    deposit.status = SecurityDepositStatus.WITHDRAWN
    _log(audit, actor, "security_deposit.withdrawn", deposit, before, request)
    return deposit
