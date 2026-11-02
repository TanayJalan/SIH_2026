"""Security Deposit release endpoints (APH 6.46).

The institution requests release and uploads the 6.46a documents; PGRC, the
Vigilance Cell and the grants cell record clearances (6.46b); the Approval
Bureau or Council issues the NOC/sanction order (6.46c-d). A deposit that is
still unpaid cannot be released.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import AuditDep, CurrentUser, DbSession, require_roles
from app.models.application import Application
from app.models.enums import Role
from app.models.security_deposit import SecurityDeposit
from app.models.user import User
from app.schemas.complaints import (
    DepositClearanceRequest,
    DepositReleaseApproveRequest,
    DepositReleaseRequest,
    SecurityDepositRead,
)
from app.services.authorization import can_access_application
from app.services.deposit_release import (
    DepositReleaseError,
    approve_release,
    clearance_catalogue,
    record_clearance,
    request_release,
    withdraw_deposit,
)

router = APIRouter(tags=["security deposits"])

_CLEARANCE_ROLES = (
    Role.REGULATION_BUREAU_OFFICER,
    Role.COMPLAINT_SCRUTINY_MEMBER,
    Role.SUPER_ADMIN,
)
_APPROVE_ROLES = (Role.REGIONAL_OFFICER, Role.SUPER_ADMIN)


def _readable_application(db: Session, user: User, application_id: uuid.UUID) -> Application:
    application = db.scalar(
        select(Application)
        .options(joinedload(Application.institution))
        .where(Application.id == application_id)
    )
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    if not can_access_application(db, user, application):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return application


def _load_deposit(db: Session, application: Application, deposit_id: uuid.UUID) -> SecurityDeposit:
    deposit = db.get(SecurityDeposit, deposit_id)
    if deposit is None or deposit.application_id != application.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Security Deposit not found")
    return deposit


def _bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.get(
    "/security-deposit-clearances",
    summary="Security Deposit release documents and clearances (APH 6.46)",
)
def get_clearance_catalogue(_: CurrentUser) -> list[dict[str, object]]:
    return clearance_catalogue()


@router.get(
    "/applications/{application_id}/security-deposits",
    response_model=list[SecurityDepositRead],
    summary="List the Security Deposits on an application (APH 1.12, 6.46)",
)
def list_security_deposits(
    application_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> list[SecurityDepositRead]:
    application = _readable_application(db, user, application_id)
    rows = db.scalars(
        select(SecurityDeposit)
        .where(SecurityDeposit.application_id == application.id)
        .order_by(SecurityDeposit.created_on.desc())
    ).all()
    return [SecurityDepositRead.model_validate(row) for row in rows]


@router.post(
    "/applications/{application_id}/security-deposits/{deposit_id}/release-request",
    response_model=SecurityDepositRead,
    summary="Request release of the Security Deposit (APH 6.46a)",
    dependencies=[Depends(require_roles(Role.INSTITUTION_ADMIN, Role.SUPER_ADMIN))],
)
def create_release_request(
    application_id: uuid.UUID,
    deposit_id: uuid.UUID,
    body: DepositReleaseRequest,
    db: DbSession,
    user: CurrentUser,
    audit: AuditDep,
    request: Request,
) -> SecurityDepositRead:
    application = _readable_application(db, user, application_id)
    deposit = _load_deposit(db, application, deposit_id)
    try:
        request_release(
            db,
            deposit,
            requested_on=body.requested_on or datetime.now(UTC).date(),
            actor=user,
            audit=audit,
            request=request,
        )
    except DepositReleaseError as exc:
        raise _bad_request(exc) from exc
    db.commit()
    db.refresh(deposit)
    return SecurityDepositRead.model_validate(deposit)


@router.post(
    "/applications/{application_id}/security-deposits/{deposit_id}/clearance",
    response_model=SecurityDepositRead,
    summary="Record a PGRC/Vigilance/grants clearance (APH 6.46b)",
    dependencies=[Depends(require_roles(*_CLEARANCE_ROLES))],
)
def create_clearance(
    application_id: uuid.UUID,
    deposit_id: uuid.UUID,
    body: DepositClearanceRequest,
    db: DbSession,
    user: CurrentUser,
    audit: AuditDep,
    request: Request,
) -> SecurityDepositRead:
    application = _readable_application(db, user, application_id)
    deposit = _load_deposit(db, application, deposit_id)
    try:
        record_clearance(
            db,
            deposit,
            code=body.code,
            cleared=body.cleared,
            remarks=body.remarks,
            actor=user,
            audit=audit,
            request=request,
        )
    except DepositReleaseError as exc:
        raise _bad_request(exc) from exc
    db.commit()
    db.refresh(deposit)
    return SecurityDepositRead.model_validate(deposit)


@router.post(
    "/applications/{application_id}/security-deposits/{deposit_id}/release",
    response_model=SecurityDepositRead,
    summary="Approve the release and record the NOC (APH 6.46c-d)",
    dependencies=[Depends(require_roles(*_APPROVE_ROLES))],
)
def approve_deposit_release(
    application_id: uuid.UUID,
    deposit_id: uuid.UUID,
    body: DepositReleaseApproveRequest,
    db: DbSession,
    user: CurrentUser,
    audit: AuditDep,
    request: Request,
) -> SecurityDepositRead:
    application = _readable_application(db, user, application_id)
    deposit = _load_deposit(db, application, deposit_id)
    try:
        approve_release(
            db,
            deposit,
            released_on=body.released_on or datetime.now(UTC).date(),
            noc_number=body.noc_number,
            actor=user,
            audit=audit,
            request=request,
        )
    except DepositReleaseError as exc:
        raise _bad_request(exc) from exc
    db.commit()
    db.refresh(deposit)
    return SecurityDepositRead.model_validate(deposit)


@router.post(
    "/applications/{application_id}/security-deposits/{deposit_id}/withdraw",
    response_model=SecurityDepositRead,
    summary="Mark the Security Deposit withdrawn (APH 2.25f)",
    dependencies=[Depends(require_roles(Role.INSTITUTION_ADMIN, Role.SUPER_ADMIN))],
)
def withdraw_security_deposit(
    application_id: uuid.UUID,
    deposit_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    audit: AuditDep,
    request: Request,
) -> SecurityDepositRead:
    application = _readable_application(db, user, application_id)
    deposit = _load_deposit(db, application, deposit_id)
    try:
        withdraw_deposit(db, deposit, actor=user, audit=audit, request=request)
    except DepositReleaseError as exc:
        raise _bad_request(exc) from exc
    db.commit()
    db.refresh(deposit)
    return SecurityDepositRead.model_validate(deposit)
