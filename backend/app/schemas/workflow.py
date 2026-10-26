"""Workflow action, timeline and deficiency/inspection API schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    ApplicationStatus,
    CommitteeMode,
    DecisionBody,
    DecisionLetterType,
    DecisionOutcome,
    DeficiencyStatus,
    InspectionRecommendation,
    InspectionStatus,
    Role,
    WorkflowAction,
    WorkflowStage,
)
from app.schemas.application import ApplicationDetailRead


class DeficiencyCreate(BaseModel):
    """One deficiency raised during scrutiny."""

    category: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=4000)
    due_date: date


class DeficiencyResponseInput(BaseModel):
    """An institution's response to one open deficiency."""

    deficiency_id: uuid.UUID
    response_text: str = Field(min_length=1, max_length=8000)
    document_id: uuid.UUID | None = None


class InspectionReportInput(BaseModel):
    """Structured inspection findings submitted by a committee member."""

    infrastructure_ok: bool
    faculty_verified: bool
    lab_verified: bool
    observations: str = Field(min_length=1, max_length=8000)
    recommendation: InspectionRecommendation


class WorkflowActionRequest(BaseModel):
    """Payload accepted by the generic workflow action endpoint.

    Only the fields relevant to the selected action are read by the workflow
    service; unrelated fields are ignored. This keeps one strongly validated
    contract for every action while still allowing action-specific forms.
    """

    comment: str | None = Field(default=None, max_length=4000)
    officer_id: uuid.UUID | None = None
    deficiencies: list[DeficiencyCreate] = Field(default_factory=list, max_length=20)
    responses: list[DeficiencyResponseInput] = Field(default_factory=list, max_length=50)
    deficiency_id: uuid.UUID | None = None
    committee_id: uuid.UUID | None = None
    scheduled_on: datetime | None = None
    evc_mode: CommitteeMode | None = None
    report: InspectionReportInput | None = None

    # Expert Visit Committee evidence (APH 1.9f-g).
    video_url: str | None = Field(default=None, max_length=1024)
    video_minutes: int | None = Field(default=None, ge=0, le=600)

    # Regulation Bureau, EC, SAC and Council decisions.
    notes: str | None = Field(default=None, max_length=8000)
    observations: str | None = Field(default=None, max_length=8000)
    decision: DecisionOutcome | None = None
    sac_recommendation: DecisionOutcome | None = None
    shc_outcome: DecisionOutcome | None = None
    quorum_met: bool = False
    speaking_order: str | None = Field(default=None, max_length=8000)

    # Security Deposit and Affidavit 3 (APH 2.25f).
    deposit_receipt_no: str | None = Field(default=None, max_length=128)
    affidavit3_filed: bool = False

    # Appeals and track-specific facts.
    appeal_text: str | None = Field(default=None, max_length=8000)
    approved_intake: int | None = Field(default=None, ge=0)
    random_evc: bool | None = None
    closure_failed: bool | None = None
    pending_court_case: bool = False
    charge_sheet_pending: bool = False


class AppealFileRequest(BaseModel):
    """The single appeal an institution may file against an LoD or LoR."""

    appeal_text: str = Field(min_length=1, max_length=8000)
    comment: str | None = Field(default=None, max_length=4000)


