"""Unauthenticated statistics used by the login first impression."""

from fastapi import APIRouter, Request
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.api.dependencies import DbSession
from app.models.application import Application
from app.models.enums import ApplicationStatus, Role
from app.schemas.public import PublicDemoAccount, PublicStats

router = APIRouter(prefix="/public", tags=["public"])

_IN_PROGRESS_STATUSES = (
    ApplicationStatus.SUBMITTED,
    ApplicationStatus.DOCUMENT_VERIFICATION,
    ApplicationStatus.SCRUTINY,
    ApplicationStatus.DEFICIENCY_RAISED,
    ApplicationStatus.DEFICIENCY_RESPONDED,
    ApplicationStatus.INSPECTION_SCHEDULED,
    ApplicationStatus.INSPECTION_DONE,
    ApplicationStatus.COMMITTEE_REVIEW,
)
_DECIDED_STATUSES = (
    ApplicationStatus.APPROVED,
    ApplicationStatus.CONDITIONALLY_APPROVED,
    ApplicationStatus.REJECTED,
)
_DEMO_ACCOUNT_SPECS = (
    (Role.INSTITUTION_ADMIN, "Institution administrator", "institution@example.edu"),
    (
        Role.REGULATION_BUREAU_OFFICER,
        "Regulation Bureau officer",
        "regulation@example.edu",
    ),
    (
        Role.SCRUTINY_COMMITTEE_MEMBER,
        "Scrutiny Committee member",
        "scrutiny@example.edu",
    ),
    (Role.EVC_MEMBER, "Expert Visit Committee member", "inspection@example.edu"),
    (Role.REGIONAL_OFFICER, "Regional Officer", "regional@example.edu"),
    (Role.SHC_MEMBER, "Standing Hearing Committee member", "shc@example.edu"),
    (Role.SAC_MEMBER, "Standing Appellate Committee member", "sac@example.edu"),
    (
        Role.EXECUTIVE_COMMITTEE_MEMBER,
        "Executive Committee member",
        "ec@example.edu",
    ),
    (
        Role.COMPLAINT_SCRUTINY_MEMBER,
        "Standing Complaint Scrutiny Committee member",
        "complaints@example.edu",
    ),
    (Role.SUPER_ADMIN, "Super administrator", ""),
)


def _average_days_to_decision(db: Session) -> float | None:
    """Return the mean elapsed time between submission and a recorded decision.

    The application model has no separate ``decided_at`` column in this
    prototype, so the last update timestamp is used for decided records.
    """
    rows = db.execute(
        select(Application.submitted_at, Application.updated_at).where(
            Application.status.in_(_DECIDED_STATUSES),
            Application.submitted_at.is_not(None),
        )
    ).all()
    durations = [
        (updated_at - submitted_at).total_seconds() / 86_400
        for submitted_at, updated_at in rows
        if submitted_at is not None and updated_at is not None and updated_at >= submitted_at
    ]
    if not durations:
        return None
    return round(sum(durations) / len(durations), 1)


@router.get(
    "/stats",
    response_model=PublicStats,
    summary="Return public login statistics and demo access details",
)
def public_stats(request: Request, db: DbSession) -> PublicStats:
    """Return live seeded-data figures without requiring authentication."""
    settings = request.app.state.settings
    now = request.app.state.clock.now()

    applications_in_progress = (
        db.scalar(
            select(func.count(Application.id)).where(
                Application.status.in_(_IN_PROGRESS_STATUSES),
                Application.is_withdrawn.is_(False),
            )
        )
        or 0
    )
    institutions_needing_attention = (
        db.scalar(
            select(func.count(distinct(Application.institution_id))).where(
                Application.status.in_(_IN_PROGRESS_STATUSES),
                Application.is_withdrawn.is_(False),
                Application.sla_due_at.is_not(None),
                Application.sla_due_at < now,
            )
        )
        or 0
    )

    demo_accounts: list[PublicDemoAccount] = []
    if settings.demo_mode:
        demo_password = settings.seed_demo_password.get_secret_value()
        admin_password = settings.seed_admin_password.get_secret_value()
        for role, label, email in _DEMO_ACCOUNT_SPECS:
            is_admin = role is Role.SUPER_ADMIN
            demo_accounts.append(
                PublicDemoAccount(
                    role=role,
                    label=label,
                    email=settings.seed_admin_email if is_admin else email,
                    password=admin_password if is_admin else demo_password,
                )
            )

    return PublicStats(
        applications_in_progress=applications_in_progress,
        average_days_to_decision=_average_days_to_decision(db),
        institutions_needing_attention=institutions_needing_attention,
        demo_mode=settings.demo_mode,
        demo_accounts=demo_accounts,
        as_of=now,
    )
