"""Role-scoped alert inbox, acknowledgement and summary endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import func, select

from app.api.dependencies import ClockDep, CurrentUser, DbSession
from app.models.alert import Alert
from app.models.enums import AlertChannel, AlertStatus, Severity
from app.schemas.alert import AlertPage, AlertRead, AlertSummaryRead
from app.services.alert_engine import acknowledge_alert

router = APIRouter(prefix="/alerts", tags=["alerts"])

_UNREAD_STATUSES = (AlertStatus.PENDING, AlertStatus.SENT)


@router.get(
    "/summary",
    response_model=AlertSummaryRead,
    summary="Count the current user's unread and acknowledged in-app alerts",
)
def alert_summary(
    current_user: CurrentUser,
    db: DbSession,
) -> AlertSummaryRead:
    """Return severity and acknowledgement totals for the alert inbox."""
    rows = db.execute(
        select(Alert.severity, Alert.status, func.count())
        .where(
            Alert.recipient_user_id == current_user.id,
            Alert.channel == AlertChannel.IN_APP,
        )
        .group_by(Alert.severity, Alert.status)
    ).all()

    by_severity: dict[Severity, int] = {severity: 0 for severity in Severity}
    unread_by_severity: dict[Severity, int] = {severity: 0 for severity in Severity}
    total = 0
    unread = 0
    acknowledged = 0
    for severity, alert_status, count in rows:
        total += count
        by_severity[severity] += count
        if alert_status in _UNREAD_STATUSES:
            unread += count
            unread_by_severity[severity] += count
        if alert_status == AlertStatus.ACKED:
            acknowledged += count

    return AlertSummaryRead(
        total=total,
        unread=unread,
        acknowledged=acknowledged,
        by_severity=by_severity,
        unread_by_severity=unread_by_severity,
    )


@router.get(
    "",
    response_model=AlertPage,
    summary="List alerts addressed to the current user",
)
def list_alerts(
    current_user: CurrentUser,
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    unread: bool = False,
    status_filter: Annotated[AlertStatus | None, Query(alias="status")] = None,
    severity: Annotated[Severity | None, Query()] = None,
    type_filter: Annotated[str | None, Query(alias="type")] = None,
    application_id: Annotated[uuid.UUID | None, Query()] = None,
    channel: AlertChannel = AlertChannel.IN_APP,
) -> AlertPage:
    """Return the authenticated user's notifications, newest first.

    The inbox defaults to ``IN_APP`` rows. Email and SMS rows are delivery
    records and should not inflate the bell count; an administrator can still
    inspect them by passing ``channel=EMAIL`` or ``channel=SMS``.
    """
    conditions = [
        Alert.recipient_user_id == current_user.id,
        Alert.channel == channel,
    ]
    if unread:
        conditions.append(Alert.status.in_(_UNREAD_STATUSES))
    if status_filter is not None:
        conditions.append(Alert.status == status_filter)
    if severity is not None:
        conditions.append(Alert.severity == severity)
    if type_filter:
        conditions.append(Alert.type == type_filter)
    if application_id is not None:
        conditions.append(Alert.application_id == application_id)

    total = db.scalar(select(func.count()).select_from(Alert).where(*conditions)) or 0
    alerts = db.scalars(
        select(Alert)
        .where(*conditions)
        .order_by(Alert.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return AlertPage(
        items=[AlertRead.model_validate(alert) for alert in alerts],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.post(
    "/{alert_id}/ack",
    response_model=AlertRead,
    summary="Acknowledge an alert",
)
def acknowledge(
    alert_id: str,
    current_user: CurrentUser,
    db: DbSession,
    clock: ClockDep,
) -> AlertRead:
    """Mark one of the current user's in-app alerts as acknowledged."""
    alert = db.scalar(
        select(Alert).where(
            Alert.id == alert_id,
            Alert.recipient_user_id == current_user.id,
            Alert.channel == AlertChannel.IN_APP,
        )
    )
    if alert is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    acknowledge_alert(db, alert, current_user, now=clock.now())
    db.commit()
    db.refresh(alert)
    return AlertRead.model_validate(alert)
