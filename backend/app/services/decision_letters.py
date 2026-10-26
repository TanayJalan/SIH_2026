"""Decision records, decision letters, PDFs and their statutory clocks.

Every decision is stored as a :class:`~app.models.decision.Decision` row before
any letter is published. Publishing an instrument creates a
:class:`~app.models.decision.DecisionLetter`, renders a PDF, and starts the
clock that belongs to that instrument:

* LoA - Security Deposit: proof and Affidavit 3 within 15 days (APH 2.25f).
* LoD / LoR / Speaking Order - seven-day appeal window (APH 1.11a, 2.24a).

The numbers are the prototype format ``AICTE-DEMO/YYYY/NNNN`` and are allocated
from ``decision_letter_number_seq`` so they never restart.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.clock import SimulatedClock
from app.core.config import get_settings
from app.models.application import Application
from app.models.compliance import ComplianceResult, ComplianceRule
from app.models.deadline import DeadlineRule
from app.models.decision import CouncilRatification, Decision, DecisionLetter
from app.models.enums import (
    DecisionBody,
    DecisionLetterType,
    DecisionOutcome,
    DecisionType,
    SecurityDepositStatus,
)
from app.models.security_deposit import SecurityDeposit
from app.models.user import User
from app.services.audit import AuditService
from app.services.deadlines import compute_due_at, start_timer
from app.services.workflow_errors import WorkflowConfigurationError

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "letters"

_OUTCOME_LABELS = {
    DecisionOutcome.LOA: "Letter of Approval (LoA)",
    DecisionOutcome.EOA: "Extension of Approval (EoA)",
    DecisionOutcome.LOD: "Letter of Deficiency (LoD)",
    DecisionOutcome.LOR: "Letter of Rejection (LoR)",
    DecisionOutcome.RECOMMEND: "Recommendation",
    DecisionOutcome.NOT_RECOMMEND: "Recommendation against approval",
    DecisionOutcome.SEND_BACK: "Send-back",
}

_LETTER_SUBJECTS = {
    DecisionLetterType.LOA: "Letter of Approval (LoA) - prototype",
    DecisionLetterType.EOA: "Extension of Approval (EoA) - prototype",
    DecisionLetterType.LOD: "Letter of Deficiency (LoD) - prototype",
    DecisionLetterType.LOR: "Letter of Rejection with Speaking Order - prototype",
    DecisionLetterType.SPEAKING_ORDER: "Speaking Order - prototype",
    DecisionLetterType.DEFICIENCY_REPORT: "Deficiency Report - prototype",
    DecisionLetterType.SHOW_CAUSE: "Show Cause Notice - prototype",
}

# Instruments that open the seven-day appeal window (APH 1.11a, 2.24a).
_APPEALABLE = frozenset(
    {
        DecisionLetterType.LOD,
        DecisionLetterType.LOR,
        DecisionLetterType.SPEAKING_ORDER,
    }
)


@dataclass(slots=True)
class LetterContext:
    """The data rendered into a decision letter."""

    letter_number: str
    issued_on: date
    letter_type: DecisionLetterType
    subject: str
    decision_text: str
    reasons_text: str
    next_steps: list[str] = field(default_factory=list)
    failed_rules: list[dict[str, str]] = field(default_factory=list)
    speaking_order: str | None = None
    appeal_text: str | None = None
    issuing_body: str = "Executive Committee"
    apH_clause: str = "APH 1.10"


def next_letter_number(db: Session, academic_year: str) -> str:
    """Allocate the next ``AICTE-DEMO/YYYY/NNNN`` letter number."""
    year = academic_year.split("-", maxsplit=1)[0]
    statement = text(
        """
        INSERT INTO decision_letter_number_seq
            (academic_year, last_value, created_at, updated_at)
        VALUES (:year, 1, now(), now())
        ON CONFLICT (academic_year)
        DO UPDATE SET
            last_value = decision_letter_number_seq.last_value + 1,
            updated_at = now()
        RETURNING last_value
        """
    )
    value = db.execute(statement, {"year": academic_year}).scalar_one()
    return f"AICTE-DEMO/{year}/{int(value):04d}"


def record_decision(
    db: Session,
    application: Application,
    *,
    body: DecisionBody,
    outcome: DecisionOutcome,
    actor: User,
    clock: SimulatedClock,
    quorum_met: bool = False,
    notes: str = "",
    committee_id: uuid.UUID | None = None,
    apH_clause: str,
    decided_on: date | None = None,
) -> Decision:
    """Persist one committee or Council decision without committing."""
    decision = Decision(
        application_id=application.id,
        body=body,
        outcome=outcome,
        decided_on=decided_on or clock.now().date(),
        committee_id=committee_id,
        quorum_met=quorum_met,
        notes=notes,
        apH_clause=apH_clause,
    )
    db.add(decision)
    db.flush()
    return decision


def latest_decision(db: Session, application_id: uuid.UUID, body: DecisionBody) -> Decision | None:
    """Return the most recent decision of one body for an application."""
    return db.scalar(
        select(Decision)
        .where(Decision.application_id == application_id, Decision.body == body)
        .order_by(Decision.created_at.desc())
        .limit(1)
    )


def record_ratification(
    db: Session,
    decision: Decision,
    *,
    actor: User,
    ratified_on: date,
    reference: str | None = None,
) -> CouncilRatification:
    """Record the Council's ratification of an EC decision (APH 2.25a)."""
    if not decision.quorum_met:
        raise WorkflowConfigurationError(
            "An Executive Committee decision without a met quorum cannot be ratified."
        )
    ratification = CouncilRatification(
        decision_id=decision.id,
        ratified_on=ratified_on,
        ratified_by=actor.id,
        ec_recommendation_ref=reference,
    )
    db.add(ratification)
    db.flush()
    return ratification


