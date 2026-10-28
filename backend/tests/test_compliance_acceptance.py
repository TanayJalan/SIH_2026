"""Acceptance tests for the APH compliance verdict.

A deficient institution must be rejected with clause-cited failures and the
penal actions those failures attract. A compliant institution must reach Nil
Deficiency, which is the only outcome that lets the EoA flow continue.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, date, datetime
from typing import Any

import pytest
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models.application import Application, ApplicationProgram
from app.models.document import Document
from app.models.enums import (
    ApplicationCategory,
    ApplicationStatus,
    ApplicationTrack,
    ApplicationType,
    DocumentVerificationStatus,
    InstitutionClass,
    InstitutionRegion,
    LandOwnership,
)
from app.models.faculty import Faculty
from app.models.institution import Institution
from app.models.programme import ApprovedIntakeLedger, Programme
from app.models.required_document import RequiredDocument
from app.schemas.application_sections import ApplicationData
from app.schemas.compliance import CompliancePreviewRead
from app.services.audit import AuditService
from app.services.compliance import evaluate_compliance
from tests.support import TestData

REFERENCE_DATE = datetime(2026, 10, 28, tzinfo=UTC)

# The fictional South campus profile. It satisfies every in-scope APH area,
# library and computing norm, so the only variable between the two fixtures is
# the deficiency the test introduces.
_INFRA_PROFILE: dict[str, Any] = {
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
}
_LIBRARY_PROFILE: dict[str, Any] = {
    "titles": 300,
    "volumes": 1500,
    "journals": 20,
    "ebooks_pct": 35.0,
    "reading_room_seats": 80,
    "digital_library_pcs": 10,
    "ndl_membership": True,
}
_COMPUTING_PROFILE: dict[str, Any] = {
    "pcs": 120,
    "pc_student_ratio": 10.0,
    "printers": 8,
    "bandwidth_mbps": 100,
    "language_lab_pcs": 20,
    "wifi": True,
    "plagiarism_software": True,
}
_ESSENTIAL_PROFILE: dict[str, Any] = {
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
}
_CAMPUS_PROFILE: dict[str, Any] = {
    "plots": [
        {
            "area_sqm": 9000.0,
            "title_status": "OWNED",
            "distance_km": 0.0,
        }
    ],
    "gap_km": 0.0,
    "contiguous": True,
    "obstacles": [],
    "built_up_sqm": 5200.0,
}


def _cadre_members(
    institution_id: uuid.UUID, programme_id: uuid.UUID, deficient: bool
) -> list[Faculty]:
    """One Principal, two Associate Professors and the remaining Assistants."""
    assistants = 6 if deficient else 9
    members = [
        Faculty(
            institution_id=institution_id,
            programme_id=programme_id,
            name="Dr Acceptance Principal (Fictional)",
            portal_faculty_id=f"ACC-PRINCIPAL-{uuid.uuid4().hex[:6]}",
            cadre="PRINCIPAL_DIRECTOR",
            qualification="PhD (Management)",
            has_phd=True,
            regular=True,
            joined_on=date(2019, 7, 1),
            portal_updated_on=date(2019, 7, 1),
            biometric=True,
            salary_via_ecs=True,
            apH_clause="APH 6.14",
        ),
        Faculty(
            institution_id=institution_id,
            programme_id=programme_id,
            name="Dr Acceptance Associate One (Fictional)",
            portal_faculty_id=f"ACC-ASSOC1-{uuid.uuid4().hex[:6]}",
            cadre="ASSOC_PROFESSOR",
            qualification="PhD (Finance)",
            has_phd=True,
            regular=True,
            joined_on=date(2019, 7, 1),
            portal_updated_on=date(2019, 7, 1),
            biometric=True,
            salary_via_ecs=True,
            apH_clause="APH 6.14",
        ),
        Faculty(
            institution_id=institution_id,
            programme_id=programme_id,
            name="Dr Acceptance Associate Two (Fictional)",
            portal_faculty_id=f"ACC-ASSOC2-{uuid.uuid4().hex[:6]}",
            cadre="ASSOC_PROFESSOR",
            qualification="PhD (Marketing)",
            has_phd=True,
            regular=True,
            joined_on=date(2019, 7, 1),
            portal_updated_on=date(2019, 7, 1),
            biometric=True,
            salary_via_ecs=True,
            apH_clause="APH 6.14",
        ),
    ]
    members.extend(
        Faculty(
            institution_id=institution_id,
            programme_id=programme_id,
            name=f"Prof Acceptance Assistant {index} (Fictional)",
            portal_faculty_id=f"ACC-ASST{index}-{uuid.uuid4().hex[:6]}",
            cadre="ASST_PROFESSOR",
            qualification="MBA",
            has_phd=index <= 3,
            regular=True,
            joined_on=date(2019, 7, 1),
            portal_updated_on=date(2019, 7, 1),
            biometric=True,
            salary_via_ecs=True,
            apH_clause="APH 6.14",
        )
        for index in range(1, assistants + 1)
    )
    if not deficient:
        # APH 6.14d: 10% of the 12 required posts must be Professors of Practice.
        members.extend(
            Faculty(
                institution_id=institution_id,
                programme_id=programme_id,
                name=f"Prof Acceptance Practice {index} (Fictional)",
                portal_faculty_id=f"ACC-POP{index}-{uuid.uuid4().hex[:6]}",
                cadre="PROF_OF_PRACTICE",
                qualification="MBA (12 years industry practice)",
                has_phd=False,
                regular=False,
                joined_on=date(2019, 7, 1),
                portal_updated_on=date(2019, 7, 1),
                biometric=True,
                salary_via_ecs=True,
                apH_clause="APH 6.14d",
            )
            for index in (1, 2)
        )
    return members


def _create_institution(
    db: Any,
    test_data: TestData,
    *,
    suffix: str,
    deficient: bool,
) -> Application:
    institution = Institution(
        name=f"Acceptance Institute {suffix} (Fictional)",
        aicte_id=f"ACC-{suffix}",
        pid=f"ACC-PID-{suffix}",
        state="Kerala",
        region="South",
        aicte_region=InstitutionRegion.SOUTHERN,
        institution_class=InstitutionClass.OTHER,
        type="Management",
        institution_type="Management",
        established_year=2005,
        land_ownership=LandOwnership.OWNED,
        accreditation={
            "naac_score": 3.05,
            "nba_courses_pct": 45.0,
            "autonomous": False,
            "avg_admission_pct_5y": 64.0,
        },
        infra_profile=dict(_INFRA_PROFILE),
        library_profile=dict(_LIBRARY_PROFILE),
        computing_profile=dict(_COMPUTING_PROFILE),
        essential_requirements={
            **_ESSENTIAL_PROFILE,
            **(
                {
                    "ic_annual_report_uploaded": False,
                    "mandatory_disclosure_complete": False,
                    "enrolment_uploaded": False,
                }
                if deficient
                else {}
            ),
        },
        campus=dict(_CAMPUS_PROFILE),
    )
    db.add(institution)
    db.flush()

    programme = Programme(
        institution_id=institution.id,
        programme_family="MANAGEMENT",
        level="PG",
        course_name="Master of Business Administration",
        duration_years=2,
        approved_intake=120,
        divisions=2,
        apH_clause="APH 6.1",
    )
    db.add(programme)
    db.flush()

    db.add_all(_cadre_members(institution.id, programme.id, deficient))
    db.add_all(
        ApprovedIntakeLedger(
            programme_id=programme.id,
            academic_year=year,
            approved_intake=120,
            admitted_total=admitted,
            apH_clause="APH 2.25b",
        )
        for year, admitted in (
            ("2021-22", 118),
            ("2022-23", 120),
            ("2023-24", 116),
            ("2024-25", 120),
            ("2025-26", 119),
        )
    )

    application = Application(
        institution_id=institution.id,
        track=ApplicationTrack.EXISTING,
        application_type=ApplicationType.EOA_SELF_DISCLOSURE,
        category=ApplicationCategory.CAT2_YEAR_ROUND,
        academic_year="2026-27",
        status=ApplicationStatus.SUBMITTED,
        current_stage="APPLICATION",
        data={
            "reference": f"ACC-{suffix}",
            "mandatory_disclosure_url": "https://acceptance.example.edu/disclosure",
        },
    )
    db.add(application)
    db.flush()
    db.add(
        ApplicationProgram(
            application_id=application.id,
            program_name="Master of Business Administration",
            level="PG",
            intake=120,
            faculty_count=12 if not deficient else 9,
            lab_count=4,
        )
    )

    requirements = db.scalars(
        select(RequiredDocument).where(
            RequiredDocument.application_type == ApplicationType.EOA_SELF_DISCLOSURE,
            RequiredDocument.mandatory.is_(True),
        )
    ).all()
    uploaded_by = test_data.users["institution_admin_west"].id
    for requirement in requirements:
        if deficient and requirement.doc_code not in {
            "AFFIDAVIT_2",
            "FIRE_SAFETY_CERTIFICATE",
        }:
            continue
        db.add(
            Document(
                application_id=application.id,
                doc_type=requirement.doc_type,
                doc_code=requirement.doc_code,
                filename=f"{requirement.doc_code}.pdf",
                content_type="application/pdf",
                size_bytes=10,
                storage_path=f"tests/{suffix}/{requirement.doc_code}.pdf",
                uploaded_by=uploaded_by,
                verification_status=DocumentVerificationStatus.PENDING,
                signed_with_dsc=True,
                version=1,
                valid_until=(
                    date(2025, 12, 31)  # expired fire certificate
                    if deficient
                    and requirement.doc_code == "FIRE_SAFETY_CERTIFICATE"
                    else date(2030, 12, 31)
                ),
            )
        )
    db.flush()
    return application


def _evaluate(db: Any, application: Application) -> CompliancePreviewRead:
    data = ApplicationData.model_validate(application.data or {})
    return evaluate_compliance(
        db, application, data, evaluated_at=REFERENCE_DATE
    )


@pytest.fixture(scope="module")
def acceptance_results(
    test_data: TestData,
) -> Generator[dict[str, CompliancePreviewRead], None, None]:
    """Build one deficient and one clean institution, then evaluate both."""
    suffix = uuid.uuid4().hex[:8]
    institution_ids: list[uuid.UUID] = []
    results: dict[str, CompliancePreviewRead] = {}
    with SessionLocal() as db:
        audit = AuditService(db)
        for key, deficient in (("deficient", True), ("clean", False)):
            application = _create_institution(
                db, test_data, suffix=f"{suffix}-{key}", deficient=deficient
            )
            institution_ids.append(application.institution_id)
            db.flush()
            results[key] = _evaluate(db, application)
        audit.log(None, "test.acceptance.created", "Institution", institution_ids[0])
        db.commit()

    yield results

    with SessionLocal() as db:
        application_ids = list(
            db.scalars(
                select(Application.id).where(
                    Application.institution_id.in_(institution_ids)
                )
            ).all()
        )
        if application_ids:
            db.execute(delete(Document).where(Document.application_id.in_(application_ids)))
            db.execute(delete(Application).where(Application.id.in_(application_ids)))
        db.execute(delete(Institution).where(Institution.id.in_(institution_ids)))
        db.commit()


def test_deficient_institution_fails_mandatory_rules_with_clauses(
    acceptance_results: dict[str, CompliancePreviewRead],
) -> None:
    preview = acceptance_results["deficient"]

    assert preview.nil_deficiency is False
    assert preview.mandatory_failed_count >= 5
    assert preview.status == "RED"

    failed = {
        rule.code: rule for rule in preview.rules if rule.mandatory and rule.status == "FAIL"
    }
    for code in (
        "APH-FSR-PG-MANAGEMENT",
        "APH-FAC-ESTABLISHMENT",
        "APH-FAC-CADRE",
        "APH-FAC-POP-MIN",
        "APH-DOC-FIRE",
        "APH-ESS-IC-REPORT",
    ):
        assert code in failed, code
        rule = failed[code]
        assert rule.apH_clause.startswith("APH "), code
        assert rule.message, code
        assert rule.penal_action_suggestions, code
        assert all(
            suggestion.hearing_required for suggestion in rule.penal_action_suggestions
        )
        assert all(
            suggestion.suggests_only for suggestion in rule.penal_action_suggestions
        )


def test_clean_institution_reaches_nil_deficiency(
    acceptance_results: dict[str, CompliancePreviewRead],
) -> None:
    preview = acceptance_results["clean"]

    blocking = [
        (rule.code, rule.status)
        for rule in preview.rules
        if rule.mandatory and rule.status != "PASS"
    ]
    assert not blocking, blocking
    assert preview.nil_deficiency is True
    assert preview.status == "GREEN"
    assert preview.mandatory_failed_count == 0
    assert preview.banner == "Nil Deficiency"
    assert all(rule.apH_clause for rule in preview.rules if rule.mandatory)
    # A scoped rule must actually be evaluated, otherwise "no failures" is a
    # false green rather than a pass.
    assert any(
        rule.code == "APH-FSR-PG-MANAGEMENT" and rule.status == "PASS"
        for rule in preview.rules
    )
