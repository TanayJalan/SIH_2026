"""Idempotent development seed data.

Only clearly fictional data is created: demo institutions, one account per APH
role, five pre-staged applications, and reference configuration (application
types, workflow definitions, compliance rules, fees, document checklists, SLA
and alert rules) loaded from ``backend/seeds/aph/*.json``.

Re-running the seed never duplicates rows: every loader is an upsert keyed on
the natural key (``aicte_id``, ``code``, ``type``, ``stage``, ``key``...).

Demo-only values (SLA durations, security-deposit terms, cut-off dates) are
flagged with ``needs_verification=True`` so they cannot be mistaken for real
AICTE norms. See ``docs/OPEN_QUESTIONS.md``.

Run from ``backend/`` with ``python -m app.seed``.
"""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import (
    AcademicCalendarEvent,
    Alert,
    AlertChannel,
    AlertRule,
    AlertTrigger,
    AlertTriggerCatalogue,
    Application,
    ApplicationCategory,
    ApplicationStatus,
    ApplicationTrack,
    ApplicationTypeRoute,
    CompetentAuthority,
    Complaint,
    ComplianceConfig,
    ComplianceRule,
    Decision,
    DecisionBody,
    DecisionLetter,
    DecisionLetterType,
    DecisionOutcome,
    DecisionType,
    Deficiency,
    DeficiencyStatus,
    Document,
    DocumentVerificationStatus,
    ExpertPool,
    FeeSchedule,
    Institution,
    LandOwnership,
    NomenclatureCourse,
    PublicNotice,
    RequiredDocument,
    Role,
    SecurityDeposit,
    SecurityDepositSchedule,
    SecurityDepositStatus,
    Severity,
    SLAConfig,
    User,
    WorkflowDefinition,
    WorkflowStage,
    WorkflowState,
    WorkflowTransition,
)
from app.models.enums import ComplaintStatus, DocumentRejectionReason, InstitutionRegion
from app.services.audit import AuditService

logger = logging.getLogger("app.seed")

SEED_DIR = Path(__file__).resolve().parent.parent / "seeds" / "aph"
ACADEMIC_YEAR = "2026-27"

# Illustrative processing limits. The handbook does not publish these; they are
# admin-editable settings seeded with clearly labelled demo values.
_SLA_CONFIGS: tuple[tuple[WorkflowStage, int, int, Role], ...] = (
    (WorkflowStage.APPLICATION, 3, 1, Role.REGIONAL_OFFICER),
    (WorkflowStage.DOCUMENT_VERIFICATION, 7, 2, Role.REGIONAL_OFFICER),
    (WorkflowStage.SCRUTINY, 15, 5, Role.REGIONAL_OFFICER),
    (WorkflowStage.DEFICIENCY, 15, 5, Role.REGIONAL_OFFICER),
    (WorkflowStage.INSPECTION, 30, 7, Role.REGIONAL_OFFICER),
    (WorkflowStage.COMMITTEE_REVIEW, 15, 5, Role.EXECUTIVE_COMMITTEE_MEMBER),
    (WorkflowStage.DECISION, 30, 7, Role.SUPER_ADMIN),
)

