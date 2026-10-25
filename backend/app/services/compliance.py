"""Evaluate database-configured compliance rules against application data.

Rules are database rows; the evaluator is a small, safe comparison engine
(``_OPERATORS``) — no ``eval()`` is used anywhere in this module. The service
layer provides:

* metric extraction from form data, programmes, documents and accreditation,
* per-rule evaluation with human-readable explanations,
* a weighted 0-100 score derived from admin-editable severity weights,
* RED/AMBER/GREEN monitoring status with configurable breakpoints,
* institution-level evaluation with append-only snapshots for trend charts,
* alert creation when an institution's status worsens to RED.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.models.application import Application, ApplicationProgram
from app.models.compliance import (
    ComplianceConfig,
    ComplianceResult,
    ComplianceRule,
    ComplianceSnapshot,
)
from app.models.document import Document
from app.models.enums import (
    ComplianceHealth,
    DocumentVerificationStatus,
    Severity,
)
from app.models.institution import Institution
from app.schemas.application_sections import ApplicationData
from app.schemas.compliance import (
    CompliancePreviewRead,
    ComplianceRulePreview,
    ComplianceRuleStatus,
)

logger = logging.getLogger("app.compliance")

Operator = Callable[[Decimal, Decimal], bool]

_OPERATORS: dict[str, Operator] = {
    "<": lambda observed, threshold: observed < threshold,
    "<=": lambda observed, threshold: observed <= threshold,
    "=": lambda observed, threshold: observed == threshold,
    "==": lambda observed, threshold: observed == threshold,
    ">=": lambda observed, threshold: observed >= threshold,
    ">": lambda observed, threshold: observed > threshold,
    "!=": lambda observed, threshold: observed != threshold,
}

_OPERATOR_PHRASES = {
    "<": "below",
    "<=": "at most",
    "=": "equal to",
    "==": "equal to",
    ">=": "at least",
    ">": "above",
    "!=": "different from",
}

_SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

_DEFAULT_SEVERITY_WEIGHTS = {
    Severity.CRITICAL.value: 25.0,
    Severity.HIGH.value: 15.0,
    Severity.MEDIUM.value: 8.0,
    Severity.LOW.value: 4.0,
}

_DEFAULT_RAG_BREAKPOINTS = {
    "red_below": 70.0,
    "amber_below": 85.0,
}
"""Score thresholds: RED below ``red_below``, AMBER below ``amber_below``.
Any failed CRITICAL rule forces RED regardless of score."""

_METRIC_METADATA: dict[str, tuple[str, str | None]] = {
    "infrastructure.land_area": ("Land area", "sq. m"),
    "infrastructure.built_up_area": ("Built-up area", "sq. m"),
    "infrastructure.labs": ("Laboratories", "count"),
    "infrastructure.library": ("Library volumes", "volumes"),
    "infrastructure.hostel": ("Hostel capacity", "beds"),
    "faculty.total": ("Total faculty", "count"),
    "faculty.professors": ("Professors", "count"),
    "faculty.associate_professors": ("Associate professors", "count"),
    "faculty.assistant_professors": ("Assistant professors", "count"),
    "faculty.student_faculty_ratio": ("Student-faculty ratio", "students/faculty"),
    "faculty.phd_faculty_ratio": ("Faculty with PhD", "%"),
    "finance.tuition_fee": ("Tuition fee", "INR/year"),
    "finance.development_fee": ("Development fee", "INR/year"),
    "finance.other_fees": ("Other fees", "INR/year"),
    "finance.balance": ("Declared balance", "INR"),
    "finance.total_annual_fee": ("Total annual fee", "INR/year"),
    "derived.qualified_faculty_pct": ("Qualified faculty share", "%"),
    "derived.built_up_area_per_student": ("Built-up area per student", "sq. m/student"),
    "derived.library_books_per_student": ("Library volumes per student", "volumes/student"),
    "derived.lab_count_per_program": ("Laboratories per programme", "count/programme"),
    "derived.total_intake": ("Approved intake", "seats"),
    "derived.naac_grade_present": ("NAAC grade declared", None),
    "derived.nba_accredited_programs_pct": ("NBA accredited programmes", "%"),
    "derived.mandatory_disclosure_published": ("Mandatory disclosure published", None),
    "derived.document_validity": ("Verified documents valid", None),
}


# --------------------------------------------------------------------------
# Config (severity weights + RAG breakpoints)
# --------------------------------------------------------------------------


def load_compliance_config(db: Session) -> tuple[dict[str, float], dict[str, float]]:
    """Return ``(severity_weights, rag_breakpoints)`` with defaults filled in."""
    weights: dict[str, float] = dict(_DEFAULT_SEVERITY_WEIGHTS)
    breakpoints: dict[str, float] = dict(_DEFAULT_RAG_BREAKPOINTS)
    rows = db.scalars(select(ComplianceConfig)).all()
    for row in rows:
        if row.key == "severity_weights" and isinstance(row.value, dict):
            for severity, weight in row.value.items():
                if severity in weights and isinstance(weight, (int, float)):
                    weights[severity] = float(weight)
        elif row.key == "rag_breakpoints" and isinstance(row.value, dict):
            for name, bound in row.value.items():
                if name in breakpoints and isinstance(bound, (int, float)):
                    breakpoints[name] = float(bound)
    return weights, breakpoints


def _weighted_score(
    results: Sequence[tuple[Severity, bool]],
    weights: dict[str, float],
) -> float:
    """Weighted 0-100 score: earned weight over assessed weight."""
    earned = 0.0
    possible = 0.0
    for severity, passed in results:
        weight = weights.get(severity.value, 0.0)
        possible += weight
        if passed:
            earned += weight
    if possible <= 0:
        return 0.0
    return round(earned / possible * 100, 2)


def _rag_status(
    *,
    failed_critical_count: int,
    score: float,
    breakpoints: dict[str, float],
) -> ComplianceHealth:
    if failed_critical_count > 0 or score < breakpoints["red_below"]:
        return ComplianceHealth.RED
    if score < breakpoints["amber_below"]:
        return ComplianceHealth.AMBER
    return ComplianceHealth.GREEN


# --------------------------------------------------------------------------
# Metric extraction
# --------------------------------------------------------------------------


def _numeric(value: object | None) -> float | None:
    if value is None:
        return None
    return float(value)


def application_metric_values(
    data: ApplicationData,
    *,
    programs: Iterable[ApplicationProgram] = (),
    documents: Iterable[Document] = (),
    document_reference_date: date | None = None,
) -> dict[str, float | None]:
    """Return every metric a rule can reference for the given data.

    Raw metrics come from the draft form values; derived metrics are computed
    from programmes, documents and accreditation entries. Derived per-student
    values use *approved intake* as the denominator, which is a documented
    proxy — approved intake is the closest programme-level student figure the
    application collects.
    """
    infrastructure = data.infrastructure
    faculty = data.faculty
    finance = data.finance

    metrics: dict[str, float | None] = {
        "infrastructure.land_area": _numeric(
            infrastructure.land_area if infrastructure else None
        ),
        "infrastructure.built_up_area": _numeric(
            infrastructure.built_up_area if infrastructure else None
        ),
        "infrastructure.labs": _numeric(infrastructure.labs if infrastructure else None),
        "infrastructure.library": _numeric(
            infrastructure.library if infrastructure else None
        ),
        "infrastructure.hostel": _numeric(infrastructure.hostel if infrastructure else None),
        "faculty.total": _numeric(faculty.total if faculty else None),
        "faculty.professors": _numeric(faculty.professors if faculty else None),
        "faculty.associate_professors": _numeric(
            faculty.associate_professors if faculty else None
        ),
        "faculty.assistant_professors": _numeric(
            faculty.assistant_professors if faculty else None
        ),
        "faculty.student_faculty_ratio": _numeric(
            faculty.student_faculty_ratio if faculty else None
        ),
        "faculty.phd_faculty_ratio": _numeric(
            faculty.phd_faculty_ratio if faculty else None
        ),
        "finance.tuition_fee": _numeric(finance.tuition_fee if finance else None),
        "finance.development_fee": _numeric(
            finance.development_fee if finance else None
        ),
        "finance.other_fees": _numeric(finance.other_fees if finance else None),
        "finance.balance": _numeric(finance.balance if finance else None),
    }

    metrics.update(
        _derived_metrics(
            data,
            programs=programs,
            documents=documents,
            document_reference_date=document_reference_date,
        )
    )
    return metrics


def _derived_metrics(
    data: ApplicationData,
    *,
    programs: Iterable[ApplicationProgram],
    documents: Iterable[Document],
    document_reference_date: date | None,
) -> dict[str, float | None]:
    """Compute derived metrics; each is ``None`` when its inputs are missing."""
    program_list = list(programs)
    document_list = list(documents)
    infrastructure = data.infrastructure
    faculty = data.faculty
    finance = data.finance

    total_intake = sum(program.intake for program in program_list)
    derived: dict[str, float | None] = {
        "derived.total_intake": float(total_intake) if program_list else None,
    }

    # Faculty composition share (permanent-rank faculty as a proxy for
    # qualified faculty; illustrative for the demo).
    if faculty and faculty.total:
        senior = (faculty.professors or 0) + (faculty.associate_professors or 0) + (
            faculty.assistant_professors or 0
        )
        derived["derived.qualified_faculty_pct"] = round(senior / faculty.total * 100, 2)
    else:
        derived["derived.qualified_faculty_pct"] = None

    if infrastructure and total_intake > 0:
        derived["derived.built_up_area_per_student"] = round(
            infrastructure.built_up_area / total_intake, 2
        )
        derived["derived.library_books_per_student"] = round(
            infrastructure.library / total_intake, 2
        )
    else:
        derived["derived.built_up_area_per_student"] = None
        derived["derived.library_books_per_student"] = None

    if program_list:
        derived["derived.lab_count_per_program"] = round(
            sum(program.lab_count for program in program_list) / len(program_list), 2
        )
    else:
        derived["derived.lab_count_per_program"] = None

    accreditation = data.accreditation
    if accreditation is None:
        derived["derived.naac_grade_present"] = None
        derived["derived.nba_accredited_programs_pct"] = None
    else:
        naac = accreditation.naac_grade
        derived["derived.naac_grade_present"] = 1.0 if (
            naac is not None and naac != "NOT_ACCREDITED"
        ) else 0.0
        derived["derived.nba_accredited_programs_pct"] = (
            100.0 if accreditation.nba_status == "ACCREDITED" else 0.0
        )

    derived["derived.mandatory_disclosure_published"] = (
        1.0 if data.mandatory_disclosure_url else 0.0
    )

    if finance is not None and any(
        (finance.tuition_fee, finance.development_fee, finance.other_fees)
    ):
        derived["finance.total_annual_fee"] = round(
            (finance.tuition_fee or 0)
            + (finance.development_fee or 0)
            + (finance.other_fees or 0),
            2,
        )
    else:
        derived["finance.total_annual_fee"] = None

    derived["derived.document_validity"] = _document_validity(
        document_list, document_reference_date
    )
    return derived


def _document_validity(
    documents: Sequence[Document],
    reference_date: date | None,
) -> float | None:
    """1.0 when every uploaded document is valid, 0.0 when any is not.

    Invalid means REJECTED/FLAGGED verification or an expiry date in the past.
    ``None`` when no documents have been uploaded yet.
    """
    document_list = list(documents)
    if not document_list:
        return None
    today = reference_date or datetime.now(UTC).date()
    for document in document_list:
        if document.verification_status in (
            DocumentVerificationStatus.REJECTED,
            DocumentVerificationStatus.FLAGGED,
        ):
            return 0.0
        if document.expiry_date is not None and document.expiry_date < today:
            return 0.0
    return 1.0


# --------------------------------------------------------------------------
# Rule evaluation
# --------------------------------------------------------------------------


def _applies_to_application(rule: ComplianceRule, application: Application) -> bool:
    """Return whether a rule's scope matches this application.

    ``applies_to`` is a comma-separated list of scopes. A scope may be an
    APH application type (``NEW_INSTITUTION``, ``EOA_SELF_DISCLOSURE``,
    ``INCREASE_INTAKE``) or a programme level (``UG``, ``PG``). ``ALL``
    always matches. A level-scoped rule only runs when the application
    requests a programme at that level.
    """
    targets = {
        target.strip().upper()
        for target in rule.applies_to.split(",")
        if target.strip()
    }
    if "ALL" in targets:
        return True
    if str(application.application_type).upper() in targets:
        return True
    return any(program.level.strip().upper() in targets for program in application.programs)


def _format_number(value: Decimal | float) -> str:
    decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    normalised = decimal_value.normalize()
    if normalised == normalised.to_integral():
        return f"{int(normalised):,}"
    return f"{normalised:,.2f}".rstrip("0").rstrip(".")


def _metric_label(metric_key: str) -> tuple[str, str | None]:
    return _METRIC_METADATA.get(
        metric_key,
        (metric_key.replace(".", " ").replace("_", " ").title(), None),
    )


def available_metric_catalogue() -> list[dict[str, str | None]]:
    """Return the metrics a rule may reference, for the admin rule editor."""
    return [
        {"key": key, "label": label, "unit": unit}
        for key, (label, unit) in sorted(
            _METRIC_METADATA.items(), key=lambda item: item[1][0]
        )
    ]


def _not_assessed_message(metric_key: str) -> str:
    label, _ = _metric_label(metric_key)
    return f"Data missing: no value found for {label}; this rule was not assessed."


def _threshold_text(
    operator: str,
    threshold: Decimal,
    threshold_max: Decimal | None,
    unit: str | None,
) -> str:
    suffix = f" {unit}" if unit else ""
    if operator == "BETWEEN":
        upper = _format_number(threshold_max) if threshold_max is not None else "?"
        return f"between {_format_number(threshold)}{suffix} and {upper}{suffix}"
    if operator == "EXISTS":
        return "a declared value"
    phrase = _OPERATOR_PHRASES.get(operator, operator)
    return f"{phrase} {_format_number(threshold)}{suffix}"


def _rule_message(
    *,
    metric_key: str,
    operator: str,
    threshold: Decimal,
    threshold_max: Decimal | None,
    observed: Decimal,
) -> str:
    """Explain the outcome, e.g. "Student-faculty ratio: 27; rule requires
    at most 20 students/faculty"."""
    label, unit = _metric_label(metric_key)
    suffix = f" {unit}" if unit else ""
    if operator == "EXISTS":
        return f"{label}: value declared (present)."
    if operator == "BETWEEN":
        expected = _threshold_text(operator, threshold, threshold_max, unit)
        return f"{label}: {_format_number(observed)}{suffix}; expected {expected}."
    return (
        f"{label}: {_format_number(observed)}{suffix}; "
        f"configured rule requires {_threshold_text(operator, threshold, None, unit)}."
    )


