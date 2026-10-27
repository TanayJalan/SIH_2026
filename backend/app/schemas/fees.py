"""Schemas for application-type routing, fees, refunds and the Deficiency Report."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ApplicationCategory, FeeKind, Severity
from app.schemas.compliance import PenalActionSuggestionRead


class FeeLineRead(BaseModel):
    """One priced line in a fee quotation."""

    item_code: str
    label: str
    unit: str
    units: int
    unit_amount_paise: int
    amount_paise: int
    apH_clause: str
    needs_verification: bool = False


class FeeQuoteRead(BaseModel):
    """The computed TER and penalty position for one application."""

    application_id: uuid.UUID
    application_no: str | None
    academic_year: str
    institution_class: str
    currency: str = "INR"
    lines: list[FeeLineRead]
    total_paise: int
    paid_paise: int
    refunded_paise: int
    due_paise: int
    is_paid: bool
    late_submission: bool
    ter_receipt_no: str | None
    ter_paid_at: datetime | None
    payment_required_for_submission: bool
    notes: list[str] = Field(default_factory=list)


class FeePaymentRequest(BaseModel):
    """Simulated gateway confirmation."""

    payment_method: Literal["SIMULATED"] = "SIMULATED"
    confirm: bool = True


class FeeTransactionRead(BaseModel):
    """One immutable money movement attached to an application."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    item_code: str
    amount_paise: int
    kind: FeeKind
    receipt_no: str | None
    paid_at: datetime | None
    apH_clause: str
    needs_verification: bool


class FeePaymentResultRead(BaseModel):
    """The updated quote plus the transactions created by a payment."""

    quote: FeeQuoteRead
    transactions: list[FeeTransactionRead]


class RefundRequest(BaseModel):
    """A documented refund reason (APH 1.4.2h, 2.3.3f, Chapter VIII)."""

    reason: Literal[
        "SCRUTINY_REJECTED_NO_APPEAL",
        "REVOKED_AFTER_PAYMENT",
        "EXCESS_PAYMENT",
    ]
    note: str | None = Field(default=None, max_length=2000)


class RefundResultRead(BaseModel):
    """The refund transaction; it is never netted against a later payment."""

    transaction: FeeTransactionRead
    refundable_paise: int
    retained_paise: int
    note: str


class SecurityDepositLineRead(BaseModel):
    """One programme's Security Deposit, doubled when the campus is leased."""

    programme_family: str
    level: str
    base_paise: int
    leased: bool
    deposit_paise: int
    penalty_percent: int
    total_due_paise: int
    apH_clause: str
    needs_verification: bool


class SecurityDepositQuoteRead(BaseModel):
    """The post-LoA Security Deposit position for an application."""

    application_id: uuid.UUID
    as_of: date
    intimation_on: date | None
    lines: list[SecurityDepositLineRead]
    total_base_paise: int
    total_due_paise: int
    penalty_windows: str
    notes: list[str] = Field(default_factory=list)



class RouteStepRead(BaseModel):
    """One APH workflow step and whether the selected type follows it."""

    key: str
    label: str
    applies: bool
    description: str
    apH_clause: str


class RouteDocumentRead(BaseModel):
    """One required/conditional document for the selected type."""

    doc_code: str | None
    doc_type: str
    label: str
    mandatory: bool
    condition_expr: str | None
    apH_clause: str
    needs_verification: bool


class ApplicationTypeRouteRead(BaseModel):
    """The selector card for one application type."""

    type: str
    label: str
    category: ApplicationCategory
    year_round: bool
    cutoff_applies: bool
    cutoff_on: date | None
    steps: list[RouteStepRead]
    required_documents: list[RouteDocumentRead]
    ter_item_code: str | None
    ter_label: str | None
    ter_unit: str | None
    ter_unit_amount_paise: int | None
    ter_note: str
    apH_clause: str
    needs_verification: bool


class DeficiencyReportItemRead(BaseModel):
    """One failed or not-yet-assessed compliance rule in the report."""

    code: str
    name: str
    category: str
    severity: Severity
    status: str
    message: str
    apH_clause: str
    needs_verification: bool
    mandatory: bool = True
    illustrative: bool = False
    """True for project-only demo thresholds, not AICTE norms."""
    unit: str | None = None
    observed_value: float | None = None
    explanation: dict[str, Any] = Field(default_factory=dict)
    penal_action_suggestions: list[PenalActionSuggestionRead] = Field(
        default_factory=list
    )
    """Advisory APH 7.3 actions; a hearing and speaking order remain mandatory."""


class DeficiencyReportRead(BaseModel):
    """A printable Deficiency Report or a Nil Deficiency banner."""

    application_id: uuid.UUID
    application_no: str | None
    academic_year: str
    generated_at: datetime
    nil_deficiency: bool
    banner: str
    items: list[DeficiencyReportItemRead]
    passed_count: int
    failed_count: int
    not_assessed_count: int
    mandatory_failed_count: int = 0
    mandatory_missing_count: int = 0
    illustrative_failed_count: int = 0
    score: float
    status: str
    include_not_assessed: bool
    apH_clause: str = "APH 2.3.3b"


class ReopenRequest(BaseModel):
    """Regulation Bureau request to reopen a wrongly submitted application once."""

    reason: str = Field(min_length=10, max_length=2000)
    trust_resolution_reference: str | None = Field(default=None, max_length=255)
    late_penalty_acknowledged: bool = True


class ReopenResultRead(BaseModel):
    """The reopened application, its new TER/penalty quote and transactions."""

    application_id: uuid.UUID
    reopen_count: int
    status: str
    quote: FeeQuoteRead
    transactions: list[FeeTransactionRead]
    message: str
