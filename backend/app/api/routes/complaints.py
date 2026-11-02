"""Complaint, penal-action and excess-admission fine endpoints (APH Chapter VII).

Access control:
* intake and show-cause reply - INSTITUTION_ADMIN (own institution) and SUPER_ADMIN;
* verification - REGULATION_BUREAU_OFFICER, COMPLAINT_SCRUTINY_MEMBER, SUPER_ADMIN;
* SCSC decision - COMPLAINT_SCRUTINY_MEMBER, SUPER_ADMIN;
* SHC hearing - SHC_MEMBER, SUPER_ADMIN;
* EC decision and issuing an action - EXECUTIVE_COMMITTEE_MEMBER, SUPER_ADMIN;
* restoration request - INSTITUTION_ADMIN, SUPER_ADMIN.

Every state change goes through :mod:`app.services.complaints` or
:mod:`app.services.penal_actions`, and every write is audited.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import false, func, select
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import AuditDep, CurrentUser, DbSession, require_roles
from app.models.application import Application
from app.models.complaint import Complaint, PenalAction
from app.models.enums import PenalActionType, Role
from app.models.institution import Institution
from app.models.user import User
from app.schemas.complaints import (
    ComplaintCatalogue,
    ComplaintCreate,
    ComplaintLifecycleStep,
    ComplaintPage,
    ComplaintRead,
    EcDecisionRequest,
    ExcessAdmissionFineRead,
    PenalActionCreate,
    PenalActionHearingRequest,
    PenalActionIssueRequest,
    PenalActionRead,
    RestorationRequest,
    ScscDecisionRequest,
    ShcHearingRequest,
    ShowCauseReplyRequest,
)
from app.services import complaints as complaint_service
from app.services import penal_actions as penal_service

router = APIRouter(tags=["complaints"])

_COMMITTEE_WIDE = frozenset(
    {
        Role.SHC_MEMBER,
        Role.SAC_MEMBER,
        Role.EXECUTIVE_COMMITTEE_MEMBER,
        Role.COMPLAINT_SCRUTINY_MEMBER,
    }
)

_INTAKE_ROLES = (Role.INSTITUTION_ADMIN, Role.REGULATION_BUREAU_OFFICER, Role.SUPER_ADMIN)
_VERIFY_ROLES = (
    Role.REGULATION_BUREAU_OFFICER,
    Role.COMPLAINT_SCRUTINY_MEMBER,
    Role.SUPER_ADMIN,
)
_SCSC_ROLES = (Role.COMPLAINT_SCRUTINY_MEMBER, Role.SUPER_ADMIN)
_SHC_ROLES = (Role.SHC_MEMBER, Role.SUPER_ADMIN)
_EC_ROLES = (Role.EXECUTIVE_COMMITTEE_MEMBER, Role.SUPER_ADMIN)
_RESTORATION_ROLES = (Role.INSTITUTION_ADMIN, Role.SUPER_ADMIN)


def _complaint_scope(user: User):
    """Return SQL conditions limiting complaints to the caller's visibility."""
    if user.role == Role.SUPER_ADMIN or user.role in _COMMITTEE_WIDE:
        return []
    if user.role == Role.INSTITUTION_ADMIN:
        if user.institution_id is None:
            return [false()]
        return [Complaint.institution_id == user.institution_id]
    if user.role == Role.REGULATION_BUREAU_OFFICER:
        if user.region is None:
            return []
        return [Complaint.institution.has(Institution.region == user.region)]
    if user.role == Role.REGIONAL_OFFICER:
        if user.region is None:
            return [false()]
        return [Complaint.institution.has(Institution.region == user.region)]
    return [false()]


def _load_complaint(db: Session, complaint_id: uuid.UUID) -> Complaint:
    complaint = db.scalar(
        select(Complaint)
        .options(joinedload(Complaint.institution))
        .where(Complaint.id == complaint_id)
    )
    if complaint is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Complaint not found")
    return complaint