def _rule_explanation(
    rule: ComplianceRule,
    *,
    status: ComplianceRuleStatus,
    observed_value: float | None,
    threshold: Decimal,
    threshold_max: Decimal | None,
    unit: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the evidence and the criteria/values/pass-fail explanation.

    The explanation is stored on every persisted result and returned with every
    preview so a reviewer can see *why* a rule passed, failed or was skipped,
    which APH clause backs it, and whether the clause still needs verification.
    """
    observed = float(observed_value) if observed_value is not None else None
    bounds = {
        "operator": rule.operator,
        "threshold": float(threshold),
        "threshold_max": float(threshold_max) if threshold_max is not None else None,
        "unit": unit,
    }
    evidence = {"metric_key": rule.metric_key, "observed_value": observed, **bounds}
    explanation = {
        "criteria": rule.description,
        "metric_key": rule.metric_key,
        "observed_value": observed,
        **bounds,
        "status": status,
        "passed": None if status == "NOT_ASSESSED" else status == "PASS",
        "apH_clause": rule.apH_clause,
        "needs_verification": rule.needs_verification,
    }
    return evidence, explanation


def _evaluate_rule(
    rule: ComplianceRule,
    observed_value: float | None,
) -> ComplianceRulePreview:
    _, unit = _metric_label(rule.metric_key)
    threshold = Decimal(rule.threshold)
    threshold_max = Decimal(rule.threshold_max) if rule.threshold_max is not None else None
    if observed_value is None:
        status: ComplianceRuleStatus = "NOT_ASSESSED"
        message = _not_assessed_message(rule.metric_key)
    else:
        observed_decimal = Decimal(str(observed_value))
        if rule.operator == "EXISTS":
            passed = True
            status = "PASS"
        elif rule.operator == "BETWEEN":
            passed = observed_decimal >= threshold and (
                threshold_max is None or observed_decimal <= threshold_max
            )
            status = "PASS" if passed else "FAIL"
        else:
            comparison = _OPERATORS.get(rule.operator)
            passed = bool(comparison and comparison(observed_decimal, threshold))
            status = "PASS" if passed else "FAIL"
        message = _rule_message(
            metric_key=rule.metric_key,
            operator=rule.operator,
            threshold=threshold,
            threshold_max=threshold_max,
            observed=observed_decimal,
        )

    evidence, explanation = _rule_explanation(
        rule,
        status=status,
        observed_value=observed_value,
        threshold=threshold,
        threshold_max=threshold_max,
        unit=unit,
    )

    return ComplianceRulePreview(
        code=rule.code,
        name=rule.name,
        category=rule.category,
        description=rule.description,
        severity=rule.severity,
        metric_key=rule.metric_key,
        operator=rule.operator,
        threshold=float(threshold),
        threshold_max=float(threshold_max) if threshold_max is not None else None,
        unit=unit,
        observed_value=observed_value,
        status=status,
        message=message,
        evidence=evidence,
        explanation=explanation,
    )


def load_active_rules(db: Session) -> list[ComplianceRule]:
    """Return every active compliance rule."""
    return list(
        db.scalars(select(ComplianceRule).where(ComplianceRule.is_active.is_(True)))
    )


def evaluate_compliance(
    db: Session,
    application: Application,
    data: ApplicationData,
    *,
    evaluated_at: datetime,
    documents: Sequence[Document] | None = None,
) -> CompliancePreviewRead:
    """Evaluate active rules against the given (possibly unsaved) values."""
    rules = load_active_rules(db)
    if documents is None:
        documents = list(application.documents)
    program_list = list(application.programs)
    metrics = application_metric_values(
        data,
        programs=program_list,
        documents=documents,
    )
    previews = [
        _evaluate_rule(rule, metrics.get(rule.metric_key))
        for rule in rules
        if _applies_to_application(rule, application)
    ]
    return _build_preview(
        application=application,
        previews=previews,
        evaluated_at=evaluated_at,
    )


def _build_preview(
    *,
    application: Application,
    previews: list[ComplianceRulePreview],
    evaluated_at: datetime,
) -> CompliancePreviewRead:
    weights, breakpoints = _config_for(application)
    severity_results = [
        (rule.severity, rule.status == "PASS")
        for rule in previews
        if rule.status != "NOT_ASSESSED"
    ]
    score = _weighted_score(
        severity_results,
        _weights_by_severity(weights),
    )
    failed_count = sum(rule.status == "FAIL" for rule in previews)
    not_assessed_count = sum(rule.status == "NOT_ASSESSED" for rule in previews)
    passed_count = len(previews) - failed_count - not_assessed_count
    failed_critical_count = sum(
        rule.status == "FAIL" and rule.severity == Severity.CRITICAL
        for rule in previews
    )
    status = _rag_status(
        failed_critical_count=failed_critical_count,
        score=score,
        breakpoints=breakpoints,
    )
    if failed_count or not_assessed_count:
        outcome = "ATTENTION" if failed_count else "INCOMPLETE"
    else:
        outcome = "PASS"

    previews.sort(
        key=lambda rule: (
            _SEVERITY_ORDER.get(rule.severity.value, len(_SEVERITY_ORDER)),
            rule.category,
            rule.name,
        )
    )

    return CompliancePreviewRead(
        application_id=application.id,
        evaluated_at=evaluated_at,
        rules=previews,
        passed_count=passed_count,
        failed_count=failed_count,
        not_assessed_count=not_assessed_count,
        assessed_count=passed_count + failed_count,
        score=score,
        outcome=outcome,
        status=status.value,
    )


def _config_for(application: Application) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load config from the owning session of the application, if any.

    Falls back to defaults when the object is detached or the session is gone.
    """
    session = Session.object_session(application)
    if session is None:
        return dict(_DEFAULT_SEVERITY_WEIGHTS), dict(_DEFAULT_RAG_BREAKPOINTS)
    return load_compliance_config(session)


def _weights_by_severity(weights: dict[str, Any]) -> dict[str, float]:
    return {
        severity: float(weight)
        for severity, weight in weights.items()
        if isinstance(weight, (int, float))
    }


# --------------------------------------------------------------------------
# Persistent evaluation + snapshots + alerts
# --------------------------------------------------------------------------


def evaluate_application(
    db: Session,
    application: Application,
    *,
    evaluated_at: datetime,
    trigger: str = "manual",
    commit: bool = True,
) -> CompliancePreviewRead:
    """Evaluate, persist per-rule results, the score and a monitoring snapshot.

    This is the write path used on application updates and by the nightly
    monitor; ``evaluate_compliance`` is the read-only preview path.
    """
    data = ApplicationData.model_validate(application.data or {})
    previews_unsorted = []
    rules = load_active_rules(db)
    metrics = application_metric_values(
        data,
        programs=list(application.programs),
        documents=list(application.documents),
    )
    for rule in rules:
        if not _applies_to_application(rule, application):
            continue
        previews_unsorted.append(_evaluate_rule(rule, metrics.get(rule.metric_key)))

    weights, breakpoints = load_compliance_config(db)
    severity_results = [
        (rule.severity, rule.status == "PASS")
        for rule in previews_unsorted
        if rule.status != "NOT_ASSESSED"
    ]
    score = _weighted_score(severity_results, _weights_by_severity(weights))
    failed_critical_count = sum(
        preview.status == "FAIL" and preview.severity == Severity.CRITICAL
        for preview in previews_unsorted
    )
    failed_count = sum(preview.status == "FAIL" for preview in previews_unsorted)
    not_assessed_count = sum(
        preview.status == "NOT_ASSESSED" for preview in previews_unsorted
    )
    failed_high_count = sum(
        preview.status == "FAIL" and preview.severity == Severity.HIGH
        for preview in previews_unsorted
    )
    status = _rag_status(
        failed_critical_count=failed_critical_count,
        score=score,
        breakpoints=breakpoints,
    )
    passed_count = len(previews_unsorted) - failed_count - not_assessed_count

    previews_unsorted.sort(
        key=lambda rule: (
            _SEVERITY_ORDER.get(rule.severity.value, len(_SEVERITY_ORDER)),
            rule.category,
            rule.name,
        )
    )
    preview = CompliancePreviewRead(
        application_id=application.id,
        evaluated_at=evaluated_at,
        rules=previews_unsorted,
        passed_count=passed_count,
        failed_count=failed_count,
        not_assessed_count=not_assessed_count,
        assessed_count=passed_count + failed_count,
        score=score,
        outcome=(
            "ATTENTION"
            if failed_count
            else ("INCOMPLETE" if not_assessed_count else "PASS")
        ),
        status=status.value,
    )

    # Persist: replace the application's result set (point-in-time state) and
    # append an institution-level snapshot row for trend charts.
    db.execute(delete(ComplianceResult).where(ComplianceResult.application_id == application.id))
    rules_by_code = {rule.code: rule for rule in rules}
    for item in previews_unsorted:
        rule_row = rules_by_code[item.code]
        db.add(
            ComplianceResult(
                application_id=application.id,
                institution_id=application.institution_id,
                rule_id=rule_row.id,
                observed_value=(
                    Decimal(str(item.observed_value))
                    if item.observed_value is not None
                    else None
                ),
                status=item.status,
                message=item.message,
                evidence=item.evidence,
                explanation=item.explanation,
                passed=item.status == "PASS",
                evaluated_at=evaluated_at,
            )
        )
    application.compliance_score = Decimal(str(score))

    _create_snapshot(
        db,
        institution_id=application.institution_id,
        application_id=application.id,
        score=score,
        status=status,
        failed_count=failed_count,
        failed_critical_count=failed_critical_count,
        failed_high_count=failed_high_count,
        missing_count=not_assessed_count,
        trigger=trigger,
        evaluated_at=evaluated_at,
        previous_status=_latest_snapshot_status(db, application.institution_id),
        application=application,
    )
    if commit:
        db.commit()
    return preview


def _latest_snapshot_status(
    db: Session, institution_id: uuid.UUID
) -> ComplianceHealth | None:
    snapshot = db.scalar(
        select(ComplianceSnapshot)
        .where(ComplianceSnapshot.institution_id == institution_id)
        .order_by(ComplianceSnapshot.evaluated_at.desc(), ComplianceSnapshot.created_at.desc())
        .limit(1)
    )
    return snapshot.status if snapshot else None


def _create_snapshot(
    db: Session,
    *,
    institution_id: uuid.UUID,
    application_id: uuid.UUID | None,
    score: float,
    status: ComplianceHealth,
    failed_count: int,
    failed_critical_count: int,
    failed_high_count: int,
    missing_count: int,
    trigger: str,
    evaluated_at: datetime,
    previous_status: ComplianceHealth | None,
    application: Application | None = None,
) -> ComplianceSnapshot:
    """Append a snapshot row and raise in-app alerts on a worsening to RED."""
    snapshot = ComplianceSnapshot(
        institution_id=institution_id,
        application_id=application_id,
        score=Decimal(str(score)),
        status=status,
        failed_count=failed_count,
        failed_critical_count=failed_critical_count,
        failed_high_count=failed_high_count,
        missing_count=missing_count,
        trigger=trigger,
        evaluated_at=evaluated_at,
    )
    db.add(snapshot)
    db.flush()

    status_rank = {ComplianceHealth.GREEN: 0, ComplianceHealth.AMBER: 1, ComplianceHealth.RED: 2}
    worsened_to_red = (
        status == ComplianceHealth.RED
        and (previous_status is None or status_rank.get(previous_status, -1) < 2)
    )
    if worsened_to_red:
        _create_red_alerts(
            db,
            institution_id,
            application=application,
            score=score,
            failed_count=failed_count,
            failed_critical_count=failed_critical_count,
            evaluated_at=evaluated_at,
        )
    return snapshot


def _create_red_alerts(
    db: Session,
    institution_id: uuid.UUID,
    *,
    application: Application | None,
    score: float,
    failed_count: int,
    failed_critical_count: int,
    evaluated_at: datetime,
) -> int:
    """Create rule-driven alerts for a compliance RED flip."""
    from app.services.alert_engine import create_compliance_red_alerts

    institution = db.get(Institution, institution_id)
    return create_compliance_red_alerts(
        db,
        institution=institution,
        application=application,
        score=score,
        failed_count=failed_count,
        failed_critical_count=failed_critical_count,
        evaluated_at=evaluated_at,
    )


def evaluate_institution(
    db: Session,
    institution: Institution,
    *,
    evaluated_at: datetime,
    trigger: str = "nightly",
    commit: bool = True,
) -> CompliancePreviewRead | None:
    """Evaluate an institution against its most recent application.

    Institutions without any application have nothing to evaluate and are
    skipped (returns ``None``).
    """
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
        logger.info(
            "Institution %s has no applications; skipped compliance evaluation.",
            institution.aicte_id,
        )
        return None
    return evaluate_application(
        db,
        application,
        evaluated_at=evaluated_at,
        trigger=trigger,
        commit=commit,
    )


def run_nightly_evaluation(
    evaluated_at: datetime | None = None,
    commit: bool = True,
    *,
    trigger: str = "nightly",
    institution_ids: Sequence[uuid.UUID] | None = None,
) -> list[dict[str, str]]:
    """Re-evaluate institutions. Runs in-process (scheduler, API or CLI).

    ``institution_ids`` restricts the run to a viewer's region for the manual
    admin trigger; the nightly job omits it and evaluates every institution.
    """
    from app.db.session import SessionLocal

    evaluated_at = evaluated_at or datetime.now(UTC)
    results: list[dict[str, str]] = []
    with SessionLocal() as db:
        query = select(Institution).order_by(Institution.name)
        if institution_ids is not None:
            if not institution_ids:
                return results
            query = query.where(Institution.id.in_(institution_ids))
        institutions = db.scalars(query).all()
        for institution in institutions:
            preview = evaluate_institution(
                db,
                institution,
                evaluated_at=evaluated_at,
                trigger=trigger,
                commit=commit,
            )
            if preview is not None:
                results.append(
                    {
                        "institution": institution.aicte_id,
                        "name": institution.name,
                        "score": f"{preview.score:.2f}",
                        "status": preview.status,
                        "failed": str(preview.failed_count),
                    }
                )
    logger.info(
        "Compliance evaluation (%s) completed for %d institutions.",
        trigger,
        len(results),
    )
    return results
