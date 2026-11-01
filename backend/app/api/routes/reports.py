"""Role-specific report and dashboard aggregate endpoints.

Every endpoint returns SQL-computed aggregates (never Python loops) narrowed by
the global filters: academic year, region, state, application type and track.
All monetary values are integer paise; every metric carries its APH clause.
"""

from __future__ import annotations

import uuid
from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api.dependencies import ClockDep, DbSession, require_roles
from app.models import Role
from app.schemas.reports import (
    AppealOutcome,
    ApplicationByTrackState,
    ApplicationReport,
    ApprovalVsRejection,
    AverageDaysPerStage,
    ComplaintStatusCount,
    DeficiencyCategory,
    Escalation,
    ExpiringDocument,
    FeePosition,
    FailingRule,
    FacultyRatioDeficit,
    InstitutionDashboard,
    InstitutionCompliance,
    LoaExpiring,
    MandatoryDisclosure,
    OpenDeficiency,
    PenalActionByType,
    QueueEntry,
    RegionalDashboard,
    ReportFilters,
    RegulationBureauDashboard,
    ReportCompliance,
    ReportDecision,
    ReportFee,
    ReportTimelineEvent,
    SlaBreach,
    SecurityDepositPending,
    UpcomingDeadline,
    ViolationCode,
)
from app.services.reports import (
    application_report_data,
    institution_dashboard,
    regional_dashboard,
    regulation_bureau_dashboard,
)

router = APIRouter(prefix="/reports", tags=["reports"])

RegulationBureauUser = Annotated[
    Role,
    Depends(
        require_roles(
            Role.REGULATION_BUREAU_OFFICER,
            Role.SCRUTINY_COMMITTEE_MEMBER,
        )
    ),
]

RegionalUser = Annotated[
    Role,
    Depends(
        require_roles(Role.REGIONAL_OFFICER, Role.SUPER_ADMIN)
    ),
]

InstitutionUser = Annotated[
    Role,
    Depends(require_roles(Role.INSTITUTION_ADMIN)),
]


@router.get(
    "/regulation-bureau",
    response_model=RegulationBureauDashboard,
    summary="Regulation Bureau / Scrutiny work queue dashboard",
)
def regulation_bureau_report(
    filters: Annotated[ReportFilters, Depends()],
    current_user: RegulationBureauUser,
    db: DbSession,
) -> RegulationBureauDashboard:
    """Return the Regulation Bureau / Scrutiny dashboard.

    Covers APH 1.8 (scrutiny), APH 1.9 (EVC/inspection), APH 1.10
    (Regulation Bureau observations).
    """
    return regulation_bureau_dashboard(db, filters)


@router.get(
    "/regional",
    response_model=RegionalDashboard,
    summary="Regional Officer / SUPER_ADMIN aggregate dashboard",
)
def regional_report(
    filters: Annotated[ReportFilters, Depends()],
    current_user: RegionalUser,
    db: DbSession,
) -> RegionalDashboard:
    """Return the Regional Officer / SUPER_ADMIN dashboard.

    Covers APH 1.8-1.11 (workflow funnel), APH 2.23-2.25 (decisions, appeals,
    deposits), APH 6.14 (faculty ratio), APH 7.3-7.4 (penal actions),
    APH 7.10 (complaints), APH 7.13 (compliance monitoring).
    """
    return regional_dashboard(db, filters)


@router.get(
    "/institution",
    response_model=InstitutionDashboard,
    summary="Institution Admin progress tracker dashboard",
)
def institution_report(
    filters: Annotated[ReportFilters, Depends()],
    current_user: InstitutionUser,
    db: DbSession,
) -> InstitutionDashboard:
    """Return the Institution Admin dashboard.

    Covers APH 1.4 (application), APH 2.3.3b (deficiencies), APH 4 (fees),
    APH 6.17h (documents), APH 7.4 (violation/fix guidance).
    """
    if current_user.institution_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No institution is linked to this account.",
        )
    return institution_dashboard(db, current_user.institution_id, filters)


# ---------------------------------------------------------------------------
# Per-application PDF report
# ---------------------------------------------------------------------------


class _ReportCanvas:
    """Minimal reportlab canvas wrapper for the application summary PDF."""

    def __init__(self, buffer: BytesIO):
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase.pdfmetrics import stringWidth
        from reportlab.pdfgen import canvas

        self._buffer = buffer
        self._canvas = canvas.Canvas(buffer, pagesize=A4)
        self._width, self._height = A4
        self._margin = 48
        self._y = self._height - self._margin
        self._font = "Helvetica"
        self._size = 9
        self._line_height = 13
        self._max_width = self._width - 2 * self._margin
        self._string_width = stringWidth

    def _wrap(self, line: str) -> list[str]:
        if not line:
            return [""]
        words = str(line).split(" ")
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if self._string_width(candidate, self._font, self._size) <= self._max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines or [""]

    def _new_page(self):
        self._canvas.setFont("Helvetica-Oblique", 7)
        self._canvas.drawString(
            self._margin, 24, "Prototype: fictional data - verify against the current APH."
        )
        self._canvas.showPage()
        self._canvas.setFont(self._font, self._size)
        self._y = self._height - self._margin

    def line(self, text: str, *, bold: bool = False, size: int | None = None):
        font = "Helvetica-Bold" if bold else self._font
        size = size or self._size
        for part in self._wrap(text):
            if self._y < self._margin + 12:
                self._new_page()
            self._canvas.setFont(font, size)
            self._canvas.drawString(self._margin, self._y, part)
            self._y -= self._line_height

    def heading(self, text: str):
        self.line(text, bold=True, size=12)
        self._y -= 4

    def save(self):
        self._canvas.setFont("Helvetica-Oblique", 7)
        self._canvas.drawString(
            self._margin, 24, "Prototype: fictional data - verify against the current APH."
        )
        self._canvas.save()
        self._buffer.seek(0)


