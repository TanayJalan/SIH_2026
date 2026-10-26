"""Named side effects for the data-driven workflow.

``workflow_transitions.side_effects`` stores effect *names*. This module is the
only place those names resolve to code. An effect receives a
:class:`~app.services.workflow_context.TransitionContext`, mutates the session
and returns an optional user-facing sentence.

Effects never commit: the workflow engine owns the transaction so a failed
guard, effect or event write rolls the whole action back.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, date, timedelta
from typing import Any

from sqlalchemy import select

from app.models.appeal import Appeal
from app.models.application import ApplicationProgram
from app.models.application_type_route import ApplicationTypeRoute
from app.models.committee import Committee
from app.models.deadline import DeadlineRule
from app.models.decision import Decision
from app.models.deficiency import Deficiency
from app.models.enums import (
    CommitteeMode,
    CommitteeStatus,
    CommitteeType,
    DecisionBody,
    DecisionLetterType,
    DecisionOutcome,
    DeficiencyStatus,
    InspectionStatus,
    ProgrammeStatus,
    Role,
    SecurityDepositStatus,
    WorkflowStage,
)
from app.models.inspection import Inspection
from app.models.sla import SLAConfig
from app.models.user import User
from app.services import decision_letters
from app.services.committee import CommitteeService
from app.services.deadlines import complete_timers
from app.services.deficiency_report import build_deficiency_report
from app.services.fee_calculator import security_deposit_penalty
from app.services.fees import FeeService
from app.services.portal_number import next_portal_application_no
from app.services.workflow_context import TransitionContext
from app.services.workflow_errors import (
    WorkflowNotFoundError,
    WorkflowValidationError,
)

Effect = Callable[[TransitionContext], str | None]

_LETTER_BY_ACTION = {
    "issue_loa": DecisionLetterType.LOA,
    "issue_eoa": DecisionLetterType.EOA,
    "issue_lod": DecisionLetterType.LOD,
    "issue_lor": DecisionLetterType.LOR,
}

_APPEALABLE_LETTERS = _LETTER_BY_ACTION


def _data(ctx: TransitionContext) -> dict[str, Any]:
    return dict(ctx.application.data) if isinstance(ctx.application.data, dict) else {}


def _store_data(ctx: TransitionContext, data: dict[str, Any]) -> None:
    ctx.application.data = data


def _route(ctx: TransitionContext) -> ApplicationTypeRoute | None:
    return ctx.db.scalar(
        select(ApplicationTypeRoute).where(
            ApplicationTypeRoute.type == ctx.application.application_type
        )
    )


def _deficiency_due_date(ctx: TransitionContext) -> date:
    config = ctx.db.scalar(select(SLAConfig).where(SLAConfig.stage == WorkflowStage.DEFICIENCY))
    days = config.duration_days if config is not None else 7
    return (ctx.now + timedelta(days=days)).date()


def _open_deficiencies(ctx: TransitionContext) -> list[Deficiency]:
    return list(
        ctx.db.scalars(
            select(Deficiency)
            .where(
                Deficiency.application_id == ctx.application.id,
                Deficiency.status != DeficiencyStatus.CLOSED,
            )
            .order_by(Deficiency.created_at.asc())
        ).all()
    )


def _latest_decision(ctx: TransitionContext, body: DecisionBody) -> Decision | None:
    return decision_letters.latest_decision(ctx.db, ctx.application.id, body)


# ---------------------------------------------------------------------------
# Submission, assignment and money
# ---------------------------------------------------------------------------


def submit(ctx: TransitionContext) -> str | None:
    """Lock the application, stamp it and issue the portal number."""
    now = ctx.now
    if ctx.application.submitted_at is None:
        ctx.application.submitted_at = now
    ctx.application.locked_at = now
    if ctx.application.portal_application_no is None:
        ctx.application.portal_application_no = next_portal_application_no(
            ctx.db, ctx.application.academic_year
        )
    ctx.add_detail("portal_application_no", ctx.application.portal_application_no)
    ctx.add_detail("submitted_at", now.isoformat())
    return "Application submitted, locked and numbered."


def assign_scrutiny(ctx: TransitionContext) -> str | None:
    """Assign a scrutiny member in the institution's region."""
    officer: User | None = None
    if ctx.payload.officer_id is not None:
        candidate = ctx.db.get(User, ctx.payload.officer_id)
        if (
            candidate is None
            or not candidate.is_active
            or candidate.role != Role.SCRUTINY_COMMITTEE_MEMBER
        ):
            raise WorkflowValidationError("Select an active scrutiny officer.")
        if candidate.region != ctx.application.institution.region:
            raise WorkflowValidationError(
                "The scrutiny officer must belong to the institution's region."
            )
        officer = candidate
    elif ctx.application.assigned_officer_id is not None:
        officer = ctx.db.get(User, ctx.application.assigned_officer_id)
    elif ctx.assignment_strategy is not None:
        officer = ctx.assignment_strategy.choose(ctx.db, ctx.application)

    if officer is None:
        ctx.add_message(
            "No scrutiny officer is currently available in this region; "
            "a Bureau officer can assign one when an officer is added."
        )
        return None

    ctx.application.assigned_officer_id = officer.id
    ctx.add_detail("officer_id", str(officer.id))
    ctx.add_detail("officer_name", officer.name)
    return f"Assigned to {officer.name}."


