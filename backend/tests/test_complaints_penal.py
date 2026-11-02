"""Complaint, penal-action and fine behaviour required by the demo.

Covers the four guards the acceptance criteria name:

* the appeal window and the one-appeal rule (APH 1.11a);
* complaint anonymity auto-rejection with the CVC reason (APH 7.10h);
* the hearing-before-action guard (APH 6.50h proviso);
* the excess-admission fine of five times the total course fee (APH 7.3g).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.clock import SimulatedClock
from app.db.session import SessionLocal
from app.models.appeal import Appeal
from app.models.application import Application
from app.models.complaint import PenalAction
from app.models.enums import (
    ApplicationCategory,
    ApplicationStatus,
    ApplicationTrack,
    PenalActionType,
    ProgrammeMode,
    ProgrammeStatus,
    Role,
    SecurityDepositStatus,
    WorkflowAction,
    WorkflowStage,
)
from app.models.institution import Institution
from app.models.programme import ApprovedIntakeLedger, Programme
from app.models.security_deposit import SecurityDeposit
from app.schemas.workflow import WorkflowActionRequest
from app.services import penal_actions
from app.services.audit import AuditService
from app.services.workflow_context import Transition, TransitionContext
from app.services.workflow_guards import no_prior_appeal, within_appeal_window
from tests.conftest import TEST_PASSWORD
from tests.support import TestData, login

# ---------------------------------------------------------------------------
# Appeal guard (APH 1.11a)
# ---------------------------------------------------------------------------


def _guard_context(db, application: Application) -> TransitionContext:
    transition = Transition(
        action=WorkflowAction.FILE_APPEAL,
        from_statuses=frozenset({ApplicationStatus.APPEAL_WINDOW}),
        to_status=ApplicationStatus.SAC_REVIEW,
        roles=frozenset({Role.INSTITUTION_ADMIN}),
        stage=WorkflowStage.DECISION,
        label="File appeal",
        description="File the one permitted appeal.",
        apH_clause="APH 1.11a",
    )
    return TransitionContext(
        db=db,
        application=application,
        actor=None,  # guards under test never read the actor
        transition=transition,
        payload=WorkflowActionRequest(),
        clock=SimulatedClock(),
        audit=AuditService(db),
        request=None,
        definition=None,  # guards under test never read the definition
    )


def test_appeal_window_guard_rejects_a_late_appeal(test_data: TestData) -> None:
    with SessionLocal() as db:
        application = db.get(Application, test_data.applications["west"])
        assert application is not None
        application.appeal_deadline = datetime.now(UTC) - timedelta(days=1)
        reason = within_appeal_window(_guard_context(db, application))
    assert reason is not None
    assert "closed" in reason
    assert "APH 1.11a" in reason


def test_appeal_window_guard_allows_an_appeal_inside_the_window(
    test_data: TestData,
) -> None:
    with SessionLocal() as db:
        application = db.get(Application, test_data.applications["west"])
        assert application is not None
        application.appeal_deadline = datetime.now(UTC) + timedelta(days=1)
        assert within_appeal_window(_guard_context(db, application)) is None


def test_only_one_appeal_is_permitted(test_data: TestData) -> None:
    application_id = test_data.applications["west"]
    with SessionLocal() as db:
        application = db.get(Application, application_id)
        assert application is not None
        db.add(
            Appeal(
                application_id=application_id,
                filed_at=datetime.now(UTC),
                within_deadline=True,
                loop_no=1,
                apH_clause="APH 1.11a",
            )
        )
        db.flush()
        reason = no_prior_appeal(_guard_context(db, application))
        db.rollback()
    assert reason is not None
    assert "Only one appeal" in reason


# ---------------------------------------------------------------------------
# Complaint anonymity (APH 7.10h)
# ---------------------------------------------------------------------------


def _auth_headers(client: TestClient, test_data: TestData, key: str) -> dict[str, str]:
    user = test_data.users[key]
    payload = login(client, user.email, TEST_PASSWORD)
    return {"Authorization": f"Bearer {payload['access_token']}"}


def test_anonymous_complaint_is_rejected_with_the_cvc_reason(
    api_client: TestClient, test_data: TestData
) -> None:
    headers = _auth_headers(api_client, test_data, "institution_admin_west")
    response = api_client.post(
        "/complaints",
        headers=headers,
        json={
            "institution_id": str(test_data.institutions["west"]),
            "source": "PORTAL",
            "category": "ADMISSION",
            "description": "Fictional anonymous complaint used by the test suite.",
            "is_anonymous": True,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "RECEIVED"
    assert body["is_anonymous"] is True
    assert body["rejection_clause"] == "APH 7.10h"
    assert "CVC" in body["rejection_reason"]
    assert body["complainant_verified"] is False

    # The refused intake can never move to PGRC or SCSC.
    verifier = _auth_headers(api_client, test_data, "complaints")
    verify = api_client.post(f"/complaints/{body['id']}/verify", headers=verifier, json={})
    assert verify.status_code == 400
    assert "APH 7.10h" in verify.json()["detail"]

    with SessionLocal() as db:
        db.execute(delete(PenalAction).where(PenalAction.complaint_id == uuid.UUID(body["id"])))
        from app.models.complaint import Complaint

        db.execute(delete(Complaint).where(Complaint.id == uuid.UUID(body["id"])))
        db.commit()


def test_verified_complaint_enters_the_pgrc_queue(
    api_client: TestClient, test_data: TestData
) -> None:
    headers = _auth_headers(api_client, test_data, "institution_admin_west")
    response = api_client.post(
        "/complaints",
        headers=headers,
        json={
            "institution_id": str(test_data.institutions["west"]),
            "source": "PORTAL",
            "category": "INFRASTRUCTURE",
            "description": "Fictional verified complaint used by the test suite.",
            "complainant_name": "Fictional Complainant",
            "complainant_contact": "complainant@example.edu",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "PGRC"
    assert body["rejection_reason"] is None

    with SessionLocal() as db:
        from app.models.complaint import Complaint

        db.execute(delete(Complaint).where(Complaint.id == uuid.UUID(body["id"])))
        db.commit()


# ---------------------------------------------------------------------------
# Hearing before action (APH 6.50h proviso)
# ---------------------------------------------------------------------------


@pytest.fixture
def penal_action(test_data: TestData):
    with SessionLocal() as db:
        action = PenalAction(
            institution_id=test_data.institutions["west"],
            action_type=PenalActionType.NO_ADMISSION,
            violation_code="g",
            apH_clause="APH 7.3, 7.4g",
        )
        db.add(action)
        db.commit()
        db.refresh(action)
        action_id = action.id
    yield action_id
    with SessionLocal() as db:
        db.execute(delete(PenalAction).where(PenalAction.id == action_id))
        db.commit()


def test_penal_action_without_a_hearing_is_refused(penal_action: uuid.UUID) -> None:
    with SessionLocal() as db:
        action = db.get(PenalAction, penal_action)
        assert action is not None
        with pytest.raises(penal_actions.PenalActionError) as excinfo:
            penal_actions.issue_penal_action(
                db,
                action,
                order_number="AICTE/PENAL/2026/0001",
                issued_on=date(2026, 6, 1),
                speaking_order="Fictional speaking order.",
                actor=None,
                audit=AuditService(db),
            )
        assert "APH 6.50h" in str(excinfo.value)
        db.rollback()


def test_penal_action_is_issued_after_a_hearing(penal_action: uuid.UUID) -> None:
    with SessionLocal() as db:
        action = db.get(PenalAction, penal_action)
        assert action is not None
        penal_actions.schedule_hearing(
            db,
            action,
            hearing_on=date(2026, 5, 20),
            notes="Fictional SHC hearing.",
            actor=None,
            audit=AuditService(db),
        )
        penal_actions.issue_penal_action(
            db,
            action,
            order_number="AICTE/PENAL/2026/0001",
            issued_on=date(2026, 6, 1),
            speaking_order="Fictional speaking order.",
            actor=None,
            audit=AuditService(db),
        )
        db.commit()
        db.refresh(action)
        assert action.hearing_done is True
        assert action.issued_on == date(2026, 6, 1)
        assert action.consequences is not None
        assert action.consequences["admission_barred"] is True


def test_withdrawn_institution_can_reapply_only_after_two_years(
    penal_action: uuid.UUID,
) -> None:
    with SessionLocal() as db:
        action = db.get(PenalAction, penal_action)
        assert action is not None
        action.action_type = PenalActionType.INSTITUTION_WITHDRAWAL
        penal_actions.schedule_hearing(
            db,
            action,
            hearing_on=date(2026, 5, 20),
            notes="Fictional SHC hearing.",
            actor=None,
            audit=AuditService(db),
        )
        penal_actions.issue_penal_action(
            db,
            action,
            order_number="AICTE/PENAL/2026/0002",
            issued_on=date(2026, 6, 1),
            speaking_order="Fictional speaking order.",
            actor=None,
            audit=AuditService(db),
        )
        penal_actions.request_restoration(
            db,
            action,
            requested_on=date(2027, 6, 1),
            actor=None,
            audit=AuditService(db),
        )
        db.commit()
        db.refresh(action)
        assert action.restoration_eligible_from == date(2028, 6, 1)
        assert action.restoration_status == "NOT_YET_ELIGIBLE"
        assert action.consequences is not None
        assert action.consequences["different_name_required"] is True


# ---------------------------------------------------------------------------
# Excess-admission fine (APH 7.3g)
# ---------------------------------------------------------------------------


def _finance_application(institution_id: uuid.UUID) -> Application:
    """A transient application carrying the finance section the calculator reads."""
    return Application(
        institution_id=institution_id,
        track=ApplicationTrack.NEW_INSTITUTION,
        application_type="NEW_INSTITUTION",
        category=ApplicationCategory.CAT1_CUTOFF,
        academic_year="2026-27",
        status=ApplicationStatus.SUBMITTED,
        current_stage=WorkflowStage.SCRUTINY,
        data={
            "finance": {
                "tuition_fee": 150000,
                "development_fee": 25000,
                "other_fees": 10000,
            }
        },
    )


def test_excess_admission_fine_is_five_times_the_total_course_fee(
    test_data: TestData,
) -> None:
    institution_id = test_data.institutions["west"]
    with SessionLocal() as db:
        institution = db.get(Institution, institution_id)
        assert institution is not None
        programme = Programme(
            institution_id=institution_id,
            programme_family="ENGINEERING_TECHNOLOGY",
            level="UG",
            course_name=f"Fictional Test Engineering {uuid.uuid4().hex[:6]}",
            duration_years=Decimal("4.0"),
            approved_intake=60,
            mode=ProgrammeMode.REGULAR,
            status=ProgrammeStatus.ACTIVE,
            apH_clause="APH 2.25b",
        )
        db.add(programme)
        db.flush()
        db.add(
            ApprovedIntakeLedger(
                programme_id=programme.id,
                academic_year="2026-27",
                approved_intake=60,
                admitted_total=66,
                apH_clause="APH 6.12",
            )
        )
        db.commit()
        try:
            fine = penal_actions.calculate_excess_admission_fine(
                db, _finance_application(institution_id)
            )
            # Annual fee 185,000 INR = 18,500,000 paise; 4 years = 74,000,000 paise.
            assert fine.excess_admissions == 6
            assert fine.total_course_fee_paise == 74_000_000
            assert fine.fine_paise == 5 * 74_000_000 * 6
            assert fine.apH_clause == "APH 7.3g"
            assert len(fine.lines) == 1
        finally:
            db.execute(
                delete(ApprovedIntakeLedger).where(
                    ApprovedIntakeLedger.programme_id == programme.id
                )
            )
            db.execute(delete(Programme).where(Programme.id == programme.id))
            db.commit()


def test_no_excess_admission_means_no_fine(test_data: TestData) -> None:
    institution_id = test_data.institutions["west"]
    with SessionLocal() as db:
        programme = Programme(
            institution_id=institution_id,
            programme_family="ENGINEERING_TECHNOLOGY",
            level="UG",
            course_name=f"Fictional Test Engineering {uuid.uuid4().hex[:6]}",
            duration_years=Decimal("4.0"),
            approved_intake=60,
            mode=ProgrammeMode.REGULAR,
            status=ProgrammeStatus.ACTIVE,
            apH_clause="APH 2.25b",
        )
        db.add(programme)
        db.flush()
        db.add(
            ApprovedIntakeLedger(
                programme_id=programme.id,
                academic_year="2026-27",
                approved_intake=60,
                admitted_total=60,
                apH_clause="APH 6.12",
            )
        )
        db.commit()
        try:
            fine = penal_actions.calculate_excess_admission_fine(
                db, _finance_application(institution_id)
            )
            assert fine.excess_admissions == 0
            assert fine.fine_paise == 0
        finally:
            db.execute(
                delete(ApprovedIntakeLedger).where(
                    ApprovedIntakeLedger.programme_id == programme.id
                )
            )
            db.execute(delete(Programme).where(Programme.id == programme.id))
            db.commit()


def test_penal_action_rejects_an_action_the_code_does_not_permit(
    test_data: TestData,
) -> None:
    with SessionLocal() as db:
        institution = db.get(Institution, test_data.institutions["west"])
        assert institution is not None
        with pytest.raises(penal_actions.PenalActionError) as excinfo:
            penal_actions.record_penal_action(
                db,
                institution=institution,
                action_type=PenalActionType.GRANT_INELIGIBLE,
                violation_code="g",
                actor=None,
                audit=AuditService(db),
            )
        assert "does not permit" in str(excinfo.value)
        db.rollback()


# ---------------------------------------------------------------------------
# End-to-end demo chain (acceptance criterion)
# ---------------------------------------------------------------------------


def test_demo_case_runs_complaint_to_restoration(
    api_client: TestClient, test_data: TestData
) -> None:
    """complaint > show-cause > hearing > penal action > restoration (APH 7.10-7.11)."""
    institution_admin = _auth_headers(api_client, test_data, "institution_admin_west")
    scsc = _auth_headers(api_client, test_data, "complaints")
    shc = _auth_headers(api_client, test_data, "shc")
    ec = _auth_headers(api_client, test_data, "ec")

    created = api_client.post(
        "/complaints",
        headers=institution_admin,
        json={
            "institution_id": str(test_data.institutions["west"]),
            "source": "PORTAL",
            "category": "EXCESS_ADMISSION",
            "description": "Fictional end-to-end complaint used by the test suite.",
            "complainant_name": "Fictional Complainant",
            "complainant_contact": "complainant@example.edu",
        },
    )
    assert created.status_code == 201, created.text
    complaint_id = created.json()["id"]
    assert created.json()["status"] == "PGRC"

    try:
        verified = api_client.post(f"/complaints/{complaint_id}/verify", headers=scsc, json={})
        assert verified.status_code == 200, verified.text
        assert verified.json()["status"] == "SCSC"

        scsc_decision = api_client.post(
            f"/complaints/{complaint_id}/scsc-decision",
            headers=scsc,
            json={"decision": "SHOW_CAUSE", "notes": "Fictional show-cause."},
        )
        assert scsc_decision.status_code == 200, scsc_decision.text
        assert scsc_decision.json()["status"] == "SHOW_CAUSE"
        assert scsc_decision.json()["show_cause_due_on"] is not None

        reply = api_client.post(
            f"/complaints/{complaint_id}/show-cause-reply",
            headers=institution_admin,
            json={"reply": "Fictional reply with compliance documents."},
        )
        assert reply.status_code == 200, reply.text
        assert reply.json()["status"] == "HEARING"

        hearing = api_client.post(
            f"/complaints/{complaint_id}/shc-hearing",
            headers=shc,
            json={"hearing_on": "2026-06-10", "findings": "Fictional SHC findings."},
        )
        assert hearing.status_code == 200, hearing.text
        assert hearing.json()["shc_hearing_on"] == "2026-06-10"

        ec_decision = api_client.post(
            f"/complaints/{complaint_id}/ec-decision",
            headers=ec,
            json={
                "decision": "PENAL_ACTION",
                "speaking_order": "Fictional detailed Speaking Order (APH 7.10g).",
            },
        )
        assert ec_decision.status_code == 200, ec_decision.text
        assert ec_decision.json()["status"] == "DECIDED"

        recorded = api_client.post(
            f"/complaints/{complaint_id}/penal-actions",
            headers=ec,
            json={"action_type": "NO_ADMISSION", "violation_code": "g"},
        )
        assert recorded.status_code == 201, recorded.text
        penal_action_id = recorded.json()["id"]
        assert recorded.json()["hearing_done"] is False

        # The hearing guard blocks issue until a hearing is recorded.
        blocked = api_client.post(
            f"/penal-actions/{penal_action_id}/issue",
            headers=ec,
            json={
                "order_number": "AICTE/PENAL/2026/9001",
                "speaking_order": "Fictional Speaking Order.",
            },
        )
        assert blocked.status_code == 400
        assert "APH 6.50h" in blocked.json()["detail"]

        scheduled = api_client.post(
            f"/penal-actions/{penal_action_id}/hearing",
            headers=shc,
            json={"hearing_on": "2026-06-20", "notes": "Fictional hearing."},
        )
        assert scheduled.status_code == 200, scheduled.text

        issued = api_client.post(
            f"/penal-actions/{penal_action_id}/issue",
            headers=ec,
            json={
                "order_number": "AICTE/PENAL/2026/9001",
                "speaking_order": "Fictional Speaking Order.",
            },
        )
        assert issued.status_code == 200, issued.text
        assert issued.json()["hearing_done"] is True
        assert issued.json()["consequences"]["admission_barred"] is True

        restoration = api_client.post(
            f"/penal-actions/{penal_action_id}/restoration-request",
            headers=institution_admin,
            json={},
        )
        assert restoration.status_code == 200, restoration.text
        assert restoration.json()["restoration_status"] == "REQUESTED"
    finally:
        with SessionLocal() as db:
            db.execute(
                delete(PenalAction).where(PenalAction.complaint_id == uuid.UUID(complaint_id))
            )
            from app.models.complaint import Complaint

            db.execute(delete(Complaint).where(Complaint.id == uuid.UUID(complaint_id)))
            db.commit()


# ---------------------------------------------------------------------------
# Security Deposit release (APH 6.46)
# ---------------------------------------------------------------------------


def test_deposit_release_waits_for_every_clearance(
    api_client: TestClient, test_data: TestData
) -> None:
    """The NOC needs PGRC, Vigilance and grants clearance first (APH 6.46b-d)."""

    application_id = test_data.applications["west"]
    with SessionLocal() as db:
        deposit = SecurityDeposit(
            institution_id=test_data.institutions["west"],
            application_id=application_id,
            programme_family="ENGINEERING_TECHNOLOGY",
            level="UG",
            required_paise=350000000,
            doubled_for_leased=False,
            created_on=date(2024, 6, 1),
            maturity_on=date(2026, 6, 1),
            status=SecurityDepositStatus.PAID,
            apH_clause="APH Table 1.4",
        )
        db.add(deposit)
        db.commit()
        deposit_id = deposit.id

    institution = _auth_headers(api_client, test_data, "institution_admin_west")
    regulation = _auth_headers(api_client, test_data, "regulation")
    regional = _auth_headers(api_client, test_data, "regional")
    base = f"/applications/{application_id}/security-deposits/{deposit_id}"

    try:
        requested = api_client.post(f"{base}/release-request", headers=institution, json={})
        assert requested.status_code == 200, requested.text
        body = requested.json()
        assert body["release_requested_on"] is not None
        clearances = body["release_clearances"]
        mandatory = [item["code"] for item in clearances if item["mandatory"]]
        assert set(mandatory) == {"PGRC", "VIGILANCE", "GRANTS"}
        assert all(item["status"] == "PENDING" for item in clearances)

        blocked = api_client.post(
            f"{base}/release", headers=regional, json={"noc_number": "AICTE/NOC/2026/9001"}
        )
        assert blocked.status_code == 400, blocked.text
        assert "PGRC" in blocked.json()["detail"]

        for code in mandatory:
            cleared = api_client.post(
                f"{base}/clearance",
                headers=regulation,
                json={"code": code, "cleared": True},
            )
            assert cleared.status_code == 200, cleared.text

        released = api_client.post(
            f"{base}/release", headers=regional, json={"noc_number": "AICTE/NOC/2026/9001"}
        )
        assert released.status_code == 200, released.text
        assert released.json()["status"] == "RELEASED"
        assert released.json()["noc_number"] == "AICTE/NOC/2026/9001"
        assert released.json()["released_on"] is not None
    finally:
        with SessionLocal() as db:
            db.execute(delete(SecurityDeposit).where(SecurityDeposit.id == deposit_id))
            db.commit()


def test_withdrawn_deposit_cannot_be_released(api_client: TestClient, test_data: TestData) -> None:
    """A withdrawn deposit leaves the release path (APH 2.25f)."""

    application_id = test_data.applications["west"]
    with SessionLocal() as db:
        deposit = SecurityDeposit(
            institution_id=test_data.institutions["west"],
            application_id=application_id,
            programme_family="ENGINEERING_TECHNOLOGY",
            level="PG",
            required_paise=150000000,
            doubled_for_leased=False,
            created_on=date(2024, 6, 1),
            maturity_on=date(2026, 6, 1),
            status=SecurityDepositStatus.PENDING,
            apH_clause="APH Table 1.4",
        )
        db.add(deposit)
        db.commit()
        deposit_id = deposit.id

    institution = _auth_headers(api_client, test_data, "institution_admin_west")
    base = f"/applications/{application_id}/security-deposits/{deposit_id}"
    try:
        withdrawn = api_client.post(f"{base}/withdraw", headers=institution, json={})
        assert withdrawn.status_code == 200, withdrawn.text
        assert withdrawn.json()["status"] == "WITHDRAWN"

        blocked = api_client.post(f"{base}/release-request", headers=institution, json={})
        assert blocked.status_code == 400, blocked.text
        assert "APH 6.46" in blocked.json()["detail"]
    finally:
        with SessionLocal() as db:
            db.execute(delete(SecurityDeposit).where(SecurityDeposit.id == deposit_id))
            db.commit()