def failed_rules(db: Session, application_id: uuid.UUID, limit: int = 20) -> list[dict[str, str]]:
    """Return the failed compliance rules quoted in a letter."""
    rows = db.execute(
        select(ComplianceResult, ComplianceRule)
        .join(ComplianceRule, ComplianceRule.id == ComplianceResult.rule_id)
        .where(
            ComplianceResult.application_id == application_id,
            ComplianceResult.status == "FAIL",
        )
        .order_by(ComplianceRule.code.asc())
        .limit(limit)
    ).all()
    return [
        {
            "code": rule.code,
            "name": rule.name,
            "apH_clause": rule.apH_clause,
            "message": result.message or rule.description,
        }
        for result, rule in rows
    ]


def _institution_address(application: Application) -> str:
    data = application.data if isinstance(application.data, dict) else {}
    profile = data.get("institution_profile") or {}
    parts = [
        profile.get("address_line1"),
        profile.get("address_line2"),
        profile.get("city"),
        profile.get("state"),
        profile.get("pin_code"),
    ]
    address = ", ".join(str(part) for part in parts if part)
    return address or application.institution.state


def _decision_text(letter_type: DecisionLetterType, decision: Decision | None) -> str:
    outcome = decision.outcome if decision is not None else None
    if letter_type == DecisionLetterType.LOA:
        return (
            "The Council has approved the application. The Letter of Approval is issued "
            "subject to the Security Deposit and Affidavit 3 conditions in paragraph 5 "
            "(APH 1.10a, 2.25f)."
        )
    if letter_type == DecisionLetterType.EOA:
        return (
            "The Council has extended the approval for the academic year covered by this "
            "letter, with the Approved Intake recorded in the Executive Committee list "
            "(APH 2.25)."
        )
    if letter_type == DecisionLetterType.LOD:
        return (
            "The Executive Committee has recorded deficiencies that must be closed before "
            "the application can proceed. This is a Letter of Deficiency, not a rejection "
            "(APH 2.23.3)."
        )
    if letter_type in {DecisionLetterType.LOR, DecisionLetterType.SPEAKING_ORDER}:
        label = _OUTCOME_LABELS.get(outcome, "rejection") if outcome else "rejection"
        return (
            f"The Executive Committee has recorded a {label}. The reasons are set out in "
            "the Speaking Order below (APH 1.10, 2.24a)."
        )
    return "This instrument records the decision of the competent authority."


def _appeal_text(
    letter_type: DecisionLetterType,
    deadline: datetime | None,
) -> str | None:
    if letter_type not in _APPEALABLE:
        return None
    when = deadline.date().isoformat() if deadline is not None else "the configured deadline"
    return (
        "The institution may file one appeal with the Standing Appellate Committee "
        f"within seven days of this letter, that is on or before {when} (APH 1.11a). "
        "A late appeal cannot be accepted."
    )


