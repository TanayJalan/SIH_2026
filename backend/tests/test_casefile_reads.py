"""Case-file read models: deadlines, decisions, appeal and fee transactions.

These endpoints only read configuration-driven data, so the tests assert the
shape and the configuration linkage (deadline rules, academic calendar rows,
APH clauses) rather than engine behaviour.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.models import Application
from tests.support import TestData, auth_headers, create_draft, pay_application_fee


def _headers(api_client: TestClient, data: TestData, key: str) -> dict[str, str]:
    return auth_headers(api_client, data.users[key], data.password)


def test_deadlines_of_a_submitted_application(
    api_client: TestClient, test_data: TestData
) -> None:
    application_id = test_data.applications["west"]
    response = api_client.get(
        f"/applications/{application_id}/deadlines",
        headers=_headers(api_client, test_data, "institution_admin_west"),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert str(body["application_id"]) == str(application_id)
    assert body["appeal"] is not None and "APH 1.11a" in body["appeal"]["apH_clause"]
    # No LoA, no deposit intimation and no running timer on this fictional file.
    assert body["security_deposit"] is None
    assert body["loa_validity"] is None
    assert body["timers"] == []


def test_deadlines_read_the_configuration_rows(
    api_client: TestClient, test_data: TestData
) -> None:
    """Set the read-model columns directly and assert the clocks follow."""
    application_id = test_data.applications["east"]
    headers = _headers(api_client, test_data, "institution_admin_east")

    with SessionLocal() as db:
        application = db.get(Application, application_id)
        assert application is not None
        application.appeal_deadline = datetime.now(UTC) + timedelta(days=3)
        application.security_deposit_due_on = date.today() + timedelta(days=10)
        application.loa_valid_until = date.today() + timedelta(days=730)
        db.commit()

    body = api_client.get(
        f"/applications/{application_id}/deadlines", headers=headers
    ).json()
    assert abs(body["appeal"]["days_left"]) <= 4
    assert body["appeal"]["letter_type"] is None
    assert body["loa_validity"]["apH_clause"] == "APH 1.10b"
    assert body["loa_validity"]["valid_until"] == (
        date.today() + timedelta(days=730)
    ).isoformat()
    deposit = body["security_deposit"]
    assert deposit is not None and deposit["apH_clause"] == "APH 2.25f"
    assert deposit["due_on"] == (date.today() + timedelta(days=10)).isoformat()
    # The ladder windows come from the seeded academic calendar, not constants.
    assert deposit["first_penalty_until"].endswith("-05-31")
    assert deposit["second_penalty_until"].endswith("-07-31")
    assert deposit["current_stage"] in {
        "grace",
        "penalty_10",
        "penalty_20",
        "withdrawal",
        "paid",
    }


def test_deadlines_are_denied_to_a_foreign_institution(
    api_client: TestClient, test_data: TestData
) -> None:
    response = api_client.get(
        f"/applications/{test_data.applications['west']}/deadlines",
        headers=_headers(api_client, test_data, "institution_admin_east"),
    )
    assert response.status_code == 403


def test_decisions_carry_their_clause_and_ratification(
    api_client: TestClient, test_data: TestData
) -> None:
    from app.models import (
        CouncilRatification,
        Decision,
        DecisionBody,
        DecisionOutcome,
    )

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
            notes="Fictional EC decision for the case-file read test.",
            apH_clause="APH 1.10a",
        )
        db.add(decision)
        db.flush()
        db.add(
            CouncilRatification(
                decision_id=decision.id,
                ratified_on=date(2026, 6, 10),
                ratified_by=test_data.users["super"].id,
                ec_recommendation_ref=f"EC/{suffix}",
            )
        )
        decision_id = str(decision.id)
        db.commit()

    try:
        body = api_client.get(
            f"/applications/{test_data.applications['west']}/decisions",
            headers=_headers(api_client, test_data, "institution_admin_west"),
        ).json()
        row = next(item for item in body if item["id"] == decision_id)
        assert row["apH_clause"] == "APH 1.10a"
        assert row["outcome"] == "LOA"
        ratification = row["ratification"]
        assert ratification is not None
        assert ratification["ratified_on"] == "2026-06-10"
        assert ratification["apH_clause"] == "APH 1.10a"
    finally:
        with SessionLocal() as db:
            decision = db.get(Decision, uuid.UUID(decision_id))
            if decision is not None:
                db.delete(decision)
                db.commit()


def test_fee_transactions_list_payments_with_clauses(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    headers = _headers(api_client, test_data, "institution_admin_west")
    draft = create_draft(api_client, headers, workspace_applications)
    pay_application_fee(api_client, headers, draft["id"])

    response = api_client.get(
        f"/applications/{draft['id']}/fee/transactions", headers=headers
    )
    assert response.status_code == 200, response.text
    transactions = response.json()
    assert len(transactions) >= 1
    for transaction in transactions:
        assert isinstance(transaction["amount_paise"], int)
        assert transaction["apH_clause"]
        assert transaction["kind"] in {"TER", "PENALTY", "REFUND", "DEDUCTION"}
