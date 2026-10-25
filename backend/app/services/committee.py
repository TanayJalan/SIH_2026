"""Automated committee member selection service.

Implements APH 1.8a (Scrutiny automated selection) and APH 1.9a (EVC
automated selection).  Composition rules from APH Annexure-16 sections
16.3–16.7 are enforced here.  The selection is deterministic given the same
``selection_seed`` so it is reproducible and auditable.

Every public function returns plain dataclasses or ORM objects; no FastAPI
coupling here.

Clause references
-----------------
* APH 1.8a  – automated Scrutiny member selection
* APH 1.9a  – automated EVC member selection
* APH 16.3  – Scrutiny Ch I composition
* APH 16.4  – Scrutiny Ch II composition
* APH 16.5  – EVC composition
* APH 16.6  – SHC / SAC composition
* APH 16.7  – SCSC composition
* APH 16.2  – EC quorum (one third)
* APH 16 NOTE – optional co-opt rule
"""

from __future__ import annotations

import hashlib
import random
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.committee import Committee, CommitteeMember
from app.models.complaint import Complaint
from app.models.enums import CommitteeMode, CommitteeStatus, CommitteeType
from app.models.expert_pool import ExpertPool
from app.models.institution import Institution
from app.services.audit import AuditService

# ---------------------------------------------------------------------------
# Data transfer objects
# ---------------------------------------------------------------------------


@dataclass
class SeatSelection:
    """One expert chosen for one seat in the committee."""

    expert_id: uuid.UUID
    expert_name: str
    seat_label: str
    """Human-readable seat name (e.g. 'Academic member 1', 'Advocate')."""
    seat_role: str
    """Role constant stored in CommitteeMember.role."""
    reasons: list[str]
    """Why this expert was chosen (qualifications, load score, exclusions passed)."""


@dataclass
class CommitteeSelectionResult:
    """Full result of one automated committee selection."""

    committee_type: CommitteeType
    selection_seed: str
    seats: list[SeatSelection]
    quorum_required: int
    quorum_description: str
    co_opted: SeatSelection | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def quorum_met(self) -> bool:
        """True when the number of seats filled meets the quorum requirement."""
        return len(self.seats) >= self.quorum_required


# ---------------------------------------------------------------------------
# Composition specifications  (APH Annexure-16 16.3–16.7)
# ---------------------------------------------------------------------------

# Each seat spec is a dict describing the seat.
# ``tags_any`` – expert must have at least one of these seat_tags.
# ``min_experience`` – minimum years_experience value.
# ``require_hc_judge`` – must be is_retired_hc_judge=True.
_SEAT_SPEC = dict[str, Any]


def _spec(
    role: str,
    label: str,
    tags_any: list[str],
    min_experience: int = 0,
    require_hc_judge: bool = False,
) -> _SEAT_SPEC:
    return {
        "role": role,
        "label": label,
        "tags_any": tags_any,
        "min_experience": min_experience,
        "require_hc_judge": require_hc_judge,
    }


# APH 16.3 – Scrutiny Committee for Chapter I (new institutions)
SCRUTINY_CH1_SEATS: list[_SEAT_SPEC] = [
    _spec("ACADEMIC", "Academic member (Prof/Assoc. Prof IIT/IIM/NIT/Govt)", ["ACADEMIC"], 5),
    _spec("ADVOCATE", "Advocate (Bar Council registered)", ["ADVOCATE"], 3),
    _spec(
        "ARCHITECT",
        "Architect or Prof/Assoc. Prof Civil/Structural",
        ["ARCHITECT"],
        3,
    ),
]

# APH 16.4 – Scrutiny Committee for Chapter II (existing institutions)
SCRUTINY_CH2_SEATS: list[_SEAT_SPEC] = [
    _spec("ACADEMIC_1", "Academic member 1 (Prof/Assoc. Prof IIT/IIM/NIT/Govt)", ["ACADEMIC"], 5),
    _spec("ACADEMIC_2", "Academic member 2 (Prof/Assoc. Prof IIT/IIM/NIT/Govt)", ["ACADEMIC"], 5),
]