def _readable_complaint(db: Session, user: User, complaint_id: uuid.UUID) -> Complaint:
    if user.role != Role.SUPER_ADMIN and user.role not in _COMMITTEE_WIDE:
        if user.role not in {
            Role.INSTITUTION_ADMIN,
            Role.REGULATION_BUREAU_OFFICER,
            Role.REGIONAL_OFFICER,
        }:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot read this complaint")
    complaint = _load_complaint(db, complaint_id)
    if user.role == Role.INSTITUTION_ADMIN and complaint.institution_id != user.institution_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Complaint not found")
    if user.role == Role.REGULATION_BUREAU_OFFICER and user.region is not None:
        if complaint.institution.region != user.region:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Complaint not found")
    if user.role == Role.REGIONAL_OFFICER:
        if user.region is None or complaint.institution.region != user.region:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Complaint not found")
    return complaint


def _load_penal_action(db: Session, penal_action_id: uuid.UUID) -> PenalAction:
    penal_action = db.get(PenalAction, penal_action_id)
    if penal_action is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Penal action not found")
    return penal_action


def _institution_for_user(
    db: Session, user: User, body_institution_id: uuid.UUID | None
) -> Institution:
    target = body_institution_id or user.institution_id
    if target is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "An institution is required to record this complaint.",
        )
    if user.role == Role.INSTITUTION_ADMIN and target != user.institution_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You may only act for your own institution")
    institution = db.get(Institution, target)
    if institution is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Institution not found")
    return institution


def _commit(db: Session) -> None:
    db.commit()


def _bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


# ---------------------------------------------------------------------------
# Catalogue and listing
# ---------------------------------------------------------------------------


@router.get(
    "/complaints/catalogue",
    response_model=ComplaintCatalogue,
    summary="Complaint lifecycle and anonymity rule (APH 7.10)",
)
def complaint_catalogue(_: CurrentUser) -> ComplaintCatalogue:
    """Return the visible complaint steps and the APH 7.10h rule."""
    return ComplaintCatalogue(
        steps=[ComplaintLifecycleStep(**step) for step in complaint_service.lifecycle()],
        anonymity_clause=complaint_service.ANONYMITY_CLAUSE,
        anonymity_reason=complaint_service.ANONYMITY_REASON,
        scsc_decisions=dict(complaint_service.SCSC_DECISIONS),
        ec_decisions=dict(complaint_service.EC_DECISIONS),
    )


