"""Schema registration tests that do not require a live database."""

import app.models  # noqa: F401
from app.db.base import Base

EXPECTED_TABLES = {
    "academic_calendar_events",
    "alert_rules",
    "alert_trigger_catalogue",
    "alerts",
    "appeals",
    "application_programs",
    "application_type_routes",
    "applications",
    "approved_intake_ledger",
    "audit_logs",
    "committee_members",
    "committee_reports",
    "committees",
    "complaints",
    "compliance_config",
    "compliance_results",
    "compliance_rules",
    "compliance_snapshots",
    "council_ratifications",
    "deadline_rules",
    "decision_letters",
    "decisions",
    "deficiencies",
    "documents",
    "faculty",
    "fee_schedules",
    "fee_transactions",
    "inspections",
    "institutions",
    "penal_actions",
    "programmes",
    "public_notices",
    "required_documents",
    "security_deposits",
    "sla_configs",
    "timers",
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
