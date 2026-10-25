"""Audit log query endpoint."""

import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.api.dependencies import DbSession, require_roles
from app.models.audit import AuditLog
from app.models.enums import Role
from app.models.user import User
from app.schemas.audit import AuditLogPage, AuditLogRead
from app.schemas.common import ErrorResponse
from app.services.authorization import audit_log_scope

router = APIRouter(tags=["audit"])

AuditLogsUser = Annotated[
    User,
    Depends(
        require_roles(
            Role.SUPER_ADMIN,
            Role.REGIONAL_OFFICER,
            Role.REGULATION_BUREAU_OFFICER,
        )
    ),
]


@router.get(
    "/audit-logs",
    response_model=AuditLogPage,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
    summary="Query audit records",
)
def list_audit_logs(
    current_user: AuditLogsUser,
    db: DbSession,
    entity_type: Annotated[str | None, Query(max_length=64)] = None,
    entity_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AuditLogPage:
    """Return audit records filtered by entity, actor and UTC date range."""
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_date must be on or before end_date",
        )

    conditions = audit_log_scope(current_user)
    if entity_type is not None:
        conditions.append(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        conditions.append(AuditLog.entity_id == entity_id)
    if actor_id is not None:
        conditions.append(AuditLog.actor_id == actor_id)
    if start_date is not None:
        conditions.append(
            AuditLog.created_at >= datetime.combine(start_date, time.min).replace(tzinfo=UTC)
        )
    if end_date is not None:
        conditions.append(
            AuditLog.created_at
            < datetime.combine(end_date + timedelta(days=1), time.min).replace(tzinfo=UTC)
        )

    total = db.scalar(select(func.count()).select_from(AuditLog).where(*conditions)) or 0
    entries = db.scalars(
        select(AuditLog)
        .options(joinedload(AuditLog.actor))
        .where(*conditions)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return AuditLogPage(
        items=[AuditLogRead.model_validate(entry) for entry in entries],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )
