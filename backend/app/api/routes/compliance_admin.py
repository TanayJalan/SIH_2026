"""Compliance admin endpoints: rules, config, monitoring and impact preview."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select

from app.api.dependencies import AuditDep, ClockDep, DbSession, require_roles
from app.models.application import Application
from app.models.compliance import (
    ComplianceConfig,
    ComplianceRule,
    ComplianceSnapshot,
)
from app.models.enums import Role
from app.models.institution import Institution
from app.models.user import User
from app.schemas.common import ErrorResponse
from app.schemas.compliance import (
    ComplianceConfigRead,
    ComplianceConfigUpdate,
    ComplianceInstitutionTrendRead,
    ComplianceMetricListRead,
    ComplianceMetricRead,
    ComplianceMonitorPage,
    ComplianceMonitorRead,
    ComplianceMonitorRunRead,
    ComplianceRuleCreate,
    ComplianceRuleImpactRead,
    ComplianceRuleImpactRequest,
    ComplianceRulePage,
    ComplianceRuleRead,
    ComplianceRuleUpdate,
    ComplianceTrendPoint,
)
from app.services import compliance_admin
from app.services.audit import AuditService
from app.services.compliance import available_metric_catalogue, run_nightly_evaluation

router = APIRouter(prefix="/compliance", tags=["compliance-admin"])

ComplianceAdminUser = Annotated[
    User,
    Depends(require_roles(Role.SUPER_ADMIN, Role.REGIONAL_HEAD)),
]


def _scoped_institutions(user: User, db: DbSession) -> list[Institution]:
    """Institutions inside the viewer's scope (regional heads see their region)."""
    query = select(Institution).order_by(Institution.name)
    if user.role == Role.REGIONAL_HEAD and user.region:
        query = query.where(Institution.region == user.region)
    return list(db.scalars(query).all())


def _readable_rule(db: DbSession, rule_id: uuid.UUID) -> ComplianceRule:
    """Load a rule or raise 404."""
    rule = db.get(ComplianceRule, rule_id)
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Compliance rule not found"
        )
    return rule


def _validate_rule_bounds(rule: ComplianceRule) -> None:
    """Ensure BETWEEN bounds are coherent after a partial edit."""
    if rule.operator == "BETWEEN":
        if rule.threshold_max is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="threshold_max is required when operator is BETWEEN",
            )
        if rule.threshold_max < rule.threshold:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="threshold_max must be greater than or equal to threshold",
            )
    elif rule.threshold_max is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="threshold_max is only valid when operator is BETWEEN",
        )


