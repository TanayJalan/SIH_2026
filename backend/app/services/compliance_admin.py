"""Compliance admin logic: impact preview and monitoring helpers.

Rule CRUD itself lives in the API layer; this module holds the read/write
evaluation logic that supports the admin screen and audit trail.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.application import Application
from app.models.compliance import (
    ComplianceConfig,
    ComplianceRule,
    ComplianceSnapshot,
)
from app.models.enums import ComplianceHealth, Severity
from app.models.institution import Institution
from app.schemas.application_sections import ApplicationData
from app.schemas.compliance import (
    ComplianceConfigRead,
    ComplianceRuleCreate,
    RagBreakpointsConfig,
    RuleImpactInstitution,
    SeverityWeightsConfig,
)
from app.services.compliance import (
    _DEFAULT_RAG_BREAKPOINTS,
    _DEFAULT_SEVERITY_WEIGHTS,
    _applies_to_application,
    _evaluate_rule,
    _rag_status,
    _weighted_score,
    application_metric_values,
)

_STATUS_RANK = {
    ComplianceHealth.GREEN: 0,
    ComplianceHealth.AMBER: 1,
    ComplianceHealth.RED: 2,
}

_MAX_AFFECTED_INSTITUTIONS = 20


def rule_snapshot(rule: ComplianceRule) -> dict[str, object]:
    """A JSON-safe snapshot of a rule for audit entries."""
    return {
        "code": rule.code,
        "name": rule.name,
        "category": rule.category,
        "description": rule.description,
        "metric_key": rule.metric_key,
        "operator": rule.operator,
        "threshold": float(rule.threshold),
        "threshold_max": (
            float(rule.threshold_max) if rule.threshold_max is not None else None
        ),
        "severity": rule.severity.value,
        "applies_to": rule.applies_to,
        "apH_clause": rule.apH_clause,
        "needs_verification": rule.needs_verification,
        "is_active": rule.is_active,
    }


def _load_config_row(
    db: Session, key: str, defaults: dict[str, float]
) -> dict[str, float]:
    """Load one config row's values, overlaying them on the defaults."""
    merged = dict(defaults)
    row = db.scalar(select(ComplianceConfig).where(ComplianceConfig.key == key))
    if row is not None and isinstance(row.value, dict):
        merged.update(
            {
                str(name): float(value)
                for name, value in row.value.items()
                if name in merged and isinstance(value, (int, float))
            }
        )
    return merged


def get_compliance_config_read(db: Session) -> ComplianceConfigRead:
    """Load the editable configuration, falling back to defaults."""
    weights = SeverityWeightsConfig(
        **_load_config_row(db, "severity_weights", dict(_DEFAULT_SEVERITY_WEIGHTS))
    )
    breakpoints = RagBreakpointsConfig(
        **_load_config_row(db, "rag_breakpoints", dict(_DEFAULT_RAG_BREAKPOINTS))
    )
    updated_at = db.scalar(
        select(ComplianceConfig.updated_at)
        .order_by(ComplianceConfig.updated_at.desc())
        .limit(1)
    )
    return ComplianceConfigRead(
        severity_weights=weights,
        rag_breakpoints=breakpoints,
        updated_at=updated_at,
    )


def group_latest_snapshots(
    db: Session, institution_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, ComplianceSnapshot]:
    """Return the newest snapshot per institution id."""
    latest: dict[uuid.UUID, ComplianceSnapshot] = {}
    if not institution_ids:
        return latest
    snapshots = db.scalars(
        select(ComplianceSnapshot)
        .where(ComplianceSnapshot.institution_id.in_(institution_ids))
        .order_by(
            ComplianceSnapshot.evaluated_at.desc(),
            ComplianceSnapshot.created_at.desc(),
        )
    ).all()
    for snapshot in snapshots:
        latest.setdefault(snapshot.institution_id, snapshot)
    return latest


