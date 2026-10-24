"""Idempotent development seed data.

Only clearly fictional data is created: two demo institutions, one account per
role, four applications and one inspection used to exercise role-scoped access
and the alert/escalation demo. Illustrative document rules, SLA durations,
alert rules and compliance rules are seeded as editable configuration; they are
not real AICTE norms or thresholds.
"""

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import (
    AlertRule,
    AlertTrigger,
    Application,
    ApplicationStatus,
    ApplicationType,
    ComplianceConfig,
    ComplianceRule,
    ComplianceSnapshot,
    Inspection,
    InspectionStatus,
    Institution,
    RequiredDocument,
    Role,
    Severity,
    SLAConfig,
    User,
    WorkflowEvent,
    WorkflowStage,
)
from app.services.audit import AuditService
from app.services.compliance import evaluate_institution

logger = logging.getLogger("app.seed")

WEST_AICTE_ID = "DEMO-INST-0001"
SOUTH_AICTE_ID = "DEMO-INST-0002"
DEMO_ACADEMIC_YEAR = "2026-27"
WEST_REFERENCE = "DEMO-WEST-2026-001"
SOUTH_REFERENCE = "DEMO-SOUTH-2026-001"
DEMO_ALERT_REFERENCE = "DEMO-WEST-2026-003"

REQUIRED_DOCUMENTS = {
    ApplicationType.NEW: (
        ("AFFILIATION_CERTIFICATE", True),
        ("LAND_OWNERSHIP_DOCUMENT", True),
        ("BUILDING_PLAN_APPROVAL", True),
        ("FACULTY_DETAILS", True),
        ("FINANCIAL_STATEMENT", True),
        ("MANDATORY_DISCLOSURE", True),
        ("NAAC_NBA_CERTIFICATE", False),
    ),
    ApplicationType.EXTENSION: (
        ("AFFILIATION_CERTIFICATE", True),
        ("LAND_OWNERSHIP_DOCUMENT", True),
        ("BUILDING_PLAN_APPROVAL", True),
        ("FACULTY_DETAILS", True),
        ("FINANCIAL_STATEMENT", True),
        ("MANDATORY_DISCLOSURE", True),
        ("NAAC_NBA_CERTIFICATE", False),
    ),
    ApplicationType.INTAKE_CHANGE: (
        ("EXISTING_APPROVAL_LETTER", True),
        ("FACULTY_DETAILS", True),
        ("INFRASTRUCTURE_PLAN", True),
        ("FINANCIAL_STATEMENT", True),
        ("MANDATORY_DISCLOSURE", True),
        ("NAAC_NBA_CERTIFICATE", False),
    ),
}

SLA_CONFIGS = (
    (WorkflowStage.APPLICATION, 30, 20, Role.REGIONAL_HEAD),
    (WorkflowStage.DOCUMENT_VERIFICATION, 10, 7, Role.SCRUTINY_OFFICER),
    (WorkflowStage.SCRUTINY, 15, 10, Role.REGIONAL_HEAD),
    (WorkflowStage.DEFICIENCY, 7, 5, Role.SCRUTINY_OFFICER),
    (WorkflowStage.INSPECTION, 20, 14, Role.REGIONAL_HEAD),
    (WorkflowStage.COMMITTEE_REVIEW, 10, 7, Role.SUPER_ADMIN),
    (WorkflowStage.DECISION, 10, 7, Role.SUPER_ADMIN),
)

