"""Audit log response schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.enums import Role


class AuditActorRead(BaseModel):
    """Minimal actor information attached to an audit entry."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    role: Role


class AuditLogRead(BaseModel):
    """An immutable audit record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_id: uuid.UUID | None
    actor: AuditActorRead | None
    action: str
    entity_type: str
    entity_id: uuid.UUID
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    ip: str | None
    created_at: datetime


class AuditLogPage(BaseModel):
    """Paginated audit records."""

    items: list[AuditLogRead]
    total: int
    page: int
    page_size: int
    pages: int