@router.get(
    "/rules",
    response_model=ComplianceRulePage,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
    summary="List compliance rules",
)
def list_rules(
    current_user: ComplianceAdminUser,
    db: DbSession,
    include_inactive: bool = True,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ComplianceRulePage:
    """Return the configurable rule catalogue."""
    query = select(ComplianceRule)
    if not include_inactive:
        query = query.where(ComplianceRule.is_active.is_(True))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = db.scalars(
        query.order_by(ComplianceRule.category, ComplianceRule.code)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ComplianceRulePage(
        items=[ComplianceRuleRead.model_validate(rule) for rule in items],
        total=int(total or 0),
        page=page,
        page_size=page_size,
    )


@router.post(
    "/rules",
    response_model=ComplianceRuleRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
    summary="Add a compliance rule",
)
def create_rule(
    payload: ComplianceRuleCreate,
    current_user: ComplianceAdminUser,
    db: DbSession,
    audit: AuditDep,
    request: Request,
) -> ComplianceRule:
    """Create a rule with a full audit entry."""
    existing = db.scalar(select(ComplianceRule).where(ComplianceRule.code == payload.code))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A rule with this code already exists",
        )
    rule = ComplianceRule(
        code=payload.code,
        name=payload.name,
        category=payload.category,
        description=payload.description,
        metric_key=payload.metric_key,
        operator=payload.operator,
        threshold=str(payload.threshold),
        threshold_max=str(payload.threshold_max) if payload.threshold_max is not None else None,
        severity=payload.severity,
        applies_to=payload.applies_to,
        is_active=payload.is_active,
    )
    db.add(rule)
    db.flush()
    audit.log(
        current_user,
        "compliance.rule.create",
        "ComplianceRule",
        rule.id,
        after=compliance_admin.rule_snapshot(rule),
        request=request,
    )
    db.commit()
    db.refresh(rule)
    return rule


@router.patch(
    "/rules/{rule_id}",
    response_model=ComplianceRuleRead,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
    summary="Edit a compliance rule",
)
def update_rule(
    rule_id: uuid.UUID,
    payload: ComplianceRuleUpdate,
    current_user: ComplianceAdminUser,
    db: DbSession,
    audit: AuditDep,
    request: Request,
) -> ComplianceRule:
    """Apply a partial rule edit with a before/after audit entry."""
    rule = _readable_rule(db, rule_id)
    before = compliance_admin.rule_snapshot(rule)
    applied: dict[str, object] = {}

    for key, value in payload.model_dump(exclude_unset=True).items():
        if key == "threshold":
            if float(rule.threshold) == value:
                continue
            rule.threshold = str(value)
        elif key == "threshold_max":
            new_value: float | None = value
            current = float(rule.threshold_max) if rule.threshold_max is not None else None
            if current == new_value:
                continue
            rule.threshold_max = str(new_value) if new_value is not None else None
        else:
            if getattr(rule, key) == value:
                continue
            setattr(rule, key, value)
        applied[key] = value

    if applied:
        _validate_rule_bounds(rule)
        db.flush()
        audit.log(
            current_user,
            "compliance.rule.update",
            "ComplianceRule",
            rule.id,
            before=before,
            after=compliance_admin.rule_snapshot(rule),
            request=request,
        )
        db.commit()
        db.refresh(rule)
    return rule


@router.post(
    "/rules/impact",
    response_model=ComplianceRuleImpactRead,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
    summary="Preview the monitoring impact of a proposed rule change",
)
def preview_rule_impact(
    payload: ComplianceRuleImpactRequest,
    current_user: ComplianceAdminUser,
    db: DbSession,
) -> ComplianceRuleImpactRead:
    """Project proposed rule values against every scoped institution."""
    if payload.rule_id is not None:
        _readable_rule(db, payload.rule_id)
    red, amber, improved, unchanged, affected = compliance_admin.preview_rule_impact(
        db,
        proposed=payload.proposed,
        rule_id=payload.rule_id,
        institutions=_scoped_institutions(current_user, db),
    )
    if red:
        message = (
            f"This change would flip {red} institution"
            f"{'s' if red != 1 else ''} to RED."
        )
    elif amber:
        message = (
            f"This change would push {amber} institution"
            f"{'s' if amber != 1 else ''} to AMBER."
        )
    else:
        message = f"No institution would worsen ({improved} would improve)."
    return ComplianceRuleImpactRead(
        red_flips=red,
        amber_flips=amber,
        improved=improved,
        unchanged=unchanged,
        affected=affected,
        message=message,
    )


@router.get(
    "/metrics",
    response_model=ComplianceMetricListRead,
    responses={status.HTTP_403_FORBIDDEN: {"model": ErrorResponse}},
    summary="List metrics available to compliance rules",
)
def list_metrics(
    current_user: ComplianceAdminUser,
) -> ComplianceMetricListRead:
    """Return the metric catalogue used by the rule editor."""
    return ComplianceMetricListRead(
        items=[
            ComplianceMetricRead(**metric)
            for metric in available_metric_catalogue()
        ]
    )


@router.get(
    "/config",
    response_model=ComplianceConfigRead,
    responses={status.HTTP_403_FORBIDDEN: {"model": ErrorResponse}},
    summary="Read scoring weights and RAG breakpoints",
)
def get_config(
    current_user: ComplianceAdminUser,
    db: DbSession,
) -> ComplianceConfigRead:
    """Return the editable weighting and monitoring configuration."""
    return compliance_admin.get_compliance_config_read(db)


@router.put(
    "/config",
    response_model=ComplianceConfigRead,
    responses={status.HTTP_403_FORBIDDEN: {"model": ErrorResponse}},
    summary="Update scoring weights and RAG breakpoints",
)
def update_config(
    payload: ComplianceConfigUpdate,
    current_user: ComplianceAdminUser,
    db: DbSession,
    audit: AuditDep,
    request: Request,
) -> ComplianceConfigRead:
    """Persist any subset of the configuration with audit entries."""
    if payload.severity_weights is not None:
        _upsert_config_key(
            db,
            audit,
            current_user,
            request,
            key="severity_weights",
            value=payload.severity_weights.model_dump(),
        )
    if payload.rag_breakpoints is not None:
        _upsert_config_key(
            db,
            audit,
            current_user,
            request,
            key="rag_breakpoints",
            value=payload.rag_breakpoints.model_dump(),
        )
    db.commit()
    return compliance_admin.get_compliance_config_read(db)


def _upsert_config_key(
    db: DbSession,
    audit: AuditService,
    actor: User,
    request: Request,
    *,
    key: str,
    value: dict[str, float],
) -> None:
    """Insert or update one configuration key with an audit entry."""
    row = db.scalar(select(ComplianceConfig).where(ComplianceConfig.key == key))
    if row is None:
        row = ComplianceConfig(key=key, value=value)
        db.add(row)
        db.flush()
        audit.log(
            actor,
            "compliance.config.create",
            "ComplianceConfig",
            row.id,
            after={"key": key, "value": value},
            request=request,
        )
        return
    before = {"key": key, "value": dict(row.value)}
    row.value = value
    db.flush()
    audit.log(
        actor,
        "compliance.config.update",
        "ComplianceConfig",
        row.id,
        before=before,
        after={"key": key, "value": value},
        request=request,
    )


@router.get(
    "/monitor",
    response_model=ComplianceMonitorPage,
    responses={status.HTTP_403_FORBIDDEN: {"model": ErrorResponse}},
    summary="Institution monitoring list with the latest status",
)
def monitor(
    current_user: ComplianceAdminUser,
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ComplianceMonitorPage:
    """Return scoped institutions with their newest evaluation snapshot."""
    institutions = _scoped_institutions(current_user, db)
    total = len(institutions)
    window = institutions[(page - 1) * page_size : (page - 1) * page_size + page_size]
    by_institution = compliance_admin.group_latest_snapshots(
        db, [institution.id for institution in window]
    )
    latest_application: dict[uuid.UUID, Application] = {}
    for row in db.scalars(
        select(Application).order_by(Application.created_at.desc())
    ).all():
        latest_application.setdefault(row.institution_id, row)

    items = [
        ComplianceMonitorRead(
            institution_id=institution.id,
            institution_name=institution.name,
            region=institution.region,
            state=institution.state,
            latest_score=(
                float(snapshot.score) if (snapshot := by_institution.get(institution.id)) else None
            ),
            latest_status=snapshot.status.value if snapshot else None,
            latest_failed_count=snapshot.failed_count if snapshot else None,
            latest_missing_count=snapshot.missing_count if snapshot else None,
            latest_evaluated_at=snapshot.evaluated_at if snapshot else None,
            latest_trigger=snapshot.trigger if snapshot else None,
            application_id=(
                application.id if (application := latest_application.get(institution.id)) else None
            ),
            application_reference=application.reference if application else None,
        )
        for institution in window
    ]
    return ComplianceMonitorPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/monitor/run",
    response_model=ComplianceMonitorRunRead,
    responses={status.HTTP_403_FORBIDDEN: {"model": ErrorResponse}},
    summary="Re-evaluate monitoring for every institution in scope",
)
def run_monitor(
    current_user: ComplianceAdminUser,
    db: DbSession,
    clock: ClockDep,
) -> ComplianceMonitorRunRead:
    """Run the evaluation immediately instead of waiting for the nightly job."""
    institutions = _scoped_institutions(current_user, db)
    results = run_nightly_evaluation(
        evaluated_at=clock.now(),
        trigger="manual",
        institution_ids=[institution.id for institution in institutions],
    )
    counts = {
        health: sum(result["status"] == health for result in results)
        for health in ("RED", "AMBER", "GREEN")
    }
    return ComplianceMonitorRunRead(
        evaluated=len(results),
        red=counts["RED"],
        amber=counts["AMBER"],
        green=counts["GREEN"],
        message=(
            f"Re-evaluated {len(results)} institution"
            f"{'s' if len(results) != 1 else ''}: "
            f"{counts['RED']} RED, {counts['AMBER']} AMBER, {counts['GREEN']} GREEN."
        ),
    )


@router.get(
    "/institutions/{institution_id}/trend",
    response_model=ComplianceInstitutionTrendRead,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    summary="Score trend for one institution",
)
def institution_trend(
    institution_id: uuid.UUID,
    current_user: ComplianceAdminUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ComplianceInstitutionTrendRead:
    """Return the stored snapshot history for an institution (chart series)."""
    institution = db.get(Institution, institution_id)
    if institution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Institution not found",
        )
    if (
        current_user.role == Role.REGIONAL_HEAD
        and current_user.region
        and institution.region != current_user.region
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this institution",
        )
    snapshots = list(
        db.scalars(
            select(ComplianceSnapshot)
            .where(ComplianceSnapshot.institution_id == institution_id)
            .order_by(
                ComplianceSnapshot.evaluated_at.desc(),
                ComplianceSnapshot.created_at.desc(),
            )
            .limit(limit)
        ).all()
    )
    snapshots.reverse()  # chart series oldest -> newest
    return ComplianceInstitutionTrendRead(
        institution_id=institution.id,
        institution_name=institution.name,
        region=institution.region,
        points=[
            ComplianceTrendPoint(
                snapshot_id=snapshot.id,
                score=float(snapshot.score),
                status=snapshot.status.value,
                failed_count=snapshot.failed_count,
                missing_count=snapshot.missing_count,
                trigger=snapshot.trigger,
                evaluated_at=snapshot.evaluated_at,
                application_id=snapshot.application_id,
            )
            for snapshot in snapshots
        ],
    )
