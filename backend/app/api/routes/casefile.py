"""Case-file read models: deadlines, decisions, appeal and fee movements.

The case file UI renders its stage track, decision badges, deadline cards and
fees ledger from these read-only endpoints. They never mutate state: every
write action goes through ``POST /applications/{id}/actions/{action}``, the
single state machine. All statutory dates come from configuration rows
(``deadline_rules``, ``academic_calendar_events``), never from constants
(APH 1.11a, 1.10b, 2.25f).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import ClockDep, CurrentUser, DbSession
from app.models.appeal import Appeal
from app.models.application import Application
from app.models.calendar import AcademicCalendarEvent
from app.models.deadline import DeadlineRule, Timer
from app.models.decision import Decision, DecisionLetter
from app.models.enums import CalendarEventKey, SecurityDepositStatus, TimerStatus
from app.models.fee import FeeTransaction
from app.models.security_deposit import SecurityDeposit
from app.schemas.fees import FeeTransactionRead
from app.schemas.workflow import AppealRead, DecisionRead
from app.services.authorization import can_access_application
from app.services.fee_calculator import (
    SecurityDepositPenaltyWindows,
    security_deposit_penalty,
)

router = APIRouter(prefix="/applications", tags=["case-file read models"])


def _load_application(db: Session, application_id: uuid.UUID) -> Application | None:
    return db.scalar(
        select(Application)
        .options(joinedload(Application.institution))
        .where(Application.id == application_id)
    )


def _readable_application(
    db: Session, user: CurrentUser, application_id: uuid.UUID
) -> Application:
    application = _load_application(db, application_id)
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    if not can_access_application(db, user, application):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You do not have access to this application",
        )
    return application


# ---------------------------------------------------------------------------
# Deadlines (stage-track countdowns and the dashboard deadline card)
# ---------------------------------------------------------------------------


class AppealDeadlineRead(BaseModel):
    """The single seven-day appeal window of the latest decision (APH 1.11a)."""

    deadline: datetime | None
    days_left: int | None
    letter_type: str | None
    apH_clause: str


class DepositDeadlineRead(BaseModel):
    """Security Deposit clock: grace, the penalty windows and the withdrawal date (APH 2.25f)."""

    due_on: date | None
    days_left: int | None
    intimated_on: date | None
    penalty_percent: int | None
    first_penalty_until: date | None
    second_penalty_until: date | None
    withdrawal_after: date | None
    current_stage: str | None
    apH_clause: str


class LoaValidityRead(BaseModel):
    """Two academic years of LoA validity (APH 1.10b)."""

    valid_until: date
    days_left: int
    expired: bool
    apH_clause: str


class TimerRead(BaseModel):
    """One live deadline timer of the application (APH_SPEC section 5)."""

    id: uuid.UUID
    deadline_rule_code: str
    status: str
    started_at: datetime
    due_at: datetime
    days_left: int
    apH_clause: str


class ApplicationDeadlinesRead(BaseModel):
    """Every statutory clock the case file stage track must show."""

    application_id: uuid.UUID
    as_of: datetime
    appeal: AppealDeadlineRead | None = None
    security_deposit: DepositDeadlineRead | None = None
    loa_validity: LoaValidityRead | None = None
    timers: list[TimerRead] = []


class _DeadlinesService:
    """Compose the deadline sections of one case file from configuration.

    A missing rule or calendar row degrades a section to ``None`` (or a null
    date) instead of guessing a date: deadlines are always configuration, never
    constants.
    """

    def __init__(self, db: Session, application: Application, now: datetime) -> None:
        self._db = db
        self._application = application
        self._now = now
        self._rules: dict[str, DeadlineRule] = {
            rule.code: rule for rule in db.scalars(select(DeadlineRule)).all()
        }

    # -- helpers -----------------------------------------------------------

    def _days_left_datetime(self, due: datetime) -> int:
        """Whole days until a datetime deadline, negative once it passed."""
        return int((due - self._now).total_seconds() // 86_400)

    def _calendar_date(self, key: CalendarEventKey) -> date | None:
        event = self._db.scalar(
            select(AcademicCalendarEvent).where(
                AcademicCalendarEvent.academic_year == self._application.academic_year,
                AcademicCalendarEvent.event_key == key,
            )
        )
        return event.date if event is not None else None

    def _latest_letter(self) -> DecisionLetter | None:
        return self._db.scalar(
            select(DecisionLetter)
            .where(DecisionLetter.application_id == self._application.id)
            .order_by(DecisionLetter.created_at.desc(), DecisionLetter.issued_on.desc())
            .limit(1)
        )

    def _open_timer(self, rule_code: str) -> Timer | None:
        return self._db.scalar(
            select(Timer)
            .join(DeadlineRule, DeadlineRule.id == Timer.deadline_rule_id)
            .where(
                Timer.application_id == self._application.id,
                DeadlineRule.code == rule_code,
                Timer.status.in_(
                    (TimerStatus.PENDING, TimerStatus.DUE, TimerStatus.BREACHED)
                ),
            )
            .order_by(Timer.due_at.desc())
            .limit(1)
        )

    def _deposit_intimation(self) -> date | None:
        """The deposit intimation date: the oldest row, or due-date minus grace."""
        deposits = self._db.scalars(
            select(SecurityDeposit)
            .where(SecurityDeposit.application_id == self._application.id)
            .order_by(SecurityDeposit.created_on.asc())
        ).all()
        if deposits:
            return deposits[0].created_on
        rule = self._rules.get("SECURITY_DEPOSIT")
        grace = rule.duration_days if rule is not None else 15
        if self._application.security_deposit_due_on is not None:
            return self._application.security_deposit_due_on - timedelta(days=grace)
        return None

    # -- sections ----------------------------------------------------------

    def read(self) -> ApplicationDeadlinesRead:
        return ApplicationDeadlinesRead(
            application_id=self._application.id,
            as_of=self._now,
            appeal=self._appeal(),
            security_deposit=self._deposit(),
            loa_validity=self._loa_validity(),
            timers=self._timers(),
        )

    def _appeal(self) -> AppealDeadlineRead | None:
        rule = self._rules.get("APPEAL_WINDOW")
        if rule is None:
            return None  # The clock is only defined when an administrator seeds it.
        letter = self._latest_letter()
        deadline = (
            self._application.appeal_deadline
            or (letter.appeal_deadline if letter is not None else None)
        )
        if deadline is None:
            timer = self._open_timer("APPEAL_WINDOW")
            deadline = timer.due_at if timer is not None else None
        return AppealDeadlineRead(
            deadline=deadline,
            days_left=self._days_left_datetime(deadline) if deadline is not None else None,
            letter_type=(letter.letter_type.value if letter is not None else None),
            apH_clause=rule.apH_clause,
        )

    def _deposit(self) -> DepositDeadlineRead | None:
        rule = self._rules.get("SECURITY_DEPOSIT")
        if rule is None:
            return None
        intimation = self._deposit_intimation()
        due_on = self._application.security_deposit_due_on
        if intimation is None and due_on is None:
            return None  # No Security Deposit clock has started on this file.

        windows = SecurityDepositPenaltyWindows(grace_days=rule.duration_days)
        grace_end = (
            intimation + timedelta(days=windows.grace_days)
            if intimation is not None
            else None
        )
        penalty_percent = (
            security_deposit_penalty(intimation, self._now.date(), windows=windows)
            if intimation is not None
            else None
        )

        first_until = self._calendar_date(CalendarEventKey.SD_PENALTY10_31MAY)
        second_until = self._calendar_date(CalendarEventKey.SD_PENALTY20_31JUL)
        current_stage: str | None = None
        today = self._now.date()
        if grace_end is not None and today <= grace_end:
            current_stage = "grace"
        elif first_until is not None and today <= first_until:
            current_stage = "penalty_10"
        elif second_until is not None and today <= second_until:
            current_stage = "penalty_20"
        elif second_until is not None:
            current_stage = "withdrawal"

        deposit_rows = self._db.scalars(
            select(SecurityDeposit)
            .where(SecurityDeposit.application_id == self._application.id)
        ).all()
        if any(
            row.status not in (SecurityDepositStatus.PENDING, SecurityDepositStatus.RELEASED)
            for row in deposit_rows
        ):
            current_stage = "paid"

        return DepositDeadlineRead(
            due_on=due_on,
            days_left=None if due_on is None else (due_on - today).days,
            intimated_on=intimation,
            penalty_percent=penalty_percent,
            first_penalty_until=first_until,
            second_penalty_until=second_until,
            withdrawal_after=second_until,
            current_stage=current_stage,
            apH_clause=rule.apH_clause,
        )

    def _loa_validity(self) -> LoaValidityRead | None:
        rule = self._rules.get("LOA_VALIDITY")
        if rule is None:
            return None
        valid_until = self._application.loa_valid_until
        if valid_until is None:
            timer = self._open_timer("LOA_VALIDITY")
            valid_until = timer.due_at.date() if timer is not None else None
        if valid_until is None:
            return None
        return LoaValidityRead(
            valid_until=valid_until,
            days_left=(valid_until - self._now.date()).days,
            expired=self._now.date() > valid_until,
            apH_clause=rule.apH_clause,
        )

    def _timers(self) -> list[TimerRead]:
        timers = self._db.scalars(
            select(Timer)
            .options(joinedload(Timer.deadline_rule))
            .where(
                Timer.application_id == self._application.id,
                Timer.status.in_(
                    (TimerStatus.PENDING, TimerStatus.DUE, TimerStatus.BREACHED)
                ),
            )
            .order_by(Timer.due_at.asc())
        ).all()
        return [
            TimerRead(
                id=timer.id,
                deadline_rule_code=timer.deadline_rule.code,
                status=timer.status.value,
                started_at=timer.started_at,
                due_at=timer.due_at,
                days_left=self._days_left_datetime(timer.due_at),
                apH_clause=timer.deadline_rule.apH_clause,
            )
            for timer in timers
        ]


@router.get(
    "/{application_id}/deadlines",
    response_model=ApplicationDeadlinesRead,
    responses={
        status.HTTP_403_FORBIDDEN: {"detail": "Not allowed"},
        status.HTTP_404_NOT_FOUND: {"detail": "Application not found"},
    },
    summary="Read the statutory clocks of one case file",
)
def get_application_deadlines(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    clock: ClockDep,
) -> ApplicationDeadlinesRead:
    """Return the appeal, Security Deposit and LoA clocks for the stage track."""
    application = _readable_application(db, current_user, application_id)
    return _DeadlinesService(db, application, clock.now()).read()


@router.get(
    "/{application_id}/appeal",
    response_model=list[AppealRead],
    responses={
        status.HTTP_403_FORBIDDEN: {"detail": "Not allowed"},
        status.HTTP_404_NOT_FOUND: {"detail": "Application not found"},
    },
    summary="Read the appeal filed against this application",
)
def get_application_appeal(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> list[AppealRead]:
    """Return the single appeal and its SAC / Council trail (APH 1.11)."""
    application = _readable_application(db, current_user, application_id)
    appeals = db.scalars(
        select(Appeal)
        .where(Appeal.application_id == application.id)
        .order_by(Appeal.filed_at.asc(), Appeal.created_at.asc())
    ).all()
    return [AppealRead.model_validate(item) for item in appeals]


# ---------------------------------------------------------------------------
# Decisions and fee movements
# ---------------------------------------------------------------------------


class CouncilRatificationRead(BaseModel):
    """Council ratification of one EC decision (APH 2.25a)."""

    ratified_on: date
    ec_recommendation_ref: str | None
    apH_clause: str
    """The clause of the ratified EC decision."""


class DecisionCasefileRead(DecisionRead):
    """A decision enriched with the committee name and Council ratification."""

    committee_name: str | None = None
    ratification: CouncilRatificationRead | None = None


@router.get(
    "/{application_id}/decisions",
    response_model=list[DecisionCasefileRead],
    responses={
        status.HTTP_403_FORBIDDEN: {"detail": "Not allowed"},
        status.HTTP_404_NOT_FOUND: {"detail": "Application not found"},
    },
    summary="Read the recorded decisions of the case file",
)
def get_application_decisions(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> list[DecisionCasefileRead]:
    """Return every EC / SAC / Council / SHC decision in reverse date order.

    Each row carries its APH clause and, when recorded, the Council
    ratification so the case file can show SAC outcomes and ratification
    without a second query (APH 1.10-1.11, 2.25a).
    """
    application = _readable_application(db, current_user, application_id)
    decisions = db.scalars(
        select(Decision)
        .options(
            joinedload(Decision.committee),
            joinedload(Decision.ratification),
        )
        .where(Decision.application_id == application.id)
        .order_by(Decision.decided_on.desc(), Decision.created_at.desc())
    ).all()
    reads: list[DecisionCasefileRead] = []
    for decision in decisions:
        read = DecisionCasefileRead(
            **DecisionRead.model_validate(decision).model_dump(),
            committee_name=decision.committee.name if decision.committee else None,
        )
        if decision.ratification is not None:
            read.ratification = CouncilRatificationRead(
                ratified_on=decision.ratification.ratified_on,
                ec_recommendation_ref=decision.ratification.ec_recommendation_ref,
                apH_clause=decision.apH_clause,
            )
        reads.append(read)
    return reads


@router.get(
    "/{application_id}/fee/transactions",
    response_model=list[FeeTransactionRead],
    responses={
        status.HTTP_403_FORBIDDEN: {"detail": "Not allowed"},
        status.HTTP_404_NOT_FOUND: {"detail": "Application not found"},
    },
    summary="Read the immutable fee movements of the application",
)
def list_application_fee_transactions(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> list[FeeTransactionRead]:
    """Return TER payments, refunds and deposit steps in chronological order."""
    application = _readable_application(db, current_user, application_id)
    transactions = db.scalars(
        select(FeeTransaction)
        .where(FeeTransaction.application_id == application.id)
        .order_by(FeeTransaction.paid_at.asc(), FeeTransaction.created_at.asc())
    ).all()
    return [FeeTransactionRead.model_validate(item) for item in transactions]