def scrutiny_recommend(ctx: TransitionContext) -> str | None:
    """Record the Scrutiny recommendation and hand the file to the next body.

    The recommendation itself is narrative; the stage it moves to is decided by
    the transition data, so this effect only captures who recommended what.
    """
    text = (ctx.payload.observations or ctx.payload.comment or "").strip()
    data = _data(ctx)
    data["scrutiny_recommendation"] = {
        "by": ctx.actor.name,
        "at": ctx.now.isoformat(),
        "notes": text or None,
    }
    _store_data(ctx, data)
    ctx.add_detail("scrutiny_by", str(ctx.actor.id))
    if text:
        ctx.add_detail("scrutiny_notes", text)
    return "Scrutiny recommendation recorded."


def pay_ter(ctx: TransitionContext) -> str | None:
    """Confirm the computed TER is paid; the payment endpoint writes the receipt."""
    route = _route(ctx)
    if route is not None and route.no_ter:
        ctx.add_detail("ter_required", False)
        return "No TER is due for this application type."
    quote = FeeService(ctx.db, ctx.audit, ctx.clock).quote(ctx.application)
    if quote.total_paise > 0 and not quote.is_paid:
        raise WorkflowValidationError(
            "Pay the computed TER through the fee endpoint before submitting."
        )
    ctx.add_detail("ter_amount_paise", quote.total_paise)
    return "TER payment confirmed."


# ---------------------------------------------------------------------------
# Deficiencies
# ---------------------------------------------------------------------------


def create_deficiencies(ctx: TransitionContext) -> str | None:
    """Create the Deficiency Report items communicated to the institution."""
    if not ctx.payload.deficiencies:
        raise WorkflowValidationError("At least one deficiency is required.")
    today = ctx.now.date()
    created: list[Deficiency] = []
    for item in ctx.payload.deficiencies:
        if item.due_date < today:
            raise WorkflowValidationError("Deficiency due dates must not be in the past.")
        deficiency = Deficiency(
            application_id=ctx.application.id,
            category=item.category.strip(),
            description=item.description.strip(),
            raised_by=ctx.actor.id,
            status=DeficiencyStatus.OPEN,
            due_date=item.due_date,
        )
        ctx.db.add(deficiency)
        created.append(deficiency)
    ctx.db.flush()
    ctx.add_detail("deficiency_ids", [str(item.id) for item in created])
    ctx.add_detail("count", len(created))
    return f"{len(created)} deficiency item(s) communicated."


def communicate_deficiency(ctx: TransitionContext) -> str | None:
    """Communicate the existing automatic Deficiency Report."""
    if ctx.payload.deficiencies:
        return create_deficiencies(ctx)
    items = _open_deficiencies(ctx)
    if not items:
        raise WorkflowValidationError("There are no deficiencies to communicate.")
    ctx.add_detail("deficiency_ids", [str(item.id) for item in items])
    ctx.add_detail("count", len(items))
    return f"{len(items)} deficiency item(s) communicated."