@router.get(
    "/complaints",
    response_model=ComplaintPage,
    summary="List complaints visible to the caller (APH 7.10)",
)
def list_complaints(
    db: DbSession,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
) -> ComplaintPage:
    """Return a role-scoped, paginated complaint list."""
    conditions = _complaint_scope(user)
    query = select(Complaint).options(joinedload(Complaint.institution))
    count_query = select(func.count(Complaint.id))
    if conditions:
        query = query.where(*conditions)
        count_query = count_query.where(*conditions)
    if status_filter:
        query = query.where(Complaint.status == status_filter)
        count_query = count_query.where(Complaint.status == status_filter)
    total = int(db.scalar(count_query) or 0)
    rows = list(
        db.scalars(
            query.order_by(Complaint.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return ComplaintPage(
        items=[ComplaintRead.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post(
    "/complaints",
    response_model=ComplaintRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record a complaint, auto-rejecting anonymous ones (APH 7.10h)",
    dependencies=[Depends(require_roles(*_INTAKE_ROLES))],
)
def create_complaint(
    body: ComplaintCreate,
    db: DbSession,
    user: CurrentUser,
    audit: AuditDep,
    request: Request,
) -> ComplaintRead:
    """Record a complaint; anonymous or pseudonymous intake is rejected at once."""
    institution = _institution_for_user(db, user, body.institution_id)
    application: Application | None = None
    if body.application_id is not None:
        application = db.get(Application, body.application_id)
        if application is None or application.institution_id != institution.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    try:
        complaint = complaint_service.create_complaint(
            db,
            institution=institution,
            application=application,
            source=body.source,
            category=body.category,
            description=body.description,
            received_on=body.received_on or datetime.now(UTC).date(),
            complainant_name=body.complainant_name,
            complainant_contact=body.complainant_contact,
            is_anonymous=body.is_anonymous,
            actor=user,
            audit=audit,
            request=request,
        )
    except complaint_service.ComplaintError as exc:
        raise _bad_request(exc) from exc
    _commit(db)
    db.refresh(complaint)
    return ComplaintRead.model_validate(complaint)


@router.get(
    "/complaints/{complaint_id}",
    response_model=ComplaintRead,
    summary="Read one complaint (APH 7.10)",
)
def get_complaint(complaint_id: uuid.UUID, db: DbSession, user: CurrentUser) -> ComplaintRead:
    return ComplaintRead.model_validate(_readable_complaint(db, user, complaint_id))


# ---------------------------------------------------------------------------
# Complaint lifecycle
# ---------------------------------------------------------------------------


@router.post(
    "/complaints/{complaint_id}/verify",
    response_model=ComplaintRead,
    summary="Verify the complaint and place it before the SCSC (APH 7.10c)",
    dependencies=[Depends(require_roles(*_VERIFY_ROLES))],
)
def verify_complaint(
    complaint_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    audit: AuditDep,
    request: Request,
) -> ComplaintRead:
    complaint = _readable_complaint(db, user, complaint_id)
    try:
        complaint_service.verify_complaint(db, complaint, actor=user, audit=audit, request=request)
    except complaint_service.ComplaintError as exc:
        raise _bad_request(exc) from exc
    _commit(db)
    db.refresh(complaint)
    return ComplaintRead.model_validate(complaint)


@router.post(
    "/complaints/{complaint_id}/scsc-decision",
    response_model=ComplaintRead,
    summary="Record the SCSC decision (APH 7.10c)",
    dependencies=[Depends(require_roles(*_SCSC_ROLES))],
)
def record_scsc_decision(
    complaint_id: uuid.UUID,
    body: ScscDecisionRequest,
    db: DbSession,
    user: CurrentUser,
    audit: AuditDep,
    request: Request,
) -> ComplaintRead:
    complaint = _readable_complaint(db, user, complaint_id)
    try:
        complaint_service.record_scsc_decision(
            db,
            complaint,
            decision=body.decision,
            notes=body.notes,
            decided_on=body.decided_on or datetime.now(UTC).date(),
            actor=user,
            audit=audit,
            request=request,
        )
    except complaint_service.ComplaintError as exc:
        raise _bad_request(exc) from exc
    _commit(db)
    db.refresh(complaint)
    return ComplaintRead.model_validate(complaint)


@router.post(
    "/complaints/{complaint_id}/show-cause-reply",
    response_model=ComplaintRead,
    summary="Record the institution's show-cause reply (APH 7.10d)",
    dependencies=[Depends(require_roles(Role.INSTITUTION_ADMIN, Role.SUPER_ADMIN))],
)
def record_show_cause_reply(
    complaint_id: uuid.UUID,
    body: ShowCauseReplyRequest,
    db: DbSession,
    user: CurrentUser,
    audit: AuditDep,
    request: Request,
) -> ComplaintRead:
    complaint = _readable_complaint(db, user, complaint_id)
    try:
        complaint_service.record_show_cause_reply(
            db,
            complaint,
            reply=body.reply,
            replied_on=body.replied_on or datetime.now(UTC).date(),
            actor=user,
            audit=audit,
            request=request,
        )
    except complaint_service.ComplaintError as exc:
        raise _bad_request(exc) from exc
    _commit(db)
    db.refresh(complaint)
    return ComplaintRead.model_validate(complaint)


@router.post(
    "/complaints/{complaint_id}/shc-hearing",
    response_model=ComplaintRead,
    summary="Record the SHC hearing and findings (APH 7.10d-e)",
    dependencies=[Depends(require_roles(*_SHC_ROLES))],
)
def record_shc_hearing(
    complaint_id: uuid.UUID,
    body: ShcHearingRequest,
    db: DbSession,
    user: CurrentUser,
    audit: AuditDep,
    request: Request,
) -> ComplaintRead:
    complaint = _readable_complaint(db, user, complaint_id)
    try:
        complaint_service.record_shc_hearing(
            db,
            complaint,
            hearing_on=body.hearing_on,
            findings=body.findings,
            actor=user,
            audit=audit,
            request=request,
        )
    except complaint_service.ComplaintError as exc:
        raise _bad_request(exc) from exc
    _commit(db)
    db.refresh(complaint)
    return ComplaintRead.model_validate(complaint)


@router.post(
    "/complaints/{complaint_id}/ec-decision",
    response_model=ComplaintRead,
    summary="Record the EC decision and Speaking Order (APH 7.10f-g)",
    dependencies=[Depends(require_roles(*_EC_ROLES))],
)
def record_ec_decision(
    complaint_id: uuid.UUID,
    body: EcDecisionRequest,
    db: DbSession,
    user: CurrentUser,
    audit: AuditDep,
    request: Request,
) -> ComplaintRead:
    complaint = _readable_complaint(db, user, complaint_id)
    try:
        complaint_service.record_ec_decision(
            db,
            complaint,
            decision=body.decision,
            speaking_order=body.speaking_order,
            decided_on=body.decided_on or datetime.now(UTC).date(),
            actor=user,
            audit=audit,
            request=request,
        )
    except complaint_service.ComplaintError as exc:
        raise _bad_request(exc) from exc
    _commit(db)
    db.refresh(complaint)
    return ComplaintRead.model_validate(complaint)


# ---------------------------------------------------------------------------
# Penal actions
# ---------------------------------------------------------------------------


@router.get(
    "/penal-actions/catalogue",
    summary="List the APH 7.4 violation code catalogue",
)
def penal_catalogue(_: CurrentUser) -> list[dict[str, object]]:
    return penal_service.catalogue()


@router.get(
    "/complaints/{complaint_id}/penal-actions",
    response_model=list[PenalActionRead],
    summary="List the penal actions linked to a complaint (APH 7.3)",
)
def list_complaint_penal_actions(
    complaint_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> list[PenalActionRead]:
    _readable_complaint(db, user, complaint_id)
    rows = db.scalars(
        select(PenalAction)
        .where(PenalAction.complaint_id == complaint_id)
        .order_by(PenalAction.created_at.desc())
    ).all()
    return [PenalActionRead.model_validate(row) for row in rows]


@router.post(
    "/complaints/{complaint_id}/penal-actions",
    response_model=PenalActionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record a draft APH 7.3 penal action (APH 7.4)",
    dependencies=[Depends(require_roles(Role.EXECUTIVE_COMMITTEE_MEMBER, Role.SUPER_ADMIN))],
)
def record_penal_action(
    complaint_id: uuid.UUID,
    body: PenalActionCreate,
    db: DbSession,
    user: CurrentUser,
    audit: AuditDep,
    request: Request,
) -> PenalActionRead:
    complaint = _readable_complaint(db, user, complaint_id)
    try:
        action_type = PenalActionType(body.action_type.strip().upper())
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown APH 7.3 action type") from exc
    application = complaint.application
    try:
        penal_action = penal_service.record_penal_action(
            db,
            institution=complaint.institution,
            action_type=action_type,
            violation_code=body.violation_code,
            application=application,
            complaint=complaint,
            effective_academic_year=body.effective_academic_year,
            actor=user,
            audit=audit,
            request=request,
        )
    except penal_service.PenalActionError as exc:
        raise _bad_request(exc) from exc
    _commit(db)
    db.refresh(penal_action)
    return PenalActionRead.model_validate(penal_action)


@router.get(
    "/penal-actions/{penal_action_id}",
    response_model=PenalActionRead,
    summary="Read one penal action (APH 7.3)",
)
def get_penal_action(
    penal_action_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> PenalActionRead:
    penal_action = _load_penal_action(db, penal_action_id)
    if user.role == Role.INSTITUTION_ADMIN and penal_action.institution_id != user.institution_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Penal action not found")
    return PenalActionRead.model_validate(penal_action)


@router.post(
    "/penal-actions/{penal_action_id}/hearing",
    response_model=PenalActionRead,
    summary="Schedule the mandatory pre-action hearing (APH 6.50h)",
    dependencies=[Depends(require_roles(*_SHC_ROLES))],
)
def schedule_penal_action_hearing(
    penal_action_id: uuid.UUID,
    body: PenalActionHearingRequest,
    db: DbSession,
    user: CurrentUser,
    audit: AuditDep,
    request: Request,
) -> PenalActionRead:
    penal_action = _load_penal_action(db, penal_action_id)
    try:
        penal_service.schedule_hearing(
            db,
            penal_action,
            hearing_on=body.hearing_on,
            notes=body.notes,
            actor=user,
            audit=audit,
            request=request,
        )
    except penal_service.PenalActionError as exc:
        raise _bad_request(exc) from exc
    _commit(db)
    db.refresh(penal_action)
    return PenalActionRead.model_validate(penal_action)


@router.post(
    "/penal-actions/{penal_action_id}/issue",
    response_model=PenalActionRead,
    summary="Issue the action after a hearing (APH 6.50h proviso)",
    dependencies=[Depends(require_roles(*_EC_ROLES))],
)
def issue_penal_action(
    penal_action_id: uuid.UUID,
    body: PenalActionIssueRequest,
    db: DbSession,
    user: CurrentUser,
    audit: AuditDep,
    request: Request,
) -> PenalActionRead:
    penal_action = _load_penal_action(db, penal_action_id)
    try:
        penal_service.issue_penal_action(
            db,
            penal_action,
            order_number=body.order_number,
            issued_on=body.issued_on or datetime.now(UTC).date(),
            speaking_order=body.speaking_order,
            actor=user,
            audit=audit,
            request=request,
        )
    except penal_service.PenalActionError as exc:
        raise _bad_request(exc) from exc
    _commit(db)
    db.refresh(penal_action)
    return PenalActionRead.model_validate(penal_action)


@router.post(
    "/penal-actions/{penal_action_id}/restoration-request",
    response_model=PenalActionRead,
    summary="Request restoration against a punitive action (APH 7.11a)",
    dependencies=[Depends(require_roles(*_RESTORATION_ROLES))],
)
def request_restoration(
    penal_action_id: uuid.UUID,
    body: RestorationRequest,
    db: DbSession,
    user: CurrentUser,
    audit: AuditDep,
    request: Request,
) -> PenalActionRead:
    penal_action = _load_penal_action(db, penal_action_id)
    if user.role == Role.INSTITUTION_ADMIN and penal_action.institution_id != user.institution_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Penal action not found")
    try:
        penal_service.request_restoration(
            db,
            penal_action,
            requested_on=body.requested_on or datetime.now(UTC).date(),
            actor=user,
            audit=audit,
            request=request,
        )
    except penal_service.PenalActionError as exc:
        raise _bad_request(exc) from exc
    _commit(db)
    db.refresh(penal_action)
    return PenalActionRead.model_validate(penal_action)


# ---------------------------------------------------------------------------
# Excess-admission fine preview
# ---------------------------------------------------------------------------


@router.get(
    "/applications/{application_id}/excess-admission-fine",
    response_model=ExcessAdmissionFineRead,
    summary="Preview the APH 7.3g fine from the approved-intake ledger",
)
def get_excess_admission_fine(
    application_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> ExcessAdmissionFineRead:
    application = db.get(Application, application_id)
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    if user.role == Role.INSTITUTION_ADMIN and application.institution_id != user.institution_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    try:
        fine = penal_service.calculate_excess_admission_fine(
            db, application, institution_id=application.institution_id
        )
    except penal_service.PenalActionError as exc:
        raise _bad_request(exc) from exc
    return ExcessAdmissionFineRead(
        academic_year=fine.academic_year,
        excess_admissions=fine.excess_admissions,
        annual_fee_paise=fine.annual_fee_paise,
        total_course_fee_paise=fine.total_course_fee_paise,
        fine_paise=fine.fine_paise,
        lines=list(fine.lines),
        apH_clause=fine.apH_clause,
    )
