"""Named guards for the data-driven workflow.

``workflow_transitions.guard_expr`` stores guard *names*. This module is the
only place those names are resolved, so an administrator can re-order or
disable a guard in seed data without executing arbitrary code. Every guard
returns ``None`` when it passes or a human-readable reason when it fails.

A guard may also raise :class:`~app.services.workflow_errors.WorkflowConfigurationError`
when the underlying configuration row is missing, because that is an operator
problem rather than an invalid institution action.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime

from sqlalchemy import func, select

from app.models.application_type_route import ApplicationTypeRoute
from app.models.calendar import AcademicCalendarEvent
from app.models.deadline import DeadlineRule, Timer
from app.models.decision import Decision, DecisionLetter
from app.models.deficiency import Deficiency
from app.models.enums import (
    ApplicationTrack,
    CalendarEventKey,
    DecisionBody,
    DecisionLetterType,
    DecisionOutcome,
    DeficiencyStatus,
    Role,
    SecurityDepositStatus,
    TimerStatus,
)
from app.models.security_deposit import SecurityDeposit
from app.services.fee_calculator import (
    SecurityDepositPenaltyWindows,
    security_deposit_penalty,
)
from app.services.workflow_context import TransitionContext
from app.services.workflow_errors import WorkflowConfigurationError

Guard = Callable[[TransitionContext], str | None]

# Guards that cannot be evaluated before the actor has supplied the action
# payload. ``allowed-actions`` skips these so the UI can still list the action.
PAYLOAD_GUARDS: frozenset[str] = frozenset(
    {
        "decision_loa",
        "decision_eoa",
        "decision_lod",
        "decision_lor",
        "ec_quorum_met",
        "speaking_order_present",
        "shc_outcome_present",
        "deposit_proof_present",
        "closure_outcome_present",
    }
)

_DEFICIENCY_DUE_DAYS = 7


def _open_deficiency_count(ctx: TransitionContext) -> int:
    return int(
        ctx.db.scalar(
            select(func.count(Deficiency.id)).where(
                Deficiency.application_id == ctx.application.id,
                Deficiency.status != DeficiencyStatus.CLOSED,
            )
        )
        or 0
    )


def _route(ctx: TransitionContext) -> ApplicationTypeRoute | None:
    return ctx.db.scalar(
        select(ApplicationTypeRoute).where(
            ApplicationTypeRoute.type == ctx.application.application_type
        )
    )


def _route_flag(
    ctx: TransitionContext,
    attr: str,
    *,
    default: bool,
) -> bool:
    route = _route(ctx)
    if route is not None:
        return bool(getattr(route, attr))
    return default


def _deadline_rule(ctx: TransitionContext, code: str) -> DeadlineRule:
    rule = ctx.db.scalar(select(DeadlineRule).where(DeadlineRule.code == code))
    if rule is None:
        raise WorkflowConfigurationError(
            f"Deadline rule {code!r} is not configured."
        )
    return rule


def _calendar_date(ctx: TransitionContext, key: CalendarEventKey) -> date:
    event = ctx.db.scalar(
        select(AcademicCalendarEvent).where(
            AcademicCalendarEvent.academic_year == ctx.application.academic_year,
            AcademicCalendarEvent.event_key == key,
        )
    )
    if event is None:
        raise WorkflowConfigurationError(
            f"Academic Calendar event {key.value} is not configured for "
            f"{ctx.application.academic_year}."
        )
    return event.date


def _latest_letter(ctx: TransitionContext) -> DecisionLetter | None:
    return ctx.db.scalar(
        select(DecisionLetter)
        .where(DecisionLetter.application_id == ctx.application.id)
        .order_by(DecisionLetter.created_at.desc(), DecisionLetter.issued_on.desc())
        .limit(1)
    )


def _appeal_deadline(ctx: TransitionContext) -> datetime | None:
    if ctx.application.appeal_deadline is not None:
        return ctx.application.appeal_deadline
    letter = _latest_letter(ctx)
    if letter is not None and letter.appeal_deadline is not None:
        return letter.appeal_deadline
    # The Timer is the scheduler's source of truth (APH 1.11a). Older files can
    # have a running clock without the application/letter read-model columns.
    timer = ctx.db.scalar(
        select(Timer)
        .join(DeadlineRule, DeadlineRule.id == Timer.deadline_rule_id)
        .where(
            Timer.application_id == ctx.application.id,
            DeadlineRule.code == "APPEAL_WINDOW",
            Timer.status.in_(
                (TimerStatus.PENDING, TimerStatus.DUE, TimerStatus.BREACHED)
            ),
        )
        .order_by(Timer.due_at.desc())
        .limit(1)
    )
    return timer.due_at if timer is not None else None


def _outcome(ctx: TransitionContext) -> str | None:
    data = ctx.application.data if isinstance(ctx.application.data, dict) else {}
    pending = data.get("pending_outcome")
    if pending:
        return str(pending)
    if ctx.application.decision_type is not None:
        return ctx.application.decision_type.value
    return None


# ---------------------------------------------------------------------------
# Route flags
# ---------------------------------------------------------------------------


def route_requires_evc(ctx: TransitionContext) -> str | None:
    """Pass when the routing row requires an Expert Visit Committee."""
    default = ctx.application.track == ApplicationTrack.NEW_INSTITUTION
    if _route_flag(ctx, "requires_evc", default=default):
        return None
    return "This application type does not require an Expert Visit Committee (APH 1.9)."


def route_not_requires_evc(ctx: TransitionContext) -> str | None:
    """Pass when the routing row does not require an EVC."""
    default = ctx.application.track == ApplicationTrack.NEW_INSTITUTION
    if _route_flag(ctx, "requires_evc", default=default):
        return "This application type requires an Expert Visit Committee (APH 1.9)."
    return None


def route_requires_hearing(ctx: TransitionContext) -> str | None:
    """Pass when the routing row requires a Standing Hearing Committee."""
    if _route_flag(ctx, "requires_hearing_aa", default=False):
        return None
    return "This application type does not require a Standing Hearing Committee (APH 2.23.3)."


def route_not_requires_hearing(ctx: TransitionContext) -> str | None:
    """Pass when the routing row does not require an SHC hearing."""
    if _route_flag(ctx, "requires_hearing_aa", default=False):
        return "A Standing Hearing Committee hearing is required for this type (APH 2.23.3)."
    return None


# ---------------------------------------------------------------------------
# Deficiencies
# ---------------------------------------------------------------------------


def has_deficiencies(ctx: TransitionContext) -> str | None:
    """Pass when the payload communicates at least one deficiency."""
    if ctx.payload.deficiencies:
        return None
    if _open_deficiency_count(ctx) > 0:
        return None
    return "At least one deficiency item is required."


def open_deficiencies(ctx: TransitionContext) -> str | None:
    """Pass when at least one deficiency is still open or responded."""
    if _open_deficiency_count(ctx) > 0:
        return None
    return "There are no open deficiencies to act on."


def responded_deficiencies(ctx: TransitionContext) -> str | None:
    """Pass when at least one deficiency has an institution response."""
    count = ctx.db.scalar(
        select(func.count(Deficiency.id)).where(
            Deficiency.application_id == ctx.application.id,
            Deficiency.status == DeficiencyStatus.RESPONDED,
        )
    )
    if int(count or 0) > 0:
        return None
    return "No responded deficiency is waiting for verification."


def no_open_deficiencies(ctx: TransitionContext) -> str | None:
    """Pass when every deficiency has been closed."""
    remaining = _open_deficiency_count(ctx)
    if remaining == 0:
        return None
    return f"{remaining} deficiency item(s) must be closed first (APH 2.4)."


def documents_reuploaded(ctx: TransitionContext) -> str | None:
    """Pass when no rejected document still awaits a replacement version.

    A reviewer rejection opens a document deficiency. Compliance cannot be
    submitted until the institution replaces every rejected document, because
    Re-Scrutiny only verifies the listed deficiencies (APH 1.8f, 1.8g, 2.4).
    """
    from app.models.document import Document
    from app.models.enums import DocumentVerificationStatus

    rows = ctx.db.scalars(
        select(Document).where(Document.application_id == ctx.application.id)
    ).all()
    newest: dict[str, Document] = {}
    for document in rows:
        current = newest.get(document.doc_type)
        if current is None or document.version > current.version:
            newest[document.doc_type] = document
    rejected = [
        document
        for document in newest.values()
        if document.verification_status == DocumentVerificationStatus.REJECTED
        and document.superseded_by is None
    ]
    if not rejected:
        return None
    labels = ", ".join(sorted(document.doc_type for document in rejected))
    return (
        f"Re-upload the rejected document(s) before submitting compliance: {labels} "
        "(APH 1.8f, 2.4)."
    )



# ---------------------------------------------------------------------------
# Inspection / EVC
# ---------------------------------------------------------------------------


def is_evc_member(ctx: TransitionContext) -> str | None:
    """Pass when the actor is a visit committee member."""
    if ctx.actor.role == Role.EVC_MEMBER:
        return None
    return "Only an Expert Visit Committee member may record visit evidence."


def video_uploaded(ctx: TransitionContext) -> str | None:
    """Pass when a visit video of at least 30 minutes is on the file."""
    data = ctx.application.data if isinstance(ctx.application.data, dict) else {}
    video = data.get("evc_video") or {}
    minutes = int(video.get("minutes") or 0)
    url = str(video.get("url") or "")
    if not url:
        return "Upload the Expert Visit Committee video before submitting the report (APH 1.9f-g)."
    if minutes < 30:
        return "The visit video must be at least 30 minutes long (APH 1.9f-g)."
    return None


def shc_outcome_present(ctx: TransitionContext) -> str | None:
    """Pass when the SHC hearing records an outcome."""
    if ctx.payload.shc_outcome is not None:
        return None
    return "Record the SHC hearing outcome (APH 2.23.3)."


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------


def _decision_is(ctx: TransitionContext, expected: DecisionOutcome) -> str | None:
    chosen = ctx.payload.decision
    if chosen is None:
        return f"Record the decision ({expected.value}) before applying it."
    if chosen != expected:
        return f"This edge records a {expected.value} decision, not {chosen.value}."
    return None


def decision_loa(ctx: TransitionContext) -> str | None:
    """Pass when the EC decision is an approval."""
    return _decision_is(ctx, DecisionOutcome.LOA)


def decision_eoa(ctx: TransitionContext) -> str | None:
    """Pass when the EC decision is an extension of approval."""
    return _decision_is(ctx, DecisionOutcome.EOA)


def decision_lod(ctx: TransitionContext) -> str | None:
    """Pass when the EC decision is a Letter of Deficiency."""
    return _decision_is(ctx, DecisionOutcome.LOD)


def decision_lor(ctx: TransitionContext) -> str | None:
    """Pass when the EC decision is a rejection."""
    return _decision_is(ctx, DecisionOutcome.LOR)


def ec_quorum_met(ctx: TransitionContext) -> str | None:
    """Pass when the actor confirms the Executive Committee quorum."""
    if ctx.payload.quorum_met:
        return None
    return "An Executive Committee decision requires a met quorum (APH 1.10a)."


def ec_decision_quorum_met(ctx: TransitionContext) -> str | None:
    """Pass when the recorded EC decision had a met quorum (APH 2.25a)."""
    decision = ctx.db.scalar(
        select(Decision)
        .where(
            Decision.application_id == ctx.application.id,
            Decision.body == DecisionBody.EC,
        )
        .order_by(Decision.created_at.desc())
        .limit(1)
    )
    if decision is None:
        return "No Executive Committee decision exists to ratify."
    if not decision.quorum_met:
        return "The Executive Committee decision did not have a met quorum."
    return None


def speaking_order_present(ctx: TransitionContext) -> str | None:
    """Pass when a rejection carries a Speaking Order (APH 2.24a)."""
    text = (ctx.payload.speaking_order or ctx.application.speaking_order or "").strip()
    if text:
        return None
    return "A rejection requires a Speaking Order with reasons (APH 2.24a)."


def _outcome_is(ctx: TransitionContext, expected: str) -> str | None:
    actual = _outcome(ctx)
    if actual == expected:
        return None
    return f"The recorded decision is {actual or 'missing'}, not {expected}."


def ratified_outcome_loa(ctx: TransitionContext) -> str | None:
    """Pass when the ratified EC decision was an approval."""
    return _outcome_is(ctx, "LOA")


def ratified_outcome_lod(ctx: TransitionContext) -> str | None:
    """Pass when the ratified EC decision was a Letter of Deficiency."""
    return _outcome_is(ctx, "LOD")


def ratified_outcome_lor(ctx: TransitionContext) -> str | None:
    """Pass when the ratified EC decision was a rejection."""
    return _outcome_is(ctx, "LOR")


def final_outcome_loa(ctx: TransitionContext) -> str | None:
    """Pass when the Council's final decision is an approval."""
    return _outcome_is(ctx, "LOA")


