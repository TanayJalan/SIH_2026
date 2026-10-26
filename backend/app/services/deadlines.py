"""One place for APH deadline computation.

``DeadlineRule`` rows describe when a clock starts, how long it runs and who
owns it. This service resolves the start event, computes the due instant and
creates a :class:`~app.models.deadline.Timer`. Fixed-date rules point at an
``AcademicCalendarEvent`` so the date stays administrable (APH_SPEC section 5).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.calendar import AcademicCalendarEvent
from app.models.deadline import DeadlineRule, Timer, TimerStatus
from app.models.decision import DecisionLetter
from app.models.enums import CalendarEventKey, DecisionLetterType
from app.models.security_deposit import SecurityDeposit
from app.services.audit import AuditService


class DeadlineError(ValueError):
    """Raised when a deadline rule cannot be resolved for an application."""


def end_of_day(value: date) -> datetime:
    """Return the last instant of ``value`` in UTC."""
    return datetime.combine(value, time(23, 59, 59), tzinfo=UTC)


def compute_due_at(started_at: datetime, duration_days: int) -> datetime:
    """Return ``started_at`` plus ``duration_days`` as an aware UTC instant."""
    if duration_days < 0:
        raise DeadlineError("duration_days must be zero or positive")
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=UTC)
    return started_at + timedelta(days=duration_days)


def _as_datetime(value: date | datetime) -> datetime:
    """Normalise a date or datetime to an aware end-of-day instant."""
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return end_of_day(value)


def resolve_start_event(
    db: Session,
    rule: DeadlineRule,
    application: Application,
    *,
    letter: DecisionLetter | None = None,
) -> datetime:
    """Resolve the configured ``start_event`` for one application.

    Fixed-date events are looked up in ``academic_calendar_events``; lifecycle
    events are read from the application, its letters or its Security Deposit.
    """
    event = rule.start_event
    try:
        calendar_key = CalendarEventKey(event)
    except ValueError:
        calendar_key = None

    if calendar_key is not None:
        calendar_event = db.scalar(
            select(AcademicCalendarEvent).where(
                AcademicCalendarEvent.academic_year == application.academic_year,
                AcademicCalendarEvent.event_key == calendar_key,
            )
        )
        if calendar_event is None:
            raise DeadlineError(
                f"No {event} calendar event for academic year "
                f"{application.academic_year}"
            )
        return end_of_day(calendar_event.date)

    if event == "DECISION_UPLOADED":
        if letter is not None:
            if letter.published_at is not None:
                return _as_datetime(letter.published_at)
            return end_of_day(letter.issued_on)
        if application.decision_uploaded_at is not None:
            return _as_datetime(application.decision_uploaded_at)
        latest_letter = db.scalar(
            select(DecisionLetter)
            .where(
                DecisionLetter.application_id == application.id,
                DecisionLetter.published_at.is_not(None),
            )
            .order_by(DecisionLetter.published_at.desc())
            .limit(1)
        )
        if latest_letter is None or latest_letter.published_at is None:
            raise DeadlineError(
                f"Application {application.id} has no uploaded decision"
            )
        return _as_datetime(latest_letter.published_at)

    if event == "SECURITY_DEPOSIT_INTIMATION":
        deposit = db.scalar(
            select(SecurityDeposit)
            .where(SecurityDeposit.application_id == application.id)
            .order_by(SecurityDeposit.created_on.desc(), SecurityDeposit.created_at.desc())
            .limit(1)
        )
        if deposit is None:
            raise DeadlineError(
                f"Application {application.id} has no Security Deposit intimation"
            )
        return end_of_day(deposit.created_on)

    if event == "SHOW_CAUSE_ISSUED":
        show_cause = db.scalar(
            select(DecisionLetter)
            .where(
                DecisionLetter.application_id == application.id,
                DecisionLetter.letter_type == DecisionLetterType.SHOW_CAUSE,
            )
            .order_by(DecisionLetter.issued_on.desc(), DecisionLetter.created_at.desc())
            .limit(1)
        )
        if show_cause is None:
            raise DeadlineError(
                f"Application {application.id} has no show-cause letter"
            )
        return end_of_day(show_cause.issued_on)

    raise DeadlineError(f"Unsupported deadline start event {event!r}")


def start_timer(
    db: Session,
    application: Application,
    rule: DeadlineRule,
    *,
    started_at: datetime | None = None,
    letter: DecisionLetter | None = None,
    audit: AuditService | None = None,
) -> Timer:
    """Create a PENDING timer for ``application`` from ``rule``."""
    start = started_at or resolve_start_event(db, rule, application, letter=letter)
    due_at = compute_due_at(start, rule.duration_days)
    timer = Timer(
        application_id=application.id,
        deadline_rule_id=rule.id,
        started_at=start,
        due_at=due_at,
        status=TimerStatus.PENDING,
        fired_levels=[],
    )
    db.add(timer)
    db.flush()
    if audit is not None:
        audit.log(
            None,
            "timer.start",
            "Timer",
            timer.id,
            after={
                "application_id": str(application.id),
                "deadline_rule": rule.code,
                "start_event": rule.start_event,
                "started_at": start.isoformat(),
                "due_at": due_at.isoformat(),
                "status": timer.status.value,
            },
        )
    return timer


def timer_status_at(timer: Timer, now: datetime) -> TimerStatus:
    """Return the status of ``timer`` at ``now`` without mutating it."""
    if timer.status in {TimerStatus.COMPLETED, TimerStatus.CANCELLED}:
        return timer.status
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    if now.date() < timer.due_at.date():
        return TimerStatus.PENDING
    if now.date() == timer.due_at.date():
        return TimerStatus.DUE
    return TimerStatus.BREACHED


def refresh_timer_status(timer: Timer, now: datetime) -> TimerStatus:
    """Set and return the timer status for ``now``."""
    timer.status = timer_status_at(timer, now)
    return timer.status


def complete_timers(
    db: Session,
    application: Application,
    *,
    rule_code: str,
    status: TimerStatus = TimerStatus.COMPLETED,
    audit: AuditService | None = None,
) -> int:
    """Close every open timer of ``rule_code`` for ``application``.

    Used when the obligation is met before the clock runs out: filing the
    appeal stops the seven-day window (APH 1.11a) and paying the Security
    Deposit stops the deposit clock (APH 2.25f).
    """
    timers = list(
        db.scalars(
            select(Timer)
            .join(DeadlineRule, DeadlineRule.id == Timer.deadline_rule_id)
            .where(
                Timer.application_id == application.id,
                DeadlineRule.code == rule_code,
                Timer.status.in_((TimerStatus.PENDING, TimerStatus.DUE)),
            )
        ).all()
    )
    for timer in timers:
        before = {"status": timer.status.value}
        timer.status = status
        if audit is not None:
            audit.log(
                None,
                f"timer.{status.value.lower()}",
                "Timer",
                timer.id,
                before=before,
                after={
                    "application_id": str(application.id),
                    "deadline_rule": rule_code,
                    "status": status.value,
                },
            )
    db.flush()
    return len(timers)
