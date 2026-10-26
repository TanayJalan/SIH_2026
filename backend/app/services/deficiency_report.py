"""The printable Deficiency Report generated from the compliance engine.

The report is available before and after submission. It evaluates the current
version of the application data with the active, admin-editable compliance
rules and returns either a Nil Deficiency banner or the failed/not-assessed
items with the APH clause that supports each one (APH 2.3.3b).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.application import Application
from app.schemas.application_sections import ApplicationData
from app.schemas.fees import DeficiencyReportItemRead, DeficiencyReportRead
from app.services.compliance import evaluate_compliance

_SEVERITY_ORDER = {
    "CRITICAL": 0,
    "HIGH": 1,
    "MEDIUM": 2,
    "LOW": 3,
}


def build_deficiency_report(
    db: Session,
    application: Application,
    *,
    evaluated_at: datetime,
    include_not_assessed: bool = True,
) -> DeficiencyReportRead:
    """Run the compliance engine and return a printable Deficiency Report.

    ``include_not_assessed`` keeps missing metrics visible so the institution
    knows what to fill in; a reviewer can hide them to show only failed rules.
    """
    raw_data = application.data if isinstance(application.data, dict) else {}
    data = ApplicationData.model_validate(raw_data)
    preview = evaluate_compliance(db, application, data, evaluated_at=evaluated_at)

    items: list[DeficiencyReportItemRead] = []
    for rule in preview.rules:
        if rule.status == "PASS":
            continue
        if rule.status == "NOT_ASSESSED" and not include_not_assessed:
            continue
        explanation = rule.explanation or {}
        items.append(
            DeficiencyReportItemRead(
                code=rule.code,
                name=rule.name,
                category=rule.category,
                severity=rule.severity,
                status=rule.status,
                message=rule.message,
                apH_clause=str(explanation.get("apH_clause") or "APH 2.3.3b"),
                needs_verification=bool(explanation.get("needs_verification", False)),
                observed_value=rule.observed_value,
                explanation=explanation,
            )
        )

    items.sort(
        key=lambda item: (
            _SEVERITY_ORDER.get(item.severity.value, len(_SEVERITY_ORDER)),
            item.category,
            item.code,
        )
    )
    nil_deficiency = not items
    return DeficiencyReportRead(
        application_id=application.id,
        application_no=application.portal_application_no,
        academic_year=application.academic_year,
        generated_at=evaluated_at,
        nil_deficiency=nil_deficiency,
        banner=(
            "Nil Deficiency"
            if nil_deficiency
            else f"{len(items)} deficiency item(s) require attention"
        ),
        items=items,
        passed_count=preview.passed_count,
        failed_count=preview.failed_count,
        not_assessed_count=preview.not_assessed_count,
        score=preview.score,
        status=getattr(preview.status, "value", str(preview.status)),
        include_not_assessed=include_not_assessed,
    )
