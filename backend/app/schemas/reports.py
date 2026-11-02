"""Report and dashboard aggregate schemas.

Every aggregate carries its governing APH clause so operators can trace each
metric back to the Approval Process Handbook. All monetary values are integer
paise; all counts come from SQL aggregations, never Python loops.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    ApplicationStatus,
    ComplianceHealth,
    DecisionLetterType,
    DecisionOutcome,
    DeficiencyStatus,
    PenalActionType,
    SecurityDepositStatus,
    TimerStatus,
)


class ReportFilters(BaseModel):
    """Global filters applied to every aggregate endpoint."""

    academic_year: str | None = Field(
        default=None, description="Filter applications by academic year."
    )
    region: str | None = Field(
        default=None, description="Filter by institution region (free text)."
    )
    state: str | None = Field(
        default=None, description="Filter by institution state."
    )
    application_type: str | None = Field(
        default=None, description="Filter by APH application type code."
    )
    track: str | None = Field(
        default=None, description="Filter by application track."
    )


# ---------------------------------------------------------------------------
# Regulation Bureau / Scrutiny dashboard
# ---------------------------------------------------------------------------


class QueueEntry(BaseModel):
    """One application in the officer's queue."""

    application_id: str
    portal_application_no: str | None
    institution_name: str
    status: ApplicationStatus
    current_stage: str
    sla_due_at: datetime | None
    days_overdue: int | None
    assigned_officer: str | None
    apH_clause: str = "APH 1.8"


class RegulationBureauDashboard(BaseModel):
    """Dashboard for REGULATION_BUREAU_OFFICER and SCRUTINY_COMMITTEE_MEMBER.

    APH 1.8 (scrutiny), APH 1.9 (inspection/EVC), APH 1.10 (Regulation Bureau
    observations).
    """

    model_config = ConfigDict(from_attributes=True)

    total_in_queue: int
    by_stage: list[dict[str, Any]]
    by_sla: list[dict[str, Any]]
    overdue_count: int
    overdue: list[QueueEntry]
    awaiting_institution_compliance: int
    upcoming_evc_dates: list[dict[str, Any]]
    average_handling_days: float | None
    apH_clause: str = "APH 1.8"


# ---------------------------------------------------------------------------
# Regional Officer / SUPER_ADMIN dashboard
# ---------------------------------------------------------------------------


class ApplicationByTrackState(BaseModel):
    track: str
    state: str
    count: int


class FunnelEntry(BaseModel):
    stage: str
    count: int


class ApprovalVsRejection(BaseModel):
    approvals: int  # LOA / EOA
    rejections: int  # LOD / LOR
    pending: int


class AppealOutcome(BaseModel):
    filed: int
    within_deadline: int
    sac_recommend: int
    sac_not_recommend: int
    sac_send_back: int
    council_allowed: int
    council_dismissed: int


class SecurityDepositPending(BaseModel):
    application_id: str
    portal_application_no: str | None
    institution_name: str
    status: SecurityDepositStatus
    penalty_percent: int | None
    due_on: date | None
    apH_clause: str = "APH 2.25f"


class LoaExpiring(BaseModel):
    application_id: str
    portal_application_no: str | None
    institution_name: str
    valid_until: date
    days_left: int
    apH_clause: str = "APH 1.10b"


class InstitutionCompliance(BaseModel):
    institution_id: str
    name: str
    state: str
    region: str
    score: float
    status: ComplianceHealth
    apH_clause: str = "APH 7.13"


class ViolationCode(BaseModel):
    code: str
    count: int


class FacultyRatioDeficit(BaseModel):
    institution_id: str
    name: str
    student_faculty_ratio: float | None
    required_ratio: float | None
    deficit: float | None
    apH_clause: str = "APH 6.14"


class DeficiencyCategory(BaseModel):
    category: str
    count: int


class SlaBreach(BaseModel):
    total_with_sla: int
    breached: int
    breach_rate: float


class Escalation(BaseModel):
    application_id: str
    portal_application_no: str | None
    institution_name: str
    level: int
    apH_clause: str = "APH 7.13"


class ComplaintStatusCount(BaseModel):
    status: str
    count: int


class PenalActionByType(BaseModel):
    action_type: str
    count: int


class AverageDaysPerStage(BaseModel):
    stage: str
    average_days: float