def final_outcome_lod(ctx: TransitionContext) -> str | None:
    """Pass when the Council's final decision is a Letter of Deficiency."""
    return _outcome_is(ctx, "LOD")


def final_outcome_lor(ctx: TransitionContext) -> str | None:
    """Pass when the Council's final decision is a rejection."""
    return _outcome_is(ctx, "LOR")


# ---------------------------------------------------------------------------
# Appeal
# ---------------------------------------------------------------------------


def within_appeal_window(ctx: TransitionContext) -> str | None:
    """Pass when the appeal is filed inside the configured window (APH 1.11a)."""
    deadline = _appeal_deadline(ctx)
    if deadline is None:
        return "There is no appeal clock on this application."
    now = ctx.now
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=UTC)
    if now <= deadline:
        return None
    return (
        "The appeal window closed on "
        f"{deadline.date().isoformat()}; a late appeal cannot be accepted (APH 1.11a)."
    )


def no_prior_appeal(ctx: TransitionContext) -> str | None:
    """Pass when the institution has not already appealed."""
    if _appeal_count(ctx) == 0:
        return None
    return "Only one appeal is permitted per application (APH 1.11a)."


def has_prior_appeal(ctx: TransitionContext) -> str | None:
    """Pass when an appeal already exists.

    After the SAC sends a case back once, the re-examined decision returns to
    the SAC directly: the institution cannot appeal a second time, so the file
    must not re-enter the appeal window (APH 1.11a, Annexure-7).
    """
    if _appeal_count(ctx) > 0:
        return None
    return "No appeal has been filed; the decision must open an appeal window first."


