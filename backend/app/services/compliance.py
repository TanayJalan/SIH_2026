"""Evaluate database-configured APH compliance rules against application data.

Every rule is a database row carrying an ``apH_clause``. The evaluator is a
small, safe expression engine — no ``eval()`` is used anywhere in this module.
It supports comparison, ``BETWEEN``, ``EXISTS``, ``DATE_NOT_EXPIRED`` and the
aggregate operators ``RATIO``, ``SUM`` and ``COUNT``.

The service provides:

* pure APH calculators (see :mod:`app.services.compliance_calculators`),
* metric extraction from the application form, approved programmes, the
  approved-intake ledger, the faculty roster, JSONB institution profiles,
  uploaded documents and Security Deposits,
* per-rule evaluation with a clause-quoting explanation,
* a weighted 0-100 score with configurable severity weights, plus the rule
  that a failed mandatory rule (or unassessed mandatory evidence) always
  prevents a Nil Deficiency result,
* RED/AMBER/GREEN monitoring status with configurable breakpoints,
* append-only institution snapshots and RED alerts.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.application import Application, ApplicationProgram
from app.models.application_type_route import ApplicationTypeRoute
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
    FacultyCadre,
    Severity,
)
from app.models.faculty import Faculty
from app.models.institution import Institution
from app.models.programme import ApprovedIntakeLedger, Programme
from app.models.required_document import RequiredDocument
from app.models.security_deposit import SecurityDeposit
from app.schemas.application_sections import ApplicationData
from app.schemas.compliance import (
    CompliancePreviewRead,
    ComplianceRulePreview,
    ComplianceRuleStatus,
    PenalActionSuggestionRead,
)
from app.services import compliance_calculators as calc
from app.services.penal_actions import suggestions_for_codes

logger = logging.getLogger("app.compliance")

MetricValue = float | int | bool | date | str | None
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

_AGGREGATE_OPERATORS = {"RATIO", "SUM", "COUNT", "DATE_NOT_EXPIRED"}
_DEFAULT_AGGREGATE_COMPARISON = {
    "RATIO": "<=",
    "SUM": ">=",
    "COUNT": ">=",
    "DATE_NOT_EXPIRED": ">=",
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

_ESSENTIAL_FLAGS = (
    "anti_ragging_committee",
    "anti_ragging_squad",
    "cctv",
    "internal_committee",
    "ic_annual_report_uploaded",
    "sc_st_committee",
    "grievance_redressal",
    "ombudsperson",
    "innovation_council",
    "abc_compliance",
    "campus_safety",
    "food_safety",
    "digital_payments",
    "letters_displayed",
    "mandatory_disclosure_complete",
    "mental_health_counselling",
    "women_helpline_24x7",
    "first_aid",
    "potable_water",
    "waste_management",
    "student_insurance",
    "sel_mechanism",
    "compulsory_internship",
    "internship_policy",
    "swayam_electives",
    "skilling_credits",
    "industry_institution_cell",
    "barrier_free_facilities",
    "language_lab",
    "iqac",
    "enrolment_uploaded",
)

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
    "faculty.required_total": ("Required faculty", "count"),
    "faculty.fsr": ("Faculty:student ratio", "students/faculty"),
    "faculty.cadre_compliant": ("Cadre mix 1:2:6", None),
    "faculty.head_present": ("Principal/Director present", None),
    "faculty.hod_present": ("Head of Department present", None),
    "faculty.pg_phd_professor_present": ("PhD Professor for PG", None),
    "faculty.adjunct_pct": ("Adjunct faculty share", "%"),
    "faculty.adjunct_count": ("Adjunct and Professor-of-Practice faculty", "count"),
    "faculty.adjunct_allowed": ("Permitted adjunct and Professor-of-Practice posts", "count"),
    "faculty.adjunct_excess": ("Adjunct posts above the permitted share", "count"),
    "faculty.prof_of_practice_pct": ("Professor of Practice share", "%"),
    "faculty.prof_of_practice_count": ("Professors of Practice", "count"),
    "faculty.prof_of_practice_min": ("Minimum Professors of Practice", "count"),
    "faculty.prof_of_practice_shortfall": ("Professor of Practice shortfall", "count"),
    "faculty.regular_pct": ("Regular faculty share", "%"),
    "faculty.regular_count": ("Regular faculty", "count"),
    "faculty.contractual_count": ("Contractual faculty", "count"),
    "faculty.ecs_pct": ("Faculty paid through ECS", "%"),
    "faculty.biometric_pct": ("Faculty with biometric attendance", "%"),
    "faculty.id_update_lag_days": ("Faculty portal ID update lag", "days"),
    "faculty.head_vacancy_months": ("Principal vacancy", "months"),
    "faculty.fsr_for": ("Faculty:student ratio (programme scope)", "students/faculty"),
    "faculty.required_for": ("Required faculty (programme scope)", "count"),
    "faculty.cadre_compliant_for": ("Cadre mix (programme scope)", None),
    "land.lease_ok": ("Lease requirement met", None),
    "land.title_ok": ("Clear land title", None),
    "land.tenure_ok": ("Title or lease tenure", None),
    "land.lease_years_total": ("Lease tenure", "years"),
    "land.lease_years_live": ("Live lease remaining", "years"),
    "land.lease_tenure_ok": ("Lease tenure of at least 30 years", None),
    "land.lease_live_ok": ("Live lease covers the longest course", None),
    "land.longest_course_years": ("Longest course duration", "years"),
    "land.plot_count": ("Land parcels", "count"),
    "land.max_plot_distance_km": ("Maximum distance between plots", "km"),
    "land.plots_ok": ("At most three plots", None),
    "land.distance_ok": ("Plots within 2 km", None),
    "land.contiguous": ("Contiguous plots", None),
    "land.obstacle_count": ("Obstacles on the land", "count"),
    "area.instructional_required": ("Required instructional area", "sq. m"),
    "area.instructional_available": ("Instructional area available", "sq. m"),
    "area.instructional_deficit": ("Instructional area deficit", "sq. m"),
    "area.administrative_required": ("Required administrative area", "sq. m"),
    "area.administrative_available": ("Administrative area available", "sq. m"),
    "area.amenities_required": ("Required amenities area", "sq. m"),
    "area.amenities_available": ("Amenities area available", "sq. m"),
    "area.built_up_required": ("Required built-up area", "sq. m"),
    "area.built_up_available": ("Built-up area available", "sq. m"),
    "area.built_up_deficit": ("Built-up area deficit", "sq. m"),
    "area.circulation_pct": ("Access and circulation", "%"),
    "document.affidavit2.present": ("Affidavit 2 uploaded", None),
    "document.affidavit2.dsc_signed": ("Affidavit 2 digitally signed", None),
    "document.occupancy.valid": ("Occupancy/Completion/Form D valid", None),
    "document.fire_safety.valid": ("Fire Safety Certificate valid", None),
    "document.structural.valid": ("Structural Stability Certificate valid", None),
    "document.structural.required": ("Structural Stability Certificate required", None),
    "document.structural.ok": ("Structural Stability Certificate requirement met", None),
    "document.expired_count": ("Expired documents", "count"),
    "document.unsigned_count": ("Documents without DSC", "count"),
    "document.annexure21.missing_count": ("Missing Annexure-2.1 documents", "count"),
    "computing.pcs": ("Computers", "count"),
    "computing.printers": ("Printers", "count"),
    "computing.bandwidth_mbps": ("Internet bandwidth", "Mbps"),
    "computing.language_lab_pcs": ("Language lab computers", "count"),
    "computing.pc_ratio": ("Students per computer", "students/PC"),
    "computing.pc_ratio_for": ("Students per computer (programme scope)", "students/PC"),
    "computing.pc_ratio_required": ("Required students per computer", "students/PC"),
    "computing.pcs_deficit": ("Computer deficit", "count"),
    "computing.pcs_required": ("Required computers", "count"),
    "computing.printers_required": ("Required printers", "count"),
    "computing.printer_pct": ("Printers as a share of PCs", "%"),
    "computing.bandwidth_required": ("Required bandwidth", "Mbps"),
    "computing.bandwidth_deficit": ("Bandwidth deficit", "Mbps"),
    "computing.language_lab_required": ("Required language lab computers", "count"),
    "computing.language_lab_deficit": ("Language lab computer deficit", "count"),
    "library.titles": ("Library titles", "titles"),
    "library.volumes": ("Library volumes", "volumes"),
    "library.journals": ("Subscribed journals", "journals"),
    "library.reading_room_seats": ("Reading-room seats", "seats"),
    "library.digital_library_pcs": ("Digital library computers", "count"),
    "library.ndl_membership": ("NDL membership", None),
    "library.titles_required": ("Required titles", "titles"),
    "library.volumes_required": ("Required volumes", "volumes"),
    "library.journals_required": ("Required journals", "journals"),
    "library.reading_seats_required": ("Required reading-room seats", "seats"),
    "library.titles_deficit": ("Title deficit", "titles"),
    "library.volumes_deficit": ("Volume deficit", "volumes"),
    "library.journals_deficit": ("Journal deficit", "journals"),
    "library.reading_seats_deficit": ("Reading-seat deficit", "seats"),
    "admissions.max_excess": ("Excess admissions", "seats"),
    "admissions.reduced_enrolment_trigger": ("Reduced-enrolment trigger", None),
    "admissions.average_admission_pct_3y": ("Average admissions (3 years)", "%"),
    "admissions.lowest_admission_pct_5y": ("Lowest admissions (5 years)", "%"),
    "derived.total_intake": ("Approved intake", "seats"),
    "derived.qualified_faculty_pct": ("Qualified faculty share", "%"),
    "derived.built_up_area_per_student": ("Built-up area per student", "sq. m/student"),
    "derived.library_books_per_student": ("Library volumes per student", "volumes/student"),
    "derived.lab_count_per_program": ("Laboratories per programme", "count/programme"),
    "derived.naac_grade_present": ("NAAC grade declared", None),
    "derived.nba_accredited_programs_pct": ("NBA accredited programmes", "%"),
    "derived.mandatory_disclosure_published": ("Mandatory disclosure published", None),
    "derived.document_validity": ("Verified documents valid", None),
    "finance.tuition_fee": ("Tuition fee", "INR/year"),
    "finance.development_fee": ("Development fee", "INR/year"),
    "finance.other_fees": ("Other fees", "INR/year"),
    "finance.balance": ("Declared balance", "INR"),
    "finance.total_annual_fee": ("Total annual fee", "INR/year"),
}
for _flag in _ESSENTIAL_FLAGS:
    _METRIC_METADATA.setdefault(
        f"essential.{_flag}",
        (_flag.replace("_", " ").capitalize(), None),
    )


# --------------------------------------------------------------------------
# Config
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


def load_norm_config(db: Session) -> dict[str, Any]:
    """Load the editable calculator configuration (ratios, area, library)."""
    config: dict[str, Any] = {}
    for row in db.scalars(select(ComplianceConfig)).all():
        if row.key in {
            "fsr_ratios",
            "cadre_ratios",
            "adjunct_caps",
            "area_norms",
            "bandwidth_tiers",
            "library_norms",
            "pc_ratios",
        } and isinstance(row.value, dict):
            config[row.key] = row.value
    return config


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


def _weighted_score_from_weights(
    results: Sequence[tuple[float, bool]],
) -> float:
    """Weighted score where each item already carries its rule weight."""
    earned = 0.0
    possible = 0.0
    for weight, passed in results:
        possible += weight
        if passed:
            earned += weight
    if possible <= 0:
        return 0.0
    return round(earned / possible * 100, 2)


def _rule_weight(rule: ComplianceRule, weights: dict[str, float]) -> float:
    if rule.weight is not None:
        return float(rule.weight)
    return weights.get(rule.severity.value, 0.0)


def _rag_status(
    *,
    failed_critical_count: int,
    score: float,
    breakpoints: dict[str, float],
    mandatory_failed_count: int = 0,
    mandatory_missing_count: int = 0,
) -> ComplianceHealth:
    """Return the monitoring band.

    A failed mandatory rule forces RED. Unassessed mandatory evidence forces
    at least AMBER because no Nil Deficiency conclusion is possible yet.
    """
    if mandatory_failed_count > 0 or failed_critical_count > 0:
        return ComplianceHealth.RED
    if score < breakpoints["red_below"]:
        return ComplianceHealth.RED
    if mandatory_missing_count > 0 or score < breakpoints["amber_below"]:
        return ComplianceHealth.AMBER
    return ComplianceHealth.GREEN


# --------------------------------------------------------------------------
# Context and metric extraction
# --------------------------------------------------------------------------


@dataclass
class RuleContext:
    """Everything a rule may read, loaded once per evaluation."""

    data: ApplicationData
    institution: Institution | None = None
    programmes: list[Programme] = field(default_factory=list)
    faculty: list[Faculty] = field(default_factory=list)
    ledger: list[ApprovedIntakeLedger] = field(default_factory=list)
    documents: list[Document] = field(default_factory=list)
    deposits: list[SecurityDeposit] = field(default_factory=list)
    required_documents: list[RequiredDocument] = field(default_factory=list)
    reference_date: date = field(default_factory=lambda: datetime.now(UTC).date())
    metrics: dict[str, MetricValue] = field(default_factory=dict)
    programme_inputs: list[calc.ProgrammeInput] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    """Editable calculator configuration loaded from ``ComplianceConfig``."""


def _numeric(value: object | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _programme_inputs(programmes: Iterable[Programme]) -> list[calc.ProgrammeInput]:
    inputs: list[calc.ProgrammeInput] = []
    for programme in programmes:
        inputs.append(
            calc.ProgrammeInput(
                family=getattr(programme, "programme_family", "Engineering"),
                level=getattr(programme, "level", "UG"),
                intake=int(getattr(programme, "approved_intake", 0) or 0),
                duration_years=float(getattr(programme, "duration_years", 4) or 4),
                divisions=int(getattr(programme, "divisions", 1) or 1),
                course_name=str(getattr(programme, "course_name", "") or ""),
            )
        )
    return inputs


def _application_programme_inputs(
    programmes: Iterable[ApplicationProgram],
) -> list[calc.ProgrammeInput]:
    inputs: list[calc.ProgrammeInput] = []
    for programme in programmes:
        level = str(getattr(programme, "level", "UG") or "UG")
        duration = 4.0 if level.upper() == "UG" else 2.0 if level.upper() == "PG" else 3.0
        name = str(getattr(programme, "program_name", "") or "")
        inputs.append(
            calc.ProgrammeInput(
                family=_family_from_name(name),
                level=level,
                intake=int(getattr(programme, "intake", 0) or 0),
                duration_years=duration,
                divisions=max(1, int(getattr(programme, "intake", 0) or 0) // 60),
                course_name=name,
            )
        )
    return inputs


def _family_from_name(name: str) -> str:
    lowered = name.lower()
    if any(
        token in lowered
        for token in (
            "management",
            "mba",
            "bba",
            "pgdm",
            "business administration",
            "business admin",
        )
    ):
        return calc.MANAGEMENT
    if any(token in lowered for token in ("computer application", "mca", "bca")):
        return calc.COMPUTER_APPLICATIONS
    if "planning" in lowered:
        return calc.PLANNING
    if "design" in lowered:
        return calc.DESIGN
    if any(token in lowered for token in ("hotel", "hmct", "catering")):
        return calc.HMCT
    return calc.ENGINEERING


def build_rule_context(
    db: Session,
    application: Application,
    data: ApplicationData,
    *,
    reference_date: date | None = None,
    documents: Sequence[Document] | None = None,
) -> RuleContext:
    """Load every record the extractors need for one application."""
    institution = application.institution
    if institution is None:
        institution = db.get(Institution, application.institution_id)
    programmes: list[Programme] = []
    faculty: list[Faculty] = []
    deposits: list[SecurityDeposit] = []
    if institution is not None:
        programmes = list(institution.programmes)
        faculty = list(institution.faculty)
        deposits = list(institution.security_deposits)
    ledger = [row for programme in programmes for row in programme.intake_ledger]
    document_list = list(documents) if documents is not None else list(application.documents)
    required = list(
        db.scalars(
            select(RequiredDocument).where(
                RequiredDocument.application_type == application.application_type,
                RequiredDocument.mandatory.is_(True),
            )
        ).all()
    )
    reference = reference_date or datetime.now(UTC).date()
    config = load_norm_config(db)
    programme_inputs = _programme_inputs(programmes)
    if not programme_inputs:
        # Fall back to the programmes requested on the application when the
        # institution's approved-programme ledger has not been populated yet.
        programme_inputs = _application_programme_inputs(list(application.programs))
    context = RuleContext(
        data=data,
        institution=institution,
        programmes=programmes,
        faculty=faculty,
        ledger=ledger,
        documents=document_list,
        deposits=deposits,
        required_documents=required,
        reference_date=reference,
        programme_inputs=programme_inputs,
        config=config,
    )
    context.metrics = _build_metrics(
        data,
        programmes=programmes,
        application_programmes=list(application.programs),
        programme_inputs=context.programme_inputs,
        faculty=faculty,
        ledger=ledger,
        documents=document_list,
        required_documents=required,
        institution=institution,
        deposits=deposits,
        reference_date=reference,
        config=config,
    )
    return context


def application_metric_values(
    data: ApplicationData,
    *,
    programs: Iterable[ApplicationProgram] = (),
    documents: Iterable[Document] = (),
    document_reference_date: date | None = None,
    institution: Institution | None = None,
    approved_programmes: Iterable[Programme] = (),
    faculty_members: Iterable[Faculty] = (),
    intake_ledger: Iterable[ApprovedIntakeLedger] = (),
    security_deposits: Iterable[SecurityDeposit] = (),
    required_documents: Iterable[RequiredDocument] = (),
    config: Mapping[str, Any] | None = None,
) -> dict[str, MetricValue]:
    """Return every metric a rule can reference for the given data.

    The keyword arguments are additive so existing callers keep working:
    ``programs`` are the requested ``ApplicationProgram`` rows, while
    ``approved_programmes``/``faculty_members``/``intake_ledger`` are the
    authoritative records used by the real APH calculators.
    """
    reference = document_reference_date or datetime.now(UTC).date()
    application_programmes = list(programs)
    approved = list(approved_programmes)
    if approved:
        programme_inputs = _programme_inputs(approved)
    else:
        programme_inputs = _application_programme_inputs(application_programmes)
    return _build_metrics(
        data,
        programmes=approved,
        application_programmes=application_programmes,
        programme_inputs=programme_inputs,
        faculty=list(faculty_members),
        ledger=list(intake_ledger),
        documents=list(documents),
        required_documents=list(required_documents),
        institution=institution,
        deposits=list(security_deposits),
        reference_date=reference,
        config=config or {},
    )


def _build_metrics(
    data: ApplicationData,
    *,
    programmes: Sequence[Programme],
    application_programmes: Sequence[ApplicationProgram] = (),
    programme_inputs: Sequence[calc.ProgrammeInput],
    faculty: Sequence[Faculty],
    ledger: Sequence[ApprovedIntakeLedger],
    documents: Sequence[Document],
    required_documents: Sequence[RequiredDocument],
    institution: Institution | None,
    deposits: Sequence[SecurityDeposit],
    reference_date: date,
    config: Mapping[str, Any],
) -> dict[str, MetricValue]:
    """Compute raw and derived metrics; missing inputs stay ``None``."""
    infrastructure = data.infrastructure
    faculty_section = data.faculty
    finance = data.finance
    infra_profile = dict(institution.infra_profile or {}) if institution else {}
    library_profile = dict(institution.library_profile or {}) if institution else {}
    computing_profile = dict(institution.computing_profile or {}) if institution else {}
    essential_profile = dict(institution.essential_requirements or {}) if institution else {}
    campus_profile = dict(institution.campus or {}) if institution else {}

    metrics: dict[str, MetricValue] = {
        "infrastructure.land_area": _numeric(
            infrastructure.land_area if infrastructure else None
        ),
        "infrastructure.built_up_area": _numeric(
            infrastructure.built_up_area if infrastructure else None
        ),
        "infrastructure.labs": _numeric(infrastructure.labs if infrastructure else None),
        "infrastructure.library": _numeric(infrastructure.library if infrastructure else None),
        "infrastructure.hostel": _numeric(infrastructure.hostel if infrastructure else None),
        "faculty.total": _numeric(faculty_section.total if faculty_section else None),
        "faculty.professors": _numeric(
            faculty_section.professors if faculty_section else None
        ),
        "faculty.associate_professors": _numeric(
            faculty_section.associate_professors if faculty_section else None
        ),
        "faculty.assistant_professors": _numeric(
            faculty_section.assistant_professors if faculty_section else None
        ),
        "faculty.student_faculty_ratio": _numeric(
            faculty_section.student_faculty_ratio if faculty_section else None
        ),
        "faculty.phd_faculty_ratio": _numeric(
            faculty_section.phd_faculty_ratio if faculty_section else None
        ),
        "finance.tuition_fee": _numeric(finance.tuition_fee if finance else None),
        "finance.development_fee": _numeric(finance.development_fee if finance else None),
        "finance.other_fees": _numeric(finance.other_fees if finance else None),
        "finance.balance": _numeric(finance.balance if finance else None),
    }

    # Faculty -------------------------------------------------------------
    metrics.update(
        _faculty_metrics(
            faculty,
            programme_inputs,
            faculty_section,
            ledger,
            reference_date,
            config,
            essential_profile,
        )
    )

    # Areas and land ------------------------------------------------------
    metrics.update(
        _area_metrics(
            infrastructure,
            infra_profile,
            campus_profile,
            programme_inputs,
            institution,
            config,
        )
    )

    # Documents -----------------------------------------------------------
    metrics.update(
        _document_metrics(
            documents,
            required_documents,
            reference_date,
            institution,
        )
    )

    # Computing and library ----------------------------------------------
    metrics.update(
        _computing_metrics(
            computing_profile,
            programme_inputs,
            config,
        )
    )
    metrics.update(_library_metrics(library_profile, programme_inputs, config))

    # Essential requirements ---------------------------------------------
    for flag in _ESSENTIAL_FLAGS:
        value = essential_profile.get(flag)
        metrics[f"essential.{flag}"] = bool(value) if value is not None else None

    # Admissions ----------------------------------------------------------
    metrics.update(_admission_metrics(ledger, institution))

    # Legacy derived metrics ---------------------------------------------
    metrics.update(
        _derived_metrics(
            data,
            programmes=programmes,
            application_programmes=application_programmes,
            programme_inputs=programme_inputs,
            documents=documents,
            institution=institution,
            reference_date=reference_date,
        )
    )

    # Security deposits are exposed for future deposit rules.
    metrics["security_deposit.count"] = len(deposits)
    return metrics


def _active_faculty(faculty: Sequence[Faculty], reference_date: date) -> list[Faculty]:
    return [
        member
        for member in faculty
        if getattr(member, "left_on", None) is None
        or (member.left_on is not None and member.left_on >= reference_date)
    ]


def _head_vacancy_months(
    faculty: Sequence[Faculty],
    essential_profile: Mapping[str, Any],
    reference_date: date,
) -> MetricValue:
    """Months the Principal/Director post has been vacant (APH 7.4b).

    An explicit ``principal_vacancy_months`` in the institution profile wins.
    Otherwise a filled post is zero and an empty post is measured from the most
    recent departure. With no roster evidence at all the value stays missing.
    """
    override = essential_profile.get("principal_vacancy_months")
    if override is not None:
        try:
            return max(0.0, float(override))
        except (TypeError, ValueError):
            return None
    heads = [
        member
        for member in faculty
        if member.cadre == FacultyCadre.PRINCIPAL_DIRECTOR
        and (member.left_on is None or member.left_on >= reference_date)
    ]
    if heads:
        return 0.0
    departures = [
        member.left_on
        for member in faculty
        if member.cadre == FacultyCadre.PRINCIPAL_DIRECTOR
        and member.left_on is not None
        and member.left_on <= reference_date
    ]
    if not departures:
        return None
    days = (reference_date - max(departures)).days
    return round(max(0, days) / 30.44, 2)


def _faculty_metrics(
    faculty: Sequence[Faculty],
    programme_inputs: Sequence[calc.ProgrammeInput],
    faculty_section: Any,
    ledger: Sequence[ApprovedIntakeLedger],
    reference_date: date,
    config: Mapping[str, Any] | None = None,
    essential_profile: Mapping[str, Any] | None = None,
) -> dict[str, MetricValue]:
    active = _active_faculty(faculty, reference_date)
    average_admission = _average_admission_pct(ledger)
    options = config or {}
    fsr_ratios = options.get("fsr_ratios")
    cadre_ratios = options.get("cadre_ratios")
    requirement = calc.faculty_requirement(
        programme_inputs,
        average_admission_pct=average_admission,
        fsr_ratios=fsr_ratios,
        cadre_ratios=cadre_ratios,
    )
    total_required = requirement.total_required
    allowance = calc.adjunct_allowance(
        requirement, caps=options.get("adjunct_caps")
    )
    metrics: dict[str, MetricValue] = {
        "faculty.required_total": float(total_required),
        "faculty.adjunct_allowed": float(allowance["cap"]),
        "faculty.prof_of_practice_min": float(
            allowance["min_professors_of_practice"]
        ),
    }

    counts = {
        FacultyCadre.PROFESSOR: 0,
        FacultyCadre.ASSOC_PROFESSOR: 0,
        FacultyCadre.ASST_PROFESSOR: 0,
        FacultyCadre.PRINCIPAL_DIRECTOR: 0,
        FacultyCadre.HOD: 0,
        FacultyCadre.PROF_OF_PRACTICE: 0,
        FacultyCadre.ADJUNCT: 0,
    }
    for member in active:
        counts[member.cadre] = counts.get(member.cadre, 0) + 1
    active_total = len(active)

    # Annexure-5 places the Principal/Director in the first Professor slot, so the
    # head counts towards the Professor tier when checking the 1:2:6 cadre.
    professors_effective = (
        counts[FacultyCadre.PROFESSOR] + counts[FacultyCadre.PRINCIPAL_DIRECTOR]
    )

    if active_total:
        metrics["faculty.total"] = float(active_total)
        metrics["faculty.professors"] = float(professors_effective)
        metrics["faculty.associate_professors"] = float(
            counts[FacultyCadre.ASSOC_PROFESSOR]
        )
        metrics["faculty.assistant_professors"] = float(counts[FacultyCadre.ASST_PROFESSOR])
        metrics["faculty.phd_faculty_ratio"] = round(
            sum(1 for member in active if member.has_phd) / active_total * 100, 2
        )
        adjunct_count = (
            counts[FacultyCadre.ADJUNCT] + counts[FacultyCadre.PROF_OF_PRACTICE]
        )
        pop_count = counts[FacultyCadre.PROF_OF_PRACTICE]
        metrics["faculty.adjunct_count"] = float(adjunct_count)
        metrics["faculty.adjunct_pct"] = round(
            adjunct_count / active_total * 100, 2
        )
        metrics["faculty.adjunct_excess"] = float(
            max(0, adjunct_count - allowance["cap"])
        )
        metrics["faculty.prof_of_practice_count"] = float(pop_count)
        metrics["faculty.prof_of_practice_pct"] = round(
            pop_count / active_total * 100, 2
        )
        metrics["faculty.prof_of_practice_shortfall"] = float(
            max(0, allowance["min_professors_of_practice"] - pop_count)
        )
        regular_count = sum(
            1
            for member in active
            if member.regular
            and member.cadre
            not in {FacultyCadre.ADJUNCT, FacultyCadre.PROF_OF_PRACTICE}
        )
        # Adjunct and Professor-of-Practice posts are governed by the separate
        # 15%/10% rule. They are not "contractual" appointments in the sense of
        # APH 6.14e, so they are excluded from the regular-share denominator;
        # otherwise a compliant institution that also engages Professors of
        # Practice could never reach 100% regular.
        establishment_count = active_total - adjunct_count
        contractual_count = max(0, establishment_count - regular_count)
        metrics["faculty.regular_count"] = float(regular_count)
        metrics["faculty.contractual_count"] = float(contractual_count)
        metrics["faculty.regular_pct"] = (
            round(regular_count / establishment_count * 100, 2)
            if establishment_count
            else None
        )
        metrics["faculty.ecs_pct"] = round(
            sum(1 for member in active if member.salary_via_ecs) / active_total * 100, 2
        )
        metrics["faculty.biometric_pct"] = round(
            sum(1 for member in active if member.biometric) / active_total * 100, 2
        )
        cadre_weights = None
        if len(requirement.groups) == 1:
            family, _, level = next(iter(requirement.groups)).partition("|")
            cadre_weights = calc.cadre_weights_for(family, level, cadre_ratios)
        metrics["faculty.cadre_compliant"] = calc.cadre_compliance(
            professors_effective,
            counts[FacultyCadre.ASSOC_PROFESSOR],
            counts[FacultyCadre.ASST_PROFESSOR],
            total_required,
            weights=cadre_weights or calc.DEFAULT_CADRE_WEIGHTS,
        )
        metrics["faculty.head_present"] = counts[FacultyCadre.PRINCIPAL_DIRECTOR] > 0
        metrics["faculty.hod_present"] = counts[FacultyCadre.HOD] > 0
        metrics["faculty.pg_phd_professor_present"] = any(
            member.has_phd
            and member.cadre
            in {
                FacultyCadre.PROFESSOR,
                FacultyCadre.PRINCIPAL_DIRECTOR,
                FacultyCadre.ASSOC_PROFESSOR,
            }
            for member in active
        )
        lags = []
        for member in active:
            event_date = member.left_on or member.joined_on
            if event_date is not None and member.portal_updated_on is not None:
                lags.append(max(0, (member.portal_updated_on - event_date).days))
        metrics["faculty.id_update_lag_days"] = float(max(lags)) if lags else None
    else:
        # Fall back to the draft totals when the roster has not been imported.
        if faculty_section and faculty_section.total:
            metrics["faculty.cadre_compliant"] = None
            metrics["faculty.head_present"] = None
            metrics["faculty.hod_present"] = None
            metrics["faculty.pg_phd_professor_present"] = None
        for key in (
            "faculty.adjunct_count",
            "faculty.adjunct_pct",
            "faculty.adjunct_excess",
            "faculty.prof_of_practice_count",
            "faculty.prof_of_practice_pct",
            "faculty.prof_of_practice_shortfall",
            "faculty.regular_count",
            "faculty.contractual_count",
            "faculty.regular_pct",
            "faculty.ecs_pct",
            "faculty.biometric_pct",
            "faculty.id_update_lag_days",
        ):
            metrics.setdefault(key, None)

    metrics["faculty.head_vacancy_months"] = _head_vacancy_months(
        faculty, essential_profile or {}, reference_date
    )

    total_students = sum(item.total_intake for item in programme_inputs)
    if active_total and total_students:
        metrics["faculty.fsr"] = round(total_students / active_total, 2)
    else:
        metrics["faculty.fsr"] = None
    return metrics


def _area_metrics(
    infrastructure: Any,
    infra_profile: Mapping[str, Any],
    campus_profile: Mapping[str, Any],
    programme_inputs: Sequence[calc.ProgrammeInput],
    institution: Institution | None,
    config: Mapping[str, Any],
) -> dict[str, MetricValue]:
    area_norms = dict(config.get("area_norms") or {})
    instructional = calc.instructional_area(programme_inputs, config=area_norms)
    built = calc.required_built_up_area(
        instructional["total"],
        administrative_sqm=area_norms.get("administrative_sqm"),
        amenities_sqm=area_norms.get("amenities_sqm"),
        circulation_factor=area_norms.get("circulation_factor"),
    )
    instructional_available = _numeric(
        infra_profile.get("instructional_area_sqm")
        or (infrastructure.built_up_area if infrastructure else None)
    )
    administrative_available = _numeric(infra_profile.get("administrative_area_sqm"))
    amenities_available = _numeric(infra_profile.get("amenities_area_sqm"))
    built_up_available = _numeric(
        infra_profile.get("built_up_sqm")
        or (infrastructure.built_up_area if infrastructure else None)
    )
    circulation = _numeric(infra_profile.get("circulation_area_sqm"))
    metrics: dict[str, MetricValue] = {
        "area.instructional_required": instructional["total"],
        "area.instructional_available": instructional_available,
        "area.instructional_deficit": (
            round(instructional["total"] - instructional_available, 2)
            if instructional_available is not None
            else None
        ),
        "area.administrative_required": built["administrative"],
        "area.administrative_available": administrative_available,
        "area.amenities_required": built["amenities"],
        "area.amenities_available": amenities_available,
        "area.built_up_required": built["total"],
        "area.built_up_available": built_up_available,
        "area.built_up_deficit": (
            round(built["total"] - built_up_available, 2)
            if built_up_available is not None
            else None
        ),
        "area.circulation_pct": (
            round(
                circulation
                / (instructional["total"] + built["administrative"] + built["amenities"])
                * 100,
                2,
            )
            if circulation is not None
            else None
        ),
    }

    # Land -----------------------------------------------------------------
    plots = list(campus_profile.get("plots") or [])
    has_campus_data = bool(campus_profile) and (
        bool(plots) or campus_profile.get("gap_km") is not None
    )
    plot_info = calc.plot_compliance(
        plots,
        contiguous=campus_profile.get("contiguous"),
        obstacles=campus_profile.get("obstacles") or [],
    )
    if not has_campus_data:
        # No campus geometry declared: report the land checks as unassessed
        # rather than failing an institution that never answered the profile.
        metrics.update(
            {
                "land.plot_count": None,
                "land.max_plot_distance_km": None,
                "land.plots_ok": None,
                "land.distance_ok": None,
                "land.contiguous": None,
                "land.obstacle_count": None,
            }
        )
    else:
        max_distance = plot_info["max_distance_km"]
        if campus_profile.get("gap_km") is not None:
            max_distance = max(max_distance, float(campus_profile["gap_km"]))
        metrics.update(
            {
                "land.plot_count": float(plot_info["plot_count"]),
                "land.max_plot_distance_km": max_distance,
                "land.plots_ok": bool(plot_info["plots_ok"]),
                "land.distance_ok": max_distance <= 2.0,
                "land.contiguous": bool(plot_info["contiguous"]),
                "land.obstacle_count": float(plot_info["obstacle_count"]),
            }
        )
    total_lease = (
        institution.lease_years_total if institution is not None else None
    )
    live_lease = institution.lease_years_live if institution is not None else None
    ownership = (
        institution.land_ownership.value if institution is not None else None
    )
    longest = calc.longest_course_duration(programme_inputs)
    lease_info = calc.lease_checks(
        land_ownership=ownership,
        lease_years_total=total_lease,
        lease_years_live=live_lease,
        longest_course_years=longest,
    )
    metrics.update(
        {
            "land.lease_years_total": _numeric(total_lease),
            "land.lease_years_live": _numeric(live_lease),
            "land.longest_course_years": float(longest),
            "land.tenure_ok": bool(lease_info["tenure_ok"])
            if ownership is not None
            else None,
            "land.title_ok": bool(lease_info["title_ok"]) if ownership else None,
            "land.lease_ok": bool(lease_info["lease_ok"])
            if ownership is not None
            else None,
            "land.lease_tenure_ok": bool(lease_info["total_ok"])
            if ownership is not None
            else None,
            "land.lease_live_ok": bool(lease_info["live_ok"])
            if ownership is not None
            else None,
        }
    )
    return metrics


def _document_index(documents: Sequence[Document]) -> dict[str, Document]:
    index: dict[str, Document] = {}
    for document in documents:
        for key in (document.doc_code, document.doc_type):
            if key:
                index.setdefault(str(key).upper(), document)
    return index


def _document_is_valid(document: Document, reference_date: date) -> bool:
    if document.verification_status in (
        DocumentVerificationStatus.REJECTED,
        DocumentVerificationStatus.FLAGGED,
    ):
        return False
    valid_until = document.valid_until or document.expiry_date
    return valid_until is None or valid_until >= reference_date


def _document_condition_applies(
    expression: str | None, values: Mapping[str, Any]
) -> bool:
    """Evaluate a simple, safe document-condition expression.

    Seeded conditions are of the form ``name == 'VALUE'`` or ``name >= 30``.
    Anything that cannot be evaluated keeps the document required, which is the
    conservative choice: an unparsed condition must never excuse a mandatory
    upload.
    """
    if not expression or not expression.strip():
        return True
    for operator in (">=", "<=", "==", "!=", ">", "<"):
        if operator in expression:
            name, _, raw = expression.partition(operator)
            break
    else:
        return True
    name = name.strip()
    raw = raw.strip()
    if name not in values or values[name] is None:
        return True
    actual = values[name]
    if hasattr(actual, "value"):
        actual = actual.value
    lowered = raw.lower()
    if lowered in {"true", "false"}:
        expected: Any = lowered == "true"
    else:
        expected = raw.strip("'\"")
        if isinstance(actual, (int, float)):
            try:
                expected = float(expected)
            except ValueError:
                return True
    try:
        if operator == ">=":
            return actual >= expected
        if operator == "<=":
            return actual <= expected
        if operator == ">":
            return actual > expected
        if operator == "<":
            return actual < expected
        if operator == "!=":
            return actual != expected
        return actual == expected
    except TypeError:
        return True


def _document_metrics(
    documents: Sequence[Document],
    required_documents: Sequence[RequiredDocument],
    reference_date: date,
    institution: Institution | None = None,
) -> dict[str, MetricValue]:
    index = _document_index(documents)
    metrics: dict[str, MetricValue] = {}

    def valid(code: str) -> MetricValue:
        document = index.get(code)
        if document is None:
            return None
        return _document_is_valid(document, reference_date)

    affidavit2 = index.get("AFFIDAVIT_2")
    metrics["document.affidavit2.present"] = affidavit2 is not None
    metrics["document.affidavit2.dsc_signed"] = (
        bool(affidavit2.signed_with_dsc) if affidavit2 is not None else None
    )
    metrics["document.occupancy.valid"] = valid("OCCUPANCY_CERTIFICATE")
    metrics["document.fire_safety.valid"] = valid("FIRE_SAFETY_CERTIFICATE")

    infra_profile = dict(institution.infra_profile or {}) if institution else {}
    completion_year = infra_profile.get("building_completion_year")
    structural_required = (
        calc.structural_certificate_required(int(completion_year), reference_date)
        if completion_year is not None
        else None
    )
    structural_doc = index.get("STRUCTURAL_STABILITY_CERTIFICATE")
    structural_valid: MetricValue = (
        _document_is_valid(structural_doc, reference_date)
        if structural_doc is not None
        else None
    )
    metrics["document.structural.required"] = structural_required
    metrics["document.structural.valid"] = structural_valid
    if structural_required is False:
        metrics["document.structural.ok"] = True
    elif structural_required is None and structural_doc is None:
        metrics["document.structural.ok"] = None
    else:
        metrics["document.structural.ok"] = bool(structural_valid)

    metrics["document.expired_count"] = float(
        sum(
            1
            for document in documents
            if (document.valid_until or document.expiry_date) is not None
            and (document.valid_until or document.expiry_date) < reference_date
        )
    )
    metrics["document.unsigned_count"] = float(
        sum(1 for document in documents if not document.signed_with_dsc)
    )

    uploaded_codes = {
        str(value).upper()
        for document in documents
        for value in (document.doc_code, document.doc_type)
        if value
    }
    completion_year = infra_profile.get("building_completion_year")
    condition_values = {
        "land_ownership": getattr(institution, "land_ownership", None),
        "building_age_years": (
            reference_date.year - int(completion_year)
            if completion_year is not None
            else None
        ),
    }
    applicable = [
        requirement
        for requirement in required_documents
        if _document_condition_applies(
            getattr(requirement, "condition_expr", None), condition_values
        )
    ]
    missing = [
        requirement
        for requirement in applicable
        if (requirement.doc_code or requirement.doc_type).upper() not in uploaded_codes
    ]
    metrics["document.annexure21.missing_count"] = (
        float(len(missing)) if applicable else None
    )
    metrics["document.annexure21.missing_codes"] = ",".join(
        sorted((requirement.doc_code or requirement.doc_type) for requirement in missing)
    )
    return metrics


def _computing_metrics(
    computing_profile: Mapping[str, Any],
    programme_inputs: Sequence[calc.ProgrammeInput],
    config: Mapping[str, Any],
) -> dict[str, MetricValue]:
    requirements = calc.pc_requirement(
        programme_inputs, pc_ratios=config.get("pc_ratios")
    )
    pcs = _numeric(computing_profile.get("pcs"))
    printers = _numeric(computing_profile.get("printers"))
    bandwidth = _numeric(computing_profile.get("bandwidth_mbps"))
    language_pcs = _numeric(computing_profile.get("language_lab_pcs"))
    annual_intake = sum(programme.intake for programme in programme_inputs)
    metrics: dict[str, MetricValue] = {
        "computing.pcs": pcs,
        "computing.printers": printers,
        "computing.bandwidth_mbps": bandwidth,
        "computing.language_lab_pcs": language_pcs,
        "computing.pcs_required": float(requirements["pcs"]),
        "computing.printers_required": float(requirements["printers"]),
        "computing.printer_pct": (
            round(printers / pcs * 100, 2) if pcs and printers is not None else None
        ),
        "computing.bandwidth_required": float(
            calc.bandwidth_requirement(annual_intake, config.get("bandwidth_tiers"))
        ),
        "computing.language_lab_required": float(requirements["language_lab_pcs"]),
    }
    metrics["computing.bandwidth_deficit"] = (
        round(metrics["computing.bandwidth_required"] - bandwidth, 2)
        if bandwidth is not None
        else None
    )
    metrics["computing.language_lab_deficit"] = (
        round(requirements["language_lab_pcs"] - language_pcs, 2)
        if language_pcs is not None
        else None
    )
    total_students = sum(programme.total_intake for programme in programme_inputs)
    metrics["computing.pc_ratio"] = (
        round(total_students / pcs, 2) if pcs and total_students else None
    )
    metrics["computing.pcs_deficit"] = (
        round(requirements["pcs"] - pcs, 2) if pcs is not None else None
    )
    return metrics


def _library_metrics(
    library_profile: Mapping[str, Any],
    programme_inputs: Sequence[calc.ProgrammeInput],
    config: Mapping[str, Any],
) -> dict[str, MetricValue]:
    requirements = calc.library_requirement(
        programme_inputs, config=config.get("library_norms")
    )
    titles = _numeric(library_profile.get("titles"))
    volumes = _numeric(library_profile.get("volumes"))
    journals = _numeric(library_profile.get("journals"))
    seats = _numeric(library_profile.get("reading_room_seats"))
    metrics: dict[str, MetricValue] = {
        "library.titles": titles,
        "library.volumes": volumes,
        "library.journals": journals,
        "library.reading_room_seats": seats,
        "library.digital_library_pcs": _numeric(
            library_profile.get("digital_library_pcs")
        ),
        "library.ndl_membership": bool(library_profile.get("ndl_membership"))
        if library_profile.get("ndl_membership") is not None
        else None,
        "library.titles_required": requirements["titles"],
        "library.volumes_required": requirements["volumes"],
        "library.journals_required": requirements["journals"],
        "library.reading_seats_required": requirements["reading_seats"],
    }
    for key, available_key, required_key in (
        ("titles_deficit", "library.titles", "library.titles_required"),
        ("volumes_deficit", "library.volumes", "library.volumes_required"),
        ("journals_deficit", "library.journals", "library.journals_required"),
        (
            "reading_seats_deficit",
            "library.reading_room_seats",
            "library.reading_seats_required",
        ),
    ):
        available = metrics[available_key]
        metrics[f"library.{key}"] = (
            round(float(metrics[required_key]) - float(available), 2)
            if available is not None
            else None
        )
    return metrics


def _average_admission_pct(ledger: Sequence[ApprovedIntakeLedger]) -> float | None:
    rows = [row for row in ledger if row.approved_intake]
    if not rows:
        return None
    percentages = [
        row.admitted_total / row.approved_intake * 100 for row in rows[-3:]
    ]
    return round(sum(percentages) / len(percentages), 2) if percentages else None


def _admission_metrics(
    ledger: Sequence[ApprovedIntakeLedger],
    institution: Institution | None,
) -> dict[str, MetricValue]:
    rows = [
        {
            "academic_year": row.academic_year,
            "approved_intake": row.approved_intake,
            "admitted_total": row.admitted_total,
            "fn_oci": row.fn_oci,
            "lateral": row.lateral,
        }
        for row in ledger
    ]
    excess = calc.excess_admission(rows)
    reduced = calc.reduced_enrolment_trigger(rows)
    average = _average_admission_pct(ledger)
    percentages = [
        row["admitted_total"] / row["approved_intake"] * 100
        for row in rows
        if row["approved_intake"]
    ]
    essential = (
        dict(institution.essential_requirements or {}) if institution else {}
    )
    return {
        "admissions.max_excess": float(excess["max_excess"]),
        "admissions.reduced_enrolment_trigger": bool(reduced["trigger"]),
        "admissions.average_admission_pct_3y": average,
        "admissions.lowest_admission_pct_5y": (
            round(min(percentages), 2) if percentages else None
        ),
        "essential.enrolment_uploaded": (
            bool(essential.get("enrolment_uploaded"))
            if essential.get("enrolment_uploaded") is not None
            else None
        ),
    }


def _derived_metrics(
    data: ApplicationData,
    *,
    programmes: Sequence[Programme],
    application_programmes: Sequence[ApplicationProgram] = (),
    programme_inputs: Sequence[calc.ProgrammeInput],
    documents: Sequence[Document],
    institution: Institution | None,
    reference_date: date,
) -> dict[str, MetricValue]:
    infrastructure = data.infrastructure
    faculty = data.faculty
    finance = data.finance
    # ``derived.total_intake`` is the annual approved intake (seats admitted in
    # one academic year). The S used by the faculty calculator sums the intake
    # across every year of the programme, which lives on ``ProgrammeInput``.
    annual_intake = sum(programme.intake for programme in programme_inputs)
    total_intake = annual_intake
    derived: dict[str, MetricValue] = {
        "derived.total_intake": float(annual_intake) if programme_inputs else None,
    }
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
    lab_counts = [
        float(getattr(programme, "lab_count", 0) or 0)
        for programme in application_programmes
    ]
    if lab_counts:
        derived["derived.lab_count_per_program"] = round(
            sum(lab_counts) / len(lab_counts), 2
        )
    elif programmes:
        derived["derived.lab_count_per_program"] = round(
            sum(float(getattr(programme, "divisions", 1) or 1) for programme in programmes)
            / len(programmes),
            2,
        )
    else:
        derived["derived.lab_count_per_program"] = None
    accreditation = data.accreditation
    if accreditation is None:
        derived["derived.naac_grade_present"] = None
        derived["derived.nba_accredited_programs_pct"] = None
    else:
        naac = accreditation.naac_grade
        derived["derived.naac_grade_present"] = (
            1.0 if (naac is not None and naac != "NOT_ACCREDITED") else 0.0
        )
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
    derived["derived.document_validity"] = _document_validity(documents, reference_date)
    if institution is not None:
        derived["institution.established_year"] = float(institution.established_year)
    return derived


def _document_validity(
    documents: Sequence[Document],
    reference_date: date | None,
) -> float | None:
    """1.0 when every uploaded document is valid, 0.0 when any is not."""
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

    ``applies_to`` is a comma-separated list of application types, programme
    levels or ``ALL``. ``applies_to_family`` and ``applies_to_level`` narrow a
    rule to one programme family/level without changing the application type.
    """
    targets = {
        target.strip().upper()
        for target in (rule.applies_to or "ALL").split(",")
        if target.strip()
    }
    if "ALL" not in targets:
        if str(application.application_type).upper() not in targets and not any(
            str(program.level).strip().upper() in targets
            for program in application.programs
        ):
            return False
    family = (rule.applies_to_family or "").strip().upper()
    level = (rule.applies_to_level or "").strip().upper()
    if not family and not level:
        return True
    for programme in application.programs:
        if family and _family_from_name(programme.program_name) != calc.normalise_family(family):
            continue
        if level and calc.normalise_level(programme.level) != calc.normalise_level(level):
            continue
        return True
    return False


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
    if operator == "DATE_NOT_EXPIRED":
        return "a certificate that has not expired"
    phrase = _OPERATOR_PHRASES.get(operator, operator.lower())
    return f"{phrase} {_format_number(threshold)}{suffix}"


