"""Apache-7 workflow tests: state machine, decisions, appeals and letters.

Every transition is data in ``workflow_transitions``; these tests exercise the
real API so they cover the engine, the guards, the effects and the seed data
together. The four APH tracks are represented by one deep test each, and the
cross-cutting rules (single appeal, send-back once, deposit ladder, LoA expiry,
cut-off dates, role separation, reopen once, locked data) get their own test
(APH Annexure-7, 1.8-1.11, 2.3-2.25).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.clock import SimulatedClock
from app.db.session import SessionLocal
from app.models import (
    AcademicCalendarEvent,
    Application,
    ApplicationCategory,
    ApplicationProgram,
    ApplicationStatus,
    ApplicationTrack,
    CouncilRatification,
    DeadlineRule,
    Decision,
    DecisionBody,
    DecisionOutcome,
    Deficiency,
    Timer,
    TimerStatus,
    User,
    WorkflowEvent,
    WorkflowStage,
)
from app.services import workflow_jobs
from tests.support import (
    COMPLETE_APPLICATION_DATA,
    TestData,
    auth_headers,
    create_draft,
    pay_application_fee,
    upload_mandatory_documents,
)

EVENT_DATE = (date.today() + timedelta(days=7)).isoformat()

REPORT = {
    "infrastructure_ok": True,
    "faculty_verified": True,
    "lab_verified": True,
    "observations": "Illustrative inspection completed; all demo checks passed.",
    "recommendation": "APPROVE",
}


def _headers(client: TestClient, test_data: TestData, key: str) -> dict[str, str]:
    return auth_headers(client, test_data.users[key], test_data.password)


def _act(
    client: TestClient,
    application_id: str,
    action: str,
    headers: dict[str, str],
    **payload: Any,
) -> dict[str, Any]:
    """Perform one workflow action and return the decoded response."""
    response = client.post(
        f"/applications/{application_id}/actions/{action}",
        headers=headers,
        json=payload or None,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _status(client: TestClient, application_id: str, headers: dict[str, str]) -> str:
    timeline = client.get(f"/applications/{application_id}/timeline", headers=headers)
    assert timeline.status_code == 200, timeline.text
    return timeline.json()["status"]


def _create_and_submit(
    client: TestClient,
    test_data: TestData,
    tracked: list[uuid.UUID],
    *,
    application_type: str = "NEW_INSTITUTION",
    pay: bool = True,
    programs: list[dict[str, Any]] | None = None,
) -> tuple[str, dict[str, str]]:
    """Create a complete fictional draft and submit it through the workspace."""
    admin = _headers(client, test_data, "institution_admin_west")
    created = create_draft(client, admin, tracked, application_type=application_type)
    application_id = created["id"]

    update = client.patch(
        f"/applications/{application_id}",
        json={"data": COMPLETE_APPLICATION_DATA},
        headers=admin,
    )
    assert update.status_code == 200, update.text

    for program in programs or []:
        added = client.post(
            f"/applications/{application_id}/programs",
            json=program,
            headers=admin,
        )
        assert added.status_code == 201, added.text

    upload_mandatory_documents(client, admin, application_id)
    if pay:
        pay_application_fee(client, admin, application_id)

    submitted = client.post(f"/applications/{application_id}/submit", headers=admin)
    assert submitted.status_code == 200, submitted.text
    return application_id, admin


def _track_a_to_ec(
    client: TestClient,
    test_data: TestData,
    application_id: str,
) -> None:
    """Run Track A up to the EC decision: scrutiny, EVC and Bureau observations."""
    regulation = _headers(client, test_data, "regulation")
    scrutiny = _headers(client, test_data, "scrutiny")
    evc = _headers(client, test_data, "inspection")

    _act(client, application_id, "assign_scrutiny", regulation)
    _act(client, application_id, "scrutiny_recommend", scrutiny)
    _act(
        client,
        application_id,
        "submit_evc_video",
        evc,
        video_url="https://example.edu/fictional-evc.mp4",
        video_minutes=45,
    )
    _act(client, application_id, "evc_report", evc, report=REPORT)
    _act(
        client,
        application_id,
        "observations",
        regulation,
        observations="Illustrative Bureau observations on the fictional file.",
    )
    _act(client, application_id, "list_for_ec", regulation)
    assert _status(client, application_id, regulation) == "EC_DECISION"


def _seed_application(
    test_data: TestData,
    tracked: list[uuid.UUID],
    *,
    status: ApplicationStatus,
    stage: WorkflowStage = WorkflowStage.APPLICATION,
    data: dict[str, Any] | None = None,
    academic_year: str = "2026-27",
    security_deposit_due_on: date | None = None,
    loa_valid_until: date | None = None,
) -> uuid.UUID:
    """Insert one application at a chosen state for clock and role tests."""
    now = datetime.now(UTC)
    reference = f"TEST-WF-{uuid.uuid4().hex[:8]}"
    application = Application(
        institution_id=test_data.institutions["west"],
        track=ApplicationTrack.NEW_INSTITUTION,
        application_type="NEW_INSTITUTION",
        category=ApplicationCategory.CAT1_CUTOFF,
        academic_year=academic_year,
        portal_application_no=f"DEMO/{academic_year}/{uuid.uuid4().hex[:4].upper()}",
        status=status,
        current_stage=stage,
        assigned_officer_id=test_data.users["scrutiny"].id,
        submitted_at=now,
        locked_at=now,
        stage_entered_at=now,
        sla_due_at=now + timedelta(days=10),
        security_deposit_due_on=security_deposit_due_on,
        loa_valid_until=loa_valid_until,
        data={"reference": reference, "demo": True, **(data or {})},
    )
    with SessionLocal() as db:
        db.add(application)
        db.commit()
        db.refresh(application)
        application_id = application.id
    tracked.append(application_id)
    return application_id


@pytest.fixture
def future_calendar() -> Any:
    """Move the demo EoA cut-offs a year forward and restore them afterwards."""
    with SessionLocal() as db:
        rows = list(db.scalars(select(AcademicCalendarEvent)).all())
        originals = {row.event_key: row.date for row in rows}
        for row in rows:
            row.date = date.today() + timedelta(days=365)
        db.commit()
    try:
        yield
    finally:
        with SessionLocal() as db:
            for row in db.scalars(select(AcademicCalendarEvent)).all():
                if row.event_key in originals:
                    row.date = originals[row.event_key]
            db.commit()


@pytest.fixture
def past_eoa_cutoff() -> Any:
    """Set the EoA last date in the past to exercise APH 2.25j."""
    with SessionLocal() as db:
        rows = list(db.scalars(select(AcademicCalendarEvent)).all())
        originals = {row.event_key: row.date for row in rows}
        for row in rows:
            if row.event_key.value == "LAST_DATE_EOA":
                row.date = date.today() - timedelta(days=1)
        db.commit()
    try:
        yield
    finally:
        with SessionLocal() as db:
            for row in db.scalars(select(AcademicCalendarEvent)).all():
                if row.event_key in originals:
                    row.date = originals[row.event_key]
            db.commit()


@pytest.fixture
def past_deposit_cutoff() -> Any:
    """Place the final Security Deposit date in the past (APH 2.25f)."""
    with SessionLocal() as db:
        rows = list(db.scalars(select(AcademicCalendarEvent)).all())
        originals = {row.event_key: row.date for row in rows}
        for row in rows:
            if row.event_key.value == "SD_PENALTY20_31JUL":
                row.date = date.today() - timedelta(days=1)
        db.commit()
    try:
        yield
    finally:
        with SessionLocal() as db:
            for row in db.scalars(select(AcademicCalendarEvent)).all():
                if row.event_key in originals:
                    row.date = originals[row.event_key]
            db.commit()


@pytest.fixture
def demo_clock(api_client: TestClient) -> Any:
    """Expose the process clock and always reset it after the test."""
    clock: SimulatedClock = api_client.app.state.clock
    clock.reset()
    try:
        yield clock
    finally:
        clock.reset()


# ---------------------------------------------------------------------------
# Track A
# ---------------------------------------------------------------------------


def test_track_a_full_path_from_submission_to_active_loa(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    """Track A: submission, EVC, EC approval, LoA, Security Deposit, active LoA."""
    application_id, admin = _create_and_submit(
        api_client, test_data, workspace_applications
    )
    assert _status(api_client, application_id, admin) == "SUBMITTED"

    with SessionLocal() as db:
        application = db.get(Application, uuid.UUID(application_id))
        assert application is not None
        assert application.assigned_officer_id == test_data.users["scrutiny"].id
        assert application.portal_application_no.startswith("AICTE/2026-27/")
        assert application.submitted_at is not None
        assert application.locked_at is not None

    _track_a_to_ec(api_client, test_data, application_id)

    ec = _headers(api_client, test_data, "ec")
    decided = _act(
        api_client,
        application_id,
        "ec_decide",
        ec,
        decision="LOA",
        quorum_met=True,
        notes="Illustrative approval of the fictional institution.",
    )
    assert decided["application"]["status"] == "LOA_ISSUED"

    issued = _act(api_client, application_id, "issue_loa", ec)
    assert issued["application"]["status"] == "SECURITY_DEPOSIT_PENDING"
    assert issued["application"]["current_stage"] == "DECISION"

    paid = _act(
        api_client,
        application_id,
        "pay_security_deposit",
        admin,
        deposit_receipt_no="SD-DEMO-0001",
        affidavit3_filed=True,
    )
    assert paid["application"]["status"] == "ACTIVE_LOA"
    assert paid["application"]["sla_due_at"] is None

    with SessionLocal() as db:
        deposit_timer = db.scalar(
            select(Timer)
            .join(DeadlineRule, DeadlineRule.id == Timer.deadline_rule_id)
            .where(
                Timer.application_id == uuid.UUID(application_id),
                DeadlineRule.code == "SECURITY_DEPOSIT",
            )
        )
        assert deposit_timer is not None
        assert deposit_timer.status == TimerStatus.COMPLETED

    timeline = api_client.get(
        f"/applications/{application_id}/timeline", headers=admin
    )
    assert timeline.status_code == 200, timeline.text
    body = timeline.json()
    assert body["status"] == "ACTIVE_LOA"
    assert [event["action"] for event in body["events"]] == [
        "submit",
        "assign_scrutiny",
        "scrutiny_recommend",
        "submit_evc_video",
        "evc_report",
        "observations",
        "list_for_ec",
        "ec_decide",
        "issue_loa",
        "pay_security_deposit",
    ]
    assert all(event["actor_name"] for event in body["events"])
    assert all(event["apH_clause"] for event in body["events"])

    # Letters: metadata, PDF, acknowledgement and the audit trail.
    letters = api_client.get(
        f"/applications/{application_id}/letters", headers=admin
    )
    assert letters.status_code == 200, letters.text
    letter_items = letters.json()
    assert len(letter_items) == 1
    letter = letter_items[0]
    assert letter["letter_type"] == "LOA"
    assert letter["letter_number"].startswith("AICTE-DEMO/2026/")
    assert letter["appeal_deadline"] is None

    fetched = api_client.get(f"/letters/{letter['id']}", headers=admin)
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["download_url"] == f"/letters/{letter['id']}/download"

    denied = api_client.post(f"/letters/{letter['id']}/acknowledge", headers=ec)
    assert denied.status_code == 403, denied.text

    acknowledged = api_client.post(
        f"/letters/{letter['id']}/acknowledge", headers=admin
    )
    assert acknowledged.status_code == 200, acknowledged.text
    assert acknowledged.json()["acknowledged_at"] is not None
    again = api_client.post(
        f"/letters/{letter['id']}/acknowledge", headers=admin
    )
    assert again.status_code == 409, again.text

    download = api_client.get(f"/letters/{letter['id']}/download", headers=admin)
    assert download.status_code == 200, download.text
    assert download.content.startswith(b"%PDF")


def test_track_a_deficiency_loop_closes_only_listed_items(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    """Deficiencies: communicate, comply, then close each one during Re-Scrutiny."""
    application_id, admin = _create_and_submit(
        api_client, test_data, workspace_applications
    )
    regulation = _headers(api_client, test_data, "regulation")
    scrutiny = _headers(api_client, test_data, "scrutiny")

    _act(api_client, application_id, "assign_scrutiny", regulation)
    raised = _act(
        api_client,
        application_id,
        "communicate_deficiency",
        scrutiny,
        deficiencies=[
            {
                "category": "DOCUMENT",
                "description": "The affiliation certificate is not legible.",
                "due_date": EVENT_DATE,
            },
            {
                "category": "FACULTY",
                "description": "The faculty list does not match the profile.",
                "due_date": EVENT_DATE,
            },
        ],
    )
    assert raised["application"]["status"] == "DEFICIENCY_COMMUNICATED"

    deficiencies = api_client.get(
        f"/applications/{application_id}/deficiencies", headers=admin
    )
    assert deficiencies.status_code == 200, deficiencies.text
    items = deficiencies.json()
    assert len(items) == 2
    assert {item["status"] for item in items} == {"OPEN"}
    ids = [item["id"] for item in items]

    responses = [
        {
            "deficiency_id": deficiency_id,
            "response_text": "A corrected fictional document has been uploaded.",
        }
        for deficiency_id in ids
    ]
    responded = _act(
        api_client,
        application_id,
        "submit_compliance",
        admin,
        responses=responses,
    )
    assert responded["application"]["status"] == "INSTITUTION_COMPLIANCE"

    closed_first = _act(
        api_client,
        application_id,
        "re_scrutiny_verify",
        scrutiny,
        deficiency_id=ids[0],
    )
    assert closed_first["application"]["status"] == "RE_SCRUTINY"
    assert _status(api_client, application_id, scrutiny) == "RE_SCRUTINY"

    closed_second = _act(
        api_client,
        application_id,
        "re_scrutiny_verify",
        scrutiny,
        deficiency_id=ids[1],
    )
    assert closed_second["application"]["status"] == "RE_SCRUTINY"

    with SessionLocal() as db:
        rows = list(
            db.scalars(
                select(Deficiency).where(
                    Deficiency.application_id == uuid.UUID(application_id)
                )
            ).all()
        )
        assert {row.status.value for row in rows} == {"CLOSED"}

    # A closed deficiency cannot be verified a second time.
    repeated = api_client.post(
        f"/applications/{application_id}/actions/re_scrutiny_verify",
        headers=scrutiny,
        json={"deficiency_id": ids[0]},
    )
    assert repeated.status_code == 409, repeated.text

    recommended = _act(api_client, application_id, "scrutiny_recommend", scrutiny)
    assert recommended["application"]["status"] == "EVC_CONSTITUTED"


def test_track_a_rejection_appeal_send_back_once_and_council_final(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    """LoR > appeal > SAC > one send-back > second SAC > Council > endorsement."""
    application_id, admin = _create_and_submit(
        api_client, test_data, workspace_applications
    )
    _track_a_to_ec(api_client, test_data, application_id)
    ec = _headers(api_client, test_data, "ec")
    regulation = _headers(api_client, test_data, "regulation")
    evc = _headers(api_client, test_data, "inspection")
    sac = _headers(api_client, test_data, "sac")
    regional = _headers(api_client, test_data, "regional")

    _act(
        api_client,
        application_id,
        "ec_decide",
        ec,
        decision="LOR",
        quorum_met=True,
        speaking_order="The fictional institution did not meet the illustrative norms.",
        notes="Illustrative rejection.",
    )
    issued = _act(api_client, application_id, "issue_lor", ec)
    assert issued["application"]["status"] == "APPEAL_WINDOW"

    appeal = api_client.post(
        f"/applications/{application_id}/appeal",
        headers=admin,
        json={"appeal_text": "The fictional institution seeks a review of the findings."},
    )
    assert appeal.status_code == 200, appeal.text
    assert appeal.json()["application"]["status"] == "SAC_REVIEW"

    with SessionLocal() as db:
        application_uuid = uuid.UUID(application_id)
        appeal_timer = db.scalar(
            select(Timer)
            .join(DeadlineRule, DeadlineRule.id == Timer.deadline_rule_id)
            .where(
                Timer.application_id == application_uuid,
                DeadlineRule.code == "APPEAL_WINDOW",
            )
            .order_by(Timer.created_at.desc())
            .limit(1)
        )
        assert appeal_timer is not None
        assert appeal_timer.status == TimerStatus.COMPLETED

    duplicate = api_client.post(
        f"/applications/{application_id}/appeal",
        headers=admin,
        json={"appeal_text": "A second attempt that must be rejected."},
    )
    assert duplicate.status_code == 409, duplicate.text

    sent_back = _act(api_client, application_id, "send_back", sac)
    assert sent_back["application"]["status"] == "EVC_CONSTITUTED"

    _act(
        api_client,
        application_id,
        "submit_evc_video",
        evc,
        video_url="https://example.edu/fictional-evc-2.mp4",
        video_minutes=40,
    )
    _act(api_client, application_id, "evc_report", evc, report=REPORT)
    _act(
        api_client,
        application_id,
        "observations",
        regulation,
        observations="Re-examined after the SAC send-back.",
    )
    _act(api_client, application_id, "list_for_ec", regulation)
    _act(
        api_client,
        application_id,
        "ec_decide",
        ec,
        decision="LOR",
        quorum_met=True,
        notes="The re-examined file is still rejected.",
    )
    second_letter = _act(api_client, application_id, "issue_lor", ec)
    assert second_letter["application"]["status"] == "SAC_REVIEW"

    refused = api_client.post(
        f"/applications/{application_id}/actions/send_back",
        headers=sac,
        json={},
    )
    assert refused.status_code == 409, refused.text

    recommended = _act(
        api_client,
        application_id,
        "sac_recommend",
        sac,
        sac_recommendation="NOT_RECOMMEND",
        notes="The SAC upholds the rejection.",
    )
    assert recommended["application"]["status"] == "COUNCIL_FINAL"

    final = _act(
        api_client,
        application_id,
        "council_final",
        ec,
        decision="LOR",
        quorum_met=True,
        notes="The Council records the final rejection.",
    )
    assert final["application"]["status"] == "REGIONAL_ENDORSEMENT"

    endorsed = _act(api_client, application_id, "endorse_decision", regional)
    assert endorsed["application"]["status"] == "FINAL_LOR"

    with SessionLocal() as db:
        application = db.get(Application, uuid.UUID(application_id))
        assert application is not None
        assert application.appeal_loop_count == 1
        assert application.data["final_outcome"] == "LOR"

    final_attempt = api_client.post(
        f"/applications/{application_id}/actions/sac_recommend",
        headers=sac,
        json={"sac_recommendation": "RECOMMEND"},
    )
    assert final_attempt.status_code == 409, final_attempt.text


def test_missed_appeal_window_makes_the_decision_final(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
    demo_clock: SimulatedClock,
) -> None:
    """A late appeal is refused and the clock closes the decision (APH 1.11a)."""
    application_id, admin = _create_and_submit(
        api_client, test_data, workspace_applications
    )
    _track_a_to_ec(api_client, test_data, application_id)
    ec = _headers(api_client, test_data, "ec")
    regulation = _headers(api_client, test_data, "regulation")

    _act(
        api_client,
        application_id,
        "ec_decide",
        ec,
        decision="LOR",
        quorum_met=True,
        speaking_order="Illustrative reasons for the fictional rejection.",
    )
    _act(api_client, application_id, "issue_lor", ec)

    demo_clock.advance(8)

    late = api_client.post(
        f"/applications/{application_id}/appeal",
        headers=admin,
        json={"appeal_text": "This appeal is deliberately late."},
    )
    assert late.status_code == 409, late.text
    assert "appeal window closed" in late.text.lower()

    finalised = _act(api_client, application_id, "finalize_no_appeal", regulation)
    assert finalised["application"]["status"] == "FINAL_LOR"

    with SessionLocal() as db:
        application = db.get(Application, uuid.UUID(application_id))
        assert application is not None
        assert application.data["final_outcome"] == "LOR"
        assert application.data["appeal_window_closed"]


def test_security_deposit_penalty_then_withdrawal(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
    past_deposit_cutoff: None,
) -> None:
    """The deposit ladder applies 20% and then withdraws after 31 July (2.25f)."""
    application_id = _seed_application(
        test_data,
        workspace_applications,
        status=ApplicationStatus.SECURITY_DEPOSIT_PENDING,
        stage=WorkflowStage.DECISION,
        security_deposit_due_on=date.today() - timedelta(days=40),
        data={"pending_outcome": "LOA"},
    )
    regulation = _headers(api_client, test_data, "regulation")
    admin = _headers(api_client, test_data, "institution_admin_west")

    penalised = _act(
        api_client, str(application_id), "apply_deposit_penalty", regulation
    )
    assert penalised["application"]["status"] == "SECURITY_DEPOSIT_PENDING"

    with SessionLocal() as db:
        application = db.get(Application, application_id)
        assert application is not None
        assert application.data["deposit_penalty_percent"] == 20

    withdrawn = _act(
        api_client, str(application_id), "apply_deposit_penalty", regulation
    )
    assert withdrawn["application"]["status"] == "WITHDRAWN"

    with SessionLocal() as db:
        application = db.get(Application, application_id)
        assert application is not None
        assert application.data["security_deposit_forfeited"]

    blocked = api_client.post(
        f"/applications/{application_id}/actions/pay_security_deposit",
        headers=admin,
        json={"deposit_receipt_no": "SD-DEMO-2", "affidavit3_filed": True},
    )
    assert blocked.status_code == 409, blocked.text


def test_loa_expiry_cancels_the_approval_and_sweep_applies_it(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An LoA lapses after two academic years; the scheduler sweep applies it."""
    application_id = _seed_application(
        test_data,
        workspace_applications,
        status=ApplicationStatus.ACTIVE_LOA,
        stage=WorkflowStage.DECISION,
        loa_valid_until=date.today() - timedelta(days=1),
        data={"pending_outcome": "LOA"},
    )

    regulation = test_data.users["regulation"]

    def _actor(db):
        return db.get(User, regulation.id)

    monkeypatch.setattr(workflow_jobs, "_system_actor", _actor)

    with SessionLocal() as db:
        advanced = workflow_jobs.sweep(db, api_client.app.state.clock)

    assert advanced >= 1
    with SessionLocal() as db:
        application = db.get(Application, application_id)
        assert application is not None
        assert application.status == ApplicationStatus.CANCELLED
        assert application.data["loa_expired_on"]


