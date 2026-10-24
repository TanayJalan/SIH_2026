"""Role-aware scoping rules for applications and audit records."""

from sqlalchemy import and_, false, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.models.application import Application
from app.models.audit import AuditLog
from app.models.enums import Role
from app.models.inspection import Inspection
from app.models.institution import Institution
from app.models.user import User


def application_scope(user: User) -> list[ColumnElement[bool]]:
    """Return SQL conditions limiting applications to the user's visibility."""
    if user.role == Role.SUPER_ADMIN:
        return []

    if user.role == Role.INSTITUTION_ADMIN:
        if user.institution_id is None:
            return [false()]
        return [Application.institution_id == user.institution_id]

    if user.role == Role.SCRUTINY_OFFICER:
        conditions: list[ColumnElement[bool]] = [Application.assigned_officer_id == user.id]
        if user.region is not None:
            conditions.append(Application.institution.has(Institution.region == user.region))
        return [or_(*conditions)]

    if user.role == Role.REGIONAL_HEAD:
        if user.region is None:
            return [false()]
        return [Application.institution.has(Institution.region == user.region)]

    if user.role == Role.INSPECTION_COMMITTEE:
        return [Application.inspections.any(Inspection.committee_id == user.id)]

    return [false()]


def institution_scope(user: User) -> list[ColumnElement[bool]]:
    """Return SQL conditions limiting institutions to the user's visibility."""
    if user.role == Role.SUPER_ADMIN:
        return []

    if user.role == Role.INSTITUTION_ADMIN:
        if user.institution_id is None:
            return [false()]
        return [Institution.id == user.institution_id]

    if user.role in {Role.SCRUTINY_OFFICER, Role.REGIONAL_HEAD}:
        if user.region is None:
            return [false()]
        return [Institution.region == user.region]

    if user.role == Role.INSPECTION_COMMITTEE:
        return [
            Institution.applications.any(
                Application.inspections.any(Inspection.committee_id == user.id)
            )
        ]

    return [false()]


def can_access_application(db: Session, user: User, application: Application) -> bool:
    """Return whether ``user`` may read ``application``."""
    if user.role == Role.SUPER_ADMIN:
        return True

    if user.role == Role.INSTITUTION_ADMIN:
        return user.institution_id is not None and application.institution_id == user.institution_id

    if user.role == Role.SCRUTINY_OFFICER:
        assigned = application.assigned_officer_id == user.id
        in_region = user.region is not None and application.institution.region == user.region
        return assigned or in_region

    if user.role == Role.REGIONAL_HEAD:
        return user.region is not None and application.institution.region == user.region

    if user.role == Role.INSPECTION_COMMITTEE:
        inspection_id = db.scalar(
            select(Inspection.id)
            .where(
                Inspection.application_id == application.id,
                Inspection.committee_id == user.id,
            )
            .limit(1)
        )
        return inspection_id is not None

    return False


def audit_log_scope(user: User) -> list[ColumnElement[bool]]:
    """Return SQL conditions limiting audit records to the user's region.

    Regional heads can see entries performed by users in their region and
    entries whose polymorphic entity is an institution, application or user in
    their region. Other entity types are covered through the actor clause.
    """
    if user.role == Role.SUPER_ADMIN:
        return []

    if user.role != Role.REGIONAL_HEAD or user.region is None:
        return [false()]

    institution_ids = select(Institution.id).where(Institution.region == user.region)
    application_ids = (
        select(Application.id)
        .join(Institution, Application.institution_id == Institution.id)
        .where(Institution.region == user.region)
    )
    user_ids = select(User.id).where(User.region == user.region)

    return [
        or_(
            AuditLog.actor.has(User.region == user.region),
            and_(
                AuditLog.entity_type == "Institution",
                AuditLog.entity_id.in_(institution_ids),
            ),
            and_(
                AuditLog.entity_type == "Application",
                AuditLog.entity_id.in_(application_ids),
            ),
            and_(
                AuditLog.entity_type == "User",
                AuditLog.entity_id.in_(user_ids),
            ),
        )
    ]