class RegionalDashboard(BaseModel):
    """Dashboard for REGIONAL_OFFICER and SUPER_ADMIN.

    Covers APH 1.8-1.11 (workflow funnel), APH 2.23-2.25 (decisions, appeals,
    deposits), APH 6.14 (faculty ratio), APH 7.3-7.4 (penal actions),
    APH 7.10 (complaints), APH 7.13 (compliance monitoring).
    """

    model_config = ConfigDict(from_attributes=True)

    total_applications: int
    by_track_state: list[ApplicationByTrackState]
    funnel: list[FunnelEntry]
    approval_vs_rejection: ApprovalVsRejection
    appeals: AppealOutcome
    appeal_windows_closing_3_days: int
    security_deposits_pending: list[SecurityDepositPending]
    loa_expiring_6_months: list[LoaExpiring]
    institutions_by_compliance: list[InstitutionCompliance]
    top_violation_codes: list[ViolationCode]
    faculty_ratio_deficit: list[FacultyRatioDeficit]
    deficiency_categories: list[DeficiencyCategory]
    sla_breach: SlaBreach
    escalations: list[Escalation]
    complaints_by_status: list[ComplaintStatusCount]
    penal_actions_by_type: list[PenalActionByType]
    average_days_per_stage: list[AverageDaysPerStage]
    apH_clause: str = "APH 1.10"


# ---------------------------------------------------------------------------
# Institution Admin dashboard
# ---------------------------------------------------------------------------


class OpenDeficiency(BaseModel):
    deficiency_id: str
    category: str
    description: str
    due_date: date
    days_left: int
    apH_clause: str = "APH 2.3.3b"


class FeePosition(BaseModel):
    total_paise: int
    paid_paise: int
    refunded_paise: int
    due_paise: int


class ExpiringDocument(BaseModel):
    document_id: str
    doc_type: str
    filename: str
    expiry_date: date | None
    valid_until: date | None
    days_left: int | None
    apH_clause: str = "APH 6.17h"


class MandatoryDisclosure(BaseModel):
    present: bool
    url: str | None


class FailingRule(BaseModel):
    code: str
    name: str
    message: str | None
    fix_text: str | None
    apH_clause: str


class UpcomingDeadline(BaseModel):
    key: str
    label: str
    due_on: date | None
    days_left: int | None
    apH_clause: str


class InstitutionDashboard(BaseModel):
    """Dashboard for INSTITUTION_ADMIN.

    Covers APH 1.4 (application), APH 2.3.3b (deficiencies), APH 4 (fees),
    APH 6.17h (documents), APH 7.4 (violation/fix guidance).
    """

    model_config = ConfigDict(from_attributes=True)

    portal_application_no: str | None
    application_id: str | None
    institution_name: str
    status: ApplicationStatus
    open_deficiencies: list[OpenDeficiency]
    fees: FeePosition
    expiring_documents: list[ExpiringDocument]
    mandatory_disclosure: MandatoryDisclosure
    compliance_score: float | None
    top_failing_rules: list[FailingRule]
    upcoming_deadlines: list[UpcomingDeadline]
    apH_clause: str = "APH 1.4"


# ---------------------------------------------------------------------------
# Application PDF report
# ---------------------------------------------------------------------------


class ReportApplication(BaseModel):
    """Summary payload for the per-application PDF report."""

    application_id: str
    portal_application_no: str | None
    institution_name: str
    track: str
    application_type: str
    academic_year: str
    status: ApplicationStatus
    current_stage: str
    submitted_at: datetime | None
    decision_type: str | None
    decision_uploaded_at: datetime | None
    compliance_score: float | None
    apH_clause: str = "APH 1.4"


class ReportTimelineEvent(BaseModel):
    created_at: datetime
    action: str | None
    from_status: str | None
    to_status: str | None
    actor_name: str | None
    apH_clause: str


class ReportDecision(BaseModel):
    body: str | None
    outcome: str | None
    decided_on: date | None
    quorum_met: bool
    apH_clause: str


class ReportFee(BaseModel):
    kind: str
    amount_paise: int
    paid_at: datetime | None
    apH_clause: str


class ReportCompliance(BaseModel):
    code: str
    name: str
    status: str
    message: str | None
    apH_clause: str


class ReportDeficiency(BaseModel):
    category: str
    description: str
    status: DeficiencyStatus
    due_date: date
    apH_clause: str = "APH 2.3.3b"


class ApplicationReport(BaseModel):
    """Full summary for ``GET /reports/application/{id}.pdf``."""

    application: ReportApplication
    timeline: list[ReportTimelineEvent]
    decisions: list[ReportDecision]
    fees: list[ReportFee]
    compliance: list[ReportCompliance]
    deficiencies: list[ReportDeficiency]
    apH_clause: str = "APH 1.4"
