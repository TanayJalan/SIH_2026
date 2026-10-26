"""data-driven workflow definitions and APH status remap

Revision ID: 0013_workflow_definition
Revises: 0012_application_fee_flow
Create Date: 2026-10-26 12:00:00.000000

Adds the runtime approval state machine as data:

  * ``workflow_definitions`` / ``workflow_states`` / ``workflow_transitions``;
  * ``workflow_key`` / ``not_implemented`` / ``not_implemented_note`` on
    ``application_type_routes``;
  * ``decision_letter_number_seq`` for ``AICTE-DEMO/YYYY/NNNN`` numbers.

It also remaps rows written by the pre-APH linear workflow to the Annexure-7
states (``docs/GAP_REPORT.md`` section 10). Conditional approval is removed:
``CONDITIONALLY_APPROVED`` becomes ``LOA_ISSUED`` because APH does not allow
conditional approval (APH 4.9c, 2.27).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0013_workflow_definition"
down_revision: str | None = "0012_application_fee_flow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Every value the ORM can write, including the legacy values kept for
# historical rows. The state machine itself only emits the APH values.
STATUSES = (
    "DRAFT",
    "SUBMITTED",
    "SCRUTINY",
    "DEFICIENCY_COMMUNICATED",
    "INSTITUTION_COMPLIANCE",
    "RE_SCRUTINY",
    "EVC_CONSTITUTED",
    "EVC_DONE",
    "REGULATION_BUREAU_OBSERVATIONS",
    "EC_DECISION",
    "COUNCIL_RATIFICATION",
    "LOA_ISSUED",
    "LOD_ISSUED",
    "LOR_ISSUED",
    "APPEAL_WINDOW",
    "SAC_REVIEW",
    "COUNCIL_FINAL",
    "REGIONAL_ENDORSEMENT",
    "FINAL_LOA",
    "FINAL_LOD",
    "FINAL_LOR",
    "SECURITY_DEPOSIT_PENDING",
    "ACTIVE_LOA",
    "CANCELLED",
    "WITHDRAWN",
    "SELF_DISCLOSURE_CHECK",
    "RANDOM_EVC",
    "COMPLIANCE_WINDOW",
    "EC_LISTING",
    "EOA_ISSUED",
    "SPEAKING_ORDER",
    "ACTIVE_EOA",
    "SHC_HEARING",
    "CLOSED",
    # Legacy values, read-only for historical rows.
    "DOCUMENT_VERIFICATION",
    "DEFICIENCY_RAISED",
    "DEFICIENCY_RESPONDED",
    "INSPECTION_SCHEDULED",
    "INSPECTION_DONE",
    "COMMITTEE_REVIEW",
    "APPROVED",
    "REJECTED",
)

STAGES = (
    "APPLICATION",
    "DOCUMENT_VERIFICATION",
    "SCRUTINY",
    "DEFICIENCY",
    "INSPECTION",
    "COMMITTEE_REVIEW",
    "DECISION",
    "COMPLETED",
)

# Pre-APH status -> APH status. See docs/GAP_REPORT.md section 10.
STATUS_REMAP = (
    ("DOCUMENT_VERIFICATION", "SUBMITTED"),
    ("DEFICIENCY_RAISED", "DEFICIENCY_COMMUNICATED"),
    ("DEFICIENCY_RESPONDED", "INSTITUTION_COMPLIANCE"),
    ("INSPECTION_SCHEDULED", "EVC_CONSTITUTED"),
    ("INSPECTION_DONE", "EVC_DONE"),
    ("COMMITTEE_REVIEW", "REGULATION_BUREAU_OBSERVATIONS"),
    ("APPROVED", "ACTIVE_LOA"),
    ("CONDITIONALLY_APPROVED", "LOA_ISSUED"),
    ("REJECTED", "FINAL_LOR"),
)

# Statutory clocks started by a decision letter get their own warning triggers
# so they are not confused with the stage SLA (APH 1.11a, 2.25f).
ALERT_TRIGGERS = (
    (
        "APPEAL_WINDOW_CLOSING",
        "APPEAL_WINDOW_CLOSING",
        "The seven-day appeal window against a Speaking Order is closing.",
        "APH 1.11a",
        False,
    ),
    (
        "DEPOSIT_DUE",
        "DEPOSIT_DUE",
        "The Security Deposit and Affidavit 3 are due after an LoA.",
        "APH 2.25f",
        False,
    ),
)


def _status_check(column: str, *, nullable: bool) -> str:
    joined = ", ".join(f"'{value}'" for value in STATUSES)
    prefix = f"{column} IS NULL OR " if nullable else ""
    return f"{prefix}{column} IN ({joined})"


def _stage_check(column: str, *, nullable: bool) -> str:
    joined = ", ".join(f"'{value}'" for value in STAGES)
    prefix = f"{column} IS NULL OR " if nullable else ""
    return f"{prefix}{column} IN ({joined})"


def _insert_alert_triggers() -> None:
    statement = sa.text(
        """
        INSERT INTO alert_trigger_catalogue
            (code, handler_key, description, "apH_clause", needs_verification)
        VALUES (:code, :handler_key, :description, :clause, :needs_verification)
        ON CONFLICT (code) DO NOTHING
        """
    )
    bind = op.get_bind()
    for code, handler_key, description, clause, needs_verification in ALERT_TRIGGERS:
        bind.execute(
            statement,
            {
                "code": code,
                "handler_key": handler_key,
                "description": description,
                "clause": clause,
                "needs_verification": needs_verification,
            },
        )


def _drop_status_checks() -> None:
    op.drop_constraint("application_status", "applications", type_="check")
    op.drop_constraint("workflow_stage", "applications", type_="check")
    op.drop_constraint("workflow_stage", "sla_configs", type_="check")
    op.drop_constraint("application_status_from", "workflow_events", type_="check")
    op.drop_constraint("application_status_to", "workflow_events", type_="check")


def _create_status_checks() -> None:
    op.create_check_constraint(
        "application_status", "applications", _status_check("status", nullable=False)
    )
    op.create_check_constraint(
        "workflow_stage",
        "applications",
        _stage_check("current_stage", nullable=False),
    )
    op.create_check_constraint(
        "workflow_stage",
        "sla_configs",
        _stage_check("stage", nullable=False),
    )
    op.create_check_constraint(
        "application_status_from",
        "workflow_events",
        _status_check("from_status", nullable=True),
    )
    op.create_check_constraint(
        "application_status_to",
        "workflow_events",
        _status_check("to_status", nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "workflow_definitions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("key", sa.String(32), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("track", sa.String(32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("apH_clause", sa.String(64), nullable=False),
        sa.Column(
            "needs_verification",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_workflow_definitions_key"),
    )
    op.create_index("ix_workflow_definitions_key", "workflow_definitions", ["key"])
    op.create_index("ix_workflow_definitions_track", "workflow_definitions", ["track"])

    op.create_table(
        "workflow_states",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("is_initial", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_terminal", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("apH_clause", sa.String(64), nullable=False),
        sa.Column(
            "needs_verification",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["definition_id"], ["workflow_definitions.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "definition_id", "code", name="uq_workflow_states_definition_code"
        ),
        sa.CheckConstraint("sort_order >= 0", name="workflow_state_sort_non_negative"),
        sa.CheckConstraint(_status_check("code", nullable=False), name="application_status"),
        sa.CheckConstraint(_stage_check("stage", nullable=False), name="workflow_stage"),
    )
    op.create_index(
        "ix_workflow_states_definition_id", "workflow_states", ["definition_id"]
    )
    op.create_index(
        "ix_workflow_states_definition_sort",
        "workflow_states",
        ["definition_id", "sort_order"],
    )

    op.create_table(
        "workflow_transitions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_state", sa.String(32), nullable=False),
        sa.Column("to_state", sa.String(32), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "allowed_roles",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "guard_expr",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "side_effects",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("requires", sa.String(32), nullable=False, server_default="none"),
        sa.Column("tone", sa.String(16), nullable=False, server_default="secondary"),
        sa.Column("sla_stage", sa.String(32), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("apH_clause", sa.String(64), nullable=False),
        sa.Column(
            "needs_verification",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["definition_id"], ["workflow_definitions.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "definition_id",
            "from_state",
            "action",
            "priority",
            name="uq_workflow_transitions_definition_edge",
        ),
        sa.CheckConstraint(
            _status_check("from_state", nullable=False), name="application_status_from"
        ),
        sa.CheckConstraint(
            _status_check("to_state", nullable=False), name="application_status_to"
        ),
        sa.CheckConstraint(_stage_check("sla_stage", nullable=True), name="workflow_stage"),
    )
    op.create_index(
        "ix_workflow_transitions_definition_id",
        "workflow_transitions",
        ["definition_id"],
    )
    op.create_index("ix_workflow_transitions_action", "workflow_transitions", ["action"])
    op.create_index(
        "ix_workflow_transitions_lookup",
        "workflow_transitions",
        ["definition_id", "from_state", "action"],
    )

    op.add_column(
        "application_type_routes",
        sa.Column("workflow_key", sa.String(32), nullable=True),
    )
    op.add_column(
        "application_type_routes",
        sa.Column(
            "not_implemented",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "application_type_routes",
        sa.Column("not_implemented_note", sa.String(255), nullable=True),
    )
    op.create_index(
        "ix_application_type_routes_workflow_key",
        "application_type_routes",
        ["workflow_key"],
    )

    op.create_table(
        "decision_letter_number_seq",
        sa.Column("academic_year", sa.String(9), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("academic_year"),
    )

    # ------------------------------------------------------------------
    # Remap pre-APH rows, then re-create the enum check constraints.
    # ------------------------------------------------------------------
    _drop_status_checks()
    for old, new in STATUS_REMAP:
        op.execute(
            f"UPDATE applications SET status = '{new}' WHERE status = '{old}'"
        )
        op.execute(
            f"UPDATE workflow_events SET from_status = '{new}' WHERE from_status = '{old}'"
        )
        op.execute(
            f"UPDATE workflow_events SET to_status = '{new}' WHERE to_status = '{old}'"
        )

    op.execute(
        """
        UPDATE applications
        SET data = jsonb_set(
            COALESCE(data, '{}'::jsonb),
            '{migration_note}',
            to_jsonb(
                'Conditional approval was removed; this row was recorded as LOA_ISSUED '
                '(APH 4.9c, 2.27).'::text
            ),
            true
        )
        WHERE data ? 'decision'
          AND data -> 'decision' ->> 'outcome' = 'CONDITIONALLY_APPROVED'
        """
    )
    op.execute(
        """
        UPDATE applications
        SET data = jsonb_set(
            data,
            '{decision,outcome}',
            to_jsonb('APPROVED'::text),
            true
        )
        WHERE data ? 'decision'
          AND data -> 'decision' ->> 'outcome' = 'CONDITIONALLY_APPROVED'
        """
    )

    _create_status_checks()
    _insert_alert_triggers()


def downgrade() -> None:
    _drop_status_checks()

    # Best-effort reverse mapping; information about the old values was lost.
    op.execute(
        "UPDATE applications SET status = 'APPROVED' WHERE status = 'ACTIVE_LOA'"
    )
    op.execute(
        "UPDATE workflow_events SET to_status = 'APPROVED' "
        "WHERE to_status = 'ACTIVE_LOA'"
    )
    op.execute(
        "UPDATE workflow_events SET from_status = 'APPROVED' "
        "WHERE from_status = 'ACTIVE_LOA'"
    )
    op.execute("UPDATE applications SET status = 'REJECTED' WHERE status = 'FINAL_LOR'")
    op.execute(
        "UPDATE workflow_events SET to_status = 'REJECTED' WHERE to_status = 'FINAL_LOR'"
    )
    op.execute(
        "UPDATE workflow_events SET from_status = 'REJECTED' "
        "WHERE from_status = 'FINAL_LOR'"
    )

    _create_status_checks()

    op.execute(
        "DELETE FROM alert_trigger_catalogue "
        "WHERE code IN ('APPEAL_WINDOW_CLOSING', 'DEPOSIT_DUE')"
    )

    op.drop_table("decision_letter_number_seq")
    op.drop_index(
        "ix_application_type_routes_workflow_key",
        table_name="application_type_routes",
    )
    op.drop_column("application_type_routes", "not_implemented_note")
    op.drop_column("application_type_routes", "not_implemented")
    op.drop_column("application_type_routes", "workflow_key")
    op.drop_table("workflow_transitions")
    op.drop_table("workflow_states")
    op.drop_table("workflow_definitions")