# Database configuration, not hard-coded business logic. Administrators can
# edit every row from the alert-rule screen. The values are illustrative demo
# settings and must be reviewed against the current AICTE handbook.
ALERT_RULES = (
    (
        "DEADLINE-7",
        "Approaching deadline: 7 days",
        "First warning before an application SLA is due.",
        AlertTrigger.DEADLINE_APPROACHING,
        7,
        Severity.LOW,
        ("IN_APP", "EMAIL"),
        (
            "The {stage} stage for {institution} (application "
            "{application_reference}, ID {application_id}) is due on {due_date}. "
            "{days_remaining} day(s) remain before the configured SLA deadline."
        ),
        Role.REGIONAL_HEAD,
    ),
    (
        "DEADLINE-3",
        "Approaching deadline: 3 days",
        "Escalated warning before an application SLA is due.",
        AlertTrigger.DEADLINE_APPROACHING,
        3,
        Severity.MEDIUM,
        ("IN_APP", "EMAIL"),
        (
            "Only {days_remaining} day(s) remain for {institution} "
            "(application {application_reference}) before the {stage} deadline "
            "on {due_date}."
        ),
        Role.REGIONAL_HEAD,
    ),
    (
        "DEADLINE-1",
        "Approaching deadline: 1 day",
        "Final warning before an application SLA is due.",
        AlertTrigger.DEADLINE_APPROACHING,
        1,
        Severity.HIGH,
        ("IN_APP", "EMAIL"),
        (
            "The {stage} deadline for {institution} (application "
            "{application_reference}) is {due_date}. Immediate attention is "
            "required."
        ),
        Role.REGIONAL_HEAD,
    ),
    (
        "SLA-BREACH",
        "SLA breached",
        "Raised when an application passes its stage SLA without a transition.",
        AlertTrigger.SLA_BREACHED,
        0,
        Severity.CRITICAL,
        ("IN_APP", "EMAIL", "SMS"),
        (
            "The configured SLA for {institution} (application "
            "{application_reference}, ID {application_id}) was due on {due_date} "
            "and is now breached. Review the case and record the next action."
        ),
        Role.REGIONAL_HEAD,
    ),
    (
        "DEFICIENCY-DUE",
        "Deficiency response due",
        "Warns the institution before a deficiency response deadline.",
        AlertTrigger.DEFICIENCY_DUE,
        3,
        Severity.MEDIUM,
        ("IN_APP", "EMAIL"),
        (
            "A response from {institution} is due on {due_date} for a deficiency "
            "on application {application_reference}. Detail: {deficiency}"
        ),
        Role.REGIONAL_HEAD,
    ),
    (
        "DEFICIENCY-OVERDUE",
        "Deficiency response overdue",
        "Raised when an open deficiency response has not arrived.",
        AlertTrigger.DEFICIENCY_OVERDUE,
        0,
        Severity.HIGH,
        ("IN_APP", "EMAIL"),
        (
            "The deficiency response for {institution} (application "
            "{application_reference}) was due on {due_date} and is now overdue. "
            "Detail: {deficiency}"
        ),
        Role.REGIONAL_HEAD,
    ),
    (
        "DOCUMENT-EXPIRING-30",
        "Document expiring in 30 days",
        "Early warning for a document that will expire soon.",
        AlertTrigger.DOCUMENT_EXPIRING,
        30,
        Severity.LOW,
        ("IN_APP", "EMAIL"),
        (
            "A document ({document}) for {institution} (application "
            "{application_reference}) expires on {due_date}. Please request a "
            "valid replacement."
        ),
        Role.REGIONAL_HEAD,
    ),
    (
        "DOCUMENT-EXPIRING-15",
        "Document expiring in 15 days",
        "Final warning for a document that will expire soon.",
        AlertTrigger.DOCUMENT_EXPIRING,
        15,
        Severity.MEDIUM,
        ("IN_APP", "EMAIL"),
        (
            "The document {document} for {institution} expires on {due_date}. "
            "The application may be blocked unless a replacement is uploaded."
        ),
        Role.REGIONAL_HEAD,
    ),
    (
        "COMPLIANCE-RED",
        "Institution compliance is RED",
        "Notifies oversight when an institution's compliance status worsens to RED.",
        AlertTrigger.COMPLIANCE_RED,
        0,
        Severity.CRITICAL,
        ("IN_APP",),
        (
            "{institution} has moved to RED compliance status (score {score}/100; "
            "{failed_count} failed rules, {failed_critical_count} critical). "
            "Review the failing rules and follow up with the institution."
        ),
        Role.SUPER_ADMIN,
    ),
    (
        "STATUS-CHANGED",
        "Application status changed",
        "Notifies the responsible officer when an application moves stage.",
        AlertTrigger.APPLICATION_STATUS_CHANGED,
        0,
        Severity.LOW,
        ("IN_APP",),
        (
            "Application {application_reference} ({application_id}) for "
            "{institution} moved from {from_status} to {status}."
        ),
        Role.REGIONAL_HEAD,
    ),
    (
        "INSPECTION-SCHEDULED",
        "Inspection scheduled",
        "Notifies the committee member and oversight when a visit is scheduled.",
        AlertTrigger.INSPECTION_SCHEDULED,
        0,
        Severity.MEDIUM,
        ("IN_APP", "EMAIL"),
        (
            "An inspection for {institution} (application "
            "{application_reference}) is scheduled for {inspection_date}."
        ),
        Role.REGIONAL_HEAD,
    ),
)


