"""APH 2024-27 data migration

Revision ID: 0009_aph_data
Revises: 0008_aph_schema
Create Date: 2026-10-25 00:31:00.000000

Remaps the legacy roles and application types in place, backfills the new APH
columns for existing rows, and then installs the new role CHECK constraints.
Every existing table and row is preserved. No demo data is inserted here: the
APH reference data is loaded by ``python -m app.seed``.

Legacy mappings (docs/GAP_REPORT.md section 9):

* ``SCRUTINY_OFFICER``      -> ``SCRUTINY_COMMITTEE_MEMBER``
* ``INSPECTION_COMMITTEE``  -> ``EVC_MEMBER``
* ``REGIONAL_HEAD``         -> ``REGIONAL_OFFICER``
* ``NEW``                   -> ``NEW_INSTITUTION``
* ``EXTENSION``             -> ``EOA_SELF_DISCLOSURE``
* ``INTAKE_CHANGE``         -> ``INCREASE_INTAKE``

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_aph_data"
down_revision: str | None = "0008_aph_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

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

LEGACY_ROLE_MAP = (
    ("SCRUTINY_OFFICER", "SCRUTINY_COMMITTEE_MEMBER"),
    ("INSPECTION_COMMITTEE", "EVC_MEMBER"),
    ("REGIONAL_HEAD", "REGIONAL_OFFICER"),
)

APPLICATION_TYPE_MAP = (
    ("NEW", "NEW_INSTITUTION"),
    ("EXTENSION", "EOA_SELF_DISCLOSURE"),
    ("INTAKE_CHANGE", "INCREASE_INTAKE"),
)

CATEGORY_2_TYPES = (
    "CHANGE_OF_SITE",
    "CLOSURE_OF_INSTITUTION",
    "WOMEN_COED_CONVERSION",
    "CLOSURE_OF_PROGRAMME",
    "CHANGE_IN_BANK_DETAILS",
    "CHANGE_OF_TRUST_NAME",
    "EXTENDED_EOA",
    "DEEMED_UNIVERSITY_CONVERSION",
    "ODL_ONLINE",
)

WORKFLOW_EVENT_CLAUSES = (
    ("submit", "APH 1.4.3"),
    ("auto_assign", "APH 1.8a"),
    ("verify_documents", "APH 1.8"),
    ("start_scrutiny", "APH 1.8"),
    ("raise_deficiency", "APH 2.3.3b"),
    ("respond_deficiency", "APH 2.4"),
    ("close_deficiency", "APH 1.8"),
    ("schedule_inspection", "APH 1.9a"),
    ("submit_inspection_report", "APH 1.9"),
    ("send_to_committee", "APH 1.10"),
    ("approve", "APH 1.10a"),
    ("conditionally_approve", "APH 4.9c"),
    ("reject", "APH 1.10"),
    ("withdraw", "APH 2.3.3f-g"),
)


def _in(column: str, values: Sequence[str]) -> str:
    joined = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({joined})"


def _remap(table: str, column: str, mapping: Sequence[tuple[str, str]]) -> None:
    for old, new in mapping:
        op.execute(
            sa.text(
                f"UPDATE {table} SET {column} = :new WHERE {column} = :old"
            ).bindparams(new=new, old=old)
        )


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Roles: remap every table that stores a role, then install the CHECK.
    # ------------------------------------------------------------------
    for table, column in (
        ("users", "role"),
        ("alert_rules", "escalation_role"),
        ("sla_configs", "escalate_to_role"),
    ):
        _remap(table, column, LEGACY_ROLE_MAP)

    for table, column in (
        ("users", "role"),
        ("alert_rules", "escalation_role"),
        ("sla_configs", "escalate_to_role"),
    ):
        op.create_check_constraint(
            "user_role",
            table,
            _in(column, ROLE_VALUES),
        )

    # ------------------------------------------------------------------
    # Application types.
    # ------------------------------------------------------------------
    _remap("applications", "application_type", APPLICATION_TYPE_MAP)
    _remap("required_documents", "application_type", APPLICATION_TYPE_MAP)

    # ------------------------------------------------------------------
    # Institutions: identity, region, type and fee class.
    # ------------------------------------------------------------------
    op.execute("UPDATE institutions SET pid = aicte_id WHERE pid IS NULL")
    op.execute(
        """
        UPDATE institutions
        SET aicte_region = CASE lower(region)
            WHEN 'west' THEN 'WESTERN'
            WHEN 'western' THEN 'WESTERN'
            WHEN 'south' THEN 'SOUTHERN'
            WHEN 'southern' THEN 'SOUTHERN'
            WHEN 'north' THEN 'NORTHERN'
            WHEN 'northern' THEN 'NORTHERN'
            WHEN 'east' THEN 'EASTERN'
            WHEN 'eastern' THEN 'EASTERN'
            WHEN 'central' THEN 'CENTRAL'
            WHEN 'north west' THEN 'NORTH_WESTERN'
            WHEN 'north-western' THEN 'NORTH_WESTERN'
            WHEN 'south central' THEN 'SOUTH_CENTRAL'
            WHEN 'south western' THEN 'SOUTH_WESTERN'
            ELSE 'WESTERN'
        END
        WHERE aicte_region IS NULL
        """
    )
    op.execute("UPDATE institutions SET institution_type = type WHERE institution_type IS NULL")
    op.execute(
        """
        UPDATE institutions
        SET institution_class = 'GOVT_TYPE'
        WHERE lower(type) LIKE '%government%'
           OR lower(type) LIKE '%govt%'
           OR lower(type) LIKE '%university%'
        """
    )
    op.execute("UPDATE institutions SET status = 'ACTIVE' WHERE status IS NULL")

    op.alter_column("institutions", "pid", existing_type=sa.String(length=64), nullable=False)
    op.alter_column(
        "institutions",
        "aicte_region",
        existing_type=sa.String(length=32),
        nullable=False,
    )
    op.alter_column(
        "institutions",
        "institution_type",
        existing_type=sa.String(length=64),
        nullable=False,
    )

    # ------------------------------------------------------------------
    # Applications: track, category, portal number and lock timestamp.
    # ------------------------------------------------------------------
    op.execute(
        """
        UPDATE applications
        SET track = CASE
            WHEN application_type IN (
                'NEW_INSTITUTION',
                'NEW_INSTITUTION_OTHER_REGULATOR',
                'CLOSURE_AND_NEW_INSTITUTION'
            ) THEN 'NEW_INSTITUTION'
            WHEN application_type = 'UNIVERSITY' THEN 'UNIVERSITY'
            WHEN application_type = 'ODL_ONLINE' THEN 'ODL'
            ELSE 'EXISTING'
        END
        """
    )
    category_2 = ", ".join(f"'{value}'" for value in CATEGORY_2_TYPES)
    op.execute(
        f"""
        UPDATE applications
        SET category = CASE
            WHEN application_type IN ({category_2}) THEN 'CAT2_YEAR_ROUND'
            ELSE 'CAT1_CUTOFF'
        END
        """
    )
    op.execute(
        """
        WITH numbered AS (
            SELECT id,
                   row_number() OVER (ORDER BY created_at, id) AS rn
            FROM applications
            WHERE portal_application_no IS NULL
        )
        UPDATE applications AS a
        SET portal_application_no =
            'AICTE/' || a.academic_year || '/LEGACY-' || lpad(numbered.rn::text, 4, '0')
        FROM numbered
        WHERE a.id = numbered.id
        """
    )
    op.execute(
        """
        UPDATE applications
        SET locked_at = submitted_at
        WHERE submitted_at IS NOT NULL AND locked_at IS NULL
        """
    )

    # ------------------------------------------------------------------
    # Clause coverage for rows that predate the APH retrofit. The demo
    # rules are illustrative, so they are explicitly marked as needing
    # verification rather than being given an invented clause.
    # ------------------------------------------------------------------
    op.execute(
        """
        UPDATE compliance_rules
        SET "apH_clause" = 'DEMO', needs_verification = true
        WHERE "apH_clause" IS NULL
        """
    )
    op.execute(
        """
        UPDATE alert_rules
        SET "apH_clause" = 'DEMO', needs_verification = true
        WHERE "apH_clause" IS NULL
        """
    )
    op.execute(
        """
        UPDATE required_documents
        SET "apH_clause" = 'DEMO', needs_verification = true
        WHERE "apH_clause" IS NULL
        """
    )
    for action, clause in WORKFLOW_EVENT_CLAUSES:
        op.execute(
            sa.text(
                'UPDATE workflow_events SET "apH_clause" = :clause '
                'WHERE action = :action AND "apH_clause" IS NULL'
            ).bindparams(clause=clause, action=action)
        )
    # Older seed data recorded a submission with a blank action.
    op.execute(
        """
        UPDATE workflow_events
        SET "apH_clause" = 'APH 1.4.3'
        WHERE (action = '' OR action IS NULL)
          AND from_status = 'DRAFT' AND to_status = 'SUBMITTED'
          AND "apH_clause" IS NULL
        """
    )
    # SLA escalation is demo configuration: the handbook does not publish
    # processing-time limits, so the event is explicitly marked DEMO.
    op.execute(
        """
        UPDATE workflow_events
        SET "apH_clause" = 'DEMO'
        WHERE action = 'escalate' AND "apH_clause" IS NULL
        """
    )
    op.alter_column(
        "workflow_events",
        "apH_clause",
        existing_type=sa.String(length=64),
        nullable=False,
    )
    op.alter_column(
        "compliance_rules",
        "apH_clause",
        existing_type=sa.String(length=64),
        nullable=False,
    )
    op.alter_column(
        "alert_rules",
        "apH_clause",
        existing_type=sa.String(length=64),
        nullable=False,
    )
    op.alter_column(
        "required_documents",
        "apH_clause",
        existing_type=sa.String(length=64),
        nullable=False,
    )

    op.execute("UPDATE documents SET doc_code = doc_type WHERE doc_code IS NULL")


def downgrade() -> None:
    for table in ("users", "alert_rules", "sla_configs"):
        op.drop_constraint("user_role", table, type_="check")

    reverse_roles = tuple((new, old) for old, new in LEGACY_ROLE_MAP)
    for table, column in (
        ("users", "role"),
        ("alert_rules", "escalation_role"),
        ("sla_configs", "escalate_to_role"),
    ):
        _remap(table, column, reverse_roles)

    reverse_types = tuple((new, old) for old, new in APPLICATION_TYPE_MAP)
    _remap("applications", "application_type", reverse_types)
    _remap("required_documents", "application_type", reverse_types)

    op.alter_column(
        "institutions",
        "institution_type",
        existing_type=sa.String(length=64),
        nullable=True,
    )
    op.alter_column(
        "institutions",
        "aicte_region",
        existing_type=sa.String(length=32),
        nullable=True,
    )
    op.alter_column("institutions", "pid", existing_type=sa.String(length=64), nullable=True)
