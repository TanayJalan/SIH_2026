"""Committee selection and expert pool API endpoints.

Access control (APH_SPEC section 1, docs/RBAC.md):
* ``POST /committees/select`` – REGULATION_BUREAU_OFFICER, REGIONAL_OFFICER, SUPER_ADMIN
* ``GET  /committees/application/{application_id}`` – role-scoped (same as applications)
* ``GET  /committees/{committee_id}`` – role-scoped
* ``GET  /committees/quorum/{committee_type}`` – authenticated
* ``GET  /expert-pool`` – REGULATION_BUREAU_OFFICER, SCRUTINY_COMMITTEE_MEMBER, EVC_MEMBER,
  REGIONAL_OFFICER, SHC_MEMBER, SAC_MEMBER, EXECUTIVE_COMMITTEE_MEMBER,
  COMPLAINT_SCRUTINY_MEMBER, SUPER_ADMIN  (all except INSTITUTION_ADMIN)

APH clause: APH 1.8a (Scrutiny automated selection), APH 1.9a (EVC),
Annexure-16 sections 16.2–16.7.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import AuditDep, CurrentUser, DbSession, require_roles
from app.models.application import Application
from app.models.committee import Committee
from app.models.complaint import Complaint
from app.models.enums import CommitteeMode, CommitteeType, Role
from app.models.expert_pool import ExpertPool
from app.schemas.committee import (
    CommitteeSelectRequest,
    CommitteeSelectionOut,
    ExpertPoolOut,
    QuorumCheckOut,
    SeatSelectionOut,
)
from app.services.authorization import can_access_application
from app.services.committee import (
    CommitteeService,
    get_committee_selection_for_application,
)

router = APIRouter(tags=["committees"])

_SELECTION_ROLES = (
    Role.REGULATION_BUREAU_OFFICER,
    Role.REGIONAL_OFFICER,
    Role.SUPER_ADMIN,
)

_PANEL_ROLES = (
    Role.REGULATION_BUREAU_OFFICER,
    Role.SCRUTINY_COMMITTEE_MEMBER,
    Role.EVC_MEMBER,
    Role.REGIONAL_OFFICER,
    Role.SHC_MEMBER,
    Role.SAC_MEMBER,
    Role.EXECUTIVE_COMMITTEE_MEMBER,
    Role.COMPLAINT_SCRUTINY_MEMBER,
    Role.SUPER_ADMIN,
)


# ---------------------------------------------------------------------------
# Expert pool
# ---------------------------------------------------------------------------


@router.get(
    "/expert-pool",
    response_model=list[ExpertPoolOut],
    summary="List active members of the expert panel (APH 1.8a, 1.9a)",
    dependencies=[Depends(require_roles(*_PANEL_ROLES))],
)
def list_expert_pool(
    db: DbSession,
    active_only: bool = Query(True, description="Filter to active experts only"),
    state: str | None = Query(None, description="Filter by home state"),
    seat_tag: str | None = Query(None, description="Filter by seat tag"),
    limit: int = Query(100, ge=1, le=500),
) -> list[ExpertPoolOut]:
    """Return the expert panel.  All fictional entries are labelled ``is_fictional=True``.

    APH clause: APH 1.8a (experts for Scrutiny), APH 1.9a (EVC panel).
    """
    q = select(ExpertPool)
    if active_only:
        q = q.where(ExpertPool.is_active == True)  # noqa: E712
    if state:
        q = q.where(ExpertPool.state == state)
    if seat_tag:
        q = q.where(ExpertPool.seat_tags.contains([seat_tag]))
    q = q.order_by(ExpertPool.recent_assignment_count, ExpertPool.name).limit(limit)
    experts = list(db.scalars(q))
    return [ExpertPoolOut.model_validate(e) for e in experts]


@router.get(
    "/expert-pool/{expert_id}",
    response_model=ExpertPoolOut,
    summary="Get one expert-pool entry",
    dependencies=[Depends(require_roles(*_PANEL_ROLES))],
)
def get_expert(expert_id: uuid.UUID, db: DbSession) -> ExpertPoolOut:
    expert = db.get(ExpertPool, expert_id)
    if expert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expert not found")
    return ExpertPoolOut.model_validate(expert)


# ---------------------------------------------------------------------------
# Committee selection
# ---------------------------------------------------------------------------


@router.post(
    "/committees/select",
    response_model=CommitteeSelectionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Automatically select committee members (APH 1.8a / 1.9a)",
    dependencies=[Depends(require_roles(*_SELECTION_ROLES))],
)
def select_committee(
    body: CommitteeSelectRequest,
    current_user: CurrentUser,
    db: DbSession,
    audit: AuditDep,
) -> CommitteeSelectionOut:
    """Run the automated committee selection algorithm.

    Exactly one of *application_id* or *complaint_id* must be provided.
    The selection is deterministic when the same *selection_seed* is supplied,
    allowing replay for audit purposes (APH 1.8a).

    APH clause: APH 1.8a (Scrutiny), APH 1.9a (EVC), APH Annexure-16.
    """
    if (body.application_id is None) == (body.complaint_id is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Exactly one of application_id or complaint_id must be provided.",
        )

    application: Application | None = None
    complaint: Complaint | None = None

    if body.application_id is not None:
        application = db.get(Application, body.application_id)
        if application is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
        if not can_access_application(db, current_user, application):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if body.complaint_id is not None:
        complaint = db.get(Complaint, body.complaint_id)
        if complaint is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")

    try:
        ct = CommitteeType(body.committee_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown committee_type '{body.committee_type}'.",
        )

    try:
        mode = CommitteeMode(body.mode)
    except ValueError:
        mode = CommitteeMode.ONLINE

    svc = CommitteeService(db, audit)
    result = svc.select_committee(
        ct,
        application=application,
        complaint=complaint,
        selection_seed=body.selection_seed,
        include_co_opt=body.include_co_opt,
        scheduled_at=body.scheduled_at,
        mode=mode,
    )

    db.flush()

    # Build the committee row to get its id.
    committee = db.scalar(
        select(Committee)
        .where(
            Committee.selection_seed == result.selection_seed,
        )
        .order_by(Committee.created_at.desc())
        .limit(1)
    )
    if committee is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Committee row not found after selection.",
        )

    db.commit()

    return CommitteeSelectionOut(
        committee_id=committee.id,
        committee_type=result.committee_type.value,
        selection_seed=result.selection_seed,
        seats=[
            SeatSelectionOut(
                expert_id=s.expert_id,
                expert_name=s.expert_name,
                seat_label=s.seat_label,
                seat_role=s.seat_role,
                reasons=s.reasons,
            )
            for s in result.seats
        ],
        co_opted=(
            SeatSelectionOut(
                expert_id=result.co_opted.expert_id,
                expert_name=result.co_opted.expert_name,
                seat_label=result.co_opted.seat_label,
                seat_role=result.co_opted.seat_role,
                reasons=result.co_opted.reasons,
            )
            if result.co_opted
            else None
        ),
        quorum_required=result.quorum_required,
        quorum_description=result.quorum_description,
        quorum_met=result.quorum_met,
        warnings=result.warnings,
        status=committee.status.value,
        mode=committee.mode.value,
        scheduled_at=committee.scheduled_at,
        selected_at=committee.created_at,
    )


@router.get(
    "/committees/application/{application_id}",
    response_model=list[CommitteeSelectionOut],
    summary="Get all committee selections for an application",
)
def get_committees_for_application(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> list[CommitteeSelectionOut]:
    """Return committee selection history for an application.

    Used by the CaseFile CommitteePanel UI component.
    """
    application = db.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    if not can_access_application(db, current_user, application):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    raw = get_committee_selection_for_application(db, application_id)
    results: list[CommitteeSelectionOut] = []
    for r in raw:
        seats = [
            SeatSelectionOut(
                expert_id=uuid.UUID(s["expert_id"]),
                expert_name=s["expert_name"],
                seat_label=s["seat_label"],
                seat_role=s["seat_role"],
                reasons=s.get("reasons", []),
            )
            for s in r.get("seats", [])
        ]
        co_opted_raw = r.get("co_opted")
        co_opted = (
            SeatSelectionOut(
                expert_id=uuid.UUID(co_opted_raw["expert_id"]),
                expert_name=co_opted_raw["expert_name"],
                seat_label=co_opted_raw.get("seat_label", "CO_OPT"),
                seat_role="CO_OPT",
                reasons=co_opted_raw.get("reasons", []),
            )
            if co_opted_raw
            else None
        )
        results.append(
            CommitteeSelectionOut(
                committee_id=uuid.UUID(r["committee_id"]),
                committee_type=r.get("committee_type", ""),
                selection_seed=r.get("selection_seed", ""),
                seats=seats,
                co_opted=co_opted,
                quorum_required=r.get("quorum_required") or 0,
                quorum_description=r.get("quorum_description") or "",
                quorum_met=bool(r.get("quorum_met")),
                warnings=r.get("warnings", []),
                status=r.get("status", ""),
                mode=r.get("mode", "ONLINE"),
                scheduled_at=r.get("scheduled_at"),
                selected_at=r.get("selected_at"),
            )
        )
    return results


@router.get(
    "/committees/{committee_id}",
    response_model=CommitteeSelectionOut,
    summary="Get a committee by ID",
)
def get_committee(
    committee_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> CommitteeSelectionOut:
    committee = db.get(Committee, committee_id)
    if committee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Committee not found")

    # Access control: must be able to see the related application.
    if committee.application_id is not None:
        application = db.get(Application, committee.application_id)
        if application is None or not can_access_application(db, current_user, application):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Reconstruct from audit log.
    from app.models.audit import AuditLog

    log = db.scalar(
        select(AuditLog)
        .where(
            AuditLog.action == "committee.selection.auto",
            AuditLog.entity_id == committee_id,
        )
        .limit(1)
    )
    after = (log.after or {}) if log else {}
    seats = [
        SeatSelectionOut(
            expert_id=uuid.UUID(s["expert_id"]),
            expert_name=s["expert_name"],
            seat_label=s["seat_label"],
            seat_role=s["seat_role"],
            reasons=s.get("reasons", []),
        )
        for s in after.get("seats", [])
    ]
    co_opted_raw = after.get("co_opted")
    co_opted = (
        SeatSelectionOut(
            expert_id=uuid.UUID(co_opted_raw["expert_id"]),
            expert_name=co_opted_raw["expert_name"],
            seat_label=co_opted_raw.get("seat_label", "CO_OPT"),
            seat_role="CO_OPT",
            reasons=co_opted_raw.get("reasons", []),
        )
        if co_opted_raw
        else None
    )
    return CommitteeSelectionOut(
        committee_id=committee.id,
        committee_type=after.get("committee_type", committee.type.value),
        selection_seed=committee.selection_seed or "",
        seats=seats,
        co_opted=co_opted,
        quorum_required=after.get("quorum_required") or 0,
        quorum_description=after.get("quorum_description") or "",
        quorum_met=bool(after.get("quorum_met")),
        warnings=after.get("warnings", []),
        status=committee.status.value,
        mode=committee.mode.value,
        scheduled_at=committee.scheduled_at,
        selected_at=log.created_at if log else None,
    )


# ---------------------------------------------------------------------------
# Quorum check
# ---------------------------------------------------------------------------


@router.get(
    "/committees/quorum/{committee_type}",
    response_model=QuorumCheckOut,
    summary="Check quorum for a committee type (APH 16.2, 16.7)",
)
def check_quorum(
    committee_type: str,
    current_user: CurrentUser,
    db: DbSession,
    present_count: int = Query(ge=0, description="Number of members present"),
) -> QuorumCheckOut:
    """Compute quorum status for a committee type.

    APH clause: APH 16.2 (EC: one third), APH 16.7 (SCSC: any two).
    """
    try:
        ct = CommitteeType(committee_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown committee_type '{committee_type}'.",
        )
    met, desc, required = CommitteeService.check_quorum(ct, present_count)

    clause_map = {
        CommitteeType.EC: "APH 16.2",
        CommitteeType.SCSC: "APH 16.7",
        CommitteeType.COUNCIL: "APH 16.1",
    }
    clause = clause_map.get(ct, "APH 16.3")

    return QuorumCheckOut(
        committee_type=ct.value,
        present_count=present_count,
        quorum_required=required,
        quorum_description=desc,
        quorum_met=met,
        apH_clause=clause,
    )
