"""Bulk demo dataset for the seven-minute APH walkthrough.

The seed in :mod:`app.seed` loads configuration and a handful of hand-written
cases. This module turns that into a demo that looks like a working system on a
fresh clone:

* eight named scenario institutions covering the flows in ``docs/DEMO_SCRIPT.md``,
* roughly 150 additional applications spread across every track and stage so
  the queues, funnels and charts are populated,
* twelve months of compliance snapshots per institution for the trend and
  tile-map views,
* committees, inspections, decisions, letters, deposits, complaints, penal
  actions, alerts, workflow events and audit rows around those records.

Everything is fictional. Dates fall between one year ago and today so that the
dashboard has history without inventing AICTE statistics. The loader is
idempotent: every row is keyed on a natural key (portal number, dedupe key,
committee seed or timestamp) and skipped when it already exists.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import SimulatedClock
from app.demo_documents import ensure_demo_documents
from app.models import (
    Alert,
    Appeal,
    Application,
    ApplicationCategory,
    ApplicationProgram,
    ApplicationStatus,
    ApplicationTrack,
    Committee,
    CommitteeMember,
    CommitteeMode,
    CommitteeStatus,
    CommitteeType,
    Complaint,
    ComplaintStatus,
    ComplianceHealth,
    ComplianceResult,
    ComplianceRule,
    ComplianceSnapshot,
    DeadlineRule,
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
    FeeKind,
    FeeTransaction,
    Inspection,
    InspectionStatus,
    Institution,
    InstitutionStatus,
    NomenclatureCourse,
    PenalAction,
    PenalActionType,
    Role,
    SecurityDeposit,
    SecurityDepositSchedule,
    SecurityDepositStatus,
    Severity,
    Timer,
    TimerStatus,
    User,
    WorkflowEvent,
    WorkflowStage,
)
from app.models.enums import AlertChannel, AlertStatus, AlertTrigger, DocumentRejectionReason
from app.schemas.application_sections import ApplicationData
from app.services.application_sections import current_documents
from app.services.audit import AuditService
from app.services.compliance import evaluate_compliance
from app.services.fees import FeeService

logger = logging.getLogger("app.demo_seed")

ACADEMIC_YEAR = "2026-27"
DEMO_PASSWORD_HINT = "ChangeMe123!"

# Scenario portal numbers sit above the hand-written ``0000001`` cases so they
# are easy to spot on the portal.
_SCENARIO_START = 101
_BULK_START = 10001

# Programme family/level used for the Security Deposit rows.
_FAMILY_LEVEL = {
    "ENGINEERING": ("ENGINEERING_TECHNOLOGY", "UG"),
    "MANAGEMENT": ("MANAGEMENT", "PG"),
}


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


def _ago(days: float, hour: int = 10) -> datetime:
    """Return an aware datetime ``days`` before now, at a stable hour."""
    value = _now() - timedelta(days=days)
    return value.replace(hour=hour, minute=0, second=0, microsecond=0)


def _date_ago(days: float) -> date:
    return _ago(days).date()


def _portal(number: int) -> str:
    return f"AICTE/{ACADEMIC_YEAR}/{number:07d}"


# ---------------------------------------------------------------------------
# Fixed demo accounts
# ---------------------------------------------------------------------------


def demo_user_specs(
    institutions: dict[str, Any], regions: dict[str, str]
) -> list[dict[str, Any]]:
    """Return the fixed demo accounts advertised in the README.

    ``regions`` maps ``aicte_id`` to the AICTE region; it is used to give the
    scrutiny and EVC accounts a sensible region without a database round-trip.

    The first nine institution admins own one named scenario each. The rest
    fill out the institution-facing demo so the officer queues have many
    tenants to work with.
    """
    ordered = sorted(institutions)
    scenario_institutions = [
        "MAH-0001",  # deficiency + complaint story
        "MAH-0002",  # increase in intake with an EVC
        "TN-0001",  # deficiency loop, LoR and appeal
        "TN-0002",  # Security Deposit penalty
        "KA-0001",  # hibernating institution
        "KA-0002",  # excess admission and fine
        "MP-0001",  # complaint with show cause and SHC hearing
        "GJ-0001",  # clean EoA by self-disclosure
        "DL-0001",  # clean Extended EoA
    ]
    remaining = [aicte for aicte in ordered if aicte not in scenario_institutions]
    admins = scenario_institutions + remaining[:11]

    specs: list[dict[str, Any]] = []
    for index, aicte_id in enumerate(admins, start=1):
        suffix = "" if index == 1 else str(index)
        specs.append(
            {
                "email": f"institution{suffix}@example.edu",
                "name": f"Fictional Institution Admin {index}",
                "role": Role.INSTITUTION_ADMIN,
                "institution": aicte_id,
                "region": None,
            }
        )

    # Regulation Bureau: no region means it sees every institution.
    specs.append(
        {
            "email": "regulation@example.edu",
            "name": "Fictional Regulation Bureau Officer",
            "role": Role.REGULATION_BUREAU_OFFICER,
            "institution": None,
            "region": None,
        }
    )

    regions_list = ["WESTERN", "NORTHERN", "SOUTHERN", "EASTERN", "CENTRAL"]
    for index, region in enumerate(regions_list, start=1):
        suffix = "" if index == 1 else str(index)
        institution = next(
            (
                aicte
                for aicte in ordered
                if regions.get(aicte) == region
            ),
            ordered[0],
        )
        specs.append(
            {
                "email": f"scrutiny{suffix}@example.edu",
                "name": f"Fictional Scrutiny Officer {index}",
                "role": Role.SCRUTINY_COMMITTEE_MEMBER,
                "institution": institution,
                "region": region,
            }
        )

    for index, region in enumerate(["WESTERN", "NORTHERN", "SOUTHERN"], start=1):
        suffix = "" if index == 1 else str(index)
        specs.append(
            {
                "email": f"regional{suffix}@example.edu",
                "name": f"Fictional Regional Officer {index}",
                "role": Role.REGIONAL_OFFICER,
                "institution": None,
                "region": region,
            }
        )

    for index in range(1, 5):
        suffix = "" if index == 1 else str(index)
        institution = ordered[(index * 7) % len(ordered)]
        specs.append(
            {
                "email": f"inspection{suffix}@example.edu",
                "name": f"Fictional EVC Expert {index}",
                "role": Role.EVC_MEMBER,
                "institution": institution,
                "region": regions.get(institution),
            }
        )

    for role, email, name in (
        (Role.SHC_MEMBER, "shc@example.edu", "Fictional SHC Chair"),
        (Role.SAC_MEMBER, "sac@example.edu", "Fictional SAC Chair"),
        (
            Role.EXECUTIVE_COMMITTEE_MEMBER,
            "ec@example.edu",
            "Fictional Executive Committee Member",
        ),
        (
            Role.COMPLAINT_SCRUTINY_MEMBER,
            "complaints@example.edu",
            "Fictional SCSC Member",
        ),
    ):
        specs.append(
            {
                "email": email,
                "name": name,
                "role": role,
                "institution": None,
                "region": None,
            }
        )

    return specs


def ensure_demo_users(
    db: Session,
    institutions: dict[str, Any],
    regions: dict[str, str],
    *,
    admin_password: str,
    super_admin_email: str,
    super_admin_password: str,
    super_admin_name: str,
) -> dict[str, User]:
    """Create or refresh the fixed demo accounts and return them by e-mail."""
    from app.core.security import hash_password

    users: dict[str, User] = {}
    for spec in demo_user_specs(institutions, regions):
        institution_id = (
            institutions.get(spec["institution"]) if spec["institution"] else None
        )
        region = spec["region"]
        if spec["role"] == Role.INSTITUTION_ADMIN and institution_id is not None:
            # Institution admins are scoped to the institution and see its city.
            institution = db.get(Institution, institution_id)
            region = institution.region if institution is not None else None

        user = db.scalar(select(User).where(User.email == spec["email"]))
        if user is None:
            user = User(
                name=spec["name"],
                email=spec["email"],
                password_hash=hash_password(admin_password),
                role=spec["role"],
                institution_id=institution_id,
                region=region,
                is_active=True,
            )
            db.add(user)
            db.flush()
        else:
            user.name = spec["name"]
            user.role = spec["role"]
            user.institution_id = institution_id
            user.region = region
            user.is_active = True
        users[spec["email"]] = user

    admin = db.scalar(select(User).where(User.email == super_admin_email))
    if admin is None:
        admin = User(
            name=super_admin_name,
            email=super_admin_email,
            password_hash=hash_password(super_admin_password),
            role=Role.SUPER_ADMIN,
            is_active=True,
        )
        db.add(admin)
        db.flush()
    else:
        admin.name = super_admin_name
        admin.role = Role.SUPER_ADMIN
        admin.is_active = True
    users[super_admin_email] = admin
    return users


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------


def _scenarios() -> tuple[dict[str, Any], ...]:
    """Return the eight named demo scenarios."""
    return (
        {
            "key": "clean_eoa",
            "portal": _portal(_SCENARIO_START),
            "aicte_id": "GJ-0001",
            "admin": "institution8@example.edu",
            "type": "EOA_SELF_DISCLOSURE",
            "track": ApplicationTrack.EXISTING,
            "status": ApplicationStatus.ACTIVE_EOA,
            "stage": WorkflowStage.COMPLETED,
            "decision": DecisionType.EOA,
            "submitted_days": 170,
            "academic_year": ACADEMIC_YEAR,
            "summary": "Clean EoA by self-disclosure with Nil Deficiency.",
            "compliance_score": 94,
            "risk_score": 12,
            "nil_deficiency": True,
        },
        {
            "key": "increase_with_evc",
            "portal": _portal(_SCENARIO_START + 1),
            "aicte_id": "MAH-0002",
            "admin": "institution2@example.edu",
            "type": "INCREASE_INTAKE",
            "track": ApplicationTrack.EXISTING,
            "status": ApplicationStatus.EVC_CONSTITUTED,
            "stage": WorkflowStage.INSPECTION,
            "decision": None,
            "submitted_days": 55,
            "academic_year": ACADEMIC_YEAR,
            "summary": "Increase in intake referred to an Expert Visit Committee.",
            "compliance_score": 81,
            "risk_score": 38,
            "nil_deficiency": False,
        },
        {
            "key": "deficiency_lor_appeal",
            "portal": _portal(_SCENARIO_START + 2),
            "aicte_id": "TN-0001",
            "admin": "institution3@example.edu",
            "type": "NEW_INSTITUTION",
            "track": ApplicationTrack.NEW_INSTITUTION,
            "status": ApplicationStatus.SAC_REVIEW,
            "stage": WorkflowStage.DECISION,
            "decision": DecisionType.LOR,
            "submitted_days": 210,
            "academic_year": ACADEMIC_YEAR,
            "summary": "Deficiency loop, LoR and an appeal before the SAC.",
            "compliance_score": 62,
            "risk_score": 74,
            "nil_deficiency": False,
        },
        {
            "key": "deposit_penalty",
            "portal": _portal(_SCENARIO_START + 3),
            "aicte_id": "TN-0002",
            "admin": "institution4@example.edu",
            "type": "INCREASE_INTAKE",
            "track": ApplicationTrack.EXISTING,
            "status": ApplicationStatus.SECURITY_DEPOSIT_PENDING,
            "stage": WorkflowStage.DECISION,
            "decision": DecisionType.LOA,
            "submitted_days": 95,
            "academic_year": ACADEMIC_YEAR,
            "summary": "Security Deposit unpaid past 31 May, penalty applied.",
            "compliance_score": 70,
            "risk_score": 66,
            "nil_deficiency": False,
        },
        {
            "key": "hibernation",
            "portal": _portal(_SCENARIO_START + 4),
            "aicte_id": "KA-0001",
            "admin": "institution5@example.edu",
            "type": "EOA_SELF_DISCLOSURE",
            "track": ApplicationTrack.EXISTING,
            "status": ApplicationStatus.ACTIVE_EOA,
            "stage": WorkflowStage.COMPLETED,
            "decision": DecisionType.EOA,
            "submitted_days": 300,
            "academic_year": ACADEMIC_YEAR,
            "summary": "Hibernating institution with no admission this year.",
            "compliance_score": 48,
            "risk_score": 82,
            "nil_deficiency": False,
        },
        {
            "key": "excess_admission_fine",
            "portal": _portal(_SCENARIO_START + 5),
            "aicte_id": "KA-0002",
            "admin": "institution6@example.edu",
            "type": "INCREASE_INTAKE",
            "track": ApplicationTrack.EXISTING,
            "status": ApplicationStatus.ACTIVE_EOA,
            "stage": WorkflowStage.COMPLETED,
            "decision": DecisionType.EOA,
            "submitted_days": 260,
            "academic_year": ACADEMIC_YEAR,
            "summary": "Excess admission detected; penal fine and intake reduction.",
            "compliance_score": 55,
            "risk_score": 88,
            "nil_deficiency": False,
        },
        {
            "key": "complaint_show_cause",
            "portal": _portal(_SCENARIO_START + 6),
            "aicte_id": "MP-0001",
            "admin": "institution7@example.edu",
            "type": "NEW_PROGRAMME",
            "track": ApplicationTrack.EXISTING,
            "status": ApplicationStatus.SHC_HEARING,
            "stage": WorkflowStage.COMMITTEE_REVIEW,
            "decision": None,
            "submitted_days": 120,
            "academic_year": ACADEMIC_YEAR,
            "summary": "Verified complaint, show-cause reply and SHC hearing.",
            "compliance_score": 58,
            "risk_score": 80,
            "nil_deficiency": False,
        },
        {
            "key": "clean_extended_eoa",
            "portal": _portal(_SCENARIO_START + 7),
            "aicte_id": "DL-0001",
            "admin": "institution9@example.edu",
            "type": "EXTENDED_EOA",
            "track": ApplicationTrack.EXISTING,
            "status": ApplicationStatus.ACTIVE_EOA,
            "stage": WorkflowStage.COMPLETED,
            "decision": DecisionType.EOA,
            "submitted_days": 90,
            "academic_year": ACADEMIC_YEAR,
            "summary": "Clean Extended EoA issued for two academic years.",
            "compliance_score": 91,
            "risk_score": 15,
            "nil_deficiency": True,
        },
        {
            "key": "deficiency_open",
            "portal": _portal(_SCENARIO_START + 8),
            "aicte_id": "MAH-0001",
            "admin": "institution@example.edu",
            "type": "NEW_INSTITUTION",
            "track": ApplicationTrack.NEW_INSTITUTION,
            "status": ApplicationStatus.SCRUTINY,
            "stage": WorkflowStage.SCRUTINY,
            "decision": None,
            "submitted_days": 18,
            "academic_year": ACADEMIC_YEAR,
            "summary": (
                "Fresh application at scrutiny: the fire safety certificate has "
                "expired and the DSC upload is unsigned, so the officer issues "
                "the Deficiency Report from the failed rules."
            ),
            "compliance_score": 64,
            "risk_score": 57,
            "nil_deficiency": False,
        },
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def seed_demo(
    db: Session,
    *,
    institutions: dict[str, Any],
    users: dict[str, User],
    storage_dir: str | Any,
) -> None:
    """Create the bulk demo dataset. Safe to run more than once."""
    paths = ensure_demo_documents(storage_dir)
    admin_by_email = {
        email: user
        for email, user in users.items()
        if user.role == Role.INSTITUTION_ADMIN
    }
    admin_by_institution = {
        user.institution_id: user for user in admin_by_email.values()
    }
    scrutiny = [
        user
        for user in users.values()
        if user.role == Role.SCRUTINY_COMMITTEE_MEMBER
    ]
    evc_users = [user for user in users.values() if user.role == Role.EVC_MEMBER]
    regional = [user for user in users.values() if user.role == Role.REGIONAL_OFFICER]
    shc = next((u for u in users.values() if u.role == Role.SHC_MEMBER), None)
    scsc = next(
        (u for u in users.values() if u.role == Role.COMPLAINT_SCRUTINY_MEMBER), None
    )
    ec = next(
        (u for u in users.values() if u.role == Role.EXECUTIVE_COMMITTEE_MEMBER), None
    )

    audit = AuditService(db)
    _seed_scenarios(
        db,
        audit,
        institutions=institutions,
        admin_by_email=admin_by_email,
        scrutiny=scrutiny,
        evc_users=evc_users,
        regional=regional,
        shc=shc,
        scsc=scsc,
        ec=ec,
        paths=paths,
    )
    _seed_bulk_applications(
        db,
        audit,
        institutions=institutions,
        admin_by_institution=admin_by_institution,
        scrutiny=scrutiny,
        evc_users=evc_users,
    )
    _seed_statutory_timers(db)
    _seed_bulk_complaints(db, institutions=institutions, scrutiny=scrutiny)
    _seed_snapshots(db, institutions=institutions)
    _seed_bulk_alerts(db, users=users)
    db.flush()


# ---------------------------------------------------------------------------
# Shared record helpers
# ---------------------------------------------------------------------------


def _existing_application(db: Session, portal: str) -> Application | None:
    return db.scalar(
        select(Application).where(Application.portal_application_no == portal)
    )


def _find_programme_name(db: Session, level: str, family: str, seed: int) -> str:
    """Return an Annexure-11 course name for the requested level."""
    names = db.scalars(
        select(NomenclatureCourse.course_name)
        .where(
            NomenclatureCourse.level == level,
            NomenclatureCourse.programme_family == family,
        )
        .order_by(NomenclatureCourse.course_name)
        .limit(50)
    ).all()
    if not names:
        return "Civil Engineering" if level in {"UG", "DIPLOMA"} else "Management"
    return names[seed % len(names)]


def _ensure_programme(
    db: Session,
    application: Application,
    *,
    level: str,
    family: str,
    intake: int,
    seed: int,
) -> None:
    exists = db.scalar(
        select(ApplicationProgram.id).where(
            ApplicationProgram.application_id == application.id
        )
    )
    if exists is not None:
        return
    name = _find_programme_name(db, level, family, seed)
    db.add(
        ApplicationProgram(
            application_id=application.id,
            program_name=name,
            level=level,
            intake=intake,
            faculty_count=max(6, intake // 15),
            lab_count=max(2, intake // 60),
        )
    )


def _ensure_fee(
    db: Session,
    application: Application,
    institution: Institution,
    *,
    paid: bool,
    days_ago: float,
) -> None:
    """Record the TER the live fee service would quote for this application.

    The quotation resolves the APH item code for the application type (for
    example ``NEW_INSTITUTION`` prices as ``NEW_INSTITUTION_TER``), applies the
    configured annual increase and the late-submission penalty. Writing the
    quote lines means the seeded Fees tab shows the same figures an
    institution would see on a fresh submission instead of a hard-coded
    amount.
    """
    del institution  # kept for call-site compatibility; the quote resolves it
    exists = db.scalar(
        select(FeeTransaction.id).where(
            FeeTransaction.application_id == application.id,
            FeeTransaction.kind == FeeKind.TER,
        )
    )
    if exists is not None:
        return
    service = FeeService(db, AuditService(db), SimulatedClock())
    quote = service.quote(application)
    application.ter_amount_paise = quote.total_paise
    if not paid:
        return
    paid_at = _ago(days_ago)
    application.ter_paid_at = paid_at
    receipt_base = (
        f"TER-{application.academic_year.replace('-', '')}-"
        f"{str(application.id).replace('-', '')[:10].upper()}"
    )
    receipt_no = f"{receipt_base}-01"
    application.ter_receipt_no = receipt_no
    for index, line in enumerate(quote.lines, start=1):
        db.add(
            FeeTransaction(
                application_id=application.id,
                item_code=line.item_code,
                amount_paise=line.amount_paise,
                kind=(
                    FeeKind.PENALTY
                    if line.item_code == "LATE_SUBMISSION_PENALTY"
                    else FeeKind.TER
                ),
                receipt_no=f"{receipt_base}-{index:02d}",
                paid_at=paid_at,
                apH_clause=line.apH_clause,
                needs_verification=line.needs_verification,
            )
        )
        if index == 1:
            application.ter_receipt_no = f"{receipt_base}-{index:02d}"


def _sync_compliance_score(db: Session, application: Application) -> None:
    """Store the score the case-file compliance preview computes.

    The scenario rows carry a hand-written score so the seeder can stay fast,
    but a hand-written figure drifts from the rule evaluation the moment the
    seeded documents change. Recomputing without persisting keeps the
    dashboard card and the case file's Compliance tab in agreement.
    """
    preview = evaluate_compliance(
        db,
        application,
        ApplicationData.model_validate(application.data or {}),
        evaluated_at=_now(),
        documents=list(current_documents(db, application.id).values()),
    )
    application.compliance_score = Decimal(str(preview.score))


def _add_document(
    db: Session,
    application: Application,
    *,
    uploader: User,
    doc_type: str,
    path_key: str,
    paths: dict[str, str],
    doc_code: str | None = None,
    status: DocumentVerificationStatus = DocumentVerificationStatus.VERIFIED,
    version: int = 1,
    rejection: DocumentRejectionReason | None = None,
    comment: str | None = None,
    valid_until: date | None = None,
    clause: str = "APH 1.4.3",
    deficiency_id: uuid.UUID | None = None,
    superseded_by: uuid.UUID | None = None,
    signer_name: str | None = None,
    signed_with_dsc: bool = True,
) -> Document | None:
    storage_path = paths.get(path_key)
    if storage_path is None:
        return None
    exists = db.scalar(
        select(Document.id).where(
            Document.application_id == application.id,
            Document.doc_type == doc_type,
            Document.version == version,
        )
    )
    if exists is not None:
        return None
    document = Document(
        application_id=application.id,
        doc_type=doc_type,
        doc_code=doc_code or doc_type,
        filename=storage_path.rsplit("/", 1)[-1],
        storage_path=storage_path,
        uploaded_by=uploader.id,
        verification_status=status,
        rejection_reason_code=rejection,
        rejection_comment=comment,
        rejected_by=uploader.id if rejection is not None else None,
        rejected_at=_ago(4) if rejection is not None else None,
        valid_until=valid_until,
        expiry_date=valid_until,
        version=version,
        apH_clause=clause,
        related_deficiency_id=deficiency_id,
        superseded_by=superseded_by,
        signer_name=signer_name,
        signed_with_dsc=signed_with_dsc,
        size_bytes=42_000,
        content_type="application/pdf",
        verification_notes={"demo": True},
    )
    db.add(document)
    db.flush()
    return document


def _add_scenario_documents(
    db: Session,
    application: Application,
    *,
    scenario_key: str,
    uploader: User,
    paths: dict[str, str],
) -> None:
    """Attach the fictional PDFs that the verification screen shows.

    Every scenario gets the standard land, building, faculty and disclosure
    papers; a few scenarios also get deliberately flawed uploads so the
    rejection reasons and AI document flags have something to display.
    """
    common = (
        ("LAND_DOCUMENT", "land_document", "APH 1.7.2"),
        ("BUILDING_PLAN", "building_plan", "APH 1.8a"),
        ("FACULTY_LIST", "faculty_list", "APH 1.10"),
        ("MANDATORY_DISCLOSURE", "mandatory_disclosure", "APH 1.4.3"),
    )
    for doc_type, path_key, clause in common:
        _add_document(
            db,
            application,
            uploader=uploader,
            doc_type=doc_type,
            doc_code=doc_type,
            path_key=path_key,
            paths=paths,
            clause=clause,
        )

    flaws: dict[str, tuple[dict[str, object], ...]] = {
        "deficiency_open": (
            {
                "doc_type": "FIRE_SAFETY_CERTIFICATE",
                "path_key": "fire_safety_expired",
                "status": DocumentVerificationStatus.REJECTED,
                "rejection": DocumentRejectionReason.EXPIRED,
                "comment": "Certificate expired on 2025-12-31 (APH 1.8f).",
                "valid_until": _date_ago(90),
                "clause": "APH 1.8f",
            },
            {
                "doc_type": "DSC_CERTIFICATE",
                "path_key": "dsc_unsigned",
                "status": DocumentVerificationStatus.FLAGGED,
                "rejection": DocumentRejectionReason.NO_DSC,
                "comment": "Upload carries no digital signature (APH 1.4.3).",
                "signed_with_dsc": False,
            },
        ),
        "deficiency_lor_appeal": (
            {
                "doc_type": "SCANNED_DOCUMENT",
                "path_key": "blank_scan",
                "status": DocumentVerificationStatus.REJECTED,
                "rejection": DocumentRejectionReason.UNREADABLE,
                "comment": "Blank scan; resubmit a legible copy (APH 1.8f).",
            },
            {
                "doc_type": "DSC_CERTIFICATE",
                "path_key": "dsc_unsigned",
                "status": DocumentVerificationStatus.FLAGGED,
                "rejection": DocumentRejectionReason.NO_DSC,
                "comment": "Upload carries no digital signature (APH 1.4.3).",
                "signed_with_dsc": False,
            },
        ),
        "complaint_show_cause": (
            {
                "doc_type": "AFFIDAVIT_3",
                "path_key": "affidavit_name_mismatch",
                "status": DocumentVerificationStatus.FLAGGED,
                "rejection": DocumentRejectionReason.NAME_MISMATCH,
                "comment": "Institution name on the affidavit differs from the portal (APH 1.4.4).",
                "signer_name": "Vidya Vikas Institute of Technology",
                "clause": "APH 1.4.4",
            },
        ),
        "excess_admission_fine": (
            {
                "doc_type": "AUDITED_STATEMENT",
                "path_key": "audit_report",
                "status": DocumentVerificationStatus.VERIFIED,
                "clause": "APH 1.8d",
            },
        ),
    }
    for position, spec in enumerate(flaws.get(scenario_key, ())):
        _add_document(
            db,
            application,
            uploader=uploader,
            paths=paths,
            version=position + 1,
            **spec,  # type: ignore[arg-type]
        )


def _add_workflow_chain(
    db: Session,
    application: Application,
    *,
    actor: User | None,
    submitted_days: float,
    final_status: ApplicationStatus,
    final_stage_days: float,
) -> None:
    """Add a plausible transition history ending at the current status."""
    exists = db.scalar(
        select(WorkflowEvent.id).where(
            WorkflowEvent.application_id == application.id
        )
    )
    if exists is not None:
        return
    chain = [
        (None, ApplicationStatus.SUBMITTED, "submit", "APH 1.4.3"),
        (
            ApplicationStatus.SUBMITTED,
            ApplicationStatus.SCRUTINY,
            "assign_scrutiny",
            "APH 1.8a",
        ),
    ]
    if final_status in {
        ApplicationStatus.DEFICIENCY_COMMUNICATED,
        ApplicationStatus.INSTITUTION_COMPLIANCE,
        ApplicationStatus.RE_SCRUTINY,
        ApplicationStatus.EVC_CONSTITUTED,
        ApplicationStatus.EVC_DONE,
        ApplicationStatus.EC_DECISION,
        ApplicationStatus.LOA_ISSUED,
        ApplicationStatus.LOR_ISSUED,
        ApplicationStatus.ACTIVE_LOA,
        ApplicationStatus.ACTIVE_EOA,
        ApplicationStatus.CLOSED,
    }:
        chain.append(
            (
                ApplicationStatus.SCRUTINY,
                ApplicationStatus.DEFICIENCY_COMMUNICATED,
                "communicate_deficiency",
                "APH 2.3.3b",
            )
        )
        chain.append(
            (
                ApplicationStatus.DEFICIENCY_COMMUNICATED,
                ApplicationStatus.INSTITUTION_COMPLIANCE,
                "submit_compliance",
                "APH 2.4",
            )
        )
        chain.append(
            (
                ApplicationStatus.INSTITUTION_COMPLIANCE,
                ApplicationStatus.RE_SCRUTINY,
                "re_scrutiny_verify",
                "APH 1.8",
            )
        )
    if final_status in {
        ApplicationStatus.EVC_CONSTITUTED,
        ApplicationStatus.EVC_DONE,
        ApplicationStatus.EC_DECISION,
        ApplicationStatus.LOA_ISSUED,
        ApplicationStatus.LOR_ISSUED,
        ApplicationStatus.ACTIVE_LOA,
        ApplicationStatus.ACTIVE_EOA,
    }:
        chain.append(
            (
                ApplicationStatus.RE_SCRUTINY,
                ApplicationStatus.EVC_CONSTITUTED,
                "constitute_evc",
                "APH 1.9a",
            )
        )
        chain.append(
            (
                ApplicationStatus.EVC_CONSTITUTED,
                ApplicationStatus.EVC_DONE,
                "evc_report",
                "APH 1.9",
            )
        )
    if final_status in {
        ApplicationStatus.EC_DECISION,
        ApplicationStatus.LOA_ISSUED,
        ApplicationStatus.LOR_ISSUED,
        ApplicationStatus.ACTIVE_LOA,
        ApplicationStatus.ACTIVE_EOA,
        ApplicationStatus.CLOSED,
    }:
        chain.append(
            (
                ApplicationStatus.EVC_DONE,
                ApplicationStatus.EC_DECISION,
                "ec_decide",
                "APH 1.10a",
            )
        )
    if final_status in {
        ApplicationStatus.LOA_ISSUED,
        ApplicationStatus.ACTIVE_LOA,
        ApplicationStatus.ACTIVE_EOA,
    }:
        chain.append(
            (
                ApplicationStatus.EC_DECISION,
                ApplicationStatus.LOA_ISSUED,
                "issue_loa",
                "APH 1.10a",
            )
        )
    if final_status in {ApplicationStatus.LOR_ISSUED, ApplicationStatus.CLOSED}:
        chain.append(
            (
                ApplicationStatus.EC_DECISION,
                ApplicationStatus.LOR_ISSUED,
                "issue_lor",
                "APH 2.24a",
            )
        )
    if final_status in {ApplicationStatus.ACTIVE_LOA, ApplicationStatus.ACTIVE_EOA}:
        chain.append(
            (
                ApplicationStatus.LOA_ISSUED,
                ApplicationStatus.ACTIVE_LOA,
                "issue_loa",
                "APH 2.25f",
            )
        )

    total = len(chain)
    for index, (from_status, to_status, action, clause) in enumerate(chain):
        when = _ago(
            max(1.0, submitted_days - (submitted_days - final_stage_days) * index / total)
        )
        db.add(
            WorkflowEvent(
                application_id=application.id,
                from_status=from_status,
                to_status=to_status,
                actor_id=actor.id if actor is not None else None,
                action=action,
                comment="Fictional demo transition.",
                details={"demo": True},
                apH_clause=clause,
                created_at=when,
                updated_at=when,
            )
        )


def _add_alert(
    db: Session,
    *,
    recipient: User,
    application: Application | None,
    alert_type: str,
    severity: Severity,
    title: str,
    message: str,
    dedupe_key: str,
    escalation_level: int = 0,
    days_ago: float = 1,
    status: AlertStatus = AlertStatus.SENT,
) -> None:
    if db.scalar(select(Alert.id).where(Alert.dedupe_key == dedupe_key)) is not None:
        return
    when = _ago(days_ago)
    db.add(
        Alert(
            application_id=application.id if application is not None else None,
            recipient_user_id=recipient.id,
            type=alert_type,
            severity=severity,
            title=title,
            message=message,
            channel=AlertChannel.IN_APP,
            status=status,
            sent_at=when,
            escalation_level=escalation_level,
            dedupe_key=dedupe_key,
            created_at=when,
            updated_at=when,
        )
    )


def _add_decision_letter(
    db: Session,
    application: Application,
    *,
    outcome: DecisionOutcome,
    decided_days: float,
    letter_type: DecisionLetterType,
    suffix: str,
    appeal_days: int | None = None,
    body: str,
) -> Decision:
    decision = db.scalar(
        select(Decision).where(
            Decision.application_id == application.id,
            Decision.outcome == outcome,
        )
    )
    if decision is None:
        decision = Decision(
            application_id=application.id,
            body=DecisionBody.EC,
            outcome=outcome,
            decided_on=_date_ago(decided_days),
            quorum_met=True,
            notes=f"Fictional demo decision: {body}",
            apH_clause="APH 1.10a",
        )
        db.add(decision)
        db.flush()

    letter_no = f"{letter_type.value}/AICTE/{ACADEMIC_YEAR}/{suffix}"
    if db.scalar(
        select(DecisionLetter.id).where(DecisionLetter.letter_number == letter_no)
    ) is None:
        issued = _ago(decided_days)
        db.add(
            DecisionLetter(
                application_id=application.id,
                decision_id=decision.id,
                letter_type=letter_type,
                letter_number=letter_no,
                issued_on=issued.date(),
                published_at=issued,
                appeal_clock_start=issued if appeal_days else None,
                appeal_deadline=(
                    issued + timedelta(days=appeal_days) if appeal_days else None
                ),
                body_text=body,
            )
        )
    return decision


# ---------------------------------------------------------------------------
# Scenario seeding
# ---------------------------------------------------------------------------


def _seed_scenarios(
    db: Session,
    audit: AuditService,
    *,
    institutions: dict[str, Any],
    admin_by_email: dict[str, User],
    scrutiny: list[User],
    evc_users: list[User],
    regional: list[User],
    shc: User | None,
    scsc: User | None,
    ec: User | None,
    paths: dict[str, str],
) -> None:
    """Create the eight hand-crafted scenario applications."""
    for index, scenario in enumerate(_scenarios()):
        if _existing_application(db, scenario["portal"]) is not None:
            continue
        institution_id = institutions[scenario["aicte_id"]]
        institution = db.get(Institution, institution_id)
        if institution is None:
            continue
        admin = admin_by_email.get(scenario["admin"])
        if admin is None:
            continue
        officer = (
            scrutiny[0]
            if scenario["key"] == "deficiency_open" and scrutiny
            else scrutiny[index % len(scrutiny)]
            if scrutiny
            else None
        )
        submitted = scenario["submitted_days"]
        final_stage_at = max(1.0, submitted - 12)
        app = Application(
            institution_id=institution_id,
            track=scenario["track"],
            application_type=scenario["type"],
            category=ApplicationCategory.CAT1_CUTOFF,
            academic_year=scenario["academic_year"],
            portal_application_no=scenario["portal"],
            status=scenario["status"],
            current_stage=scenario["stage"],
            decision_type=scenario["decision"],
            submitted_at=_ago(submitted),
            locked_at=_ago(submitted),
            stage_entered_at=_ago(final_stage_at),
            sla_due_at=_ago(final_stage_at - 20) if final_stage_at > 20 else _ago(-3),
            assigned_officer_id=officer.id if officer else None,
            risk_score=Decimal(str(scenario["risk_score"])),
            compliance_score=Decimal(str(scenario["compliance_score"])),
            data={
                "reference": scenario["portal"],
                "demo": True,
                "scenario": scenario["key"],
                "summary": scenario["summary"],
                "nil_deficiency": scenario["nil_deficiency"],
                "mandatory_disclosure_url": (
                    f"https://{scenario['aicte_id'].lower()}.example.edu/disclosure"
                ),
            },
            created_at=_ago(submitted + 1),
            updated_at=_ago(final_stage_at),
        )
        if scenario["decision"] in {DecisionType.LOA, DecisionType.EOA}:
            app.loa_valid_until = _date_ago(-365)
        if scenario["key"] == "deficiency_lor_appeal":
            app.appeal_deadline = _ago(-4)
        db.add(app)
        db.flush()

        _ensure_programme(
            db,
            app,
            level="UG" if institution.type == "ENGINEERING" else "PG",
            family=_FAMILY_LEVEL.get(institution.type, ("ENGINEERING_TECHNOLOGY", "UG"))[0],
            intake=120 if institution.type == "ENGINEERING" else 60,
            seed=index * 5,
        )
        _ensure_fee(
            db,
            app,
            institution,
            paid=True,
            days_ago=submitted,
        )
        _add_workflow_chain(
            db,
            app,
            actor=officer,
            submitted_days=submitted,
            final_status=scenario["status"],
            final_stage_days=final_stage_at,
        )
        audit.log(
            admin,
            "DEMO_SEED_APPLICATION",
            "Application",
            app.id,
            after={
                "portal_application_no": scenario["portal"],
                "scenario": scenario["key"],
            },
        )
        _add_scenario_documents(
            db,
            app,
            scenario_key=scenario["key"],
            uploader=admin,
            paths=paths,
        )

        if scenario["key"] == "increase_with_evc":
            _seed_evc_scenario(
                db, app, institution, evc_users=evc_users, paths=paths, admin=admin
            )
        elif scenario["key"] == "deficiency_lor_appeal":
            _seed_lor_appeal_scenario(
                db, app, paths=paths, admin=admin, officer=officer, shc=shc
            )
        elif scenario["key"] == "deposit_penalty":
            _seed_deposit_penalty_scenario(db, app, institution)
        elif scenario["key"] == "excess_admission_fine":
            _seed_excess_admission_scenario(
                db, app, institution, ec=ec, scsc=scsc
            )
        elif scenario["key"] == "complaint_show_cause":
            _seed_show_cause_scenario(
                db,
                app,
                institution,
                admin=admin,
                shc=shc,
                scsc=scsc,
                ec=ec,
            )
        elif scenario["key"] == "hibernation":
            institution.status = InstitutionStatus.HIBERNATION
            institution.last_eoa_year = "2024-25"
        elif scenario["key"] in {"clean_eoa", "clean_extended_eoa"}:
            _add_decision_letter(
                db,
                app,
                outcome=DecisionOutcome.EOA,
                decided_days=max(5.0, submitted - 60),
                letter_type=DecisionLetterType.EOA,
                suffix=scenario["portal"][-7:],
                body=scenario["summary"],
            )

        if scenario["decision"] in {DecisionType.LOA, DecisionType.EOA}:
            _seed_deposit_for_scenario(
                db,
                app,
                institution,
                status=(
                    SecurityDepositStatus.PAID
                    if scenario["key"] == "clean_eoa"
                    else SecurityDepositStatus.PAID
                ),
                created_days=max(1.0, submitted - 65),
            )

        _seed_compliance_results(
            db,
            app,
            passing=scenario["nil_deficiency"],
            seed=index,
        )
        _add_scenario_alerts(
            db,
            scenario,
            app,
            institution=institution,
            admin=admin,
            officer=officer,
            regional=regional,
        )
        _sync_compliance_score(db, app)
        logger.debug(" seeded scenario %s", scenario["key"])


def _seed_evc_scenario(
    db: Session,
    app: Application,
    institution: Institution,
    *,
    evc_users: list[User],
    paths: dict[str, str],
    admin: User,
) -> None:
    exists = db.scalar(select(Committee.id).where(Committee.application_id == app.id))
    if exists is None:
        committee = Committee(
            application_id=app.id,
            type=CommitteeType.EVC,
            mode=CommitteeMode.PHYSICAL,
            scheduled_at=_ago(-5, hour=11),
            selection_seed=f"demo-evc-{app.id}",
            status=CommitteeStatus.SCHEDULED,
            apH_clause="APH 1.9a",
        )
        db.add(committee)
        db.flush()
        for index, member in enumerate(evc_users[:3]):
            db.add(
                CommitteeMember(
                    committee_id=committee.id,
                    user_id=member.id,
                    role="CHAIR" if index == 0 else "MEMBER",
                    apH_clause="APH 16.5",
                )
            )
        db.add(
            Inspection(
                application_id=app.id,
                committee_id=evc_users[0].id,
                scheduled_on=_ago(-5, hour=11),
                status=InspectionStatus.SCHEDULED,
                report={
                    "demo": True,
                    "video_url": "https://video.example.edu/evc-demo",
                    "checklist": ["land", "building", "faculty", "library"],
                },
                recommendation=None,
            )
        )
        _add_document(
            db,
            app,
            uploader=admin,
            doc_type="EVC_VIDEO",
            doc_code="EVC_VIDEO",
            path_key="land_document",
            paths=paths,
            status=DocumentVerificationStatus.PENDING,
            clause="APH 1.9f",
        )
        _add_alert(
            db,
            recipient=evc_users[0],
            application=app,
            alert_type=AlertTrigger.INSPECTION_SCHEDULED.value,
            severity=Severity.HIGH,
            title="EVC visit scheduled in 5 days",
            message=(
                f"Expert Visit Committee for {institution.name} is scheduled in five days. "
                "The institution must upload the 30-minute video before the visit (APH 1.9f)."
            ),
            dedupe_key=f"demo:evc:{app.id}",
            days_ago=2,
        )


def _seed_lor_appeal_scenario(
    db: Session,
    app: Application,
    *,
    paths: dict[str, str],
    admin: User,
    officer: User | None,
    shc: User | None,
) -> None:
    del shc
    # A closed deficiency loop followed by a fresh one kept open today.
    closed = db.scalar(
        select(Deficiency.id).where(
            Deficiency.application_id == app.id,
            Deficiency.status == DeficiencyStatus.CLOSED,
        )
    )
    if closed is None:
        closed_row = Deficiency(
            application_id=app.id,
            category="Document",
            description=(
                "Fire safety certificate had expired; a valid certificate was uploaded "
                "and verified during re-scrutiny (APH 2.3.3b)."
            ),
            raised_by=officer.id if officer else admin.id,
            status=DeficiencyStatus.CLOSED,
            due_date=_date_ago(120),
            response_text="Valid fire safety certificate uploaded.",
            responded_at=_ago(118),
            closed_at=_ago(115),
        )
        db.add(closed_row)
        db.flush()
        _add_document(
            db,
            app,
            uploader=admin,
            doc_type="FIRE_SAFETY_CERTIFICATE",
            doc_code="FIRE_SAFETY_CERTIFICATE",
            path_key="fire_safety_expired",
            paths=paths,
            status=DocumentVerificationStatus.REJECTED,
            rejection=DocumentRejectionReason.EXPIRED,
            comment="Expired on 2025-12-31 (APH 1.8f).",
            valid_until=_date_ago(90),
            deficiency_id=closed_row.id,
            clause="APH 1.8f",
        )
        _add_document(
            db,
            app,
            uploader=admin,
            doc_type="FIRE_SAFETY_CERTIFICATE",
            doc_code="FIRE_SAFETY_CERTIFICATE",
            path_key="fire_safety_valid",
            paths=paths,
            version=2,
            valid_until=_date_ago(-300),
        )

    if db.scalar(select(Decision.id).where(Decision.application_id == app.id)) is None:
        decision = _add_decision_letter(
            db,
            app,
            outcome=DecisionOutcome.LOR,
            decided_days=30,
            letter_type=DecisionLetterType.LOR,
            suffix=app.portal_application_no[-7:] if app.portal_application_no else "0103",
            appeal_days=7,
            body=(
                "Fictional Letter of Rejection: the institution did not cure the "
                "deficiencies within the scrutiny window."
            ),
        )
        del decision
        app.appeal_loop_count = 1
        db.add(
            Appeal(
                application_id=app.id,
                filed_at=_ago(24),
                within_deadline=True,
                loop_no=1,
                sac_recommendation=None,
                apH_clause="APH 1.11a",
            )
        )
        _add_alert(
            db,
            recipient=admin,
            application=app,
            alert_type=AlertTrigger.APPEAL_WINDOW_CLOSING.value,
            severity=Severity.HIGH,
            title="Appeal filed against the Letter of Rejection",
            message=(
                "The appeal was filed within the seven-day window and is pending before "
                "the Standing Appellate Committee (APH 1.11a)."
            ),
            dedupe_key=f"demo:appeal:{app.id}",
            days_ago=22,
            status=AlertStatus.READ,
        )


def _seed_deposit_penalty_scenario(
    db: Session, app: Application, institution: Institution
) -> None:
    deposit = _seed_deposit_for_scenario(
        db,
        app,
        institution,
        status=SecurityDepositStatus.PENALTY_20,
        created_days=95,
    )
    if deposit is not None:
        deposit.penalty_percent = 20
        deposit.needs_verification = True
        db.add(
            FeeTransaction(
                application_id=app.id,
                item_code="SECURITY_DEPOSIT_PENALTY",
                amount_paise=int(deposit.required_paise * 20 / 100),
                kind=FeeKind.PENALTY,
                receipt_no=f"SD-PEN/{ACADEMIC_YEAR}/{str(app.id)[:8]}",
                paid_at=None,
                apH_clause="APH 6.46a",
                needs_verification=True,
            )
        )
    app.security_deposit_due_on = _date_ago(-10)
    app.data = {
        **(app.data or {}),
        "security_deposit_note": (
            "Deposit proof not received by 31 May; a 20% penalty applies (APH 6.46a)."
        ),
    }


def _seed_excess_admission_scenario(
    db: Session,
    app: Application,
    institution: Institution,
    *,
    ec: User | None,
    scsc: User | None,
) -> None:
    complaint = db.scalar(
        select(Complaint).where(Complaint.application_id == app.id)
    )
    if complaint is None:
        complaint = Complaint(
            institution_id=institution.id,
            application_id=app.id,
            source="PORTAL",
            status=ComplaintStatus.DECIDED,
            category="EXCESS_ADMISSION",
            description=(
                "Fictional verified complaint: students were admitted beyond the "
                "approved intake for the 2025-26 academic year."
            ),
            received_on=_date_ago(160),
            complainant_name="Fictional Complainant",
            complainant_contact="complainant@example.edu",
            complainant_verified=True,
            is_anonymous=False,
            scsc_decision="SHOW_CAUSE",
            scsc_decided_on=_date_ago(140),
            scsc_notes="SCSC found the complaint verified (APH 7.10c).",
            show_cause_issued_on=_date_ago(140),
            show_cause_due_on=_date_ago(125),
            show_cause_reply="The institution accepted that 18 extra students were admitted.",
            show_cause_replied_on=_date_ago(128),
            shc_hearing_on=_date_ago(100),
            shc_findings="SHC confirmed the excess admission.",
            ec_decision="PENAL_ACTION",
            speaking_order=(
                "Fine of INR 2,50,000 and a 10% intake reduction for 2026-27 "
                "(APH 7.4g, 7.3b)."
            ),
            decided_on=_date_ago(90),
            apH_clause="APH 7.10f",
        )
        db.add(complaint)
        db.flush()

    if db.scalar(select(PenalAction.id).where(PenalAction.complaint_id == complaint.id)) is None:
        db.add(
            PenalAction(
                institution_id=institution.id,
                complaint_id=complaint.id,
                application_id=app.id,
                action_type=PenalActionType.EXCESS_ADMISSION_FINE,
                violation_code="g",
                order_number=f"PENAL/AICTE/{ACADEMIC_YEAR}/0042",
                issued_on=_date_ago(90),
                hearing_on=_date_ago(100),
                hearing_notes="SHC hearing attended by the institution (APH 6.50h).",
                hearing_by_user_id=ec.id if ec else None,
                hearing_done=True,
                speaking_order=complaint.speaking_order,
                fine_paise=25_000_000,
                fine_basis="INR 2,50,000 for 18 excess admissions, illustrative only.",
                consequences={
                    "intake_reduction_pct": 10,
                    "academic_year": ACADEMIC_YEAR,
                    "other": "No admission beyond the reduced intake.",
                },
                effective_academic_year=ACADEMIC_YEAR,
                apH_clause="APH 7.4g",
                needs_verification=True,
            )
        )
        db.add(
            PenalAction(
                institution_id=institution.id,
                complaint_id=complaint.id,
                application_id=app.id,
                action_type=PenalActionType.INTAKE_REDUCTION,
                violation_code="g",
                order_number=f"PENAL/AICTE/{ACADEMIC_YEAR}/0043",
                issued_on=_date_ago(90),
                hearing_on=_date_ago(100),
                hearing_by_user_id=ec.id if ec else None,
                hearing_done=True,
                speaking_order="A 10% intake reduction applies for one academic year.",
                fine_paise=None,
                effective_academic_year=ACADEMIC_YEAR,
                apH_clause="APH 7.3b",
                needs_verification=True,
            )
        )
    if scsc is not None:
        _add_alert(
            db,
            recipient=scsc,
            application=app,
            alert_type="PENAL_ACTION_ISSUED",
            severity=Severity.CRITICAL,
            title="Excess admission: penal action issued",
            message=(
                "The EC issued a fine and a 10% intake reduction under APH 7.3b/7.4g. "
                "The Speaking Order is published on the portal."
            ),
            dedupe_key=f"demo:penal:{app.id}",
            days_ago=88,
        )


def _seed_show_cause_scenario(
    db: Session,
    app: Application,
    institution: Institution,
    *,
    admin: User,
    shc: User | None,
    scsc: User | None,
    ec: User | None,
) -> None:
    complaint = db.scalar(
        select(Complaint).where(Complaint.application_id == app.id)
    )
    if complaint is None:
        complaint = Complaint(
            institution_id=institution.id,
            application_id=app.id,
            source="PGRC",
            status=ComplaintStatus.SHOW_CAUSE,
            category="FACULTY_SHORTAGE",
            description=(
                "Fictional verified complaint: a programme is being run with fewer "
                "regular faculty than the approved intake requires."
            ),
            received_on=_date_ago(28),
            complainant_name="Fictional Complainant",
            complainant_contact="complainant@example.edu",
            complainant_verified=True,
            is_anonymous=False,
            scsc_decision="SHOW_CAUSE",
            scsc_decided_on=_date_ago(12),
            scsc_notes="SCSC verified the complaint and issued a show-cause notice.",
            show_cause_issued_on=_date_ago(12),
            show_cause_due_on=_date_ago(-3),
            apH_clause="APH 7.10d",
        )
        db.add(complaint)
        db.flush()
    if shc is not None:
        committee = db.scalar(
            select(Committee).where(
                Committee.complaint_id == complaint.id,
                Committee.type == CommitteeType.SHC,
            )
        )
        if committee is None:
            committee = Committee(
                complaint_id=complaint.id,
                type=CommitteeType.SHC,
                mode=CommitteeMode.PHYSICAL,
                scheduled_at=_ago(-7, hour=12),
                selection_seed=f"demo-shc-{complaint.id}",
                status=CommitteeStatus.SCHEDULED,
                apH_clause="APH 7.10e",
            )
            db.add(committee)
            db.flush()
            db.add(
                CommitteeMember(
                    committee_id=committee.id,
                    user_id=shc.id,
                    role="CHAIR",
                    apH_clause="APH 16.6",
                )
            )
            if scsc is not None:
                db.add(
                    CommitteeMember(
                        committee_id=committee.id,
                        user_id=scsc.id,
                        role="MEMBER_SECRETARY",
                        apH_clause="APH 16.6",
                    )
                )
    if ec is not None:
        _add_alert(
            db,
            recipient=ec,
            application=app,
            alert_type="COMPLAINT_HEARING",
            severity=Severity.HIGH,
            title="SHC hearing scheduled for a verified complaint",
            message=(
                "A verified faculty-shortage complaint is listed for the SHC in seven "
                "days. A show-cause reply is due from the institution (APH 7.10d-e)."
            ),
            dedupe_key=f"demo:shc:{complaint.id}",
            days_ago=1,
        )
    _add_alert(
        db,
        recipient=admin,
        application=app,
        alert_type=AlertTrigger.DEFICIENCY_DUE.value,
        severity=Severity.CRITICAL,
        title="Show-cause notice: faculty shortage complaint",
        message=(
            "The Standing Complaint Scrutiny Committee issued a show-cause notice. "
            f"Reply by {_date_ago(-3).isoformat()} (APH 7.10d)."
        ),
        dedupe_key=f"demo:showcause:{complaint.id}",
        escalation_level=1,
        days_ago=11,
    )


def _seed_deposit_for_scenario(
    db: Session,
    app: Application,
    institution: Institution,
    *,
    status: SecurityDepositStatus,
    created_days: float,
) -> SecurityDeposit | None:
    existing = db.scalar(
        select(SecurityDeposit).where(SecurityDeposit.application_id == app.id)
    )
    if existing is not None:
        return existing
    if institution.institution_class.value == "GOVT_TYPE":
        # APH Table 1.4: Government and government-aided institutions are exempt.
        return None
    family, level = _FAMILY_LEVEL.get(institution.type, ("ENGINEERING_TECHNOLOGY", "UG"))
    schedule = db.scalar(
        select(SecurityDepositSchedule).where(
            SecurityDepositSchedule.programme_family == family,
            SecurityDepositSchedule.level == level,
        )
    )
    if schedule is None:
        return None
    created = _date_ago(created_days)
    deposit = SecurityDeposit(
        institution_id=institution.id,
        application_id=app.id,
        programme_family=family,
        level=level,
        required_paise=schedule.amount_paise,
        doubled_for_leased=(
            institution.land_ownership.value == "LEASED" or institution.building_leased
        ),
        created_on=created,
        maturity_on=date(created.year + 2, created.month, created.day),
        status=status,
        apH_clause=schedule.apH_clause,
        needs_verification=schedule.needs_verification,
    )
    if status == SecurityDepositStatus.PAID:
        deposit.release_clearances = []
    app.security_deposit_due_on = created + timedelta(days=15)
    db.add(deposit)
    return deposit


# ---------------------------------------------------------------------------
# Bulk applications
# ---------------------------------------------------------------------------

_PROFILES: tuple[tuple[ApplicationStatus, WorkflowStage, DecisionType | None], ...] = (
    (ApplicationStatus.DRAFT, WorkflowStage.APPLICATION, None),
    (ApplicationStatus.SUBMITTED, WorkflowStage.APPLICATION, None),
    (ApplicationStatus.SCRUTINY, WorkflowStage.SCRUTINY, None),
    (ApplicationStatus.DEFICIENCY_COMMUNICATED, WorkflowStage.DEFICIENCY, None),
    (ApplicationStatus.INSTITUTION_COMPLIANCE, WorkflowStage.DEFICIENCY, None),
    (ApplicationStatus.RE_SCRUTINY, WorkflowStage.SCRUTINY, None),
    (ApplicationStatus.EVC_CONSTITUTED, WorkflowStage.INSPECTION, None),
    (ApplicationStatus.EVC_DONE, WorkflowStage.INSPECTION, None),
    (
        ApplicationStatus.REGULATION_BUREAU_OBSERVATIONS,
        WorkflowStage.COMMITTEE_REVIEW,
        None,
    ),
    (ApplicationStatus.EC_DECISION, WorkflowStage.DECISION, None),
    (ApplicationStatus.LOA_ISSUED, WorkflowStage.DECISION, DecisionType.LOA),
    (ApplicationStatus.LOR_ISSUED, WorkflowStage.DECISION, DecisionType.LOR),
    (ApplicationStatus.APPEAL_WINDOW, WorkflowStage.DECISION, DecisionType.LOR),
    (ApplicationStatus.SAC_REVIEW, WorkflowStage.DECISION, DecisionType.LOR),
    (ApplicationStatus.SECURITY_DEPOSIT_PENDING, WorkflowStage.DECISION, DecisionType.LOA),
    (ApplicationStatus.ACTIVE_LOA, WorkflowStage.COMPLETED, DecisionType.LOA),
    (ApplicationStatus.EOA_ISSUED, WorkflowStage.DECISION, DecisionType.EOA),
    (ApplicationStatus.ACTIVE_EOA, WorkflowStage.COMPLETED, DecisionType.EOA),
    (ApplicationStatus.SELF_DISCLOSURE_CHECK, WorkflowStage.SCRUTINY, None),
    (ApplicationStatus.RANDOM_EVC, WorkflowStage.INSPECTION, None),
    (ApplicationStatus.COMPLIANCE_WINDOW, WorkflowStage.DEFICIENCY, None),
    (ApplicationStatus.EC_LISTING, WorkflowStage.COMMITTEE_REVIEW, None),
    (ApplicationStatus.WITHDRAWN, WorkflowStage.APPLICATION, None),
    (ApplicationStatus.FINAL_LOA, WorkflowStage.COMPLETED, DecisionType.LOA),
    (ApplicationStatus.FINAL_LOR, WorkflowStage.COMPLETED, DecisionType.LOR),
)

_TYPES_BY_TRACK: dict[ApplicationTrack, tuple[str, ...]] = {
    ApplicationTrack.NEW_INSTITUTION: (
        "NEW_INSTITUTION",
        "UNIVERSITY",
        "NEW_INSTITUTION_OTHER_REGULATOR",
        "CLOSURE_AND_NEW_INSTITUTION",
    ),
    ApplicationTrack.EXISTING: (
        "INCREASE_INTAKE",
        "NEW_PROGRAMME",
        "EOA_SELF_DISCLOSURE",
        "CHANGE_OF_NAME",
        "COURSE_RENAME_MERGE_REDUCTION",
        "NRI_SEATS",
        "INTEGRATED_DUAL_DEGREE",
        "EXTENDED_EOA",
        "CHANGE_OF_SITE",
        "CLOSURE_OF_PROGRAMME",
        "WOMEN_COED_CONVERSION",
    ),
    ApplicationTrack.UNIVERSITY: ("UNIVERSITY",),
    ApplicationTrack.ODL: ("ODL_ONLINE",),
}


def _seed_bulk_applications(
    db: Session,
    audit: AuditService,
    *,
    institutions: dict[str, Any],
    admin_by_institution: dict[Any, User],
    scrutiny: list[User],
    evc_users: list[User],
) -> None:
    """Create 150 applications spread over twelve months."""
    bulk_portals = [_portal(_BULK_START + offset) for offset in range(150)]
    already_seeded = db.scalar(
        select(Application.id)
        .where(Application.portal_application_no.in_(bulk_portals))
        .limit(1)
    )
    if already_seeded is not None:
        return

    ordered = sorted(institutions)
    total = 150
    evc_index = 0
    for index in range(total):
        aicte_id = ordered[(index * 7 + 3) % len(ordered)]
        institution_id = institutions[aicte_id]
        institution = db.get(Institution, institution_id)
        if institution is None:
            continue
        admin = admin_by_institution.get(institution_id)
        if admin is None:
            admin = next(iter(admin_by_institution.values()))
        profile = _PROFILES[index % len(_PROFILES)]
        status, stage, decision = profile
        if status in {
            ApplicationStatus.ACTIVE_EOA,
            ApplicationStatus.EOA_ISSUED,
            ApplicationStatus.SELF_DISCLOSURE_CHECK,
        }:
            track = ApplicationTrack.EXISTING
        elif institution.type == "MANAGEMENT":
            track = ApplicationTrack.EXISTING
        else:
            track = (
                ApplicationTrack.NEW_INSTITUTION
                if index % 6 == 0
                else ApplicationTrack.EXISTING
            )
        types = _TYPES_BY_TRACK[track]
        application_type = types[index % len(types)]
        submitted_days = 30 + ((index * 37) % 330)
        decided_days = max(3.0, submitted_days - 45 - (index % 20))
        officer = scrutiny[index % len(scrutiny)] if scrutiny else None

        portal = _portal(_BULK_START + index)
        app = Application(
            institution_id=institution_id,
            track=track,
            application_type=application_type,
            category=(
                ApplicationCategory.CAT2_YEAR_ROUND
                if application_type
                in {"EXTENDED_EOA", "CHANGE_OF_SITE", "CLOSURE_OF_PROGRAMME", "ODL_ONLINE"}
                else ApplicationCategory.CAT1_CUTOFF
            ),
            academic_year=ACADEMIC_YEAR,
            portal_application_no=portal if status != ApplicationStatus.DRAFT else None,
            status=status,
            current_stage=stage,
            decision_type=decision,
            submitted_at=_ago(submitted_days) if status != ApplicationStatus.DRAFT else None,
            locked_at=_ago(submitted_days) if status != ApplicationStatus.DRAFT else None,
            stage_entered_at=_ago(decided_days),
            sla_due_at=(
                _ago(decided_days - (7 + index % 21))
                if index % 4 != 0
                else _ago(-(index % 9))
            ),
            assigned_officer_id=officer.id if officer else None,
            risk_score=Decimal(str(10 + (index * 13) % 85)),
            compliance_score=Decimal(str(45 + (index * 7) % 55)),
            is_withdrawn=status is ApplicationStatus.WITHDRAWN,
            data={
                "reference": portal,
                "demo": True,
                "bulk": True,
                "history_month": (_ago(submitted_days)).strftime("%Y-%m"),
            },
            created_at=_ago(submitted_days + 1),
            updated_at=_ago(decided_days),
        )
        if decision in {DecisionType.LOA, DecisionType.EOA}:
            app.loa_valid_until = _date_ago(-(120 + index % 400))
        if status is ApplicationStatus.APPEAL_WINDOW:
            app.appeal_deadline = _ago(-(1 + index % 6))
            app.appeal_loop_count = 1
        db.add(app)
        db.flush()

        _ensure_programme(
            db,
            app,
            level="UG" if institution.type == "ENGINEERING" else "PG",
            family=_FAMILY_LEVEL.get(institution.type, ("ENGINEERING_TECHNOLOGY", "UG"))[0],
            intake=60 + (index % 4) * 30,
            seed=index,
        )
        if status != ApplicationStatus.DRAFT:
            _ensure_fee(db, app, institution, paid=True, days_ago=submitted_days)
            _add_workflow_chain(
                db,
                app,
                actor=officer,
                submitted_days=submitted_days,
                final_status=status,
                final_stage_days=decided_days,
            )
        if decision in {DecisionType.LOA, DecisionType.EOA, DecisionType.LOR, DecisionType.LOD}:
            outcome = {
                DecisionType.LOA: DecisionOutcome.LOA,
                DecisionType.EOA: DecisionOutcome.EOA,
                DecisionType.LOR: DecisionOutcome.LOR,
                DecisionType.LOD: DecisionOutcome.LOD,
            }[decision]
            letter_type = {
                DecisionType.LOA: DecisionLetterType.LOA,
                DecisionType.EOA: DecisionLetterType.EOA,
                DecisionType.LOR: DecisionLetterType.LOR,
                DecisionType.LOD: DecisionLetterType.LOD,
            }[decision]
            _add_decision_letter(
                db,
                app,
                outcome=outcome,
                decided_days=decided_days,
                letter_type=letter_type,
                suffix=f"B{index:04d}",
                appeal_days=7 if decision in {DecisionType.LOR, DecisionType.LOD} else None,
                body=f"Fictional {letter_type.value} issued for the demo dataset.",
            )
        if status in {ApplicationStatus.EVC_CONSTITUTED, ApplicationStatus.RANDOM_EVC}:
            _seed_bulk_evc(db, app, evc_users, evc_index)
            evc_index += 1
        if status in {
            ApplicationStatus.DEFICIENCY_COMMUNICATED,
            ApplicationStatus.INSTITUTION_COMPLIANCE,
        }:
            _seed_bulk_deficiency(db, app, officer or admin, index)

        if index % 11 == 0:
            audit.log(
                admin,
                "DEMO_SEED_APPLICATION",
                "Application",
                app.id,
                after={"portal_application_no": portal, "bulk": True},
            )


def _seed_statutory_timers(db: Session) -> None:
    """Start the appeal and Security Deposit clocks for the seeded cases.

    Scenario rows are inserted straight into their final state, so the workflow
    effects that normally start these timers never run. Without a timer the
    case-file deadlines strip is empty and the scheduled scan has nothing to
    warn about, so the demo could not show the APH 1.11a / 2.25f clocks.
    """
    rules = {rule.code: rule for rule in db.scalars(select(DeadlineRule)).all()}
    existing = {
        (timer.application_id, timer.deadline_rule_id)
        for timer in db.scalars(select(Timer)).all()
    }
    created = 0
    for application in db.scalars(select(Application)).all():
        if application.status == ApplicationStatus.APPEAL_WINDOW:
            code = "APPEAL_WINDOW"
            due = application.appeal_deadline
        elif application.status == ApplicationStatus.SECURITY_DEPOSIT_PENDING:
            code = "SECURITY_DEPOSIT"
            due = application.security_deposit_due_on
        else:
            continue
        rule = rules.get(code)
        if rule is None or due is None:
            continue
        if (application.id, rule.id) in existing:
            continue
        if isinstance(due, datetime):
            due_at = due if due.tzinfo is not None else due.replace(tzinfo=UTC)
        else:
            due_at = datetime.combine(due, datetime.max.time(), UTC)
        db.add(
            Timer(
                application_id=application.id,
                deadline_rule_id=rule.id,
                started_at=due_at - timedelta(days=rule.duration_days),
                due_at=due_at,
                status=TimerStatus.PENDING,
                fired_levels=[],
            )
        )
        existing.add((application.id, rule.id))
        created += 1
    db.flush()
    if created:
        logger.info("demo statutory timers started", extra={"count": created})


def _seed_bulk_evc(
    db: Session, app: Application, evc_users: list[User], index: int
) -> None:
    if not evc_users:
        return
    member = evc_users[index % len(evc_users)]
    db.add(
        Inspection(
            application_id=app.id,
            committee_id=member.id,
            scheduled_on=_ago(-(3 + index % 25), hour=10),
            status=InspectionStatus.SCHEDULED,
            report={"demo": True, "video_url": "https://video.example.edu/evc-demo"},
            recommendation=None,
        )
    )


def _seed_bulk_deficiency(
    db: Session, app: Application, officer: User, index: int
) -> None:
    if db.scalar(select(Deficiency.id).where(Deficiency.application_id == app.id)):
        return
    descriptions = (
        "Faculty list does not show the required cadre ratio.",
        "Land use certificate is not in the name of the trust.",
        "Library titles do not cover every approved programme.",
        "Built-up area statement is missing the circulation component.",
    )
    db.add(
        Deficiency(
            application_id=app.id,
            category="Document" if index % 2 == 0 else "Compliance",
            description=descriptions[index % len(descriptions)],
            raised_by=officer.id,
            status=(
                DeficiencyStatus.OPEN
                if app.status is ApplicationStatus.DEFICIENCY_COMMUNICATED
                else DeficiencyStatus.RESPONDED
            ),
            due_date=_date_ago(-(5 + index % 10)),
            response_text=(
                None
                if app.status is ApplicationStatus.DEFICIENCY_COMMUNICATED
                else "Institution uploaded a revised statement for re-scrutiny."
            ),
            responded_at=(
                None
                if app.status is ApplicationStatus.DEFICIENCY_COMMUNICATED
                else _ago(4)
            ),
        )
    )


def _seed_bulk_complaints(
    db: Session, *, institutions: dict[str, Any], scrutiny: list[User]
) -> None:
    """Add a few complaints in earlier stages so the complaint chart is varied."""
    if not scrutiny:
        return
    ordered = sorted(institutions)
    statuses = (
        (ComplaintStatus.RECEIVED, "ANONYMOUS", True),
        (ComplaintStatus.PGRC, "FEE_IRREGULARITY", False),
        (ComplaintStatus.SCSC, "INFRASTRUCTURE", False),
    )
    for index, (status, category, anonymous) in enumerate(statuses):
        aicte_id = ordered[(index * 13 + 5) % len(ordered)]
        institution_id = institutions[aicte_id]
        exists = db.scalar(
            select(Complaint.id).where(
                Complaint.institution_id == institution_id,
                Complaint.category == category,
            )
        )
        if exists is not None:
            continue
        complaint = Complaint(
            institution_id=institution_id,
            source="PGRC" if status is not ComplaintStatus.RECEIVED else "PORTAL",
            status=status,
            category=category,
            description=f"Fictional demo complaint about {category.lower().replace('_', ' ')}.",
            received_on=_date_ago(15 + index * 20),
            complainant_name=None if anonymous else "Fictional Complainant",
            complainant_contact=None if anonymous else "complainant@example.edu",
            complainant_verified=not anonymous,
            is_anonymous=anonymous,
            rejection_reason=(
                "Anonymous complaint not processed (CVC guidance adopted by APH 7.10h)."
                if anonymous
                else None
            ),
            rejection_clause="APH 7.10h" if anonymous else None,
            apH_clause="APH 7.10",
        )
        db.add(complaint)


def _seed_compliance_results(
    db: Session, app: Application, *, passing: bool, seed: int
) -> None:
    """Attach a small set of rule results to one scenario application."""
    exists = db.scalar(
        select(ComplianceResult.id).where(
            ComplianceResult.application_id == app.id
        )
    )
    if exists is not None:
        return
    rules = db.scalars(
        select(ComplianceRule)
        .where(ComplianceRule.is_active.is_(True))
        .order_by(ComplianceRule.code)
        .limit(14)
    ).all()
    for index, rule in enumerate(rules):
        failed = (not passing) and index in {0, 3, 7}
        observed = rule.threshold
        status = "PASS" if not failed or passing else "FAIL"
        db.add(
            ComplianceResult(
                application_id=app.id,
                institution_id=app.institution_id,
                rule_id=rule.id,
                observed_value=observed,
                status=status,
                passed=status == "PASS",
                message=(
                    f"{rule.name}: observed {observed} against threshold "
                    f"{rule.threshold} ({rule.apH_clause})."
                ),
                evidence={
                    "observed": float(observed),
                    "threshold": float(rule.threshold),
                    "demo": True,
                },
                explanation={
                    "rule_code": rule.code,
                    "rule_name": rule.name,
                    "apH_clause": rule.apH_clause,
                    "observed": float(observed),
                    "threshold": float(rule.threshold),
                    "result": status,
                    "fix_text": (
                        "Upload evidence that meets the configured norm."
                        if status == "FAIL"
                        else None
                    ),
                },
                evaluated_at=_ago(5 + (seed % 20)),
            )
        )


def _seed_snapshots(db: Session, *, institutions: dict[str, Any]) -> None:
    """Create twelve monthly compliance snapshots per institution."""
    now = _now()
    for aicte_id in sorted(institutions):
        institution_id = institutions[aicte_id]
        existing = set(
            db.scalars(
                select(ComplianceSnapshot.evaluated_at).where(
                    ComplianceSnapshot.institution_id == institution_id,
                    ComplianceSnapshot.trigger == "seed",
                )
            ).all()
        )
        for month in range(12):
            evaluated = (now - timedelta(days=30 * month)).replace(
                hour=2, minute=30, second=0, microsecond=0
            )
            if any(
                value.year == evaluated.year and value.month == evaluated.month
                for value in existing
            ):
                continue
            drift = (sum(ord(c) for c in aicte_id) + month * 7) % 42
            score = max(42, 96 - drift)
            health = (
                ComplianceHealth.GREEN
                if score >= 85
                else ComplianceHealth.AMBER
                if score >= 70
                else ComplianceHealth.RED
            )
            failed = max(0, int((100 - score) / 8))
            db.add(
                ComplianceSnapshot(
                    institution_id=institution_id,
                    application_id=None,
                    score=Decimal(str(score)),
                    status=health,
                    failed_count=failed,
                    failed_critical_count=1 if health is ComplianceHealth.RED else 0,
                    failed_high_count=max(0, failed - 1),
                    missing_count=max(0, failed - 2),
                    trigger="seed",
                    evaluated_at=evaluated,
                    created_at=evaluated,
                    updated_at=evaluated,
                )
            )
        db.flush()


def _seed_bulk_alerts(db: Session, *, users: dict[str, User]) -> None:
    """Add a handful of unread alerts so the inbox is not empty."""
    institution_admin = users.get("institution@example.edu")
    if institution_admin is None:
        return
    samples = (
        (
            "demo:inbox:1",
            AlertTrigger.SLA_BREACHED.value,
            Severity.HIGH,
            "Scrutiny SLA breached on an application in your region",
            "An application has been in scrutiny for more than the configured 15 days (demo SLA).",
        ),
        (
            "demo:inbox:2",
            AlertTrigger.DOCUMENT_EXPIRING.value,
            Severity.MEDIUM,
            "Fire safety certificate expires in 45 days",
            "Upload a renewed certificate before the deadline to avoid a deficiency.",
        ),
        (
            "demo:inbox:3",
            AlertTrigger.DEPOSIT_DUE.value,
            Severity.MEDIUM,
            "Security Deposit proof due within 15 days",
            "Affidavit 3 and the deposit proof are due under APH 2.25f.",
        ),
    )
    for key, alert_type, severity, title, message in samples:
        _add_alert(
            db,
            recipient=institution_admin,
            application=None,
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            dedupe_key=key,
            days_ago=1,
            status=AlertStatus.PENDING,
        )


def _add_scenario_alerts(
    db: Session,
    scenario: dict[str, Any],
    app: Application,
    *,
    institution: Institution,
    admin: User,
    officer: User | None,
    regional: list[User],
) -> None:
    """Create the alert that drives the scenario on the dashboards."""
    key = scenario["key"]
    if key == "clean_eoa":
        _add_alert(
            db,
            recipient=admin,
            application=app,
            alert_type="EOA_ISSUED",
            severity=Severity.LOW,
            title="Extended EoA issued",
            message="The Extended EoA is valid for two academic years (APH 1.10b).",
            dedupe_key=f"demo:{key}:{app.id}",
            days_ago=20,
            status=AlertStatus.READ,
        )
    elif key == "deposit_penalty":
        _add_alert(
            db,
            recipient=admin,
            application=app,
            alert_type=AlertTrigger.DEPOSIT_PENALTY.value,
            severity=Severity.CRITICAL,
            title="Security Deposit penalty of 20% applied",
            message=(
                "The deposit proof was not received by 31 July, so a 20% penalty "
                "applies (APH 6.46a)."
            ),
            dedupe_key=f"demo:{key}:{app.id}",
            days_ago=3,
            escalation_level=2,
        )
        if regional:
            _add_alert(
                db,
                recipient=regional[0],
                application=app,
                alert_type=AlertTrigger.DEPOSIT_PENALTY.value,
                severity=Severity.CRITICAL,
                title="Security Deposit penalty escalated",
                message=(
                    f"{institution.name} has an unpaid Security Deposit with a 20% penalty."
                ),
                dedupe_key=f"demo:{key}:{app.id}:regional",
                days_ago=2,
                escalation_level=2,
            )
    elif key == "deficiency_lor_appeal":
        _add_alert(
            db,
            recipient=admin,
            application=app,
            alert_type=AlertTrigger.APPEAL_WINDOW_CLOSING.value,
            severity=Severity.HIGH,
            title="Appeal pending before the SAC",
            message="The appeal was filed within the seven-day window (APH 1.11a).",
            dedupe_key=f"demo:{key}:{app.id}",
            days_ago=22,
            status=AlertStatus.READ,
        )
    elif key == "hibernation":
        _add_alert(
            db,
            recipient=admin,
            application=app,
            alert_type="EOA_AFTER_BREAK",
            severity=Severity.MEDIUM,
            title="Institution in hibernation",
            message=(
                "No admission was reported this year. Restoration requires a fresh "
                "application after the break (APH 2.16)."
            ),
            dedupe_key=f"demo:{key}:{app.id}",
            days_ago=40,
        )
    elif key == "clean_extended_eoa":
        _add_alert(
            db,
            recipient=admin,
            application=app,
            alert_type="EOA_ISSUED",
            severity=Severity.LOW,
            title="Extended EoA issued",
            message="The Extended EoA is valid for two academic years (APH 1.10b).",
            dedupe_key=f"demo:{key}:{app.id}",
            days_ago=10,
            status=AlertStatus.ACKED,
        )
    if officer is not None and key in {"increase_with_evc", "deficiency_lor_appeal"}:
        _add_alert(
            db,
            recipient=officer,
            application=app,
            alert_type=AlertTrigger.SLA_BREACHED.value,
            severity=Severity.HIGH,
            title="SLA watch: scenario application",
            message=f"{institution.name} needs action under the demo SLA.",
            dedupe_key=f"demo:{key}:{app.id}:officer",
            days_ago=1,
            escalation_level=1,
        )
