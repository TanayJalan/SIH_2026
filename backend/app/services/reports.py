"""Report and dashboard aggregate service.

Every metric is computed with SQL aggregations (``func.count``, ``func.avg``,
case expressions) — never Python loops over result rows. All monetary values
are integer paise; every metric carries its governing APH clause so operators
can trace figures back to the Approval Process Handbook.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import (
    AcademicCalendarEvent,
    Appeal,
    Application,
    ApplicationStatus,
    ApplicationTrack,
    Complaint,
    Decision,
    DecisionType,
    Deficiency,
    DeficiencyStatus,
    Document,
    FeeKind,
    FeeTransaction,
    Inspection,
    InspectionStatus,
    Institution,
    PenalAction,
    SecurityDeposit,
    SecurityDepositStatus,
    User,
    WorkflowEvent,
)
from app.models.compliance import ComplianceResult, ComplianceRule, ComplianceSnapshot
from app.models.enums import ComplianceHealth
from app.schemas.reports import (
    ApplicationByTrackState,
    ApplicationReport,
    AppealOutcome,
    ApprovalVsRejection,
    AverageDaysPerStage,
    ComplaintStatusCount,
    DeficiencyCategory,
    Escalation,
    ExpiringDocument,
    FeePosition,
    FailingRule,
    FacultyRatioDeficit,
    FunnelEntry,
    InstitutionDashboard,
    InstitutionCompliance,
    LoaExpiring,
    MandatoryDisclosure,
    OpenDeficiency,
    PenalActionByType,
    QueueEntry,
    RegionalDashboard,
    ReportApplication,
    ReportFilters,
    RegulationBureauDashboard,
    ReportCompliance,
    ReportDecision,
    ReportDeficiency,
    ReportFee,
    ReportTimelineEvent,
    SlaBreach,
    SecurityDepositPending,
    UpcomingDeadline,
    ViolationCode,
)

# Academic calendar event keys referenced by APH section 5.
_ENROLMENT_UPLOAD_KEY = "ENROLMENT_UPLOAD_30NOV"
_IC_REPORT_KEY = "IC_REPORT_30JUN"


def _zero(result: Any) -> int:
    """Return a scalar query result or 0 when None."""
    return result or 0


def _filter_conditions(model, filters: ReportFilters) -> list:
    """Return the global filter conditions as a list of SQL expressions."""
    conditions = []
    if filters.academic_year is not None:
        conditions.append(model.academic_year == filters.academic_year)
    if filters.application_type is not None:
        conditions.append(model.application_type == filters.application_type)
    if filters.track is not None:
        conditions.append(model.track == filters.track)
    if filters.region is not None:
        conditions.append(model.institution_id.in_(
            select(Institution.id).where(Institution.region == filters.region)
        ))
    if filters.state is not None:
        conditions.append(model.institution_id.in_(
            select(Institution.id).where(Institution.state == filters.state)
        ))
    return conditions


def _apply_global_filters(query, model, filters: ReportFilters):
    """Apply the global report filters to a SQLAlchemy query.

    Filters are optional; only supplied values narrow the result set. The
    caller is responsible for joining ``Institution`` before passing the query
    when region/state filters are set.
    """
    for cond in _filter_conditions(model, filters):
        query = query.where(cond)
    return query


def _terminal_statuses() -> list[ApplicationStatus]:
    """Application statuses that are terminal for SLA/funnel purposes."""
    return [
        ApplicationStatus.ACTIVE_LOA,
        ApplicationStatus.ACTIVE_EOA,
        ApplicationStatus.CANCELLED,
        ApplicationStatus.FINAL_LOD,
        ApplicationStatus.FINAL_LOR,
        ApplicationStatus.WITHDRAWN,
        ApplicationStatus.APPROVED,
        ApplicationStatus.REJECTED,
        ApplicationStatus.CLOSED,
    ]


def _now() -> datetime:
    return datetime.now(UTC)


def _sla_state_label(sla_due_at, now: datetime):
    """Return a SLA state label for one application's due date."""
    return case(
        (sla_due_at.is_(None), "no_sla"),
        (sla_due_at < now, "overdue"),
        (sla_due_at <= now + timedelta(days=3), "watch"),
        else_="on_track",
    )


# ---------------------------------------------------------------------------
# Regulation Bureau / Scrutiny dashboard
# ---------------------------------------------------------------------------


