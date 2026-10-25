"""Compliance preview, admin and monitoring schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import Severity
from app.schemas.application_sections import ApplicationData

ComplianceRuleStatus = Literal["PASS", "FAIL", "NOT_ASSESSED"]
ComplianceOutcome = Literal["PASS", "ATTENTION", "INCOMPLETE"]
ComplianceHealthValue = Literal["GREEN", "AMBER", "RED"]

RuleOperator = Literal["<", "<=", ">=", ">", "=", "==", "!=", "BETWEEN", "EXISTS"]


class CompliancePreviewRequest(BaseModel):
    """Unsaved draft values to evaluate without persisting them."""

    data: ApplicationData


class ComplianceRulePreview(BaseModel):
    """One configured rule evaluated against the current form values."""

    code: str
    name: str
    category: str
    description: str
    severity: Severity
    metric_key: str
    operator: str
    threshold: float
    threshold_max: float | None = None
    unit: str | None
    observed_value: float | None
    status: ComplianceRuleStatus
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    """Values the decision was based on: metric, observed value and threshold."""
    explanation: dict[str, Any] = Field(default_factory=dict)
    """Structured criteria, values, pass/fail and APH clause for the decision."""


class CompliancePreviewRead(BaseModel):
    """Live rule outcomes for one application, plus the weighted score."""

    application_id: uuid.UUID
    evaluated_at: datetime
    rules: list[ComplianceRulePreview]
    passed_count: int
    failed_count: int
    not_assessed_count: int
    assessed_count: int
    score: float
    outcome: ComplianceOutcome
    status: ComplianceHealthValue


# --------------------------------------------------------------------------
# Admin: rules
# --------------------------------------------------------------------------


class ComplianceRuleRead(BaseModel):
    """A compliance rule as stored and editable through the admin screen."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    category: str
    description: str
    metric_key: str
    operator: RuleOperator
    threshold: float
    threshold_max: float | None
    severity: Severity
    applies_to: str
    apH_clause: str
    needs_verification: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ComplianceRulePage(BaseModel):
    """Paginated rule list for the admin screen."""

    items: list[ComplianceRuleRead]
    total: int
    page: int
    page_size: int


class ComplianceMonitorPage(BaseModel):
    """Paginated monitoring list for the admin screen."""

    items: list[ComplianceMonitorRead]
    total: int
    page: int
    page_size: int


class ComplianceRuleCreate(BaseModel):
    """Payload to add a rule; threshold values are illustrative and editable."""

    code: str = Field(max_length=64)
    name: str = Field(max_length=255)
    category: str = Field(max_length=64)
    description: str = Field(max_length=2000)
    metric_key: str = Field(max_length=100)
    operator: RuleOperator
    threshold: float = Field(ge=0)
    threshold_max: float | None = Field(default=None, ge=0)
    severity: Severity
    applies_to: str = "ALL"
    """Comma separated scopes: APH application types (for example
    NEW_INSTITUTION or EOA_SELF_DISCLOSURE), programme levels (UG/PG), or ALL."""
    apH_clause: str = Field(default="DEMO", max_length=64)
    """APH clause backing the rule; ``DEMO`` marks illustrative configuration."""
    needs_verification: bool = True
    """True while the clause or threshold still needs verification."""
    is_active: bool = True

    @model_validator(mode="after")
    def _validate_between_bounds(self) -> ComplianceRuleCreate:
        if self.operator == "BETWEEN":
            if self.threshold_max is None:
                raise ValueError("threshold_max is required when operator is BETWEEN")
            if self.threshold_max < self.threshold:
                raise ValueError("threshold_max must be greater than or equal to threshold")
        elif self.threshold_max is not None:
            raise ValueError("threshold_max is only valid when operator is BETWEEN")
        return self


class ComplianceRuleUpdate(BaseModel):
    """Partial rule edit; only the given fields change."""

    name: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=2000)
    metric_key: str | None = Field(default=None, max_length=100)
    operator: RuleOperator | None = None
    threshold: float | None = Field(default=None, ge=0)
    threshold_max: float | None = Field(default=None, ge=0)
    severity: Severity | None = None
    applies_to: str | None = None
    apH_clause: str | None = Field(default=None, max_length=64)
    needs_verification: bool | None = None
    is_active: bool | None = None


