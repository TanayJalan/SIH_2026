"""APH 2024-27 schema retrofit

Revision ID: 0008_aph_schema
Revises: 0007_alert_recipient_cascade
Create Date: 2026-10-25 00:30:00.000000

Adds the APH vocabulary, tables and columns described in docs/GAP_REPORT.md.
No existing table or row is dropped. The companion revision ``0009_aph_data``
remaps the legacy role and application-type values, backfills the new columns
and seeds nothing (seed data is loaded by ``python -m app.seed``).

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_aph_schema"
down_revision: str | None = "0007_alert_recipient_cascade"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB(astext_type=sa.Text())

# ---------------------------------------------------------------------------
# Enum CHECK constraints. Models use native_enum=False, so the vocabulary is
# enforced by a VARCHAR CHECK named ``ck_<table>_<enum name>``.
# ---------------------------------------------------------------------------

ROLE_VALUES = (
    "INSTITUTION_ADMIN",
    "REGULATION_BUREAU_OFFICER",
    "SCRUTINY_COMMITTEE_MEMBER",
    "EVC_MEMBER",
    "REGIONAL_OFFICER",
    "SHC_MEMBER",
    "SAC_MEMBER",
    "EXECUTIVE_COMMITTEE_MEMBER",
    "COMPLAINT_SCRUTINY_MEMBER",
    "SUPER_ADMIN",
)

REGION_VALUES = (
    "CENTRAL",
    "EASTERN",
    "NORTHERN",
    "NORTH_WESTERN",
    "SOUTH_CENTRAL",
    "SOUTHERN",
    "SOUTH_WESTERN",
    "WESTERN",
)


def _in(column: str, values: Sequence[str]) -> str:
    joined = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({joined})"


def _create_enum_check(table: str, name: str, column: str, values: Sequence[str]) -> None:
    op.create_check_constraint(
        name,
        table,
        _in(column, values),
    )


def _drop_enum_check(table: str, name: str) -> None:
    op.drop_constraint(name, table, type_="check")


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Institutions: APH identity, classification, status and profiles.
    # ------------------------------------------------------------------
    op.add_column("institutions", sa.Column("pid", sa.String(length=64), nullable=True))
    op.add_column(
        "institutions",
        sa.Column("aicte_region", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "institutions",
        sa.Column("institution_class", sa.String(length=16), nullable=False, server_default="OTHER"),
    )
    op.add_column(
        "institutions",
        sa.Column("institution_type", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "institutions",
        sa.Column("is_women_only", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "institutions",
        sa.Column("is_pwbd", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "institutions",
        sa.Column("in_jk_ladakh_ne", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "institutions",
        sa.Column("affiliating_body", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "institutions",
        sa.Column("land_ownership", sa.String(length=16), nullable=False, server_default="OWNED"),
    )
    op.add_column(
        "institutions",
        sa.Column("lease_years_total", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "institutions",
        sa.Column("lease_years_live", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "institutions",
        sa.Column("building_leased", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "institutions",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ACTIVE"),
    )
    op.add_column(
        "institutions",
        sa.Column("last_eoa_year", sa.String(length=9), nullable=True),
    )
    op.add_column(
        "institutions",
        sa.Column("accreditation", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "institutions",
        sa.Column("infra_profile", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "institutions",
        sa.Column("library_profile", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "institutions",
        sa.Column("computing_profile", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "institutions",
        sa.Column(
            "essential_requirements",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "institutions",
        sa.Column("campus", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index(op.f("ix_institutions_pid"), "institutions", ["pid"], unique=True)
    op.create_index(
        op.f("ix_institutions_aicte_region"),
        "institutions",
        ["aicte_region"],
        unique=False,
    )
    op.create_index(
        op.f("ix_institutions_institution_class"),
        "institutions",
        ["institution_class"],
        unique=False,
    )
    op.create_index(
        op.f("ix_institutions_status"),
        "institutions",
        ["status"],
        unique=False,
    )
    op.create_check_constraint(
        "lease_years_total_non_negative",
        "institutions",
        "lease_years_total IS NULL OR lease_years_total >= 0",
    )
    op.create_check_constraint(
        "lease_years_live_non_negative",
        "institutions",
        "lease_years_live IS NULL OR lease_years_live >= 0",
    )
    _create_enum_check("institutions", "aicte_region", "aicte_region", REGION_VALUES)
    _create_enum_check(
        "institutions", "institution_class", "institution_class", ("GOVT_TYPE", "OTHER")
    )
    _create_enum_check("institutions", "land_ownership", "land_ownership", ("OWNED", "LEASED"))
    _create_enum_check(
        "institutions",
        "institution_status",
        "status",
        (
            "ACTIVE",
            "HIBERNATION",
            "NO_ADMISSION",
            "CLOSED_PROGRESSIVE",
            "CLOSED",
            "WITHDRAWN",
        ),
    )

    # ------------------------------------------------------------------
    # Public notices and Academic Calendar (admin-editable demo dates).
    # ------------------------------------------------------------------
    op.create_table(
        "public_notices",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("academic_year", sa.String(length=9), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("opens_on", sa.Date(), nullable=False),
        sa.Column("cutoff_on", sa.Date(), nullable=False),
        sa.Column("apH_clause", sa.String(length=64), nullable=False),
        sa.Column("needs_verification", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_public_notices"),
        sa.UniqueConstraint(
            "academic_year",
            "category",
            name="uq_public_notices_year_category",
        ),
        sa.CheckConstraint("cutoff_on >= opens_on", name="public_notice_window_ordered"),
    )
    op.create_index(
        op.f("ix_public_notices_academic_year"),
        "public_notices",
        ["academic_year"],
        unique=False,
    )
    op.create_index(
        op.f("ix_public_notices_category"),
        "public_notices",
        ["category"],
        unique=False,
    )
    _create_enum_check(
        "public_notices", "application_category", "category", ("CAT1_CUTOFF", "CAT2_YEAR_ROUND")
    )

    op.create_table(
        "academic_calendar_events",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("academic_year", sa.String(length=9), nullable=False),
        sa.Column("event_key", sa.String(length=32), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("apH_clause", sa.String(length=64), nullable=False),
        sa.Column("needs_verification", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_academic_calendar_events"),
        sa.UniqueConstraint(
            "academic_year",
            "event_key",
            name="uq_academic_calendar_events_year_key",
        ),
    )
    op.create_index(
        op.f("ix_academic_calendar_events_academic_year"),
        "academic_calendar_events",
        ["academic_year"],
        unique=False,
    )
    op.create_index(
        op.f("ix_academic_calendar_events_event_key"),
        "academic_calendar_events",
        ["event_key"],
        unique=False,
    )
    _create_enum_check(
        "academic_calendar_events",
        "calendar_event_key",
        "event_key",
        (
            "LAST_DATE_EOA",
            "ENROLMENT_UPLOAD_30NOV",
            "NOMENCLATURE_30NOV",
            "SD_PENALTY10_31MAY",
            "SD_PENALTY20_31JUL",
            "IC_REPORT_30JUN",
            "CLOSURE_REVOKE_10APR",
            "RESTORATION_30APR",
        ),
    )

    # ------------------------------------------------------------------
    # Application type routing (Table 2.3) and fee schedules (section 4).
    # ------------------------------------------------------------------
    op.create_table(
        "application_type_routes",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("requires_self_disclosure", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("requires_scrutiny", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("requires_evc", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("requires_hearing_aa", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("nil_deficiency_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("no_ter", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("year_round", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("apH_clause", sa.String(length=64), nullable=False),
        sa.Column("needs_verification", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_application_type_routes"),
        sa.UniqueConstraint("type", name="uq_application_type_routes_type"),
        sa.CheckConstraint(
            "year_round = (category = 'CAT2_YEAR_ROUND')",
            name="year_round_matches_category",
        ),
    )
    op.create_index(
        op.f("ix_application_type_routes_type"),
        "application_type_routes",
        ["type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_application_type_routes_category"),
        "application_type_routes",
        ["category"],
        unique=False,
    )
    _create_enum_check(
        "application_type_routes",
        "application_category",
        "category",
        ("CAT1_CUTOFF", "CAT2_YEAR_ROUND"),
    )

    op.create_table(
        "fee_schedules",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("item_code", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("institution_class", sa.String(length=16), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("base_academic_year", sa.String(length=9), nullable=False),
        sa.Column(
            "annual_increase_pct",
            sa.Numeric(precision=5, scale=2),
            nullable=False,
            server_default=sa.text("10"),
        ),
        sa.Column("apH_clause", sa.String(length=64), nullable=False),
        sa.Column("needs_verification", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_fee_schedules"),
        sa.CheckConstraint("amount_paise >= 0", name="fee_amount_paise_non_negative"),
        sa.CheckConstraint(
            "annual_increase_pct >= 0",
            name="annual_increase_pct_non_negative",
        ),
    )
    op.create_index(op.f("ix_fee_schedules_item_code"), "fee_schedules", ["item_code"], unique=False)
    op.create_index(
        "ix_fee_schedules_item_class",
        "fee_schedules",
        ["item_code", "institution_class"],
        unique=False,
    )
    _create_enum_check(
        "fee_schedules", "institution_class", "institution_class", ("GOVT_TYPE", "OTHER")
    )
    _create_enum_check(
        "fee_schedules",
        "fee_unit",
        "unit",
        ("FLAT", "PER_DIVISION", "PER_COURSE", "PER_1000_SEATS", "PER_LSC"),
    )

    # ------------------------------------------------------------------
    # Programmes, intake ledger and faculty (sections 6.12-6.14).
    # ------------------------------------------------------------------
    op.create_table(
        "programmes",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("institution_id", sa.UUID(), nullable=False),
        sa.Column("programme_family", sa.String(length=64), nullable=False),
        sa.Column("level", sa.String(length=32), nullable=False),
        sa.Column("course_name", sa.String(length=255), nullable=False),
        sa.Column("is_core", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("mode", sa.String(length=32), nullable=False, server_default="REGULAR"),
        sa.Column("duration_years", sa.Numeric(precision=3, scale=1), nullable=False),
        sa.Column("approved_intake", sa.Integer(), nullable=False),
        sa.Column("divisions", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ACTIVE"),
        sa.Column("apH_clause", sa.String(length=64), nullable=False),
        sa.Column("needs_verification", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_programmes"),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "institution_id",
            "course_name",
            "level",
            name="uq_programmes_institution_course_level",
        ),
        sa.CheckConstraint("approved_intake >= 0", name="approved_intake_non_negative"),
        sa.CheckConstraint("divisions >= 0", name="divisions_non_negative"),
        sa.CheckConstraint("duration_years > 0", name="duration_years_positive"),
    )
    op.create_index(
        op.f("ix_programmes_institution_id"),
        "programmes",
        ["institution_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_programmes_programme_family"),
        "programmes",
        ["programme_family"],
        unique=False,
    )
    op.create_index(op.f("ix_programmes_level"), "programmes", ["level"], unique=False)
    op.create_index(op.f("ix_programmes_status"), "programmes", ["status"], unique=False)
    op.create_index(
        "ix_programmes_institution_status",
        "programmes",
        ["institution_id", "status"],
        unique=False,
    )
    _create_enum_check(
        "programmes",
        "programme_mode",
        "mode",
        ("REGULAR", "FLEXIBLE_TIMING", "ODL_ONLINE"),
    )
    _create_enum_check(
        "programmes", "programme_status", "status", ("ACTIVE", "CLOSED", "ZERO_INTAKE")
    )

    op.create_table(
        "approved_intake_ledger",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("programme_id", sa.UUID(), nullable=False),
        sa.Column("academic_year", sa.String(length=9), nullable=False),
        sa.Column("approved_intake", sa.Integer(), nullable=False),
        sa.Column("nri", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("fn_oci", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "lateral",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            quote=True,
        ),
        sa.Column("tfw", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("ews", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("admitted_total", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("admitted_by_category", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("apH_clause", sa.String(length=64), nullable=False),
        sa.Column("needs_verification", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_approved_intake_ledger"),
        sa.ForeignKeyConstraint(["programme_id"], ["programmes.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "programme_id",
            "academic_year",
            name="uq_approved_intake_ledger_programme_year",
        ),
        sa.CheckConstraint(
            "approved_intake >= 0",
            name="ledger_approved_intake_non_negative",
        ),
        sa.CheckConstraint("nri >= 0", name="ledger_nri_non_negative"),
        sa.CheckConstraint("fn_oci >= 0", name="ledger_fn_oci_non_negative"),
        sa.CheckConstraint('"lateral" >= 0', name="ledger_lateral_non_negative"),
        sa.CheckConstraint("tfw >= 0", name="ledger_tfw_non_negative"),
        sa.CheckConstraint("ews >= 0", name="ledger_ews_non_negative"),
        sa.CheckConstraint(
            "admitted_total >= 0",
            name="ledger_admitted_total_non_negative",
        ),
    )
    op.create_index(
        op.f("ix_approved_intake_ledger_programme_id"),
        "approved_intake_ledger",
        ["programme_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_approved_intake_ledger_academic_year"),
        "approved_intake_ledger",
        ["academic_year"],
        unique=False,
    )

    op.create_table(
        "faculty",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("institution_id", sa.UUID(), nullable=False),
        sa.Column("programme_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("portal_faculty_id", sa.String(length=64), nullable=True),
        sa.Column("cadre", sa.String(length=32), nullable=False),
        sa.Column("qualification", sa.String(length=255), nullable=True),
        sa.Column("has_phd", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("regular", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("joined_on", sa.Date(), nullable=True),
        sa.Column("left_on", sa.Date(), nullable=True),
        sa.Column("portal_updated_on", sa.Date(), nullable=True),
        sa.Column("biometric", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("salary_via_ecs", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("apH_clause", sa.String(length=64), nullable=False),
        sa.Column("needs_verification", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_faculty"),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["programme_id"], ["programmes.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "left_on IS NULL OR joined_on IS NULL OR left_on >= joined_on",
            name="faculty_dates_ordered",
        ),
    )
    op.create_index(op.f("ix_faculty_institution_id"), "faculty", ["institution_id"], unique=False)
    op.create_index(op.f("ix_faculty_programme_id"), "faculty", ["programme_id"], unique=False)
    op.create_index(op.f("ix_faculty_cadre"), "faculty", ["cadre"], unique=False)
    op.create_index("ix_faculty_institution_cadre", "faculty", ["institution_id", "cadre"], unique=False)
    op.create_index("ix_faculty_portal_id", "faculty", ["portal_faculty_id"], unique=False)
    _create_enum_check(
        "faculty",
        "faculty_cadre",
        "cadre",
        (
            "PRINCIPAL_DIRECTOR",
            "HOD",
            "PROFESSOR",
            "ASSOC_PROFESSOR",
            "ASST_PROFESSOR",
            "PROF_OF_PRACTICE",
            "ADJUNCT",
        ),
    )

    # ------------------------------------------------------------------
    # Applications: APH track, decision and appeal columns.
    # ------------------------------------------------------------------
    op.add_column(
        "applications",
        sa.Column("track", sa.String(length=32), nullable=False, server_default="NEW_INSTITUTION"),
    )
    op.add_column(
        "applications",
        sa.Column("category", sa.String(length=32), nullable=False, server_default="CAT1_CUTOFF"),
    )
    op.add_column("applications", sa.Column("public_notice_id", sa.UUID(), nullable=True))
    op.add_column(
        "applications",
        sa.Column("portal_application_no", sa.String(length=64), nullable=True),
    )
    op.add_column("applications", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "applications",
        sa.Column("reopen_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "applications",
        sa.Column("late_submission", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("applications", sa.Column("ter_amount_paise", sa.BigInteger(), nullable=True))
    op.add_column("applications", sa.Column("ter_paid_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("applications", sa.Column("ter_receipt_no", sa.String(length=64), nullable=True))
    op.add_column("applications", sa.Column("decision", sa.String(length=16), nullable=True))
    op.add_column("applications", sa.Column("speaking_order", sa.Text(), nullable=True))
    op.add_column(
        "applications",
        sa.Column("decision_uploaded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("applications", sa.Column("appeal_deadline", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "applications",
        sa.Column("appeal_loop_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column("applications", sa.Column("evc_mode", sa.String(length=16), nullable=True))
    op.add_column(
        "applications",
        sa.Column("evc_random_selected", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("applications", sa.Column("loa_valid_until", sa.Date(), nullable=True))
    op.add_column("applications", sa.Column("security_deposit_due_on", sa.Date(), nullable=True))

    op.alter_column(
        "applications",
        "application_type",
        existing_type=sa.String(length=16),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    _drop_enum_check("applications", "application_type")

    op.create_foreign_key(
        "fk_applications_public_notice_id_public_notices",
        "applications",
        "public_notices",
        ["public_notice_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_applications_public_notice_id"),
        "applications",
        ["public_notice_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_applications_portal_application_no"),
        "applications",
        ["portal_application_no"],
        unique=True,
    )
    op.create_index(op.f("ix_applications_track"), "applications", ["track"], unique=False)
    op.create_index(op.f("ix_applications_decision"), "applications", ["decision"], unique=False)
    op.create_index(
        op.f("ix_applications_application_type"),
        "applications",
        ["application_type"],
        unique=False,
    )
    op.create_check_constraint(
        "reopen_count_non_negative",
        "applications",
        "reopen_count >= 0",
    )
    op.create_check_constraint(
        "appeal_loop_count_non_negative",
        "applications",
        "appeal_loop_count >= 0",
    )
    op.create_check_constraint(
        "ter_amount_paise_non_negative",
        "applications",
        "ter_amount_paise IS NULL OR ter_amount_paise >= 0",
    )
    _create_enum_check(
        "applications",
        "application_track",
        "track",
        ("NEW_INSTITUTION", "EXISTING", "UNIVERSITY", "ODL"),
    )
    _create_enum_check(
        "applications",
        "application_category",
        "category",
        ("CAT1_CUTOFF", "CAT2_YEAR_ROUND"),
    )
    _create_enum_check(
        "applications",
        "application_decision",
        "decision",
        ("LOA", "EOA", "LOD", "LOR"),
    )
    _create_enum_check(
        "applications",
        "committee_mode",
        "evc_mode",
        ("ONLINE", "PHYSICAL", "HYBRID"),
    )

    # ------------------------------------------------------------------
    # Fee transactions, security deposits and appeals.
    # ------------------------------------------------------------------
    op.create_table(
        "fee_transactions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("item_code", sa.String(length=64), nullable=False),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("receipt_no", sa.String(length=64), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("apH_clause", sa.String(length=64), nullable=False),
        sa.Column("needs_verification", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_fee_transactions"),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "amount_paise >= 0",
            name="fee_transaction_amount_non_negative",
        ),
    )
    op.create_index(
        op.f("ix_fee_transactions_application_id"),
        "fee_transactions",
        ["application_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_fee_transactions_item_code"),
        "fee_transactions",
        ["item_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_fee_transactions_receipt_no"),
        "fee_transactions",
        ["receipt_no"],
        unique=True,
    )
    op.create_index(
        "ix_fee_transactions_application_kind",
        "fee_transactions",
        ["application_id", "kind"],
        unique=False,
    )
    _create_enum_check(
        "fee_transactions", "fee_kind", "kind", ("TER", "PENALTY", "REFUND", "DEDUCTION")
    )

    op.create_table(
        "security_deposits",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("institution_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=True),
        sa.Column("programme_family", sa.String(length=64), nullable=False),
        sa.Column("level", sa.String(length=32), nullable=False),
        sa.Column("required_paise", sa.BigInteger(), nullable=False),
        sa.Column("doubled_for_leased", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_on", sa.Date(), nullable=False),
        sa.Column("maturity_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING"),
        sa.Column("penalty_percent", sa.SmallInteger(), nullable=True),
        sa.Column("apH_clause", sa.String(length=64), nullable=False),
        sa.Column("needs_verification", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_security_deposits"),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "required_paise >= 0",
            name="security_deposit_amount_non_negative",
        ),
        sa.CheckConstraint(
            "penalty_percent IS NULL OR penalty_percent IN (10, 20)",
            name="security_deposit_penalty_percent_allowed",
        ),
        sa.CheckConstraint(
            "maturity_on >= created_on",
            name="security_deposit_maturity_after_creation",
        ),
    )
    op.create_index(
        op.f("ix_security_deposits_institution_id"),
        "security_deposits",
        ["institution_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_security_deposits_application_id"),
        "security_deposits",
        ["application_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_security_deposits_status"),
        "security_deposits",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_security_deposits_institution_status",
        "security_deposits",
        ["institution_id", "status"],
        unique=False,
    )
    _create_enum_check(
        "security_deposits",
        "security_deposit_status",
        "status",
        ("PENDING", "PAID", "PENALTY_10", "PENALTY_20", "WITHDRAWN", "RELEASED", "FORFEITED"),
    )

    op.create_table(
        "appeals",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("filed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("within_deadline", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("loop_no", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("sac_recommendation", sa.String(length=64), nullable=True),
        sa.Column("council_decision", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("apH_clause", sa.String(length=64), nullable=False),
        sa.Column("needs_verification", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_appeals"),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.CheckConstraint("loop_no >= 1", name="appeal_loop_no_positive"),
    )
    op.create_index(op.f("ix_appeals_application_id"), "appeals", ["application_id"], unique=False)
    op.create_index(
        "ix_appeals_application_filed",
        "appeals",
        ["application_id", "filed_at"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # Complaints and penal actions (Chapter VII).
    # ------------------------------------------------------------------
    op.create_table(
        "complaints",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("institution_id", sa.UUID(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="RECEIVED"),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("received_on", sa.Date(), nullable=True),
        sa.Column("show_cause_due_on", sa.Date(), nullable=True),
        sa.Column("is_anonymous", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("apH_clause", sa.String(length=64), nullable=False),
        sa.Column("needs_verification", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_complaints"),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
    )
    op.create_index(
        op.f("ix_complaints_institution_id"),
        "complaints",
        ["institution_id"],
        unique=False,
    )
    op.create_index(op.f("ix_complaints_status"), "complaints", ["status"], unique=False)
    op.create_index(
        "ix_complaints_institution_status",
        "complaints",
        ["institution_id", "status"],
        unique=False,
    )
    _create_enum_check(
        "complaints",
        "complaint_status",
        "status",
        ("RECEIVED", "PGRC", "SCSC", "SHOW_CAUSE", "HEARING", "DECIDED", "CLOSED"),
    )

    op.create_table(
        "penal_actions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("institution_id", sa.UUID(), nullable=False),
        sa.Column("complaint_id", sa.UUID(), nullable=True),
        sa.Column("application_id", sa.UUID(), nullable=True),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("violation_code", sa.String(length=2), nullable=False),
        sa.Column("hearing_done", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("speaking_order", sa.Text(), nullable=True),
        sa.Column("effective_academic_year", sa.String(length=9), nullable=True),
        sa.Column("apH_clause", sa.String(length=64), nullable=False),
        sa.Column("needs_verification", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_penal_actions"),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["complaint_id"], ["complaints.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "violation_code IN ('a','b','c','d','e','f','g','h','i','j','k','l','m','n')",
            name="penal_action_violation_code_allowed",
        ),
    )
    op.create_index(
        op.f("ix_penal_actions_institution_id"),
        "penal_actions",
        ["institution_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_penal_actions_complaint_id"),
        "penal_actions",
        ["complaint_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_penal_actions_application_id"),
        "penal_actions",
        ["application_id"],
        unique=False,
    )
    op.create_index(op.f("ix_penal_actions_action_type"), "penal_actions", ["action_type"], unique=False)
    op.create_index(
        "ix_penal_actions_institution_year",
        "penal_actions",
        ["institution_id", "effective_academic_year"],
        unique=False,
    )
    _create_enum_check(
        "penal_actions",
        "penal_action_type",
        "action_type",
        (
            "NRI_SUSPENSION",
            "INTAKE_REDUCTION",
            "NO_ADMISSION",
            "PROGRAMME_WITHDRAWAL",
            "AUTONOMY_WITHDRAWAL",
            "INSTITUTION_WITHDRAWAL",
            "EXCESS_ADMISSION_FINE",
            "GRANT_INELIGIBLE",
        ),
    )

    # ------------------------------------------------------------------
    # Committees, members and reports (section 1, Annexure-16).
    # ------------------------------------------------------------------
    op.create_table(
        "committees",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=True),
        sa.Column("complaint_id", sa.UUID(), nullable=True),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False, server_default="ONLINE"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("selection_seed", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="SCHEDULED"),
        sa.Column("apH_clause", sa.String(length=64), nullable=False),
        sa.Column("needs_verification", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_committees"),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["complaint_id"], ["complaints.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "num_nonnulls(application_id, complaint_id) = 1",
            name="committee_exactly_one_subject",
        ),
    )
    op.create_index(op.f("ix_committees_application_id"), "committees", ["application_id"], unique=False)
    op.create_index(op.f("ix_committees_complaint_id"), "committees", ["complaint_id"], unique=False)
    op.create_index(op.f("ix_committees_type"), "committees", ["type"], unique=False)
    op.create_index(op.f("ix_committees_status"), "committees", ["status"], unique=False)
    op.create_index("ix_committees_type_status", "committees", ["type", "status"], unique=False)
    op.create_index("ix_committees_scheduled", "committees", ["scheduled_at"], unique=False)
    _create_enum_check(
        "committees",
        "committee_type",
        "type",
        ("SCRUTINY", "RE_SCRUTINY", "EVC", "SHC", "SAC", "SCSC", "EC", "COUNCIL"),
    )
    _create_enum_check(
        "committees", "committee_mode", "mode", ("ONLINE", "PHYSICAL", "HYBRID")
    )
    _create_enum_check(
        "committees",
        "committee_status",
        "status",
        ("SCHEDULED", "COMPLETED", "CANCELLED"),
    )

    op.create_table(
        "committee_members",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("committee_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("apH_clause", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_committee_members"),
        sa.ForeignKeyConstraint(["committee_id"], ["committees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "committee_id",
            "user_id",
            name="uq_committee_members_committee_user",
        ),
    )
    op.create_index(
        op.f("ix_committee_members_committee_id"),
        "committee_members",
        ["committee_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_committee_members_user_id"),
        "committee_members",
        ["user_id"],
        unique=False,
    )
    op.create_index("ix_committee_members_user", "committee_members", ["user_id"], unique=False)

    op.create_table(
        "committee_reports",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("committee_id", sa.UUID(), nullable=False),
        sa.Column("findings", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("deficiencies", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("recommendation", sa.String(length=64), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("video_url", sa.Text(), nullable=True),
        sa.Column("apH_clause", sa.String(length=64), nullable=False),
        sa.Column("needs_verification", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_committee_reports"),
        sa.ForeignKeyConstraint(["committee_id"], ["committees.id"], ondelete="CASCADE"),
    )
    op.create_index(
        op.f("ix_committee_reports_committee_id"),
        "committee_reports",
        ["committee_id"],
        unique=False,
    )
    op.create_index(
        "ix_committee_reports_committee",
        "committee_reports",
        ["committee_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # Existing tables: APH columns and vocabulary changes.
    # ------------------------------------------------------------------
    op.alter_column(
        "required_documents",
        "application_type",
        existing_type=sa.String(length=16),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    _drop_enum_check("required_documents", "application_type")
    op.add_column(
        "required_documents",
        sa.Column("doc_code", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "required_documents",
        sa.Column("condition_expr", sa.Text(), nullable=True),
    )
    op.add_column(
        "required_documents",
        sa.Column("apH_clause", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "required_documents",
        sa.Column(
            "needs_verification",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index(
        op.f("ix_required_documents_doc_code"),
        "required_documents",
        ["doc_code"],
        unique=False,
    )

    op.add_column("documents", sa.Column("doc_code", sa.String(length=64), nullable=True))
    op.add_column(
        "documents",
        sa.Column("signed_with_dsc", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("documents", sa.Column("valid_until", sa.Date(), nullable=True))
    op.add_column("documents", sa.Column("affidavit_no", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_documents_doc_code"), "documents", ["doc_code"], unique=False)

    op.add_column(
        "compliance_rules",
        sa.Column("apH_clause", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "compliance_rules",
        sa.Column("needs_verification", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "compliance_rules",
        sa.Column("applies_to_family", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "compliance_rules",
        sa.Column("applies_to_level", sa.String(length=32), nullable=True),
    )

    op.add_column(
        "compliance_results",
        sa.Column("evidence", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "compliance_results",
        sa.Column("explanation", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )

    op.add_column(
        "workflow_events",
        sa.Column("apH_clause", sa.String(length=64), nullable=True),
    )

    op.add_column(
        "alert_rules",
        sa.Column("apH_clause", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "alert_rules",
        sa.Column("needs_verification", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    # SLA durations are project-configured processing limits, not handbook
    # values. They still carry a clause marker so the configuration-coverage
    # test can distinguish "demo" rows from rows with a real APH citation.
    op.add_column(
        "sla_configs",
        sa.Column(
            "apH_clause",
            sa.String(length=64),
            nullable=False,
            server_default="DEMO",
        ),
    )
    op.add_column(
        "sla_configs",
        sa.Column(
            "needs_verification",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )

    # Drop the five-value role CHECK on users, alert rules and SLA configs.
    # The replacement CHECK is created by ``0009_aph_data`` after the legacy
    # role values have been remapped, because PostgreSQL validates existing
    # rows when a CHECK constraint is added.
    for table in ("users", "alert_rules", "sla_configs"):
        _drop_enum_check(table, "user_role")

    # Allow the committee-composition configuration row.
    op.drop_constraint(
        "compliance_config_key_allowed",
        "compliance_config",
        type_="check",
    )
    op.create_check_constraint(
        "compliance_config_key_allowed",
        "compliance_config",
        "key IN ('severity_weights', 'rag_breakpoints', 'committee_compositions')",
    )

    # Sequence used to generate the AICTE portal application number.
    op.execute("CREATE SEQUENCE IF NOT EXISTS portal_application_no_seq START WITH 1")


def downgrade() -> None:
    op.execute("DROP SEQUENCE IF EXISTS portal_application_no_seq")

    op.drop_constraint(
        "compliance_config_key_allowed",
        "compliance_config",
        type_="check",
    )
    op.create_check_constraint(
        "compliance_config_key_allowed",
        "compliance_config",
        "key IN ('severity_weights', 'rag_breakpoints')",
    )

    for table, column in (
        ("users", "role"),
        ("alert_rules", "escalation_role"),
        ("sla_configs", "escalate_to_role"),
    ):
        op.create_check_constraint(
            "user_role",
            table,
            _in(
                column,
                (
                    "INSTITUTION_ADMIN",
                    "SCRUTINY_OFFICER",
                    "INSPECTION_COMMITTEE",
                    "REGIONAL_HEAD",
                    "SUPER_ADMIN",
                ),
            ),
        )

    op.drop_column("alert_rules", "needs_verification")
    op.drop_column("alert_rules", "apH_clause")
    op.drop_column("sla_configs", "needs_verification")
    op.drop_column("sla_configs", "apH_clause")
    op.drop_column("workflow_events", "apH_clause")
    op.drop_column("compliance_results", "explanation")
    op.drop_column("compliance_results", "evidence")
    op.drop_column("compliance_rules", "applies_to_level")
    op.drop_column("compliance_rules", "applies_to_family")
    op.drop_column("compliance_rules", "needs_verification")
    op.drop_column("compliance_rules", "apH_clause")

    op.drop_index(op.f("ix_documents_doc_code"), table_name="documents")
    op.drop_column("documents", "affidavit_no")
    op.drop_column("documents", "valid_until")
    op.drop_column("documents", "signed_with_dsc")
    op.drop_column("documents", "doc_code")

    op.drop_index(op.f("ix_required_documents_doc_code"), table_name="required_documents")
    op.drop_column("required_documents", "needs_verification")
    op.drop_column("required_documents", "apH_clause")
    op.drop_column("required_documents", "condition_expr")
    op.drop_column("required_documents", "doc_code")
    _create_enum_check(
        "required_documents",
        "application_type",
        "application_type",
        ("NEW", "EXTENSION", "INTAKE_CHANGE"),
    )
    op.alter_column(
        "required_documents",
        "application_type",
        existing_type=sa.String(length=64),
        type_=sa.String(length=16),
        existing_nullable=False,
    )

    for name in (
        "committee_mode",
        "application_decision",
        "application_category",
        "application_track",
        "ter_amount_paise_non_negative",
        "appeal_loop_count_non_negative",
        "reopen_count_non_negative",
    ):
        op.drop_constraint(name, "applications", type_="check")
    op.drop_index(op.f("ix_applications_decision"), table_name="applications")
    op.drop_index(op.f("ix_applications_application_type"), table_name="applications")
    op.drop_index(op.f("ix_applications_track"), table_name="applications")
    op.drop_index(op.f("ix_applications_portal_application_no"), table_name="applications")
    op.drop_index(op.f("ix_applications_public_notice_id"), table_name="applications")
    op.drop_constraint(
        "fk_applications_public_notice_id_public_notices",
        "applications",
        type_="foreignkey",
    )
    _create_enum_check(
        "applications",
        "application_type",
        "application_type",
        ("NEW", "EXTENSION", "INTAKE_CHANGE"),
    )
    op.alter_column(
        "applications",
        "application_type",
        existing_type=sa.String(length=64),
        type_=sa.String(length=16),
        existing_nullable=False,
    )
    for column in (
        "security_deposit_due_on",
        "loa_valid_until",
        "evc_random_selected",
        "evc_mode",
        "appeal_loop_count",
        "appeal_deadline",
        "decision_uploaded_at",
        "speaking_order",
        "decision",
        "ter_receipt_no",
        "ter_paid_at",
        "ter_amount_paise",
        "late_submission",
        "reopen_count",
        "locked_at",
        "portal_application_no",
        "public_notice_id",
        "category",
        "track",
    ):
        op.drop_column("applications", column)

    op.drop_table("committee_reports")
    op.drop_table("committee_members")
    op.drop_table("committees")
    op.drop_table("penal_actions")
    op.drop_table("complaints")
    op.drop_table("appeals")
    op.drop_table("security_deposits")
    op.drop_table("fee_transactions")
    op.drop_table("faculty")
    op.drop_table("approved_intake_ledger")
    op.drop_table("programmes")
    op.drop_table("fee_schedules")
    op.drop_table("application_type_routes")
    op.drop_table("academic_calendar_events")
    op.drop_table("public_notices")

    for name in (
        "institution_status",
        "land_ownership",
        "institution_class",
        "aicte_region",
        "lease_years_live_non_negative",
        "lease_years_total_non_negative",
    ):
        op.drop_constraint(name, "institutions", type_="check")
    op.drop_index(op.f("ix_institutions_status"), table_name="institutions")
    op.drop_index(op.f("ix_institutions_institution_class"), table_name="institutions")
    op.drop_index(op.f("ix_institutions_aicte_region"), table_name="institutions")
    op.drop_index(op.f("ix_institutions_pid"), table_name="institutions")
    for column in (
        "campus",
        "essential_requirements",
        "computing_profile",
        "library_profile",
        "infra_profile",
        "accreditation",
        "last_eoa_year",
        "status",
        "building_leased",
        "lease_years_live",
        "lease_years_total",
        "land_ownership",
        "affiliating_body",
        "in_jk_ladakh_ne",
        "is_pwbd",
        "is_women_only",
        "institution_type",
        "institution_class",
        "aicte_region",
        "pid",
    ):
        op.drop_column("institutions", column)