def _build_pdf(report: ApplicationReport) -> BytesIO:
    """Render the application summary report to a PDF buffer."""
    buffer = BytesIO()
    pdf = _ReportCanvas(buffer)

    app = report.application
    pdf.line("AICTE Approval Process Handbook - Application Summary Report", bold=True, size=14)
    pdf._y -= 2
    pdf.line(f"Application: {app.portal_application_no or app.application_id}  ({app.academic_year})")
    pdf.line(f"Institution: {app.institution_name}")
    pdf.line(f"Track: {app.track}  |  Type: {app.application_type}")
    pdf.line(f"Status: {app.status}  |  Stage: {app.current_stage}")
    pdf.line(f"Submitted: {app.submitted_at:%d %b %Y %H:%M UTC}" if app.submitted_at else "Submitted: —")
    pdf.line(f"Decision: {app.decision_type or '—'}")
    pdf.line(f"Compliance score: {app.compliance_score if app.compliance_score is not None else '—'}")
    pdf.line(f"Governing clause: {app.apH_clause}")
    pdf._y -= 6

    # Timeline
    pdf.heading("Workflow Timeline")
    if report.timeline:
        for event in report.timeline:
            pdf.line(
                f"{event.created_at:%d %b %Y %H:%M}  {event.action or '—'}  "
                f"{(event.from_status or '—')} -> {event.to_status}  "
                f"by {event.actor_name or 'system'}  [{event.apH_clause}]",
                size=8,
            )
    else:
        pdf.line("No workflow events recorded.", size=8)
    pdf._y -= 6

    # Decisions
    pdf.heading("Decisions")
    if report.decisions:
        for d in report.decisions:
            pdf.line(
                f"{d.decided_on:%d %b %Y}  {d.body or '—'}  {d.outcome or '—'}  "
                f"quorum={'met' if d.quorum_met else 'not met'}  [{d.apH_clause}]",
                size=8,
            )
    else:
        pdf.line("No decisions recorded.", size=8)
    pdf._y -= 6

    # Fees
    pdf.heading("Fees (integer paise)")
    if report.fees:
        for f in report.fees:
            pdf.line(
                f"{f.kind}  ₹{f.amount_paise / 100:,.2f}  "
                f"paid {f.paid_at:%d %b %Y %H:%M}" if f.paid_at else f"{f.kind}  ₹{f.amount_paise / 100:,.2f}  unpaid",
                size=8,
            )
    else:
        pdf.line("No fee transactions recorded.", size=8)
    pdf._y -= 6

    # Compliance
    pdf.heading("Compliance Results")
    if report.compliance:
        for c in report.compliance:
            pdf.line(
                f"{c.code}  {c.name}  {c.status}  [{c.apH_clause}]  {c.message or ''}",
                size=8,
            )
    else:
        pdf.line("No compliance results recorded.", size=8)
    pdf._y -= 6

    # Deficiencies
    pdf.heading("Deficiencies")
    if report.deficiencies:
        for d in report.deficiencies:
            pdf.line(
                f"{d.category}  {d.description}  {d.status.value}  due {d.due_date:%d %b %Y}  [{d.apH_clause}]",
                size=8,
            )
    else:
        pdf.line("No deficiencies recorded.", size=8)

    pdf.save()
    return buffer


@router.get(
    "/application/{application_id}.pdf",
    responses={
        status.HTTP_200_OK: {"content": {"application/pdf": {}}},
        status.HTTP_403_FORBIDDEN: {"model": dict},
        status.HTTP_404_NOT_FOUND: {"model": dict},
    },
    summary="Download the per-application summary report as PDF",
)
def application_report_pdf(
    application_id: uuid.UUID,
    current_user: Annotated[Role, Depends(require_roles(Role.INSTITUTION_ADMIN, Role.REGIONAL_OFFICER, Role.SUPER_ADMIN, Role.REGULATION_BUREAU_OFFICER, Role.SCRUTINY_COMMITTEE_MEMBER))],
    db: DbSession,
    clock: ClockDep,
) -> StreamingResponse:
    """Return a PDF summary of one application: timeline, clauses, fees,
    compliance results, deficiencies and decision (APH 1.4, 2.3.3b).

    The UI (M11) renders this endpoint; this backend only builds the PDF.
    """
    report = application_report_data(db, application_id)
    buffer = _build_pdf(report)
    filename = f"application-report-{report.application.portal_application_no or report.application.application_id}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