# ---------------------------------------------------------------------------
# Track B, C and D
# ---------------------------------------------------------------------------


def test_track_b_self_disclosure_issues_an_eoa(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
    future_calendar: None,
) -> None:
    """Track B: automatic self-disclosure, optional EVC and the EoA."""
    application_id, admin = _create_and_submit(
        api_client,
        test_data,
        workspace_applications,
        application_type="EOA_SELF_DISCLOSURE",
    )
    regulation = _headers(api_client, test_data, "regulation")
    ec = _headers(api_client, test_data, "ec")

    checked = _act(
        api_client, application_id, "run_self_disclosure_check", regulation
    )
    assert checked["application"]["status"] == "SELF_DISCLOSURE_CHECK"

    deficiencies = api_client.get(
        f"/applications/{application_id}/deficiencies", headers=admin
    ).json()
    if deficiencies:
        _act(api_client, application_id, "communicate_deficiency", regulation)
        responses = [
            {
                "deficiency_id": item["id"],
                "response_text": "The fictional self-disclosure has been corrected.",
            }
            for item in deficiencies
        ]
        _act(api_client, application_id, "submit_compliance", admin, responses=responses)
        for item in deficiencies:
            _act(
                api_client,
                application_id,
                "re_scrutiny_verify",
                regulation,
                deficiency_id=item["id"],
            )

    cleared = _act(
        api_client,
        application_id,
        "scrutiny_recommend",
        regulation,
        random_evc=False,
    )
    assert cleared["application"]["status"] == "EC_LISTING"

    _act(api_client, application_id, "list_for_ec", regulation)
    assert _status(api_client, application_id, regulation) == "EC_DECISION"

    decided = _act(
        api_client,
        application_id,
        "ec_decide",
        ec,
        decision="EOA",
        quorum_met=True,
        notes="Illustrative extension of approval.",
    )
    assert decided["application"]["status"] == "EOA_ISSUED"

    issued = _act(api_client, application_id, "issue_eoa", ec)
    assert issued["application"]["status"] == "ACTIVE_EOA"

    letters = api_client.get(
        f"/applications/{application_id}/letters", headers=admin
    ).json()
    assert [item["letter_type"] for item in letters] == ["EOA"]