def _appeal_count(ctx: TransitionContext) -> int:
    from app.models.appeal import Appeal

    count = ctx.db.scalar(
        select(func.count(Appeal.id)).where(Appeal.application_id == ctx.application.id)
    )
    return int(count or 0)


def appeal_window_closed(ctx: TransitionContext) -> str | None:
    """Pass when the appeal window has elapsed without an appeal."""
    deadline = _appeal_deadline(ctx)
    if deadline is None:
        return "There is no appeal clock on this application."
    now = ctx.now
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=UTC)
    if now > deadline:
        return None
    letter = _latest_letter(ctx)
    if letter is not None and letter.acknowledged_at is not None:
        return None
    return (
        "The appeal window is still open until "
        f"{deadline.date().isoformat()} (APH 1.11a)."
    )


def appeal_loop_available(ctx: TransitionContext) -> str | None:
    """Pass when the SAC has not already sent the case back once."""
    if ctx.application.appeal_loop_count < 1:
        return None
    return "The SAC may send a case back only once (Annexure-7)."


def _letter_type_is(ctx: TransitionContext, expected: DecisionLetterType) -> str | None:
    letter = _latest_letter(ctx)
    if letter is None:
        return "No decision letter has been issued yet."
    if letter.letter_type != expected:
        return f"The appealable decision is a {letter.letter_type.value}, not {expected.value}."
    return None


