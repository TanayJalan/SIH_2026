"""Role-scoped alert inbox, acknowledgement and summary endpoints."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi import status as http_status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select

from app.api.dependencies import (
    ClockDep,
    CurrentUser,
    DbSession,
    resolve_user_from_token,
)
from app.models.alert import Alert
from app.models.enums import AlertChannel, AlertStatus, Severity
from app.models.user import User
from app.schemas.alert import AlertPage, AlertRead, AlertSummaryRead
from app.services.alert_engine import acknowledge_alert
from app.services.alert_stream import format_sse, get_alert_stream_broker

router = APIRouter(prefix="/alerts", tags=["alerts"])

_UNREAD_STATUSES = (AlertStatus.PENDING, AlertStatus.SENT)

_stream_bearer = HTTPBearer(auto_error=False)

# Seconds between SSE keepalive comments; well below typical proxy timeouts.
_STREAM_KEEPALIVE_SECONDS = 15.0


def get_stream_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_stream_bearer)],
    db: DbSession,
    token: Annotated[str | None, Query()] = None,
) -> User:
    """Authenticate an SSE subscriber from a Bearer header or query token.

    ``EventSource`` cannot set headers, so the token query parameter is the
    fallback the browser uses. The token is validated with exactly the same
    rules as the Bearer dependency.
    """
    if credentials is not None and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
    if not token:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return resolve_user_from_token(request, token, db)


@router.get(
    "/stream",
    summary="Server-Sent Events stream of the current user's new alerts",
)
async def stream_alerts(
    current_user: Annotated[User, Depends(get_stream_user)],
) -> StreamingResponse:
    """Stream committed alert rows and simulated-clock advances live.

    Frames are ``alert`` (one new in-app alert row) and ``time`` (the demo
    clock moved, so every countdown and deadline view is stale). Comments are
    emitted as keepalives so proxies keep the connection open.
    """
    broker = get_alert_stream_broker()
    user_id = str(current_user.id)
    events = broker.register(user_id)

    async def event_publisher() -> AsyncIterator[str]:
        try:
            yield "event: connected\ndata: {}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(
                        events.queue.get(), timeout=_STREAM_KEEPALIVE_SECONDS
                    )
                except TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield format_sse(event)
        finally:
            broker.unregister(user_id, events)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(
        event_publisher(),
        media_type="text/event-stream",
        headers=headers,
    )


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