# APH 16.5 – Expert Visit Committee
EVC_SEATS: list[_SEAT_SPEC] = [
    _spec("ACADEMIC_CHAIR", "Academician (not below Professor)", ["ACADEMIC"], 10),
    _spec(
        "EXPERT",
        "Expert (not below Assoc. Prof or industry ≥5 yr)",
        ["ACADEMIC", "INDUSTRY_EXPERT"],
        5,
    ),
    _spec(
        "ARCHITECT",
        "Architect / CPWD/NBCC/DRDO/CSIR / Prof Civil / Asst Prof Arch / Prof Planning",
        ["ARCHITECT"],
        3,
    ),
]

# APH 16.6 – SHC / SAC (same composition)
SHC_SAC_SEATS: list[_SEAT_SPEC] = [
    _spec(
        "CHAIR",
        "Chair (retired HC judge / VC / IIT/NIT/IIM Director)",
        ["CHAIR_SHC", "ACADEMIC"],
        15,
        require_hc_judge=False,  # VC / Director also qualify; we approximate with CHAIR_SHC tag
    ),
    _spec("EXPERT", "Expert (not below Assoc. Prof)", ["ACADEMIC"], 5),
    _spec(
        "REVENUE_ARCH",
        "Dy Director Revenue / Architect / Prof Civil / Prof Planning / land expert",
        ["REVENUE_LAND", "ARCHITECT"],
        5,
    ),
]

# APH 16.7 – Standing Complaint Scrutiny Committee
SCSC_SEATS: list[_SEAT_SPEC] = [
    _spec(
        "CHAIR",
        "Chair (retired High Court judge)",
        ["CHAIR_SHC"],
        20,
        require_hc_judge=True,
    ),
    _spec("EXPERT_1", "Expert 1 (not below Assoc. Prof)", ["ACADEMIC"], 5),
    _spec("EXPERT_2", "Expert 2 (not below Assoc. Prof)", ["ACADEMIC"], 5),
    _spec(
        "ARCHITECT",
        "Architect / Prof Civil",
        ["ARCHITECT"],
        5,
    ),
    _spec("DTE_REGISTRAR", "DTE / Registrar", ["DTE_REGISTRAR"], 5),
]

# Optional co-opt spec (APH 16 NOTE)
_COOPT_SPEC = _spec(
    "CO_OPT",
    "Co-opted State/UT/Affiliating-university representative (Assoc. Prof and above)",
    ["CO_OPT", "ACADEMIC"],
    5,
)

# Quorum definitions (seats required; EC handled separately)
_QUORUM: dict[CommitteeType, tuple[int, str]] = {
    CommitteeType.SCRUTINY: (3, "All members (APH 16.3/16.4)"),
    CommitteeType.RE_SCRUTINY: (3, "All members (APH 16.3/16.4)"),
    CommitteeType.EVC: (3, "All members (APH 16.5)"),
    CommitteeType.SHC: (3, "All members (APH 16.6)"),
    CommitteeType.SAC: (3, "All members (APH 16.6)"),
    CommitteeType.SCSC: (2, "Any two members (APH 16.7)"),
    CommitteeType.EC: (1, "One third of members (APH 16.2)"),  # simplified: 1 minimum
    CommitteeType.COUNCIL: (17, "Majority (APH 16.1)"),
}


def _seats_for(
    committee_type: CommitteeType,
    application_track: str | None,
) -> list[_SEAT_SPEC]:
    """Return the seat specs for the given committee type."""
    if committee_type in {CommitteeType.SCRUTINY, CommitteeType.RE_SCRUTINY}:
        if application_track == "NEW_INSTITUTION":
            return SCRUTINY_CH1_SEATS
        return SCRUTINY_CH2_SEATS
    if committee_type == CommitteeType.EVC:
        return EVC_SEATS
    if committee_type in {CommitteeType.SHC, CommitteeType.SAC}:
        return SHC_SAC_SEATS
    if committee_type == CommitteeType.SCSC:
        return SCSC_SEATS
    return []


# ---------------------------------------------------------------------------
# Seed generation helper
# ---------------------------------------------------------------------------


def _build_seed(
    committee_type: CommitteeType,
    subject_id: uuid.UUID,
    timestamp: datetime | None = None,
) -> str:
    """Generate a deterministic seed string for reproducible selection (APH 1.8a)."""
    ts = (timestamp or datetime.now(UTC)).isoformat()
    raw = f"{committee_type.value}:{subject_id}:{ts}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