# Deliberately illustrative thresholds for the local demo. They are database
# configuration, not official AICTE norms, and should be reviewed by an
# administrator against the current Approval Process Handbook.
COMPLIANCE_RULES = (
    # code, name, category, description, metric_key, operator, threshold,
    # threshold_max, severity, applies_to
    (
        "DEMO-LAND-AREA",
        "Minimum campus land area",
        "Infrastructure",
        "Illustrative minimum land area available to the institution.",
        "infrastructure.land_area",
        ">=",
        Decimal("8000"),
        None,
        Severity.HIGH,
        "ALL",
    ),
    (
        "DEMO-BUILT-UP-AREA",
        "Minimum built-up area",
        "Infrastructure",
        "Illustrative minimum constructed area for teaching and support spaces.",
        "infrastructure.built_up_area",
        ">=",
        Decimal("5000"),
        None,
        Severity.HIGH,
        "ALL",
    ),
    (
        "DEMO-LABORATORIES",
        "Laboratory count",
        "Infrastructure",
        "Illustrative minimum number of laboratories for the demo flow.",
        "infrastructure.labs",
        ">=",
        Decimal("10"),
        None,
        Severity.MEDIUM,
        "ALL",
    ),
    (
        "DEMO-LIBRARY-VOLUMES",
        "Library volumes",
        "Infrastructure",
        "Illustrative minimum library collection for the demo flow.",
        "infrastructure.library",
        ">=",
        Decimal("10000"),
        None,
        Severity.MEDIUM,
        "ALL",
    ),
    (
        "DEMO-FACULTY-TOTAL",
        "Total faculty strength",
        "Faculty",
        "Illustrative minimum total faculty strength for the demo flow.",
        "faculty.total",
        ">=",
        Decimal("60"),
        None,
        Severity.HIGH,
        "ALL",
    ),
    (
        "DEMO-STUDENT-FACULTY-RATIO",
        "Student-faculty ratio",
        "Faculty",
        "Illustrative maximum students per faculty member.",
        "faculty.student_faculty_ratio",
        "<=",
        Decimal("20"),
        None,
        Severity.HIGH,
        "ALL",
    ),
    (
        "DEMO-PHD-FACULTY-RATIO",
        "Faculty with a PhD",
        "Faculty",
        "Illustrative minimum share of faculty holding a PhD.",
        "faculty.phd_faculty_ratio",
        ">=",
        Decimal("30"),
        None,
        Severity.MEDIUM,
        "ALL",
    ),
    (
        "DEMO-FINANCIAL-BALANCE",
        "Non-negative declared balance",
        "Finance",
        "Illustrative requirement that the declared annual balance is not negative.",
        "finance.balance",
        ">=",
        Decimal("0"),
        None,
        Severity.MEDIUM,
        "ALL",
    ),
    (
        "DEMO-QUALIFIED-FACULTY",
        "Qualified faculty share",
        "Faculty",
        "Illustrative minimum share of permanent-rank (professorial) faculty.",
        "derived.qualified_faculty_pct",
        ">=",
        Decimal("90"),
        None,
        Severity.HIGH,
        "ALL",
    ),
    (
        "DEMO-BUILT-UP-PER-STUDENT",
        "Built-up area per student",
        "Infrastructure",
        "Illustrative minimum constructed area per approved intake seat.",
        "derived.built_up_area_per_student",
        ">=",
        Decimal("1.5"),
        None,
        Severity.MEDIUM,
        "ALL",
    ),
    (
        "DEMO-LAB-PER-PROGRAM",
        "Laboratories per programme",
        "Infrastructure",
        "Illustrative minimum average laboratories per requested programme.",
        "derived.lab_count_per_program",
        ">=",
        Decimal("1"),
        None,
        Severity.MEDIUM,
        "ALL",
    ),
    (
        "DEMO-NAAC-DECLARED",
        "NAAC grade declared",
        "Accreditation",
        "Illustrative expectation that a valid NAAC grade is declared.",
        "derived.naac_grade_present",
        ">=",
        Decimal("1"),
        None,
        Severity.MEDIUM,
        "ALL",
    ),
    (
        "DEMO-MANDATORY-DISCLOSURE",
        "Mandatory disclosure published",
        "Accreditation",
        "Illustrative requirement that a mandatory disclosure URL is provided.",
        "derived.mandatory_disclosure_published",
        ">=",
        Decimal("1"),
        None,
        Severity.HIGH,
        "ALL",
    ),
    (
        "DEMO-DOCUMENTS-VALID",
        "Uploaded documents valid",
        "Documents",
        "Illustrative rule that no uploaded document is rejected, flagged or expired.",
        "derived.document_validity",
        ">=",
        Decimal("1"),
        None,
        Severity.HIGH,
        "ALL",
    ),
    (
        "DEMO-FEE-BAND",
        "Total annual fee band",
        "Finance",
        (
            "Illustrative fee band: total annual fee (tuition + development + other) "
            "must fall between the lower and upper cap."
        ),
        "finance.total_annual_fee",
        "BETWEEN",
        Decimal("20000"),
        Decimal("200000"),
        Severity.MEDIUM,
        "ALL",
    ),
)