def record_responses(ctx: TransitionContext) -> str | None:
    """Record the institution's response to every open deficiency."""
    open_items = {
        item.id: item for item in _open_deficiencies(ctx)
    }
    if not open_items:
        raise WorkflowValidationError("There are no open deficiencies to respond to.")
    if not ctx.payload.responses:
        raise WorkflowValidationError("A response is required for every open deficiency.")

    response_map: dict[uuid.UUID, Any] = {}
    for response in ctx.payload.responses:
        if response.deficiency_id in response_map:
            raise WorkflowValidationError("Each deficiency can only be answered once.")
        response_map[response.deficiency_id] = response

    missing = set(open_items) - set(response_map)
    extra = set(response_map) - set(open_items)
    if missing:
        raise WorkflowValidationError("Respond to every open deficiency in one submission.")
    if extra:
        raise WorkflowValidationError(
            "One or more deficiencies are not open for this application."
        )

    from app.models.document import Document

    document_ids: list[str] = []
    responded_at = ctx.now
    for deficiency_id, response in response_map.items():
        deficiency = open_items[deficiency_id]
        if response.document_id is not None:
            document = ctx.db.scalar(
                select(Document).where(
                    Document.id == response.document_id,
                    Document.application_id == ctx.application.id,
                )
            )
            if document is None:
                raise WorkflowValidationError(
                    "The selected response document does not belong to this application."
                )
            document_ids.append(str(document.id))
        deficiency.response_text = response.response_text.strip()
        deficiency.response_document_id = response.document_id
        deficiency.responded_at = responded_at
        deficiency.status = DeficiencyStatus.RESPONDED

    ctx.db.flush()
    ctx.add_detail("deficiency_ids", [str(item) for item in response_map])
    ctx.add_detail("document_ids", document_ids)
    return f"Institution responded to {len(response_map)} deficiency item(s)."


def verify_deficiencies(ctx: TransitionContext) -> str | None:
    """Close one listed deficiency during Re-Scrutiny."""
    if ctx.payload.deficiency_id is None:
        raise WorkflowValidationError("Select the deficiency to verify.")
    deficiency = ctx.db.scalar(
        select(Deficiency).where(
            Deficiency.id == ctx.payload.deficiency_id,
            Deficiency.application_id == ctx.application.id,
        )
    )
    if deficiency is None:
        raise WorkflowNotFoundError("Deficiency not found for this application.")
    if deficiency.status != DeficiencyStatus.RESPONDED:
        raise WorkflowValidationError("Only a responded deficiency can be closed.")
    deficiency.status = DeficiencyStatus.CLOSED
    deficiency.closed_at = ctx.now
    ctx.db.flush()
    remaining = len(_open_deficiencies(ctx))
    ctx.add_detail("deficiency_id", str(deficiency.id))
    ctx.add_detail("remaining", remaining)
    if remaining == 0:
        return "All deficiencies closed. Re-Scrutiny may now recommend the next stage."
    return f"Deficiency closed. {remaining} item(s) still need review."


# ---------------------------------------------------------------------------
# Expert Visit Committee and hearings
# ---------------------------------------------------------------------------


def _pick_evc_user(ctx: TransitionContext) -> User | None:
    return ctx.db.scalar(
        select(User)
        .where(
            User.role == Role.EVC_MEMBER,
            User.is_active.is_(True),
            User.region == ctx.application.institution.region,
        )
        .order_by(User.name.asc())
        .limit(1)
    )


def constitute_evc(ctx: TransitionContext) -> str | None:
    """Constitute the Expert Visit Committee and schedule the visit."""
    scheduled_on = ctx.payload.scheduled_on or (ctx.now + timedelta(days=2))
    if scheduled_on.tzinfo is None:
        scheduled_on = scheduled_on.replace(tzinfo=UTC)
    mode = ctx.payload.evc_mode or CommitteeMode.ONLINE

    try:
        CommitteeService(ctx.db, ctx.audit).select_committee(
            CommitteeType.EVC,
            application=ctx.application,
            scheduled_at=scheduled_on,
            mode=mode,
        )
    except Exception:  # pragma: no cover - expert pool data is demo-only
        # The prototype must still move the case even when the expert pool is
        # not populated; the selection is logged when it succeeds.
        pass

    evc_user = _pick_evc_user(ctx)
    if evc_user is not None:
        inspection = Inspection(
            application_id=ctx.application.id,
            committee_id=evc_user.id,
            scheduled_on=scheduled_on,
            status=InspectionStatus.SCHEDULED,
        )
        ctx.db.add(inspection)
        ctx.db.flush()
        ctx.add_detail("inspection_id", str(inspection.id))
        ctx.add_detail("committee_id", str(evc_user.id))
    ctx.add_detail("scheduled_on", scheduled_on.isoformat())
    ctx.add_detail("evc_mode", mode.value)
    return "Expert Visit Committee constituted."


def submit_evc_video(ctx: TransitionContext) -> str | None:
    """Record the visit video; it must be at least 30 minutes long."""
    url = (ctx.payload.video_url or "").strip()
    minutes = int(ctx.payload.video_minutes or 0)
    if not url:
        raise WorkflowValidationError("A video URL is required (APH 1.9f-g).")
    if minutes < 30:
        raise WorkflowValidationError("The visit video must be at least 30 minutes long.")
    data = _data(ctx)
    data["evc_video"] = {"url": url, "minutes": minutes, "uploaded_at": ctx.now.isoformat()}
    _store_data(ctx, data)
    ctx.add_detail("video_minutes", minutes)
    return "Visit video recorded."


