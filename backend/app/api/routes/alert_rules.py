"""Super-admin CRUD for database-configured alert rules."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select

from app.api.dependencies import AuditDep, DbSession, require_roles
from app.models.alert import AlertRule
from app.models.enums import Role
from app.models.user import User
from app.schemas.alert import (
    AlertRuleCreate,
    AlertRulePage,
    AlertRuleRead,
    AlertRuleUpdate,
)
from app.schemas.common import ErrorResponse
from app.services.alert_triggers import (
    UnknownAlertTriggerError,
    validate_trigger,
)

router = APIRouter(prefix="/alert-rules", tags=["alert-rules"])

AlertAdminUser = Annotated[User, Depends(require_roles(Role.SUPER_ADMIN))]


def _snapshot(rule: AlertRule) -> dict[str, object]:
    """A JSON-safe rule snapshot for the audit trail."""
    return {
        "code": rule.code,
        "name": rule.name,
        "description": rule.description,
        "trigger_type": rule.trigger_type,
        "days_before": rule.days_before,
        "severity": rule.severity.value,
        "channel_list": list(rule.channel_list),
        "template": rule.template,
        "escalation_role": rule.escalation_role.value,
        "apH_clause": rule.apH_clause,
        "needs_verification": rule.needs_verification,
        "is_active": rule.is_active,
    }


def _readable_rule(db: DbSession, rule_id: uuid.UUID) -> AlertRule:
    rule = db.get(AlertRule, rule_id)
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert rule not found",
        )
    return rule


def _validated_trigger(db: DbSession, code: str) -> str:
    """Return the catalogue code, or raise 422 for an unknown trigger."""
    normalised = code.strip().upper()
    try:
        return validate_trigger(db, normalised).code
    except UnknownAlertTriggerError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


def _ensure_unique(
    db: DbSession,
    *,
    code: str,
    trigger_type: str,
    days_before: int,
    exclude_id: uuid.UUID | None = None,
) -> None:
    code_query = select(AlertRule.id).where(AlertRule.code == code)
    threshold_query = select(AlertRule.id).where(
        AlertRule.trigger_type == trigger_type,
        AlertRule.days_before == days_before,
    )
    if exclude_id is not None:
        code_query = code_query.where(AlertRule.id != exclude_id)
        threshold_query = threshold_query.where(AlertRule.id != exclude_id)
    if db.scalar(code_query) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An alert rule with this code already exists",
        )
    if db.scalar(threshold_query) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A rule for this trigger and threshold already exists",
        )


@router.get(
    "",
    response_model=AlertRulePage,
    responses={status.HTTP_403_FORBIDDEN: {"model": ErrorResponse}},
    summary="List alert rules",
)
def list_rules(
    _current_user: AlertAdminUser,
    db: DbSession,
    include_inactive: bool = True,
    trigger_type: Annotated[str | None, Query(min_length=2, max_length=64)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AlertRulePage:
    """Return the editable alert-rule catalogue."""
    query = select(AlertRule)
    if not include_inactive:
        query = query.where(AlertRule.is_active.is_(True))
    if trigger_type is not None:
        query = query.where(
            AlertRule.trigger_type == _validated_trigger(db, trigger_type)
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(
        query.order_by(AlertRule.trigger_type, AlertRule.days_before.desc(), AlertRule.code)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return AlertRulePage(
        items=[AlertRuleRead.model_validate(rule) for rule in items],
        total=int(total),
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{rule_id}",
    response_model=AlertRuleRead,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    summary="Read one alert rule",
)
def get_rule(
    rule_id: uuid.UUID,
    _current_user: AlertAdminUser,
    db: DbSession,
) -> AlertRule:
    return _readable_rule(db, rule_id)


@router.post(
    "",
    response_model=AlertRuleRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
    summary="Create an alert rule",
)
def create_rule(
    payload: AlertRuleCreate,
    current_user: AlertAdminUser,
    db: DbSession,
    audit: AuditDep,
    request: Request,
) -> AlertRule:
    """Create a rule with audit logging."""
    trigger_type = _validated_trigger(db, payload.trigger_type)
    _ensure_unique(
        db,
        code=payload.code,
        trigger_type=trigger_type,
        days_before=payload.days_before,
    )
    rule = AlertRule(
        code=payload.code,
        name=payload.name,
        description=payload.description,
        trigger_type=trigger_type,
        days_before=payload.days_before,
        severity=payload.severity,
        channel_list=[channel.value for channel in payload.channel_list],
        template=payload.template,
        escalation_role=payload.escalation_role,
        apH_clause=payload.apH_clause,
        needs_verification=payload.needs_verification,
        is_active=payload.is_active,
    )
    db.add(rule)
    db.flush()
    audit.log(
        current_user,
        "alert_rule.create",
        "AlertRule",
        rule.id,
        after=_snapshot(rule),
        request=request,
    )
    db.commit()
    db.refresh(rule)
    return rule


@router.patch(
    "/{rule_id}",
    response_model=AlertRuleRead,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
    summary="Edit an alert rule",
)
def update_rule(
    rule_id: uuid.UUID,
    payload: AlertRuleUpdate,
    current_user: AlertAdminUser,
    db: DbSession,
    audit: AuditDep,
    request: Request,
) -> AlertRule:
    """Apply a partial alert-rule edit with a before/after audit entry."""
    rule = _readable_rule(db, rule_id)
    before = _snapshot(rule)
    applied: dict[str, object] = {}

    if payload.trigger_type is not None:
        _validated_trigger(db, payload.trigger_type)

    for key, value in payload.model_dump(exclude_unset=True).items():
        if key == "escalation_role":
            new_value = value.value
        elif key == "channel_list":
            new_value = [channel.value for channel in value]
        else:
            new_value = value
        if getattr(rule, key) == new_value:
            continue
        setattr(rule, key, new_value)
        applied[key] = new_value

    if applied:
        _ensure_unique(
            db,
            code=rule.code,
            trigger_type=rule.trigger_type,
            days_before=rule.days_before,
            exclude_id=rule.id,
        )
        db.flush()
        audit.log(
            current_user,
            "alert_rule.update",
            "AlertRule",
            rule.id,
            before=before,
            after=_snapshot(rule),
            request=request,
        )
        db.commit()
        db.refresh(rule)
    return rule


@router.delete(
    "/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    summary="Delete an alert rule",
)
def delete_rule(
    rule_id: uuid.UUID,
    current_user: AlertAdminUser,
    db: DbSession,
    audit: AuditDep,
    request: Request,
) -> Response:
    """Delete an alert rule while retaining historical alerts."""
    rule = _readable_rule(db, rule_id)
    audit.log(
        current_user,
        "alert_rule.delete",
        "AlertRule",
        rule.id,
        before=_snapshot(rule),
        request=request,
    )
    db.delete(rule)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