COMPLIANCE_DEFAULT_CONFIG: dict[str, dict[str, float]] = {
    "severity_weights": {
        "CRITICAL": 25.0,
        "HIGH": 15.0,
        "MEDIUM": 8.0,
        "LOW": 4.0,
    },
    "rag_breakpoints": {
        "red_below": 70.0,
        "amber_below": 85.0,
    },
}
"""Illustrative scoring weights and status bands; editable from the admin screen."""


def _get_or_create_institution(
    db: Session,
    audit: AuditService,
    *,
    name: str,
    aicte_id: str,
    state: str,
    region: str,
    institution_type: str,
    established_year: int,
) -> tuple[Institution, bool]:
    institution = db.scalar(select(Institution).where(Institution.aicte_id == aicte_id))
    if institution is not None:
        return institution, False

    institution = Institution(
        name=name,
        aicte_id=aicte_id,
        state=state,
        region=region,
        type=institution_type,
        established_year=established_year,
        naac_grade=None,
        nba_status=None,
    )
    db.add(institution)
    db.flush()
    audit.log(
        None,
        "seed.institution.create",
        "Institution",
        institution.id,
        after={
            "name": institution.name,
            "aicte_id": institution.aicte_id,
            "state": institution.state,
            "region": institution.region,
            "type": institution.type,
        },
    )
    return institution, True


