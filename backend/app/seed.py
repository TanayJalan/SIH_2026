"""Idempotent development seed data.

Only clearly fictional data is created: two demo institutions, one account per
role, four applications and one inspection used to exercise role-scoped access
and the alert/escalation demo. Illustrative document rules, SLA durations,
alert rules and compliance rules are seeded as editable configuration; they are
not real AICTE norms or thresholds.
"""

import json
import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import (
    AcademicCalendarEvent,
    AlertRule,
    AlertTrigger,
    Application,
    ApplicationCategory,
    ApplicationProgram,
    ApplicationStatus,
    ApplicationTrack,
    ApplicationTypeRoute,
    ApprovedIntakeLedger,
    CalendarEventKey,
    ComplianceConfig,
    ComplianceRule,
    ComplianceSnapshot,
    DeadlineRule,
    DecisionType,
    Document,
    DocumentVerificationStatus,
    ExpertPool,
    Faculty,
    FacultyCadre,
    FeeSchedule,
    FeeUnit,
    Inspection,
    InspectionStatus,
    Institution,
    InstitutionClass,
    InstitutionRegion,
    InstitutionStatus,
    LandOwnership,
    Programme,
    ProgrammeStatus,
    PublicNotice,
    RequiredDocument,
    Role,
    SecurityDepositSchedule,
    Severity,
    SLAConfig,
    User,
    WorkflowDefinition,
    WorkflowEvent,
    WorkflowStage,
    WorkflowState,
    WorkflowTransition,
)
from app.services.audit import AuditService
from app.services.compliance import evaluate_institution
from app.services.portal_number import next_portal_application_no

logger = logging.getLogger("app.seed")

WEST_AICTE_ID = "DEMO-INST-0001"
SOUTH_AICTE_ID = "DEMO-INST-0002"
DEMO_ACADEMIC_YEAR = "2026-27"
WEST_REFERENCE = "DEMO-WEST-2026-001"
SOUTH_REFERENCE = "DEMO-SOUTH-2026-001"
DEMO_ALERT_REFERENCE = "DEMO-WEST-2026-003"

SEED_DIR = Path(__file__).resolve().parent.parent / "seeds" / "aph"
"""Generated APH configuration (``python scripts/seed_aph.py``)."""


def _load_seed(name: str) -> Any:
    """Load one generated APH seed file, failing loudly when it is missing."""
    path = SEED_DIR / name
    if not path.exists():
        raise RuntimeError(
            f"Missing APH seed file {path}. Run `python scripts/seed_aph.py` first."
        )
    return json.loads(path.read_text(encoding="utf-8"))


SLA_CONFIGS = (
    (WorkflowStage.APPLICATION, 30, 20, Role.REGIONAL_OFFICER),
    (WorkflowStage.DOCUMENT_VERIFICATION, 10, 7, Role.SCRUTINY_COMMITTEE_MEMBER),
    (WorkflowStage.SCRUTINY, 15, 10, Role.REGIONAL_OFFICER),
    (WorkflowStage.DEFICIENCY, 7, 5, Role.SCRUTINY_COMMITTEE_MEMBER),
    (WorkflowStage.INSPECTION, 20, 14, Role.REGIONAL_OFFICER),
    (WorkflowStage.COMMITTEE_REVIEW, 10, 7, Role.REGIONAL_OFFICER),
    (WorkflowStage.DECISION, 10, 7, Role.EXECUTIVE_COMMITTEE_MEMBER),
)

# Deadline rules are configuration, not constants. The appeal clock start event
# is configurable because APH does not fix it unambiguously (APH 1.11a); the
# Security Deposit ladder is quoted from APH 2.25f.
DEADLINE_RULES = (
    (
        "APPEAL_WINDOW",
        "DECISION_UPLOADED",
        7,
        Role.INSTITUTION_ADMIN,
        [],
        "APH 1.11a",
        True,
        False,
    ),
    (
        "SECURITY_DEPOSIT",
        "DECISION_UPLOADED",
        15,
        Role.INSTITUTION_ADMIN,
        [
            {"after_days": 15, "penalty_percent": 10, "until": "05-31"},
            {"after_days": 15, "penalty_percent": 20, "until": "07-31"},
            {"after_days": 15, "action": "WITHDRAWAL"},
        ],
        "APH 2.25f",
        False,
        False,
    ),
    (
        "ENROLMENT_UPLOAD",
        "ENROLMENT_UPLOAD_30NOV",
        0,
        Role.INSTITUTION_ADMIN,
        [],
        "APH 3.4",
        False,
        False,
    ),
    (
        "IC_REPORT",
        "IC_REPORT_30JUN",
        0,
        Role.EVC_MEMBER,
        [],
        "APH 1.9",
        False,
        False,
    ),
    (
        "CLOSURE_REVOKE",
        "CLOSURE_REVOKE_10APR",
        0,
        Role.REGIONAL_OFFICER,
        [],
        "APH 2.3.3h",
        False,
        True,
    ),
    (
        "SHOW_CAUSE_REPLY",
        "SHOW_CAUSE_ISSUED",
        15,
        Role.INSTITUTION_ADMIN,
        [],
        "APH 2.24",
        False,
        True,
    ),
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
        Role.REGIONAL_OFFICER,
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
        Role.REGIONAL_OFFICER,
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
        Role.REGIONAL_OFFICER,
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
        Role.REGIONAL_OFFICER,
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
        Role.REGIONAL_OFFICER,
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
        Role.REGIONAL_OFFICER,
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
        Role.REGIONAL_OFFICER,
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
        Role.REGIONAL_OFFICER,
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
        Role.REGIONAL_OFFICER,
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
        Role.REGIONAL_OFFICER,
    ),
    (
        "APPEAL-WINDOW-CLOSING",
        "Appeal window closing",
        "Warns the institution before the seven-day appeal window closes.",
        AlertTrigger.APPEAL_WINDOW_CLOSING,
        3,
        Severity.HIGH,
        ("IN_APP", "EMAIL"),
        (
            "The appeal window for {institution} (application "
            "{application_reference}) closes on {due_date}. {days_remaining} "
            "day(s) remain to file the single appeal."
        ),
        Role.REGIONAL_OFFICER,
    ),
    (
        "DEPOSIT-DUE-7",
        "Security Deposit due: 7 days",
        "Early warning for the Security Deposit and Affidavit 3.",
        AlertTrigger.DEPOSIT_DUE,
        7,
        Severity.MEDIUM,
        ("IN_APP", "EMAIL"),
        (
            "The Security Deposit and Affidavit 3 for {institution} "
            "(application {application_reference}) are due on {due_date}. "
            "{days_remaining} day(s) remain."
        ),
        Role.REGIONAL_OFFICER,
    ),
    (
        "DEPOSIT-DUE-1",
        "Security Deposit due: 1 day",
        "Final warning before the Security Deposit clock closes.",
        AlertTrigger.DEPOSIT_DUE,
        1,
        Severity.HIGH,
        ("IN_APP", "EMAIL"),
        (
            "The Security Deposit for {institution} (application "
            "{application_reference}) is due on {due_date}. Missing it "
            "attracts a penalty or withdrawal (APH 2.25f)."
        ),
        Role.REGIONAL_OFFICER,
    ),
)


# The compliance rule library and calculator norms are data files under
# ``seeds/aph`` so an administrator can edit every norm without a code change.
# Real rules carry an APH clause; the DEMO-* rows are project-only thresholds
# and are marked ``illustrative`` so the UI can badge them.

_seed_compliance_rules_cache: list[dict[str, Any]] | None = None


def _compliance_rule_rows() -> list[dict[str, Any]]:
    """Return the APH rule library from JSON (loaded once per process)."""
    global _seed_compliance_rules_cache
    if _seed_compliance_rules_cache is None:
        _seed_compliance_rules_cache = _load_seed("compliance_rules.json")
    return _seed_compliance_rules_cache


