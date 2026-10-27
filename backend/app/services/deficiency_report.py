"""The printable Deficiency Report generated from the compliance engine.

The report is available before and after submission. It evaluates the current
version of the application data with the active, admin-editable compliance
rules and returns either a Nil Deficiency banner or the failed/not-assessed
items with the APH clause that supports each one (APH 2.3.3b).

A Nil Deficiency result is decided by mandatory rules only. Illustrative
project thresholds are listed as advisory observations and never block a Nil
Deficiency conclusion.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from io import BytesIO

from sqlalchemy.orm import Session

from app.models.application import Application
from app.schemas.application_sections import ApplicationData
from app.schemas.compliance import PenalActionSuggestionRead
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
    include_illustrative: bool = True,
) -> DeficiencyReportRead:
    """Run the compliance engine and return a printable Deficiency Report.

    ``include_not_assessed`` keeps missing metrics visible so the institution
    knows what to fill in; a reviewer can hide them to show only failed rules.
    ``include_illustrative`` keeps the project-only demo thresholds visible as
    advisory observations.
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
        if rule.illustrative and not include_illustrative:
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
                mandatory=rule.mandatory,
                illustrative=rule.illustrative,
                unit=rule.unit,
                observed_value=rule.observed_value,
                explanation=explanation,
                penal_action_suggestions=[
                    PenalActionSuggestionRead(**suggestion)
                    for suggestion in rule.penal_action_suggestions
                ],
            )
        )

    items.sort(
        key=lambda item: (
            0 if item.mandatory else 1,
            _SEVERITY_ORDER.get(item.severity.value, len(_SEVERITY_ORDER)),
            item.category,
            item.code,
        )
    )
    nil_deficiency = preview.nil_deficiency
    if nil_deficiency:
        banner = "Nil Deficiency"
    else:
        banner = (
            "Not Nil Deficiency: "
            f"{preview.mandatory_failed_count} mandatory failure(s) and "
            f"{preview.mandatory_missing_count} unassessed mandatory item(s)"
        )
    return DeficiencyReportRead(
        application_id=application.id,
        application_no=application.portal_application_no,
        academic_year=application.academic_year,
        generated_at=evaluated_at,
        nil_deficiency=nil_deficiency,
        banner=banner,
        items=items,
        passed_count=preview.passed_count,
        failed_count=preview.failed_count,
        not_assessed_count=preview.not_assessed_count,
        mandatory_failed_count=preview.mandatory_failed_count,
        mandatory_missing_count=preview.mandatory_missing_count,
        illustrative_failed_count=sum(
            1
            for rule in preview.rules
            if rule.illustrative and rule.status != "PASS"
        ),
        score=preview.score,
        status=getattr(preview.status, "value", str(preview.status)),
        include_not_assessed=include_not_assessed,
    )


def render_deficiency_report_pdf(report: DeficiencyReportRead) -> BytesIO:
    """Render the Deficiency Report as a paginated PDF (APH 2.3.3b)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    buffer = BytesIO()
    page_width, page_height = A4
    margin = 18 * mm
    max_width = page_width - 2 * margin
    document = canvas.Canvas(buffer, pagesize=A4)
    y = page_height - margin

    def line(text: str, *, font: str = "Helvetica", size: float = 9) -> None:
        nonlocal y
        for part in _wrap(text, font, size, max_width):
            if y < margin + 12:
                _footer(document, margin)
                document.showPage()
                y = page_height - margin
            document.setFont(font, size)
            document.drawString(margin, y, part)
            y -= size + 4

    def gap(height: float = 4) -> None:
        nonlocal y
        y -= height

    def footer() -> None:
        _footer(document, margin)

    line("AICTE Approval Process Handbook - Deficiency Report", font="Helvetica-Bold", size=14)
    gap(2)
    line(f"Application: {report.application_no or '-'} ({report.academic_year})")
    line(f"Generated: {report.generated_at:%d %b %Y %H:%M} UTC")
    line(f"Score: {report.score} | Status: {report.status}")
    gap(4)
    line(report.banner, font="Helvetica-Bold", size=12)
    if report.nil_deficiency:
        line(
            "Every mandatory requirement assessed for this application passed. "
            "This is a Nil Deficiency result."
        )
    line(
        f"Passed {report.passed_count} | Failed {report.failed_count} | "
        f"Unassessed {report.not_assessed_count}"
    )
    if report.illustrative_failed_count:
        line(
            f"{report.illustrative_failed_count} illustrative project threshold(s) "
            "are listed for information only and are not AICTE norms."
        )
    gap(6)

    if not report.items:
        line("No deficiencies recorded.")
    for index, item in enumerate(report.items, start=1):
        gap(4)
        badge = "ADVISORY - NOT AN AICTE NORM" if item.illustrative else item.severity.value
        line(
            f"{index}. {item.code} - {item.name} [{badge}]",
            font="Helvetica-Bold",
            size=10,
        )
        line(f"Category: {item.category} | Status: {item.status}")
        line(f"Clause: {item.apH_clause}")
        if item.needs_verification:
            line("This clause or threshold is marked for verification.", font="Helvetica-Oblique")
        line(item.message)
        if item.penal_action_suggestions:
            line("Suggested action under APH 7.3 (a hearing is mandatory):", font="Helvetica-Bold")
            for suggestion in item.penal_action_suggestions:
                line(
                    f"- {suggestion.action_label} ({suggestion.violation_code})",
                    font="Helvetica",
                    size=8,
                )

    footer()
    document.save()
    buffer.seek(0)
    return buffer


def _wrap(text: str, font: str, size: float, max_width: float) -> list[str]:
    from reportlab.pdfbase.pdfmetrics import stringWidth

    if not text:
        return [""]
    words = str(text).split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if stringWidth(candidate, font, size) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def _footer(document: object, margin: float) -> None:
    document.setFont("Helvetica-Oblique", 7)  # type: ignore[attr-defined]
    document.drawString(  # type: ignore[attr-defined]
        margin,
        12,
        "Prototype: fictional data - thresholds are configurable and must be "
        "verified against the current APH.",
    )


def suggestions_for_item(
    item: DeficiencyReportItemRead,
) -> Sequence[PenalActionSuggestionRead]:
    """Return the advisory penal actions attached to a report item."""
    return item.penal_action_suggestions