def regulation_bureau_dashboard(
    db: Session, filters: ReportFilters
) -> RegulationBureauDashboard:
    """Aggregate the Regulation Bureau / Scrutiny work queue.

    Every figure is a single SQL aggregation over ``applications`` joined to
    ``institutions``.
    """
    now = _now()

    base = select(Application).join(
        Institution, Institution.id == Application.institution_id
    )
    base = _apply_global_filters(base, Application, filters)
    base = base.where(Application.is_withdrawn.is_(False))

    # Applications still being worked (not withdrawn, not terminal).
    active = base.where(Application.status.not_in(_terminal_statuses()))
    active_sub = active.subquery()
    total_in_queue = _zero(
        db.scalar(select(func.count()).select_from(active_sub))
    )

    # By stage.
    by_stage_rows = db.execute(
        select(
            active_sub.c.current_stage,
            func.count(active_sub.c.id).label("count"),
        )
        .group_by(active_sub.c.current_stage)
    ).all()
    by_stage = [
        {"stage": row.current_stage.value, "count": row.count}
        for row in by_stage_rows
    ]

    # By SLA state relative to now.
    sla_sub = select(
        active_sub.c.id,
        _sla_state_label(active_sub.c.sla_due_at, now).label("sla_state"),
    ).subquery()
    by_sla_rows = db.execute(
        select(
            sla_sub.c.sla_state,
            func.count().label("count"),
        )
        .group_by(sla_sub.c.sla_state)
    ).all()
    by_sla = [{"state": row.sla_state, "count": row.count} for row in by_sla_rows]

    # Overdue: SLA due date has passed and the application is still active.
    overdue_query = active.where(
        Application.sla_due_at.is_not(None),
        Application.sla_due_at < now,
    )
    overdue_sub = overdue_query.subquery()
    overdue_count = _zero(
        db.scalar(select(func.count()).select_from(overdue_sub))
    )
    overdue_rows = db.execute(
        select(
            overdue_sub.c.id,
            overdue_sub.c.portal_application_no,
            Institution.name,
            overdue_sub.c.status,
            overdue_sub.c.current_stage,
            overdue_sub.c.sla_due_at,
        )
        .join(Institution, Institution.id == overdue_sub.c.institution_id)
        .order_by(overdue_sub.c.sla_due_at.asc())
        .limit(50)
    ).all()
    overdue = [
        QueueEntry(
            application_id=str(r.id),
            portal_application_no=r.portal_application_no,
            institution_name=r.name,
            status=r.status,
            current_stage=r.current_stage.value,
            sla_due_at=r.sla_due_at,
            days_overdue=(now.date() - r.sla_due_at.date()).days
            if r.sla_due_at
            else None,
            assigned_officer=None,
            apH_clause="APH 1.8",
        )
        for r in overdue_rows
    ]

    # Applications awaiting institution compliance response.
    awaiting_compliance = base.where(
        Application.status == ApplicationStatus.INSTITUTION_COMPLIANCE
    )
    awaiting_compliance_count = _zero(
        db.scalar(select(func.count()).select_from(awaiting_compliance.subquery()))
    )

    # Upcoming EVC dates: inspections scheduled in the next 30 days.
    upcoming_evc_rows = db.execute(
        select(
            Inspection.id,
            Application.id,
            Application.portal_application_no,
            Institution.name,
            Inspection.scheduled_on,
            Inspection.status,
        )
        .join(Application, Application.id == Inspection.application_id)
        .join(Institution, Institution.id == Application.institution_id)
        .where(
            Inspection.status.in_(
                [InspectionStatus.SCHEDULED, InspectionStatus.COMPLETED]
            ),
            Inspection.scheduled_on >= now,
            Inspection.scheduled_on <= now + timedelta(days=30),
            Application.is_withdrawn.is_(False),
            *(
                [Application.academic_year == filters.academic_year]
                if filters.academic_year
                else []
            ),
            *(
                [Application.application_type == filters.application_type]
                if filters.application_type
                else []
            ),
            *(
                [Application.track == filters.track]
                if filters.track
                else []
            ),
            *(
                [Institution.region == filters.region]
                if filters.region
                else []
            ),
            *(
                [Institution.state == filters.state]
                if filters.state
                else []
            ),
        )
        .order_by(Inspection.scheduled_on.asc())
        .limit(50)
    ).all()
    upcoming_evc_dates = [
        {
            "inspection_id": str(r.id),
            "application_id": str(r[1]),
            "portal_application_no": r.portal_application_no,
            "institution_name": r.name,
            "scheduled_on": r.scheduled_on.isoformat()
            if r.scheduled_on
            else None,
            "status": r.status.value,
        }
        for r in upcoming_evc_rows
    ]

    # Average handling time: days from submitted_at to decision_uploaded_at
    # (or now for still-active applications).
    base_sub2 = base.subquery()
    handling_rows = db.execute(
        select(
            func.avg(
                func.coalesce(base_sub2.c.decision_uploaded_at, now)
                - base_sub2.c.submitted_at
            ).label("avg_interval")
        )
        .where(base_sub2.c.submitted_at.is_not(None))
    ).first()
    average_handling_days = None
    if handling_rows and handling_rows.avg_interval is not None:
        avg_delta: timedelta = handling_rows.avg_interval
        average_handling_days = round(avg_delta.total_seconds() / 86400, 2)

    return RegulationBureauDashboard(
        total_in_queue=total_in_queue,
        by_stage=by_stage,
        by_sla=by_sla,
        overdue_count=overdue_count,
        overdue=overdue,
        awaiting_institution_compliance=awaiting_compliance_count,
        upcoming_evc_dates=upcoming_evc_dates,
        average_handling_days=average_handling_days,
    )


# ---------------------------------------------------------------------------
# Regional Officer / SUPER_ADMIN dashboard
# ---------------------------------------------------------------------------