def _get_or_create_user(
    db: Session,
    audit: AuditService,
    *,
    name: str,
    email: str,
    password: str,
    role: Role,
    institution: Institution,
) -> tuple[User, bool]:
    normalised_email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == normalised_email))
    if user is not None:
        return user, False

    user = User(
        name=name,
        email=normalised_email,
        password_hash=hash_password(password),
        role=role,
        institution_id=institution.id,
        region=institution.region,
        is_active=True,
    )
    db.add(user)
    db.flush()
    audit.log(
        None,
        "seed.user.create",
        "User",
        user.id,
        after={
            "name": user.name,
            "email": user.email,
            "role": user.role.value,
            "institution_id": str(institution.id),
            "region": user.region,
        },
    )
    return user, True


def _get_or_create_application(
    db: Session,
    audit: AuditService,
    *,
    reference: str,
    institution: Institution,
    application_type: ApplicationType,
    status: ApplicationStatus,
    stage: WorkflowStage,
    assigned_officer: User | None,
    sla_days: int,
    submitted_days_ago: int = 0,
    decision_days_ago: int | None = None,
) -> tuple[Application, bool]:
    terminal = status in {
        ApplicationStatus.APPROVED,
        ApplicationStatus.CONDITIONALLY_APPROVED,
        ApplicationStatus.REJECTED,
    }
    application = db.scalar(
        select(Application).where(Application.data["reference"].astext == reference)
    )
    if application is not None:
        has_events = db.scalar(
            select(WorkflowEvent.id)
            .where(WorkflowEvent.application_id == application.id)
            .limit(1)
        )
        if has_events is None and application.data.get("demo"):
            # Keep the demo pipeline aligned with the current state machine.
            application.status = status
            application.current_stage = stage
            application.assigned_officer_id = (
                assigned_officer.id if assigned_officer else None
            )
            application.stage_entered_at = application.updated_at
            if terminal:
                application.sla_due_at = None
            elif application.sla_due_at is None:
                application.sla_due_at = application.submitted_at + timedelta(
                    days=sla_days
                )
            db.flush()
        if application.stage_entered_at is None:
            application.stage_entered_at = application.updated_at
        if (
            application.sla_due_at is None
            and application.status
            not in {
                ApplicationStatus.APPROVED,
                ApplicationStatus.CONDITIONALLY_APPROVED,
                ApplicationStatus.REJECTED,
            }
        ):
            previous_due = None
            application.sla_due_at = datetime.now(UTC) + timedelta(days=sla_days)
            audit.log(
                None,
                "seed.application.backfill_sla",
                "Application",
                application.id,
                before={"sla_due_at": previous_due},
                after={"sla_due_at": application.sla_due_at.isoformat()},
            )
            db.flush()
        return application, False

    now = datetime.now(UTC)
    submitted_at = now - timedelta(days=submitted_days_ago)
    application = Application(
        institution_id=institution.id,
        application_type=application_type,
        academic_year=DEMO_ACADEMIC_YEAR,
        status=status,
        current_stage=stage,
        assigned_officer_id=assigned_officer.id if assigned_officer else None,
        submitted_at=submitted_at,
        stage_entered_at=submitted_at,
        sla_due_at=None if terminal else submitted_at + timedelta(days=sla_days),
        data={"reference": reference, "demo": True},
        created_at=submitted_at,
    )
    if decision_days_ago is not None:
        application.updated_at = now - timedelta(days=decision_days_ago)
    db.add(application)
    db.flush()
    audit.log(
        None,
        "seed.application.create",
        "Application",
        application.id,
        after={
            "reference": reference,
            "institution_id": str(institution.id),
            "application_type": application.application_type.value,
            "status": application.status.value,
            "current_stage": application.current_stage.value,
        },
    )
    return application, True