def _get_or_create_institution(
    db: Session,
    audit: AuditService,
    *,
    name: str,
    aicte_id: str,
    pid: str,
    state: str,
    region: str,
    aicte_region: InstitutionRegion,
    institution_class: InstitutionClass,
    institution_type: str,
    established_year: int,
    is_women_only: bool = False,
    is_pwbd: bool = False,
    in_jk_ladakh_ne: bool = False,
    affiliating_body: str | None = None,
    land_ownership: LandOwnership = LandOwnership.OWNED,
    lease_years_total: int | None = None,
    lease_years_live: int | None = None,
    building_leased: bool = False,
    last_eoa_year: str | None = None,
    accreditation: dict[str, Any] | None = None,
    infra_profile: dict[str, Any] | None = None,
    library_profile: dict[str, Any] | None = None,
    computing_profile: dict[str, Any] | None = None,
    essential_requirements: dict[str, Any] | None = None,
    campus: dict[str, Any] | None = None,
) -> tuple[Institution, bool]:
    institution = db.scalar(select(Institution).where(Institution.aicte_id == aicte_id))
    if institution is not None:
        # Backfill profile keys added by later APH releases without overwriting
        # anything the institution has already answered. This keeps an existing
        # demo database usable after a seed change.
        changed = False
        for field_name, values in (
            ("accreditation", accreditation),
            ("infra_profile", infra_profile),
            ("library_profile", library_profile),
            ("computing_profile", computing_profile),
            ("essential_requirements", essential_requirements),
            ("campus", campus),
        ):
            if not values:
                continue
            current = dict(getattr(institution, field_name) or {})
            missing = {
                key: value for key, value in values.items() if key not in current
            }
            if missing:
                setattr(institution, field_name, {**current, **missing})
                changed = True
        if changed:
            db.flush()
            audit.log(
                None,
                "seed.institution.backfill_profiles",
                "Institution",
                institution.id,
                after={"aicte_id": aicte_id},
            )
        return institution, False

    institution = Institution(
        name=name,
        aicte_id=aicte_id,
        pid=pid,
        state=state,
        region=region,
        aicte_region=aicte_region,
        institution_class=institution_class,
        type=institution_type,
        institution_type=institution_type,
        is_women_only=is_women_only,
        is_pwbd=is_pwbd,
        in_jk_ladakh_ne=in_jk_ladakh_ne,
        affiliating_body=affiliating_body,
        land_ownership=land_ownership,
        lease_years_total=lease_years_total,
        lease_years_live=lease_years_live,
        building_leased=building_leased,
        status=InstitutionStatus.ACTIVE,
        last_eoa_year=last_eoa_year,
        established_year=established_year,
        naac_grade=None,
        nba_status=None,
        accreditation=accreditation or {},
        infra_profile=infra_profile or {},
        library_profile=library_profile or {},
        computing_profile=computing_profile or {},
        essential_requirements=essential_requirements or {},
        campus=campus or {},
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
            "pid": institution.pid,
            "state": institution.state,
            "region": institution.region,
            "aicte_region": institution.aicte_region.value,
            "institution_class": institution.institution_class.value,
            "institution_type": institution.institution_type,
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
    institution: Institution | None,
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
        institution_id=institution.id if institution else None,
        region=institution.region if institution else None,
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
            "institution_id": str(institution.id) if institution else None,
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
    application_type: str,
    track: ApplicationTrack,
    status: ApplicationStatus,
    stage: WorkflowStage,
    assigned_officer: User | None,
    sla_days: int,
    submitted_days_ago: int = 0,
    decision_days_ago: int | None = None,
    decision: DecisionType | None = None,
) -> tuple[Application, bool]:
    terminal = status in {
        ApplicationStatus.ACTIVE_LOA,
        ApplicationStatus.ACTIVE_EOA,
        ApplicationStatus.FINAL_LOA,
        ApplicationStatus.FINAL_LOD,
        ApplicationStatus.FINAL_LOR,
        ApplicationStatus.CANCELLED,
        ApplicationStatus.CLOSED,
        ApplicationStatus.WITHDRAWN,
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
                ApplicationStatus.ACTIVE_LOA,
                ApplicationStatus.ACTIVE_EOA,
                ApplicationStatus.FINAL_LOA,
                ApplicationStatus.FINAL_LOD,
                ApplicationStatus.FINAL_LOR,
                ApplicationStatus.CANCELLED,
                ApplicationStatus.CLOSED,
                ApplicationStatus.WITHDRAWN,
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

    route = db.scalar(
        select(ApplicationTypeRoute).where(ApplicationTypeRoute.type == application_type)
    )
    category = route.category if route is not None else ApplicationCategory.CAT1_CUTOFF
    notice = db.scalar(
        select(PublicNotice).where(
            PublicNotice.academic_year == DEMO_ACADEMIC_YEAR,
            PublicNotice.category == category,
        )
    )

    now = datetime.now(UTC)
    submitted_at = now - timedelta(days=submitted_days_ago)
    decision_uploaded_at = (
        now - timedelta(days=decision_days_ago) if decision_days_ago is not None else None
    )
    application = Application(
        institution_id=institution.id,
        track=track,
        application_type=application_type,
        category=category,
        public_notice_id=notice.id if notice is not None else None,
        portal_application_no=next_portal_application_no(db, DEMO_ACADEMIC_YEAR),
        academic_year=DEMO_ACADEMIC_YEAR,
        status=status,
        current_stage=stage,
        assigned_officer_id=assigned_officer.id if assigned_officer else None,
        submitted_at=submitted_at,
        locked_at=submitted_at,
        stage_entered_at=submitted_at,
        sla_due_at=None if terminal else submitted_at + timedelta(days=sla_days),
        decision_type=decision,
        decision_uploaded_at=decision_uploaded_at,
        appeal_deadline=(
            decision_uploaded_at + timedelta(days=7)
            if decision_uploaded_at is not None
            else None
        ),
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
            "application_type": application.application_type,
            "track": application.track.value,
            "category": application.category.value,
            "portal_application_no": application.portal_application_no,
            "status": application.status.value,
            "current_stage": application.current_stage.value,
        },
    )
    return application, True


DEMO_FACULTY_APH_CLAUSE = "APH 7.1"


def _ensure_programmes(
    db: Session,
    audit: AuditService,
    *,
    institution: Institution,
    programmes: list[dict[str, Any]],
) -> tuple[list[Programme], int]:
    """Create the approved programmes used by the compliance calculators."""
    created = 0
    rows: list[Programme] = []
    for spec in programmes:
        programme = db.scalar(
            select(Programme).where(
                Programme.institution_id == institution.id,
                Programme.course_name == spec["course_name"],
                Programme.level == spec["level"],
            )
        )
        if programme is None:
            programme = Programme(
                institution_id=institution.id,
                programme_family=spec["programme_family"],
                level=spec["level"],
                course_name=spec["course_name"],
                is_core=bool(spec.get("is_core", True)),
                duration_years=Decimal(str(spec["duration_years"])),
                approved_intake=int(spec["approved_intake"]),
                divisions=int(spec.get("divisions", 1)),
                status=ProgrammeStatus.ACTIVE,
                apH_clause=spec.get("apH_clause", "APH 6.1"),
                needs_verification=False,
            )
            db.add(programme)
            db.flush()
            audit.log(
                None,
                "seed.programme.create",
                "Programme",
                programme.id,
                after={
                    "institution_id": str(institution.id),
                    "course_name": programme.course_name,
                    "level": programme.level,
                    "approved_intake": programme.approved_intake,
                },
            )
            created += 1
        rows.append(programme)
    return rows, created


def _ensure_faculty(
    db: Session,
    audit: AuditService,
    *,
    institution: Institution,
    members: list[dict[str, Any]],
) -> int:
    """Create the demo faculty roster, idempotent on the portal faculty ID."""
    created = 0
    for member in members:
        existing = db.scalar(
            select(Faculty).where(
                Faculty.institution_id == institution.id,
                Faculty.portal_faculty_id == member["portal_faculty_id"],
            )
        )
        if existing is not None:
            continue
        faculty = Faculty(
            institution_id=institution.id,
            programme_id=member.get("programme_id"),
            name=member["name"],
            portal_faculty_id=member["portal_faculty_id"],
            cadre=FacultyCadre(member["cadre"]),
            qualification=member.get("qualification"),
            has_phd=bool(member.get("has_phd", False)),
            regular=bool(member.get("regular", True)),
            joined_on=member.get("joined_on", date(2019, 7, 1)),
            portal_updated_on=member.get("portal_updated_on", date(2019, 7, 1)),
            biometric=bool(member.get("biometric", True)),
            salary_via_ecs=bool(member.get("salary_via_ecs", True)),
            apH_clause=DEMO_FACULTY_APH_CLAUSE,
            needs_verification=False,
        )
        db.add(faculty)
        db.flush()
        audit.log(
            None,
            "seed.faculty.create",
            "Faculty",
            faculty.id,
            after={
                "institution_id": str(institution.id),
                "name": faculty.name,
                "cadre": faculty.cadre.value,
                "has_phd": faculty.has_phd,
            },
        )
        created += 1
    if created:
        db.flush()
    return created


def _ensure_intake_ledger(
    db: Session,
    audit: AuditService,
    *,
    programme: Programme,
    rows: list[dict[str, Any]],
) -> int:
    """Create the per-year approved/admitted seat history for one programme."""
    created = 0
    for row in rows:
        existing = db.scalar(
            select(ApprovedIntakeLedger).where(
                ApprovedIntakeLedger.programme_id == programme.id,
                ApprovedIntakeLedger.academic_year == row["academic_year"],
            )
        )
        if existing is not None:
            continue
        ledger = ApprovedIntakeLedger(
            programme_id=programme.id,
            academic_year=row["academic_year"],
            approved_intake=int(row["approved_intake"]),
            admitted_total=int(row["admitted_total"]),
            apH_clause="APH 2.25b",
            needs_verification=False,
        )
        db.add(ledger)
        db.flush()
        audit.log(
            None,
            "seed.intake_ledger.create",
            "ApprovedIntakeLedger",
            ledger.id,
            after={
                "programme_id": str(programme.id),
                "academic_year": ledger.academic_year,
                "approved_intake": ledger.approved_intake,
                "admitted_total": ledger.admitted_total,
            },
        )
        created += 1
    if created:
        db.flush()
    return created


