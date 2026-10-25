"""Application, programme, document and checklist API schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (
    ApplicationCategory,
    ApplicationStatus,
    ApplicationTrack,
    DecisionType,
    DocumentVerificationStatus,
    Role,
    WorkflowStage,
)
from app.schemas.application_sections import ApplicationData
from app.schemas.institution import InstitutionSummary


class OfficerSummary(BaseModel):
    """Public identity of the officer assigned to an application."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    role: Role


class ApplicationRead(BaseModel):
    """An application visible to the current user."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reference: str | None
    institution_id: uuid.UUID
    institution: InstitutionSummary
    track: ApplicationTrack
    application_type: str
    category: ApplicationCategory
    portal_application_no: str | None = None
    academic_year: str
    status: ApplicationStatus
    current_stage: WorkflowStage
    assigned_officer_id: uuid.UUID | None
    submitted_at: datetime | None
    locked_at: datetime | None = None
    stage_entered_at: datetime | None
    sla_due_at: datetime | None
    is_withdrawn: bool
    is_escalated: bool
    reopen_count: int = 0
    late_submission: bool = False
    ter_amount_paise: int | None = None
    ter_paid_at: datetime | None = None
    ter_receipt_no: str | None = None
    decision_type: DecisionType | None = None
    decision_uploaded_at: datetime | None = None
    appeal_deadline: datetime | None = None
    risk_score: Decimal | None
    compliance_score: Decimal | None
    created_at: datetime
    updated_at: datetime


class ApplicationPage(BaseModel):
    """Paginated applications."""

    items: list[ApplicationRead]
    total: int
    page: int
    page_size: int
    pages: int


class ApplicationCreate(BaseModel):
    """Fields accepted when an institution starts a draft.

    ``application_type`` is an APH code from Table 2.3. The authoritative
    routing table (``application_type_routes``) is checked by the workspace
    service, so an administrator can add a type without a code change.
    """

    application_type: str = Field(min_length=1, max_length=64)
    academic_year: str = Field(pattern=r"^\d{4}-\d{2}$")
    track: ApplicationTrack | None = None
    category: ApplicationCategory | None = None

    @field_validator("academic_year")
    @classmethod
    def _validate_academic_year(cls, value: str) -> str:
        start_year = int(value[:4])
        end_year = int(value[5:])
        if end_year != (start_year + 1) % 100:
            raise ValueError("academic_year must span two consecutive years")
        return value


class ApplicationUpdate(BaseModel):
    """A partial section update; omitted sections remain unchanged."""

    data: ApplicationData


class ApplicationProgramCreate(BaseModel):
    """Fields accepted when adding a programme to a draft."""

    program_name: str = Field(min_length=1, max_length=255)
    level: str = Field(min_length=1, max_length=32)
    intake: int = Field(ge=0)
    faculty_count: int = Field(ge=0)
    lab_count: int = Field(ge=0)


class ApplicationProgramUpdate(BaseModel):
    """Fields accepted when editing a programme on a draft."""

    program_name: str | None = Field(default=None, min_length=1, max_length=255)
    level: str | None = Field(default=None, min_length=1, max_length=32)
    intake: int | None = Field(default=None, ge=0)
    faculty_count: int | None = Field(default=None, ge=0)
    lab_count: int | None = Field(default=None, ge=0)


class ApplicationProgramRead(BaseModel):
    """A programme requested in an application."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    program_name: str
    level: str
    intake: int
    faculty_count: int
    lab_count: int


class ApplicationDetailRead(ApplicationRead):
    """An application with its editable form data and programmes."""

    data: ApplicationData
    programs: list[ApplicationProgramRead]
    assigned_officer: OfficerSummary | None = None
    decision: dict[str, Any] | None = None


class DocumentRead(BaseModel):
    """Metadata for one uploaded document version."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    doc_type: str
    filename: str
    content_type: str
    size_bytes: int
    version: int
    verification_status: DocumentVerificationStatus
    verification_reason: str | None = None
    uploaded_by: uuid.UUID
    created_at: datetime
    download_url: str


class ChecklistDocument(BaseModel):
    """One row in the required-document checklist."""

    doc_type: str
    label: str
    mandatory: bool
    uploaded: bool
    document_id: uuid.UUID | None = None
    filename: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    version: int | None = None
    verification_status: DocumentVerificationStatus | None = None
    verification_reason: str | None = None
    uploaded_at: datetime | None = None
    download_url: str | None = None


class DocumentChecklistRead(BaseModel):
    """Upload status for every document rule of an application type."""

    application_id: uuid.UUID
    documents: list[ChecklistDocument]
    required_count: int
    uploaded_count: int
    percentage: int


class ChecklistSection(BaseModel):
    """Completeness status for one form section."""

    key: str
    label: str
    complete: bool
    missing_fields: list[str]


class MissingItem(BaseModel):
    """A readable reason why an application cannot be submitted."""

    code: str
    section: str
    message: str


class ApplicationChecklistRead(BaseModel):
    """Combined section and document readiness for the wizard sidebar."""

    application_id: uuid.UUID
    sections: list[ChecklistSection]
    documents: list[ChecklistDocument]
    required_items: int
    completed_items: int
    percentage: int
    can_submit: bool
    missing: list[MissingItem]


class ApplicationSubmitResponse(BaseModel):
    """Result of a successful submission."""

    application: ApplicationDetailRead
    submitted_at: datetime
    sla_due_at: datetime
    message: str = "Application submitted successfully"
