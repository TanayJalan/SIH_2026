"""Compliance rules and evaluation results."""

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
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ComplianceHealth, Severity
from app.models.types import enum_type

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.institution import Institution


class ComplianceRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A configurable norm evaluated against an application or institution."""

    __tablename__ = "compliance_rules"
    __table_args__ = (
        CheckConstraint(
            "operator IN ('<', '<=', '=', '==', '>=', '>', '!=', 'BETWEEN', 'EXISTS')",
            name="operator_allowed",
        ),
        Index("ix_compliance_rules_category_active", "category", "is_active"),
    )

    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    metric_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    operator: Mapped[str] = mapped_column(String(8), nullable=False)
    threshold: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    """Lower bound (BETWEEN), the single bound for comparison operators, or the
    nominal marker for EXISTS."""
    threshold_max: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4), nullable=True
    )
    """Upper bound for the BETWEEN operator; ignored otherwise."""
    severity: Mapped[Severity] = mapped_column(
        enum_type(Severity, "severity", length=16), nullable=False, index=True
    )
    applies_to: Mapped[str] = mapped_column(String(64), nullable=False)
    applies_to_family: Mapped[str | None] = mapped_column(String(64), nullable=True)
    """Programme family the rule applies to; ``None`` means every family."""
    applies_to_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    """Level the rule applies to; ``None`` means every level."""
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    apH_clause: Mapped[str] = mapped_column(String(64), nullable=False)
    # APH clause this rule comes from, for example "APH 6.14a".
    needs_verification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    # Set when the clause could not be found in APH_SPEC; see OPEN_QUESTIONS.md.

    results: Mapped[list[ComplianceResult]] = relationship(back_populates="rule")


class ComplianceResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The outcome of evaluating one rule at a point in time."""

    __tablename__ = "compliance_results"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PASS', 'FAIL', 'NOT_ASSESSED')",
            name="status_allowed",
        ),
        Index(
            "ix_compliance_results_application_rule",
            "application_id",
            "rule_id",
        ),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("institutions.id"),
        nullable=False,
        index=True,
    )
    rule_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("compliance_rules.id"),
        nullable=False,
        index=True,
    )
    observed_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    """``None`` when the metric could not be derived from the application data."""
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="PASS", server_default="PASS"
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    """Human-readable explanation captured at evaluation time."""
    evidence: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    """The values the decision was based on, for example observed and threshold."""
    explanation: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    """Structured explanation: criteria, values, pass/fail and APH clause."""
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    application: Mapped[Application] = relationship(back_populates="compliance_results")
    institution: Mapped[Institution] = relationship(back_populates="compliance_results")
    rule: Mapped[ComplianceRule] = relationship(back_populates="results")


class ComplianceConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single named, admin-editable compliance configuration value."""

    __tablename__ = "compliance_config"
    __table_args__ = (
        CheckConstraint(
            "key IN ('severity_weights', 'rag_breakpoints', 'committee_compositions')",
            name="compliance_config_key_allowed",
        ),
    )

    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ComplianceSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One institution-level compliance evaluation for trend charts.

    Rows are append-only so the monitoring screen can chart score history.
    """

    __tablename__ = "compliance_snapshots"
    __table_args__ = (
        Index("ix_compliance_snapshots_institution_time", "institution_id", "evaluated_at"),
    )

    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
    )
    score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    status: Mapped[ComplianceHealth] = mapped_column(
        enum_type(ComplianceHealth, "compliance_health", length=8), nullable=False, index=True
    )
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_critical_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_high_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trigger: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    """What caused the evaluation: application_update, nightly, manual or seed."""
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    institution: Mapped[Institution] = relationship(back_populates="compliance_snapshots")