def _ensure_application_programmes(
    db: Session,
    audit: AuditService,
    *,
    application: Application,
    programmes: list[dict[str, Any]],
) -> int:
    """Create the programme rows requested by one application."""
    created = 0
    for spec in programmes:
        existing = db.scalar(
            select(ApplicationProgram).where(
                ApplicationProgram.application_id == application.id,
                ApplicationProgram.program_name == spec["program_name"],
                ApplicationProgram.level == spec["level"],
            )
        )
        if existing is not None:
            continue
        row = ApplicationProgram(
            application_id=application.id,
            program_name=spec["program_name"],
            level=spec["level"],
            intake=int(spec["intake"]),
            faculty_count=int(spec.get("faculty_count", 0)),
            lab_count=int(spec.get("lab_count", 0)),
        )
        db.add(row)
        db.flush()
        audit.log(
            None,
            "seed.application_program.create",
            "ApplicationProgram",
            row.id,
            after={
                "application_id": str(application.id),
                "program_name": row.program_name,
                "level": row.level,
                "intake": row.intake,
            },
        )
        created += 1
    if created:
        db.flush()
    return created


def _ensure_documents(
    db: Session,
    audit: AuditService,
    *,
    application: Application,
    documents: list[dict[str, Any]],
    uploaded_by: User,
) -> int:
    """Create demo uploads so the document rules have something to assess."""
    created = 0
    for spec in documents:
        existing = db.scalar(
            select(Document).where(
                Document.application_id == application.id,
                Document.doc_type == spec["doc_type"],
                Document.version == 1,
            )
        )
        if existing is not None:
            continue
        document = Document(
            application_id=application.id,
            doc_type=spec["doc_type"],
            doc_code=spec.get("doc_code", spec["doc_type"]),
            signed_with_dsc=bool(spec.get("signed_with_dsc", True)),
            valid_until=spec.get("valid_until"),
            affidavit_no=spec.get("affidavit_no"),
            filename=spec.get("filename", f"{spec['doc_type'].lower()}.pdf"),
            content_type="application/pdf",
            size_bytes=int(spec.get("size_bytes", 120_000)),
            storage_path=f"demo/{application.id}/{spec['doc_type'].lower()}.pdf",
            uploaded_by=uploaded_by.id,
            verification_status=DocumentVerificationStatus(
                spec.get("verification_status", "VERIFIED")
            ),
            version=1,
        )
        db.add(document)
        db.flush()
        audit.log(
            None,
            "seed.document.create",
            "Document",
            document.id,
            after={
                "application_id": str(application.id),
                "doc_type": document.doc_type,
                "doc_code": document.doc_code,
                "valid_until": document.valid_until.isoformat()
                if document.valid_until
                else None,
            },
        )
        created += 1
    if created:
        db.flush()
    return created


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


def _ensure_application_type_routes(db: Session, audit: AuditService) -> int:
    """Load the Table 2.3 routing rows without overwriting administrator edits."""
    created = 0
    for row in _load_seed("application_type_routes.json"):
        existing = db.scalar(
            select(ApplicationTypeRoute).where(ApplicationTypeRoute.type == row["type"])
        )
        if existing is not None:
            # Backfill the workflow assignment introduced by the data-driven
            # engine. The routing flags themselves are never overwritten.
            if existing.workflow_key is None:
                existing.workflow_key = row.get("workflow_key")
            if not existing.not_implemented:
                existing.not_implemented = row.get("not_implemented", False)
                existing.not_implemented_note = row.get("not_implemented_note")
            continue
        route = ApplicationTypeRoute(
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
            not_implemented=row.get("not_implemented", False),
            not_implemented_note=row.get("not_implemented_note"),
            apH_clause=row["apH_clause"],
            needs_verification=row["needs_verification"],
        )
        db.add(route)
        db.flush()
        audit.log(
            None,
            "seed.application_type_route.create",
            "ApplicationTypeRoute",
            route.id,
            after={
                "type": route.type,
                "category": route.category.value,
                "apH_clause": route.apH_clause,
                "needs_verification": route.needs_verification,
            },
        )
        created += 1
    return created


def _ensure_fee_schedules(db: Session, audit: AuditService) -> int:
    """Load the APH TER table as integer paise without overwriting edits."""
    created = 0
    for row in _load_seed("fee_schedules.json"):
        institution_class = (
            InstitutionClass(row["institution_class"])
            if row["institution_class"] is not None
            else None
        )
        existing = db.scalar(
            select(FeeSchedule).where(
                FeeSchedule.item_code == row["item_code"],
                FeeSchedule.institution_class == institution_class,
                FeeSchedule.base_academic_year == DEMO_ACADEMIC_YEAR,
            )
        )
        if existing is not None:
            continue
        schedule = FeeSchedule(
            item_code=row["item_code"],
            label=row["label"],
            description=row["description"],
            institution_class=institution_class,
            unit=FeeUnit(row["unit"]),
            amount_paise=row["amount_paise"],
            base_academic_year=DEMO_ACADEMIC_YEAR,
            annual_increase_pct=Decimal("10"),
            apH_clause=row["apH_clause"],
            needs_verification=row.get("needs_verification", False),
        )
        db.add(schedule)
        db.flush()
        audit.log(
            None,
            "seed.fee_schedule.create",
            "FeeSchedule",
            schedule.id,
            after={
                "item_code": schedule.item_code,
                "institution_class": (
                    schedule.institution_class.value if schedule.institution_class else None
                ),
                "amount_paise": schedule.amount_paise,
                "apH_clause": schedule.apH_clause,
            },
        )
        created += 1
    return created


def _ensure_security_deposit_schedules(db: Session, audit: AuditService) -> int:
    """Load the Table 1.4 Security Deposit rates without overwriting edits."""
    created = 0
    for row in _load_seed("security_deposit_schedules.json"):
        existing = db.scalar(
            select(SecurityDepositSchedule).where(
                SecurityDepositSchedule.programme_family == row["programme_family"],
                SecurityDepositSchedule.level == row["level"],
            )
        )
        if existing is not None:
            continue
        schedule = SecurityDepositSchedule(
            programme_family=row["programme_family"],
            level=row["level"],
            amount_paise=row["amount_paise"],
            doubled_for_leased=row["doubled_for_leased"],
            apH_clause=row["apH_clause"],
            needs_verification=row.get("needs_verification", False),
        )
        db.add(schedule)
        db.flush()
        audit.log(
            None,
            "seed.security_deposit_schedule.create",
            "SecurityDepositSchedule",
            schedule.id,
            after={
                "programme_family": schedule.programme_family,
                "level": schedule.level,
                "amount_paise": schedule.amount_paise,
                "apH_clause": schedule.apH_clause,
            },
        )
        created += 1
    return created


def _ensure_required_documents(db: Session, audit: AuditService) -> int:
    """Load the Annexure-2 document catalogue without overwriting edits."""
    created = 0
    for row in _load_seed("required_documents.json"):
        existing = db.scalar(
            select(RequiredDocument).where(
                RequiredDocument.application_type == row["application_type"],
                RequiredDocument.doc_type == row["doc_type"],
            )
        )
        if existing is not None:
            continue
        rule = RequiredDocument(
            application_type=row["application_type"],
            doc_type=row["doc_type"],
            doc_code=row["doc_code"],
            mandatory=row["mandatory"],
            condition_expr=row["condition_expr"],
            apH_clause=row["apH_clause"],
        )
        db.add(rule)
        db.flush()
        audit.log(
            None,
            "seed.required_document.create",
            "RequiredDocument",
            rule.id,
            after={
                "application_type": rule.application_type,
                "doc_type": rule.doc_type,
                "doc_code": rule.doc_code,
                "mandatory": rule.mandatory,
                "apH_clause": rule.apH_clause,
            },
        )
        created += 1
    return created


def _ensure_public_notices(db: Session, audit: AuditService) -> int:
    """Load the demo Public Notice windows; dates are labelled DEMO."""
    created = 0
    for row in _load_seed("public_notices.json"):
        category = ApplicationCategory(row["category"])
        existing = db.scalar(
            select(PublicNotice).where(
                PublicNotice.academic_year == row["academic_year"],
                PublicNotice.category == category,
            )
        )
        if existing is not None:
            continue
        notice = PublicNotice(
            academic_year=row["academic_year"],
            category=category,
            opens_on=date.fromisoformat(row["opens_on"]),
            cutoff_on=date.fromisoformat(row["cutoff_on"]),
            apH_clause=row["apH_clause"],
            needs_verification=row["needs_verification"],
            is_demo=row["is_demo"],
            note=row["note"],
        )
        db.add(notice)
        db.flush()
        audit.log(
            None,
            "seed.public_notice.create",
            "PublicNotice",
            notice.id,
            after={
                "academic_year": notice.academic_year,
                "category": notice.category.value,
                "cutoff_on": notice.cutoff_on.isoformat(),
                "is_demo": notice.is_demo,
            },
        )
        created += 1
    return created