def test_track_c_hearing_then_eoa(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
    future_calendar: None,
) -> None:
    """Track C: scrutiny, EVC, SHC hearing and the EoA."""
    application_id, admin = _create_and_submit(
        api_client,
        test_data,
        workspace_applications,
        application_type="NEW_PROGRAMME",
    )
    regulation = _headers(api_client, test_data, "regulation")
    scrutiny = _headers(api_client, test_data, "scrutiny")
    evc = _headers(api_client, test_data, "inspection")
    shc = _headers(api_client, test_data, "shc")
    ec = _headers(api_client, test_data, "ec")

    _act(api_client, application_id, "assign_scrutiny", regulation)
    _act(api_client, application_id, "scrutiny_recommend", scrutiny)
    _act(
        api_client,
        application_id,
        "submit_evc_video",
        evc,
        video_url="https://example.edu/fictional-evc-3.mp4",
        video_minutes=35,
    )
    _act(api_client, application_id, "evc_report", evc, report=REPORT)
    _act(
        api_client,
        application_id,
        "observations",
        regulation,
        observations="Illustrative observations for the new programme.",
    )

    hearing = _act(
        api_client,
        application_id,
        "shc_hearing",
        shc,
        shc_outcome="RECOMMEND",
        notes="The SHC heard the fictional institution.",
    )
    assert hearing["application"]["status"] == "SHC_HEARING"

    _act(api_client, application_id, "list_for_ec", shc)
    assert _status(api_client, application_id, shc) == "EC_LISTING"
    _act(api_client, application_id, "list_for_ec", regulation)
    assert _status(api_client, application_id, regulation) == "EC_DECISION"

    decided = _act(
        api_client,
        application_id,
        "ec_decide",
        ec,
        decision="EOA",
        quorum_met=True,
        notes="Illustrative extension for the new programme.",
    )
    assert decided["application"]["status"] == "EOA_ISSUED"
    _act(api_client, application_id, "issue_eoa", ec)
    assert _status(api_client, application_id, admin) == "ACTIVE_EOA"

    with SessionLocal() as db:
        shc_decision = db.scalar(
            select(Decision).where(
                Decision.application_id == uuid.UUID(application_id),
                Decision.body == DecisionBody.SHC,
            )
        )
        assert shc_decision is not None
        assert shc_decision.outcome == DecisionOutcome.RECOMMEND