def _get_or_create_inspection(
    db: Session,
    audit: AuditService,
    *,
    application: Application,
    committee_member: User,
) -> tuple[Inspection, bool]:
    inspection = db.scalar(
        select(Inspection).where(
            Inspection.application_id == application.id,
            Inspection.committee_id == committee_member.id,
        )
    )
    if inspection is not None:
        return inspection, False

    inspection = Inspection(
        application_id=application.id,
        committee_id=committee_member.id,
        scheduled_on=datetime.now(UTC) + timedelta(days=7),
        status=InspectionStatus.SCHEDULED,
    )
    db.add(inspection)
    db.flush()
    audit.log(
        None,
        "seed.inspection.create",
        "Inspection",
        inspection.id,
        after={
            "application_id": str(application.id),
            "committee_id": str(committee_member.id),
            "scheduled_on": inspection.scheduled_on.isoformat(),
        },
    )
    return inspection, True


def _ensure_required_documents(db: Session, audit: AuditService) -> int:
    """Create illustrative document rules without overwriting edits."""
    created = 0
    for application_type, rules in REQUIRED_DOCUMENTS.items():
        for doc_type, mandatory in rules:
            existing = db.scalar(
                select(RequiredDocument).where(
                    RequiredDocument.application_type == application_type,
                    RequiredDocument.doc_type == doc_type,
                )
            )
            if existing is not None:
                continue
            rule = RequiredDocument(
                application_type=application_type,
                doc_type=doc_type,
                mandatory=mandatory,
            )
            db.add(rule)
            db.flush()
            audit.log(
                None,
                "seed.required_document.create",
                "RequiredDocument",
                rule.id,
                after={
                    "application_type": application_type.value,
                    "doc_type": doc_type,
                    "mandatory": mandatory,
                },
            )
            created += 1
    return created


def _ensure_sla_configs(db: Session, audit: AuditService) -> int:
    """Create illustrative SLA durations without overwriting edits."""
    created = 0
    for stage, duration_days, escalation_after_days, escalate_to_role in SLA_CONFIGS:
        existing = db.scalar(select(SLAConfig).where(SLAConfig.stage == stage))
        if existing is not None:
            continue
        config = SLAConfig(
            stage=stage,
            duration_days=duration_days,
            escalation_after_days=escalation_after_days,
            escalate_to_role=escalate_to_role,
        )
        db.add(config)
        db.flush()
        audit.log(
            None,
            "seed.sla_config.create",
            "SLAConfig",
            config.id,
            after={
                "stage": stage.value,
                "duration_days": duration_days,
                "escalation_after_days": escalation_after_days,
                "escalate_to_role": escalate_to_role.value,
            },
        )
        created += 1
    return created


def _ensure_alert_rules(db: Session, audit: AuditService) -> int:
    """Create illustrative alert rules without overwriting administrator edits."""
    created = 0
    for (
        code,
        name,
        description,
        trigger,
        days_before,
        severity,
        channels,
        template,
        escalation_role,
    ) in ALERT_RULES:
        existing = db.scalar(select(AlertRule).where(AlertRule.code == code))
        if existing is not None:
            continue
        rule = AlertRule(
            code=code,
            name=name,
            description=description,
            trigger_type=trigger.value,
            days_before=days_before,
            severity=severity,
            channel_list=list(channels),
            template=template,
            escalation_role=escalation_role,
            is_active=True,
        )
        db.add(rule)
        db.flush()
        audit.log(
            None,
            "seed.alert_rule.create",
            "AlertRule",
            rule.id,
            after={
                "code": code,
                "trigger_type": trigger.value,
                "days_before": days_before,
                "severity": severity.value,
                "channel_list": list(channels),
                "escalation_role": escalation_role.value,
                "is_active": True,
            },
        )
        created += 1
    return created


