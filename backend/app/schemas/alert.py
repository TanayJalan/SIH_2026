"""Alert and alert-rule schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (
    AlertChannel,
    AlertStatus,
    Role,
    Severity,
)


class AlertRead(BaseModel):
    """An in-app or outbound notification addressed to a user."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID | None
    rule_id: uuid.UUID | None
    parent_alert_id: uuid.UUID | None
    type: str
    severity: Severity
    title: str
    message: str
    channel: AlertChannel
    status: AlertStatus
    escalation_level: int
    sent_at: datetime | None
    acknowledged_at: datetime | None
    acknowledged_by_id: uuid.UUID | None
    created_at: datetime


class AlertPage(BaseModel):
    """Paginated alerts for the current user."""

    items: list[AlertRead]
    total: int
    page: int
    page_size: int
    pages: int


class AlertSummaryRead(BaseModel):
    """Unread and severity counts for the current user's inbox."""

    total: int
    unread: int
    acknowledged: int
    by_severity: dict[Severity, int]
    unread_by_severity: dict[Severity, int]


class AlertRuleBase(BaseModel):
    """Editable alert-rule fields shared by create and update schemas."""

    code: str = Field(min_length=2, max_length=64, pattern=r"^[A-Z0-9][A-Z0-9_-]*$")
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    trigger_type: str = Field(
        min_length=2, max_length=64, pattern=r"^[A-Z0-9][A-Z0-9_-]*$"
    )
    days_before: int = Field(default=0, ge=0, le=365)
    severity: Severity
    channel_list: list[AlertChannel] = Field(min_length=1, max_length=3)
    template: str = Field(min_length=1, max_length=8000)
    escalation_role: Role = Role.REGIONAL_OFFICER
    apH_clause: str = Field(default="DEMO", max_length=64)
    """APH clause backing the alert; ``DEMO`` marks illustrative configuration."""
    needs_verification: bool = True
    """True while the clause or trigger threshold still needs verification."""
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def _normalise_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("trigger_type")
    @classmethod
    def _normalise_trigger_type(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("channel_list")
    @classmethod
    def _normalise_channels(cls, value: list[AlertChannel]) -> list[AlertChannel]:
        unique: list[AlertChannel] = []
        for channel in value:
            if channel not in unique:
                unique.append(channel)
        if AlertChannel.IN_APP not in unique:
            unique.insert(0, AlertChannel.IN_APP)
        return unique


class AlertRuleCreate(AlertRuleBase):
    """Payload for creating an alert rule."""


class AlertRuleUpdate(BaseModel):
    """Partial alert-rule edit; omitted fields remain unchanged."""

    code: str | None = Field(
        default=None,
        min_length=2,
        max_length=64,
        pattern=r"^[A-Z0-9][A-Z0-9_-]*$",
    )
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    trigger_type: str | None = Field(
        default=None,
        min_length=2,
        max_length=64,
        pattern=r"^[A-Z0-9][A-Z0-9_-]*$",
    )
    days_before: int | None = Field(default=None, ge=0, le=365)
    severity: Severity | None = None
    channel_list: list[AlertChannel] | None = Field(default=None, min_length=1, max_length=3)
    template: str | None = Field(default=None, min_length=1, max_length=8000)
    escalation_role: Role | None = None
    apH_clause: str | None = Field(default=None, max_length=64)
    needs_verification: bool | None = None
    is_active: bool | None = None

    @field_validator("code")
    @classmethod
    def _normalise_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None

    @field_validator("trigger_type")
    @classmethod
    def _normalise_trigger_type(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None

    @field_validator("channel_list")
    @classmethod
    def _normalise_channels(
        cls, value: list[AlertChannel] | None
    ) -> list[AlertChannel] | None:
        if value is None:
            return None
        unique: list[AlertChannel] = []
        for channel in value:
            if channel not in unique:
                unique.append(channel)
        if AlertChannel.IN_APP not in unique:
            unique.insert(0, AlertChannel.IN_APP)
        return unique


class AlertRuleRead(BaseModel):
    """An alert rule returned by the admin API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    description: str
    trigger_type: str
    days_before: int
    severity: Severity
    channel_list: list[AlertChannel]
    template: str
    escalation_role: Role
    apH_clause: str
    needs_verification: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AlertRulePage(BaseModel):
    """Paginated alert-rule catalogue."""

    items: list[AlertRuleRead]
    total: int
    page: int
    page_size: int