def test_track_d_failed_closure_gets_zero_intake(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
    future_calendar: None,
) -> None:
    """Track D: year-round closure decision, guards and zero intake (2.3.3h)."""
    application_id, admin = _create_and_submit(
        api_client,
        test_data,
        workspace_applications,
        application_type="CLOSURE_OF_INSTITUTION",
        pay=False,
        programs=[
            {
                "program_name": "Civil Engineering",
                "level": "UG",
                "intake": 60,
                "faculty_count": 12,
                "lab_count": 6,
            }
        ],
    )
    regulation = _headers(api_client, test_data, "regulation")
    scrutiny = _headers(api_client, test_data, "scrutiny")
    ec = _headers(api_client, test_data, "ec")

    _act(api_client, application_id, "assign_scrutiny", regulation)
    _act(api_client, application_id, "scrutiny_recommend", scrutiny)
    _act(api_client, application_id, "list_for_ec", regulation)
    assert _status(api_client, application_id, regulation) == "EC_DECISION"

    missing_outcome = api_client.post(
        f"/applications/{application_id}/actions/ec_decide",
        headers=ec,
        json={"decision": "EOA", "quorum_met": True},
    )
    assert missing_outcome.status_code == 409, missing_outcome.text

    investigation = api_client.post(
        f"/applications/{application_id}/actions/ec_decide",
        headers=ec,
        json={
            "decision": "EOA",
            "quorum_met": True,
            "closure_failed": True,
            "pending_court_case": True,
        },
    )
    assert investigation.status_code == 409, investigation.text
    assert "investigation" in investigation.text.lower()

    decided = _act(
        api_client,
        application_id,
        "ec_decide",
        ec,
        decision="EOA",
        quorum_met=True,
        closure_failed=True,
        notes="The closure did not succeed.",
    )
    assert decided["application"]["status"] == "EOA_ISSUED"

    with SessionLocal() as db:
        application = db.get(Application, uuid.UUID(application_id))
        assert application is not None
        assert application.data["approved_intake"] == 0
        programmes = list(
            db.scalars(
                select(ApplicationProgram).where(
                    ApplicationProgram.application_id == application.id
                )
            ).all()
        )
        assert programmes
        assert all(programme.intake == 0 for programme in programmes)

    _act(api_client, application_id, "issue_eoa", ec)
    assert _status(api_client, application_id, admin) == "ACTIVE_EOA"


