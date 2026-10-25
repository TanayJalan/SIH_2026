"""Application and program models."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    ApplicationCategory,
    ApplicationStatus,
    ApplicationTrack,
    CommitteeMode,
    DecisionType,
    WorkflowStage,
)
from app.models.types import enum_type

if TYPE_CHECKING:
    from app.models.alert import Alert
    from app.models.appeal import Appeal
    from app.models.calendar import PublicNotice
    from app.models.committee import Committee
    from app.models.complaint import PenalAction
    from app.models.compliance import ComplianceResult
    from app.models.deadline import Timer
    from app.models.decision import Decision, DecisionLetter
    from app.models.deficiency import Deficiency
    from app.models.document import Document
    from app.models.fee import FeeTransaction
    from app.models.inspection import Inspection
    from app.models.institution import Institution
    from app.models.security_deposit import SecurityDeposit
    from app.models.user import User
    from app.models.workflow import WorkflowEvent


class Application(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An AICTE approval application for an institution."""

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
        CheckConstraint("reopen_count >= 0", name="reopen_count_non_negative"),
        CheckConstraint("appeal_loop_count >= 0", name="appeal_loop_count_non_negative"),
        CheckConstraint(
            "ter_amount_paise IS NULL OR ter_amount_paise >= 0",
            name="ter_amount_paise_non_negative",
        ),
        Index("ix_applications_status_sla_due_at", "status", "sla_due_at"),
    )

    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("institutions.id"),
        nullable=False,
        index=True,
    )
    track: Mapped[ApplicationTrack] = mapped_column(
        enum_type(ApplicationTrack, "application_track", length=32),
        nullable=False,
        default=ApplicationTrack.NEW_INSTITUTION,
        server_default=ApplicationTrack.NEW_INSTITUTION.value,
        index=True,
    )
    application_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    """APH application type code; ``application_type_routes`` is authoritative."""
    category: Mapped[ApplicationCategory] = mapped_column(
        enum_type(ApplicationCategory, "application_category", length=32),
        nullable=False,
        default=ApplicationCategory.CAT1_CUTOFF,
        server_default=ApplicationCategory.CAT1_CUTOFF.value,
    )
    academic_year: Mapped[str] = mapped_column(String(9), nullable=False)
    public_notice_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("public_notices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    portal_application_no: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
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
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    """Set on final submission; the applicant can no longer edit the draft (APH 1.4.3)."""
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
    reopen_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    """A wrongly submitted application may be reopened only once (APH 2.3.3d-e)."""
    late_submission: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    ter_amount_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    """TER amount in integer paise, computed from ``fee_schedules``."""
    ter_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ter_receipt_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision_type: Mapped[DecisionType | None] = mapped_column(
        "decision",
        enum_type(DecisionType, "application_decision", length=16),
        nullable=True,
        index=True,
    )
    """Final letter type. The demo payload remains available as ``decision``."""
    speaking_order: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_uploaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    appeal_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    """Seven days from the configured appeal start event (APH 1.11a, 2.24a)."""
    appeal_loop_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    """The SAC send-back loop repeats only once (APH Annexure-7)."""
    evc_mode: Mapped[CommitteeMode | None] = mapped_column(
        enum_type(CommitteeMode, "committee_mode", length=16), nullable=True
    )
    evc_random_selected: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    """Random EVC selection for self-disclosure cases (APH 2.3.5a)."""
    loa_valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    """LoA is valid for two academic years (APH 1.10b ii)."""
    security_deposit_due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    """Proof and Affidavit 3 are due within 15 days of intimation (APH 2.25f)."""
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
    public_notice: Mapped[PublicNotice | None] = relationship(back_populates="applications")
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
    committees: Mapped[list[Committee]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    appeals: Mapped[list[Appeal]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    fee_transactions: Mapped[list[FeeTransaction]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    security_deposits: Mapped[list[SecurityDeposit]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    penal_actions: Mapped[list[PenalAction]] = relationship(back_populates="application")
    alerts: Mapped[list[Alert]] = relationship(back_populates="application")
    decisions: Mapped[list[Decision]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    decision_letters: Mapped[list[DecisionLetter]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    timers: Mapped[list[Timer]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )

    @property
    def reference(self) -> str | None:
        """Return the demo reference stored in the application data payload."""
        value = self.data.get("reference")
        return value if isinstance(value, str) else None

    @property
    def decision(self) -> dict[str, Any] | None:
        """Return the legacy decision payload stored in ``data``.

        The APH decision letter type lives in the ``decision`` column and is
        exposed as :attr:`decision_type`.
        """
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
