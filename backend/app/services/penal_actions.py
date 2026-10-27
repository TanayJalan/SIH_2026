"""Suggest APH 7.3 penal actions for APH 7.4 violations.

The engine only *suggests*. A hearing, a speaking order and the appeal route
remain mandatory workflow steps (APH 6.50h proviso, Chapter VII). Nothing here
mutates an institution's approval.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.models.enums import PenalActionType


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
                {"action": action.value, "label": _ACTION_LABELS[action]}
                for action in actions
            ],
            "hearing_required": True,
        }
        for code, (violation, actions) in _VIOLATIONS.items()
    ]