def preview_rule_impact(
    db: Session,
    *,
    proposed: ComplianceRuleCreate,
    rule_id: uuid.UUID | None,
    institutions: Sequence[Institution],
) -> tuple[int, int, int, int, list[RuleImpactInstitution]]:
    """Compare projected monitoring statuses with stored latest statuses.

    Returns ``(red_flips, amber_flips, improved, unchanged, affected)``.
    Institutions without an application or without a stored snapshot cannot
    be projected and are skipped: the stored latest snapshot is the baseline.
    """
    from app.services.compliance import load_compliance_config

    weights, breakpoints = load_compliance_config(db)
    active_rules = list(
        db.scalars(select(ComplianceRule).where(ComplianceRule.is_active.is_(True)))
    )
    red_flips = amber_flips = improved = unchanged = 0
    affected: list[RuleImpactInstitution] = []

    for institution in institutions:
        application = db.scalar(
            select(Application)
            .options(
                selectinload(Application.programs),
                selectinload(Application.documents),
            )
            .where(Application.institution_id == institution.id)
            .order_by(Application.created_at.desc())
            .limit(1)
        )
        if application is None:
            continue
        latest_status = db.scalar(
            select(ComplianceSnapshot.status)
            .where(ComplianceSnapshot.institution_id == institution.id)
            .order_by(ComplianceSnapshot.evaluated_at.desc())
            .limit(1)
        )
        if latest_status is None:
            continue

        projected_status = _projected_status(
            application=application,
            active_rules=active_rules,
            proposed=proposed,
            rule_id=rule_id,
            weights=weights,
            breakpoints=breakpoints,
        )
        current_rank = _STATUS_RANK[latest_status]
        projected_rank = _STATUS_RANK[projected_status]
        if projected_rank > current_rank:
            if projected_status == ComplianceHealth.RED:
                red_flips += 1
            else:
                amber_flips += 1
            if len(affected) < _MAX_AFFECTED_INSTITUTIONS:
                affected.append(
                    RuleImpactInstitution(
                        institution_id=institution.id,
                        institution_name=institution.name,
                        region=institution.region,
                        current_status=latest_status.value,
                        projected_status=projected_status.value,
                    )
                )
        elif projected_rank < current_rank:
            improved += 1
        else:
            unchanged += 1
    return red_flips, amber_flips, improved, unchanged, affected


def _projected_status(
    *,
    application: Application,
    active_rules: list[ComplianceRule],
    proposed: ComplianceRuleCreate,
    rule_id: uuid.UUID | None,
    weights: dict[str, float],
    breakpoints: dict[str, float],
) -> ComplianceHealth:
    """Evaluate the rule set as it would exist after the proposed change."""
    data = ApplicationData.model_validate(application.data or {})
    metrics = application_metric_values(
        data,
        programs=list(application.programs),
        documents=list(application.documents),
    )

    severity_results: list[tuple[Severity, bool]] = []
    failed_critical = 0
    for rule in active_rules:
        if rule_id is not None and rule.id == rule_id:
            continue  # the proposed rule replaces this one
        if not _applies_to_application(rule, application):
            continue
        preview = _evaluate_rule(rule, metrics.get(rule.metric_key))
        if preview.status == "NOT_ASSESSED":
            continue
        severity_results.append((rule.severity, preview.status == "PASS"))
        if preview.status == "FAIL" and rule.severity == Severity.CRITICAL:
            failed_critical += 1

    if proposed.is_active:
        replacement = ComplianceRule(
            code=proposed.code,
            name=proposed.name,
            category=proposed.category,
            description=proposed.description,
            metric_key=proposed.metric_key,
            operator=proposed.operator,
            threshold=Decimal(str(proposed.threshold)),
            threshold_max=(
                Decimal(str(proposed.threshold_max))
                if proposed.threshold_max is not None
                else None
            ),
            severity=proposed.severity,
            applies_to=proposed.applies_to,
            apH_clause=proposed.apH_clause,
            needs_verification=proposed.needs_verification,
            is_active=True,
        )
        if _applies_to_application(replacement, application):
            preview = _evaluate_rule(replacement, metrics.get(replacement.metric_key))
            if preview.status != "NOT_ASSESSED":
                severity_results.append((replacement.severity, preview.status == "PASS"))
                if preview.status == "FAIL" and replacement.severity == Severity.CRITICAL:
                    failed_critical += 1

    score = _weighted_score(severity_results, weights)
    return _rag_status(
        failed_critical_count=failed_critical,
        score=score,
        breakpoints=breakpoints,
    )