def _rule_message(
    *,
    metric_key: str,
    operator: str,
    comparison: str,
    threshold: Decimal,
    threshold_max: Decimal | None,
    observed: Decimal | None,
    unit: str | None,
    passed: bool,
) -> str:
    """Explain the outcome, e.g. "Faculty:student ratio: 27 against at most 20"."""
    label, default_unit = _metric_label(metric_key)
    suffix = f" {unit or default_unit}" if (unit or default_unit) else ""
    if operator == "EXISTS":
        if metric_key.endswith(".valid"):
            outcome = "valid on the reference date" if passed else "missing, expired or rejected"
            return f"{label}: {outcome}."
        return f"{label}: {'present' if passed else 'not present'}."
    if operator == "DATE_NOT_EXPIRED":
        return f"{label}: {'valid on the reference date' if passed else 'missing or expired'}."
    if observed is None:
        return _not_assessed_message(metric_key)
    if operator == "BETWEEN" or comparison == "BETWEEN":
        expected = _threshold_text("BETWEEN", threshold, threshold_max, unit or default_unit)
        return f"{label}: {_format_number(observed)}{suffix}; expected {expected}."
    expected = _threshold_text(comparison, threshold, None, unit or default_unit)
    result = "meets" if passed else "does not meet"
    return (
        f"{label}: {_format_number(observed)}{suffix}; {result} the requirement "
        f"of {expected}."
    )