def _next_steps(letter_type: DecisionLetterType, deposit_days: int) -> list[str]:
    if letter_type == DecisionLetterType.LOA:
        return [
            f"Pay the Security Deposit and file Affidavit 3 within {deposit_days} days "
            "of this letter (APH 2.25f).",
            "A 10% penalty applies after that date up to 31 May and 20% up to 31 July; "
            "after that the approval may be withdrawn (APH 2.25f).",
            "The LoA is valid for two academic years; the following year needs an "
            "Extension of Approval (APH 1.10b).",
        ]
    if letter_type == DecisionLetterType.EOA:
        return [
            "Retain the Approved Intake and the compliance evidence for inspection.",
            "The next academic year requires a fresh Extension of Approval (APH 2.25).",
        ]
    if letter_type == DecisionLetterType.LOD:
        return [
            "Respond to every deficiency through the portal before the communicated date.",
            "The Re-Scrutiny Committee verifies only the deficiencies that were listed "
            "(APH 1.8).",
        ]
    return [
        "The rejection may be appealed once to the Standing Appellate Committee "
        "(APH 1.11a).",
        "If no appeal is filed, the decision becomes final after the appeal window.",
    ]


def _render_pdf(context: dict[str, Any], destination: Path) -> None:
    """Render the letter template to a PDF with reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.pdfgen import canvas

    environment = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(enabled_extensions=("html", "xml")),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = environment.get_template("decision_letter.txt.j2")
    rendered = template.render(**context)

    destination.parent.mkdir(parents=True, exist_ok=True)
    page_width, page_height = A4
    margin = 48
    line_height = 13
    font = "Helvetica"
    size = 9
    max_width = page_width - 2 * margin

    def wrap(line: str) -> list[str]:
        if not line:
            return [""]
        words = line.split(" ")
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
        return lines

    document = canvas.Canvas(str(destination), pagesize=A4)
    y = page_height - margin
    for raw_line in rendered.splitlines():
        for line in wrap(raw_line):
            if y < margin:
                document.setFont("Helvetica-Oblique", 7)
                document.drawString(
                    margin,
                    24,
                    "Prototype: fictional data - not a real AICTE communication",
                )
                document.showPage()
                document.setFont(font, size)
                y = page_height - margin
            document.setFont(font, size)
            document.drawString(margin, y, line)
            y -= line_height
    document.setFont("Helvetica-Oblique", 7)
    document.drawString(margin, 24, "Prototype: fictional data - not a real AICTE communication")
    document.save()


def issue_letter(
    db: Session,
    application: Application,
    *,
    letter_type: DecisionLetterType,
    actor: User,
    clock: SimulatedClock,
    audit: AuditService,
    decision: Decision | None = None,
    apH_clause: str,
    speaking_order: str | None = None,
    observations: str | None = None,
    settings: Any | None = None,
    request: Any | None = None,
) -> DecisionLetter:
    """Render a PDF, publish a letter and start its statutory clock."""
    settings = settings or get_settings()
    now = clock.now()
    issued_on = now.date()
    letter_number = next_letter_number(db, application.academic_year)

    # The appeal clock is configuration, not a constant (APH 1.11a).
    appeal_rule = db.scalar(select(DeadlineRule).where(DeadlineRule.code == "APPEAL_WINDOW"))
    deposit_rule = db.scalar(select(DeadlineRule).where(DeadlineRule.code == "SECURITY_DEPOSIT"))
    if appeal_rule is None or deposit_rule is None:
        raise WorkflowConfigurationError(
            "APPEAL_WINDOW and SECURITY_DEPOSIT deadline rules must be configured."
        )

    start = now
    appeal_deadline: datetime | None = None
    if letter_type in _APPEALABLE:
        appeal_deadline = compute_due_at(start, appeal_rule.duration_days)

    context = LetterContext(
        letter_number=letter_number,
        issued_on=issued_on,
        letter_type=letter_type,
        subject=_LETTER_SUBJECTS[letter_type],
        decision_text=_decision_text(letter_type, decision),
        reasons_text=(
            observations
            or (decision.notes if decision is not None and decision.notes else "")
            or "The reasons are recorded in the Executive Committee minutes."
        ),
        next_steps=_next_steps(letter_type, deposit_rule.duration_days),
        failed_rules=failed_rules(db, application.id),
        speaking_order=speaking_order,
        appeal_text=_appeal_text(letter_type, appeal_deadline),
        issuing_body=(
            "Council"
            if decision is not None and decision.body == DecisionBody.COUNCIL
            else "Executive Committee"
        ),
        apH_clause=apH_clause,
    )

    render_context = {
        "letter_number": letter_number,
        "issued_on": issued_on.isoformat(),
        "academic_year": application.academic_year,
        "institution_name": application.institution.name,
        "institution_address": _institution_address(application),
        "subject": context.subject,
        "application_reference": application.portal_application_no or str(application.id),
        "application_type_label": application.application_type.replace("_", " ").title(),
        "decision_text": context.decision_text,
        "reasons_text": context.reasons_text,
        "speaking_order": context.speaking_order,
        "failed_rules": context.failed_rules,
        "next_steps": context.next_steps,
        "appeal_text": context.appeal_text,
        "issued_by": actor.name,
        "issuing_body": context.issuing_body,
        "apH_clause": apH_clause,
    }

    storage_root = Path(settings.storage_dir)
    relative = Path("letters") / f"{letter_number.replace('/', '_')}.pdf"
    _render_pdf(render_context, storage_root / relative)

    letter = DecisionLetter(
        application_id=application.id,
        decision_id=decision.id if decision is not None else None,
        letter_type=letter_type,
        letter_number=letter_number,
        issued_on=issued_on,
        published_at=now,
        appeal_clock_start=start if appeal_deadline is not None else None,
        appeal_deadline=appeal_deadline,
        body_text=(
            f"Subject: {context.subject}\n\n{context.decision_text}\n\n"
            f"{context.reasons_text}"
        ),
        pdf_path=str(relative),
    )
    db.add(letter)
    db.flush()

    application.decision_uploaded_at = now
    if decision is not None and decision.outcome in {
        DecisionOutcome.LOA,
        DecisionOutcome.EOA,
        DecisionOutcome.LOD,
        DecisionOutcome.LOR,
    }:
        application.decision_type = DecisionType(decision.outcome.value)

    if letter_type == DecisionLetterType.LOA:
        application.loa_valid_until = date(issued_on.year + 2, issued_on.month, issued_on.day)
        application.security_deposit_due_on = issued_on + timedelta(
            days=deposit_rule.duration_days
        )
        _create_security_deposits(db, application, issued_on=issued_on)
        start_timer(
            db,
            application,
            deposit_rule,
            started_at=start,
            audit=audit,
        )
    if appeal_deadline is not None:
        application.appeal_deadline = appeal_deadline
        start_timer(
            db,
            application,
            appeal_rule,
            started_at=start,
            audit=audit,
        )

    audit.log(
        actor,
        f"letter.{letter_type.value.lower()}.issue",
        "DecisionLetter",
        letter.id,
        after={
            "letter_number": letter_number,
            "application_id": str(application.id),
            "issued_on": issued_on.isoformat(),
            "appeal_deadline": appeal_deadline.isoformat() if appeal_deadline else None,
            "pdf_path": letter.pdf_path,
        },
        request=request,
    )
    return letter


def _create_security_deposits(
    db: Session,
    application: Application,
    *,
    issued_on: date,
) -> list[SecurityDeposit]:
    """Create one pending Security Deposit row per programme (Table 1.4)."""
    from app.services.fees import FeeService

    clock = SimulatedClock()
    service = FeeService(db, AuditService(db), clock)
    quote = service.security_deposit_quote(application, as_of=issued_on)
    deposits: list[SecurityDeposit] = []
    for line in quote.lines:
        deposit = SecurityDeposit(
            institution_id=application.institution_id,
            application_id=application.id,
            programme_family=line.programme_family,
            level=line.level,
            required_paise=line.deposit_paise,
            doubled_for_leased=line.leased,
            created_on=issued_on,
            maturity_on=date(issued_on.year + 2, issued_on.month, issued_on.day),
            status=SecurityDepositStatus.PENDING,
            apH_clause=line.apH_clause,
            needs_verification=line.needs_verification,
        )
        db.add(deposit)
        deposits.append(deposit)
    db.flush()
    return deposits


def letter_path(letter: DecisionLetter, settings: Any | None = None) -> Path:
    """Return the absolute PDF path for a letter."""
    settings = settings or get_settings()
    if letter.pdf_path is None:
        raise WorkflowConfigurationError("This letter has no rendered PDF.")
    return Path(settings.storage_dir) / letter.pdf_path


def utcnow() -> datetime:
    """Return the current UTC instant (kept here for test monkeypatching)."""
    return datetime.now(UTC)