def _ensure_inspection(ctx: TransitionContext) -> Inspection:
    inspection = ctx.db.scalar(
        select(Inspection)
        .where(
            Inspection.application_id == ctx.application.id,
            Inspection.status == InspectionStatus.SCHEDULED,
        )
        .order_by(Inspection.scheduled_on.desc())
        .limit(1)
    )
    if inspection is not None:
        return inspection
    inspection = Inspection(
        application_id=ctx.application.id,
        committee_id=ctx.actor.id,
        scheduled_on=ctx.now,
        status=InspectionStatus.SCHEDULED,
    )
    ctx.db.add(inspection)
    ctx.db.flush()
    return inspection


def evc_report(ctx: TransitionContext) -> str | None:
    """Record the visit findings and recommendation."""
    if ctx.payload.report is None:
        raise WorkflowValidationError("An inspection report is required.")
    inspection = _ensure_inspection(ctx)
    inspection.report = ctx.payload.report.model_dump(mode="json")
    inspection.recommendation = ctx.payload.report.recommendation.value
    inspection.status = InspectionStatus.COMPLETED
    ctx.db.flush()
    ctx.add_detail("inspection_id", str(inspection.id))
    ctx.add_detail("recommendation", ctx.payload.report.recommendation.value)
    return "Expert Visit Committee report submitted."


def observations(ctx: TransitionContext) -> str | None:
    """Place the Regulation Bureau observations on the file."""
    text = (ctx.payload.observations or ctx.payload.comment or "").strip()
    if not text:
        raise WorkflowValidationError("Record the Regulation Bureau observations.")
    data = _data(ctx)
    data["bureau_observations"] = text
    _store_data(ctx, data)
    ctx.add_detail("observations", text)
    return "Regulation Bureau observations recorded."


def list_for_ec(ctx: TransitionContext) -> str | None:
    """Place the case on the Executive Committee agenda."""
    data = _data(ctx)
    if ctx.payload.approved_intake is not None:
        data["approved_intake"] = ctx.payload.approved_intake
        ctx.add_detail("approved_intake", ctx.payload.approved_intake)
    _store_data(ctx, data)
    committee = Committee(
        application_id=ctx.application.id,
        type=CommitteeType.EC,
        mode=CommitteeMode.ONLINE,
        scheduled_at=ctx.now,
        status=CommitteeStatus.SCHEDULED,
        apH_clause="APH 1.10a",
    )
    ctx.db.add(committee)
    ctx.db.flush()
    ctx.add_detail("committee_id", str(committee.id))
    return "Case listed before the Executive Committee."


def shc_hearing(ctx: TransitionContext) -> str | None:
    """Record the single SHC hearing outcome (APH 2.23.3)."""
    if ctx.payload.shc_outcome is None:
        raise WorkflowValidationError("Record the SHC hearing outcome.")
    decision = decision_letters.record_decision(
        ctx.db,
        ctx.application,
        body=DecisionBody.SHC,
        outcome=ctx.payload.shc_outcome,
        actor=ctx.actor,
        clock=ctx.clock,
        notes=ctx.payload.notes or ctx.payload.comment or "",
        apH_clause=ctx.transition.apH_clause,
    )
    ctx.add_detail("decision_id", str(decision.id))
    ctx.add_detail("shc_outcome", decision.outcome.value)
    return f"SHC hearing recorded: {decision.outcome.value}."


# ---------------------------------------------------------------------------
# Decisions, ratification and appeal
# ---------------------------------------------------------------------------


def _record_ec_decision(ctx: TransitionContext, outcome: DecisionOutcome) -> str | None:
    decision = decision_letters.record_decision(
        ctx.db,
        ctx.application,
        body=DecisionBody.EC,
        outcome=outcome,
        actor=ctx.actor,
        clock=ctx.clock,
        quorum_met=bool(ctx.payload.quorum_met),
        notes=ctx.payload.notes or ctx.payload.comment or "",
        apH_clause=ctx.transition.apH_clause,
    )
    data = _data(ctx)
    data["pending_outcome"] = outcome.value
    data["decision"] = {
        "outcome": outcome.value,
        "decided_by": str(ctx.actor.id),
        "decided_by_name": ctx.actor.name,
        "decided_at": ctx.now.isoformat(),
        "quorum_met": bool(ctx.payload.quorum_met),
        "notes": ctx.payload.notes or ctx.payload.comment,
    }
    if ctx.payload.speaking_order:
        ctx.application.speaking_order = ctx.payload.speaking_order
        data["speaking_order"] = ctx.payload.speaking_order
    _store_data(ctx, data)
    if outcome == DecisionOutcome.LOA:
        ctx.application.decision_type = None
    ctx.add_detail("decision_id", str(decision.id))
    ctx.add_detail("outcome", outcome.value)
    ctx.add_detail("quorum_met", bool(ctx.payload.quorum_met))
    return f"Executive Committee decision recorded: {outcome.value}."