class RuleImpactInstitution(BaseModel):
    """One institution whose monitoring status the proposed rule would change."""

    institution_id: uuid.UUID
    institution_name: str
    region: str
    current_status: ComplianceHealthValue
    projected_status: ComplianceHealthValue


class ComplianceRuleImpactRead(BaseModel):
    """Result of previewing a proposed rule change against current data."""

    red_flips: int
    amber_flips: int
    improved: int
    unchanged: int
    affected: list[RuleImpactInstitution]
    message: str


class ComplianceRuleImpactRequest(BaseModel):
    """A proposed rule change (existing rule id plus the new values)."""

    rule_id: uuid.UUID | None = None
    """Existing rule to modify; ``None`` evaluates a brand new rule."""
    proposed: ComplianceRuleCreate


class ComplianceMetricRead(BaseModel):
    """A metric the rule editor can reference."""

    key: str
    label: str
    unit: str | None


class ComplianceMetricListRead(BaseModel):
    """Metric catalogue for the rule editor."""

    items: list[ComplianceMetricRead]


class ComplianceMonitorRunRead(BaseModel):
    """Outcome of an on-demand monitoring re-evaluation."""

    evaluated: int
    red: int
    amber: int
    green: int
    message: str


# --------------------------------------------------------------------------
# Admin: config (severity weights + RAG breakpoints)
# --------------------------------------------------------------------------


class SeverityWeightsConfig(BaseModel):
    """Weight contributed by each failed severity to the score penalty."""

    CRITICAL: float = Field(default=25.0, ge=0)
    HIGH: float = Field(default=15.0, ge=0)
    MEDIUM: float = Field(default=8.0, ge=0)
    LOW: float = Field(default=4.0, ge=0)


class RagBreakpointsConfig(BaseModel):
    """Score bands for monitoring status; a failed CRITICAL rule forces RED."""

    red_below: float = Field(default=70.0, ge=0, le=100)
    amber_below: float = Field(default=85.0, ge=0, le=100)

    @model_validator(mode="after")
    def _ordered_bands(self) -> RagBreakpointsConfig:
        if self.amber_below < self.red_below:
            raise ValueError("amber_below must be greater than or equal to red_below")
        return self


class ComplianceConfigRead(BaseModel):
    """Admin-editable compliance configuration."""

    severity_weights: SeverityWeightsConfig
    rag_breakpoints: RagBreakpointsConfig
    updated_at: datetime | None = None


class ComplianceConfigUpdate(BaseModel):
    """Any subset of the configuration keys to persist."""

    severity_weights: SeverityWeightsConfig | None = None
    rag_breakpoints: RagBreakpointsConfig | None = None


# --------------------------------------------------------------------------
# Monitoring
# --------------------------------------------------------------------------


class ComplianceSnapshotRead(BaseModel):
    """One historical evaluation of an institution."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    institution_id: uuid.UUID
    application_id: uuid.UUID | None
    score: float
    status: ComplianceHealthValue
    failed_count: int
    failed_critical_count: int
    failed_high_count: int
    missing_count: int
    trigger: str
    evaluated_at: datetime


class ComplianceMonitorRead(BaseModel):
    """Institution list entry for the monitoring screen."""

    institution_id: uuid.UUID
    institution_name: str
    region: str
    state: str
    latest_score: float | None
    latest_status: ComplianceHealthValue | None
    latest_failed_count: int | None
    latest_missing_count: int | None
    latest_evaluated_at: datetime | None
    latest_trigger: str | None
    application_id: uuid.UUID | None
    application_reference: str | None


class ComplianceTrendPoint(BaseModel):
    """One point on an institution's score trend chart."""

    snapshot_id: uuid.UUID
    score: float
    status: ComplianceHealthValue
    failed_count: int
    missing_count: int
    trigger: str
    evaluated_at: datetime
    application_id: uuid.UUID | None


class ComplianceInstitutionTrendRead(BaseModel):
    """Trail of evaluations for one institution."""

    institution_id: uuid.UUID
    institution_name: str
    region: str
    points: list[ComplianceTrendPoint]
