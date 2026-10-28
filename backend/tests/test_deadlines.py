"""Deadline-rule seeds, start-event resolution and timer transitions."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import (
    Application,
    DeadlineRule,
    Decision,
    DecisionBody,
    DecisionLetter,
    DecisionLetterType,
    DecisionOutcome,
    Role,
    Timer,
    TimerStatus,
)
from app.services.deadlines import (
    DeadlineError,
    compute_due_at,
    end_of_day,
    resolve_start_event,
    start_timer,
    timer_status_at,
)
from tests.support import TestData


def test_deadline_rules_are_seeded_with_aph_values() -> None:
    with SessionLocal() as db:
        rules = {
            rule.code: rule
            for rule in db.scalars(select(DeadlineRule)).all()
        }

    assert {
        "APPEAL_WINDOW",
        "SECURITY_DEPOSIT",
        "LOA_VALIDITY",
        "ENROLMENT_UPLOAD",
        "IC_REPORT",
        "CLOSURE_REVOKE",
        "SHOW_CAUSE_REPLY",
    } <= set(rules)

    assert rules["APPEAL_WINDOW"].duration_days == 7
    assert rules["APPEAL_WINDOW"].start_event_configurable is True

    ladder = rules["SECURITY_DEPOSIT"].penalty_ladder
    assert [entry["penalty_percent"] for entry in ladder[:2]] == [10, 20]
    assert ladder[-1]["action"] == "WITHDRAWAL"
    assert rules["SECURITY_DEPOSIT"].duration_days == 15
    assert rules["SECURITY_DEPOSIT"].start_event == "EC_RECOMMENDS_LOA"

    assert rules["LOA_VALIDITY"].start_event == "LOA_ISSUED"
    assert rules["LOA_VALIDITY"].needs_verification is True

    assert rules["ENROLMENT_UPLOAD"].start_event == "ENROLMENT_UPLOAD_30NOV"
    assert rules["IC_REPORT"].start_event == "IC_REPORT_30JUN"
    assert rules["CLOSURE_REVOKE"].start_event == "CLOSURE_REVOKE_10APR"
    assert rules["SHOW_CAUSE_REPLY"].needs_verification is True


def test_compute_due_at_is_a_pure_day_addition() -> None:
    start = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    assert compute_due_at(start, 7) == datetime(2026, 5, 8, 12, 0, tzinfo=UTC)
    assert compute_due_at(start, 0) == start

    with pytest.raises(DeadlineError):
        compute_due_at(start, -1)


def test_fixed_calendar_event_resolves_to_end_of_day(test_data: TestData) -> None:
    with SessionLocal() as db:
        application = db.get(Application, test_data.applications["west"])
        assert application is not None
        rule = db.scalar(
            select(DeadlineRule).where(DeadlineRule.code == "ENROLMENT_UPLOAD")
        )
        assert rule is not None

        timer = start_timer(db, application, rule)
        db.commit()
        try:
            assert timer.started_at == datetime(2026, 11, 30, 23, 59, 59, tzinfo=UTC)
            assert timer.due_at == timer.started_at
            assert timer.status == TimerStatus.PENDING
        finally:
            db.delete(timer)
            db.commit()


def test_security_deposit_timer_starts_at_ec_recommendation(test_data: TestData) -> None:
    """The deposit clock starts with the EC LoA recommendation (APH 2.25f)."""
    with SessionLocal() as db:
        application = db.get(Application, test_data.applications["west"])
        assert application is not None
        rule = db.scalar(
            select(DeadlineRule).where(DeadlineRule.code == "SECURITY_DEPOSIT")
        )
        assert rule is not None

        decision = Decision(
            application_id=application.id,
            body=DecisionBody.EC,
            outcome=DecisionOutcome.LOA,
            decided_on=date(2026, 5, 1),
            notes="Fictional EC recommendation for the deadline test.",
            apH_clause="APH 2.25f",
        )
        db.add(decision)
        db.flush()

        timer = start_timer(db, application, rule)
        db.commit()
        try:
            assert timer.started_at == end_of_day(date(2026, 5, 1))
            assert timer.due_at == end_of_day(date(2026, 5, 16))
        finally:
            db.delete(timer)
            db.delete(decision)
            db.commit()


def test_appeal_window_starts_at_published_decision(test_data: TestData) -> None:
    suffix = uuid.uuid4().hex[:8].upper()
    with SessionLocal() as db:
        application = db.get(Application, test_data.applications["west"])
        assert application is not None
        rule = db.scalar(
            select(DeadlineRule).where(DeadlineRule.code == "APPEAL_WINDOW")
        )
        assert rule is not None

        letter = DecisionLetter(
            application_id=application.id,
            letter_type=DecisionLetterType.LOD,
            letter_number=f"TEST/APPEAL/{suffix}",
            issued_on=date(2026, 5, 1),
            published_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
            body_text="Fictional decision letter.",
        )
        db.add(letter)
        db.flush()

        timer = start_timer(db, application, rule, letter=letter)
        db.commit()
        try:
            assert timer.started_at == datetime(2026, 5, 2, 10, 0, tzinfo=UTC)
            assert timer.due_at == datetime(2026, 5, 9, 10, 0, tzinfo=UTC)
        finally:
            db.delete(timer)
            db.delete(letter)
            db.commit()


def test_show_cause_reply_starts_at_letter_issue(test_data: TestData) -> None:
    suffix = uuid.uuid4().hex[:8].upper()
    with SessionLocal() as db:
        application = db.get(Application, test_data.applications["west"])
        assert application is not None
        rule = db.scalar(
            select(DeadlineRule).where(DeadlineRule.code == "SHOW_CAUSE_REPLY")
        )
        assert rule is not None

        letter = DecisionLetter(
            application_id=application.id,
            letter_type=DecisionLetterType.SHOW_CAUSE,
            letter_number=f"TEST/SHOWCAUSE/{suffix}",
            issued_on=date(2026, 6, 1),
            body_text="Fictional show-cause notice.",
        )
        db.add(letter)
        db.flush()

        timer = start_timer(db, application, rule)
        db.commit()
        try:
            assert timer.started_at == end_of_day(date(2026, 6, 1))
            assert timer.due_at == end_of_day(date(2026, 6, 16))
        finally:
            db.delete(timer)
            db.delete(letter)
            db.commit()


def test_unknown_start_event_is_rejected(test_data: TestData) -> None:
    with SessionLocal() as db:
        application = db.get(Application, test_data.applications["west"])
        assert application is not None
        rule = DeadlineRule(
            code="TEST-UNKNOWN-START",
            start_event="NOT_A_REAL_EVENT",
            duration_days=1,
            owner_role=Role.REGIONAL_OFFICER,
            penalty_ladder=[],
            apH_clause="DEMO",
            needs_verification=True,
        )
        with pytest.raises(DeadlineError):
            resolve_start_event(db, rule, application)


def test_timer_status_transitions() -> None:
    timer = Timer(
        started_at=datetime(2026, 5, 1, tzinfo=UTC),
        due_at=datetime(2026, 5, 10, 23, 59, 59, tzinfo=UTC),
        status=TimerStatus.PENDING,
        fired_levels=[],
    )

    assert timer_status_at(timer, datetime(2026, 5, 9, 12, 0, tzinfo=UTC)) == (
        TimerStatus.PENDING
    )
    assert timer_status_at(timer, datetime(2026, 5, 10, 0, 0, tzinfo=UTC)) == (
        TimerStatus.DUE
    )
    assert timer_status_at(timer, datetime(2026, 5, 10, 23, 59, 59, tzinfo=UTC)) == (
        TimerStatus.DUE
    )
    assert timer_status_at(timer, datetime(2026, 5, 11, 0, 0, tzinfo=UTC)) == (
        TimerStatus.BREACHED
    )

    timer.status = TimerStatus.COMPLETED
    assert timer_status_at(timer, datetime(2026, 5, 11, 0, 0, tzinfo=UTC)) == (
        TimerStatus.COMPLETED
    )


def test_timer_expires_at_its_due_instant_not_just_its_due_date() -> None:
    """The workflow closes the window at the instant; the timer must agree."""
    timer = Timer(
        started_at=datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
        due_at=datetime(2026, 5, 8, 10, 0, tzinfo=UTC),
        status=TimerStatus.PENDING,
        fired_levels=[],
    )

    assert timer_status_at(timer, datetime(2026, 5, 8, 9, 59, tzinfo=UTC)) == (
        TimerStatus.DUE
    )
    assert timer_status_at(timer, datetime(2026, 5, 8, 10, 0, tzinfo=UTC)) == (
        TimerStatus.DUE
    )
    assert timer_status_at(timer, datetime(2026, 5, 8, 10, 1, tzinfo=UTC)) == (
        TimerStatus.BREACHED
    )