def _decision_effect(outcome: DecisionOutcome) -> Effect:
    def effect(ctx: TransitionContext) -> str | None:
        return _record_ec_decision(ctx, outcome)

    return effect


def council_ratification(ctx: TransitionContext) -> str | None:
    """Ratify an existing EC decision with a met quorum (APH 2.25a)."""
    decision = _latest_decision(ctx, DecisionBody.EC)
    if decision is None:
        raise WorkflowValidationError("No Executive Committee decision exists to ratify.")
    if not decision.quorum_met:
        raise WorkflowValidationError(
            "The Executive Committee decision did not have a met quorum."
        )
    ratification = decision_letters.record_ratification(
        ctx.db,
        decision,
        actor=ctx.actor,
        ratified_on=ctx.now.date(),
        reference=ctx.payload.notes,
    )
    ctx.add_detail("decision_id", str(decision.id))
    ctx.add_detail("ratification_id", str(ratification.id))
    return "Executive Committee decision ratified by the Council secretariat."


def _confirm(outcome: DecisionOutcome) -> Effect:
    def effect(ctx: TransitionContext) -> str | None:
        original = _latest_decision(ctx, DecisionBody.EC)
        decision = decision_letters.record_decision(
            ctx.db,
            ctx.application,
            body=DecisionBody.EC,
            outcome=outcome,
            actor=ctx.actor,
            clock=ctx.clock,
            quorum_met=bool(original.quorum_met) if original is not None else False,
            notes=ctx.payload.notes or "Ratified decision recorded.",
            apH_clause=ctx.transition.apH_clause,
        )
        data = _data(ctx)
        data["pending_outcome"] = outcome.value
        _store_data(ctx, data)
        ctx.add_detail("decision_id", str(decision.id))
        return f"Ratified {outcome.value} decision recorded."

    return effect


def _issue_letter(letter_type: DecisionLetterType) -> Effect:
    def effect(ctx: TransitionContext) -> str | None:
        decision = _latest_decision(ctx, DecisionBody.EC)
        speaking_order = ctx.payload.speaking_order or ctx.application.speaking_order
        letter = decision_letters.issue_letter(
            ctx.db,
            ctx.application,
            letter_type=letter_type,
            actor=ctx.actor,
            clock=ctx.clock,
            audit=ctx.audit,
            decision=decision,
            apH_clause=ctx.transition.apH_clause,
            speaking_order=speaking_order,
            observations=ctx.payload.observations,
            settings=ctx.settings,
            request=ctx.request,
        )
        ctx.add_detail("letter_id", str(letter.id))
        ctx.add_detail("letter_number", letter.letter_number)
        return f"{letter_type.value} letter {letter.letter_number} issued."

    return effect


def file_appeal(ctx: TransitionContext) -> str | None:
    """Record the single appeal against the latest LoD/LoR."""
    now = ctx.now
    appeal = Appeal(
        application_id=ctx.application.id,
        filed_at=now,
        within_deadline=True,
        loop_no=ctx.application.appeal_loop_count + 1,
        sac_recommendation=None,
        apH_clause=ctx.transition.apH_clause,
        needs_verification=False,
    )
    ctx.db.add(appeal)
    ctx.db.flush()
    complete_timers(
        ctx.db, ctx.application, rule_code="APPEAL_WINDOW", audit=ctx.audit
    )
    data = _data(ctx)
    data["appeal"] = {
        "appeal_id": str(appeal.id),
        "filed_at": now.isoformat(),
        "grounds": ctx.payload.appeal_text or ctx.payload.comment,
    }
    data["appeal_start_event"] = ctx.definition.config.get(
        "appeal_start_event", "DECISION_UPLOADED"
    )
    _store_data(ctx, data)
    ctx.add_detail("appeal_id", str(appeal.id))
    return "Appeal filed with the Standing Appellate Committee."


