"""Scheduled advancement of statutory clocks.

Three decisions do not need a human: a rejection or deficiency decision becomes
final when the seven-day appeal window closes with no appeal (APH 1.11a), a
Letter of Approval lapses at the end of its two academic years (APH 1.10b), and
an unpaid Security Deposit moves up its penalty ladder and is eventually
withdrawn (APH 2.25f). Every step is applied through the same data-driven state
machine as a manual action, so it is still recorded in ``WorkflowEvent`` and
``AuditLog`` and the alert engine adds the notification.

The sweep runs with the periodic alert scan; it never invents a transition and
silently skips a case whose configured guards do not pass.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import SimulatedClock
from app.core.config import Settings
from app.models.appeal import Appeal
from app.models.application import Application
from app.models.deadline import DeadlineRule, Timer, TimerStatus
from app.models.enums import ApplicationStatus, Role, WorkflowAction
from app.models.user import User
from app.schemas.workflow import WorkflowActionRequest
from app.services.alert_engine import NotificationService, notify_deposit_step
from app.services.audit import AuditService
from app.services.workflow import WorkflowError, WorkflowService

logger = logging.getLogger("app.workflow_jobs")

# Statuses whose next step is decided by a clock rather than a person.
_APPEAL_STATUSES = (ApplicationStatus.APPEAL_WINDOW,)
_LOA_STATUSES = (ApplicationStatus.ACTIVE_LOA,)
_DEPOSIT_STATUSES = (ApplicationStatus.SECURITY_DEPOSIT_PENDING,)


def _system_actor(db: Session) -> User | None:
    """Return the officer used to sign automatic steps.

    ``finalize_no_appeal`` and ``expire_loa`` are Regulation Bureau actions, so
    the sweep acts as an active Regulation Bureau officer instead of inventing a
    system role that the transition data does not allow.
    """
    return db.scalar(
        select(User)
        .where(
            User.role == Role.REGULATION_BUREAU_OFFICER,
            User.is_active.is_(True),
        )
        .order_by(User.name.asc())
        .limit(1)
    )


def _appeal_clock_deadline(db: Session, application: Application):
    """Return the appeal deadline from the read model or its open Timer.

    The timer is the scheduler's source of truth (APH 1.11a). The application
    column is kept as a read model for the UI, but an older row may only have
    the ``Timer``, so the sweep falls back to it instead of skipping the case.
    """
    if application.appeal_deadline is not None:
        return application.appeal_deadline
    timer = db.scalar(
        select(Timer)
        .join(DeadlineRule, DeadlineRule.id == Timer.deadline_rule_id)
        .where(
            Timer.application_id == application.id,
            DeadlineRule.code == "APPEAL_WINDOW",
            Timer.status.in_(
                (TimerStatus.PENDING, TimerStatus.DUE, TimerStatus.BREACHED)
            ),
        )
        .order_by(Timer.due_at.desc())
        .limit(1)
    )
    return timer.due_at if timer is not None else None


def _has_appeal(db: Session, application: Application) -> bool:
    return bool(
        db.scalar(
            select(func.count(Appeal.id)).where(
                Appeal.application_id == application.id
            )
        )
    )


def _apply(
    db: Session,
    application: Application,
    actor: User,
    action: WorkflowAction,
    comment: str,
    clock: SimulatedClock,
) -> bool:
    """Apply one automatic step, rolling back only that step on failure."""
    service = WorkflowService(db, AuditService(db), clock)
    try:
        service.execute(
            application,
            actor=actor,
            action=action,
            payload=WorkflowActionRequest(comment=comment),
        )
    except WorkflowError as error:
        db.rollback()
        logger.info(
            "Automatic workflow step skipped",
            extra={
                "event": "workflow.auto.skip",
                "application_id": str(application.id),
                "action": action.value,
                "reason": str(error),
            },
        )
        return False
    return True


def sweep_appeal_windows(db: Session, clock: SimulatedClock) -> int:
    """Finalise decisions whose appeal window closed without an appeal."""
    now = clock.now()
    actor = _system_actor(db)
    if actor is None:
        return 0

    advanced = 0
    applications = db.scalars(
        select(Application).where(Application.status.in_(_APPEAL_STATUSES))
    ).all()
    for application in applications:
        deadline = _appeal_clock_deadline(db, application)
        if deadline is None:
            continue
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=now.tzinfo)
        if deadline > now:
            continue
        if _has_appeal(db, application):
            continue
        if _apply(
            db,
            application,
            actor,
            WorkflowAction.FINALIZE_NO_APPEAL,
            "Automatic: the appeal window closed with no appeal.",
            clock,
        ):
            advanced += 1
    return advanced


def sweep_expired_loas(db: Session, clock: SimulatedClock) -> int:
    """Cancel LoAs whose two academic years have elapsed (APH 1.10b)."""
    today = clock.now().date()
    actor = _system_actor(db)
    if actor is None:
        return 0

    advanced = 0
    applications = db.scalars(
        select(Application).where(Application.status.in_(_LOA_STATUSES))
    ).all()
    for application in applications:
        valid_until = application.loa_valid_until
        if valid_until is None or valid_until >= today:
            continue
        if _apply(
            db,
            application,
            actor,
            WorkflowAction.EXPIRE_LOA,
            "Automatic: the LoA validity period has ended.",
            clock,
        ):
            advanced += 1
    return advanced


def sweep_deposit_ladder(
    db: Session,
    clock: SimulatedClock,
    *,
    settings: Settings | None = None,
    notifications: NotificationService | None = None,
) -> int:
    """Apply the next Security Deposit ladder step (APH 2.25f).

    The workflow rows and their guards decide which step applies: a higher
    penalty window, or withdrawal after the final 31 July date. A guard that is
    not reached leaves the case untouched, so this sweep is safe to run with
    every periodic scan.
    """
    actor = _system_actor(db)
    if actor is None:
        return 0

    advanced = 0
    applications = db.scalars(
        select(Application).where(Application.status.in_(_DEPOSIT_STATUSES))
    ).all()
    for application in applications:
        if application.security_deposit_due_on is None:
            continue
        if _apply(
            db,
            application,
            actor,
            WorkflowAction.APPLY_DEPOSIT_PENALTY,
            "Automatic: the Security Deposit clock reached its next window.",
            clock,
        ):
            advanced += 1
            notify_deposit_step(
                db,
                application,
                clock,
                settings=settings,
                notifications=notifications,
            )
    return advanced


def sweep(
    db: Session,
    clock: SimulatedClock,
    *,
    settings: Settings | None = None,
    notifications: NotificationService | None = None,
) -> int:
    """Run every clock-driven workflow step and return how many were applied."""
    return (
        sweep_appeal_windows(db, clock)
        + sweep_expired_loas(db, clock)
        + sweep_deposit_ladder(
            db,
            clock,
            settings=settings,
            notifications=notifications,
        )
    )