def appeal_letter_loa(ctx: TransitionContext) -> str | None:
    """Pass when the appeal period follows a Letter of Approval."""
    return _letter_type_is(ctx, DecisionLetterType.LOA)


def appeal_letter_lod(ctx: TransitionContext) -> str | None:
    """Pass when the appeal period follows a Letter of Deficiency."""
    return _letter_type_is(ctx, DecisionLetterType.LOD)


def appeal_letter_lor(ctx: TransitionContext) -> str | None:
    """Pass when the appeal period follows a rejection."""
    return _letter_type_is(ctx, DecisionLetterType.LOR)


# ---------------------------------------------------------------------------
# Reopen
# ---------------------------------------------------------------------------


def reopen_available(ctx: TransitionContext) -> str | None:
    """Pass when the application has not already been reopened."""
    if ctx.application.reopen_count < 1:
        return None
    return "An application can be reopened only once (APH 2.3.3d-e)."


# ---------------------------------------------------------------------------
# Security Deposit and LoA lifecycle
# ---------------------------------------------------------------------------


def _deposits(ctx: TransitionContext) -> list[SecurityDeposit]:
    return list(
        ctx.db.scalars(
            select(SecurityDeposit).where(
                SecurityDeposit.application_id == ctx.application.id
            )
        ).all()
    )