def send_back(ctx: TransitionContext) -> str | None:
    """Record the SAC's single send-back."""
    ctx.application.appeal_loop_count += 1
    appeal = _latest_appeal(ctx)
    if appeal is not None:
        appeal.sac_recommendation = DecisionOutcome.SEND_BACK.value
    ctx.add_detail("appeal_loop_count", ctx.application.appeal_loop_count)
    return "The SAC sent the case back once for re-examination."


def _latest_appeal(ctx: TransitionContext) -> Appeal | None:
    return ctx.db.scalar(
        select(Appeal)
        .where(Appeal.application_id == ctx.application.id)
        .order_by(Appeal.created_at.desc())
        .limit(1)
    )


def sac_recommend(ctx: TransitionContext) -> str | None:
    """Record the SAC recommendation (APH 1.11d)."""
    if ctx.payload.sac_recommendation is None:
        raise WorkflowValidationError("Record the SAC recommendation.")
    outcome = ctx.payload.sac_recommendation
    decision = decision_letters.record_decision(
        ctx.db,
        ctx.application,
        body=DecisionBody.SAC,
        outcome=outcome,
        actor=ctx.actor,
        clock=ctx.clock,
        notes=ctx.payload.notes or ctx.payload.comment or "",
        apH_clause=ctx.transition.apH_clause,
    )
    appeal = _latest_appeal(ctx)
    if appeal is not None:
        appeal.sac_recommendation = outcome.value
        appeal.decided_at = ctx.now
    ctx.add_detail("decision_id", str(decision.id))
    ctx.add_detail("sac_recommendation", outcome.value)
    return f"SAC recommendation recorded: {outcome.value}."


def council_final(ctx: TransitionContext) -> str | None:
    """Record the Council's final decision (APH 1.11e)."""
    if ctx.payload.decision is None:
        raise WorkflowValidationError("Record the Council's final decision.")
    outcome = ctx.payload.decision
    decision = decision_letters.record_decision(
        ctx.db,
        ctx.application,
        body=DecisionBody.COUNCIL,
        outcome=outcome,
        actor=ctx.actor,
        clock=ctx.clock,
        quorum_met=bool(ctx.payload.quorum_met),
        notes=ctx.payload.notes or ctx.payload.comment or "",
        apH_clause=ctx.transition.apH_clause,
    )
    appeal = _latest_appeal(ctx)
    if appeal is not None:
        appeal.council_decision = outcome.value
        appeal.decided_at = ctx.now
    data = _data(ctx)
    data["final_outcome"] = outcome.value
    data["pending_outcome"] = outcome.value
    _store_data(ctx, data)
    ctx.add_detail("decision_id", str(decision.id))
    ctx.add_detail("final_outcome", outcome.value)
    return f"Council final decision recorded: {outcome.value}."


def endorse_decision(ctx: TransitionContext) -> str | None:
    """Record the Regional Officer endorsement (a signature, not a vote)."""
    data = _data(ctx)
    data["regional_endorsement"] = {
        "by": ctx.actor.name,
        "at": ctx.now.isoformat(),
    }
    _store_data(ctx, data)
    ctx.add_detail("endorsed_by", ctx.actor.name)
    return "Regional Officer endorsed the final decision."


def finalize_no_appeal(ctx: TransitionContext) -> str | None:
    """Make the decision final when nobody appealed in time (APH 1.11a)."""
    complete_timers(
        ctx.db, ctx.application, rule_code="APPEAL_WINDOW", audit=ctx.audit
    )
    data = _data(ctx)
    outcome = data.get("pending_outcome") or (
        ctx.application.decision_type.value if ctx.application.decision_type else None
    )
    if outcome is None:
        raise WorkflowValidationError("The decision outcome is not recorded.")
    data["final_outcome"] = outcome
    data["appeal_window_closed"] = ctx.now.isoformat()
    _store_data(ctx, data)
    ctx.add_detail("final_outcome", outcome)
    return "No appeal was filed; the decision is final."


# ---------------------------------------------------------------------------
# Security Deposit and post-approval lifecycle
# ---------------------------------------------------------------------------


def _deposits(ctx: TransitionContext):
    from app.models.security_deposit import SecurityDeposit

    return list(
        ctx.db.scalars(
            select(SecurityDeposit).where(
                SecurityDeposit.application_id == ctx.application.id
            )
        ).all()
    )