def _ensure_compliance_rules(db: Session, audit: AuditService) -> int:
    """Create illustrative compliance rules without overwriting edits."""
    created = 0
    for (
        code,
        name,
        category,
        description,
        metric_key,
        operator,
        threshold,
        threshold_max,
        severity,
        applies_to,
    ) in COMPLIANCE_RULES:
        existing = db.scalar(select(ComplianceRule).where(ComplianceRule.code == code))
        if existing is not None:
            continue
        rule = ComplianceRule(
            code=code,
            name=name,
            category=category,
            description=description,
            metric_key=metric_key,
            operator=operator,
            threshold=threshold,
            threshold_max=threshold_max,
            severity=severity,
            applies_to=applies_to,
            is_active=True,
        )
        db.add(rule)
        db.flush()
        audit.log(
            None,
            "seed.compliance_rule.create",
            "ComplianceRule",
            rule.id,
            after={
                "code": code,
                "metric_key": metric_key,
                "operator": operator,
                "threshold": str(threshold),
                "threshold_max": str(threshold_max) if threshold_max else None,
                "severity": severity.value,
                "applies_to": applies_to,
            },
        )
        created += 1
    return created


def _ensure_compliance_config(db: Session, audit: AuditService) -> int:
    """Create the default scoring/rag configuration rows."""
    created = 0
    for key, value in COMPLIANCE_DEFAULT_CONFIG.items():
        existing = db.scalar(select(ComplianceConfig).where(ComplianceConfig.key == key))
        if existing is not None:
            continue
        config = ComplianceConfig(key=key, value=value)
        db.add(config)
        db.flush()
        audit.log(
            None,
            "seed.compliance_config.create",
            "ComplianceConfig",
            config.id,
            after={"key": key, "value": value},
        )
        created += 1
    return created


def _ensure_baseline_snapshots(db: Session) -> int:
    """Evaluate each institution once so trend charts start with data."""
    evaluated = 0
    institutions = db.scalars(select(Institution).order_by(Institution.aicte_id)).all()
    for institution in institutions:
        existing = db.scalar(
            select(ComplianceSnapshot.institution_id).where(
                ComplianceSnapshot.institution_id == institution.id
            )
        )
        if existing is not None:
            continue
        evaluate_institution(
            db,
            institution,
            evaluated_at=datetime.now(UTC),
            trigger="seed",
            commit=False,
        )
        evaluated += 1
    return evaluated