def test_eoa_is_rejected_after_the_academic_calendar_last_date(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
    past_eoa_cutoff: None,
) -> None:
    """No Extension of Approval may be processed after the last date (2.25j)."""
    application_id, _ = _create_and_submit(
        api_client,
        test_data,
        workspace_applications,
        application_type="CLOSURE_OF_INSTITUTION",
        pay=False,
    )
    regulation = _headers(api_client, test_data, "regulation")
    scrutiny = _headers(api_client, test_data, "scrutiny")
    ec = _headers(api_client, test_data, "ec")

    _act(api_client, application_id, "assign_scrutiny", regulation)
    _act(api_client, application_id, "scrutiny_recommend", scrutiny)
    _act(api_client, application_id, "list_for_ec", regulation)

    rejected = api_client.post(
        f"/applications/{application_id}/actions/ec_decide",
        headers=ec,
        json={"decision": "EOA", "quorum_met": True, "closure_failed": False},
    )
    assert rejected.status_code == 409, rejected.text
    assert "no extension of approval" in rejected.text.lower()


# ---------------------------------------------------------------------------
# Role separation and lifecycle rules
# ---------------------------------------------------------------------------


def test_super_admin_can_only_ratify_an_ec_decision(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    """SUPER_ADMIN never decides; it may only ratify a quorate EC decision."""
    application_id = _seed_application(
        test_data,
        workspace_applications,
        status=ApplicationStatus.EC_DECISION,
        stage=WorkflowStage.DECISION,
        data={"pending_outcome": "LOA"},
    )
    super_admin = _headers(api_client, test_data, "super")
    ec = _headers(api_client, test_data, "ec")

    with SessionLocal() as db:
        db.add(
            Decision(
                application_id=application_id,
                body=DecisionBody.EC,
                outcome=DecisionOutcome.LOA,
                decided_on=date.today(),
                quorum_met=True,
                notes="Illustrative quorate EC decision.",
                apH_clause="APH 1.10a",
            )
        )
        db.commit()

    allowed = api_client.get(
        f"/applications/{application_id}/allowed-actions", headers=super_admin
    )
    assert allowed.status_code == 200, allowed.text
    assert [item["action"] for item in allowed.json()["actions"]] == [
        "council_ratification"
    ]

    forbidden = (
        (
            ApplicationStatus.EC_DECISION,
            WorkflowStage.DECISION,
            "ec_decide",
            {"decision": "LOA", "quorum_met": True},
        ),
        (ApplicationStatus.LOA_ISSUED, WorkflowStage.DECISION, "issue_loa", {}),
        (ApplicationStatus.LOR_ISSUED, WorkflowStage.DECISION, "issue_lor", {}),
        (
            ApplicationStatus.SCRUTINY,
            WorkflowStage.SCRUTINY,
            "scrutiny_recommend",
            {},
        ),
        (
            ApplicationStatus.SECURITY_DEPOSIT_PENDING,
            WorkflowStage.DECISION,
            "apply_deposit_penalty",
            {},
        ),
    )
    for status, stage, action, payload in forbidden:
        seeded = _seed_application(
            test_data,
            workspace_applications,
            status=status,
            stage=stage,
            data={"pending_outcome": "LOA"},
        )
        denied = api_client.post(
            f"/applications/{seeded}/actions/{action}",
            headers=super_admin,
            json=payload or None,
        )
        assert denied.status_code == 403, (action, denied.text)

    ratified = _act(
        api_client,
        application_id,
        "council_ratification",
        super_admin,
        notes="EC/2026/DEMO-1",
    )
    assert ratified["application"]["status"] == "COUNCIL_RATIFICATION"

    with SessionLocal() as db:
        ratification = db.scalar(
            select(CouncilRatification).where(
                CouncilRatification.decision_id.in_(
                    select(Decision.id).where(
                        Decision.application_id == uuid.UUID(application_id)
                    )
                )
            )
        )
        assert ratification is not None

    confirmed = _act(api_client, application_id, "ec_decide", ec)
    assert confirmed["application"]["status"] == "LOA_ISSUED"


def test_regional_officer_cannot_approve_reject_or_decide(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    """The Regional Officer constitutes the EVC and endorses; it never decides."""
    application_id = _seed_application(
        test_data,
        workspace_applications,
        status=ApplicationStatus.EC_DECISION,
        stage=WorkflowStage.DECISION,
        data={"pending_outcome": "LOA"},
    )
    regional = _headers(api_client, test_data, "regional")

    allowed = api_client.get(
        f"/applications/{application_id}/allowed-actions", headers=regional
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["actions"] == []

    forbidden = (
        (
            ApplicationStatus.EC_DECISION,
            WorkflowStage.DECISION,
            "ec_decide",
            {"decision": "LOA", "quorum_met": True},
        ),
        (ApplicationStatus.LOA_ISSUED, WorkflowStage.DECISION, "issue_loa", {}),
        (ApplicationStatus.LOR_ISSUED, WorkflowStage.DECISION, "issue_lor", {}),
        (
            ApplicationStatus.COUNCIL_FINAL,
            WorkflowStage.DECISION,
            "council_final",
            {"decision": "LOA", "quorum_met": True},
        ),
    )
    for status, stage, action, payload in forbidden:
        seeded = _seed_application(
            test_data,
            workspace_applications,
            status=status,
            stage=stage,
            data={"pending_outcome": "LOA"},
        )
        denied = api_client.post(
            f"/applications/{seeded}/actions/{action}",
            headers=regional,
            json=payload or None,
        )
        assert denied.status_code == 403, (action, denied.text)

    endorsement = _seed_application(
        test_data,
        workspace_applications,
        status=ApplicationStatus.REGIONAL_ENDORSEMENT,
        stage=WorkflowStage.COMMITTEE_REVIEW,
        data={"pending_outcome": "LOA"},
    )
    endorsed = _act(api_client, str(endorsement), "endorse_decision", regional)
    assert endorsed["application"]["status"] == "FINAL_LOA"


def test_reopen_is_allowed_once_with_a_fresh_ter(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    """A wrongly submitted file can be reopened once (APH 2.3.3d-e)."""
    application_id, admin = _create_and_submit(
        api_client, test_data, workspace_applications
    )
    regulation = _headers(api_client, test_data, "regulation")

    reopened = api_client.post(
        f"/applications/{application_id}/reopen",
        headers=regulation,
        json={
            "reason": "The submitted data contained a fictional typo.",
            "late_penalty_acknowledged": True,
            "trust_resolution_reference": "FORMAT-3-DEMO",
        },
    )
    assert reopened.status_code == 200, reopened.text
    body = reopened.json()
    assert body["status"] == "DRAFT"
    assert body["reopen_count"] == 1
    assert body["quote"]["total_paise"] > 0

    with SessionLocal() as db:
        application = db.get(Application, uuid.UUID(application_id))
        assert application is not None
        assert application.locked_at is None

    second = api_client.post(
        f"/applications/{application_id}/reopen",
        headers=regulation,
        json={
            "reason": "A second reopen must be refused.",
            "late_penalty_acknowledged": True,
        },
    )
    assert second.status_code == 409, second.text


def test_submitted_application_data_is_locked(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    """A submitted file is locked against edits (APH 1.4.3)."""
    application_id, admin = _create_and_submit(
        api_client, test_data, workspace_applications
    )
    edit = api_client.patch(
        f"/applications/{application_id}",
        headers=admin,
        json={"data": {"infrastructure": {"land_area": 99999}}},
    )
    assert edit.status_code == 409, edit.text


def test_withdrawal_is_terminal_for_further_actions(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    """Withdrawal preserves history and blocks every later transition."""
    application_id, admin = _create_and_submit(
        api_client, test_data, workspace_applications
    )
    regulation = _headers(api_client, test_data, "regulation")

    withdrawn = _act(
        api_client,
        application_id,
        "withdraw_application",
        admin,
        comment="The fictional institution withdrew its application.",
    )
    assert withdrawn["application"]["status"] == "WITHDRAWN"
    assert withdrawn["application"]["is_withdrawn"] is True

    blocked = api_client.post(
        f"/applications/{application_id}/actions/assign_scrutiny",
        headers=regulation,
    )
    assert blocked.status_code == 409, blocked.text

    allowed = api_client.get(
        f"/applications/{application_id}/allowed-actions", headers=admin
    )
    assert allowed.status_code == 200
    assert allowed.json()["actions"] == []


def test_workflow_definition_and_diagram_come_from_the_database(
    api_client: TestClient,
    test_data: TestData,
) -> None:
    """The case file and docs read states and edges from the API, not code."""
    admin = _headers(api_client, test_data, "institution_admin_west")

    definition = api_client.get(
        "/workflow/definition", params={"type": "NEW_INSTITUTION"}, headers=admin
    )
    assert definition.status_code == 200, definition.text
    body = definition.json()
    assert body["key"] == "TRACK_A"
    assert body["config"]["security_deposit"] is True
    states = {state["code"] for state in body["states"]}
    assert {"DRAFT", "EVC_CONSTITUTED", "EC_DECISION", "ACTIVE_LOA"} <= states
    actions = {(edge["action"], edge["to_state"]) for edge in body["transitions"]}
    assert ("ec_decide", "LOA_ISSUED") in actions
    assert all(edge["apH_clause"] for edge in body["transitions"])

    diagram = api_client.get("/workflow/diagram", headers=admin)
    assert diagram.status_code == 200, diagram.text
    mermaid = diagram.json()["mermaid"]
    assert mermaid.startswith("flowchart TD")
    assert "EC_DECISION" in mermaid
    assert "TRACK_A" in mermaid

    missing = api_client.get(
        "/workflow/definition", params={"type": "NOT_A_TYPE"}, headers=admin
    )
    assert missing.status_code == 404, missing.text

    anonymous = api_client.get("/workflow/definition", params={"type": "TRACK_A"})
    assert anonymous.status_code == 401, anonymous.text


def test_workflow_events_and_audit_rows_are_written_for_every_action(
    api_client: TestClient,
    test_data: TestData,
    workspace_applications: list[uuid.UUID],
) -> None:
    """Every transition writes one WorkflowEvent carrying its APH clause."""
    application_id, admin = _create_and_submit(
        api_client, test_data, workspace_applications
    )
    regulation = _headers(api_client, test_data, "regulation")
    _act(api_client, application_id, "assign_scrutiny", regulation)

    with SessionLocal() as db:
        events = list(
            db.scalars(
                select(WorkflowEvent)
                .where(WorkflowEvent.application_id == uuid.UUID(application_id))
                .order_by(WorkflowEvent.created_at.asc())
            ).all()
        )
        assert [event.action for event in events] == ["submit", "assign_scrutiny"]
        assert all(event.apH_clause for event in events)
        assert events[-1].from_status == ApplicationStatus.SUBMITTED
        assert events[-1].to_status == ApplicationStatus.SCRUTINY
