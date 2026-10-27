"""Compliance admin endpoints: rules, config, monitoring and impact preview."""

import copy
import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select

from app.api.dependencies import AuditDep, ClockDep, DbSession, require_roles
from app.models.application import Application
from app.models.audit import AuditLog
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
    ComplianceRuleChangeRead,
    ComplianceRuleCreate,
    ComplianceRuleHistoryRead,
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
    Depends(require_roles(Role.SUPER_ADMIN, Role.REGIONAL_OFFICER)),
]


def _scoped_institutions(user: User, db: DbSession) -> list[Institution]:
    """Institutions inside the viewer's scope (regional heads see their region)."""
    query = select(Institution).order_by(Institution.name)
    if user.role == Role.REGIONAL_OFFICER and user.region:
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
    category: str | None = None,
    family: str | None = None,
    level: str | None = None,
    needs_verification: bool | None = None,
    illustrative: bool | None = None,
    mandatory: bool | None = None,
    search: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ComplianceRulePage:
    """Return the configurable rule catalogue with optional filters."""
    query = select(ComplianceRule)
    if not include_inactive:
        query = query.where(ComplianceRule.is_active.is_(True))
    if category:
        query = query.where(ComplianceRule.category == category)
    if family:
        query = query.where(ComplianceRule.applies_to_family == family)
    if level:
        query = query.where(ComplianceRule.applies_to_level == level)
    if needs_verification is not None:
        query = query.where(
            ComplianceRule.needs_verification.is_(needs_verification)
        )
    if illustrative is not None:
        query = query.where(ComplianceRule.illustrative.is_(illustrative))
    if mandatory is not None:
        query = query.where(ComplianceRule.mandatory.is_(mandatory))
    if search:
        needle = f"%{search.strip()}%"
        query = query.where(
            ComplianceRule.code.ilike(needle)
            | ComplianceRule.name.ilike(needle)
            | ComplianceRule.apH_clause.ilike(needle)
        )
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
        applies_to_family=payload.applies_to_family,
        applies_to_level=payload.applies_to_level,
        apH_clause=payload.apH_clause,
        needs_verification=payload.needs_verification,
        mandatory=payload.mandatory,
        illustrative=payload.illustrative,
        weight=Decimal(str(payload.weight)) if payload.weight is not None else None,
        unit=payload.unit,
        explanation_template=payload.explanation_template,
        metric_params=dict(payload.metric_params),
        penalty_codes=list(payload.penalty_codes),
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
        if rule.illustrative and not rule.needs_verification:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="an illustrative rule cannot claim a verified AICTE clause",
            )
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


@router.get(
    "/rules/{rule_id}/history",
    response_model=ComplianceRuleHistoryRead,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    summary="Audit history for one compliance rule",
)
def rule_history(
    rule_id: uuid.UUID,
    current_user: ComplianceAdminUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ComplianceRuleHistoryRead:
    """Return every audited change to a rule, newest first."""
    rule = _readable_rule(db, rule_id)
    entries = db.scalars(
        select(AuditLog)
        .where(
            AuditLog.entity_type == "ComplianceRule",
            AuditLog.entity_id == rule.id,
        )
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    ).all()
    actor_ids = {entry.actor_id for entry in entries if entry.actor_id is not None}
    actors = {
        user.id: user.name
        for user in (
            db.scalars(select(User).where(User.id.in_(actor_ids))).all()
            if actor_ids
            else []
        )
    }
    return ComplianceRuleHistoryRead(
        rule_id=rule.id,
        code=rule.code,
        items=[
            ComplianceRuleChangeRead(
                id=entry.id,
                action=entry.action,
                actor_name=actors.get(entry.actor_id) if entry.actor_id else None,
                created_at=entry.created_at,
                before=entry.before,
                after=entry.after,
                changed_fields=_changed_fields(entry.before, entry.after),
            )
            for entry in entries
        ],
    )


def _changed_fields(
    before: dict[str, object] | None, after: dict[str, object] | None
) -> list[str]:
    """Field names whose values differ between two audit snapshots."""
    if not before or not after:
        return sorted((after or before or {}).keys())
    return sorted(
        key
        for key in set(before) | set(after)
        if before.get(key) != after.get(key)
    )


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
    payload_values: dict[str, object] = {}
    if payload.severity_weights is not None:
        payload_values["severity_weights"] = payload.severity_weights.model_dump()
    if payload.rag_breakpoints is not None:
        payload_values["rag_breakpoints"] = payload.rag_breakpoints.model_dump()
    if payload.fsr_ratios is not None:
        payload_values["fsr_ratios"] = payload.fsr_ratios
    if payload.cadre_ratios is not None:
        payload_values["cadre_ratios"] = payload.cadre_ratios
    if payload.area_norms is not None:
        payload_values["area_norms"] = payload.area_norms
    if payload.bandwidth_tiers is not None:
        payload_values["bandwidth_tiers"] = [
            tier.model_dump() for tier in payload.bandwidth_tiers
        ]
    if payload.library_norms is not None:
        payload_values["library_norms"] = payload.library_norms
    if payload.pc_ratios is not None:
        payload_values["pc_ratios"] = payload.pc_ratios
    for key, value in payload_values.items():
        _upsert_config_key(
            db,
            audit,
            current_user,
            request,
            key=key,
            value=value,
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
    value: object,
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
    before = {"key": key, "value": copy.deepcopy(row.value)}
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
    snapshot_application_ids = {
        snapshot.application_id
        for snapshot in by_institution.values()
        if snapshot.application_id is not None
    }
    applications: dict[uuid.UUID, Application] = (
        {
            application.id: application
            for application in db.scalars(
                select(Application).where(
                    Application.id.in_(snapshot_application_ids)
                )
            ).all()
        }
        if snapshot_application_ids
        else {}
    )

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
            application_id=snapshot.application_id if snapshot else None,
            application_reference=(
                applications[snapshot.application_id].reference
                if snapshot
                and snapshot.application_id is not None
                and snapshot.application_id in applications
                else None
            ),
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
        current_user.role == Role.REGIONAL_OFFICER
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