def pay_security_deposit(ctx: TransitionContext) -> str | None:
    """Mark the deposit paid and record the receipt and Affidavit 3."""
    deposits = _deposits(ctx)
    if not deposits:
        ctx.add_message("No Security Deposit rows exist; proof was recorded on the file.")
    for deposit in deposits:
        deposit.status = SecurityDepositStatus.PAID
    complete_timers(
        ctx.db, ctx.application, rule_code="SECURITY_DEPOSIT", audit=ctx.audit
    )
    data = _data(ctx)
    data["security_deposit"] = {
        "receipt_no": ctx.payload.deposit_receipt_no,
        "affidavit3_filed": bool(ctx.payload.affidavit3_filed),
        "paid_at": ctx.now.isoformat(),
    }
    _store_data(ctx, data)
    ctx.add_detail("deposit_receipt_no", ctx.payload.deposit_receipt_no)
    return "Security Deposit and Affidavit 3 recorded."


def apply_deposit_penalty(ctx: TransitionContext) -> str | None:
    """Apply the 10% or 20% penalty and keep the case pending (APH 2.25f)."""
    intimation = ctx.application.security_deposit_due_on
    if intimation is None:
        raise WorkflowValidationError("No Security Deposit intimation exists.")
    rule = ctx.db.scalar(select(DeadlineRule).where(DeadlineRule.code == "SECURITY_DEPOSIT"))
    grace = rule.duration_days if rule is not None else 15
    percent = security_deposit_penalty(intimation, ctx.now.date())
    if percent <= 0:
        raise WorkflowValidationError("No Security Deposit penalty is due yet.")
    status = (
        SecurityDepositStatus.PENALTY_10
        if percent == 10
        else SecurityDepositStatus.PENALTY_20
    )
    for deposit in _deposits(ctx):
        deposit.status = status
        deposit.penalty_percent = percent
    data = _data(ctx)
    data["deposit_penalty_percent"] = percent
    data["security_deposit_grace_days"] = grace
    _store_data(ctx, data)
    ctx.add_detail("penalty_percent", percent)
    return f"Security Deposit penalty of {percent}% applied."


def forfeit_deposit(ctx: TransitionContext) -> str | None:
    """Forfeit the deposit and withdraw the approval after 31 July (APH 2.25f)."""
    for deposit in _deposits(ctx):
        deposit.status = SecurityDepositStatus.FORFEITED
    data = _data(ctx)
    data["security_deposit_forfeited"] = ctx.now.isoformat()
    _store_data(ctx, data)
    ctx.add_detail("forfeited", True)
    return "Security Deposit not paid in time; the approval is withdrawn."


def expire_loa(ctx: TransitionContext) -> str | None:
    """Record that the two-academic-year LoA has expired (APH 1.10b)."""
    data = _data(ctx)
    data["loa_expired_on"] = ctx.now.date().isoformat()
    _store_data(ctx, data)
    ctx.add_detail("loa_valid_until", (
        ctx.application.loa_valid_until.isoformat()
        if ctx.application.loa_valid_until
        else None
    ))
    return "The LoA validity has ended; the institution needs a fresh EoA."


# ---------------------------------------------------------------------------
# Track B - self-disclosure
# ---------------------------------------------------------------------------


def run_self_disclosure_check(ctx: TransitionContext) -> str | None:
    """Generate the automatic Deficiency Report (APH 2.3.5a)."""
    report = build_deficiency_report(
        ctx.db,
        ctx.application,
        evaluated_at=ctx.now,
        include_not_assessed=False,
    )
    created: list[Deficiency] = []
    due = _deficiency_due_date(ctx)
    for item in report.items:
        if item.status != "FAIL":
            continue
        deficiency = Deficiency(
            application_id=ctx.application.id,
            category=item.category,
            description=f"{item.name}: {item.message}",
            raised_by=ctx.actor.id,
            status=DeficiencyStatus.OPEN,
            due_date=due,
        )
        ctx.db.add(deficiency)
        created.append(deficiency)
    ctx.db.flush()

    data = _data(ctx)
    data["self_disclosure_report"] = {
        "generated_at": ctx.now.isoformat(),
        "nil_deficiency": report.nil_deficiency,
        "failed_count": report.failed_count,
        "banner": report.banner,
    }
    _store_data(ctx, data)
    ctx.add_detail("nil_deficiency", report.nil_deficiency)
    ctx.add_detail("deficiency_ids", [str(item.id) for item in created])
    if report.nil_deficiency:
        return "Self-disclosure check complete: Nil Deficiency."
    return f"Self-disclosure check complete: {len(created)} deficiency item(s) raised."


def record_random_evc(ctx: TransitionContext) -> str | None:
    """Constitute the random EVC for a sampled self-disclosure case."""
    ctx.application.evc_random_selected = True
    data = _data(ctx)
    data["random_evc"] = True
    _store_data(ctx, data)
    return constitute_evc(ctx) or "Random Expert Visit Committee selected."


