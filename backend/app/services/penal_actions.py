"""Suggest APH 7.3 penal actions for APH 7.4 violations.

The engine only *suggests*. A hearing, a speaking order and the appeal route
remain mandatory workflow steps (APH 6.50h proviso, Chapter VII). Recording and
issuing an action is a separate, explicitly audited step in this module; nothing
here runs inside the application state machine.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.models.application import Application
from app.models.complaint import Complaint, PenalAction
from app.models.enums import PenalActionType, ProgrammeStatus
from app.models.institution import Institution
from app.models.programme import ApprovedIntakeLedger, Programme
from app.models.user import User
from app.services.audit import AuditService


@dataclass(frozen=True)
class PenalActionSuggestion:
    """One suggested action for a violation, with its handbook clause."""

    violation_code: str
    violation: str
    action: PenalActionType
    action_label: str
    apH_clause: str
    suggests_only: bool = True
    hearing_required: bool = True


_ACTION_LABELS: dict[PenalActionType, str] = {
    PenalActionType.NRI_SUSPENSION: "Suspension of NRI/supernumerary seats for one year",
    PenalActionType.INTAKE_REDUCTION: "Reduction in approved intake",
    PenalActionType.NO_ADMISSION: "No admission in one or more courses for a year",
    PenalActionType.PROGRAMME_WITHDRAWAL: "Withdrawal of programme approval",
    PenalActionType.AUTONOMY_WITHDRAWAL: "Withdrawal of graded autonomy",
    PenalActionType.INSTITUTION_WITHDRAWAL: "Withdrawal of institution approval",
    PenalActionType.EXCESS_ADMISSION_FINE: (
        "Fine of five times the total course fee per excess admission"
    ),
    PenalActionType.GRANT_INELIGIBLE: "Ineligibility for AICTE grants",
}

_VIOLATIONS: dict[str, tuple[str, tuple[PenalActionType, ...]]] = {
    "7.4a": (
        "False, incomplete or missing information in the EoA application",
        (
            PenalActionType.PROGRAMME_WITHDRAWAL,
            PenalActionType.INSTITUTION_WITHDRAWAL,
            PenalActionType.GRANT_INELIGIBLE,
        ),
    ),
    "7.4b": (
        "Principal/Director vacant for more than 12 months",
        (
            PenalActionType.INTAKE_REDUCTION,
            PenalActionType.NO_ADMISSION,
            PenalActionType.PROGRAMME_WITHDRAWAL,
            PenalActionType.INSTITUTION_WITHDRAWAL,
        ),
    ),
    "7.4c": (
        "Shortfall in faculty:student ratio, pay scale or qualifications for more than 12 months",
        (
            PenalActionType.INTAKE_REDUCTION,
            PenalActionType.NO_ADMISSION,
            PenalActionType.PROGRAMME_WITHDRAWAL,
            PenalActionType.INSTITUTION_WITHDRAWAL,
        ),
    ),
    "7.4d": (
        "Shortfall in computers, software, laboratories, books, journals or library",
        (
            PenalActionType.INTAKE_REDUCTION,
            PenalActionType.PROGRAMME_WITHDRAWAL,
            PenalActionType.GRANT_INELIGIBLE,
        ),
    ),
    "7.4e": (
        "Essential requirements of APH 6.47-6.53 not met",
        (
            PenalActionType.INTAKE_REDUCTION,
            PenalActionType.PROGRAMME_WITHDRAWAL,
            PenalActionType.INSTITUTION_WITHDRAWAL,
        ),
    ),
    "7.4f": (
        "Temporary or unapproved location, or insufficient built-up area",
        (
            PenalActionType.NO_ADMISSION,
            PenalActionType.PROGRAMME_WITHDRAWAL,
            PenalActionType.INSTITUTION_WITHDRAWAL,
        ),
    ),
    "7.4g": (
        "Admission in excess of the approved intake",
        (
            PenalActionType.EXCESS_ADMISSION_FINE,
            PenalActionType.INTAKE_REDUCTION,
            PenalActionType.NO_ADMISSION,
        ),
    ),
    "7.4h": (
        "Admission eligibility violation, including improper lateral transfers",
        (
            PenalActionType.NO_ADMISSION,
            PenalActionType.PROGRAMME_WITHDRAWAL,
            PenalActionType.INSTITUTION_WITHDRAWAL,
        ),
    ),
    "7.4i": (
        "Charging fees in excess of the State Fee Regulatory Committee fee",
        (
            PenalActionType.INTAKE_REDUCTION,
            PenalActionType.GRANT_INELIGIBLE,
        ),
    ),
    "7.4j": (
        "Refusing EVC access, or no Occupancy/Completion/Form D or barrier-free environment",
        (
            PenalActionType.NO_ADMISSION,
            PenalActionType.PROGRAMME_WITHDRAWAL,
            PenalActionType.INSTITUTION_WITHDRAWAL,
        ),
    ),
    "7.4k": (
        "Retaining original degree certificates of students or faculty",
        (
            PenalActionType.GRANT_INELIGIBLE,
            PenalActionType.PROGRAMME_WITHDRAWAL,
        ),
    ),
    "7.4l": (
        "Deemed university without Academic Bank of Credits registration",
        (
            PenalActionType.GRANT_INELIGIBLE,
            PenalActionType.PROGRAMME_WITHDRAWAL,
        ),
    ),
    "7.4m": (
        "PGDM norm violation, no ABC registration, or enrolment data not uploaded",
        (
            PenalActionType.INTAKE_REDUCTION,
            PenalActionType.PROGRAMME_WITHDRAWAL,
            PenalActionType.GRANT_INELIGIBLE,
        ),
    ),
    "7.4n": (
        "Running partial-approval programmes or integrated/dual programmes "
        "needing multiple regulators",
        (
            PenalActionType.PROGRAMME_WITHDRAWAL,
            PenalActionType.INSTITUTION_WITHDRAWAL,
        ),
    ),
}

_PROCESS_STEPS = (
    "Issuing a show-cause notice and giving a hearing (APH 6.50h proviso)",
    "Passing a detailed speaking order on the portal (APH 2.23.3, 7.10)",
    "Allowing one appeal to the Standing Appellate Committee within 7 days (APH 1.11a, 2.24a)",
)


def suggestions_for_codes(codes: Iterable[str]) -> list[PenalActionSuggestion]:
    """Expand APH 7.4 codes into suggested APH 7.3 actions.

    Unknown codes are ignored rather than guessed at, so a typo in a rule's
    ``penalty_codes`` cannot invent a penalty.
    """
    suggestions: list[PenalActionSuggestion] = []
    seen: set[tuple[str, PenalActionType]] = set()
    for raw_code in codes:
        code = str(raw_code).strip().lower().replace("aph", "").strip()
        if not code.startswith("7.4"):
            code = f"7.4{code}" if len(code) == 1 else code
        if not code.startswith("7.4") or code not in _VIOLATIONS:
            continue
        violation, actions = _VIOLATIONS[code]
        for action in actions:
            key = (code, action)
            if key in seen:
                continue
            seen.add(key)
            suggestions.append(
                PenalActionSuggestion(
                    violation_code=f"APH {code}",
                    violation=violation,
                    action=action,
                    action_label=_ACTION_LABELS[action],
                    apH_clause=f"APH 7.3, {code}",
                )
            )
    return suggestions


def process_steps() -> Sequence[str]:
    """The mandatory steps that precede any penal action."""
    return _PROCESS_STEPS


def catalogue() -> list[dict[str, object]]:
    """Return the violation code catalogue for the admin screen."""
    return [
        {
            "code": f"APH {code}",
            "violation": violation,
            "actions": [
                {"action": action.value, "label": _ACTION_LABELS[action]} for action in actions
            ],
            "hearing_required": True,
        }
        for code, (violation, actions) in _VIOLATIONS.items()
    ]


# ---------------------------------------------------------------------------
# Recording, hearing and consequences
# ---------------------------------------------------------------------------

#: APH 7.3g fixes the fine at five times the total course fee per excess
#: admission. It is a parameter so tests can assert the arithmetic directly.
EXCESS_ADMISSION_FINE_MULTIPLIER = 5

#: APH 7.1b bars a withdrawn institution from applying again for two academic
#: years. The period is expressed in years so the calculator can add it to a
#: date without guessing term lengths.
INSTITUTION_REAPPLY_YEARS = 2

HEARING_CLAUSE = "APH 6.50h"
"""A hearing before action is mandatory under the proviso to APH 6.50h."""


class PenalActionError(ValueError):
    """Raised when a penal action cannot be recorded or issued."""


@dataclass(frozen=True)
class ExcessAdmissionFine:
    """The APH 7.3g fine computed from the approved-intake ledger."""

    academic_year: str
    excess_admissions: int
    annual_fee_paise: int
    total_course_fee_paise: int
    fine_paise: int
    lines: tuple[dict[str, Any], ...]
    apH_clause: str = "APH 7.3g"


def _to_paise(value: Any) -> int:
    """Convert a rupee amount in the application form to integer paise."""
    if value is None:
        return 0
    return int(round(float(value) * 100))


def _normalise_violation_code(code: str) -> str:
    """Return a bare ``7.4x`` code from ``g``, ``7.4g`` or ``APH 7.4g``."""
    text = str(code).strip().lower().replace("aph", "").strip()
    if len(text) == 1:
        text = f"7.4{text}"
    return text


def _annual_fee_paise(application: Application | None) -> int:
    """Return the annual course fee declared on the application, in paise."""
    if application is None:
        return 0
    finance = (application.data or {}).get("finance") or {}
    return sum(
        _to_paise(finance.get(key)) for key in ("tuition_fee", "development_fee", "other_fees")
    )


def calculate_excess_admission_fine(
    db: Session,
    application: Application | None,
    *,
    institution_id: uuid.UUID | None = None,
    academic_year: str | None = None,
) -> ExcessAdmissionFine:
    """Compute the APH 7.3g fine from the approved-intake ledger.

    For each programme of the institution in the academic year, the excess is
    ``admitted_total - approved_intake`` (never below zero). The total course fee
    is the annual fee declared on the application multiplied by the programme
    duration; the fine is five times that amount for every excess admission.
    """
    institution = institution_id
    if institution is None and application is not None:
        institution = application.institution_id
    if institution is None:
        raise PenalActionError("An institution is required to compute the excess-admission fine.")
    year = academic_year or (application.academic_year if application is not None else None)
    if not year:
        raise PenalActionError(
            "The academic year is required to compute the excess-admission fine."
        )

    annual_fee_paise = _annual_fee_paise(application)
    programmes = list(
        db.scalars(select(Programme).where(Programme.institution_id == institution)).all()
    )
    ledger_by_programme = {
        row.programme_id: row
        for row in db.scalars(
            select(ApprovedIntakeLedger).where(
                ApprovedIntakeLedger.programme_id.in_([programme.id for programme in programmes]),
                ApprovedIntakeLedger.academic_year == year,
            )
        ).all()
    }

    lines: list[dict[str, Any]] = []
    total_excess = 0
    fine_paise = 0
    total_course_fee_paise = 0
    for programme in programmes:
        ledger = ledger_by_programme.get(programme.id)
        if ledger is None:
            continue
        excess = max(0, ledger.admitted_total - ledger.approved_intake)
        if excess == 0:
            continue
        duration = Decimal(str(programme.duration_years or 0))
        total_course_fee = int(round(annual_fee_paise * float(duration)))
        line_fine = EXCESS_ADMISSION_FINE_MULTIPLIER * total_course_fee * excess
        total_excess += excess
        fine_paise += line_fine
        total_course_fee_paise += total_course_fee
        lines.append(
            {
                "programme_id": str(programme.id),
                "course_name": programme.course_name,
                "level": programme.level,
                "approved_intake": ledger.approved_intake,
                "admitted_total": ledger.admitted_total,
                "excess_admissions": excess,
                "duration_years": str(duration),
                "annual_fee_paise": annual_fee_paise,
                "total_course_fee_paise": total_course_fee,
                "fine_paise": line_fine,
                "apH_clause": "APH 7.3g, 7.4g",
            }
        )

    return ExcessAdmissionFine(
        academic_year=year,
        excess_admissions=total_excess,
        annual_fee_paise=annual_fee_paise,
        total_course_fee_paise=total_course_fee_paise,
        fine_paise=fine_paise,
        lines=tuple(lines),
    )


def _two_academic_years_after(day: date) -> date:
    """Return the date two calendar years after ``day``, clamped to month end."""
    year = day.year + INSTITUTION_REAPPLY_YEARS
    try:
        return day.replace(year=year)
    except ValueError:  # 29 February
        return day.replace(year=year, day=28)


def _log(
    audit: AuditService,
    actor: User | None,
    action: str,
    penal_action: PenalAction,
    before: dict[str, Any] | None,
    request: Request | None,
) -> None:
    audit.log(
        actor,
        action,
        entity_type="PenalAction",
        entity_id=penal_action.id,
        before=before,
        after={
            "action_type": penal_action.action_type.value,
            "violation_code": penal_action.violation_code,
            "issued_on": penal_action.issued_on.isoformat() if penal_action.issued_on else None,
            "fine_paise": penal_action.fine_paise,
            "consequences": penal_action.consequences,
        },
        request=request,
    )


def record_penal_action(
    db: Session,
    *,
    institution: Institution,
    action_type: PenalActionType,
    violation_code: str,
    application: Application | None = None,
    complaint: Complaint | None = None,
    effective_academic_year: str | None = None,
    actor: User | None,
    audit: AuditService,
    request: Request | None = None,
) -> PenalAction:
    """Record a draft APH 7.3 action against an APH 7.4 violation.

    The action is only a draft: :func:`issue_penal_action` requires a hearing
    first. An excess-admission fine is computed from the ledger at record time so
    the order carries a stable amount.
    """
    code = _normalise_violation_code(violation_code)
    if code not in _VIOLATIONS:
        raise PenalActionError(f"{violation_code!r} is not an APH 7.4 violation code (a-n).")
    _, allowed_actions = _VIOLATIONS[code]
    if action_type not in allowed_actions:
        allowed = ", ".join(action.value for action in allowed_actions)
        raise PenalActionError(
            f"APH {code} does not permit {action_type.value}; use one of {allowed}."
        )

    penal_action = PenalAction(
        institution_id=institution.id,
        complaint_id=complaint.id if complaint is not None else None,
        application_id=application.id if application is not None else None,
        action_type=action_type,
        violation_code=code.removeprefix("7.4"),
        effective_academic_year=effective_academic_year
        or (application.academic_year if application is not None else None),
        apH_clause=f"APH 7.3, {code}",
        hearing_done=False,
    )
    if action_type == PenalActionType.EXCESS_ADMISSION_FINE:
        fine = calculate_excess_admission_fine(
            db,
            application,
            institution_id=institution.id,
            academic_year=effective_academic_year,
        )
        penal_action.fine_paise = fine.fine_paise
        penal_action.fine_basis = (
            "Five times the total course fee per excess admission "
            f"(APH 7.3g): {fine.excess_admissions} excess admission(s), "
            f"total course fee {fine.total_course_fee_paise} paise annually."
        )
        penal_action.consequences = {
            "fine_lines": list(fine.lines),
            "excess_admissions": fine.excess_admissions,
        }
    db.add(penal_action)
    db.flush()
    _log(audit, actor, "penal_action.recorded", penal_action, None, request)
    return penal_action


def schedule_hearing(
    db: Session,
    penal_action: PenalAction,
    *,
    hearing_on: date,
    notes: str | None,
    actor: User | None,
    audit: AuditService,
    request: Request | None = None,
) -> PenalAction:
    """Schedule the hearing that must precede any penal action (APH 6.50h)."""
    if penal_action.issued_on is not None:
        raise PenalActionError("The penal action has already been issued.")
    before = {"hearing_on": None}
    penal_action.hearing_on = hearing_on
    penal_action.hearing_notes = notes
    penal_action.hearing_by_user_id = actor.id if actor is not None else None
    _log(audit, actor, "penal_action.hearing_scheduled", penal_action, before, request)
    return penal_action


def _apply_consequences(
    db: Session, penal_action: PenalAction, *, issued_on: date
) -> dict[str, Any]:
    """Apply the automatic consequences of an issued action (APH 7.3)."""
    institution = db.get(Institution, penal_action.institution_id)
    year = penal_action.effective_academic_year
    consequences: dict[str, Any] = {"issued_on": issued_on.isoformat()}

    if penal_action.action_type == PenalActionType.NRI_SUSPENSION:
        withdrawn: list[str] = []
        if institution is not None and year:
            programme_ids = select(Programme.id).where(Programme.institution_id == institution.id)
            for ledger in db.scalars(
                select(ApprovedIntakeLedger).where(
                    ApprovedIntakeLedger.programme_id.in_(programme_ids),
                    ApprovedIntakeLedger.academic_year == year,
                )
            ).all():
                ledger.nri = 0
                ledger.fn_oci = 0
                withdrawn.append(str(ledger.programme_id))
        consequences.update(
            {
                "supernumerary_seats_withdrawn": True,
                "programme_ids": withdrawn,
                "apH_clause": "APH 7.3",
            }
        )
    elif penal_action.action_type == PenalActionType.PROGRAMME_WITHDRAWAL:
        closed: list[str] = []
        if institution is not None:
            for programme in db.scalars(
                select(Programme).where(Programme.institution_id == institution.id)
            ).all():
                programme.status = ProgrammeStatus.CLOSED
                closed.append(programme.course_name)
        consequences.update(
            {
                "programmes_closed": closed,
                "students_redistributed_by_state": True,
                "apH_clause": "APH 7.1c",
            }
        )
    elif penal_action.action_type == PenalActionType.INSTITUTION_WITHDRAWAL:
        eligible_from = _two_academic_years_after(issued_on)
        penal_action.restoration_eligible_from = eligible_from
        consequences.update(
            {
                "approval_withdrawn": True,
                "reapply_after": eligible_from.isoformat(),
                "different_name_required": True,
                "students_redistributed_by_state": True,
                "apH_clause": "APH 7.1b, 7.1c",
            }
        )
    elif penal_action.action_type == PenalActionType.NO_ADMISSION:
        consequences.update({"admission_barred": True, "apH_clause": "APH 7.3"})
    elif penal_action.action_type == PenalActionType.INTAKE_REDUCTION:
        consequences.update({"intake_reduction_requires_order": True, "apH_clause": "APH 7.3"})
    elif penal_action.action_type == PenalActionType.AUTONOMY_WITHDRAWAL:
        consequences.update({"graded_autonomy_withdrawn": True, "apH_clause": "APH 7.3"})
    elif penal_action.action_type == PenalActionType.EXCESS_ADMISSION_FINE:
        consequences.update(
            {
                "fine_paise": penal_action.fine_paise,
                "fine_basis": penal_action.fine_basis,
                "apH_clause": "APH 7.3g",
            }
        )
    elif penal_action.action_type == PenalActionType.GRANT_INELIGIBLE:
        consequences.update({"grants_ineligible": True, "apH_clause": "APH 7.3"})
    return consequences


def issue_penal_action(
    db: Session,
    penal_action: PenalAction,
    *,
    order_number: str,
    issued_on: date,
    speaking_order: str,
    actor: User | None,
    audit: AuditService,
    request: Request | None = None,
) -> PenalAction:
    """Issue the action after a hearing and apply its consequences (APH 6.50h).

    The hearing guard is the whole point of this function: without a recorded
    ``hearing_on`` the issue is refused, so no endpoint can skip the proviso to
    APH 6.50h.
    """
    if penal_action.hearing_on is None:
        raise PenalActionError("A hearing before a penal action is mandatory (APH 6.50h proviso).")
    if penal_action.issued_on is not None:
        raise PenalActionError("The penal action has already been issued.")
    if not speaking_order.strip():
        raise PenalActionError("A penal action must be supported by a Speaking Order (APH 7.10g).")
    before = {
        "issued_on": None,
        "fine_paise": penal_action.fine_paise,
        "consequences": penal_action.consequences,
    }
    penal_action.hearing_done = True
    penal_action.issued_on = issued_on
    penal_action.order_number = order_number
    penal_action.speaking_order = speaking_order
    penal_action.consequences = _apply_consequences(db, penal_action, issued_on=issued_on)
    _log(audit, actor, "penal_action.issued", penal_action, before, request)
    return penal_action


def request_restoration(
    db: Session,
    penal_action: PenalAction,
    *,
    requested_on: date,
    actor: User | None,
    audit: AuditService,
    request: Request | None = None,
) -> PenalAction:
    """Record a restoration request against a punitive action (APH 7.11a).

    A withdrawn institution may only apply after two academic years under a
    different name (APH 7.1b); the request is stored but marked ineligible until
    ``restoration_eligible_from``. The request is filed with the next Extension of
    Approval application (APH 7.11a), which remains a separate workflow step.
    """
    if penal_action.issued_on is None:
        raise PenalActionError("A restoration request requires an issued action.")
    if penal_action.restoration_requested_on is not None:
        raise PenalActionError("A restoration request has already been recorded.")

    before = {"restoration_status": penal_action.restoration_status}
    blocked = (
        penal_action.action_type == PenalActionType.INSTITUTION_WITHDRAWAL
        and penal_action.restoration_eligible_from is not None
        and requested_on < penal_action.restoration_eligible_from
    )
    penal_action.restoration_requested_on = requested_on
    penal_action.restoration_status = "REQUESTED" if not blocked else "NOT_YET_ELIGIBLE"
    _log(audit, actor, "penal_action.restoration_requested", penal_action, before, request)
    return penal_action
