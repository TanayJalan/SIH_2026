"""Compliance admin logic: impact preview and monitoring helpers.

Rule CRUD itself lives in the API layer; this module holds the read/write
evaluation logic that supports the admin screen and audit trail.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.application import Application
from app.models.compliance import (
    ComplianceConfig,
    ComplianceRule,
    ComplianceSnapshot,
)
from app.models.enums import ComplianceHealth
from app.models.institution import Institution
from app.schemas.application_sections import ApplicationData
from app.schemas.compliance import (
    BandwidthTierConfig,
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
    _build_preview,
    _evaluate_rule_from_metrics,
    _scope_metrics,
    build_rule_context,
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
        "applies_to_family": rule.applies_to_family,
        "applies_to_level": rule.applies_to_level,
        "apH_clause": rule.apH_clause,
        "needs_verification": rule.needs_verification,
        "mandatory": rule.mandatory,
        "illustrative": rule.illustrative,
        "weight": float(rule.weight) if rule.weight is not None else None,
        "unit": rule.unit,
        "explanation_template": rule.explanation_template,
        "metric_params": dict(rule.metric_params or {}),
        "penalty_codes": list(rule.penalty_codes or []),
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
    rows = {
        row.key: row.value
        for row in db.scalars(select(ComplianceConfig)).all()
        if isinstance(row.value, (dict, list))
    }

    def mapping(key: str) -> dict[str, Any]:
        value = rows.get(key)
        return dict(value) if isinstance(value, dict) else {}

    def floats(key: str) -> dict[str, float]:
        return {
            str(name): float(value)
            for name, value in mapping(key).items()
            if isinstance(value, (int, float))
        }

    def nested(key: str) -> dict[str, dict[str, float]]:
        return {
            str(name): {
                str(level): float(ratio)
                for level, ratio in value.items()
                if isinstance(ratio, (int, float))
            }
            for name, value in mapping(key).items()
            if isinstance(value, dict)
        }

    def cadre(key: str) -> dict[str, list[int]]:
        return {
            str(name): [int(part) for part in value]
            for name, value in mapping(key).items()
            if isinstance(value, list)
        }

    tiers = rows.get("bandwidth_tiers")
    bandwidth = (
        [BandwidthTierConfig(**tier) for tier in tiers]
        if isinstance(tiers, list)
        else []
    )
    updated_at = db.scalar(
        select(ComplianceConfig.updated_at)
        .order_by(ComplianceConfig.updated_at.desc())
        .limit(1)
    )
    return ComplianceConfigRead(
        severity_weights=weights,
        rag_breakpoints=breakpoints,
        fsr_ratios=nested("fsr_ratios"),
        cadre_ratios=cadre("cadre_ratios"),
        area_norms=floats("area_norms"),
        bandwidth_tiers=bandwidth,
        library_norms=floats("library_norms"),
        pc_ratios=nested("pc_ratios"),
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
    institutions without an application or without a stored snapshot cannot
    be projected and are skipped: the stored latest snapshot is the baseline.
    """
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
            db=db,
            application=application,
            active_rules=active_rules,
            proposed=proposed,
            rule_id=rule_id,
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
    db: Session,
    application: Application,
    active_rules: list[ComplianceRule],
    proposed: ComplianceRuleCreate,
    rule_id: uuid.UUID | None,
) -> ComplianceHealth:
    """Evaluate the rule set as it would exist after the proposed change."""
    data = ApplicationData.model_validate(application.data or {})
    context = build_rule_context(db, application, data)
    context.metrics.update(_scope_metrics(context))

    previews = [
        _evaluate_rule_from_metrics(
            rule,
            context.metrics,
            reference_date=context.reference_date,
        )
        for rule in active_rules
        if (rule_id is None or rule.id != rule_id)
        and _applies_to_application(rule, application)
    ]

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
            applies_to_family=proposed.applies_to_family,
            applies_to_level=proposed.applies_to_level,
            apH_clause=proposed.apH_clause,
            needs_verification=proposed.needs_verification,
            mandatory=proposed.mandatory,
            illustrative=proposed.illustrative,
            weight=(
                Decimal(str(proposed.weight))
                if proposed.weight is not None
                else None
            ),
            unit=proposed.unit,
            explanation_template=proposed.explanation_template,
            metric_params=dict(proposed.metric_params or {}),
            penalty_codes=list(proposed.penalty_codes or []),
            is_active=True,
        )
        if _applies_to_application(replacement, application):
            previews.append(
                _evaluate_rule_from_metrics(
                    replacement,
                    context.metrics,
                    reference_date=context.reference_date,
                )
            )

    preview = _build_preview(
        db,
        application=application,
        previews=previews,
        evaluated_at=datetime.now(UTC),
    )
    return ComplianceHealth(preview.status)