class WorkflowEventRead(BaseModel):
    """One entry in an application's workflow timeline."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    from_status: ApplicationStatus | None
    to_status: ApplicationStatus
    action: str | None
    actor_id: uuid.UUID | None
    actor_name: str | None = None
    comment: str | None
    details: dict[str, Any] | None
    apH_clause: str
    created_at: datetime


class WorkflowTimelineRead(BaseModel):
    """Timeline and current workflow position for an application."""

    application_id: uuid.UUID
    status: ApplicationStatus
    current_stage: WorkflowStage
    stage_entered_at: datetime | None
    sla_due_at: datetime | None
    is_withdrawn: bool
    is_escalated: bool
    events: list[WorkflowEventRead]


class AllowedActionRead(BaseModel):
    """One action available to the current user at this workflow state."""

    action: WorkflowAction
    label: str
    description: str
    requires: Literal[
        "none",
        "deficiencies",
        "responses",
        "deficiency_id",
        "inspection_schedule",
        "inspection_report",
        "video",
        "decision",
        "shc_outcome",
        "deposit",
    ]
    tone: Literal["primary", "secondary", "danger"]


class AllowedActionsRead(BaseModel):
    """Actions the current user may perform on an application."""

    application_id: uuid.UUID
    status: ApplicationStatus
    current_stage: WorkflowStage
    is_withdrawn: bool
    actions: list[AllowedActionRead]


class DeficiencyRead(BaseModel):
    """One application deficiency and its institution response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    category: str
    description: str
    status: DeficiencyStatus
    due_date: date
    raised_by: uuid.UUID
    raised_by_name: str | None = None
    response_text: str | None
    response_document_id: uuid.UUID | None
    response_document_filename: str | None = None
    responded_at: datetime | None
    closed_at: datetime | None
    created_at: datetime


class InspectionRead(BaseModel):
    """A scheduled or completed inspection and its structured report."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    committee_id: uuid.UUID
    committee_name: str | None = None
    scheduled_on: datetime
    status: InspectionStatus
    report: dict[str, Any] | None
    recommendation: str | None
    created_at: datetime


class CommitteeMemberRead(BaseModel):
    """An inspection committee member who can be assigned to a visit."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    role: Role
    region: str | None


class WorkflowActionRead(BaseModel):
    """Result of one successful workflow action."""

    application: ApplicationDetailRead
    events: list[WorkflowEventRead]
    message: str


class DecisionRead(BaseModel):
    """One recorded decision or recommendation of a body."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    body: DecisionBody
    outcome: DecisionOutcome
    decided_on: date
    quorum_met: bool
    notes: str
    apH_clause: str
    created_at: datetime


class DecisionLetterRead(BaseModel):
    """A letter published on the portal, with its statutory clocks."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    decision_id: uuid.UUID | None
    letter_type: DecisionLetterType
    letter_number: str
    issued_on: date
    published_at: datetime | None
    appeal_clock_start: datetime | None
    appeal_deadline: datetime | None
    body_text: str
    acknowledged_at: datetime | None
    download_url: str | None = None


class AppealRead(BaseModel):
    """The single appeal filed by an institution."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    filed_at: datetime | None
    within_deadline: bool
    loop_no: int
    sac_recommendation: str | None
    council_decision: str | None
    decided_at: datetime | None
    apH_clause: str


class WorkflowStateRead(BaseModel):
    """One state of a workflow definition."""

    model_config = ConfigDict(from_attributes=True)

    code: ApplicationStatus
    label: str
    stage: WorkflowStage
    is_initial: bool
    is_terminal: bool
    sort_order: int
    description: str
    apH_clause: str
    needs_verification: bool


class WorkflowTransitionRead(BaseModel):
    """One legal edge of a workflow definition."""

    model_config = ConfigDict(from_attributes=True)

    from_state: ApplicationStatus
    to_state: ApplicationStatus
    action: str
    label: str
    description: str
    allowed_roles: list[Role]
    guard_expr: list[str]
    side_effects: list[str]
    requires: str
    tone: str
    sla_stage: WorkflowStage | None
    priority: int
    apH_clause: str
    needs_verification: bool


class WorkflowDefinitionRead(BaseModel):
    """A complete workflow definition, ordered for rendering."""

    key: str
    label: str
    track: str
    description: str
    config: dict[str, Any]
    apH_clause: str
    needs_verification: bool
    states: list[WorkflowStateRead]
    transitions: list[WorkflowTransitionRead]


class WorkflowDiagramRead(BaseModel):
    """A Mermaid rendering of one or more workflow definitions."""

    definitions: list[str]
    mermaid: str