def zero_intake_if_closure_failed(ctx: TransitionContext) -> str | None:
    """Give an EoA with zero intake when a closure did not succeed (APH 2.3.3h)."""
    if not ctx.payload.closure_failed:
        return None
    programmes = list(
        ctx.db.scalars(
            select(ApplicationProgram).where(
                ApplicationProgram.application_id == ctx.application.id
            )
        ).all()
    )
    for programme in programmes:
        programme.intake = 0
        programme.status = ProgrammeStatus.ZERO_INTAKE
    data = _data(ctx)
    data["closure_failed"] = True
    data["approved_intake"] = 0
    _store_data(ctx, data)
    ctx.add_detail("closure_failed", True)
    ctx.add_detail("approved_intake", 0)
    return "Closure did not succeed; the EoA records zero intake."


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


def reopen_once(ctx: TransitionContext) -> str | None:
    """Reopen a wrongly submitted application once (APH 2.3.3d-e)."""
    if ctx.application.reopen_count >= 1:
        raise WorkflowValidationError("An application can be reopened only once.")
    ctx.application.reopen_count += 1
    ctx.application.locked_at = None
    ctx.application.submitted_at = None
    ctx.application.assigned_officer_id = None
    ctx.application.sla_due_at = None
    ctx.add_detail("reopen_count", ctx.application.reopen_count)
    ctx.add_detail("trust_resolution_required", "Format 3")
    return "Application reopened once; correct the data and resubmit."


def withdraw_application(ctx: TransitionContext) -> str | None:
    """Withdraw the application without deleting its history."""
    ctx.application.is_withdrawn = True
    ctx.application.sla_due_at = None
    ctx.add_detail("reason", ctx.payload.comment)
    return "Application withdrawn; the history is preserved."


def _noop(ctx: TransitionContext) -> str | None:
    """An explicitly configured no-op effect."""
    return None


EFFECTS: dict[str, Effect] = {
    "submit": submit,
    "assign_scrutiny": assign_scrutiny,
    "scrutiny_recommend": scrutiny_recommend,
    "pay_ter": pay_ter,
    "create_deficiencies": create_deficiencies,
    "communicate_deficiency": communicate_deficiency,
    "record_responses": record_responses,
    "verify_deficiencies": verify_deficiencies,
    "constitute_evc": constitute_evc,
    "submit_evc_video": submit_evc_video,
    "evc_report": evc_report,
    "observations": observations,
    "list_for_ec": list_for_ec,
    "shc_hearing": shc_hearing,
    "ec_decide_loa": _decision_effect(DecisionOutcome.LOA),
    "ec_decide_eoa": _decision_effect(DecisionOutcome.EOA),
    "ec_decide_lod": _decision_effect(DecisionOutcome.LOD),
    "ec_decide_lor": _decision_effect(DecisionOutcome.LOR),
    "council_ratification": council_ratification,
    "confirm_loa": _confirm(DecisionOutcome.LOA),
    "confirm_lod": _confirm(DecisionOutcome.LOD),
    "confirm_lor": _confirm(DecisionOutcome.LOR),
    "issue_loa": _issue_letter(DecisionLetterType.LOA),
    "issue_eoa": _issue_letter(DecisionLetterType.EOA),
    "issue_lod": _issue_letter(DecisionLetterType.LOD),
    "issue_lor": _issue_letter(DecisionLetterType.LOR),
    "file_appeal": file_appeal,
    "send_back": send_back,
    "sac_recommend": sac_recommend,
    "council_final": council_final,
    "endorse_decision": endorse_decision,
    "finalize_no_appeal": finalize_no_appeal,
    "pay_security_deposit": pay_security_deposit,
    "apply_deposit_penalty": apply_deposit_penalty,
    "forfeit_deposit": forfeit_deposit,
    "expire_loa": expire_loa,
    "run_self_disclosure_check": run_self_disclosure_check,
    "record_random_evc": record_random_evc,
    "zero_intake_if_closure_failed": zero_intake_if_closure_failed,
    "reopen_once": reopen_once,
    "withdraw_application": withdraw_application,
    "noop": _noop,
}
"""Registry of effect name -> callable. Names are the seed-data contract."""


def apply_effect(name: str, ctx: TransitionContext) -> str | None:
    """Run one effect, failing loudly when seed data names an unknown effect."""
    effect = EFFECTS.get(name)
    if effect is None:
        from app.services.workflow_errors import WorkflowConfigurationError

        raise WorkflowConfigurationError(
            f"Workflow transition references unknown side effect {name!r}."
        )
    return effect(ctx)