def seed() -> None:
    """Create demo records if they do not already exist."""
    settings = get_settings()
    configure_logging(settings.log_level)
    demo_password = settings.seed_demo_password.get_secret_value()
    admin_password = settings.seed_admin_password.get_secret_value()
    created = {
        "institutions": 0,
        "users": 0,
        "applications": 0,
        "inspections": 0,
        "required_documents": 0,
        "sla_configs": 0,
        "alert_rules": 0,
        "compliance_rules": 0,
        "compliance_config": 0,
        "compliance_snapshots": 0,
    }

    with SessionLocal() as db:
        audit = AuditService(db)

        west, made = _get_or_create_institution(
            db,
            audit,
            name="Sunrise Institute of Technology (Fictional Demo)",
            aicte_id=WEST_AICTE_ID,
            state="Maharashtra",
            region="West",
            institution_type="Engineering",
            established_year=2001,
        )
        created["institutions"] += int(made)

        south, made = _get_or_create_institution(
            db,
            audit,
            name="Riverbend Institute of Management (Fictional Demo)",
            aicte_id=SOUTH_AICTE_ID,
            state="Kerala",
            region="South",
            institution_type="Management",
            established_year=2005,
        )
        created["institutions"] += int(made)

        admin, made = _get_or_create_user(
            db,
            audit,
            name=settings.seed_admin_name,
            email=settings.seed_admin_email,
            password=admin_password,
            role=Role.SUPER_ADMIN,
            institution=west,
        )
        created["users"] += int(made)

        institution_admin, made = _get_or_create_user(
            db,
            audit,
            name="West Institution Administrator (Demo)",
            email="institution@example.edu",
            password=demo_password,
            role=Role.INSTITUTION_ADMIN,
            institution=west,
        )
        created["users"] += int(made)

        scrutiny_officer, made = _get_or_create_user(
            db,
            audit,
            name="West Scrutiny Officer (Demo)",
            email="scrutiny@example.edu",
            password=demo_password,
            role=Role.SCRUTINY_OFFICER,
            institution=west,
        )
        created["users"] += int(made)

        inspection_member, made = _get_or_create_user(
            db,
            audit,
            name="West Inspection Committee Member (Demo)",
            email="inspection@example.edu",
            password=demo_password,
            role=Role.INSPECTION_COMMITTEE,
            institution=west,
        )
        created["users"] += int(made)

        regional_head, made = _get_or_create_user(
            db,
            audit,
            name="West Regional Head (Demo)",
            email="regional@example.edu",
            password=demo_password,
            role=Role.REGIONAL_HEAD,
            institution=west,
        )
        created["users"] += int(made)

        _, made = _get_or_create_user(
            db,
            audit,
            name="South Institution Administrator (Demo)",
            email="institution.south@example.edu",
            password=demo_password,
            role=Role.INSTITUTION_ADMIN,
            institution=south,
        )
        created["users"] += int(made)

        west_application, made = _get_or_create_application(
            db,
            audit,
            reference=WEST_REFERENCE,
            institution=west,
            application_type=ApplicationType.NEW,
            status=ApplicationStatus.INSPECTION_SCHEDULED,
            stage=WorkflowStage.INSPECTION,
            assigned_officer=scrutiny_officer,
            sla_days=-2,
        )
        created["applications"] += int(made)

        _, made = _get_or_create_application(
            db,
            audit,
            reference=SOUTH_REFERENCE,
            institution=south,
            application_type=ApplicationType.EXTENSION,
            status=ApplicationStatus.SUBMITTED,
            stage=WorkflowStage.APPLICATION,
            assigned_officer=None,
            sla_days=14,
        )
        created["applications"] += int(made)

        _, made = _get_or_create_application(
            db,
            audit,
            reference="DEMO-WEST-2026-002",
            institution=west,
            application_type=ApplicationType.NEW,
            status=ApplicationStatus.APPROVED,
            stage=WorkflowStage.COMPLETED,
            assigned_officer=regional_head,
            sla_days=30,
            submitted_days_ago=28,
            decision_days_ago=9,
        )
        created["applications"] += int(made)

        # A dedicated pending case for the one-click +8 day alert demo. It is
        # due in seven days, so the replay produces T-7, T-3 and T-1 warnings,
        # then an SLA breach and escalation to the regional head.
        _, made = _get_or_create_application(
            db,
            audit,
            reference=DEMO_ALERT_REFERENCE,
            institution=west,
            application_type=ApplicationType.NEW,
            status=ApplicationStatus.SCRUTINY,
            stage=WorkflowStage.SCRUTINY,
            assigned_officer=scrutiny_officer,
            sla_days=7,
        )
        created["applications"] += int(made)

        _, made = _get_or_create_inspection(
            db,
            audit,
            application=west_application,
            committee_member=inspection_member,
        )
        created["inspections"] += int(made)

        created["required_documents"] += _ensure_required_documents(db, audit)
        created["sla_configs"] += _ensure_sla_configs(db, audit)
        created["alert_rules"] += _ensure_alert_rules(db, audit)
        created["compliance_rules"] += _ensure_compliance_rules(db, audit)
        created["compliance_config"] += _ensure_compliance_config(db, audit)
        created["compliance_snapshots"] += _ensure_baseline_snapshots(db)

        db.commit()

    logger.info(
        "seed completed",
        extra={
            "event": "seed_completed",
            "seed_created": created,
            "admin_email": admin.email,
            "demo_institution_admin": institution_admin.email,
        },
    )


if __name__ == "__main__":
    seed()
