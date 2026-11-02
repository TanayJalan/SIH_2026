"""Pydantic schemas for complaints, penal actions and Security Deposit release.

APH 7.10 (complaints), APH 7.3/7.4/7.1b/7.11 (penal actions and restoration) and
APH 6.46 (Security Deposit release).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Complaints
# ---------------------------------------------------------------------------


class ComplaintCreate(BaseModel):
    """Intake for a complaint (APH 7.10b)."""

    application_id: uuid.UUID | None = None
    institution_id: uuid.UUID | None = Field(
        default=None,
        description="Required only for super admins; institution users are scoped.",
    )
    source: str = Field(default="PORTAL", min_length=1, max_length=64)
    category: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1)
    received_on: date | None = None
    complainant_name: str | None = Field(default=None, max_length=255)
    complainant_contact: str | None = Field(default=None, max_length=255)
    is_anonymous: bool = False


class ScscDecisionRequest(BaseModel):
    """SCSC recommendation (APH 7.10c)."""

    decision: str = Field(description="WARNING, SHOW_CAUSE or EVC")
    notes: str | None = None
    decided_on: date | None = None


class ShowCauseReplyRequest(BaseModel):
    """Institution reply to a show-cause notice (APH 7.10d)."""

    reply: str = Field(min_length=1)
    replied_on: date | None = None


class ShcHearingRequest(BaseModel):
    """SHC hearing record (APH 7.10d-e)."""

    hearing_on: date
    findings: str = Field(min_length=1)


class EcDecisionRequest(BaseModel):
    """EC decision with its Speaking Order (APH 7.10f-g)."""

    decision: str = Field(description="WARNING, PENAL_ACTION or CLOSE")
    speaking_order: str = Field(min_length=1)
    decided_on: date | None = None


class ComplaintRead(BaseModel):
    """One complaint with its full lifecycle."""

    id: uuid.UUID
    institution_id: uuid.UUID
    application_id: uuid.UUID | None
    source: str
    status: str
    category: str
    description: str
    received_on: date | None
    complainant_name: str | None
    complainant_contact: str | None
    complainant_verified: bool
    rejection_reason: str | None
    rejection_clause: str | None
    is_anonymous: bool
    scsc_decision: str | None
    scsc_decided_on: date | None
    scsc_notes: str | None
    show_cause_issued_on: date | None
    show_cause_due_on: date | None
    show_cause_reply: str | None
    show_cause_replied_on: date | None
    shc_hearing_on: date | None
    shc_findings: str | None
    ec_decision: str | None
    speaking_order: str | None
    decided_on: date | None
    apH_clause: str
    needs_verification: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ComplaintPage(BaseModel):
    """Paginated complaints."""

    items: list[ComplaintRead]
    total: int
    page: int
    page_size: int
    pages: int


class ComplaintLifecycleStep(BaseModel):
    """One visible complaint step."""

    key: str
    label: str
    apH_clause: str


class ComplaintCatalogue(BaseModel):
    """The lifecycle and the anonymity rule the UI renders."""

    steps: list[ComplaintLifecycleStep]
    anonymity_clause: str
    anonymity_reason: str
    scsc_decisions: dict[str, str]
    ec_decisions: dict[str, str]


# ---------------------------------------------------------------------------
# Penal actions
# ---------------------------------------------------------------------------


class PenalActionCreate(BaseModel):
    """Record a draft APH 7.3 action for an APH 7.4 violation."""

    action_type: str
    violation_code: str = Field(
        min_length=1,
        max_length=8,
        description="APH 7.4 letter a-n, or the full 7.4x code.",
    )
    application_id: uuid.UUID | None = None
    complaint_id: uuid.UUID | None = None
    effective_academic_year: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")


class PenalActionHearingRequest(BaseModel):
    """Schedule the mandatory pre-action hearing (APH 6.50h proviso)."""

    hearing_on: date
    notes: str | None = None


class PenalActionIssueRequest(BaseModel):
    """Issue the action after its hearing (APH 6.50h, 7.10g)."""

    order_number: str = Field(min_length=1, max_length=64)
    issued_on: date | None = None
    speaking_order: str = Field(min_length=1)


class RestorationRequest(BaseModel):
    """Request restoration against a punitive action (APH 7.11a)."""

    requested_on: date | None = None


class PenalActionRead(BaseModel):
    """One penal action with its hearing, fine and consequences."""

    id: uuid.UUID
    institution_id: uuid.UUID
    complaint_id: uuid.UUID | None
    application_id: uuid.UUID | None
    action_type: str
    violation_code: str
    order_number: str | None
    issued_on: date | None
    hearing_on: date | None
    hearing_notes: str | None
    hearing_done: bool
    speaking_order: str | None
    fine_paise: int | None
    fine_basis: str | None
    consequences: dict[str, Any] | None
    restoration_requested_on: date | None
    restoration_eligible_from: date | None
    restoration_status: str | None
    effective_academic_year: str | None
    apH_clause: str
    needs_verification: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ExcessAdmissionFineRead(BaseModel):
    """The APH 7.3g fine preview for one application."""

    academic_year: str
    excess_admissions: int
    annual_fee_paise: int
    total_course_fee_paise: int
    fine_paise: int
    lines: list[dict[str, Any]]
    apH_clause: str


# ---------------------------------------------------------------------------
# Security Deposit release (APH 6.46)
# ---------------------------------------------------------------------------


class DepositClearanceRequest(BaseModel):
    """Record one clearance from PGRC, Vigilance or the grants cell."""

    code: str
    cleared: bool
    remarks: str | None = None


class DepositReleaseRequest(BaseModel):
    """Institution request to release the Security Deposit (APH 6.46a)."""

    requested_on: date | None = None


class DepositReleaseApproveRequest(BaseModel):
    """Approve the release with the NOC number (APH 6.46c-d)."""

    noc_number: str = Field(min_length=1, max_length=64)
    released_on: date | None = None


class SecurityDepositRead(BaseModel):
    """One Security Deposit row with its release state."""

    id: uuid.UUID
    institution_id: uuid.UUID
    application_id: uuid.UUID | None
    programme_family: str
    level: str
    required_paise: int
    doubled_for_leased: bool
    created_on: date
    maturity_on: date
    status: str
    penalty_percent: int | None
    release_requested_on: date | None
    release_clearances: list[dict[str, Any]] | None
    released_on: date | None
    noc_number: str | None
    apH_clause: str
    needs_verification: bool

    model_config = {"from_attributes": True}