def _ensure_academic_calendar_events(db: Session, audit: AuditService) -> int:
    """Load the demo Academic Calendar dates; every row is labelled DEMO."""
    created = 0
    for row in _load_seed("academic_calendar_events.json"):
        existing = db.scalar(
            select(AcademicCalendarEvent).where(
                AcademicCalendarEvent.academic_year == row["academic_year"],
                AcademicCalendarEvent.event_key == row["event_key"],
            )
        )
        if existing is not None:
            continue
        event = AcademicCalendarEvent(
            academic_year=row["academic_year"],
            event_key=CalendarEventKey(row["event_key"]),
            date=date.fromisoformat(row["date"]),
            description=row["description"],
            apH_clause=row["apH_clause"],
            needs_verification=row["needs_verification"],
            is_demo=row["is_demo"],
        )
        db.add(event)
        db.flush()
        audit.log(
            None,
            "seed.academic_calendar_event.create",
            "AcademicCalendarEvent",
            event.id,
            after={
                "academic_year": event.academic_year,
                "event_key": event.event_key.value,
                "date": event.date.isoformat(),
                "is_demo": event.is_demo,
            },
        )
        created += 1
    return created


def _ensure_committee_compositions(db: Session, audit: AuditService) -> int:
    """Store the Annexure-16 compositions as editable configuration."""
    existing = db.scalar(
        select(ComplianceConfig).where(ComplianceConfig.key == "committee_compositions")
    )
    if existing is not None:
        return 0
    config = ComplianceConfig(
        key="committee_compositions",
        value=_load_seed("committee_compositions.json"),
    )
    db.add(config)
    db.flush()
    audit.log(
        None,
        "seed.committee_compositions.create",
        "ComplianceConfig",
        config.id,
        after={"key": config.key},
    )
    return 1


def _ensure_workflow_definitions(db: Session, audit: AuditService) -> int:
    """Load the APH workflow definitions, states and transitions as data."""
    created = 0
    for row in _load_seed("workflow_definitions.json"):
        existing = db.scalar(
            select(WorkflowDefinition).where(WorkflowDefinition.key == row["key"])
        )
        if existing is not None:
            continue
        definition = WorkflowDefinition(
            key=row["key"],
            label=row["label"],
            track=row["track"],
            description=row["description"],
            is_active=row["is_active"],
            config=row.get("config", {}),
            apH_clause=row["apH_clause"],
            needs_verification=row["needs_verification"],
        )
        db.add(definition)
        db.flush()
        for state_row in row["states"]:
            db.add(
                WorkflowState(
                    definition_id=definition.id,
                    code=ApplicationStatus(state_row["code"]),
                    label=state_row["label"],
                    stage=WorkflowStage(state_row["stage"]),
                    is_initial=state_row["is_initial"],
                    is_terminal=state_row["is_terminal"],
                    sort_order=state_row["sort_order"],
                    description=state_row["description"],
                    apH_clause=state_row["apH_clause"],
                    needs_verification=state_row["needs_verification"],
                )
            )
        for transition_row in row["transitions"]:
            db.add(
                WorkflowTransition(
                    definition_id=definition.id,
                    from_state=ApplicationStatus(transition_row["from_state"]),
                    to_state=ApplicationStatus(transition_row["to_state"]),
                    action=transition_row["action"],
                    label=transition_row["label"],
                    description=transition_row["description"],
                    allowed_roles=list(transition_row["allowed_roles"]),
                    guard_expr=list(transition_row["guard_expr"]),
                    side_effects=list(transition_row["side_effects"]),
                    requires=transition_row["requires"],
                    tone=transition_row["tone"],
                    sla_stage=(
                        WorkflowStage(transition_row["sla_stage"])
                        if transition_row.get("sla_stage")
                        else None
                    ),
                    priority=transition_row["priority"],
                    apH_clause=transition_row["apH_clause"],
                    needs_verification=transition_row["needs_verification"],
                )
            )
        db.flush()
        audit.log(
            None,
            "seed.workflow_definition.create",
            "WorkflowDefinition",
            definition.id,
            after={
                "key": definition.key,
                "track": definition.track,
                "states": len(row["states"]),
                "transitions": len(row["transitions"]),
            },
        )
        created += 1
    return created


def _ensure_aph_reference_data(db: Session, audit: AuditService) -> dict[str, int]:
    """Load every generated APH seed file in dependency order."""
    return {
        "deadline_rules": _ensure_deadline_rules(db, audit),
        "workflow_definitions": _ensure_workflow_definitions(db, audit),
        "application_type_routes": _ensure_application_type_routes(db, audit),
        "fee_schedules": _ensure_fee_schedules(db, audit),
        "required_documents": _ensure_required_documents(db, audit),
        "security_deposit_schedules": _ensure_security_deposit_schedules(db, audit),
        "public_notices": _ensure_public_notices(db, audit),
        "academic_calendar_events": _ensure_academic_calendar_events(db, audit),
        "committee_compositions": _ensure_committee_compositions(db, audit),
    }


