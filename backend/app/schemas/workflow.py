"""Workflow action, timeline and deficiency/inspection API schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    ApplicationStatus,
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
    report: InspectionReportInput | None = None
    conditions: str | None = Field(default=None, max_length=4000)


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
        "conditions",
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