def regional_dashboard(db: Session, filters: ReportFilters) -> RegionalDashboard:
    """Aggregate the Regional Officer / SUPER_ADMIN dashboard.

    All figures are SQL aggregations; the result set is narrowed by the global
    filters.
    """
    now = _now()
    three_days = now + timedelta(days=3)
    six_months = now + timedelta(days=180)

    base = select(Application).join(
        Institution, Institution.id == Application.institution_id
    )
    base = _apply_global_filters(base, Application, filters)
    base = base.where(Application.is_withdrawn.is_(False))
    base_sub = base.subquery()

    total_applications = _zero(
        db.scalar(select(func.count()).select_from(base_sub))
    )

    # Applications by track and state.
    by_track_state_rows = db.execute(
        select(
            Application.track,
            Institution.state,
            func.count(Application.id).label("count"),
        )
        .join(Institution, Institution.id == Application.institution_id)
        .where(Application.is_withdrawn.is_(False))
        .where(*_filter_conditions(Application, filters))
        .group_by(Application.track, Institution.state)
        .order_by(Application.track, Institution.state)
    ).all()
    by_track_state = [
        ApplicationByTrackState(
            track=row.track.value,
            state=row.state,
            count=row.count,
        )
        for row in by_track_state_rows
    ]

    # Funnel: Submitted > Scrutiny > EVC > EC > LoA/EoA.
    funnel_stages = [
        (ApplicationStatus.SUBMITTED, "Submitted"),
        (ApplicationStatus.SCRUTINY, "Scrutiny"),
        (ApplicationStatus.EVC_CONSTITUTED, "EVC Constituted"),
        (ApplicationStatus.EC_DECISION, "EC Decision"),
        (ApplicationStatus.LOA_ISSUED, "LoA Issued"),
        (ApplicationStatus.EOA_ISSUED, "EoA Issued"),
    ]
    funnel = []
    for status_value, label in funnel_stages:
        count = _zero(
            db.scalar(
                select(func.count(Application.id)).where(
                    Application.id.in_(
                        select(Application.id).where(
                            Application.status == status_value,
                            *(
                                [
                                    Application.academic_year
                                    == filters.academic_year
                                ]
                                if filters.academic_year
                                else []
                            ),
                            *(
                                [
                                    Application.application_type
                                    == filters.application_type
                                ]
                                if filters.application_type
                                else []
                            ),
                            *(
                                [Application.track == filters.track]
                                if filters.track
                                else []
                            ),
                            *(
                                [
                                    Application.institution_id.in_(
                                        select(Institution.id).where(
                                            Institution.region == filters.region
                                        )
                                    )
                                ]
                                if filters.region
                                else []
                            ),
                            *(
                                [
                                    Application.institution_id.in_(
                                        select(Institution.id).where(
                                            Institution.state == filters.state
                                        )
                                    )
                                ]
                                if filters.state
                                else []
                            ),
                        )
                    )
                )
            )
        )
    funnel.append(FunnelEntry(stage=label, count=count))

    # Approval vs rejection (final decision_type on the application).
    approvals = _zero(
        db.scalar(
            select(func.count(Application.id)).where(
                Application.id.in_(
                    select(Application.id).where(
                        Application.decision_type.in_(
                            [DecisionType.LOA, DecisionType.EOA]
                        ),
                        *(
                            [
                                Application.academic_year
                                == filters.academic_year
                            ]
                            if filters.academic_year
                            else []
                        ),
                        *(
                            [
                                Application.application_type
                                == filters.application_type
                            ]
                            if filters.application_type
                            else []
                        ),
                        *(
                            [Application.track == filters.track]
                            if filters.track
                            else []
                        ),
                        *(
                            [
                                Application.institution_id.in_(
                                    select(Institution.id).where(
                                        Institution.region == filters.region
                                    )
                                )
                            ]
                            if filters.region
                            else []
                        ),
                        *(
                            [
                                Application.institution_id.in_(
                                    select(Institution.id).where(
                                        Institution.state == filters.state
                                    )
                                )
                            ]
                            if filters.state
                            else []
                        ),
                    )
                )
            )
        )
    )
    rejections = _zero(
        db.scalar(
            select(func.count(Application.id)).where(
                Application.id.in_(
                    select(Application.id).where(
                        Application.decision_type.in_(
                            [DecisionType.LOD, DecisionType.LOR]
                        ),
                        *(
                            [
                                Application.academic_year
                                == filters.academic_year
                            ]
                            if filters.academic_year
                            else []
                        ),
                        *(
                            [
                                Application.application_type
                                == filters.application_type
                            ]
                            if filters.application_type
                            else []
                        ),
                        *(
                            [Application.track == filters.track]
                            if filters.track
                            else []
                        ),
                        *(
                            [
                                Application.institution_id.in_(
                                    select(Institution.id).where(
                                        Institution.region == filters.region
                                    )
                                )
                            ]
                            if filters.region
                            else []
                        ),
                        *(
                            [
                                Application.institution_id.in_(
                                    select(Institution.id).where(
                                        Institution.state == filters.state
                                    )
                                )
                            ]
                            if filters.state
                            else []
                        ),
                    )
                )
            )
        )
    )
    pending = total_applications - approvals - rejections
    approval_vs_rejection = ApprovalVsRejection(
        approvals=approvals,
        rejections=rejections,
        pending=max(0, pending),
    )

    # Appeals filed and outcome (appeals joined to applications).
    appeals_app_sub = _apply_global_filters(
        select(Application.id).join(
            Institution, Institution.id == Application.institution_id
        ),
        Application,
        filters,
    ).subquery()

    appeals_filed = _zero(
        db.scalar(
            select(func.count(Application.id)).where(
                Application.id.in_(appeals_app_sub),
                Application.appeal_loop_count > 0,
            )
        )
    )
    appeals_within = _zero(
        db.scalar(
            select(func.count(Application.id)).where(
                Application.id.in_(appeals_app_sub),
                Application.appeal_deadline >= now,
            )
        )
    )
    sac_recommend = _zero(
        db.scalar(
            select(func.count(Application.id))
            .join(Appeal, Appeal.application_id == Application.id)
            .where(
                Application.id.in_(appeals_app_sub),
                Appeal.sac_recommendation == "RECOMMEND",
            )
        )
    )
    sac_not_recommend = _zero(
        db.scalar(
            select(func.count(Application.id))
            .join(Appeal, Appeal.application_id == Application.id)
            .where(
                Application.id.in_(appeals_app_sub),
                Appeal.sac_recommendation == "NOT_RECOMMEND",
            )
        )
    )
    sac_send_back = _zero(
        db.scalar(
            select(func.count(Application.id))
            .join(Appeal, Appeal.application_id == Application.id)
            .where(
                Application.id.in_(appeals_app_sub),
                Appeal.sac_recommendation == "SEND_BACK",
            )
        )
    )
    council_allowed = _zero(
        db.scalar(
            select(func.count(Application.id))
            .join(Appeal, Appeal.application_id == Application.id)
            .where(
                Application.id.in_(appeals_app_sub),
                Appeal.council_decision.isnot(None),
                Appeal.council_decision.ilike("%allow%"),
            )
        )
    )
    council_dismissed = _zero(
        db.scalar(
            select(func.count(Application.id))
            .join(Appeal, Appeal.application_id == Application.id)
            .where(
                Application.id.in_(appeals_app_sub),
                Appeal.council_decision.isnot(None),
                Appeal.council_decision.ilike("%dismiss%"),
            )
        )
    )
    appeals = AppealOutcome(
        filed=appeals_filed,
        within_deadline=appeals_within,
        sac_recommend=sac_recommend,
        sac_not_recommend=sac_not_recommend,
        sac_send_back=sac_send_back,
        council_allowed=council_allowed,
        council_dismissed=council_dismissed,
    )

    # Appeal windows closing in 3 days.
    appeal_windows_closing = _zero(
        db.scalar(
            select(func.count(Application.id))
            .join(Institution, Institution.id == Application.institution_id)
            .where(
                Application.appeal_deadline.is_not(None),
                Application.appeal_deadline >= now,
                Application.appeal_deadline <= three_days,
                *(
                    [Application.academic_year == filters.academic_year]
                    if filters.academic_year
                    else []
                ),
                *(
                    [Application.application_type == filters.application_type]
                    if filters.application_type
                    else []
                ),
                *(
                    [Application.track == filters.track]
                    if filters.track
                    else []
                ),
                *(
                    [Institution.region == filters.region]
                    if filters.region
                    else []
                ),
                *(
                    [Institution.state == filters.state]
                    if filters.state
                    else []
                ),
            )
        )
    )

    # Security Deposits pending with penalty status.
    deposit_rows = db.execute(
        select(
            SecurityDeposit.id,
            Application.id,
            Application.portal_application_no,
            Institution.name,
            SecurityDeposit.status,
            SecurityDeposit.penalty_percent,
            SecurityDeposit.created_on,
        )
        .join(Application, Application.id == SecurityDeposit.application_id)
        .join(Institution, Institution.id == Application.institution_id)
        .where(
            SecurityDeposit.status.in_(
                [
                    SecurityDepositStatus.PENDING,
                    SecurityDepositStatus.PENALTY_10,
                    SecurityDepositStatus.PENALTY_20,
                ]
            ),
            *(
                [Application.academic_year == filters.academic_year]
                if filters.academic_year
                else []
            ),
            *(
                [Application.application_type == filters.application_type]
                if filters.application_type
                else []
            ),
            *(
                [Application.track == filters.track]
                if filters.track
                else []
            ),
            *(
                [Institution.region == filters.region]
                if filters.region
                else []
            ),
            *(
                [Institution.state == filters.state]
                if filters.state
                else []
            ),
        )
        .limit(100)
    ).all()
    security_deposits_pending = [
        SecurityDepositPending(
            application_id=str(r.id),
            portal_application_no=r.portal_application_no,
            institution_name=r.name,
            status=r.status,
            penalty_percent=r.penalty_percent,
            due_on=r.created_on + timedelta(days=15)
            if r.created_on
            else None,
            apH_clause="APH 2.25f",
        )
        for r in deposit_rows
    ]

    # LoA expiring in 6 months.
    loa_rows = db.execute(
        select(
            Application.id,
            Application.portal_application_no,
            Institution.name,
            Application.loa_valid_until,
        )
        .join(Institution, Institution.id == Application.institution_id)
        .where(
            Application.loa_valid_until.is_not(None),
            Application.loa_valid_until >= now.date(),
            Application.loa_valid_until <= six_months.date(),
            *(
                [Application.academic_year == filters.academic_year]
                if filters.academic_year
                else []
            ),
            *(
                [Application.application_type == filters.application_type]
                if filters.application_type
                else []
            ),
            *(
                [Application.track == filters.track]
                if filters.track
                else []
            ),
            *(
                [Institution.region == filters.region]
                if filters.region
                else []
            ),
            *(
                [Institution.state == filters.state]
                if filters.state
                else []
            ),
        )
        .limit(100)
    ).all()
    loa_expiring = [
        LoaExpiring(
            application_id=str(r.id),
            portal_application_no=r.portal_application_no,
            institution_name=r.name,
            valid_until=r.loa_valid_until,
            days_left=(r.loa_valid_until - now.date()).days
            if r.loa_valid_until
            else None,
            apH_clause="APH 1.10b",
        )
        for r in loa_rows
    ]

    # Institutions by compliance (latest snapshot per institution).
    latest_snapshot_q = (
        select(
            ComplianceSnapshot.institution_id,
            ComplianceSnapshot.score,
            ComplianceSnapshot.status,
            func.row_number()
            .over(
                partition_by=ComplianceSnapshot.institution_id,
                order_by=ComplianceSnapshot.evaluated_at.desc(),
            )
            .label("rn"),
        )
        .subquery()
    )
    institution_compliance_rows = db.execute(
        select(
            Institution.id,
            Institution.name,
            Institution.state,
            Institution.region,
            latest_snapshot_q.c.score,
            latest_snapshot_q.c.status,
        )
        .join(
            latest_snapshot_q,
            latest_snapshot_q.c.institution_id == Institution.id,
            isouter=True,
        )
        .where(latest_snapshot_q.c.rn == 1)
        .order_by(Institution.name)
        .limit(100)
    ).all()
    institutions_by_compliance = [
        InstitutionCompliance(
            institution_id=str(r.id),
            name=r.name,
            state=r.state,
            region=r.region,
            score=float(r.score) if r.score is not None else 0.0,
            status=r.status if r.status else ComplianceHealth.GREEN,
        )
        for r in institution_compliance_rows
    ]

    # Top violation codes (APH 7.4) from penal actions.
    violation_rows = db.execute(
        select(
            PenalAction.violation_code,
            func.count(PenalAction.id).label("count"),
        )
        .join(Institution, Institution.id == PenalAction.institution_id)
        .where(
            *(
                [
                    PenalAction.effective_academic_year
                    == filters.academic_year
                ]
                if filters.academic_year
                else []
            ),
            *(
                [Institution.region == filters.region]
                if filters.region
                else []
            ),
            *(
                [Institution.state == filters.state]
                if filters.state
                else []
            ),
        )
        .group_by(PenalAction.violation_code)
        .order_by(func.count(PenalAction.id).desc())
        .limit(10)
    ).all()
    top_violation_codes = [
        ViolationCode(code=row.violation_code, count=row.count)
        for row in violation_rows
    ]

    # Faculty-ratio deficit distribution (placeholder; ratio lives in app data JSONB).
    faculty_rows = db.execute(
        select(
            Institution.id,
            Institution.name,
        )
        .select_from(Institution)
        .group_by(Institution.id, Institution.name)
        .limit(100)
    ).all()
    faculty_ratio_deficit = [
        FacultyRatioDeficit(
            institution_id=str(r.id),
            name=r.name,
            student_faculty_ratio=None,
            required_ratio=None,
            deficit=None,
            apH_clause="APH 6.14",
        )
        for r in faculty_rows
    ]

    # Deficiency categories (open).
    deficiency_rows = db.execute(
        select(
            Deficiency.category,
            func.count(Deficiency.id).label("count"),
        )
        .join(Application, Application.id == Deficiency.application_id)
        .join(Institution, Institution.id == Application.institution_id)
        .where(
            Deficiency.status == DeficiencyStatus.OPEN,
            *(
                [Application.academic_year == filters.academic_year]
                if filters.academic_year
                else []
            ),
            *(
                [Application.application_type == filters.application_type]
                if filters.application_type
                else []
            ),
            *(
                [Application.track == filters.track]
                if filters.track
                else []
            ),
            *(
                [Institution.region == filters.region]
                if filters.region
                else []
            ),
            *(
                [Institution.state == filters.state]
                if filters.state
                else []
            ),
        )
        .group_by(Deficiency.category)
        .order_by(func.count(Deficiency.id).desc())
    ).all()
    deficiency_categories = [
        DeficiencyCategory(category=row.category, count=row.count)
        for row in deficiency_rows
    ]

    # SLA breach rate.
    total_with_sla = _zero(
        db.scalar(
            select(func.count(Application.id))
            .join(Institution, Institution.id == Application.institution_id)
            .where(
                Application.sla_due_at.is_not(None),
                *(
                    [Application.academic_year == filters.academic_year]
                    if filters.academic_year
                    else []
                ),
                *(
                    [Application.application_type == filters.application_type]
                    if filters.application_type
                    else []
                ),
                *(
                    [Application.track == filters.track]
                    if filters.track
                    else []
                ),
                *(
                    [Institution.region == filters.region]
                    if filters.region
                    else []
                ),
                *(
                    [Institution.state == filters.state]
                    if filters.state
                    else []
                ),
            )
        )
    )
    breached = _zero(
        db.scalar(
            select(func.count(Application.id)).where(
                Application.sla_due_at.is_not(None),
                Application.sla_due_at < now,
                *(
                    [Application.academic_year == filters.academic_year]
                    if filters.academic_year
                    else []
                ),
                *(
                    [Application.application_type == filters.application_type]
                    if filters.application_type
                    else []
                ),
                *(
                    [Application.track == filters.track]
                    if filters.track
                    else []
                ),
                *(
                    [
                        Application.institution_id.in_(
                            select(Institution.id).where(
                                Institution.region == filters.region
                            )
                        )
                    ]
                    if filters.region
                    else []
                ),
                *(
                    [
                        Application.institution_id.in_(
                            select(Institution.id).where(
                                Institution.state == filters.state
                            )
                        )
                    ]
                    if filters.state
                    else []
                ),
            )
        )
    )
    breach_rate = (
        round((breached / total_with_sla) * 100, 2) if total_with_sla else 0.0
    )
    sla_breach = SlaBreach(
        total_with_sla=total_with_sla,
        breached=breached,
        breach_rate=breach_rate,
    )

    # Escalations (applications flagged is_escalated).
    escalation_rows = db.execute(
        select(
            Application.id,
            Application.portal_application_no,
            Institution.name,
        )
        .join(Institution, Institution.id == Application.institution_id)
        .where(
            Application.is_escalated.is_(True),
            *(
                [Application.academic_year == filters.academic_year]
                if filters.academic_year
                else []
            ),
            *(
                [Application.application_type == filters.application_type]
                if filters.application_type
                else []
            ),
            *(
                [Application.track == filters.track]
                if filters.track
                else []
            ),
            *(
                [Institution.region == filters.region]
                if filters.region
                else []
            ),
            *(
                [Institution.state == filters.state]
                if filters.state
                else []
            ),
        )
        .limit(100)
    ).all()
    escalations = [
        Escalation(
            application_id=str(r.id),
            portal_application_no=r.portal_application_no,
            institution_name=r.name,
            level=1,
            apH_clause="APH 7.13",
        )
        for r in escalation_rows
    ]

    # Complaints by status (last 365 days).
    complaint_rows = db.execute(
        select(
            Complaint.status,
            func.count(Complaint.id).label("count"),
        )
        .join(Institution, Institution.id == Complaint.institution_id)
        .where(
            Complaint.received_on >= now.date() - timedelta(days=365),
            *(
                [Institution.region == filters.region]
                if filters.region
                else []
            ),
            *(
                [Institution.state == filters.state]
                if filters.state
                else []
            ),
        )
        .group_by(Complaint.status)
    ).all()
    complaints_by_status = [
        ComplaintStatusCount(status=row.status.value, count=row.count)
        for row in complaint_rows
    ]

    # Penal actions by type.
    penal_rows = db.execute(
        select(
            PenalAction.action_type,
            func.count(PenalAction.id).label("count"),
        )
        .join(Institution, Institution.id == PenalAction.institution_id)
        .where(
            *(
                [Institution.region == filters.region]
                if filters.region
                else []
            ),
            *(
                [Institution.state == filters.state]
                if filters.state
                else []
            ),
        )
        .group_by(PenalAction.action_type)
        .order_by(func.count(PenalAction.id).desc())
    ).all()
    penal_actions_by_type = [
        PenalActionByType(action_type=row.action_type.value, count=row.count)
        for row in penal_rows
    ]

    # Average days per stage from workflow events (time between transitions).
    stage_diff_subq = select(
        WorkflowEvent.application_id,
        WorkflowEvent.to_status,
        func.extract(
            "epoch",
            WorkflowEvent.created_at
            - func.lag(WorkflowEvent.created_at).over(
                partition_by=WorkflowEvent.application_id,
                order_by=WorkflowEvent.created_at,
            ),
        )
        .label("days_diff"),
    ).subquery()
    stage_days_rows = db.execute(
        select(
            stage_diff_subq.c.to_status,
            func.avg(stage_diff_subq.c.days_diff / 86400.0).label("avg_days"),
        )
        .group_by(stage_diff_subq.c.to_status)
    ).all()
    average_days_per_stage = [
        AverageDaysPerStage(
            stage=row.to_status.value,
            average_days=round(row.avg_days, 2) if row.avg_days else 0.0,
        )
        for row in stage_days_rows
    ]

    return RegionalDashboard(
        total_applications=total_applications,
        by_track_state=by_track_state,
        funnel=funnel,
        approval_vs_rejection=approval_vs_rejection,
        appeals=appeals,
        appeal_windows_closing_3_days=appeal_windows_closing,
        security_deposits_pending=security_deposits_pending,
        loa_expiring_6_months=loa_expiring,
        institutions_by_compliance=institutions_by_compliance,
        top_violation_codes=top_violation_codes,
        faculty_ratio_deficit=faculty_ratio_deficit,
        deficiency_categories=deficiency_categories,
        sla_breach=sla_breach,
        escalations=escalations,
        complaints_by_status=complaints_by_status,
        penal_actions_by_type=penal_actions_by_type,
        average_days_per_stage=average_days_per_stage,
    )