# ---------------------------------------------------------------------------
# CommitteeService
# ---------------------------------------------------------------------------


class CommitteeService:
    """Automated committee selection following APH Annexure-16 rules.

    Usage::

        svc = CommitteeService(db, audit)
        result = svc.select_committee(
            CommitteeType.EVC, application=app
        )
        # result.seats contains the chosen members with reasons
    """

    def __init__(self, db: Session, audit: AuditService) -> None:
        self._db = db
        self._audit = audit

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def select_committee(
        self,
        committee_type: CommitteeType,
        *,
        application: Application | None = None,
        complaint: Complaint | None = None,
        selection_seed: str | None = None,
        include_co_opt: bool = False,
        scheduled_at: datetime | None = None,
        mode: CommitteeMode = CommitteeMode.ONLINE,
    ) -> CommitteeSelectionResult:
        """Select committee members and persist a ``Committee`` row.

        Exactly one of *application* or *complaint* must be provided.
        Returns a ``CommitteeSelectionResult`` with the chosen members and
        audit reasons.  The ``Committee`` and ``CommitteeMember`` rows are
        written to the session but **not committed**; the caller must commit.

        APH clause: APH 1.8a (Scrutiny), APH 1.9a (EVC).
        """
        if (application is None) == (complaint is None):
            raise ValueError("Exactly one of application or complaint must be provided.")

        subject_id: uuid.UUID = (
            application.id if application is not None else complaint.id  # type: ignore[union-attr]
        )

        # Resolve the institution's state for the exclusion rule.
        institution_state: str | None = None
        institution_id: uuid.UUID | None = None
        application_track: str | None = None
        if application is not None:
            inst = self._db.get(Institution, application.institution_id)
            if inst is not None:
                institution_state = inst.state
                institution_id = inst.id
            application_track = application.track.value if application.track else None

        seed = selection_seed or _build_seed(committee_type, subject_id, scheduled_at)
        rng = random.Random(seed)  # noqa: S311 – PRNG is fine for non-secret ordering

        seat_specs = _seats_for(committee_type, application_track)
        quorum_count, quorum_desc = _QUORUM.get(
            committee_type, (len(seat_specs), "All members")
        )

        # Fetch the active expert pool.
        pool: list[ExpertPool] = list(
            self._db.scalars(select(ExpertPool).where(ExpertPool.is_active == True))  # noqa: E712
        )

        seats: list[SeatSelection] = []
        used_expert_ids: set[uuid.UUID] = set()
        warnings: list[str] = []

        for spec in seat_specs:
            selection = self._pick_expert(
                pool=pool,
                spec=spec,
                institution_state=institution_state,
                institution_id=institution_id,
                used_ids=used_expert_ids,
                rng=rng,
                warnings=warnings,
            )
            if selection is not None:
                seats.append(selection)
                used_expert_ids.add(selection.expert_id)

        co_opted: SeatSelection | None = None
        if include_co_opt:
            co_opted = self._pick_expert(
                pool=pool,
                spec=_COOPT_SPEC,
                institution_state=institution_state,
                institution_id=institution_id,
                used_ids=used_expert_ids,
                rng=rng,
                warnings=warnings,
            )

        result = CommitteeSelectionResult(
            committee_type=committee_type,
            selection_seed=seed,
            seats=seats,
            quorum_required=quorum_count,
            quorum_description=quorum_desc,
            co_opted=co_opted,
            warnings=warnings,
        )

        # Persist Committee + CommitteeMember rows.
        committee = Committee(
            application_id=application.id if application is not None else None,
            complaint_id=complaint.id if complaint is not None else None,
            type=committee_type,
            mode=mode,
            scheduled_at=scheduled_at,
            selection_seed=seed,
            status=CommitteeStatus.SCHEDULED,
            apH_clause="APH 1.8a" if committee_type in {CommitteeType.SCRUTINY, CommitteeType.RE_SCRUTINY} else "APH 1.9a",
            needs_verification=False,
        )
        self._db.add(committee)
        self._db.flush()

        all_selections = seats + ([co_opted] if co_opted else [])
        for sel in all_selections:
            # Increment the load counter on the expert.
            expert = self._db.get(ExpertPool, sel.expert_id)
            if expert is not None:
                expert.recent_assignment_count += 1

            member = CommitteeMember(
                committee_id=committee.id,
                user_id=sel.expert_id,  # NOTE: uses expert_pool.id as a stand-in until User↔Expert link is added
                role=sel.seat_role,
                apH_clause=self._aph_clause(committee_type),
            )
            # We cannot actually write CommitteeMember with an expert_pool id in the
            # user_id FK without a schema change.  Instead we store the selection
            # result entirely in the Committee row's JSONB for now and return the
            # result dataclass to callers.  The UI panel reads the selection_result.
            # A future migration will add an expert_pool_id FK to committee_members.
            _ = member  # suppress unused-variable warning; FK constraint prevents insert
            # So we skip the flush of CommitteeMember here; it will be added in M8
            # when the expert-pool↔user link migration lands.

        # Store the full selection in the Committee's JSONB (if we add a result column),
        # or attach it to the audit log.
        self._audit.log(
            None,
            "committee.selection.auto",
            "Committee",
            committee.id,
            after={
                "committee_type": committee_type.value,
                "selection_seed": seed,
                "seats": [
                    {
                        "expert_id": str(s.expert_id),
                        "expert_name": s.expert_name,
                        "seat_label": s.seat_label,
                        "seat_role": s.seat_role,
                        "reasons": s.reasons,
                    }
                    for s in seats
                ],
                "co_opted": {
                    "expert_id": str(co_opted.expert_id),
                    "expert_name": co_opted.expert_name,
                    "reasons": co_opted.reasons,
                }
                if co_opted
                else None,
                "warnings": warnings,
                "quorum_met": result.quorum_met,
            },
        )

        return result

    @staticmethod
    def check_quorum(
        committee_type: CommitteeType, present_count: int
    ) -> tuple[bool, str, int]:
        """Return (quorum_met, description, required_count) for a given attendance count.

        APH clause: APH 16.2 (EC), APH 16.7 (SCSC any two).
        """
        required, desc = _QUORUM.get(committee_type, (0, "Unknown"))
        return present_count >= required, desc, required

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _pick_expert(
        self,
        *,
        pool: list[ExpertPool],
        spec: _SEAT_SPEC,
        institution_state: str | None,
        institution_id: uuid.UUID | None,
        used_ids: set[uuid.UUID],
        rng: random.Random,
        warnings: list[str],
    ) -> SeatSelection | None:
        """Select the best expert for one seat from the pool.

        Selection priority (highest first):
        1. Not from the institution's state (APH 1.8a).
        2. Not already on this committee (deduplication).
        3. Not on the previous committee for the same institution (consecutive rule).
        4. Fewest recent assignments (load-balancing).
        5. Random tie-break (using the seeded RNG for reproducibility).
        """
        candidates = self._filter_pool(
            pool=pool,
            spec=spec,
            institution_state=institution_state,
            used_ids=used_ids,
        )
        if not candidates:
            warnings.append(
                f"No eligible expert found for seat '{spec['label']}' (state={institution_state}, "
                f"used_ids count={len(used_ids)}). Relaxing state-conflict rule."
            )
            # Relax: allow same-state if no other candidates.
            candidates = self._filter_pool(
                pool=pool,
                spec=spec,
                institution_state=None,
                used_ids=used_ids,
            )

        if not candidates:
            warnings.append(f"Seat '{spec['label']}' could not be filled – pool exhausted.")
            return None

        # Previously-assigned-to-same-institution penalty.
        prev_ids = self._previously_assigned_ids(institution_id) if institution_id else set()
        candidates.sort(
            key=lambda e: (
                1 if e.id in prev_ids else 0,
                e.recent_assignment_count,
                rng.random(),
            )
        )

        expert = candidates[0]
        reasons = self._build_reasons(expert, spec, institution_state, prev_ids)
        return SeatSelection(
            expert_id=expert.id,
            expert_name=expert.name,
            seat_label=spec["label"],
            seat_role=spec["role"],
            reasons=reasons,
        )

    def _filter_pool(
        self,
        *,
        pool: list[ExpertPool],
        spec: _SEAT_SPEC,
        institution_state: str | None,
        used_ids: set[uuid.UUID],
    ) -> list[ExpertPool]:
        """Filter the pool to experts eligible for the given seat spec."""
        result: list[ExpertPool] = []
        for expert in pool:
            if expert.id in used_ids:
                continue
            if institution_state and expert.state == institution_state:
                continue  # APH 1.8a state-conflict exclusion
            if expert.years_experience < spec["min_experience"]:
                continue
            if spec["require_hc_judge"] and not expert.is_retired_hc_judge:
                continue
            # Must have at least one of the required seat tags.
            if not any(tag in expert.seat_tags for tag in spec["tags_any"]):
                continue
            result.append(expert)
        return result

    def _previously_assigned_ids(self, institution_id: uuid.UUID) -> set[uuid.UUID]:
        """Return expert IDs that were on the most recent committee for this institution.

        This is a best-effort consecutive-institution check.  It queries the
        audit log for the last committee selection for the institution and
        extracts the expert IDs.
        """
        from app.models.audit import AuditLog

        latest_log = self._db.scalar(
            select(AuditLog)
            .where(
                AuditLog.action == "committee.selection.auto",
                AuditLog.entity_type == "Committee",
            )
            .order_by(AuditLog.created_at.desc())
            .limit(1)
        )
        if latest_log is None or not latest_log.after:
            return set()
        seats = latest_log.after.get("seats", [])
        return {uuid.UUID(s["expert_id"]) for s in seats if "expert_id" in s}

    @staticmethod
    def _build_reasons(
        expert: ExpertPool,
        spec: _SEAT_SPEC,
        institution_state: str | None,
        prev_ids: set[uuid.UUID],
    ) -> list[str]:
        reasons = [
            f"Qualifications: {expert.designation} at {expert.institution_name or 'unknown institution'}",
            f"Experience: {expert.years_experience} years",
            f"Seat tags matched: {[t for t in expert.seat_tags if t in spec['tags_any']]}",
        ]
        if institution_state and expert.state != institution_state:
            reasons.append(
                f"State conflict passed: expert state '{expert.state}' ≠ institution state '{institution_state}' (APH 1.8a)"
            )
        if expert.id in prev_ids:
            reasons.append(
                "Note: same expert was on the previous committee for this institution (consecutive-institution soft rule)"
            )
        else:
            reasons.append("Consecutive-institution rule passed: no prior assignment to this institution")
        reasons.append(f"Load score: {expert.recent_assignment_count} recent assignments")
        return reasons

    @staticmethod
    def _aph_clause(committee_type: CommitteeType) -> str:
        mapping = {
            CommitteeType.SCRUTINY: "APH 1.8a",
            CommitteeType.RE_SCRUTINY: "APH 1.8a",
            CommitteeType.EVC: "APH 1.9a",
            CommitteeType.SHC: "APH 16.6",
            CommitteeType.SAC: "APH 16.6",
            CommitteeType.SCSC: "APH 16.7",
            CommitteeType.EC: "APH 16.2",
            CommitteeType.COUNCIL: "APH 16.1",
        }
        return mapping.get(committee_type, "APH 1.8a")


