"""Pytest fixtures for authentication and authorization integration tests."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, or_, select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import create_app
from app.models import (
    Application,
    ApplicationCategory,
    ApplicationStatus,
    ApplicationTrack,
    Inspection,
    Institution,
    InstitutionClass,
    InstitutionRegion,
    Role,
    User,
    WorkflowStage,
)
from app.models.alert import Alert
from app.models.audit import AuditLog
from app.models.security_deposit import SecurityDeposit
from app.services.audit import AuditService
from tests.support import TestData, TestUser

TEST_PASSWORD = "TestPass123!"


@pytest.fixture(scope="session", autouse=True)
def ensure_reference_config() -> None:
    """Make the rule catalogue and APH routing available on an unseeded DB."""
    from app.seed import (
        _ensure_alert_rules,
        _ensure_aph_reference_data,
        _ensure_baseline_snapshots,
        _ensure_compliance_config,
        _ensure_compliance_rules,
        _ensure_expert_pool,
        _ensure_sla_configs,
    )

    with SessionLocal() as db:
        audit = AuditService(db)
        _ensure_sla_configs(db, audit)
        _ensure_alert_rules(db, audit)
        _ensure_compliance_rules(db, audit)
        _ensure_compliance_config(db, audit)
        _ensure_aph_reference_data(db, audit)
        _ensure_baseline_snapshots(db)
        _ensure_expert_pool(db, audit)
        db.commit()


@pytest.fixture(scope="session")
def api_client(tmp_path_factory: pytest.TempPathFactory) -> Generator[TestClient, None, None]:
    """Run the API with its real request/response stack and isolated storage."""
    settings = get_settings().model_copy(
        update={
            "storage_dir": tmp_path_factory.mktemp("storage"),
            "compliance_monitor_enabled": False,
            "alert_scan_enabled": False,
            "notifications_enabled": False,
        }
    )
    with TestClient(create_app(settings)) as client:
        yield client


@pytest.fixture
def workspace_applications() -> Generator[list[uuid.UUID], None, None]:
    """Track application drafts created by workspace tests and remove them."""
    application_ids: list[uuid.UUID] = []
    yield application_ids

    if not application_ids:
        return
    with SessionLocal() as db:
        db.execute(
            delete(SecurityDeposit).where(
                SecurityDeposit.application_id.in_(application_ids)
            )
        )
        db.execute(delete(Application).where(Application.id.in_(application_ids)))
        db.commit()


@pytest.fixture(scope="session")
def test_data() -> Generator[TestData, None, None]:
    """Create isolated fictional records and remove them after the test run."""
    suffix = uuid.uuid4().hex[:10]
    west_region = f"TestWest-{suffix}"
    east_region = f"TestEast-{suffix}"
    password_hash = hash_password(TEST_PASSWORD)

    with SessionLocal() as db:
        west = Institution(
            name=f"Test West Institute {suffix} (Fictional)",
            aicte_id=f"TEST-W-{suffix}",
            pid=f"TEST-PID-W-{suffix}",
            state="Test State West",
            region=west_region,
            aicte_region=InstitutionRegion.WESTERN,
            institution_class=InstitutionClass.OTHER,
            type="Engineering",
            institution_type="Engineering",
            established_year=2001,
        )
        east = Institution(
            name=f"Test East Institute {suffix} (Fictional)",
            aicte_id=f"TEST-E-{suffix}",
            pid=f"TEST-PID-E-{suffix}",
            state="Test State East",
            region=east_region,
            aicte_region=InstitutionRegion.EASTERN,
            institution_class=InstitutionClass.OTHER,
            type="Management",
            institution_type="Management",
            established_year=2005,
        )
        db.add_all([west, east])
        db.flush()

        def make_user(
            key: str,
            role: Role,
            institution: Institution | None,
            region: str | None,
        ) -> User:
            return User(
                name=f"Test {key} {suffix}",
                email=f"test.{suffix}.{key}@example.edu",
                password_hash=password_hash,
                role=role,
                institution_id=institution.id if institution else None,
                region=region,
                is_active=True,
            )

        users = {
            "institution_admin_west": make_user(
                "institution_admin_west", Role.INSTITUTION_ADMIN, west, west_region
            ),
            "institution_admin_east": make_user(
                "institution_admin_east", Role.INSTITUTION_ADMIN, east, east_region
            ),
            "scrutiny": make_user(
                "scrutiny", Role.SCRUTINY_COMMITTEE_MEMBER, west, west_region
            ),
            "inspection": make_user("inspection", Role.EVC_MEMBER, west, west_region),
            "regional": make_user("regional", Role.REGIONAL_OFFICER, west, west_region),
            "regulation": make_user(
                "regulation", Role.REGULATION_BUREAU_OFFICER, None, west_region
            ),
            "shc": make_user("shc", Role.SHC_MEMBER, None, west_region),
            "sac": make_user("sac", Role.SAC_MEMBER, None, west_region),
            "ec": make_user("ec", Role.EXECUTIVE_COMMITTEE_MEMBER, None, west_region),
            "complaints": make_user(
                "complaints", Role.COMPLAINT_SCRUTINY_MEMBER, None, west_region
            ),
            "super": make_user("super", Role.SUPER_ADMIN, None, None),
        }
        db.add_all(users.values())
        db.flush()

        submitted_at = datetime.now(UTC)
        west_application = Application(
            institution_id=west.id,
            track=ApplicationTrack.NEW_INSTITUTION,
            application_type="NEW_INSTITUTION",
            category=ApplicationCategory.CAT1_CUTOFF,
            academic_year="2026-27",
            status=ApplicationStatus.SUBMITTED,
            current_stage=WorkflowStage.SCRUTINY,
            assigned_officer_id=users["scrutiny"].id,
            submitted_at=submitted_at,
            locked_at=submitted_at,
            sla_due_at=submitted_at - timedelta(days=2),
            data={"reference": f"TEST-W-{suffix}", "demo": True},
        )
        east_application = Application(
            institution_id=east.id,
            track=ApplicationTrack.EXISTING,
            application_type="EOA_SELF_DISCLOSURE",
            category=ApplicationCategory.CAT1_CUTOFF,
            academic_year="2026-27",
            status=ApplicationStatus.SUBMITTED,
            current_stage=WorkflowStage.APPLICATION,
            assigned_officer_id=None,
            submitted_at=submitted_at,
            locked_at=submitted_at,
            sla_due_at=submitted_at + timedelta(days=10),
            data={"reference": f"TEST-E-{suffix}", "demo": True},
        )
        db.add_all([west_application, east_application])
        db.flush()

        inspection = Inspection(
            application_id=west_application.id,
            committee_id=users["inspection"].id,
            scheduled_on=submitted_at + timedelta(days=5),
        )
        db.add(inspection)
        db.commit()

        data = TestData(
            password=TEST_PASSWORD,
            users={
                key: TestUser(
                    id=user.id,
                    email=user.email,
                    role=user.role,
                    region=user.region,
                    institution_id=user.institution_id,
                )
                for key, user in users.items()
            },
            institutions={"west": west.id, "east": east.id},
            applications={
                "west": west_application.id,
                "east": east_application.id,
            },
            inspection_id=inspection.id,
        )

    yield data

    user_ids = [user.id for user in data.users.values()]
    with SessionLocal() as db:
        application_ids = db.scalars(
            select(Application.id).where(
                Application.institution_id.in_(data.institutions.values())
            )
        ).all()
        entity_ids = [
            *user_ids,
            *data.institutions.values(),
            *data.applications.values(),
            *application_ids,
            data.inspection_id,
        ]
        db.execute(
            delete(AuditLog).where(
                or_(
                    AuditLog.actor_id.in_(user_ids),
                    AuditLog.entity_id.in_(entity_ids),
                )
            )
        )
        db.execute(delete(Alert).where(Alert.recipient_user_id.in_(user_ids)))
        db.execute(delete(Inspection).where(Inspection.id == data.inspection_id))
        db.execute(
            delete(Application).where(
                Application.institution_id.in_(data.institutions.values())
            )
        )
        db.execute(delete(User).where(User.id.in_(user_ids)))
        db.execute(delete(Institution).where(Institution.id.in_(data.institutions.values())))
        db.commit()