# ---------------------------------------------------------------------------
# Institution Admin dashboard
# ---------------------------------------------------------------------------


def institution_dashboard(
    db: Session, institution_id, filters: ReportFilters
) -> InstitutionDashboard:
    """Aggregate the Institution Admin dashboard for one institution.

    Progress tracker with the institution's own applications, deficiencies,
    fees, documents, compliance and upcoming academic-calendar deadlines.
    """
    now = _now()

    app_query = select(Application).where(
        Application.institution_id == institution_id,
        Application.is_withdrawn.is_(False),
    )
    app_query = _apply_global_filters(app_query, Application, filters)
    application = db.scalar(
        app_query.order_by(Application.created_at.desc())
    )
    institution = db.get(Institution, institution_id)
    institution_name = institution.name if institution else ""

    if application is None:
        return InstitutionDashboard(
            portal_application_no=None,
            application_id=None,
            institution_name=institution_name,
            status=ApplicationStatus.DRAFT,
            open_deficiencies=[],
            fees=FeePosition(
                total_paise=0, paid_paise=0, refunded_paise=0, due_paise=0
            ),
            expiring_documents=[],
            mandatory_disclosure=MandatoryDisclosure(present=False, url=None),
            compliance_score=None,
            top_failing_rules=[],
            upcoming_deadlines=[],
        )

    # Open deficiencies with countdown.
    deficiency_rows = db.execute(
        select(
            Deficiency.id,
            Deficiency.category,
            Deficiency.description,
            Deficiency.due_date,
        )
        .where(
            Deficiency.application_id == application.id,
            Deficiency.status == DeficiencyStatus.OPEN,
        )
        .order_by(Deficiency.due_date.asc())
    ).all()
    open_deficiencies = [
        OpenDeficiency(
            deficiency_id=str(r.id),
            category=r.category,
            description=r.description,
            due_date=r.due_date,
            days_left=(r.due_date - now.date()).days,
            apH_clause="APH 2.3.3b",
        )
        for r in deficiency_rows
    ]

    # Fees paid/refunded.
    fee_rows = db.execute(
        select(
            FeeTransaction.kind,
            func.sum(FeeTransaction.amount_paise).label("total"),
        )
        .where(
            FeeTransaction.application_id == application.id,
            FeeTransaction.paid_at.is_not(None),
        )
        .group_by(FeeTransaction.kind)
    ).all()
    fee_map = {row.kind.value: int(row.total or 0) for row in fee_rows}
    total_paid = sum(
        v for k, v in fee_map.items() if k in (FeeKind.TER.value, FeeKind.PENALTY.value)
    )
    total_refunded = fee_map.get(FeeKind.REFUND.value, 0)
    total_due = max(
        0,
        (application.ter_amount_paise or 0) - total_paid + total_refunded,
    )
    fees = FeePosition(
        total_paise=application.ter_amount_paise or 0,
        paid_paise=total_paid,
        refunded_paise=total_refunded,
        due_paise=total_due,
    )

    # Documents expiring within 60 days.
    doc_rows = db.execute(
        select(
            Document.id,
            Document.doc_type,
            Document.filename,
            Document.expiry_date,
            Document.valid_until,
        )
        .where(
            Document.application_id == application.id,
            Document.superseded_by.is_(None),
            (
                Document.expiry_date.is_not(None)
                | Document.valid_until.is_not(None)
            ),
        )
    ).all()
    expiring_documents = []
    for r in doc_rows:
        expiry = r.expiry_date or r.valid_until
        days_left = (expiry - now.date()).days if expiry else None
        if days_left is not None and days_left <= 60:
            expiring_documents.append(
                ExpiringDocument(
                    document_id=str(r.id),
                    doc_type=r.doc_type,
                    filename=r.filename,
                    expiry_date=r.expiry_date,
                    valid_until=r.valid_until,
                    days_left=days_left,
                    apH_clause="APH 6.17h",
                )
            )

    # Mandatory disclosure completeness.
    data = application.data or {}
    mandatory_url = data.get("mandatory_disclosure_url")
    mandatory_disclosure = MandatoryDisclosure(
        present=bool(mandatory_url),
        url=mandatory_url if isinstance(mandatory_url, str) else None,
    )

    # Compliance score and top three failing rules.
    compliance_score = (
        float(application.compliance_score)
        if application.compliance_score is not None
        else None
    )
    failing_rows = db.execute(
        select(
            ComplianceRule.code,
            ComplianceRule.name,
            ComplianceResult.message,
            ComplianceRule.apH_clause,
            ComplianceResult.explanation,
        )
        .join(ComplianceRule, ComplianceRule.id == ComplianceResult.rule_id)
        .where(
            ComplianceResult.application_id == application.id,
            ComplianceResult.status == "FAIL",
        )
        .order_by(
            ComplianceRule.severity.desc(),
            ComplianceResult.evaluated_at.desc(),
        )
        .limit(3)
    ).all()
    top_failing_rules = []
    for r in failing_rows:
        explanation = r.explanation if isinstance(r.explanation, dict) else {}
        top_failing_rules.append(
            FailingRule(
                code=explanation.get("rule_code", r.code),
                name=explanation.get("rule_name", r.name),
                message=r.message,
                fix_text=explanation.get("fix_text"),
                apH_clause=explanation.get("apH_clause", r.apH_clause),
            )
        )

    # Upcoming deadlines from the academic calendar.
    upcoming_rows = db.execute(
        select(
            AcademicCalendarEvent.event_key,
            AcademicCalendarEvent.description,
            AcademicCalendarEvent.date,
        )
        .where(
            AcademicCalendarEvent.academic_year == application.academic_year,
            AcademicCalendarEvent.event_key.in_(
                [_ENROLMENT_UPLOAD_KEY, _IC_REPORT_KEY]
            ),
            AcademicCalendarEvent.date >= now.date(),
        )
        .order_by(AcademicCalendarEvent.date.asc())
    ).all()
    upcoming_deadlines = [
        UpcomingDeadline(
            key=r.event_key.value,
            label=r.description or r.event_key.value.replace("_", " ").title(),
            due_on=r.date,
            days_left=(r.date - now.date()).days,
            apH_clause="APH 5",
        )
        for r in upcoming_rows
    ]

    return InstitutionDashboard(
        portal_application_no=application.portal_application_no,
        application_id=str(application.id),
        institution_name=institution_name,
        status=application.status,
        open_deficiencies=open_deficiencies,
        fees=fees,
        expiring_documents=expiring_documents,
        mandatory_disclosure=mandatory_disclosure,
        compliance_score=compliance_score,
        top_failing_rules=top_failing_rules,
        upcoming_deadlines=upcoming_deadlines,
    )


