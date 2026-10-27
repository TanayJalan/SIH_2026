"""The APH workflow catalogue expressed as seed data.

This module is a pure transcription of the APH Annexure-7 cycle into plain
Python dictionaries. It contains no workflow behaviour: guards, side effects
and role checks are *names* that the workflow service resolves from its
registry. ``scripts/seed_aph.py`` writes the result to
``backend/seeds/aph/workflow_definitions.json`` and ``app.seed`` loads it into
``workflow_definitions`` / ``workflow_states`` / ``workflow_transitions``.

Scope (prototype):

* Track A - Chapter I new institution and extension of approval.
* Track B - EoA by self-disclosure and NRI seats.
* Track C - existing-institution changes (shared Track A edges, optional EVC
  and an SHC compliance hearing).
* Track D - year-round scrutiny-only changes.

Hibernation, break-in-EoA, merger, ODL, university and
``CLOSURE_AND_NEW_INSTITUTION`` are deliberately out of scope and are marked
``not_implemented`` on their ``application_type_routes`` row.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# State metadata: label, SLA stage, terminal flag, clause
# ---------------------------------------------------------------------------

STATE_META: dict[str, dict[str, Any]] = {
    "DRAFT": {
        "label": "Draft",
        "stage": "APPLICATION",
        "terminal": False,
        "initial": True,
        "clause": "APH 1.4",
    },
    "SUBMITTED": {
        "label": "Submitted (locked, TER paid, portal number issued)",
        "stage": "APPLICATION",
        "terminal": False,
        "clause": "APH 1.4.3",
    },
    "SCRUTINY": {
        "label": "Scrutiny Committee",
        "stage": "SCRUTINY",
        "terminal": False,
        "clause": "APH 1.8",
    },
    "DEFICIENCY_COMMUNICATED": {
        "label": "Deficiency communicated (LoD)",
        "stage": "DEFICIENCY",
        "terminal": False,
        "clause": "APH 2.3.3b",
    },
    "INSTITUTION_COMPLIANCE": {
        "label": "Institution response received",
        "stage": "DEFICIENCY",
        "terminal": False,
        "clause": "APH 2.4",
    },
    "RE_SCRUTINY": {
        "label": "Re-Scrutiny of listed deficiencies",
        "stage": "SCRUTINY",
        "terminal": False,
        "clause": "APH 1.8",
    },
    "EVC_CONSTITUTED": {
        "label": "Expert Visit Committee constituted",
        "stage": "INSPECTION",
        "terminal": False,
        "clause": "APH 1.9a",
    },
    "EVC_DONE": {
        "label": "EVC report received",
        "stage": "INSPECTION",
        "terminal": False,
        "clause": "APH 1.9",
    },
    "REGULATION_BUREAU_OBSERVATIONS": {
        "label": "Regulation Bureau observations",
        "stage": "COMMITTEE_REVIEW",
        "terminal": False,
        "clause": "APH 1.10",
    },
    "SHC_HEARING": {
        "label": "Standing Hearing Committee",
        "stage": "COMMITTEE_REVIEW",
        "terminal": False,
        "clause": "APH 2.23.3",
    },
    "EC_DECISION": {
        "label": "Executive Committee decision",
        "stage": "DECISION",
        "terminal": False,
        "clause": "APH 1.10a",
    },
    "COUNCIL_RATIFICATION": {
        "label": "Council ratification",
        "stage": "DECISION",
        "terminal": False,
        "clause": "APH 2.25a",
    },
    "LOA_ISSUED": {
        "label": "Letter of Approval recorded",
        "stage": "DECISION",
        "terminal": False,
        "clause": "APH 1.10a",
    },
    "LOD_ISSUED": {
        "label": "Letter of Deficiency recorded",
        "stage": "DECISION",
        "terminal": False,
        "clause": "APH 2.23.3",
    },
    "LOR_ISSUED": {
        "label": "Letter of Rejection recorded with Speaking Order",
        "stage": "DECISION",
        "terminal": False,
        "clause": "APH 1.10",
    },
    "APPEAL_WINDOW": {
        "label": "Seven-day appeal window (SAC)",
        "stage": "DECISION",
        "terminal": False,
        "clause": "APH 1.11a",
    },
    "SAC_REVIEW": {
        "label": "Standing Appellate Committee",
        "stage": "COMMITTEE_REVIEW",
        "terminal": False,
        "clause": "APH 1.11c",
    },
    "COUNCIL_FINAL": {
        "label": "Council final decision",
        "stage": "DECISION",
        "terminal": False,
        "clause": "APH 1.11e",
    },
    "REGIONAL_ENDORSEMENT": {
        "label": "Regional Officer endorsement",
        "stage": "COMMITTEE_REVIEW",
        "terminal": False,
        "clause": "APH 1.11e",
    },
    "FINAL_LOA": {
        "label": "Final Letter of Approval",
        "stage": "COMPLETED",
        "terminal": False,
        "clause": "APH 1.10b",
    },
    "FINAL_LOR": {
        "label": "Final Letter of Rejection",
        "stage": "COMPLETED",
        "terminal": True,
        "clause": "APH 1.11e",
    },
    "FINAL_LOD": {
        "label": "Final Letter of Deficiency",
        "stage": "COMPLETED",
        "terminal": True,
        "clause": "APH 1.11e",
    },
    "WITHDRAWN": {
        "label": "Withdrawn",
        "stage": "COMPLETED",
        "terminal": True,
        "clause": "APH 2.3.3f-g",
    },
    "SECURITY_DEPOSIT_PENDING": {
        "label": "Security Deposit pending",
        "stage": "DECISION",
        "terminal": False,
        "clause": "APH 2.25f",
    },
    "ACTIVE_LOA": {
        "label": "Active LoA",
        "stage": "COMPLETED",
        "terminal": True,
        "clause": "APH 1.10b",
    },
    "CANCELLED": {
        "label": "Approval cancelled",
        "stage": "COMPLETED",
        "terminal": True,
        "clause": "APH 1.10b",
    },
    "SELF_DISCLOSURE_CHECK": {
        "label": "Self-disclosure check",
        "stage": "SCRUTINY",
        "terminal": False,
        "clause": "APH 2.3.5a",
    },
    "RANDOM_EVC": {
        "label": "Random Expert Visit Committee",
        "stage": "INSPECTION",
        "terminal": False,
        "clause": "APH 2.3.5a",
    },
    "COMPLIANCE_WINDOW": {
        "label": "Compliance window",
        "stage": "DEFICIENCY",
        "terminal": False,
        "clause": "APH 2.4",
    },
    "EC_LISTING": {
        "label": "Listed before the Executive Committee",
        "stage": "DECISION",
        "terminal": False,
        "clause": "APH 2.25",
    },
    "EOA_ISSUED": {
        "label": "Extension of Approval recorded",
        "stage": "DECISION",
        "terminal": False,
        "clause": "APH 2.25",
    },
    "ACTIVE_EOA": {
        "label": "Active EoA",
        "stage": "COMPLETED",
        "terminal": True,
        "clause": "APH 2.25",
    },
    "SPEAKING_ORDER": {
        "label": "Speaking Order",
        "stage": "DECISION",
        "terminal": False,
        "clause": "APH 2.24a",
    },
}

# ---------------------------------------------------------------------------
# Transition helpers
# ---------------------------------------------------------------------------

T = dict[str, Any]


def _edge(
    action: str,
    from_state: str,
    to_state: str,
    roles: list[str],
    *,
    label: str,
    description: str,
    clause: str,
    guards: list[str] | None = None,
    effects: list[str] | None = None,
    requires: str = "none",
    tone: str = "secondary",
    sla_stage: str | None = None,
    priority: int = 0,
) -> T:
    return {
        "action": action,
        "from_state": from_state,
        "to_state": to_state,
        "allowed_roles": roles,
        "guard_expr": guards or [],
        "side_effects": effects or [],
        "requires": requires,
        "tone": tone,
        "sla_stage": sla_stage or STATE_META[to_state]["stage"],
        "priority": priority,
        "label": label,
        "description": description,
        "apH_clause": clause,
        "needs_verification": False,
    }


_WITHDRAWABLE = (
    "SUBMITTED",
    "SCRUTINY",
    "DEFICIENCY_COMMUNICATED",
    "INSTITUTION_COMPLIANCE",
    "RE_SCRUTINY",
    "EVC_CONSTITUTED",
    "EVC_DONE",
    "REGULATION_BUREAU_OBSERVATIONS",
    "SHC_HEARING",
    "EC_DECISION",
    "EC_LISTING",
    "LOA_ISSUED",
    "LOD_ISSUED",
    "LOR_ISSUED",
    "APPEAL_WINDOW",
    "SAC_REVIEW",
    "SECURITY_DEPOSIT_PENDING",
)


def _withdraw_edges() -> list[T]:
    """Withdrawal is an overlay, but the state machine records one edge per state."""
    return [
        _edge(
            "withdraw_application",
            state,
            "WITHDRAWN",
            ["INSTITUTION_ADMIN"],
            label="Withdraw application",
            description="Withdraw without discarding the workflow history.",
            clause="APH 2.3.3f-g",
            effects=["withdraw_application"],
            tone="danger",
            sla_stage="COMPLETED",
        )
        for state in _WITHDRAWABLE
    ]


def _reopen_edges() -> list[T]:
    return [
        _edge(
            "reopen_once",
            state,
            "DRAFT",
            ["REGULATION_BUREAU_OFFICER"],
            label="Reopen a wrongly submitted application (once)",
            description=(
                "Reopen once, after a fresh TER and late penalty, so the institution "
                "can correct the data (APH 2.3.3d-e)."
            ),
            clause="APH 2.3.3d-e",
            guards=["reopen_available"],
            effects=["reopen_once"],
            tone="danger",
            sla_stage="APPLICATION",
        )
        for state in ("SUBMITTED", "SCRUTINY", "DEFICIENCY_COMMUNICATED")
    ]


def _appeal_chain(send_back_state: str = "EVC_CONSTITUTED") -> list[T]:
    """Appeal -> SAC -> optional single send-back -> Council -> endorsement.

    ``send_back_state`` is the state the SAC returns the case to. Track A and C
    return to the EVC (or Re-Scrutiny); Track B returns to the self-disclosure
    check; Track D returns to scrutiny.
    """
    return [
        _edge(
            "file_appeal",
            "APPEAL_WINDOW",
            "SAC_REVIEW",
            ["INSTITUTION_ADMIN"],
            label="File appeal with the SAC",
            description="One appeal only, within the configured seven-day window.",
            clause="APH 1.11a",
            guards=["within_appeal_window", "no_prior_appeal"],
            effects=["file_appeal"],
            tone="primary",
        ),
        _edge(
            "finalize_no_appeal",
            "APPEAL_WINDOW",
            "FINAL_LOA",
            ["REGULATION_BUREAU_OFFICER"],
            label="Finalise without appeal (LoA)",
            description="If no appeal is filed, the decision becomes final automatically.",
            clause="APH 1.11a",
            guards=["appeal_window_closed", "appeal_letter_loa"],
            effects=["finalize_no_appeal"],
            priority=0,
        ),
        _edge(
            "finalize_no_appeal",
            "APPEAL_WINDOW",
            "FINAL_LOD",
            ["REGULATION_BUREAU_OFFICER"],
            label="Finalise without appeal (LoD)",
            description="A deficiency decision becomes final after the appeal window.",
            clause="APH 1.11a",
            guards=["appeal_window_closed", "appeal_letter_lod"],
            effects=["finalize_no_appeal"],
            priority=1,
        ),
        _edge(
            "finalize_no_appeal",
            "APPEAL_WINDOW",
            "FINAL_LOR",
            ["REGULATION_BUREAU_OFFICER"],
            label="Finalise without appeal (LoR)",
            description="If no appeal is filed, the decision becomes final automatically.",
            clause="APH 1.11a",
            guards=["appeal_window_closed", "appeal_letter_lor"],
            effects=["finalize_no_appeal"],
            tone="danger",
            priority=2,
        ),
        _edge(
            "send_back",
            "SAC_REVIEW",
            send_back_state,
            ["SAC_MEMBER"],
            label="Send the case back once",
            description=(
                "The SAC may send the case back once; a second send-back is not "
                "allowed (Annexure-7)."
            ),
            clause="APH 1.11c",
            guards=["appeal_loop_available"],
            effects=["send_back"],
        ),
        _edge(
            "sac_recommend",
            "SAC_REVIEW",
            "COUNCIL_FINAL",
            ["SAC_MEMBER"],
            label="Record the SAC recommendation",
            description="The SAC recommends; the Council records the final decision.",
            clause="APH 1.11d",
            effects=["sac_recommend"],
            tone="primary",
        ),
        _edge(
            "council_final",
            "COUNCIL_FINAL",
            "REGIONAL_ENDORSEMENT",
            ["EXECUTIVE_COMMITTEE_MEMBER"],
            label="Record the Council's final decision",
            description=(
                "The Council decision is final. The EC member records it in the Council "
                "secretariat capacity; the super admin only ratifies EC decisions."
            ),
            clause="APH 1.11e",
            effects=["council_final"],
            tone="primary",
        ),
        _edge(
            "endorse_decision",
            "REGIONAL_ENDORSEMENT",
            "FINAL_LOA",
            ["REGIONAL_OFFICER"],
            label="Endorse the final approval",
            description="The Regional Officer endorses; they do not approve or reject.",
            clause="APH 1.11e",
            guards=["final_outcome_loa"],
            effects=["endorse_decision"],
            tone="primary",
        ),
        _edge(
            "endorse_decision",
            "REGIONAL_ENDORSEMENT",
            "FINAL_LOD",
            ["REGIONAL_OFFICER"],
            label="Endorse the final deficiency letter",
            description="The Regional Officer endorses; they do not approve or reject.",
            clause="APH 1.11e",
            guards=["final_outcome_lod"],
            effects=["endorse_decision"],
            priority=1,
        ),
        _edge(
            "endorse_decision",
            "REGIONAL_ENDORSEMENT",
            "FINAL_LOR",
            ["REGIONAL_OFFICER"],
            label="Endorse the final rejection",
            description="The Regional Officer endorses; they do not approve or reject.",
            clause="APH 1.11e",
            guards=["final_outcome_lor"],
            effects=["endorse_decision"],
            tone="danger",
            priority=2,
        ),
    ]


def _second_review_edge(
    letter_state: str,
    letter_action: str,
    label: str,
    clause: str,
    *,
    tone: str = "danger",
) -> T:
    """Return the re-examined letter edge that goes straight back to the SAC.

    An institution may appeal only once. When the SAC has already sent the case
    back, the decision recorded after re-examination is published as a new
    letter and handed to the SAC for its final recommendation instead of
    opening a second appeal window (APH 1.11a, Annexure-7).
    """
    guards = ["has_prior_appeal"]
    if letter_action == "issue_lor":
        guards.append("speaking_order_present")
    return _edge(
        letter_action,
        letter_state,
        "SAC_REVIEW",
        ["EXECUTIVE_COMMITTEE_MEMBER"],
        label=label,
        description=(
            "The institution already used its single appeal, so the re-examined "
            "decision returns to the SAC for its final recommendation."
        ),
        clause=clause,
        guards=guards,
        effects=[letter_action],
        tone=tone,
        priority=1,
    )


def _security_deposit_edges() -> list[T]:
    return [
        _edge(
            "pay_security_deposit",
            "SECURITY_DEPOSIT_PENDING",
            "ACTIVE_LOA",
            ["INSTITUTION_ADMIN"],
            label="Pay Security Deposit and file Affidavit 3",
            description=(
                "Proof and Affidavit 3 are due within 15 days; the deposit is 10% "
                "penalised to 31 May and 20% to 31 July."
            ),
            clause="APH 2.25f",
            guards=["deposit_payable"],
            effects=["pay_security_deposit"],
            tone="primary",
        ),
        _edge(
            "apply_deposit_penalty",
            "SECURITY_DEPOSIT_PENDING",
            "SECURITY_DEPOSIT_PENDING",
            ["REGULATION_BUREAU_OFFICER"],
            label="Apply the Security Deposit penalty",
            description="Scheduler action: 10% to 31 May, 20% to 31 July.",
            clause="APH 2.25f",
            guards=["deposit_penalty_due"],
            effects=["apply_deposit_penalty"],
            sla_stage="DECISION",
        ),
        _edge(
            "apply_deposit_penalty",
            "SECURITY_DEPOSIT_PENDING",
            "WITHDRAWN",
            ["REGULATION_BUREAU_OFFICER"],
            label="Withdraw approval after the final deposit date",
            description="After 31 July the approval may be withdrawn (APH 2.25f).",
            clause="APH 2.25f",
            guards=["deposit_forfeited"],
            effects=["forfeit_deposit"],
            tone="danger",
            sla_stage="COMPLETED",
            priority=1,
        ),
        _edge(
            "expire_loa",
            "ACTIVE_LOA",
            "CANCELLED",
            ["REGULATION_BUREAU_OFFICER"],
            label="Cancel the LoA after two academic years",
            description="An LoA is valid for two academic years; the next year is EoA.",
            clause="APH 1.10b",
            guards=["loa_expired"],
            effects=["expire_loa"],
            tone="danger",
            sla_stage="COMPLETED",
        ),
    ]


# ---------------------------------------------------------------------------
# Track A - Chapter I / extension of approval
# ---------------------------------------------------------------------------

TRACK_A_TRANSITIONS: list[T] = [
    _edge(
        "submit",
        "DRAFT",
        "SUBMITTED",
        ["INSTITUTION_ADMIN"],
        label="Submit application",
        description="TER paid, data locked and a portal number issued (APH 1.4.3).",
        clause="APH 1.4.3",
        effects=["submit", "assign_scrutiny"],
        tone="primary",
    ),
    _edge(
        "pay_ter",
        "DRAFT",
        "DRAFT",
        ["INSTITUTION_ADMIN"],
        label="Confirm TER payment",
        description="Verify that the computed TER has been paid before submission.",
        clause="APH 1.4.2h",
        effects=["pay_ter"],
        sla_stage="APPLICATION",
    ),
    _edge(
        "assign_scrutiny",
        "SUBMITTED",
        "SCRUTINY",
        ["REGULATION_BUREAU_OFFICER"],
        label="Assign the Scrutiny Committee",
        description="Regulation Bureau assigns a scrutiny member and opens scrutiny.",
        clause="APH 1.8a",
        effects=["assign_scrutiny"],
        tone="primary",
    ),
    _edge(
        "communicate_deficiency",
        "SCRUTINY",
        "DEFICIENCY_COMMUNICATED",
        ["SCRUTINY_COMMITTEE_MEMBER"],
        label="Communicate deficiencies (LoD)",
        description="Issue the Deficiency Report and pause the application.",
        clause="APH 2.3.3b",
        guards=["has_deficiencies"],
        effects=["create_deficiencies"],
        requires="deficiencies",
        tone="primary",
    ),
    _edge(
        "scrutiny_recommend",
        "SCRUTINY",
        "EVC_CONSTITUTED",
        ["SCRUTINY_COMMITTEE_MEMBER"],
        label="Recommend an Expert Visit Committee",
        description="Scrutiny is clear; the Regional Officer constitutes the EVC.",
        clause="APH 1.9a",
        guards=["route_requires_evc", "no_open_deficiencies"],
        effects=["constitute_evc"],
        tone="primary",
        priority=0,
    ),
    _edge(
        "scrutiny_recommend",
        "SCRUTINY",
        "REGULATION_BUREAU_OBSERVATIONS",
        ["SCRUTINY_COMMITTEE_MEMBER"],
        label="Clear scrutiny without an EVC",
        description="This route does not require an Expert Visit Committee.",
        clause="APH 1.8",
        guards=["route_not_requires_evc", "no_open_deficiencies"],
        effects=["scrutiny_recommend"],
        tone="primary",
        priority=1,
    ),
    _edge(
        "submit_compliance",
        "DEFICIENCY_COMMUNICATED",
        "INSTITUTION_COMPLIANCE",
        ["INSTITUTION_ADMIN"],
        label="Submit compliance",
        description="Respond to every open deficiency with evidence.",
        clause="APH 2.4",
        guards=["open_deficiencies", "documents_reuploaded"],
        effects=["record_responses"],
        requires="responses",
        tone="primary",
    ),
    _edge(
        "re_scrutiny_verify",
        "INSTITUTION_COMPLIANCE",
        "RE_SCRUTINY",
        ["SCRUTINY_COMMITTEE_MEMBER"],
        label="Verify the listed deficiencies",
        description="Re-Scrutiny checks only the deficiencies that were communicated.",
        clause="APH 1.8",
        guards=["responded_deficiencies"],
        effects=["verify_deficiencies"],
        requires="deficiency_id",
        tone="primary",
    ),
    _edge(
        "re_scrutiny_verify",
        "RE_SCRUTINY",
        "RE_SCRUTINY",
        ["SCRUTINY_COMMITTEE_MEMBER"],
        label="Verify another listed deficiency",
        description="Remaining deficiencies are verified one by one in Re-Scrutiny.",
        clause="APH 1.8",
        guards=["responded_deficiencies"],
        effects=["verify_deficiencies"],
        requires="deficiency_id",
        sla_stage="SCRUTINY",
    ),
    _edge(
        "scrutiny_recommend",
        "RE_SCRUTINY",
        "EVC_CONSTITUTED",
        ["SCRUTINY_COMMITTEE_MEMBER"],
        label="Close Re-Scrutiny and constitute the EVC",
        description="All deficiencies are closed; the file moves to the EVC.",
        clause="APH 1.9a",
        guards=["route_requires_evc", "no_open_deficiencies"],
        effects=["constitute_evc"],
        tone="primary",
        priority=0,
    ),
    _edge(
        "scrutiny_recommend",
        "RE_SCRUTINY",
        "REGULATION_BUREAU_OBSERVATIONS",
        ["SCRUTINY_COMMITTEE_MEMBER"],
        label="Close Re-Scrutiny without an EVC",
        description="All deficiencies are closed; this route has no EVC.",
        clause="APH 1.8",
        guards=["route_not_requires_evc", "no_open_deficiencies"],
        effects=["scrutiny_recommend"],
        tone="primary",
        priority=1,
    ),
    _edge(
        "submit_evc_video",
        "EVC_CONSTITUTED",
        "EVC_CONSTITUTED",
        ["EVC_MEMBER"],
        label="Upload the EVC video",
        description="The visit video must be at least 30 minutes long (APH 1.9f-g).",
        clause="APH 1.9f-g",
        guards=["is_evc_member"],
        effects=["submit_evc_video"],
        requires="video",
    ),
    _edge(
        "evc_report",
        "EVC_CONSTITUTED",
        "EVC_DONE",
        ["EVC_MEMBER"],
        label="Submit the EVC report",
        description="Record findings only after the 30-minute video is uploaded.",
        clause="APH 1.9",
        guards=["is_evc_member", "video_uploaded"],
        effects=["evc_report"],
        requires="inspection_report",
        tone="primary",
    ),
    _edge(
        "observations",
        "EVC_DONE",
        "REGULATION_BUREAU_OBSERVATIONS",
        ["REGULATION_BUREAU_OFFICER"],
        label="Place Regulation Bureau observations",
        description="The Bureau places observations before the EC.",
        clause="APH 1.10",
        effects=["observations"],
        tone="primary",
    ),
    _edge(
        "list_for_ec",
        "REGULATION_BUREAU_OBSERVATIONS",
        "EC_DECISION",
        ["REGULATION_BUREAU_OFFICER"],
        label="List before the Executive Committee",
        description="The case is placed on the EC agenda.",
        clause="APH 1.10a",
        effects=["list_for_ec"],
        tone="primary",
    ),
    _edge(
        "ec_decide",
        "EC_DECISION",
        "LOA_ISSUED",
        ["EXECUTIVE_COMMITTEE_MEMBER"],
        label="Decide to approve (LoA)",
        description="The EC records an approval decision; no conditional approval exists.",
        clause="APH 1.10a",
        guards=["decision_loa", "ec_quorum_met"],
        effects=["ec_decide_loa"],
        requires="decision",
        tone="primary",
        priority=0,
    ),
    _edge(
        "ec_decide",
        "EC_DECISION",
        "LOD_ISSUED",
        ["EXECUTIVE_COMMITTEE_MEMBER"],
        label="Decide a Letter of Deficiency",
        description="The EC records deficiencies rather than rejecting outright.",
        clause="APH 2.23.3",
        guards=["decision_lod", "ec_quorum_met"],
        effects=["ec_decide_lod"],
        requires="decision",
        priority=1,
    ),
    _edge(
        "ec_decide",
        "EC_DECISION",
        "LOR_ISSUED",
        ["EXECUTIVE_COMMITTEE_MEMBER"],
        label="Decide to reject (LoR)",
        description="The EC records a rejection with a Speaking Order.",
        clause="APH 1.10",
        guards=["decision_lor", "ec_quorum_met", "speaking_order_present"],
        effects=["ec_decide_lor"],
        requires="decision",
        tone="danger",
        priority=2,
    ),
    _edge(
        "council_ratification",
        "EC_DECISION",
        "COUNCIL_RATIFICATION",
        ["SUPER_ADMIN"],
        label="Ratify the EC decision (Council secretariat)",
        description=(
            "Ratification requires an EC decision with a met quorum. The super admin "
            "has no operational approval or rejection power."
        ),
        clause="APH 2.25a",
        guards=["ec_decision_quorum_met"],
        effects=["council_ratification"],
    ),
    _edge(
        "issue_loa",
        "LOA_ISSUED",
        "SECURITY_DEPOSIT_PENDING",
        ["EXECUTIVE_COMMITTEE_MEMBER"],
        label="Issue the Letter of Approval",
        description="Issue the LoA and start the 15-day Security Deposit clock.",
        clause="APH 1.10a",
        effects=["issue_loa"],
        tone="primary",
    ),
    _edge(
        "issue_lod",
        "LOD_ISSUED",
        "APPEAL_WINDOW",
        ["EXECUTIVE_COMMITTEE_MEMBER"],
        label="Issue the Letter of Deficiency",
        description="Issue the LoD and start the seven-day appeal clock.",
        clause="APH 1.11a",
        guards=["no_prior_appeal"],
        effects=["issue_lod"],
    ),
    _second_review_edge(
        "LOD_ISSUED",
        "issue_lod",
        "Issue the re-examined Letter of Deficiency",
        "APH 1.11a",
        tone="secondary",
    ),
    _edge(
        "issue_lor",
        "LOR_ISSUED",
        "APPEAL_WINDOW",
        ["EXECUTIVE_COMMITTEE_MEMBER"],
        label="Issue the Speaking Order (LoR)",
        description="Issue the LoR with the Speaking Order and appeal deadline.",
        clause="APH 1.10",
        guards=["no_prior_appeal", "speaking_order_present"],
        effects=["issue_lor"],
        tone="danger",
    ),
    _second_review_edge(
        "LOR_ISSUED",
        "issue_lor",
        "Issue the re-examined Speaking Order",
        "APH 1.10",
    ),
    _edge(
        "ec_decide",
        "COUNCIL_RATIFICATION",
        "LOA_ISSUED",
        ["EXECUTIVE_COMMITTEE_MEMBER"],
        label="Record the ratified approval",
        description="The EC records the ratified decision without a second vote.",
        clause="APH 2.25a",
        guards=["ratified_outcome_loa"],
        effects=["confirm_loa"],
        priority=0,
    ),
    _edge(
        "ec_decide",
        "COUNCIL_RATIFICATION",
        "LOD_ISSUED",
        ["EXECUTIVE_COMMITTEE_MEMBER"],
        label="Record the ratified deficiency letter",
        description="The EC records the ratified deficiency decision.",
        clause="APH 2.25a",
        guards=["ratified_outcome_lod"],
        effects=["confirm_lod"],
        priority=1,
    ),
    _edge(
        "ec_decide",
        "COUNCIL_RATIFICATION",
        "LOR_ISSUED",
        ["EXECUTIVE_COMMITTEE_MEMBER"],
        label="Record the ratified rejection",
        description="The EC records the ratified rejection.",
        clause="APH 2.25a",
        guards=["ratified_outcome_lor"],
        effects=["confirm_lor"],
        tone="danger",
        priority=2,
    ),
    _edge(
        "issue_loa",
        "FINAL_LOA",
        "SECURITY_DEPOSIT_PENDING",
        ["EXECUTIVE_COMMITTEE_MEMBER"],
        label="Issue the final Letter of Approval",
        description="The final LoA starts the Security Deposit clock.",
        clause="APH 1.10b",
        effects=["issue_loa"],
        tone="primary",
    ),
    *_appeal_chain(),
    *_security_deposit_edges(),
    *_reopen_edges(),
    *_withdraw_edges(),
]

# ---------------------------------------------------------------------------
# Track B - EoA by self-disclosure (and NRI seats)
# ---------------------------------------------------------------------------

TRACK_B_TRANSITIONS: list[T] = [
    _edge(
        "submit",
        "DRAFT",
        "SUBMITTED",
        ["INSTITUTION_ADMIN"],
        label="Submit application",
        description="TER paid, data locked and a portal number issued.",
        clause="APH 1.4.3",
        effects=["submit", "assign_scrutiny"],
        tone="primary",
    ),
    _edge(
        "pay_ter",
        "DRAFT",
        "DRAFT",
        ["INSTITUTION_ADMIN"],
        label="Confirm TER payment",
        description="No EoA can be processed before the TER is paid.",
        clause="APH 1.4.2h",
        effects=["pay_ter"],
        sla_stage="APPLICATION",
    ),
    _edge(
        "run_self_disclosure_check",
        "SUBMITTED",
        "SELF_DISCLOSURE_CHECK",
        ["REGULATION_BUREAU_OFFICER"],
        label="Run the self-disclosure check",
        description=(
            "Generate the automatic Deficiency Report; a Nil Deficiency declaration "
            "is required before the EC can list the case."
        ),
        clause="APH 2.3.5a",
        effects=["run_self_disclosure_check"],
        tone="primary",
    ),
    _edge(
        "communicate_deficiency",
        "SELF_DISCLOSURE_CHECK",
        "COMPLIANCE_WINDOW",
        ["REGULATION_BUREAU_OFFICER"],
        label="Communicate the Deficiency Report",
        description="Open the compliance window for every deficiency found.",
        clause="APH 2.4",
        guards=["open_deficiencies"],
        effects=["communicate_deficiency"],
        tone="primary",
    ),
    _edge(
        "submit_compliance",
        "COMPLIANCE_WINDOW",
        "SELF_DISCLOSURE_CHECK",
        ["INSTITUTION_ADMIN"],
        label="Submit compliance evidence",
        description="Respond to every open deficiency; the Bureau re-runs the check.",
        clause="APH 2.4",
        guards=["open_deficiencies", "documents_reuploaded"],
        effects=["record_responses"],
        requires="responses",
        tone="primary",
    ),
    _edge(
        "re_scrutiny_verify",
        "SELF_DISCLOSURE_CHECK",
        "SELF_DISCLOSURE_CHECK",
        ["REGULATION_BUREAU_OFFICER"],
        label="Verify a responded deficiency",
        description=(
            "The Bureau verifies each responded self-disclosure deficiency before the "
            "case can be cleared (APH 1.8, 2.4)."
        ),
        clause="APH 2.4",
        guards=["responded_deficiencies"],
        effects=["verify_deficiencies"],
        requires="deficiency_id",
        tone="primary",
    ),
    _edge(
        "scrutiny_recommend",
        "SELF_DISCLOSURE_CHECK",
        "RANDOM_EVC",
        ["REGULATION_BUREAU_OFFICER"],
        label="Select a random EVC",
        description="A configurable percentage of self-disclosure cases get a random EVC.",
        clause="APH 2.3.5a",
        guards=["no_open_deficiencies", "random_evc_selected"],
        effects=["record_random_evc"],
        tone="primary",
        priority=0,
    ),
    _edge(
        "scrutiny_recommend",
        "SELF_DISCLOSURE_CHECK",
        "EC_LISTING",
        ["REGULATION_BUREAU_OFFICER"],
        label="Clear the self-disclosure check",
        description="Nil Deficiency or all deficiencies closed; list before the EC.",
        clause="APH 2.3.5a",
        guards=["no_open_deficiencies", "random_evc_not_selected"],
        effects=["list_for_ec"],
        tone="primary",
        priority=1,
    ),
    _edge(
        "evc_report",
        "RANDOM_EVC",
        "EC_LISTING",
        ["EVC_MEMBER"],
        label="Submit the random EVC report",
        description="Record the visit findings and list the case before the EC.",
        clause="APH 2.3.5a",
        effects=["evc_report", "list_for_ec"],
        requires="inspection_report",
        tone="primary",
    ),
    _edge(
        "list_for_ec",
        "EC_LISTING",
        "EC_DECISION",
        ["REGULATION_BUREAU_OFFICER"],
        label="List before the Executive Committee",
        description="The consolidated list records the Approved Intake.",
        clause="APH 2.25",
        effects=["list_for_ec"],
        tone="primary",
    ),
    _edge(
        "ec_decide",
        "EC_DECISION",
        "EOA_ISSUED",
        ["EXECUTIVE_COMMITTEE_MEMBER"],
        label="Decide to extend approval (EoA)",
        description=(
            "EoA requires the last-date check, no pending investigation and three "
            "core branches for Engineering & Technology."
        ),
        clause="APH 2.25j",
        guards=[
            "decision_eoa",
            "eoa_before_last_date",
            "no_pending_investigation",
            "core_branches_ok",
            "ec_quorum_met",
        ],
        effects=["ec_decide_eoa"],
        requires="decision",
        tone="primary",
        priority=0,
    ),
    _edge(
        "ec_decide",
        "EC_DECISION",
        "SPEAKING_ORDER",
        ["EXECUTIVE_COMMITTEE_MEMBER"],
        label="Decide to reject with a Speaking Order",
        description="The EC records a rejection with reasons.",
        clause="APH 2.24a",
        guards=["decision_lor", "speaking_order_present", "ec_quorum_met"],
        effects=["ec_decide_lor"],
        requires="decision",
        tone="danger",
        priority=1,
    ),
    _edge(
        "issue_eoa",
        "EOA_ISSUED",
        "ACTIVE_EOA",
        ["EXECUTIVE_COMMITTEE_MEMBER"],
        label="Issue the Extension of Approval",
        description="Publish the EoA letter and mark the approval active.",
        clause="APH 2.25",
        effects=["issue_eoa"],
        tone="primary",
    ),
    _edge(
        "issue_lor",
        "SPEAKING_ORDER",
        "APPEAL_WINDOW",
        ["EXECUTIVE_COMMITTEE_MEMBER"],
        label="Issue the Speaking Order",
        description="Publish the LoR and start the seven-day appeal clock.",
        clause="APH 2.24a",
        guards=["no_prior_appeal", "speaking_order_present"],
        effects=["issue_lor"],
        tone="danger",
    ),
    _second_review_edge(
        "SPEAKING_ORDER",
        "issue_lor",
        "Issue the re-examined Speaking Order",
        "APH 2.24a",
    ),
    _edge(
        "issue_eoa",
        "FINAL_LOA",
        "ACTIVE_EOA",
        ["EXECUTIVE_COMMITTEE_MEMBER"],
        label="Issue the final approval after appeal",
        description="The Council decision is final; publish the EoA letter.",
        clause="APH 1.11e",
        effects=["issue_eoa"],
        tone="primary",
    ),
    *_appeal_chain("SELF_DISCLOSURE_CHECK"),
    *_reopen_edges(),
    *_withdraw_edges(),
]

# ---------------------------------------------------------------------------
# Track C - existing institution changes (shared Track A edges)
# ---------------------------------------------------------------------------

_TRACK_C_KEEP = {
    "submit",
    "pay_ter",
    "assign_scrutiny",
    "communicate_deficiency",
    "scrutiny_recommend",
    "submit_compliance",
    "re_scrutiny_verify",
    "submit_evc_video",
    "evc_report",
    "observations",
    "list_for_ec",
    "ec_decide",
}

TRACK_C_TRANSITIONS: list[T] = [
    edge
    for edge in TRACK_A_TRANSITIONS
    if edge["action"] in _TRACK_C_KEEP
    and edge["from_state"]
    in {
        "DRAFT",
        "SUBMITTED",
        "SCRUTINY",
        "DEFICIENCY_COMMUNICATED",
        "INSTITUTION_COMPLIANCE",
        "RE_SCRUTINY",
        "EVC_CONSTITUTED",
        "EVC_DONE",
        "REGULATION_BUREAU_OBSERVATIONS",
        "EC_DECISION",
    }
    and edge["to_state"]
    not in {
        "LOA_ISSUED",
        "LOD_ISSUED",
        "LOR_ISSUED",
        "SECURITY_DEPOSIT_PENDING",
        "EC_LISTING",
    }
]

TRACK_C_TRANSITIONS += [
    _edge(
        "shc_hearing",
        "REGULATION_BUREAU_OBSERVATIONS",
        "SHC_HEARING",
        ["SHC_MEMBER"],
        label="Hold the SHC compliance hearing",
        description="A single hearing stage with a recorded outcome (APH 2.23.3).",
        clause="APH 2.23.3",
        guards=["route_requires_hearing"],
        effects=["shc_hearing"],
        requires="shc_outcome",
        tone="primary",
    ),
    _edge(
        "list_for_ec",
        "REGULATION_BUREAU_OBSERVATIONS",
        "EC_LISTING",
        ["REGULATION_BUREAU_OFFICER"],
        label="List before the EC without an SHC",
        description="This route does not require a Standing Hearing Committee.",
        clause="APH 1.10a",
        guards=["route_not_requires_hearing"],
        effects=["list_for_ec"],
        tone="primary",
        priority=1,
    ),
    _edge(
        "list_for_ec",
        "SHC_HEARING",
        "EC_LISTING",
        ["SHC_MEMBER"],
        label="List before the EC after the SHC",
        description="The SHC outcome is placed before the Executive Committee.",
        clause="APH 2.23.3",
        effects=["list_for_ec"],
        tone="primary",
    ),
    _edge(
        "list_for_ec",
        "EC_LISTING",
        "EC_DECISION",
        ["REGULATION_BUREAU_OFFICER"],
        label="List before the Executive Committee",
        description="The consolidated list records the Approved Intake.",
        clause="APH 2.25",
        effects=["list_for_ec"],
        tone="primary",
    ),
    _edge(
        "ec_decide",
        "EC_DECISION",
        "EOA_ISSUED",
        ["EXECUTIVE_COMMITTEE_MEMBER"],
        label="Decide to grant an EoA",
        description="Existing-institution change approved subject to both checks.",
        clause="APH 2.6e",
        guards=[
            "decision_eoa",
            "core_branches_ok",
            "eoa_before_last_date",
            "no_pending_investigation",
            "ec_quorum_met",
        ],
        effects=["ec_decide_eoa"],
        requires="decision",
        tone="primary",
        priority=0,
    ),
    _edge(
        "ec_decide",
        "EC_DECISION",
        "SPEAKING_ORDER",
        ["EXECUTIVE_COMMITTEE_MEMBER"],
        label="Reject with a Speaking Order",
        description="Record the rejection with reasons and an appeal clock.",
        clause="APH 2.24a",
        guards=["decision_lor", "speaking_order_present", "ec_quorum_met"],
        effects=["ec_decide_lor"],
        requires="decision",
        tone="danger",
        priority=1,
    ),
    _edge(
        "issue_eoa",
        "EOA_ISSUED",
        "ACTIVE_EOA",
        ["EXECUTIVE_COMMITTEE_MEMBER"],
        label="Issue the EoA",
        description="Publish the EoA letter.",
        clause="APH 2.25",
        effects=["issue_eoa"],
        tone="primary",
    ),
    _edge(
        "issue_lor",
        "SPEAKING_ORDER",
        "APPEAL_WINDOW",
        ["EXECUTIVE_COMMITTEE_MEMBER"],
        label="Issue the Speaking Order",
        description="Publish the LoR and start the appeal clock.",
        clause="APH 2.24a",
        guards=["no_prior_appeal", "speaking_order_present"],
        effects=["issue_lor"],
        tone="danger",
    ),
    _second_review_edge(
        "SPEAKING_ORDER",
        "issue_lor",
        "Issue the re-examined Speaking Order",
        "APH 2.24a",
    ),
    _edge(
        "issue_eoa",
        "FINAL_LOA",
        "ACTIVE_EOA",
        ["EXECUTIVE_COMMITTEE_MEMBER"],
        label="Issue the final approval after appeal",
        description="Publish the EoA letter after the Council decision.",
        clause="APH 1.11e",
        effects=["issue_eoa"],
        tone="primary",
    ),
    *_appeal_chain("EVC_CONSTITUTED"),
    *_reopen_edges(),
    *_withdraw_edges(),
]

# ---------------------------------------------------------------------------
# Track D - year-round scrutiny-only changes
# ---------------------------------------------------------------------------

TRACK_D_TRANSITIONS: list[T] = [
    _edge(
        "submit",
        "DRAFT",
        "SUBMITTED",
        ["INSTITUTION_ADMIN"],
        label="Submit application",
        description="Year-round application; TER rules come from the route row.",
        clause="APH 1.4.3",
        effects=["submit", "assign_scrutiny"],
        tone="primary",
    ),
    _edge(
        "pay_ter",
        "DRAFT",
        "DRAFT",
        ["INSTITUTION_ADMIN"],
        label="Confirm TER payment",
        description="Some year-round types are exempt from TER.",
        clause="APH 1.4.2h",
        effects=["pay_ter"],
        sla_stage="APPLICATION",
    ),
    _edge(
        "assign_scrutiny",
        "SUBMITTED",
        "SCRUTINY",
        ["REGULATION_BUREAU_OFFICER"],
        label="Assign scrutiny",
        description="Regulation Bureau opens scrutiny.",
        clause="APH 1.8a",
        effects=["assign_scrutiny"],
        tone="primary",
    ),
    _edge(
        "scrutiny_recommend",
        "SCRUTINY",
        "EC_LISTING",
        ["SCRUTINY_COMMITTEE_MEMBER"],
        label="Clear scrutiny and list before the EC",
        description="Year-round changes are scrutiny-only.",
        clause="APH 1.8",
        effects=["list_for_ec"],
        tone="primary",
    ),
    _edge(
        "list_for_ec",
        "EC_LISTING",
        "EC_DECISION",
        ["REGULATION_BUREAU_OFFICER"],
        label="List before the Executive Committee",
        description="The case is placed on the EC agenda.",
        clause="APH 1.10a",
        effects=["list_for_ec"],
        tone="primary",
    ),
    _edge(
        "ec_decide",
        "EC_DECISION",
        "EOA_ISSUED",
        ["EXECUTIVE_COMMITTEE_MEMBER"],
        label="Decide the year-round change",
        description=(
            "A failed closure still produces an EoA with zero intake (APH 2.3.3h). "
            "A pending court case or charge sheet blocks the change."
        ),
        clause="APH 2.3.3h",
        guards=[
            "decision_eoa",
            "closure_outcome_present",
            "eoa_before_last_date",
            "no_pending_investigation",
            "ec_quorum_met",
        ],
        effects=["ec_decide_eoa", "zero_intake_if_closure_failed"],
        requires="decision",
        tone="primary",
        priority=0,
    ),
    _edge(
        "ec_decide",
        "EC_DECISION",
        "SPEAKING_ORDER",
        ["EXECUTIVE_COMMITTEE_MEMBER"],
        label="Reject the change with a Speaking Order",
        description="Record the rejection with reasons.",
        clause="APH 2.24a",
        guards=["decision_lor", "speaking_order_present", "ec_quorum_met"],
        effects=["ec_decide_lor"],
        requires="decision",
        tone="danger",
        priority=1,
    ),
    _edge(
        "issue_eoa",
        "EOA_ISSUED",
        "ACTIVE_EOA",
        ["EXECUTIVE_COMMITTEE_MEMBER"],
        label="Issue the EoA",
        description="Publish the EoA letter.",
        clause="APH 2.25",
        effects=["issue_eoa"],
        tone="primary",
    ),
    _edge(
        "issue_lor",
        "SPEAKING_ORDER",
        "APPEAL_WINDOW",
        ["EXECUTIVE_COMMITTEE_MEMBER"],
        label="Issue the Speaking Order",
        description="Publish the LoR and start the appeal clock.",
        clause="APH 2.24a",
        guards=["no_prior_appeal", "speaking_order_present"],
        effects=["issue_lor"],
        tone="danger",
    ),
    _second_review_edge(
        "SPEAKING_ORDER",
        "issue_lor",
        "Issue the re-examined Speaking Order",
        "APH 2.24a",
    ),
    _edge(
        "issue_eoa",
        "FINAL_LOA",
        "ACTIVE_EOA",
        ["EXECUTIVE_COMMITTEE_MEMBER"],
        label="Issue the final approval after appeal",
        description="Publish the EoA letter after the Council decision.",
        clause="APH 1.11e",
        effects=["issue_eoa"],
        tone="primary",
    ),
    *_appeal_chain("SCRUTINY"),
    *_reopen_edges(),
    *_withdraw_edges(),
]

# ---------------------------------------------------------------------------
# Definitions
# ---------------------------------------------------------------------------

DEFINITIONS: list[dict[str, Any]] = [
    {
        "key": "TRACK_A",
        "label": "Track A - Chapter I approval and extension",
        "track": "TRACK_A",
        "description": (
            "New institution and extension-of-approval cycle: scrutiny, deficiency "
            "loop, EVC, EC decision, appeal, Council, endorsement, Security Deposit."
        ),
        "apH_clause": "APH 1.3-1.12",
        "needs_verification": False,
        "config": {"appeal_start_event": "DECISION_UPLOADED", "security_deposit": True},
        "states": [
            "DRAFT",
            "SUBMITTED",
            "SCRUTINY",
            "DEFICIENCY_COMMUNICATED",
            "INSTITUTION_COMPLIANCE",
            "RE_SCRUTINY",
            "EVC_CONSTITUTED",
            "EVC_DONE",
            "REGULATION_BUREAU_OBSERVATIONS",
            "EC_DECISION",
            "COUNCIL_RATIFICATION",
            "LOA_ISSUED",
            "LOD_ISSUED",
            "LOR_ISSUED",
            "APPEAL_WINDOW",
            "SAC_REVIEW",
            "COUNCIL_FINAL",
            "REGIONAL_ENDORSEMENT",
            "FINAL_LOA",
            "FINAL_LOD",
            "FINAL_LOR",
            "SECURITY_DEPOSIT_PENDING",
            "ACTIVE_LOA",
            "CANCELLED",
            "WITHDRAWN",
        ],
        "transitions": TRACK_A_TRANSITIONS,
    },
    {
        "key": "TRACK_B",
        "label": "Track B - EoA by self-disclosure",
        "track": "TRACK_B",
        "description": (
            "Existing institution: automatic self-disclosure Deficiency Report, "
            "optional random EVC, compliance window, EC listing and EoA."
        ),
        "apH_clause": "APH 2.3.5; 2.25",
        "needs_verification": False,
        "config": {
            "appeal_start_event": "DECISION_UPLOADED",
            "security_deposit": False,
            "random_evc_percent": 10,
            "core_branches_required": 3,
        },
        "states": [
            "DRAFT",
            "SUBMITTED",
            "SELF_DISCLOSURE_CHECK",
            "COMPLIANCE_WINDOW",
            "RANDOM_EVC",
            "EC_LISTING",
            "EC_DECISION",
            "EOA_ISSUED",
            "ACTIVE_EOA",
            "SPEAKING_ORDER",
            "APPEAL_WINDOW",
            "SAC_REVIEW",
            "COUNCIL_FINAL",
            "REGIONAL_ENDORSEMENT",
            "FINAL_LOA",
            "FINAL_LOD",
            "FINAL_LOR",
            "WITHDRAWN",
        ],
        "transitions": TRACK_B_TRANSITIONS,
    },
    {
        "key": "TRACK_C",
        "label": "Track C - existing institution changes",
        "track": "TRACK_C",
        "description": (
            "Chapter II changes: Track A scrutiny edges, optional EVC, one SHC "
            "compliance hearing, EC listing and EoA/Speaking Order."
        ),
        "apH_clause": "APH 2.3; 2.23.3",
        "needs_verification": False,
        "config": {"appeal_start_event": "DECISION_UPLOADED", "security_deposit": False},
        "states": [
            "DRAFT",
            "SUBMITTED",
            "SCRUTINY",
            "DEFICIENCY_COMMUNICATED",
            "INSTITUTION_COMPLIANCE",
            "RE_SCRUTINY",
            "EVC_CONSTITUTED",
            "EVC_DONE",
            "REGULATION_BUREAU_OBSERVATIONS",
            "SHC_HEARING",
            "EC_LISTING",
            "EC_DECISION",
            "EOA_ISSUED",
            "ACTIVE_EOA",
            "SPEAKING_ORDER",
            "APPEAL_WINDOW",
            "SAC_REVIEW",
            "COUNCIL_FINAL",
            "REGIONAL_ENDORSEMENT",
            "FINAL_LOA",
            "FINAL_LOD",
            "FINAL_LOR",
            "WITHDRAWN",
        ],
        "transitions": TRACK_C_TRANSITIONS,
    },
    {
        "key": "TRACK_D",
        "label": "Track D - year-round scrutiny-only changes",
        "track": "TRACK_D",
        "description": (
            "Closure, bank details, trust name and course changes: scrutiny, EC "
            "listing and decision. A failed closure gives an EoA with zero intake."
        ),
        "apH_clause": "APH 2.3.3h; 2.3.4",
        "needs_verification": False,
        "config": {"appeal_start_event": "DECISION_UPLOADED", "security_deposit": False},
        "states": [
            "DRAFT",
            "SUBMITTED",
            "SCRUTINY",
            "EC_LISTING",
            "EC_DECISION",
            "EOA_ISSUED",
            "ACTIVE_EOA",
            "SPEAKING_ORDER",
            "APPEAL_WINDOW",
            "SAC_REVIEW",
            "COUNCIL_FINAL",
            "REGIONAL_ENDORSEMENT",
            "FINAL_LOA",
            "FINAL_LOD",
            "FINAL_LOR",
            "WITHDRAWN",
        ],
        "transitions": TRACK_D_TRANSITIONS,
    },
]


def _state_rows(codes: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for order, code in enumerate(codes):
        meta = STATE_META[code]
        rows.append(
            {
                "code": code,
                "label": meta["label"],
                "stage": meta["stage"],
                "is_initial": bool(meta.get("initial")),
                "is_terminal": bool(meta.get("terminal")),
                "sort_order": order,
                "description": "",
                "apH_clause": meta["clause"],
                "needs_verification": False,
            }
        )
    return rows


def build_workflow_definitions() -> list[dict[str, Any]]:
    """Return every workflow definition as JSON-serialisable seed data."""
    rows: list[dict[str, Any]] = []
    for definition in DEFINITIONS:
        states = _state_rows(definition["states"])
        state_codes = {state["code"] for state in states}
        # Shared helper edges (withdraw/reopen) are generated for every track;
        # keep only the ones whose endpoints exist in this definition.
        transitions = [
            edge
            for edge in definition["transitions"]
            if edge["from_state"] in state_codes and edge["to_state"] in state_codes
        ]
        rows.append(
            {
                "key": definition["key"],
                "label": definition["label"],
                "track": definition["track"],
                "description": definition["description"],
                "apH_clause": definition["apH_clause"],
                "needs_verification": definition["needs_verification"],
                "is_active": True,
                "config": definition.get("config", {}),
                "states": states,
                "transitions": transitions,
            }
        )
    return rows


# Application type -> workflow key / not-implemented flags. This is repeated in
# the route seed file so the catalogue and the routing table cannot drift.
ROUTE_WORKFLOW_KEYS: dict[str, str] = {
    "NEW_INSTITUTION": "TRACK_A",
    "NEW_INSTITUTION_OTHER_REGULATOR": "TRACK_A",
    "OFF_CAMPUS": "TRACK_A",
    "DIPLOMA_DEGREE_CONVERSION": "TRACK_A",
    "CHANGE_OF_NAME": "TRACK_A",
    "SUPERNUMERARY_FN_OCI": "TRACK_A",
    "EXTENDED_EOA": "TRACK_A",
    "EOA_SELF_DISCLOSURE": "TRACK_B",
    "NRI_SEATS": "TRACK_B",
    "NEW_PROGRAMME": "TRACK_C",
    "INCREASE_INTAKE": "TRACK_C",
    "INTEGRATED_DUAL_DEGREE": "TRACK_C",
    "FPM": "TRACK_C",
    "COLLABORATION_TWINNING": "TRACK_C",
    "CHANGE_OF_SITE": "TRACK_C",
    "CLOSURE_OF_INSTITUTION": "TRACK_D",
    "CLOSURE_OF_PROGRAMME": "TRACK_D",
    "WOMEN_COED_CONVERSION": "TRACK_D",
    "CHANGE_IN_BANK_DETAILS": "TRACK_D",
    "CHANGE_OF_TRUST_NAME": "TRACK_D",
    "COURSE_RENAME_MERGE_REDUCTION": "TRACK_D",
}

NOT_IMPLEMENTED_TYPES: dict[str, str] = {
    "UNIVERSITY": "University-specific logic is outside the prototype scope.",
    "CLOSURE_AND_NEW_INSTITUTION": "Combined closure/new-institution logic is outside scope.",
    "MERGER_OF_INSTITUTIONS": "Merger logic is outside the prototype scope.",
    "EOA_AFTER_BREAK": "Break-in-EoA restoration is outside the prototype scope.",
    "DEEMED_UNIVERSITY_CONVERSION": "Deemed-university conversion is outside scope.",
    "ODL_ONLINE": "ODL/online approval is outside the prototype scope.",
}