def _ensure_deadline_rules(db: Session, audit: AuditService) -> int:
    """Create the appeal and Security Deposit clocks without overwriting edits."""
    created = 0
    for (
        code,
        start_event,
        duration_days,
        owner_role,
        penalty_ladder,
        apH_clause,
        start_event_configurable,
        needs_verification,
    ) in DEADLINE_RULES:
        existing = db.scalar(select(DeadlineRule).where(DeadlineRule.code == code))
        if existing is not None:
            continue
        rule = DeadlineRule(
            code=code,
            start_event=start_event,
            duration_days=duration_days,
            owner_role=owner_role,
            penalty_ladder=list(penalty_ladder),
            apH_clause=apH_clause,
            start_event_configurable=start_event_configurable,
            needs_verification=needs_verification,
        )
        db.add(rule)
        db.flush()
        audit.log(
            None,
            "seed.deadline_rule.create",
            "DeadlineRule",
            rule.id,
            after={
                "code": rule.code,
                "start_event": rule.start_event,
                "duration_days": rule.duration_days,
                "apH_clause": rule.apH_clause,
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
            apH_clause="DEMO",
            needs_verification=True,
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
                "apH_clause": "DEMO",
                "needs_verification": True,
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
            apH_clause="DEMO",
            needs_verification=True,
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
    """Create the APH compliance rule library without overwriting edits.

    Real rules carry an APH clause and default to ``mandatory``. The ``DEMO-*``
    rows are project-only thresholds: they are seeded with
    ``illustrative=True, mandatory=False`` so they can never turn a clean
    institution into a deficiency.
    """
    created = 0
    for row in _compliance_rule_rows():
        code = str(row["code"])
        existing = db.scalar(select(ComplianceRule).where(ComplianceRule.code == code))
        if existing is not None:
            continue
        rule = ComplianceRule(
            code=code,
            name=str(row["name"]),
            category=str(row["category"]),
            description=str(row["description"]),
            metric_key=str(row["metric_key"]),
            operator=str(row["operator"]),
            threshold=Decimal(str(row["threshold"])),
            threshold_max=(
                Decimal(str(row["threshold_max"]))
                if row.get("threshold_max") is not None
                else None
            ),
            severity=Severity(str(row["severity"])),
            applies_to=str(row.get("applies_to", "ALL")),
            applies_to_family=row.get("applies_to_family"),
            applies_to_level=row.get("applies_to_level"),
            apH_clause=str(row.get("apH_clause", "DEMO")),
            needs_verification=bool(row.get("needs_verification", False)),
            mandatory=bool(row.get("mandatory", True)),
            illustrative=bool(row.get("illustrative", False)),
            weight=(
                Decimal(str(row["weight"])) if row.get("weight") is not None else None
            ),
            unit=row.get("unit"),
            explanation_template=row.get("explanation_template"),
            metric_params=dict(row.get("metric_params") or {}),
            penalty_codes=list(row.get("penalty_codes") or []),
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
                "metric_key": rule.metric_key,
                "operator": rule.operator,
                "threshold": str(rule.threshold),
                "severity": rule.severity.value,
                "apH_clause": rule.apH_clause,
                "mandatory": rule.mandatory,
                "illustrative": rule.illustrative,
            },
        )
        created += 1
    return created


def _ensure_compliance_config(db: Session, audit: AuditService) -> int:
    """Create the editable scoring and calculator norms from JSON."""
    created = 0
    config_rows: dict[str, Any] = _load_seed("compliance_config.json")
    for key, value in config_rows.items():
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


_FICTIONAL_EXPERTS: list[dict[str, Any]] = [
    # 1. Academic Members (IIT / NIT / Govt)
    {
        "name": "Prof. Rajeshwar K. Sharma (Fictional)",
        "designation": "Professor, Mechanical Engineering",
        "institution_name": "IIT Bombay",
        "state": "Maharashtra",
        "aicte_region": "Western",
        "email": "rajeshwar.sharma.fictional@aicte.gov.in",
        "seat_tags": ["ACADEMIC", "CHAIR_SHC"],
        "years_experience": 18,
        "is_retired_hc_judge": False,
    },
    {
        "name": "Prof. Sundaram Meenakshi (Fictional)",
        "designation": "Professor, Computer Science & Engineering",
        "institution_name": "IIT Madras",
        "state": "Tamil Nadu",
        "aicte_region": "Southern",
        "email": "sundaram.meenakshi.fictional@aicte.gov.in",
        "seat_tags": ["ACADEMIC"],
        "years_experience": 15,
        "is_retired_hc_judge": False,
    },
    {
        "name": "Prof. Anirban Sengupta (Fictional)",
        "designation": "Professor, Civil & Structural Engineering",
        "institution_name": "IIT Kharagpur",
        "state": "West Bengal",
        "aicte_region": "Eastern",
        "email": "anirban.sengupta.fictional@aicte.gov.in",
        "seat_tags": ["ACADEMIC", "ARCHITECT"],
        "years_experience": 20,
        "is_retired_hc_judge": False,
    },
    {
        "name": "Prof. Harpreet Singh Dhillon (Fictional)",
        "designation": "Professor, Electrical Engineering",
        "institution_name": "IIT Ropar",
        "state": "Punjab",
        "aicte_region": "North-Western",
        "email": "harpreet.dhillon.fictional@aicte.gov.in",
        "seat_tags": ["ACADEMIC"],
        "years_experience": 12,
        "is_retired_hc_judge": False,
    },
    {
        "name": "Prof. Vandana Kulkarni (Fictional)",
        "designation": "Associate Professor, Electronics & Telecomm",
        "institution_name": "VNIT Nagpur",
        "state": "Maharashtra",
        "aicte_region": "Western",
        "email": "vandana.kulkarni.fictional@aicte.gov.in",
        "seat_tags": ["ACADEMIC"],
        "years_experience": 9,
        "is_retired_hc_judge": False,
    },
    {
        "name": "Prof. Ramesh C. Tiwari (Fictional)",
        "designation": "Professor, Management Studies",
        "institution_name": "IIM Lucknow",
        "state": "Uttar Pradesh",
        "aicte_region": "Northern",
        "email": "ramesh.tiwari.fictional@aicte.gov.in",
        "seat_tags": ["ACADEMIC", "CHAIR_SHC"],
        "years_experience": 16,
        "is_retired_hc_judge": False,
    },
    {
        "name": "Prof. Deepa Narayanan (Fictional)",
        "designation": "Associate Professor, Information Technology",
        "institution_name": "NIT Calicut",
        "state": "Kerala",
        "aicte_region": "South-Western",
        "email": "deepa.narayanan.fictional@aicte.gov.in",
        "seat_tags": ["ACADEMIC"],
        "years_experience": 8,
        "is_retired_hc_judge": False,
    },
    {
        "name": "Prof. Arvind K. Patel (Fictional)",
        "designation": "Professor, Chemical Engineering",
        "institution_name": "SVNIT Surat",
        "state": "Gujarat",
        "aicte_region": "Central",
        "email": "arvind.patel.fictional@aicte.gov.in",
        "seat_tags": ["ACADEMIC"],
        "years_experience": 14,
        "is_retired_hc_judge": False,
    },
    {
        "name": "Prof. Jayashree Srinivas (Fictional)",
        "designation": "Professor, Structural Engineering",
        "institution_name": "IISc Bangalore",
        "state": "Karnataka",
        "aicte_region": "South-Western",
        "email": "jayashree.srinivas.fictional@aicte.gov.in",
        "seat_tags": ["ACADEMIC", "ARCHITECT"],
        "years_experience": 22,
        "is_retired_hc_judge": False,
    },
    {
        "name": "Prof. Birendra Nath Roy (Fictional)",
        "designation": "Associate Professor, Computer Science",
        "institution_name": "NIT Rourkela",
        "state": "Odisha",
        "aicte_region": "Eastern",
        "email": "birendra.roy.fictional@aicte.gov.in",
        "seat_tags": ["ACADEMIC"],
        "years_experience": 7,
        "is_retired_hc_judge": False,
    },
    # 2. Advocates (Bar Council Registered)
    {
        "name": "Adv. Meenakshi Ramanathan (Fictional)",
        "designation": "Senior Advocate",
        "institution_name": "Bar Council of Tamil Nadu & Puducherry",
        "state": "Tamil Nadu",
        "aicte_region": "Southern",
        "email": "adv.meenakshi.fictional@aicte.gov.in",
        "seat_tags": ["ADVOCATE"],
        "years_experience": 14,
        "is_retired_hc_judge": False,
    },
    {
        "name": "Adv. Siddharth K. Deshmukh (Fictional)",
        "designation": "Advocate",
        "institution_name": "Bar Council of Maharashtra & Goa",
        "state": "Maharashtra",
        "aicte_region": "Western",
        "email": "adv.deshmukh.fictional@aicte.gov.in",
        "seat_tags": ["ADVOCATE"],
        "years_experience": 11,
        "is_retired_hc_judge": False,
    },
    {
        "name": "Adv. Pradeep K. Verma (Fictional)",
        "designation": "Senior Advocate",
        "institution_name": "Bar Council of Uttar Pradesh",
        "state": "Uttar Pradesh",
        "aicte_region": "Northern",
        "email": "adv.pradeep.fictional@aicte.gov.in",
        "seat_tags": ["ADVOCATE"],
        "years_experience": 16,
        "is_retired_hc_judge": False,
    },
    {
        "name": "Adv. Sangeeta Rao (Fictional)",
        "designation": "Advocate",
        "institution_name": "Karnataka State Bar Council",
        "state": "Karnataka",
        "aicte_region": "South-Western",
        "email": "adv.sangeeta.fictional@aicte.gov.in",
        "seat_tags": ["ADVOCATE"],
        "years_experience": 8,
        "is_retired_hc_judge": False,
    },
    {
        "name": "Adv. Vikramaditya Sen (Fictional)",
        "designation": "Advocate",
        "institution_name": "Bar Council of West Bengal",
        "state": "West Bengal",
        "aicte_region": "Eastern",
        "email": "adv.vikram.fictional@aicte.gov.in",
        "seat_tags": ["ADVOCATE"],
        "years_experience": 12,
        "is_retired_hc_judge": False,
    },
    # 3. Architects / Structural / Planning Experts (Council of Architecture / CPWD)
    {
        "name": "Ar. Nitin G. Gokhale (Fictional)",
        "designation": "Senior Architect (CoA Registered)",
        "institution_name": "Gokhale Urban Consultants",
        "state": "Maharashtra",
        "aicte_region": "Western",
        "email": "ar.gokhale.fictional@aicte.gov.in",
        "seat_tags": ["ARCHITECT"],
        "years_experience": 18,
        "is_retired_hc_judge": False,
    },
    {
        "name": "Ar. Sunita Balakrishnan (Fictional)",
        "designation": "Chief Architect",
        "institution_name": "Urban Design Studio (CoA CA/98/12345)",
        "state": "Tamil Nadu",
        "aicte_region": "Southern",
        "email": "ar.sunita.fictional@aicte.gov.in",
        "seat_tags": ["ARCHITECT"],
        "years_experience": 15,
        "is_retired_hc_judge": False,
    },
    {
        "name": "Ar. Alok Ranjan (Fictional)",
        "designation": "Professor of Architecture",
        "institution_name": "MNIT Jaipur",
        "state": "Rajasthan",
        "aicte_region": "North-Western",
        "email": "ar.alok.fictional@aicte.gov.in",
        "seat_tags": ["ARCHITECT", "ACADEMIC"],
        "years_experience": 20,
        "is_retired_hc_judge": False,
    },
    {
        "name": "Ar. Tariq Ahmad Khan (Fictional)",
        "designation": "Superintending Architect",
        "institution_name": "Central Public Works Department (CPWD)",
        "state": "Delhi",
        "aicte_region": "Northern",
        "email": "ar.tariq.fictional@aicte.gov.in",
        "seat_tags": ["ARCHITECT"],
        "years_experience": 13,
        "is_retired_hc_judge": False,
    },
    {
        "name": "Ar. Priya Murthy (Fictional)",
        "designation": "Principal Architect",
        "institution_name": "Murthy & Associates (CoA Reg.)",
        "state": "Karnataka",
        "aicte_region": "South-Western",
        "email": "ar.priya.fictional@aicte.gov.in",
        "seat_tags": ["ARCHITECT"],
        "years_experience": 10,
        "is_retired_hc_judge": False,
    },
    # 4. Retired High Court Judges (SHC / SAC / SCSC Chairs)
    {
        "name": "Justice (Retd.) K. Radhakrishnan (Fictional)",
        "designation": "Retired Judge, High Court of Kerala",
        "institution_name": "High Court of Kerala (Former)",
        "state": "Kerala",
        "aicte_region": "South-Western",
        "email": "justice.radhakrishnan.fictional@aicte.gov.in",
        "seat_tags": ["CHAIR_SHC"],
        "years_experience": 28,
        "is_retired_hc_judge": True,
    },
    {
        "name": "Justice (Retd.) Hemant R. Patil (Fictional)",
        "designation": "Retired Judge, High Court of Bombay",
        "institution_name": "Bombay High Court (Former)",
        "state": "Maharashtra",
        "aicte_region": "Western",
        "email": "justice.patil.fictional@aicte.gov.in",
        "seat_tags": ["CHAIR_SHC"],
        "years_experience": 25,
        "is_retired_hc_judge": True,
    },
    {
        "name": "Justice (Retd.) Shanti Swarup Misra (Fictional)",
        "designation": "Retired Judge, High Court of Delhi",
        "institution_name": "Delhi High Court (Former)",
        "state": "Delhi",
        "aicte_region": "Northern",
        "email": "justice.misra.fictional@aicte.gov.in",
        "seat_tags": ["CHAIR_SHC"],
        "years_experience": 30,
        "is_retired_hc_judge": True,
    },
    # 5. Industry Experts
    {
        "name": "Dr. Mohan V. Kelkar (Fictional)",
        "designation": "VP Technology & R&D",
        "institution_name": "Bharat Dynamics Ltd",
        "state": "Telangana",
        "aicte_region": "South-Central",
        "email": "mohan.kelkar.fictional@aicte.gov.in",
        "seat_tags": ["INDUSTRY_EXPERT", "ACADEMIC"],
        "years_experience": 19,
        "is_retired_hc_judge": False,
    },
    {
        "name": "Smt. Radhika Swaminathan (Fictional)",
        "designation": "Chief Technology Officer",
        "institution_name": "Titan Technologies",
        "state": "Tamil Nadu",
        "aicte_region": "Southern",
        "email": "radhika.swami.fictional@aicte.gov.in",
        "seat_tags": ["INDUSTRY_EXPERT"],
        "years_experience": 16,
        "is_retired_hc_judge": False,
    },
    {
        "name": "Shri Gautam Dasgupta (Fictional)",
        "designation": "Executive Director (Engineering)",
        "institution_name": "Tata Steel Ltd",
        "state": "Jharkhand",
        "aicte_region": "Eastern",
        "email": "gautam.dasgupta.fictional@aicte.gov.in",
        "seat_tags": ["INDUSTRY_EXPERT"],
        "years_experience": 21,
        "is_retired_hc_judge": False,
    },
    # 6. Revenue & Land Experts
    {
        "name": "Shri Manohar Lal Joshi (Fictional)",
        "designation": "Former Deputy Director of Land Records & Revenue",
        "institution_name": "Department of Revenue, Govt. of UP",
        "state": "Uttar Pradesh",
        "aicte_region": "Northern",
        "email": "manohar.joshi.fictional@aicte.gov.in",
        "seat_tags": ["REVENUE_LAND"],
        "years_experience": 24,
        "is_retired_hc_judge": False,
    },
    {
        "name": "Smt. Suhasini Kulkarni (Fictional)",
        "designation": "Additional Collector (Land Administration)",
        "institution_name": "Revenue Department, Govt. of Maharashtra",
        "state": "Maharashtra",
        "aicte_region": "Western",
        "email": "suhasini.kulkarni.fictional@aicte.gov.in",
        "seat_tags": ["REVENUE_LAND"],
        "years_experience": 18,
        "is_retired_hc_judge": False,
    },
    # 7. DTE / Registrars
    {
        "name": "Dr. G. Chandrasekhar (Fictional)",
        "designation": "Registrar & Former Joint Director DTE",
        "institution_name": "JNTU Hyderabad",
        "state": "Telangana",
        "aicte_region": "South-Central",
        "email": "dr.chandrasekhar.fictional@aicte.gov.in",
        "seat_tags": ["DTE_REGISTRAR", "ACADEMIC"],
        "years_experience": 22,
        "is_retired_hc_judge": False,
    },
    {
        "name": "Dr. Bhaskar Dev Goswami (Fictional)",
        "designation": "Joint Director",
        "institution_name": "Directorate of Technical Education, Assam",
        "state": "Assam",
        "aicte_region": "Eastern",
        "email": "bhaskar.goswami.fictional@aicte.gov.in",
        "seat_tags": ["DTE_REGISTRAR", "ACADEMIC"],
        "years_experience": 17,
        "is_retired_hc_judge": False,
    },
    # 8. Co-opted State / University Nominees
    {
        "name": "Prof. Anuradha Mallick (Fictional)",
        "designation": "Dean of Academic Courses & University Nominee",
        "institution_name": "Biju Patnaik University of Technology",
        "state": "Odisha",
        "aicte_region": "Eastern",
        "email": "anuradha.mallick.fictional@aicte.gov.in",
        "seat_tags": ["CO_OPT", "ACADEMIC"],
        "years_experience": 13,
        "is_retired_hc_judge": False,
    },
    {
        "name": "Prof. Suresh P. Chavan (Fictional)",
        "designation": "Professor & State Board of Technical Education Nominee",
        "institution_name": "Savitribai Phule Pune University",
        "state": "Maharashtra",
        "aicte_region": "Western",
        "email": "suresh.chavan.fictional@aicte.gov.in",
        "seat_tags": ["CO_OPT", "ACADEMIC"],
        "years_experience": 15,
        "is_retired_hc_judge": False,
    },
]


def _ensure_expert_pool(db: Session, audit: AuditService) -> int:
    """Seed the approved panel of fictional experts for committee selection (APH 1.8a, 1.9a)."""
    created = 0
    for data in _FICTIONAL_EXPERTS:
        existing = db.scalar(select(ExpertPool).where(ExpertPool.email == data["email"]))
        if existing is not None:
            continue
        expert = ExpertPool(
            name=data["name"],
            designation=data["designation"],
            institution_name=data["institution_name"],
            state=data["state"],
            aicte_region=data["aicte_region"],
            email=data["email"],
            seat_tags=data["seat_tags"],
            years_experience=data["years_experience"],
            is_retired_hc_judge=data["is_retired_hc_judge"],
            recent_assignment_count=0,
            is_active=True,
            is_fictional=True,
        )
        db.add(expert)
        created += 1
    if created:
        db.flush()
    return created


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
        "application_programs": 0,
        "programmes": 0,
        "faculty": 0,
        "intake_ledger": 0,
        "documents": 0,
        "inspections": 0,
        "application_type_routes": 0,
        "fee_schedules": 0,
        "required_documents": 0,
        "security_deposit_schedules": 0,
        "public_notices": 0,
        "academic_calendar_events": 0,
        "committee_compositions": 0,
        "expert_pool": 0,
        "sla_configs": 0,
        "alert_rules": 0,
        "deadline_rules": 0,
        "workflow_definitions": 0,
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
            pid="DEMO-PID-0001",
            state="Maharashtra",
            region="West",
            aicte_region=InstitutionRegion.WESTERN,
            institution_class=InstitutionClass.OTHER,
            institution_type="Engineering",
            established_year=2001,
            affiliating_body="Demo State Technical University (Fictional)",
            last_eoa_year="2025-26",
            accreditation={
                "nirf_8th": False,
                "qs_asia_2024": False,
                "naac_score": 3.2,
                "nba_courses_pct": 60.0,
                "autonomous": False,
                "avg_admission_pct_5y": 72.5,
            },
            infra_profile={
                "land_area_sqm": 12000.0,
                "built_up_sqm": 8000.0,
                "instructional_area_sqm": 4800.0,
                "administrative_area_sqm": 820.0,
                "amenities_area_sqm": 540.0,
                "circulation_area_sqm": 1450.0,
                "building_completion_year": 2001,
                "classrooms": 24,
                "tutorial_rooms": 8,
                "labs": 12,
                "workshops": 4,
                "library_area_sqm": 400.0,
                "seminar_hall_sqm": 250.0,
                "computer_centre_sqm": 300.0,
                "playground": True,
                "barrier_free": True,
            },
            library_profile={
                "titles": 500,
                "volumes": 2500,
                "journals": 30,
                "ebooks_pct": 40.0,
                "reading_room_seats": 120,
                "digital_library_pcs": 15,
                "ndl_membership": True,
            },
            computing_profile={
                "pcs": 240,
                "pc_student_ratio": 10.0,
                "printers": 15,
                "bandwidth_mbps": 300,
                "language_lab_pcs": 20,
                "wifi": True,
                "plagiarism_software": True,
            },
            essential_requirements={
                "anti_ragging_committee": True,
                "anti_ragging_squad": True,
                "cctv": True,
                "internal_committee": True,
                "ic_annual_report_uploaded": False,
                "sc_st_committee": True,
                "grievance_redressal": True,
                "ombudsperson": True,
                "innovation_council": True,
                "barrier_free_facilities": True,
                "abc_compliance": True,
                "campus_safety": True,
                "food_safety": True,
                "digital_payments": True,
                "letters_displayed": True,
                "mandatory_disclosure_complete": False,
                "mental_health_counselling": True,
                "women_helpline_24x7": True,
                "first_aid": True,
                "potable_water": True,
                "waste_management": True,
                "student_insurance": True,
                "sel_mechanism": True,
                "compulsory_internship": True,
                "internship_policy": False,
                "swayam_electives": True,
                "skilling_credits": True,
                "industry_institution_cell": True,
                "language_lab": True,
                "iqac": True,
                "enrolment_uploaded": False,
            },
            campus={
                "plots": [
                    {
                        "area_sqm": 12000.0,
                        "title_status": "OWNED",
                        "lease_years": 0,
                        "distance_km": 0.0,
                    }
                ],
                "gap_km": 0.0,
                "contiguous": True,
                "obstacles": [],
                "built_up_sqm": 8000.0,
                "lat": 19.076,
                "lng": 72.8777,
            },
        )
        created["institutions"] += int(made)

        south, made = _get_or_create_institution(
            db,
            audit,
            name="Riverbend Institute of Management (Fictional Demo)",
            aicte_id=SOUTH_AICTE_ID,
            pid="DEMO-PID-0002",
            state="Kerala",
            region="South",
            aicte_region=InstitutionRegion.SOUTHERN,
            institution_class=InstitutionClass.OTHER,
            institution_type="Management",
            established_year=2005,
            affiliating_body="Demo University of Management (Fictional)",
            land_ownership=LandOwnership.LEASED,
            lease_years_total=30,
            lease_years_live=12,
            building_leased=False,
            last_eoa_year="2025-26",
            accreditation={
                "naac_score": 3.05,
                "nba_courses_pct": 45.0,
                "autonomous": False,
                "avg_admission_pct_5y": 64.0,
            },
            infra_profile={
                "land_area_sqm": 9000.0,
                "built_up_sqm": 5200.0,
                "instructional_area_sqm": 3100.0,
                "administrative_area_sqm": 800.0,
                "amenities_area_sqm": 600.0,
                "circulation_area_sqm": 900.0,
                "building_completion_year": 2012,
                "classrooms": 16,
                "tutorial_rooms": 6,
                "labs": 6,
                "library_area_sqm": 300.0,
                "playground": True,
                "barrier_free": True,
            },
            library_profile={
                "titles": 300,
                "volumes": 1500,
                "journals": 20,
                "ebooks_pct": 35.0,
                "reading_room_seats": 80,
                "digital_library_pcs": 10,
                "ndl_membership": True,
            },
            computing_profile={
                "pcs": 120,
                "pc_student_ratio": 10.0,
                "printers": 8,
                "bandwidth_mbps": 100,
                "language_lab_pcs": 20,
                "wifi": True,
                "plagiarism_software": True,
            },
            essential_requirements={
                "anti_ragging_committee": True,
                "anti_ragging_squad": True,
                "cctv": True,
                "internal_committee": True,
                "sc_st_committee": True,
                "grievance_redressal": True,
                "ombudsperson": True,
                "innovation_council": True,
                "barrier_free_facilities": True,
                "abc_compliance": True,
                "campus_safety": True,
                "food_safety": True,
                "digital_payments": True,
                "letters_displayed": True,
                "mental_health_counselling": True,
                "women_helpline_24x7": True,
                "first_aid": True,
                "potable_water": True,
                "waste_management": True,
                "student_insurance": True,
                "sel_mechanism": True,
                "compulsory_internship": True,
                "swayam_electives": True,
                "skilling_credits": True,
                "industry_institution_cell": True,
                "language_lab": True,
                "iqac": True,
                "ic_annual_report_uploaded": True,
                "mandatory_disclosure_complete": True,
                "internship_policy": True,
                "enrolment_uploaded": True,
            },
            campus={
                "plots": [
                    {
                        "area_sqm": 9000.0,
                        "title_status": "LEASED",
                        "lease_years": 30,
                        "distance_km": 0.0,
                    }
                ],
                "gap_km": 0.0,
                "contiguous": True,
                "obstacles": [],
                "built_up_sqm": 5200.0,
                "lat": 9.9312,
                "lng": 76.2673,
            },
        )
        created["institutions"] += int(made)

        # Approved programmes, faculty roster and admission history. These rows
        # feed the APH calculators (FSR, cadre split, area, library, PC ratio,
        # reduced enrolment) so the compliance demo evaluates real data.
        west_programmes, made = _ensure_programmes(
            db,
            audit,
            institution=west,
            programmes=[
                {
                    "programme_family": "ENGINEERING_TECHNOLOGY",
                    "level": "UG",
                    "course_name": "B.Tech Computer Science and Engineering",
                    "duration_years": 4,
                    "approved_intake": 60,
                    "divisions": 1,
                    "apH_clause": "APH 6.1",
                }
            ],
        )
        created["programmes"] += made
        created["faculty"] += _ensure_faculty(
            db,
            audit,
            institution=west,
            members=[
                {
                    "name": "Dr. Meera Deshpande (Fictional)",
                    "portal_faculty_id": "DEMO-WEST-FAC-01",
                    "cadre": "PRINCIPAL_DIRECTOR",
                    "qualification": "PhD (Computer Science)",
                    "has_phd": True,
                    "programme_id": west_programmes[0].id,
                },
                {
                    "name": "Dr. Rahul Kulkarni (Fictional)",
                    "portal_faculty_id": "DEMO-WEST-FAC-02",
                    "cadre": "ASSOC_PROFESSOR",
                    "qualification": "PhD (Computer Science)",
                    "has_phd": True,
                    "programme_id": west_programmes[0].id,
                },
                *[
                    {
                        "name": f"Prof. Demo Faculty {index} (Fictional)",
                        "portal_faculty_id": f"DEMO-WEST-FAC-{index + 2:02d}",
                        "cadre": "ASST_PROFESSOR",
                        "qualification": "M.Tech",
                        "has_phd": False,
                        "programme_id": west_programmes[0].id,
                    }
                    for index in range(1, 7)
                ],
            ],
        )
        created["intake_ledger"] += _ensure_intake_ledger(
            db,
            audit,
            programme=west_programmes[0],
            rows=[
                {
                    "academic_year": academic_year,
                    "approved_intake": 60,
                    "admitted_total": admitted,
                }
                for academic_year, admitted in (
                    ("2021-22", 42),
                    ("2022-23", 45),
                    ("2023-24", 40),
                    ("2024-25", 43),
                    ("2025-26", 46),
                )
            ],
        )

        south_programmes, made = _ensure_programmes(
            db,
            audit,
            institution=south,
            programmes=[
                {
                    "programme_family": "MANAGEMENT",
                    "level": "PG",
                    "course_name": "Master of Business Administration",
                    "duration_years": 2,
                    "approved_intake": 120,
                    "divisions": 2,
                    "apH_clause": "APH 6.1",
                }
            ],
        )
        created["programmes"] += made
        created["faculty"] += _ensure_faculty(
            db,
            audit,
            institution=south,
            members=[
                {
                    "name": "Dr. Ananya Menon (Fictional)",
                    "portal_faculty_id": "DEMO-SOUTH-FAC-01",
                    "cadre": "PRINCIPAL_DIRECTOR",
                    "qualification": "PhD (Management)",
                    "has_phd": True,
                    "programme_id": south_programmes[0].id,
                },
                {
                    "name": "Dr. Vikram Nair (Fictional)",
                    "portal_faculty_id": "DEMO-SOUTH-FAC-02",
                    "cadre": "ASSOC_PROFESSOR",
                    "qualification": "PhD (Finance)",
                    "has_phd": True,
                    "programme_id": south_programmes[0].id,
                },
                {
                    "name": "Dr. Leela Krishnan (Fictional)",
                    "portal_faculty_id": "DEMO-SOUTH-FAC-03",
                    "cadre": "ASSOC_PROFESSOR",
                    "qualification": "PhD (Marketing)",
                    "has_phd": True,
                    "programme_id": south_programmes[0].id,
                },
                *[
                    {
                        "name": f"Prof. Demo MBA Faculty {index} (Fictional)",
                        "portal_faculty_id": f"DEMO-SOUTH-FAC-{index + 3:02d}",
                        "cadre": "ASST_PROFESSOR",
                        "qualification": "MBA",
                        "has_phd": index <= 3,
                        "programme_id": south_programmes[0].id,
                    }
                    for index in range(1, 10)
                ],
            ],
        )
        created["intake_ledger"] += _ensure_intake_ledger(
            db,
            audit,
            programme=south_programmes[0],
            rows=[
                {
                    "academic_year": academic_year,
                    "approved_intake": 120,
                    "admitted_total": admitted,
                }
                for academic_year, admitted in (
                    ("2021-22", 118),
                    ("2022-23", 120),
                    ("2023-24", 116),
                    ("2024-25", 120),
                    ("2025-26", 119),
                )
            ],
        )

        admin, made = _get_or_create_user(
            db,
            audit,
            name=settings.seed_admin_name,
            email=settings.seed_admin_email,
            password=admin_password,
            role=Role.SUPER_ADMIN,
            institution=None,
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

        scrutiny_member, made = _get_or_create_user(
            db,
            audit,
            name="Scrutiny Committee Member (Demo)",
            email="scrutiny@example.edu",
            password=demo_password,
            role=Role.SCRUTINY_COMMITTEE_MEMBER,
            institution=west,
        )
        created["users"] += int(made)

        evc_member, made = _get_or_create_user(
            db,
            audit,
            name="EVC Member (Demo)",
            email="inspection@example.edu",
            password=demo_password,
            role=Role.EVC_MEMBER,
            institution=west,
        )
        created["users"] += int(made)

        regional_officer, made = _get_or_create_user(
            db,
            audit,
            name="Regional Officer (Demo)",
            email="regional@example.edu",
            password=demo_password,
            role=Role.REGIONAL_OFFICER,
            institution=west,
        )
        created["users"] += int(made)

        south_admin, made = _get_or_create_user(
            db,
            audit,
            name="South Institution Administrator (Demo)",
            email="institution.south@example.edu",
            password=demo_password,
            role=Role.INSTITUTION_ADMIN,
            institution=south,
        )
        created["users"] += int(made)

        # APH actors that do not belong to an institution.
        for name, email, role in (
            (
                "Regulation Bureau Officer (Demo)",
                "regulation@example.edu",
                Role.REGULATION_BUREAU_OFFICER,
            ),
            (
                "Executive Committee Member (Demo)",
                "ec@example.edu",
                Role.EXECUTIVE_COMMITTEE_MEMBER,
            ),
            (
                "Standing Hearing Committee Member (Demo)",
                "shc@example.edu",
                Role.SHC_MEMBER,
            ),
            (
                "Standing Appellate Committee Member (Demo)",
                "sac@example.edu",
                Role.SAC_MEMBER,
            ),
            (
                "Complaint Scrutiny Member (Demo)",
                "complaints@example.edu",
                Role.COMPLAINT_SCRUTINY_MEMBER,
            ),
        ):
            _, made = _get_or_create_user(
                db,
                audit,
                name=name,
                email=email,
                password=demo_password,
                role=role,
                institution=None,
            )
            created["users"] += int(made)

        reference_counts = _ensure_aph_reference_data(db, audit)
        for key, value in reference_counts.items():
            created[key] = created.get(key, 0) + value

        west_application, made = _get_or_create_application(
            db,
            audit,
            reference=WEST_REFERENCE,
            institution=west,
            application_type="NEW_INSTITUTION",
            track=ApplicationTrack.NEW_INSTITUTION,
            status=ApplicationStatus.EVC_CONSTITUTED,
            stage=WorkflowStage.INSPECTION,
            assigned_officer=scrutiny_member,
            sla_days=-2,
        )
        created["applications"] += int(made)

        south_application, made = _get_or_create_application(
            db,
            audit,
            reference=SOUTH_REFERENCE,
            institution=south,
            application_type="EOA_SELF_DISCLOSURE",
            track=ApplicationTrack.EXISTING,
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
            application_type="NEW_INSTITUTION",
            track=ApplicationTrack.NEW_INSTITUTION,
            status=ApplicationStatus.ACTIVE_LOA,
            stage=WorkflowStage.COMPLETED,
            assigned_officer=regional_officer,
            sla_days=30,
            submitted_days_ago=28,
            decision_days_ago=9,
            decision=DecisionType.LOA,
        )
        created["applications"] += int(made)

        # A dedicated pending case for the one-click +8 day alert demo. It is
        # due in seven days, so the replay produces T-7, T-3 and T-1 warnings,
        # then an SLA breach and escalation to the regional officer.
        _, made = _get_or_create_application(
            db,
            audit,
            reference=DEMO_ALERT_REFERENCE,
            institution=west,
            application_type="NEW_INSTITUTION",
            track=ApplicationTrack.NEW_INSTITUTION,
            status=ApplicationStatus.SCRUTINY,
            stage=WorkflowStage.SCRUTINY,
            assigned_officer=scrutiny_member,
            sla_days=7,
        )
        created["applications"] += int(made)

        # One Category 2 (year-round) case so the routing table is exercised.
        _, made = _get_or_create_application(
            db,
            audit,
            reference="DEMO-SOUTH-2026-002",
            institution=south,
            application_type="CHANGE_OF_SITE",
            track=ApplicationTrack.EXISTING,
            status=ApplicationStatus.SUBMITTED,
            stage=WorkflowStage.APPLICATION,
            assigned_officer=None,
            sla_days=21,
        )
        created["applications"] += int(made)

        created["application_programs"] += _ensure_application_programmes(
            db,
            audit,
            application=west_application,
            programmes=[
                {
                    "program_name": "B.Tech Computer Science and Engineering",
                    "level": "UG",
                    "intake": 60,
                    "faculty_count": 8,
                    "lab_count": 6,
                }
            ],
        )
        created["application_programs"] += _ensure_application_programmes(
            db,
            audit,
            application=south_application,
            programmes=[
                {
                    "program_name": "Master of Business Administration",
                    "level": "PG",
                    "intake": 120,
                    "faculty_count": 12,
                    "lab_count": 4,
                }
            ],
        )

        # The deficient demo institution has uploaded only its Affidavit 2, so
        # the Annexure-2.1 checklist and several essential requirements fail.
        created["documents"] += _ensure_documents(
            db,
            audit,
            application=west_application,
            uploaded_by=institution_admin,
            documents=[
                {
                    "doc_type": "AFFIDAVIT_2",
                    "doc_code": "AFFIDAVIT_2",
                    "affidavit_no": "Affidavit 2",
                    "signed_with_dsc": True,
                },
                {
                    "doc_type": "FIRE_SAFETY_CERTIFICATE",
                    "doc_code": "FIRE_SAFETY_CERTIFICATE",
                    "signed_with_dsc": True,
                    "valid_until": date(2025, 12, 31),
                },
            ],
        )

        # The clean demo institution has a complete, valid document set.
        created["documents"] += _ensure_documents(
            db,
            audit,
            application=south_application,
            uploaded_by=south_admin,
            documents=[
                {
                    "doc_type": "AFFIDAVIT_2",
                    "doc_code": "AFFIDAVIT_2",
                    "affidavit_no": "Affidavit 2",
                    "signed_with_dsc": True,
                },
                {
                    "doc_type": "TER_RECEIPT",
                    "doc_code": "TER_RECEIPT",
                    "signed_with_dsc": True,
                },
                {
                    "doc_type": "OCCUPANCY_CERTIFICATE",
                    "doc_code": "OCCUPANCY_CERTIFICATE",
                    "signed_with_dsc": True,
                    "valid_until": date(2030, 12, 31),
                },
                {
                    "doc_type": "STRUCTURAL_STABILITY_CERTIFICATE",
                    "doc_code": "STRUCTURAL_STABILITY_CERTIFICATE",
                    "signed_with_dsc": True,
                    "valid_until": date(2031, 3, 31),
                },
                {
                    "doc_type": "FIRE_SAFETY_CERTIFICATE",
                    "doc_code": "FIRE_SAFETY_CERTIFICATE",
                    "signed_with_dsc": True,
                    "valid_until": date(2027, 12, 31),
                },
                {
                    "doc_type": "SATELLITE_MAP",
                    "doc_code": "SATELLITE_MAP",
                    "signed_with_dsc": True,
                },
                {
                    "doc_type": "AUDITED_ACCOUNTS_PREVIOUS_YEAR",
                    "doc_code": "AUDITED_ACCOUNTS_PREVIOUS_YEAR",
                    "signed_with_dsc": True,
                },
                {
                    "doc_type": "AFFILIATION_CERTIFICATE",
                    "doc_code": "AFFILIATION_CERTIFICATE",
                    "signed_with_dsc": True,
                },
                {
                    "doc_type": "FACULTY_DETAILS",
                    "doc_code": "FACULTY_DETAILS",
                    "signed_with_dsc": True,
                },
                {
                    "doc_type": "MANDATORY_DISCLOSURE",
                    "doc_code": "MANDATORY_DISCLOSURE",
                    "signed_with_dsc": True,
                },
            ],
        )

        _, made = _get_or_create_inspection(
            db,
            audit,
            application=west_application,
            committee_member=evc_member,
        )
        created["inspections"] += int(made)

        created["sla_configs"] += _ensure_sla_configs(db, audit)
        created["alert_rules"] += _ensure_alert_rules(db, audit)
        created["compliance_rules"] += _ensure_compliance_rules(db, audit)
        created["compliance_config"] += _ensure_compliance_config(db, audit)
        created["compliance_snapshots"] += _ensure_baseline_snapshots(db)
        created["expert_pool"] += _ensure_expert_pool(db, audit)

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