def _deposit_intimation(ctx: TransitionContext) -> date | None:
    if ctx.application.security_deposit_due_on is not None:
        return ctx.application.security_deposit_due_on
    deposits = _deposits(ctx)
    return deposits[0].created_on if deposits else None


def deposit_proof_present(ctx: TransitionContext) -> str | None:
    """Pass when the deposit receipt and Affidavit 3 are recorded."""
    if ctx.payload.deposit_receipt_no and ctx.payload.affidavit3_filed:
        return None
    return (
        "Record the Security Deposit receipt number and confirm Affidavit 3 "
        "before marking the deposit paid (APH 2.25f)."
    )


def deposit_payable(ctx: TransitionContext) -> str | None:
    """Pass when the deposit is still payable."""
    deposits = _deposits(ctx)
    if any(deposit.status in {
        SecurityDepositStatus.WITHDRAWN,
        SecurityDepositStatus.FORFEITED,
    } for deposit in deposits):
        return "The approval has been withdrawn; the deposit can no longer be paid."
    return deposit_proof_present(ctx)


def deposit_penalty_due(ctx: TransitionContext) -> str | None:
    """Pass when a higher penalty window has been reached (APH 2.25f)."""
    intimation = _deposit_intimation(ctx)
    if intimation is None:
        return "No Security Deposit intimation exists for this application."
    rule = _deadline_rule(ctx, "SECURITY_DEPOSIT")
    penalty = security_deposit_penalty(
        intimation,
        ctx.now.date(),
        windows=SecurityDepositPenaltyWindows(grace_days=rule.duration_days),
    )
    applied = int(
        (ctx.application.data or {}).get("deposit_penalty_percent") or 0
    )
    if penalty > applied:
        return None
    return "No higher Security Deposit penalty window has been reached yet (APH 2.25f)."


def deposit_forfeited(ctx: TransitionContext) -> str | None:
    """Pass when the 31 July final deposit date has passed (APH 2.25f)."""
    final_date = _calendar_date(ctx, CalendarEventKey.SD_PENALTY20_31JUL)
    if ctx.now.date() > final_date:
        return None
    return (
        f"The approval can only be withdrawn after {final_date.isoformat()} (APH 2.25f)."
    )


def loa_expired(ctx: TransitionContext) -> str | None:
    """Pass when the two-academic-year LoA validity has elapsed (APH 1.10b)."""
    if ctx.application.loa_valid_until is None:
        return "This application has no LoA validity date."
    if ctx.now.date() > ctx.application.loa_valid_until:
        return None
    return (
        "The LoA remains valid until "
        f"{ctx.application.loa_valid_until.isoformat()} (APH 1.10b)."
    )


# ---------------------------------------------------------------------------
# Cross-cutting APH rules
# ---------------------------------------------------------------------------


def eoa_before_last_date(ctx: TransitionContext) -> str | None:
    """Pass when the EoA is decided by the Academic Calendar last date (APH 2.25j)."""
    last_date = _calendar_date(ctx, CalendarEventKey.LAST_DATE_EOA)
    if ctx.now.date() <= last_date:
        return None
    return (
        "No Extension of Approval can be processed after "
        f"{last_date.isoformat()} (APH 2.25j)."
    )


def no_pending_investigation(ctx: TransitionContext) -> str | None:
    """Pass when no court case, charge sheet or investigation is pending (APH 2.6e)."""
    data = ctx.application.data if isinstance(ctx.application.data, dict) else {}
    flags = {
        "pending_court_case": bool(ctx.payload.pending_court_case)
        or bool(data.get("pending_court_case")),
        "charge_sheet_pending": bool(ctx.payload.charge_sheet_pending)
        or bool(data.get("charge_sheet_pending")),
        "pending_investigation": bool(data.get("pending_investigation")),
    }
    active = [name for name, value in flags.items() if value]
    if not active:
        return None
    return (
        "An intake increase or change is blocked while an investigation is pending "
        f"({', '.join(active)}) (APH 2.6e)."
    )