def _template_result(status: ComplianceRuleStatus) -> str:
    """Plain-language outcome for ``{result}`` in explanation templates."""
    if status == "PASS":
        return "compliant"
    if status == "FAIL":
        return "not compliant"
    return "not assessed"


def _format_template(
    rule: ComplianceRule,
    *,
    observed: Decimal | None,
    threshold: Decimal,
    unit: str | None,
    result: str = "",
) -> str | None:
    if not rule.explanation_template:
        return None
    values = {
        "observed": _format_number(observed) if observed is not None else "data missing",
        "threshold": _format_number(threshold),
        "unit": unit or "",
        "clause": rule.apH_clause,
        "name": rule.name,
        "code": rule.code,
        "result": result,
    }
    try:
        return rule.explanation_template.format(**values)
    except (KeyError, IndexError, ValueError):
        return rule.explanation_template


def _rule_explanation(
    rule: ComplianceRule,
    *,
    status: ComplianceRuleStatus,
    observed_value: float | None,
    threshold: Decimal,
    threshold_max: Decimal | None,
    unit: str | None,
    message: str,
    extra: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the evidence and the criteria/values/pass-fail explanation."""
    observed = float(observed_value) if observed_value is not None else None
    bounds = {
        "operator": rule.operator,
        "threshold": float(threshold),
        "threshold_max": float(threshold_max) if threshold_max is not None else None,
        "unit": unit,
    }
    evidence = {
        "metric_key": rule.metric_key,
        "observed_value": observed,
        **bounds,
        **dict(extra or {}),
    }
    suggestions = suggestions_for_codes(rule.penalty_codes or [])
    explanation = {
        "criteria": rule.description,
        "metric_key": rule.metric_key,
        "observed_value": observed,
        **bounds,
        "status": status,
        "passed": None if status == "NOT_ASSESSED" else status == "PASS",
        "apH_clause": rule.apH_clause,
        "needs_verification": rule.needs_verification,
        "mandatory": rule.mandatory,
        "illustrative": rule.illustrative,
        "message": message,
        "penalty_codes": list(rule.penalty_codes or []),
        "penal_action_suggestions": [
            {
                "violation_code": suggestion.violation_code,
                "violation": suggestion.violation,
                "action": suggestion.action.value,
                "action_label": suggestion.action_label,
                "apH_clause": suggestion.apH_clause,
                "suggests_only": suggestion.suggests_only,
                "hearing_required": suggestion.hearing_required,
            }
            for suggestion in suggestions
        ],
        **dict(extra or {}),
    }
    return evidence, explanation


def _metric_for_scope(
    metrics: Mapping[str, MetricValue],
    metric_key: str,
    params: Mapping[str, Any],
) -> MetricValue:
    """Resolve family/level-scoped metrics such as ``faculty.fsr_for``."""
    family = calc.normalise_family(params.get("family")) if params.get("family") else None
    level = calc.normalise_level(params.get("level")) if params.get("level") else None
    if metric_key in {"faculty.fsr_for", "faculty.required_for", "faculty.cadre_compliant_for"}:
        scope = metrics.get("_scope", {})
        key = f"{family}|{level}"
        scoped = scope.get(key) if isinstance(scope, dict) else None
        if not isinstance(scoped, dict):
            if family or level:
                # The application has no programme in this scope, so the
                # scoped metric is genuinely unassessed.
                return None
            # Fall back to the whole-institution value when no scope was built.
            return metrics.get(
                {
                    "faculty.fsr_for": "faculty.fsr",
                    "faculty.required_for": "faculty.required_total",
                    "faculty.cadre_compliant_for": "faculty.cadre_compliant",
                }[metric_key]
            )
        mapping = {
            "faculty.fsr_for": "fsr",
            "faculty.required_for": "required",
            "faculty.cadre_compliant_for": "cadre_compliant",
        }
        return scoped.get(mapping[metric_key])
    if metric_key in {"computing.pc_ratio_for", "computing.pc_ratio_required_for"}:
        scope = metrics.get("_scope", {})
        key = f"{family}|{level}"
        scoped = scope.get(key) if isinstance(scope, dict) else None
        if not isinstance(scoped, dict):
            if family or level:
                return None
            return metrics.get(
                "computing.pc_ratio"
                if metric_key == "computing.pc_ratio_for"
                else "computing.pc_ratio_required"
            )
        return scoped.get(
            "pc_ratio" if metric_key == "computing.pc_ratio_for" else "pc_ratio_required"
        )
    return metrics.get(metric_key)


def _resolve_observed(
    rule: ComplianceRule,
    metrics: Mapping[str, MetricValue],
    *,
    reference_date: date,
) -> tuple[MetricValue, dict[str, Any]]:
    """Resolve a rule's operand(s) from the metric map.

    Returns ``(value, extra_evidence)``. ``value`` is ``None`` when the data
    needed to evaluate the rule is missing.
    """
    params = rule.metric_params or {}
    if rule.operator == "RATIO":
        numerator_key = params.get("numerator")
        denominator_key = params.get("denominator")
        numerator = (
            _metric_for_scope(metrics, str(numerator_key), params)
            if numerator_key
            else metrics.get(rule.metric_key)
        )
        denominator = (
            _metric_for_scope(metrics, str(denominator_key), params)
            if denominator_key
            else None
        )
        if numerator is None or denominator in (None, 0):
            return None, {
                "numerator": numerator,
                "denominator": denominator,
            }
        value = float(numerator) / float(denominator)
        return round(value, 4), {
            "numerator": numerator,
            "denominator": denominator,
            "ratio": round(value, 4),
        }
    if rule.operator == "SUM":
        keys = params.get("metrics") or [rule.metric_key]
        values = [metrics.get(str(key)) for key in keys]
        if any(value is None for value in values):
            return None, {"summed_metrics": list(keys)}
        return float(sum(float(value) for value in values)), {
            "summed_metrics": list(keys),
            "values": values,
        }
    if rule.operator == "COUNT":
        keys = params.get("metrics") or [rule.metric_key]
        equals = params.get("equals", True)
        values = [metrics.get(str(key)) for key in keys]
        if values and all(value is None for value in values):
            return None, {"counted_metrics": list(keys)}
        count = sum(1 for value in values if value is not None and value == equals)
        return float(count), {"counted_metrics": list(keys)}
    if rule.operator == "DATE_NOT_EXPIRED":
        value = _metric_for_scope(metrics, rule.metric_key, params)
        if value is None:
            return None, {"observed_date": None}
        if isinstance(value, datetime):
            value = value.date()
        if isinstance(value, date):
            return value, {"observed_date": value.isoformat()}
        return None, {"observed_date": value}
    observed = _metric_for_scope(metrics, rule.metric_key, params)
    extra: dict[str, Any] = {}
    if rule.metric_key == "document.annexure21.missing_count":
        codes = metrics.get("document.annexure21.missing_codes")
        if codes:
            extra["missing_document_codes"] = str(codes).split(",")
    return observed, extra


def _evaluate_rule(
    rule: ComplianceRule,
    observed_value: MetricValue,
    *,
    reference_date: date | None = None,
    extra: Mapping[str, Any] | None = None,
) -> ComplianceRulePreview:
    """Evaluate one rule safely; missing data becomes NOT_ASSESSED, never a crash."""
    reference = reference_date or datetime.now(UTC).date()
    unit = rule.unit or _metric_label(rule.metric_key)[1]
    threshold = Decimal(rule.threshold)
    threshold_max = Decimal(rule.threshold_max) if rule.threshold_max is not None else None
    params = rule.metric_params or {}
    comparison_name = str(
        params.get("compare")
        or (
            _DEFAULT_AGGREGATE_COMPARISON.get(rule.operator)
            if rule.operator in _AGGREGATE_OPERATORS
            else rule.operator
        )
    )
    status: ComplianceRuleStatus
    passed = False
    numeric_observed: float | None = None
    if observed_value is None:
        status = "NOT_ASSESSED"
    elif rule.operator == "EXISTS":
        status = "PASS" if bool(observed_value) else "FAIL"
        passed = status == "PASS"
        # Surface presence as 1/0 so the evidence panel and rule preview show a
        # value instead of a blank observed column.
        numeric_observed = 1.0 if passed else 0.0
    elif rule.operator == "DATE_NOT_EXPIRED":
        date_value = observed_value
        if isinstance(date_value, datetime):
            date_value = date_value.date()
        if not isinstance(date_value, date):
            status = "NOT_ASSESSED"
        else:
            passed = date_value >= reference
            status = "PASS" if passed else "FAIL"
            extra = {**dict(extra or {}), "observed_date": date_value.isoformat()}
    else:
        try:
            observed_decimal = Decimal(str(observed_value))
        except Exception:  # noqa: BLE001 - defensive: unknown metric types are missing data
            observed_decimal = None
        if observed_decimal is None:
            status = "NOT_ASSESSED"
        elif rule.operator == "BETWEEN" or comparison_name == "BETWEEN":
            passed = observed_decimal >= threshold and (
                threshold_max is None or observed_decimal <= threshold_max
            )
            status = "PASS" if passed else "FAIL"
            numeric_observed = float(observed_decimal)
        else:
            comparison = _OPERATORS.get(comparison_name)
            passed = bool(comparison and comparison(observed_decimal, threshold))
            status = "PASS" if passed else "FAIL"
            numeric_observed = float(observed_decimal)

    message = _rule_message(
        metric_key=rule.metric_key,
        operator=rule.operator,
        comparison=comparison_name,
        threshold=threshold,
        threshold_max=threshold_max,
        observed=Decimal(str(numeric_observed)) if numeric_observed is not None else None,
        unit=unit,
        passed=passed,
    )
    if status == "NOT_ASSESSED":
        message = _not_assessed_message(rule.metric_key)
    templated = _format_template(
        rule,
        observed=Decimal(str(numeric_observed)) if numeric_observed is not None else None,
        threshold=threshold,
        unit=unit,
        result=_template_result(status),
    )
    if templated and status != "NOT_ASSESSED":
        message = templated

    evidence, explanation = _rule_explanation(
        rule,
        status=status,
        observed_value=numeric_observed,
        threshold=threshold,
        threshold_max=threshold_max,
        unit=unit,
        message=message,
        extra={**dict(extra or {}), "comparison": comparison_name},
    )
    suggestions = suggestions_for_codes(rule.penalty_codes or [])
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
        observed_value=numeric_observed,
        status=status,
        message=message,
        evidence=evidence,
        explanation=explanation,
        apH_clause=rule.apH_clause,
        needs_verification=(
            False if rule.needs_verification is None else bool(rule.needs_verification)
        ),
        mandatory=True if rule.mandatory is None else bool(rule.mandatory),
        illustrative=False if rule.illustrative is None else bool(rule.illustrative),
        weight=float(rule.weight) if rule.weight is not None else None,
        penalty_codes=list(rule.penalty_codes or []),
        penal_action_suggestions=[
            PenalActionSuggestionRead(
                violation_code=suggestion.violation_code,
                violation=suggestion.violation,
                action=suggestion.action.value,
                action_label=suggestion.action_label,
                apH_clause=suggestion.apH_clause,
                suggests_only=suggestion.suggests_only,
                hearing_required=suggestion.hearing_required,
            )
            for suggestion in suggestions
        ],
    )


def load_active_rules(db: Session) -> list[ComplianceRule]:
    """Return every active compliance rule."""
    return list(
        db.scalars(select(ComplianceRule).where(ComplianceRule.is_active.is_(True)))
    )


def _evaluate_rule_from_metrics(
    rule: ComplianceRule,
    metrics: Mapping[str, MetricValue],
    *,
    reference_date: date,
) -> ComplianceRulePreview:
    """Resolve a rule's operands then evaluate it against the reference date."""
    observed, extra = _resolve_observed(rule, metrics, reference_date=reference_date)
    return _evaluate_rule(
        rule,
        observed,
        reference_date=reference_date,
        extra=extra,
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
    context = build_rule_context(
        db,
        application,
        data,
        reference_date=evaluated_at.date(),
        documents=documents,
    )
    context.metrics.update(_scope_metrics(context))
    previews = [
        _evaluate_rule_from_metrics(
            rule,
            context.metrics,
            reference_date=context.reference_date,
        )
        for rule in rules
        if _applies_to_application(rule, application)
    ]
    return _build_preview(db, application=application, previews=previews, evaluated_at=evaluated_at)


def _scope_metrics(context: RuleContext) -> dict[str, MetricValue]:
    """Per-family/level metrics used by scoped rules (FSR, PC ratio)."""
    options = context.config or {}
    fsr_ratios = options.get("fsr_ratios")
    cadre_ratios = options.get("cadre_ratios")
    pc_ratios = options.get("pc_ratios")
    scope: dict[str, dict[str, MetricValue]] = {}
    active = _active_faculty(context.faculty, context.reference_date)
    average_admission = _average_admission_pct(context.ledger)
    total_pcs = (
        _numeric((context.institution.computing_profile or {}).get("pcs"))
        if context.institution
        else None
    )
    requirement = calc.faculty_requirement(
        context.programme_inputs,
        average_admission_pct=average_admission,
        fsr_ratios=fsr_ratios,
        cadre_ratios=cadre_ratios,
    )
    any_mapped = any(member.programme_id is not None for member in active)
    single_group = len(requirement.groups) == 1
    cadre_results: list[bool] = []
    for group in requirement.groups:
        family, level = group.split("|", 1)
        group_inputs = [
            item
            for item in context.programme_inputs
            if item.canonical_family == family and item.canonical_level == level
        ]
        total_intake = sum(item.total_intake for item in group_inputs)
        group_faculty = [
            member
            for member in active
            if member.programme_id is not None
            and any(
                programme.id == member.programme_id
                and calc.normalise_family(programme.programme_family) == family
                and calc.normalise_level(programme.level) == level
                for programme in context.programmes
            )
        ]
        if any_mapped:
            faculty_count: int | None = len(group_faculty)
        elif single_group:
            faculty_count = len(active)
        else:
            faculty_count = None
        group_requirement = calc.faculty_requirement(
            group_inputs,
            average_admission_pct=average_admission,
            fsr_ratios=fsr_ratios,
            cadre_ratios=cadre_ratios,
        )
        required = group_requirement.total_required
        cadre_value: MetricValue = None
        if group_faculty and required:
            cadre_value = calc.cadre_compliance(
                sum(
                    1
                    for member in group_faculty
                    if member.cadre
                    in {FacultyCadre.PROFESSOR, FacultyCadre.PRINCIPAL_DIRECTOR}
                ),
                sum(
                    1
                    for member in group_faculty
                    if member.cadre == FacultyCadre.ASSOC_PROFESSOR
                ),
                sum(
                    1
                    for member in group_faculty
                    if member.cadre == FacultyCadre.ASST_PROFESSOR
                ),
                required,
                weights=calc.cadre_weights_for(family, level, cadre_ratios),
            )
            cadre_results.append(bool(cadre_value))
        scope[group] = {
            "required": float(required),
            "fsr": (
                round(total_intake / faculty_count, 2)
                if faculty_count and total_intake
                else None
            ),
            "cadre_compliant": cadre_value,
            "pc_ratio": (
                round(total_intake / total_pcs, 2) if total_pcs and total_intake else None
            ),
            "pc_ratio_required": (
                float(calc.pc_requirement(group_inputs, pc_ratios=pc_ratios)["pcs"])
                if group_inputs
                else None
            ),
        }
    # The unscoped cadre rule must use the configured R for the institution's
    # programme mix, not the 1:2:6 default.
    aggregate_cadre: MetricValue = None
    if cadre_results:
        aggregate_cadre = all(cadre_results)
    return {"_scope": scope, "faculty.cadre_compliant": aggregate_cadre}


def _nil_deficiency(previews: Sequence[ComplianceRulePreview]) -> bool:
    """A Nil Deficiency result requires every mandatory rule to pass."""
    return not any(
        rule.mandatory and rule.status in {"FAIL", "NOT_ASSESSED"} for rule in previews
    )


def _build_preview(
    db: Session,
    *,
    application: Application,
    previews: list[ComplianceRulePreview],
    evaluated_at: datetime,
) -> CompliancePreviewRead:
    weights, breakpoints = load_compliance_config(db)
    severity_results = [
        (_rule_weight_from_preview(rule, weights), rule.status == "PASS")
        for rule in previews
        if rule.status != "NOT_ASSESSED"
    ]
    score = _weighted_score_from_weights(severity_results)
    failed_count = sum(rule.status == "FAIL" for rule in previews)
    not_assessed_count = sum(rule.status == "NOT_ASSESSED" for rule in previews)
    passed_count = len(previews) - failed_count - not_assessed_count
    failed_critical_count = sum(
        rule.status == "FAIL" and rule.severity == Severity.CRITICAL
        for rule in previews
    )
    mandatory_failed_count = sum(
        rule.mandatory and rule.status == "FAIL" for rule in previews
    )
    mandatory_missing_count = sum(
        rule.mandatory and rule.status == "NOT_ASSESSED" for rule in previews
    )
    status = _rag_status(
        failed_critical_count=failed_critical_count,
        score=score,
        breakpoints=breakpoints,
        mandatory_failed_count=mandatory_failed_count,
        mandatory_missing_count=mandatory_missing_count,
    )
    nil_deficiency = _nil_deficiency(previews)
    if failed_count:
        outcome = "ATTENTION"
    elif mandatory_missing_count or not_assessed_count:
        outcome = "INCOMPLETE"
    else:
        outcome = "PASS"

    previews.sort(
        key=lambda rule: (
            0 if rule.mandatory and rule.status != "PASS" else 1,
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
        mandatory_failed_count=mandatory_failed_count,
        mandatory_missing_count=mandatory_missing_count,
        nil_deficiency=nil_deficiency,
        banner=(
            "Nil Deficiency"
            if nil_deficiency
            else "Not Nil Deficiency: a mandatory requirement failed or is unassessed"
        ),
    )


def _rule_weight_from_preview(
    rule: ComplianceRulePreview, weights: dict[str, float]
) -> float:
    if rule.weight is not None:
        return rule.weight
    return weights.get(rule.severity.value, 0.0)


def _config_for(application: Application) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load config from the owning session of the application, if any."""
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
    """Evaluate, persist per-rule results, the score and a monitoring snapshot."""
    data = ApplicationData.model_validate(application.data or {})
    rules = load_active_rules(db)
    context = build_rule_context(
        db,
        application,
        data,
        reference_date=evaluated_at.date(),
    )
    context.metrics.update(_scope_metrics(context))
    previews_unsorted = [
        _evaluate_rule_from_metrics(
            rule,
            context.metrics,
            reference_date=context.reference_date,
        )
        for rule in rules
        if _applies_to_application(rule, application)
    ]
    preview = _build_preview(
        db,
        application=application,
        previews=previews_unsorted,
        evaluated_at=evaluated_at,
    )
    weights, breakpoints = load_compliance_config(db)
    failed_high_count = sum(
        item.status == "FAIL" and item.severity == Severity.HIGH
        for item in preview.rules
    )

    # Persist: replace the application's result set and append a snapshot.
    db.execute(delete(ComplianceResult).where(ComplianceResult.application_id == application.id))
    rules_by_code = {rule.code: rule for rule in rules}
    for item in preview.rules:
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
    application.compliance_score = Decimal(str(preview.score))

    _create_snapshot(
        db,
        institution_id=application.institution_id,
        application_id=application.id,
        score=preview.score,
        status=ComplianceHealth(preview.status),
        failed_count=preview.failed_count,
        failed_critical_count=sum(
            item.status == "FAIL" and item.severity == Severity.CRITICAL
            for item in preview.rules
        ),
        failed_high_count=failed_high_count,
        missing_count=preview.not_assessed_count,
        mandatory_failed_count=preview.mandatory_failed_count,
        mandatory_missing_count=preview.mandatory_missing_count,
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
    mandatory_failed_count: int = 0,
    mandatory_missing_count: int = 0,
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


def _monitored_application(
    db: Session, institution_id: uuid.UUID
) -> Application | None:
    """Return the application the monitor should evaluate for an institution.

    Compliance norms are programme-scoped (APH 6.14, Annexure-3), so the monitor
    prefers the most recent application that carries programme rows: the
    New/Extension of Approval case in the MVP flow. A year-round request such as
    a change of site or a closure is recorded without programme detail and would
    otherwise report nothing but missing data.

    Applications whose type is marked ``not_implemented`` in
    ``application_type_routes`` are skipped first: the workflow refuses to
    process them (HTTP 503), so a snapshot built from one describes a case an
    officer cannot open. A stray legacy row of such a type would otherwise
    outrank the live case.

    The latest application remains the fallback so every institution still gets
    a snapshot.
    """
    programme_count = (
        select(func.count(ApplicationProgram.id))
        .where(ApplicationProgram.application_id == Application.id)
        .correlate(Application)
        .scalar_subquery()
    )
    base = (
        select(Application)
        .options(
            selectinload(Application.programs),
            selectinload(Application.documents),
        )
        .where(Application.institution_id == institution_id)
    )
    application = db.scalar(
        base.join(
            ApplicationTypeRoute,
            ApplicationTypeRoute.type == Application.application_type,
        )
        .where(
            programme_count > 0,
            ApplicationTypeRoute.not_implemented.is_(False),
        )
        .order_by(Application.created_at.desc())
        .limit(1)
    )
    if application is not None:
        return application
    application = db.scalar(
        base.where(programme_count > 0).order_by(Application.created_at.desc()).limit(1)
    )
    if application is not None:
        return application
    return db.scalar(base.order_by(Application.created_at.desc()).limit(1))


def evaluate_institution(
    db: Session,
    institution: Institution,
    *,
    evaluated_at: datetime,
    trigger: str = "nightly",
    commit: bool = True,
) -> CompliancePreviewRead | None:
    """Evaluate an institution against its most recent programme application."""
    application = _monitored_application(db, institution.id)
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
    """Re-evaluate institutions. Runs in-process (scheduler, API or CLI)."""
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
