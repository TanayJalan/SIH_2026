"""Application and program models."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ApplicationStatus, ApplicationType, WorkflowStage
from app.models.types import enum_type

if TYPE_CHECKING:
    from app.models.alert import Alert
    from app.models.compliance import ComplianceResult
    from app.models.deficiency import Deficiency
    from app.models.document import Document
    from app.models.inspection import Inspection
    from app.models.institution import Institution
    from app.models.user import User
    from app.models.workflow import WorkflowEvent


class Application(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A New/Extension approval application for an institution."""

    __tablename__ = "applications"
    __table_args__ = (
        CheckConstraint(
            "risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 100)",
            name="risk_score_range",
        ),
        CheckConstraint(
            "compliance_score IS NULL OR (compliance_score >= 0 AND compliance_score <= 100)",
            name="compliance_score_range",
        ),
        Index("ix_applications_status_sla_due_at", "status", "sla_due_at"),
    )

    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("institutions.id"),
        nullable=False,
        index=True,
    )
    application_type: Mapped[ApplicationType] = mapped_column(
        enum_type(ApplicationType, "application_type", length=16),
        nullable=False,
    )
    academic_year: Mapped[str] = mapped_column(String(9), nullable=False)
    status: Mapped[ApplicationStatus] = mapped_column(
        enum_type(ApplicationStatus, "application_status", length=32),
        nullable=False,
        default=ApplicationStatus.DRAFT,
        server_default=ApplicationStatus.DRAFT.value,
        index=True,
    )
    current_stage: Mapped[WorkflowStage] = mapped_column(
        enum_type(WorkflowStage, "workflow_stage", length=32),
        nullable=False,
        default=WorkflowStage.APPLICATION,
        server_default=WorkflowStage.APPLICATION.value,
    )
    assigned_officer_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stage_entered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sla_due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    is_withdrawn: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    is_escalated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    risk_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    compliance_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    institution: Mapped[Institution] = relationship(back_populates="applications")
    assigned_officer: Mapped[User | None] = relationship(back_populates="assigned_applications")
    programs: Mapped[list[ApplicationProgram]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    documents: Mapped[list[Document]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    workflow_events: Mapped[list[WorkflowEvent]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    deficiencies: Mapped[list[Deficiency]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    inspections: Mapped[list[Inspection]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    compliance_results: Mapped[list[ComplianceResult]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    alerts: Mapped[list[Alert]] = relationship(back_populates="application")

    @property
    def reference(self) -> str | None:
        """Return the demo reference stored in the application data payload."""
        value = self.data.get("reference")
        return value if isinstance(value, str) else None

    @property
    def decision(self) -> dict[str, Any] | None:
        """Return the recorded decision payload, if a decision was made."""
        value = self.data.get("decision")
        return value if isinstance(value, dict) else None


class ApplicationProgram(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A programme requested in an application."""

    __tablename__ = "application_programs"
    __table_args__ = (
        CheckConstraint("intake >= 0", name="intake_non_negative"),
        CheckConstraint("faculty_count >= 0", name="faculty_count_non_negative"),
        CheckConstraint("lab_count >= 0", name="lab_count_non_negative"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    program_name: Mapped[str] = mapped_column(String(255), nullable=False)
    level: Mapped[str] = mapped_column(String(32), nullable=False)
    intake: Mapped[int] = mapped_column(Integer, nullable=False)
    faculty_count: Mapped[int] = mapped_column(Integer, nullable=False)
    lab_count: Mapped[int] = mapped_column(Integer, nullable=False)

    application: Mapped[Application] = relationship(back_populates="programs")
