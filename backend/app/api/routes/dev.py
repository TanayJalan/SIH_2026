"""DEBUG-only demo time controls."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field, model_validator

from app.api.dependencies import AuditDep, ClockDep, CurrentUser, DbSession
from app.core.clock import SimulatedClock
from app.core.config import Settings
from app.db.session import SessionLocal
from app.services.alert_engine import AlertEngine

router = APIRouter(prefix="/dev", tags=["development"])

_TIME_ENTITY_ID = uuid.UUID(int=0)


class AlertScanRead(BaseModel):
    """Aggregate result of one or more alert scans."""

    alerts_created: int
    escalations: int
    notifications_sent: int
    scanned_through: datetime


class TimeSimulationRead(BaseModel):
    """Current state of the demo clock."""

    enabled: bool
    simulated_now: datetime
    real_now: datetime
    offset_days: int
    scan: AlertScanRead | None = None


class TimeSimulationUpdate(BaseModel):
    """Advance the demo clock or reset it to real time."""

    days: int = Field(default=0, ge=0, le=30)
    reset: bool = False

    @model_validator(mode="after")
    def _validate_action(self) -> "TimeSimulationUpdate":
        if self.reset and self.days != 0:
            raise ValueError("days must be zero when reset is true")
        if not self.reset and self.days == 0:
            raise ValueError("days must be at least 1 unless reset is true")
        return self


def _state(clock: SimulatedClock, scan: AlertScanRead | None = None) -> TimeSimulationRead:
    return TimeSimulationRead(
        enabled=True,
        simulated_now=clock.now(),
        real_now=datetime.now(UTC),
        offset_days=clock.offset_days,
        scan=scan,
    )


def _replay_scan(
    *,
    clock: SimulatedClock,
    settings: Settings,
    days: int,
) -> AlertScanRead:
    """Walk the simulated clock forward one day at a time and scan each day.

    Replaying daily keeps thresholds such as T-7, T-3 and T-1 observable in a
    single demo call instead of jumping past every intermediate alert window.
    Delivery is deferred to one final SMTP/SMS pass so a short demo does not
    depend on a running relay between scans.
    """
    alerts_created = 0
    escalations = 0

    for _ in range(days):
        clock.advance(1)
        with SessionLocal() as scan_db:
            engine = AlertEngine(scan_db, clock, settings=settings)
            result = engine.scan()
            scan_db.commit()
            alerts_created += result.alerts_created
            escalations += result.escalations

    notifications_sent = 0
    if settings.notifications_enabled:
        with SessionLocal() as delivery_db:
            engine = AlertEngine(delivery_db, clock, settings=settings)
            notifications_sent = engine.deliver_pending()
            delivery_db.commit()

    return AlertScanRead(
        alerts_created=alerts_created,
        escalations=escalations,
        notifications_sent=notifications_sent,
        scanned_through=clock.now(),
    )


@router.get(
    "/simulate-time",
    response_model=TimeSimulationRead,
    summary="Simulate days and run the scheduler catch-up scan",
)
def get_simulated_time(
    _current_user: CurrentUser,
    clock: ClockDep,
    db: DbSession,
    audit: AuditDep,
    request: Request,
    days: Annotated[int | None, Query(ge=1, le=30)] = None,
) -> TimeSimulationRead:
    """Read the simulated clock, optionally replaying daily alert scans.

    A single ``days=N`` call walks the clock forward one day at a time and
    runs the periodic scan for each day before returning. This is what makes
    a short demo produce the realistic sequence: approaching deadline, then
    SLA breach, then escalation, instead of skipping straight to the final
    date. Outbound email/SMS rows are delivered once at the end.
    """
    if days is None:
        return _state(clock)

    settings = request.app.state.settings
    before = {
        "offset_days": clock.offset_days,
        "simulated_now": clock.now().isoformat(),
    }
    scan = _replay_scan(clock=clock, settings=settings, days=days)

    audit.log(
        _current_user,
        "dev.time.simulate",
        "SimulatedTime",
        _TIME_ENTITY_ID,
        before=before,
        after={
            "offset_days": clock.offset_days,
            "simulated_now": clock.now().isoformat(),
            "days": days,
            "alerts_created": scan.alerts_created,
            "escalations": scan.escalations,
            "notifications_sent": scan.notifications_sent,
        },
        request=request,
    )
    db.commit()
    return _state(clock, scan)


@router.post(
    "/simulate-time",
    response_model=TimeSimulationRead,
    summary="Advance or reset the DEBUG-only simulated clock",
)
def update_simulated_time(
    payload: TimeSimulationUpdate,
    current_user: CurrentUser,
    clock: ClockDep,
    db: DbSession,
    audit: AuditDep,
    request: Request,
) -> TimeSimulationRead:
    """Move the demo clock and, when advancing, replay the periodic scans.

    Reset returns the clock to real time without creating alerts. Advancing is
    equivalent to the ``GET ?days=`` replay so the top-bar demo control and a
    direct API call produce the same observable alerts.
    """
    settings = request.app.state.settings
    before = {
        "offset_days": clock.offset_days,
        "simulated_now": clock.now().isoformat(),
    }

    scan: AlertScanRead | None = None
    if payload.reset:
        clock.reset()
        action = "dev.time.reset"
    else:
        scan = _replay_scan(clock=clock, settings=settings, days=payload.days)
        action = "dev.time.advance"

    audit.log(
        current_user,
        action,
        "SimulatedTime",
        _TIME_ENTITY_ID,
        before=before,
        after={
            "offset_days": clock.offset_days,
            "simulated_now": clock.now().isoformat(),
            "days": payload.days,
            "alerts_created": scan.alerts_created if scan is not None else 0,
            "escalations": scan.escalations if scan is not None else 0,
            "notifications_sent": (
                scan.notifications_sent if scan is not None else 0
            ),
        },
        request=request,
    )
    db.commit()
    return _state(clock, scan)