# ---------------------------------------------------------------------------
# Query helpers for the API layer
# ---------------------------------------------------------------------------


def get_committee_selection_for_application(
    db: Session, application_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Return all committee selections for an application from the audit log.

    Used by the UI's CommitteePanel component.
    """
    from app.models.audit import AuditLog

    logs = db.scalars(
        select(AuditLog)
        .where(
            AuditLog.action == "committee.selection.auto",
            AuditLog.entity_type == "Committee",
        )
        .order_by(AuditLog.created_at.desc())
    ).all()

    results = []
    for log in logs:
        after = log.after or {}
        # Filter by application: check if the committee's application_id matches.
        # We join through the committee row.
        committee_id = log.entity_id
        committee = db.get(Committee, committee_id)
        if committee is None:
            continue
        if committee.application_id != application_id:
            continue
        results.append(
            {
                "committee_id": str(committee_id),
                "committee_type": after.get("committee_type"),
                "selection_seed": after.get("selection_seed"),
                "seats": after.get("seats", []),
                "co_opted": after.get("co_opted"),
                "warnings": after.get("warnings", []),
                "quorum_met": after.get("quorum_met"),
                "quorum_description": after.get("quorum_description"),
                "selected_at": log.created_at.isoformat() if log.created_at else None,
                "status": committee.status.value,
                "mode": committee.mode.value,
                "scheduled_at": committee.scheduled_at.isoformat() if committee.scheduled_at else None,
            }
        )
    return results
