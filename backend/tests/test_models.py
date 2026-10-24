"""Schema registration tests that do not require a live database."""

import app.models  # noqa: F401
from app.db.base import Base

EXPECTED_TABLES = {
    "alert_rules",
    "alerts",
    "application_programs",
    "applications",
    "audit_logs",
    "compliance_results",
    "compliance_rules",
    "compliance_config",
    "compliance_snapshots",
    "deficiencies",
    "documents",
    "inspections",
    "institutions",
    "required_documents",
    "sla_configs",
    "users",
    "workflow_events",
}


def test_all_expected_tables_are_registered() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_required_indexes_exist() -> None:
    application_indexes = {index.name for index in Base.metadata.tables["applications"].indexes}
    alert_indexes = {index.name for index in Base.metadata.tables["alerts"].indexes}

    assert "ix_applications_status" in application_indexes
    assert "ix_applications_institution_id" in application_indexes
    assert "ix_applications_sla_due_at" in application_indexes
    assert "ix_alerts_recipient_status" in alert_indexes
