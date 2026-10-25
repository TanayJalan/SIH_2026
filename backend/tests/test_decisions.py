"""Decision, letter and Council-ratification persistence and relationships."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import (
    Application,
    CouncilRatification,
    Decision,
    DecisionBody,
    DecisionLetter,
    DecisionLetterType,
    DecisionOutcome,
)
from tests.support import TestData


def test_decision_letter_and_ratification_relationships(test_data: TestData) -> None:
    suffix = uuid.uuid4().hex[:8].upper()
    with SessionLocal() as db:
        application = db.get(Application, test_data.applications["west"])
        assert application is not None

        decision = Decision(
            application_id=application.id,
            body=DecisionBody.EC,
            outcome=DecisionOutcome.LOA,
            decided_on=date(2026, 6, 1),
            quorum_met=True,
            notes="Fictional EC decision for the test suite.",
            apH_clause="APH 1.10",
        )
        db.add(decision)
        db.flush()

        letter = DecisionLetter(
            application_id=application.id,
            decision_id=decision.id,
            letter_type=DecisionLetterType.LOA,
            letter_number=f"TEST/LOA/{suffix}",
            issued_on=date(2026, 6, 2),
            published_at=datetime(2026, 6, 2, 12, 0, tzinfo=UTC),
            appeal_clock_start=datetime(2026, 6, 2, 12, 0, tzinfo=UTC),
            appeal_deadline=datetime(2026, 6, 9, 12, 0, tzinfo=UTC),
            body_text="Fictional letter of approval.",
            acknowledged_by=test_data.users["institution_admin_west"].id,
            acknowledged_at=datetime(2026, 6, 3, 9, 0, tzinfo=UTC),
        )
        ratification = CouncilRatification(
            decision_id=decision.id,
            ratified_on=date(2026, 6, 10),
            ratified_by=test_data.users["ec"].id,
            ec_recommendation_ref=f"EC/{suffix}",
        )
        db.add_all([letter, ratification])
        db.commit()
        decision_id = decision.id
        letter_id = letter.id
        ratification_id = ratification.id

    try:
        with SessionLocal() as db:
            decision = db.get(Decision, decision_id)
            assert decision is not None
            assert decision.application.id == test_data.applications["west"]
            assert decision.quorum_met is True
            assert [row.id for row in decision.letters] == [letter_id]
            assert decision.ratification is not None
            assert decision.ratification.id == ratification_id
            assert decision.ratification.ec_recommendation_ref == f"EC/{suffix}"

            letter = db.get(DecisionLetter, letter_id)
            assert letter is not None
            assert letter.decision is not None
            assert letter.decision.id == decision_id
            assert letter.acknowledged_by_user is not None
            assert letter.acknowledged_by_user.id == (
                test_data.users["institution_admin_west"].id
            )

            ratification = db.get(CouncilRatification, ratification_id)
            assert ratification is not None
            assert ratification.ratified_by_user is not None
            assert ratification.ratified_by_user.id == test_data.users["ec"].id

            application = db.get(Application, test_data.applications["west"])
            assert application is not None
            assert any(row.id == decision_id for row in application.decisions)
            assert any(row.id == letter_id for row in application.decision_letters)
    finally:
        with SessionLocal() as db:
            decision = db.get(Decision, decision_id)
            if decision is not None:
                db.delete(decision)
                db.commit()
            leftover = db.scalar(
                select(DecisionLetter).where(DecisionLetter.id == letter_id)
            )
            if leftover is not None:
                db.delete(leftover)
                db.commit()