# Baseline alert rules. Each row is configuration, not logic: the engine reads
# the trigger through ``alert_trigger_catalogue``.
_ALERT_RULES: tuple[dict[str, Any], ...] = (
    {
        "code": "DEADLINE-7",
        "trigger": AlertTrigger.DEADLINE_APPROACHING,
        "days_before": 7,
        "severity": Severity.LOW,
        "channels": [AlertChannel.IN_APP, AlertChannel.EMAIL],
        "escalation_role": Role.REGIONAL_OFFICER,
        "template": (
            "The {stage} stage for {institution} (application "
            "{application_reference}) is due on {due_date}: {days_remaining} day(s) left."
        ),
    },
    {
        "code": "DEADLINE-3",
        "trigger": AlertTrigger.DEADLINE_APPROACHING,
        "days_before": 3,
        "severity": Severity.MEDIUM,
        "channels": [AlertChannel.IN_APP, AlertChannel.EMAIL],
        "escalation_role": Role.REGIONAL_OFFICER,
        "template": (
            "The {stage} stage for {institution} (application "
            "{application_reference}) closes on {due_date}."
        ),
    },
    {
        "code": "SLA-BREACHED",
        "trigger": AlertTrigger.SLA_BREACHED,
        "days_before": 0,
        "severity": Severity.HIGH,
        "channels": [AlertChannel.IN_APP, AlertChannel.EMAIL],
        "escalation_role": Role.REGIONAL_OFFICER,
        "template": (
            "The {stage} stage for {institution} (application "
            "{application_reference}) is past its {due_date} deadline."
        ),
    },
    {
        "code": "DEFICIENCY-DUE-3",
        "trigger": AlertTrigger.DEFICIENCY_DUE,
        "days_before": 3,
        "severity": Severity.MEDIUM,
        "channels": [AlertChannel.IN_APP, AlertChannel.EMAIL],
        "escalation_role": Role.REGIONAL_OFFICER,
        "template": (
            "Deficiency response for {institution} (application "
            "{application_reference}) is due on {due_date}: {deficiency}"
        ),
    },
    {
        "code": "DEFICIENCY-OVERDUE",
        "trigger": AlertTrigger.DEFICIENCY_OVERDUE,
        "days_before": 0,
        "severity": Severity.HIGH,
        "channels": [AlertChannel.IN_APP, AlertChannel.EMAIL],
        "escalation_role": Role.REGIONAL_OFFICER,
        "template": (
            "Deficiency response for {institution} (application "
            "{application_reference}) was due on {due_date}."
        ),
    },
    {
        "code": "DOCUMENT-EXPIRING-30",
        "trigger": AlertTrigger.DOCUMENT_EXPIRING,
        "days_before": 30,
        "severity": Severity.MEDIUM,
        "channels": [AlertChannel.IN_APP, AlertChannel.EMAIL],
        "escalation_role": Role.REGIONAL_OFFICER,
        "template": (
            "Document {document} for {institution} (application "
            "{application_reference}) expires on {due_date}."
        ),
    },
    {
        "code": "COMPLIANCE-RED",
        "trigger": AlertTrigger.COMPLIANCE_RED,
        "days_before": 0,
        "severity": Severity.CRITICAL,
        "channels": [AlertChannel.IN_APP, AlertChannel.EMAIL],
        "escalation_role": Role.REGIONAL_OFFICER,
        "template": (
            "{institution} is in the RED compliance band (application {application_reference})."
        ),
    },
    {
        "code": "STATUS-CHANGED",
        "trigger": AlertTrigger.APPLICATION_STATUS_CHANGED,
        "days_before": 0,
        "severity": Severity.LOW,
        "channels": [AlertChannel.IN_APP],
        "escalation_role": Role.INSTITUTION_ADMIN,
        "template": ("Application {application_reference} for {institution} moved to {status}."),
    },
    {
        "code": "INSPECTION-SCHEDULED",
        "trigger": AlertTrigger.INSPECTION_SCHEDULED,
        "days_before": 7,
        "severity": Severity.LOW,
        "channels": [AlertChannel.IN_APP, AlertChannel.EMAIL],
        "escalation_role": Role.EVC_MEMBER,
        "template": (
            "Expert Visit Committee for {institution} (application "
            "{application_reference}) is scheduled on {inspection_date}."
        ),
    },
    {
        "code": "APPEAL-WINDOW-7",
        "trigger": AlertTrigger.APPEAL_WINDOW_CLOSING,
        "days_before": 7,
        "severity": Severity.MEDIUM,
        "channels": [AlertChannel.IN_APP, AlertChannel.EMAIL],
        "escalation_role": Role.INSTITUTION_ADMIN,
        "template": (
            "The appeal window for {institution} (application "
            "{application_reference}) closes on {due_date}."
        ),
    },
    {
        "code": "APPEAL-EXPIRED",
        "trigger": AlertTrigger.APPEAL_EXPIRED,
        "days_before": 0,
        "severity": Severity.HIGH,
        "channels": [AlertChannel.IN_APP, AlertChannel.EMAIL],
        "escalation_role": Role.REGIONAL_OFFICER,
        "template": (
            "The appeal window for {institution} (application "
            "{application_reference}) ended on {due_date}."
        ),
    },
    {
        "code": "DEPOSIT-DUE-5",
        "trigger": AlertTrigger.DEPOSIT_DUE,
        "days_before": 5,
        "severity": Severity.MEDIUM,
        "channels": [AlertChannel.IN_APP, AlertChannel.EMAIL],
        "escalation_role": Role.INSTITUTION_ADMIN,
        "template": (
            "Security Deposit and Affidavit 3 for {institution} (application "
            "{application_reference}) are due on {due_date}."
        ),
    },
    {
        "code": "DEPOSIT-OVERDUE",
        "trigger": AlertTrigger.DEPOSIT_OVERDUE,
        "days_before": 0,
        "severity": Severity.HIGH,
        "channels": [AlertChannel.IN_APP, AlertChannel.EMAIL],
        "escalation_role": Role.REGIONAL_OFFICER,
        "template": (
            "Security Deposit for {institution} (application "
            "{application_reference}) was due on {due_date}."
        ),
    },
    {
        "code": "DEPOSIT-PENALTY",
        "trigger": AlertTrigger.DEPOSIT_PENALTY,
        "days_before": 0,
        "severity": Severity.HIGH,
        "channels": [AlertChannel.IN_APP, AlertChannel.EMAIL],
        "escalation_role": Role.REGIONAL_OFFICER,
        "template": (
            "A deposit penalty applies to {institution} (application {application_reference})."
        ),
    },
    {
        "code": "LOA-EXPIRED",
        "trigger": AlertTrigger.LOA_EXPIRED,
        "days_before": 0,
        "severity": Severity.CRITICAL,
        "channels": [AlertChannel.IN_APP, AlertChannel.EMAIL],
        "escalation_role": Role.INSTITUTION_ADMIN,
        "template": (
            "The Letter of Approval for {institution} expired on {due_date}; "
            "a fresh EoA application is required."
        ),
    },
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_json(name: str) -> Any:
    """Read one generated APH seed file."""
    return json.loads((SEED_DIR / name).read_text(encoding="utf-8"))


def _today() -> date:
    """Return the current UTC date."""
    return datetime.now(UTC).date()


def _as_date(value: str | date) -> date:
    """Return ``value`` as a ``date``."""
    return value if isinstance(value, date) else date.fromisoformat(value)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def seed(database: bool = True) -> None:
    """Apply migrations and seed the demo dataset (idempotent)."""
    if database:
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.error("alembic upgrade head failed:\n%s", result.stderr)
            raise SystemExit(result.stderr)

    db: Session = SessionLocal()
    audit = AuditService(db)
    try:
        institutions = _ensure_institutions(db)
        users = _ensure_demo_users(db, institutions)

        _ensure_sla_configs(db, audit)
        _ensure_alert_rules(db, audit)
        _ensure_compliance_config(db, audit)
        _ensure_compliance_rules(db, audit)
        _ensure_aph_reference_data(db, audit)
        _ensure_expert_pool(db, audit)
        _ensure_baseline_snapshots(db)

        cases = _seed_cases(db, institutions, users)

        db.commit()

        # Bulk demo data runs in its own transaction so a failure there cannot
        # roll back the reference configuration above.
        from app.core.config import get_settings
        from app.demo_seed import seed_demo

        try:
            seed_demo(
                db,
                institutions=institutions,
                users=_demo_accounts(db),
                storage_dir=get_settings().storage_dir,
            )
            _advance_portal_sequence(db)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception(" bulk demo seeding failed, rolled back")
            raise

        logger.info(
            " seed complete: %d institutions, %d users, %d cases",
            len(institutions),
            len(users),
            len(cases),
        )
    except Exception:
        db.rollback()
        logger.exception(" seed failed, rolled back")
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Institutions, users and demo cases
# ---------------------------------------------------------------------------


def _advance_portal_sequence(db: Session) -> None:
    """Move the portal-number sequence past the hand-written demo numbers.

    Seeded applications use explicit portal numbers (``AICTE/2026-27/0000109``)
    without consuming ``portal_application_no_seq``. Without this the first
    application created from the UI would collide with a seeded row.
    """
    db.execute(
        text(
            """
            SELECT setval(
                'portal_application_no_seq',
                GREATEST(
                    (
                        SELECT COALESCE(
                            MAX(right(portal_application_no, 7)::int), 1
                        )
                        FROM applications
                        WHERE portal_application_no
                            ~ '^AICTE/[0-9]{4}-[0-9]{2}/[0-9]{7}$'
                    ),
                    1
                ),
                true
            )
            """
        )
    )


def _ensure_institutions(db: Session) -> dict[str, Any]:
    """Upsert the demo institutions and return ``{aicte_id: UUID}``."""
    mapping: dict[str, Any] = {}
    for inst_data in _load_json("institutions.json"):
        inst = db.scalar(select(Institution).where(Institution.aicte_id == inst_data["aicte_id"]))
        if inst is None:
            inst = Institution(
                name=inst_data["name"],
                aicte_id=inst_data["aicte_id"],
                pid=inst_data["pid"],
                state=inst_data["state"],
                region=inst_data["region"],
                aicte_region=inst_data["aicte_region"],
                institution_class=inst_data["institution_class"],
                institution_type=inst_data.get("institution_type", inst_data["type"]),
                type=inst_data["type"],
                established_year=inst_data["established_year"],
                is_women_only=inst_data.get("is_women_only", False),
                is_pwbd=inst_data.get("is_pwbd", False),
                in_jk_ladakh_ne=inst_data.get("in_jk_ladakh_ne", False),
                affiliating_body=inst_data.get("affiliating_body"),
            )
            db.add(inst)
            db.flush()
            logger.info(" seeded institution %s (%s)", inst.name, inst.aicte_id)
        elif inst.institution_class != inst_data["institution_class"]:
            # The fee class drives the TER table and the Security Deposit
            # exemption (APH Table 1.4), so keep the demo row in step with the
            # seed file instead of leaving a stale class behind.
            inst.institution_class = inst_data["institution_class"]
            logger.info(
                " refreshed %s institution_class -> %s",
                inst.name,
                inst_data["institution_class"],
            )
        mapping[inst_data["aicte_id"]] = inst.id
    return mapping


def _ensure_demo_users(db: Session, institutions: dict[str, Any]) -> dict[str, User]:
    """Create the fixed demo accounts and return ``{role: User}``.

    The full account directory (20 institution admins, five scrutiny officers,
    three regional officers, committee pools) lives in :mod:`app.demo_seed`.
    This wrapper keeps the older ``{role: User}`` contract used by
    :func:`_seed_cases`, while the demo seeder receives every account.
    """
    from app.core.config import get_settings
    from app.demo_seed import ensure_demo_users

    settings = get_settings()
    regions = {
        institution.aicte_id: institution.aicte_region.value
        for institution in db.scalars(select(Institution)).all()
    }
    accounts = ensure_demo_users(
        db,
        institutions,
        regions,
        admin_password=settings.seed_demo_password.get_secret_value(),
        super_admin_email=settings.seed_admin_email,
        super_admin_password=settings.seed_admin_password.get_secret_value(),
        super_admin_name=settings.seed_admin_name,
    )

    users: dict[str, User] = {}
    for user in accounts.values():
        users.setdefault(user.role.value, user)
    return users


def _demo_accounts(db: Session) -> dict[str, User]:
    """Return every seeded demo account keyed by e-mail."""
    accounts: dict[str, User] = {}
    for user in db.scalars(select(User)).all():
        accounts[user.email] = user
    return accounts


def _table_14_rate(
    db: Session,
    application: Application,
    *,
    programme_family: str,
    level: str,
) -> tuple[int, bool, str, bool]:
    """Return ``(amount, doubled, clause, needs_verification)`` for Table 1.4.

    The amount comes from ``security_deposit_schedules`` so the seed carries no
    deposit figure of its own; the doubling for a privately leased building or
    land comes from the institution's tenure (APH Table 1.4).
    """
    from app.services.fee_calculator import security_deposit_amount

    schedule = db.scalar(
        select(SecurityDepositSchedule).where(
            SecurityDepositSchedule.programme_family == programme_family,
            SecurityDepositSchedule.level == level,
        )
    )
    if schedule is None:
        raise RuntimeError(
            "Security Deposit rates must be loaded before the demo cases "
            f"(missing {programme_family} {level})."
        )
    institution = db.get(Institution, application.institution_id)
    leased = bool(
        institution
        and (institution.land_ownership == LandOwnership.LEASED or institution.building_leased)
    )
    return (
        security_deposit_amount(schedule.amount_paise, leased=leased),
        leased,
        schedule.apH_clause,
        schedule.needs_verification,
    )


def _ensure_security_deposit(
    db: Session,
    application: Application,
    *,
    programme_family: str,
    level: str,
    status: SecurityDepositStatus,
    created_on: date,
) -> SecurityDeposit | None:
    """Create the demo deposit row or refresh it from the configured rate."""
    from app.services.fees import is_security_deposit_exempt

    if is_security_deposit_exempt(db.get(Institution, application.institution_id)):
        # APH Table 1.4: no deposit for a Government or government-aided body.
        return None
    amount, leased, clause, needs_verification = _table_14_rate(
        db,
        application,
        programme_family=programme_family,
        level=level,
    )
    existing = db.scalar(
        select(SecurityDeposit).where(
            SecurityDeposit.application_id == application.id,
            SecurityDeposit.programme_family == programme_family,
            SecurityDeposit.level == level,
        )
    )
    if existing is not None:
        existing.required_paise = amount
        existing.doubled_for_leased = leased
        existing.apH_clause = clause
        existing.needs_verification = needs_verification
        return existing
    deposit = SecurityDeposit(
        institution_id=application.institution_id,
        application_id=application.id,
        programme_family=programme_family,
        level=level,
        required_paise=amount,
        doubled_for_leased=leased,
        created_on=created_on,
        maturity_on=date(created_on.year + 2, created_on.month, created_on.day),
        status=status,
        apH_clause=clause,
        needs_verification=needs_verification,
    )
    db.add(deposit)
    return deposit


def _seed_cases(
    db: Session,
    institutions: dict[str, Any],
    users: dict[str, User],
) -> list[Application]:
    """Create the five pre-staged demo applications (idempotent by portal number)."""
    aicte_ids = sorted(institutions)
    now = datetime.now(UTC)
    today = now.date()

    def app_slot(index: int) -> Any:
        return institutions[aicte_ids[index % len(aicte_ids)]]

    def get_or_create(
        portal_no: str,
        *,
        institution_id: Any,
        application_type: str,
        track: ApplicationTrack,
        status: ApplicationStatus,
        stage: WorkflowStage,
        decision_type: DecisionType | None = None,
        **extra: Any,
    ) -> tuple[Application, bool]:
        existing = db.scalar(
            select(Application).where(Application.portal_application_no == portal_no)
        )
        if existing is not None:
            return existing, False
        application = Application(
            institution_id=institution_id,
            track=track,
            application_type=application_type,
            category=ApplicationCategory.CAT1_CUTOFF,
            academic_year=ACADEMIC_YEAR,
            portal_application_no=portal_no,
            status=status,
            current_stage=stage,
            decision_type=decision_type,
            data={"reference": portal_no, "demo": True},
            created_at=extra.get("submitted_at") or now,
            updated_at=extra.get("submitted_at") or now,
            **extra,
        )
        db.add(application)
        db.flush()
        return application, True

    def add_alert(
        application: Application,
        *,
        recipient: User,
        alert_type: str,
        severity: Severity,
        title: str,
        message: str,
        dedupe_key: str,
    ) -> None:
        if db.scalar(select(Alert.id).where(Alert.dedupe_key == dedupe_key)) is not None:
            return
        db.add(
            Alert(
                application_id=application.id,
                rule_id=None,
                recipient_user_id=recipient.id,
                type=alert_type,
                severity=severity,
                title=title,
                message=message,
                channel=AlertChannel.IN_APP,
                escalation_level=0,
                dedupe_key=dedupe_key,
            )
        )

    institution_admin = users["INSTITUTION_ADMIN"]
    scrutiny_officer = users["SCRUTINY_COMMITTEE_MEMBER"]
    cases: list[Application] = []

    # --- Case 1: EoA by self-disclosure, submitted, with an open deficiency ---
    app1, created = get_or_create(
        "AICTE/2026-27/0000001",
        institution_id=app_slot(0),
        application_type="EOA_SELF_DISCLOSURE",
        track=ApplicationTrack.EXISTING,
        status=ApplicationStatus.SUBMITTED,
        stage=WorkflowStage.APPLICATION,
        submitted_at=now - timedelta(days=25),
        locked_at=now - timedelta(days=25),
        stage_entered_at=now - timedelta(days=12),
        sla_due_at=now + timedelta(days=3),
    )
    if created:
        deficiency = Deficiency(
            application_id=app1.id,
            category="Document",
            description="Fire safety certificate expired on 2025-12-31; renewal in progress.",
            raised_by=scrutiny_officer.id,
            status=DeficiencyStatus.OPEN,
            due_date=today + timedelta(days=7),
        )
        db.add(deficiency)
        db.flush()

        db.add(
            Document(
                application_id=app1.id,
                doc_type="FIRE_SAFETY_CERTIFICATE",
                doc_code="FIRE_SAFETY_CERTIFICATE",
                filename="fire_safety_certificate_expired.pdf",
                storage_path="demo/fire_safety_certificate_expired.pdf",
                uploaded_by=institution_admin.id,
                verification_status=DocumentVerificationStatus.REJECTED,
                rejection_reason_code=DocumentRejectionReason.EXPIRED,
                rejection_comment="Certificate expired on 2025-12-31.",
                verification_notes={"note": "Expired certificate retained for the audit trail."},
                related_deficiency_id=deficiency.id,
                apH_clause="APH 1.8f",
            )
        )
        add_alert(
            app1,
            recipient=institution_admin,
            alert_type=AlertTrigger.DEFICIENCY_DUE.value,
            severity=Severity.HIGH,
            title="Deficiency raised: expired fire safety certificate",
            message=(
                "The fire safety certificate uploaded with this application has expired. "
                "Upload a valid certificate before the response deadline (APH 1.8f)."
            ),
            dedupe_key=f"seed:deficiency:{app1.id}",
        )
        logger.info(" seeded Case 1: EoA self-disclosure with an open deficiency")
    cases.append(app1)

    # --- Case 2: New institution at Scrutiny with a document deficiency ---
    app2, created = get_or_create(
        "AICTE/2026-27/0000002",
        institution_id=app_slot(1),
        application_type="NEW_INSTITUTION",
        track=ApplicationTrack.NEW_INSTITUTION,
        status=ApplicationStatus.SCRUTINY,
        stage=WorkflowStage.SCRUTINY,
        submitted_at=now - timedelta(days=5),
        locked_at=now - timedelta(days=5),
        stage_entered_at=now - timedelta(days=5),
        sla_due_at=now + timedelta(days=10),
        assigned_officer_id=scrutiny_officer.id,
    )
    if created:
        deficiency = Deficiency(
            application_id=app2.id,
            category="Document",
            description=(
                "Digital Signature Certificate not uploaded; submission cannot be verified."
            ),
            raised_by=scrutiny_officer.id,
            status=DeficiencyStatus.OPEN,
            due_date=today + timedelta(days=10),
        )
        db.add(deficiency)
        db.flush()

        db.add(
            Document(
                application_id=app2.id,
                doc_type="DSC_CERTIFICATE",
                doc_code="DSC_CERTIFICATE",
                filename="dsc_certificate_unsigned.pdf",
                storage_path="demo/dsc_certificate_unsigned.pdf",
                uploaded_by=institution_admin.id,
                verification_status=DocumentVerificationStatus.PENDING,
                related_deficiency_id=deficiency.id,
                apH_clause="APH 1.4.3",
            )
        )
        add_alert(
            app2,
            recipient=institution_admin,
            alert_type=AlertTrigger.DEFICIENCY_DUE.value,
            severity=Severity.CRITICAL,
            title="Deficiency raised: DSC certificate pending verification",
            message=(
                "The Digital Signature Certificate for this application has not been "
                "verified. Uploads must be digitally signed (APH 1.4.3)."
            ),
            dedupe_key=f"seed:deficiency:{app2.id}",
        )
        logger.info(" seeded Case 2: new-institution scrutiny with a DSC deficiency")
    cases.append(app2)

    # --- Case 3: LoR issued, seven-day appeal window running ---
    appeal_deadline = now + timedelta(days=7)
    app3, created = get_or_create(
        "AICTE/2026-27/0000003",
        institution_id=app_slot(2),
        application_type="INCREASE_INTAKE",
        track=ApplicationTrack.EXISTING,
        status=ApplicationStatus.APPEAL_WINDOW,
        stage=WorkflowStage.DECISION,
        decision_type=DecisionType.LOR,
        submitted_at=now - timedelta(days=40),
        locked_at=now - timedelta(days=40),
        stage_entered_at=now - timedelta(days=2),
        sla_due_at=now + timedelta(days=20),
        appeal_deadline=appeal_deadline,
    )
    if created:
        decision = Decision(
            application_id=app3.id,
            body=DecisionBody.EC,
            outcome=DecisionOutcome.LOR,
            decided_on=today - timedelta(days=2),
            quorum_met=True,
            notes="Fictional demo decision: deficiencies not addressed within the window.",
            apH_clause="APH 1.10",
        )
        db.add(decision)
        db.flush()

        db.add(
            DecisionLetter(
                application_id=app3.id,
                decision_id=decision.id,
                letter_type=DecisionLetterType.LOR,
                letter_number=f"LoR/AICTE/{ACADEMIC_YEAR}/0003",
                issued_on=today - timedelta(days=2),
                published_at=now - timedelta(days=2),
                appeal_clock_start=now - timedelta(days=2),
                appeal_deadline=appeal_deadline,
                body_text="Fictional Letter of Rejection issued for the demo dataset.",
            )
        )
        add_alert(
            app3,
            recipient=institution_admin,
            alert_type=AlertTrigger.APPEAL_WINDOW_CLOSING.value,
            severity=Severity.MEDIUM,
            title="Appeal window closing in 7 days",
            message=(
                "The seven-day appeal window against this decision closes on "
                f"{appeal_deadline.date().isoformat()} (APH 1.11a)."
            ),
            dedupe_key=f"seed:appeal:{app3.id}",
        )
        logger.info(" seeded Case 3: LoR issued with the appeal window running")
    cases.append(app3)

    # --- Case 4: LoA recommended, Security Deposit pending ---
    # Owned by the Institution Administrator demo account so the deposit clock
    # and the release flow are visible on the institution dashboard.
    app4, created = get_or_create(
        "AICTE/2026-27/0000004",
        institution_id=institution_admin.institution_id or app_slot(3),
        application_type="INCREASE_INTAKE",
        track=ApplicationTrack.EXISTING,
        status=ApplicationStatus.SECURITY_DEPOSIT_PENDING,
        stage=WorkflowStage.DECISION,
        decision_type=DecisionType.LOA,
        submitted_at=now - timedelta(days=60),
        locked_at=now - timedelta(days=60),
        stage_entered_at=now - timedelta(days=3),
        sla_due_at=now + timedelta(days=12),
        security_deposit_due_on=today + timedelta(days=12),
    )
    if created:
        decision = Decision(
            application_id=app4.id,
            body=DecisionBody.EC,
            outcome=DecisionOutcome.LOA,
            decided_on=today - timedelta(days=3),
            quorum_met=True,
            notes="Fictional demo decision: LoA recommended, Security Deposit pending.",
            apH_clause="APH 1.10",
        )
        db.add(decision)
        db.flush()

        add_alert(
            app4,
            recipient=institution_admin,
            alert_type=AlertTrigger.DEPOSIT_DUE.value,
            severity=Severity.MEDIUM,
            title="Security Deposit and Affidavit 3 due within 15 days",
            message=(
                "The Security Deposit and Affidavit 3 for this application are due by "
                f"{(today + timedelta(days=15)).isoformat()} (APH 2.25f)."
            ),
            dedupe_key=f"seed:deposit:{app4.id}",
        )
        logger.info(" seeded Case 4: LoA recommended with the Security Deposit pending")
    cases.append(app4)

    # --- Case 5: Clean institution, Nil Deficiency, LoA active ---
    # The deposit on this file is already paid, so the release request, the
    # clearances and the NOC can all be demonstrated (APH 6.46).
    app5, created = get_or_create(
        "AICTE/2026-27/0000005",
        institution_id=institution_admin.institution_id or app_slot(4),
        application_type="NEW_INSTITUTION",
        track=ApplicationTrack.NEW_INSTITUTION,
        status=ApplicationStatus.ACTIVE_LOA,
        stage=WorkflowStage.COMPLETED,
        decision_type=DecisionType.LOA,
        submitted_at=now - timedelta(days=200),
        locked_at=now - timedelta(days=200),
        stage_entered_at=now - timedelta(days=120),
        loa_valid_until=today + timedelta(days=610),
    )
    if created:
        logger.info(" seeded Case 5: clean institution with Nil Deficiency")
    cases.append(app5)

    # --- Security Deposit clocks on the two seeded approvals (APH 2.25f) ----
    # Both files are owned by the Institution Administrator demo account so the
    # 15-day clock, the penalty ladder and the release flow are visible on the
    # dashboard. Amounts come from the configured Table 1.4 rates.
    if institution_admin.institution_id is not None:
        for application in (app4, app5):
            application.institution_id = institution_admin.institution_id
        db.flush()
    _ensure_security_deposit(
        db,
        app4,
        programme_family="ENGINEERING_TECHNOLOGY",
        level="UG",
        status=SecurityDepositStatus.PENDING,
        created_on=today - timedelta(days=3),
    )
    db.flush()
    _ensure_security_deposit(
        db,
        app5,
        programme_family="ENGINEERING_TECHNOLOGY",
        level="UG",
        status=SecurityDepositStatus.PAID,
        created_on=today - timedelta(days=90),
    )

    # --- Case 6: verified complaint at the show-cause stage -----------------
    # The full demo chain runs from here: show-cause reply (institution admin),
    # SHC hearing (SHC member), EC decision with Speaking Order (EC member),
    # record + hear + issue a penal action, then a restoration request.
    # Alerts must reach the institution that owns Case 1, which is not
    # necessarily the demo Institution Administrator: an older database can
    # keep Case 1 on another institution.
    case_owner_admin = (
        db.scalar(
            select(User).where(
                User.institution_id == app1.institution_id,
                User.role == Role.INSTITUTION_ADMIN,
            )
        )
        or institution_admin
    )
    existing_complaint = db.scalar(
        select(Complaint).where(
            Complaint.application_id == app1.id,
            Complaint.category == "EXCESS_ADMISSION",
        )
    )
    if existing_complaint is None:
        complaint = Complaint(
            institution_id=app1.institution_id,
            application_id=app1.id,
            source="PORTAL",
            status=ComplaintStatus.SHOW_CAUSE,
            category="EXCESS_ADMISSION",
            description=(
                "Fictional verified complaint: the institution is alleged to have "
                "admitted students beyond its approved intake (APH 7.4g)."
            ),
            received_on=today - timedelta(days=20),
            complainant_name="Fictional Complainant",
            complainant_contact="complainant@example.edu",
            complainant_verified=True,
            is_anonymous=False,
            scsc_decision="SHOW_CAUSE",
            scsc_decided_on=today - timedelta(days=8),
            scsc_notes=(
                "SCSC found the complaint verified and issued a show-cause notice (APH 7.10c)."
            ),
            show_cause_issued_on=today - timedelta(days=8),
            show_cause_due_on=today + timedelta(days=7),
            apH_clause="APH 7.10d",
        )
        db.add(complaint)
        db.flush()
        add_alert(
            app1,
            recipient=case_owner_admin,
            alert_type=AlertTrigger.DEFICIENCY_DUE.value,
            severity=Severity.HIGH,
            title="Show-cause notice: complaint of excess admission",
            message=(
                "The Standing Complaint Scrutiny Committee issued a show-cause notice. "
                f"Reply by {(today + timedelta(days=7)).isoformat()} (APH 7.10c-d)."
            ),
            dedupe_key=f"seed:complaint:{app1.id}",
        )
        logger.info(" seeded Case 6: verified complaint at the show-cause stage")
    else:
        # Keep an already-seeded notice pointing at the current case owner.
        complaint_alert = db.scalar(
            select(Alert).where(Alert.dedupe_key == f"seed:complaint:{app1.id}")
        )
        if complaint_alert is not None:
            complaint_alert.recipient_user_id = case_owner_admin.id

    return cases


# ---------------------------------------------------------------------------
# Reference configuration (idempotent upserts)
# ---------------------------------------------------------------------------


def _ensure_sla_configs(db: Session, audit: AuditService | None = None) -> None:
    """Create the illustrative per-stage SLA rows when they are missing."""
    for stage, duration_days, escalation_after_days, escalate_to_role in _SLA_CONFIGS:
        existing = db.scalar(select(SLAConfig).where(SLAConfig.stage == stage))
        if existing is not None:
            continue
        db.add(
            SLAConfig(
                stage=stage,
                duration_days=duration_days,
                escalation_after_days=escalation_after_days,
                escalate_to_role=escalate_to_role,
                apH_clause="DEMO",
                needs_verification=True,
            )
        )
    db.flush()


def _ensure_alert_rules(db: Session, audit: AuditService | None = None) -> None:
    """Create the trigger catalogue and the baseline alert rules."""
    for trigger in AlertTrigger:
        existing = db.scalar(
            select(AlertTriggerCatalogue).where(AlertTriggerCatalogue.code == trigger.value)
        )
        if existing is None:
            db.add(
                AlertTriggerCatalogue(
                    code=trigger.value,
                    handler_key=trigger.value,
                    description=f"Demo trigger {trigger.value}.",
                    apH_clause="DEMO",
                    needs_verification=True,
                )
            )
    db.flush()

    for definition in _ALERT_RULES:
        # One active rule per trigger keeps scan output deterministic: a second
        # rule for the same trigger would raise duplicate alerts for one event.
        existing = db.scalar(
            select(AlertRule).where(
                AlertRule.code == definition["code"],
            )
        )
        already_configured = db.scalar(
            select(AlertRule.id).where(
                AlertRule.trigger_type == definition["trigger"].value,
                AlertRule.is_active.is_(True),
            )
        )
        if existing is not None or already_configured is not None:
            continue
        db.add(
            AlertRule(
                code=definition["code"],
                name=definition["code"].replace("-", " ").title(),
                description="Illustrative demo alert rule; thresholds are not AICTE norms.",
                trigger_type=definition["trigger"].value,
                days_before=definition["days_before"],
                severity=definition["severity"],
                channel_list=[channel.value for channel in definition["channels"]],
                template=definition["template"],
                escalation_role=definition["escalation_role"],
                is_active=True,
                apH_clause="DEMO",
                needs_verification=True,
            )
        )
    db.flush()


def _ensure_compliance_config(db: Session, audit: AuditService | None = None) -> None:
    """Load the admin-editable compliance configuration keys."""
    for key, value in _load_json("compliance_config.json").items():
        existing = db.scalar(select(ComplianceConfig).where(ComplianceConfig.key == key))
        if existing is None:
            db.add(ComplianceConfig(key=key, value=value))
    db.flush()


def _ensure_compliance_rules(db: Session, audit: AuditService | None = None) -> None:
    """Load the APH compliance rule library."""
    for row in _load_json("compliance_rules.json"):
        existing = db.scalar(select(ComplianceRule).where(ComplianceRule.code == row["code"]))
        if existing is not None:
            continue
        db.add(
            ComplianceRule(
                code=row["code"],
                name=row["name"],
                category=row["category"],
                description=row["description"],
                metric_key=row["metric_key"],
                operator=row["operator"],
                threshold=Decimal(str(row["threshold"])),
                severity=Severity(row["severity"]),
                applies_to="INSTITUTION",
                applies_to_family=row.get("applies_to_family"),
                applies_to_level=row.get("applies_to_level"),
                apH_clause=row["apH_clause"],
                needs_verification=row.get("needs_verification", False),
                metric_params=row.get("metric_params", {}),
                explanation_template=row.get("explanation_template"),
                penalty_codes=row.get("penalty_codes", []),
            )
        )
    db.flush()


def _ensure_aph_reference_data(db: Session, audit: AuditService | None = None) -> None:
    """Load the generated APH reference tables.

    The route rows carry the prototype ``workflow_key`` binding added by the
    generator, so ``make seed`` also restores them after ``make reset-demo``.
    """
    _ensure_application_type_routes(db)

    for row in _load_json("public_notices.json"):
        existing = db.scalar(
            select(PublicNotice).where(
                PublicNotice.academic_year == row["academic_year"],
                PublicNotice.category == ApplicationCategory(row["category"]),
            )
        )
        if existing is not None:
            continue
        db.add(
            PublicNotice(
                academic_year=row["academic_year"],
                category=ApplicationCategory(row["category"]),
                opens_on=_as_date(row["opens_on"]),
                cutoff_on=_as_date(row["cutoff_on"]),
                apH_clause=row["apH_clause"],
                needs_verification=row.get("needs_verification", True),
                is_demo=row.get("is_demo", True),
                note=row.get("note"),
            )
        )

    for row in _load_json("academic_calendar_events.json"):
        existing = db.scalar(
            select(AcademicCalendarEvent).where(
                AcademicCalendarEvent.academic_year == row["academic_year"],
                AcademicCalendarEvent.event_key == row["event_key"],
            )
        )
        if existing is not None:
            continue
        db.add(
            AcademicCalendarEvent(
                academic_year=row["academic_year"],
                event_key=row["event_key"],
                date=_as_date(row["date"]),
                description=row.get("description"),
                apH_clause=row["apH_clause"],
                needs_verification=row.get("needs_verification", True),
                is_demo=row.get("is_demo", True),
            )
        )

    for row in _load_json("fee_schedules.json"):
        existing = db.scalar(
            select(FeeSchedule).where(
                FeeSchedule.item_code == row["item_code"],
                FeeSchedule.institution_class == row.get("institution_class"),
            )
        )
        if existing is not None:
            continue
        db.add(
            FeeSchedule(
                item_code=row["item_code"],
                label=row["label"],
                description=row.get("description"),
                institution_class=row.get("institution_class"),
                unit=row["unit"],
                amount_paise=row["amount_paise"],
                base_academic_year=row.get("base_academic_year", ACADEMIC_YEAR),
                annual_increase_pct=Decimal(str(row.get("annual_increase_pct", 10))),
                apH_clause=row["apH_clause"],
                needs_verification=row.get("needs_verification", False),
            )
        )

    for row in _load_json("required_documents.json"):
        existing = db.scalar(
            select(RequiredDocument).where(
                RequiredDocument.application_type == row["application_type"],
                RequiredDocument.doc_type == row["doc_type"],
            )
        )
        if existing is not None:
            continue
        db.add(
            RequiredDocument(
                application_type=row["application_type"],
                doc_type=row["doc_type"],
                doc_code=row.get("doc_code"),
                condition_expr=row.get("condition_expr"),
                apH_clause=row["apH_clause"],
                needs_verification=row.get("needs_verification", False),
                mandatory=row.get("mandatory", True),
            )
        )

    for row in _load_json("security_deposit_schedules.json"):
        existing = db.scalar(
            select(SecurityDepositSchedule).where(
                SecurityDepositSchedule.programme_family == row["programme_family"],
                SecurityDepositSchedule.level == row["level"],
            )
        )
        if existing is not None:
            continue
        db.add(
            SecurityDepositSchedule(
                programme_family=row["programme_family"],
                level=row["level"],
                amount_paise=row["amount_paise"],
                doubled_for_leased=row.get("doubled_for_leased", True),
                apH_clause=row["apH_clause"],
                needs_verification=row.get("needs_verification", False),
            )
        )

    for row in _load_json("workflow_definitions.json"):
        existing = db.scalar(select(WorkflowDefinition).where(WorkflowDefinition.key == row["key"]))
        if existing is not None:
            continue
        definition = WorkflowDefinition(
            key=row["key"],
            label=row["label"],
            track=row["track"],
            description=row.get("description", ""),
            is_active=row.get("is_active", True),
            config=row.get("config", {}),
            apH_clause=row["apH_clause"],
            needs_verification=row.get("needs_verification", False),
            states=[
                WorkflowState(
                    code=state["code"],
                    label=state["label"],
                    stage=state["stage"],
                    is_initial=state.get("is_initial", False),
                    is_terminal=state.get("is_terminal", False),
                    sort_order=state.get("sort_order", 0),
                    description=state.get("description", ""),
                    apH_clause=state["apH_clause"],
                    needs_verification=state.get("needs_verification", False),
                )
                for state in row["states"]
            ],
            transitions=[
                WorkflowTransition(
                    from_state=edge["from_state"],
                    to_state=edge["to_state"],
                    action=edge["action"],
                    label=edge["label"],
                    description=edge.get("description", ""),
                    allowed_roles=edge.get("allowed_roles", []),
                    guard_expr=edge.get("guard_expr", []),
                    side_effects=edge.get("side_effects", []),
                    requires=edge.get("requires", "none"),
                    tone=edge.get("tone", "secondary"),
                    sla_stage=edge.get("sla_stage"),
                    priority=edge.get("priority", 0),
                    apH_clause=edge["apH_clause"],
                    needs_verification=edge.get("needs_verification", False),
                )
                for edge in row["transitions"]
            ],
        )
        db.add(definition)
    _ensure_nomenclature_courses(db)
    _ensure_competent_authorities(db)
    db.flush()


def _ensure_application_type_routes(db: Session) -> None:
    """Load the Table 2.3 application-type routes and their workflow binding."""
    rows = _load_json("application_type_routes.json")
    existing = {
        route.type: route for route in db.scalars(select(ApplicationTypeRoute)).all()
    }
    added = 0
    for row in rows:
        route = existing.get(row["type"])
        if route is not None:
            if route.workflow_key is None and row.get("workflow_key"):
                route.workflow_key = row["workflow_key"]
            continue
        db.add(
            ApplicationTypeRoute(
                type=row["type"],
                label=row["label"],
                category=ApplicationCategory(row["category"]),
                requires_self_disclosure=row["requires_self_disclosure"],
                requires_scrutiny=row["requires_scrutiny"],
                requires_evc=row["requires_evc"],
                requires_hearing_aa=row["requires_hearing_aa"],
                nil_deficiency_required=row["nil_deficiency_required"],
                no_ter=row["no_ter"],
                year_round=row["year_round"],
                workflow_key=row.get("workflow_key"),
                apH_clause=row["apH_clause"],
                needs_verification=row.get("needs_verification", False),
            )
        )
        added += 1
    if added:
        logger.info(" seeded %d application-type routes", added)


def _ensure_nomenclature_courses(db: Session) -> None:
    """Load the Annexure-11 course names without rewriting existing rows."""
    rows = _load_json("nomenclature_courses.json")
    existing = {
        (level, family, name)
        for level, family, name in db.execute(
            select(
                NomenclatureCourse.level,
                NomenclatureCourse.programme_family,
                NomenclatureCourse.course_name,
            )
        ).all()
    }
    added = 0
    for row in rows:
        key = (row["level"], row["programme_family"], row["course_name"])
        if key in existing:
            continue
        db.add(
            NomenclatureCourse(
                level=row["level"],
                programme_family=row["programme_family"],
                course_name=row["course_name"],
                source_section=row["source_section"],
                is_emerging=row.get("is_emerging", False),
                apH_clause=row["apH_clause"],
                needs_verification=row.get("needs_verification", False),
            )
        )
        existing.add(key)
        added += 1
    if added:
        logger.info(" seeded %d Annexure-11 course names", added)


def _ensure_competent_authorities(db: Session) -> None:
    """Load the Annexure-14 certificate authorities without rewriting rows."""
    rows = _load_json("competent_authorities.json")
    existing = set(db.scalars(select(CompetentAuthority.state)).all())
    added = 0
    for row in rows:
        if row["state"] in existing:
            continue
        db.add(
            CompetentAuthority(
                state=row["state"],
                aicte_region=InstitutionRegion(row["aicte_region"]),
                land_use_authority=row.get("land_use_authority"),
                site_plan_authority=row.get("site_plan_authority"),
                building_plan_authority=row.get("building_plan_authority"),
                occupation_authority=row.get("occupation_authority"),
                source_text=row.get("source_text"),
                apH_clause=row["apH_clause"],
                needs_verification=row.get("needs_verification", True),
            )
        )
        existing.add(row["state"])
        added += 1
    if added:
        logger.info(" seeded %d Annexure-14 competent authorities", added)


def _ensure_expert_pool(db: Session, audit: AuditService | None = None) -> None:
    """Create clearly fictional committee members when the pool is empty."""
    if db.scalar(select(ExpertPool.id).limit(1)) is not None:
        return

    # (name, designation, state, AICTE region, seat tags, years, retired HC judge)
    experts: tuple[tuple[str, str, str, str, tuple[str, ...], int, bool], ...] = (
        (
            "Fictional Chair A",
            "Retired Judge, High Court",
            "Delhi",
            "NORTHERN",
            ("CHAIR_SHC",),
            30,
            True,
        ),
        (
            "Fictional Chair B",
            "Retired Judge, High Court",
            "Kerala",
            "SOUTH_WESTERN",
            ("CHAIR_SHC",),
            28,
            True,
        ),
        (
            "Fictional Academic A",
            "Professor, Computer Science",
            "Tamil Nadu",
            "SOUTHERN",
            ("ACADEMIC",),
            15,
            False,
        ),
        (
            "Fictional Academic B",
            "Professor, Civil Engineering",
            "West Bengal",
            "EASTERN",
            ("ACADEMIC", "ARCHITECT"),
            20,
            False,
        ),
        (
            "Fictional Academic C",
            "Professor, Electrical Engineering",
            "Punjab",
            "NORTH_WESTERN",
            ("ACADEMIC",),
            12,
            False,
        ),
        (
            "Fictional Academic D",
            "Professor, Management Studies",
            "Uttar Pradesh",
            "NORTHERN",
            ("ACADEMIC", "CHAIR_SHC"),
            16,
            False,
        ),
        (
            "Fictional Academic E",
            "Professor, Structural Engineering",
            "Karnataka",
            "SOUTH_WESTERN",
            ("ACADEMIC", "ARCHITECT"),
            22,
            False,
        ),
        (
            "Fictional Academic F",
            "Professor, Chemical Engineering",
            "Gujarat",
            "CENTRAL",
            ("ACADEMIC",),
            14,
            False,
        ),
        ("Fictional Advocate A", "Senior Advocate", "Delhi", "NORTHERN", ("ADVOCATE",), 16, False),
        ("Fictional Advocate B", "Advocate", "Karnataka", "SOUTH_WESTERN", ("ADVOCATE",), 8, False),
        ("Fictional Advocate C", "Advocate", "West Bengal", "EASTERN", ("ADVOCATE",), 12, False),
        (
            "Fictional Advocate D",
            "Senior Advocate",
            "Tamil Nadu",
            "SOUTHERN",
            ("ADVOCATE",),
            14,
            False,
        ),
        (
            "Fictional Architect A",
            "Chief Architect",
            "Tamil Nadu",
            "SOUTHERN",
            ("ARCHITECT",),
            15,
            False,
        ),
        (
            "Fictional Architect B",
            "Superintending Architect",
            "Delhi",
            "NORTHERN",
            ("ARCHITECT",),
            13,
            False,
        ),
        (
            "Fictional Architect C",
            "Professor of Architecture",
            "Rajasthan",
            "NORTH_WESTERN",
            ("ARCHITECT", "ACADEMIC"),
            20,
            False,
        ),
        (
            "Fictional Industry A",
            "Chief Technology Officer",
            "Tamil Nadu",
            "SOUTHERN",
            ("INDUSTRY_EXPERT",),
            16,
            False,
        ),
        (
            "Fictional Industry B",
            "Executive Director (Engineering)",
            "Jharkhand",
            "EASTERN",
            ("INDUSTRY_EXPERT",),
            21,
            False,
        ),
        (
            "Fictional Revenue A",
            "Additional Collector (Land Administration)",
            "Uttar Pradesh",
            "NORTHERN",
            ("REVENUE_LAND",),
            24,
            False,
        ),
        (
            "Fictional Revenue B",
            "Deputy Director, Land Records",
            "Odisha",
            "EASTERN",
            ("REVENUE_LAND",),
            19,
            False,
        ),
        (
            "Fictional Registrar A",
            "Registrar & Former Joint Director DTE",
            "Telangana",
            "SOUTH_CENTRAL",
            ("DTE_REGISTRAR", "ACADEMIC"),
            22,
            False,
        ),
        (
            "Fictional Registrar B",
            "Joint Director, Technical Education",
            "Assam",
            "EASTERN",
            ("DTE_REGISTRAR", "ACADEMIC"),
            17,
            False,
        ),
        (
            "Fictional Co-opt A",
            "Dean of Academic Courses",
            "Odisha",
            "EASTERN",
            ("CO_OPT", "ACADEMIC"),
            13,
            False,
        ),
        (
            "Fictional Co-opt B",
            "State Board of Technical Education Nominee",
            "Kerala",
            "SOUTH_WESTERN",
            ("CO_OPT", "ACADEMIC"),
            15,
            False,
        ),
    )
    for index, (name, designation, state, region, tags, years, hc_judge) in enumerate(experts):
        db.add(
            ExpertPool(
                name=f"{name} (Fictional)",
                designation=designation,
                institution_name="Fictional Institute",
                state=state,
                aicte_region=region,
                email=f"expert{index + 1}@demo.edu",
                seat_tags=list(tags),
                years_experience=years,
                is_retired_hc_judge=hc_judge,
                is_active=True,
                is_fictional=True,
                apH_clause="APH 1.8a",
            )
        )
    db.flush()


def _ensure_baseline_snapshots(db: Session) -> None:
    """Reserve the hook for baseline compliance snapshots.

    Snapshots are produced by the compliance monitor, so the seed only needs to
    guarantee that the rule catalogue exists (``_ensure_compliance_rules``).
    """
    logger.debug(" baseline compliance snapshots are produced by the monitor")


if __name__ == "__main__":
    seed(database=True)