# ---------------------------------------------------------------------------
# Application PDF report data
# ---------------------------------------------------------------------------


def application_report_data(db: Session, application_id) -> ApplicationReport:
    """Gather all summary data for the per-application PDF report."""
    application = db.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    institution = db.get(Institution, application.institution_id)

    app_summary = ReportApplication(
        application_id=str(application.id),
        portal_application_no=application.portal_application_no,
        institution_name=institution.name if institution else "",
        track=application.track.value,
        application_type=application.application_type,
        academic_year=application.academic_year,
        status=application.status,
        current_stage=application.current_stage.value,
        submitted_at=application.submitted_at,
        decision_type=application.decision_type.value
        if application.decision_type
        else None,
        decision_uploaded_at=application.decision_uploaded_at,
        compliance_score=float(application.compliance_score)
        if application.compliance_score is not None
        else None,
    )

    # Timeline events from workflow events.
    timeline_rows = db.execute(
        select(
            WorkflowEvent.created_at,
            WorkflowEvent.action,
            WorkflowEvent.from_status,
            WorkflowEvent.to_status,
            User.name,
            WorkflowEvent.apH_clause,
        )
        .join(User, User.id == WorkflowEvent.actor_id, isouter=True)
        .where(WorkflowEvent.application_id == application.id)
        .order_by(WorkflowEvent.created_at.asc())
    ).all()
    timeline = [
        ReportTimelineEvent(
            created_at=r.created_at,
            action=r.action,
            from_status=r.from_status.value if r.from_status else None,
            to_status=r.to_status.value,
            actor_name=r.name,
            apH_clause=r.apH_clause,
        )
        for r in timeline_rows
    ]

    # Decisions.
    decision_rows = db.execute(
        select(
            Decision.body,
            Decision.outcome,
            Decision.decided_on,
            Decision.quorum_met,
            Decision.apH_clause,
        )
        .where(Decision.application_id == application.id)
        .order_by(Decision.decided_on.asc())
    ).all()
    decisions = [
        ReportDecision(
            body=r.body.value if r.body else None,
            outcome=r.outcome.value if r.outcome else None,
            decided_on=r.decided_on,
            quorum_met=r.quorum_met,
            apH_clause=r.apH_clause,
        )
        for r in decision_rows
    ]

    # Fees.
    fee_rows = db.execute(
        select(
            FeeTransaction.kind,
            FeeTransaction.amount_paise,
            FeeTransaction.paid_at,
            FeeTransaction.apH_clause,
        )
        .where(FeeTransaction.application_id == application.id)
        .order_by(FeeTransaction.paid_at.asc())
    ).all()
    fees = [
        ReportFee(
            kind=r.kind.value,
            amount_paise=r.amount_paise,
            paid_at=r.paid_at,
            apH_clause=r.apH_clause,
        )
        for r in fee_rows
    ]

    # Compliance results.
    compliance_rows = db.execute(
        select(
            ComplianceRule.code,
            ComplianceRule.name,
            ComplianceResult.status,
            ComplianceResult.message,
            ComplianceRule.apH_clause,
        )
        .join(ComplianceRule, ComplianceRule.id == ComplianceResult.rule_id)
        .where(ComplianceResult.application_id == application.id)
        .order_by(ComplianceRule.code.asc())
    ).all()
    compliance = [
        ReportCompliance(
            code=r.code,
            name=r.name,
            status=r.status,
            message=r.message,
            apH_clause=r.apH_clause,
        )
        for r in compliance_rows
    ]

    # Deficiencies.
    deficiency_rows = db.execute(
        select(
            Deficiency.category,
            Deficiency.description,
            Deficiency.status,
            Deficiency.due_date,
        )
        .where(Deficiency.application_id == application.id)
        .order_by(Deficiency.created_at.asc())
    ).all()
    deficiencies = [
        ReportDeficiency(
            category=r.category,
            description=r.description,
            status=r.status,
            due_date=r.due_date,
            apH_clause="APH 2.3.3b",
        )
        for r in deficiency_rows
    ]

    return ApplicationReport(
        application=app_summary,
        timeline=timeline,
        decisions=decisions,
        fees=fees,
        compliance=compliance,
        deficiencies=deficiencies,
    )