def core_branches_ok(ctx: TransitionContext) -> str | None:
    """Pass when Engineering & Technology keeps the required core branches (APH 2.6c)."""
    required = int(ctx.definition.config.get("core_branches_required", 3))
    data = ctx.application.data if isinstance(ctx.application.data, dict) else {}
    branches = data.get("core_branches")
    if isinstance(branches, list):
        count = len({str(item).strip() for item in branches if str(item).strip()})
    else:
        keywords = {
            str(item).lower()
            for item in ctx.definition.config.get("core_branch_keywords", [])
        }
        names = {
            programme.program_name.strip().lower()
            for programme in ctx.application.programs
            if programme.program_name
        }
        if not keywords:
            return None
        count = len({name for name in names if any(key in name for key in keywords)})
    if count >= required:
        return None
    return (
        f"Engineering & Technology must retain at least {required} core branches; "
        f"only {count} were identified (APH 2.6c)."
    )


def random_evc_selected(ctx: TransitionContext) -> str | None:
    """Pass when this case falls inside the random EVC sample (APH 2.3.5a)."""
    selected = _random_evc(ctx)
    if selected:
        return None
    return "This case was not selected for a random Expert Visit Committee."


def random_evc_not_selected(ctx: TransitionContext) -> str | None:
    """Pass when this case does not need a random EVC."""
    if _random_evc(ctx):
        return "This case was selected for a random Expert Visit Committee."
    return None


def _random_evc(ctx: TransitionContext) -> bool:
    if ctx.payload.random_evc is not None:
        return bool(ctx.payload.random_evc)
    percent = int(ctx.definition.config.get("random_evc_percent", 10))
    if percent <= 0:
        return False
    if percent >= 100:
        return True
    # Deterministic per application so a retry cannot change the sample.
    bucket = int(ctx.application.id.hex, 16) % 100
    return bucket < percent


def closure_outcome_present(ctx: TransitionContext) -> str | None:
    """Pass when the closure outcome is recorded (APH 2.3.3h)."""
    if ctx.payload.closure_failed is not None:
        return None
    return "Record whether the closure actually succeeded (APH 2.3.3h)."


GUARDS: dict[str, Guard] = {
    name: globals()[name]
    for name in (
        "route_requires_evc",
        "route_not_requires_evc",
        "route_requires_hearing",
        "route_not_requires_hearing",
        "has_deficiencies",
        "open_deficiencies",
        "responded_deficiencies",
        "no_open_deficiencies",
        "documents_reuploaded",
        "is_evc_member",
        "video_uploaded",
        "shc_outcome_present",
        "decision_loa",
        "decision_eoa",
        "decision_lod",
        "decision_lor",
        "ec_quorum_met",
        "ec_decision_quorum_met",
        "speaking_order_present",
        "ratified_outcome_loa",
        "ratified_outcome_lod",
        "ratified_outcome_lor",
        "final_outcome_loa",
        "final_outcome_lod",
        "final_outcome_lor",
        "within_appeal_window",
        "no_prior_appeal",
        "has_prior_appeal",
        "appeal_window_closed",
        "appeal_loop_available",
        "appeal_letter_loa",
        "appeal_letter_lod",
        "appeal_letter_lor",
        "reopen_available",
        "deposit_proof_present",
        "deposit_payable",
        "deposit_penalty_due",
        "deposit_forfeited",
        "loa_expired",
        "eoa_before_last_date",
        "no_pending_investigation",
        "core_branches_ok",
        "random_evc_selected",
        "random_evc_not_selected",
        "closure_outcome_present",
    )
}
"""Registry of guard name -> callable. Names are the seed-data contract."""


def evaluate_guard(name: str, ctx: TransitionContext) -> str | None:
    """Run one guard, failing loudly when seed data names an unknown guard."""
    guard = GUARDS.get(name)
    if guard is None:
        raise WorkflowConfigurationError(
            f"Workflow transition references unknown guard {name!r}."
        )
    return guard(ctx)
