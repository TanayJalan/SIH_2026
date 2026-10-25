"""decisions, decision letters, Council ratification, alert catalogue and deadlines

Revision ID: 0010_decisions_deadlines
Revises: 0009_aph_data
Create Date: 2026-10-25 01:30:00.000000

Adds the APH decision/letter/ratification tables, moves the alert-trigger
vocabulary from a hard-coded ``CHECK`` into ``alert_trigger_catalogue``, and
introduces data-driven ``DeadlineRule`` and ``Timer`` tables.

The eight existing trigger values are copied into the catalogue before the
``CHECK`` is removed, so existing alert rules keep working without a rewrite.
Deadline rules are reference data with their APH clause; the show-cause reply
duration is marked ``needs_verification`` because APH does not state one.
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_decisions_deadlines"
down_revision: str | None = "0009_aph_data"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DECISION_BODIES = ("EC", "COUNCIL", "SAC", "SHC")
DECISION_OUTCOMES = (
    "LOA",
    "EOA",
    "LOD",
    "LOR",
    "RECOMMEND",
    "NOT_RECOMMEND",
    "SEND_BACK",
)
DECISION_LETTER_TYPES = (
    "LOA",
    "EOA",
    "LOD",
    "LOR",
    "SPEAKING_ORDER",
    "DEFICIENCY_REPORT",
    "SHOW_CAUSE",
)
TIMER_STATUSES = ("PENDING", "DUE", "BREACHED", "COMPLETED", "CANCELLED")
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

# The engine handler keys are unchanged; the catalogue decouples them from the
# stored trigger code so a new statutory trigger is a data change.
ALERT_TRIGGERS = (
    (
        "DEADLINE_APPROACHING",
        "DEADLINE_APPROACHING",
        "An application deadline is approaching.",
        "APH 1.2",
        False,
    ),
    (
        "SLA_BREACHED",
        "SLA_BREACHED",
        "A configured processing deadline has passed.",
        "DEMO",
        True,
    ),
    (
        "DEFICIENCY_DUE",
        "DEFICIENCY_DUE",
        "A deficiency response is due.",
        "APH 2.4",
        False,
    ),
    (
        "DEFICIENCY_OVERDUE",
        "DEFICIENCY_OVERDUE",
        "A deficiency response is overdue.",
        "APH 2.25c",
        False,
    ),
    (
        "DOCUMENT_EXPIRING",
        "DOCUMENT_EXPIRING",
        "A document is approaching its expiry date.",
        "APH 6.17h",
        False,
    ),
    (
        "COMPLIANCE_RED",
        "COMPLIANCE_RED",
        "An institution has moved to RED compliance status.",
        "APH 7.13",
        False,
    ),
    (
        "APPLICATION_STATUS_CHANGED",
        "APPLICATION_STATUS_CHANGED",
        "An application moved to a new workflow status.",
        "APH 1.4.3",
        False,
    ),
    (
        "INSPECTION_SCHEDULED",
        "INSPECTION_SCHEDULED",
        "An Expert Visit Committee inspection was scheduled.",
        "APH 1.9a",
        False,
    ),
)

SECURITY_DEPOSIT_LADDER = [
    {
        "level": 1,
        "penalty_percent": 10,
        "until": "05-31",
        "action": "PENALTY",
        "apH_clause": "APH 2.25f",
    },
    {
        "level": 2,
        "penalty_percent": 20,
        "until": "07-31",
        "action": "PENALTY",
        "apH_clause": "APH 2.25f",
    },
    {
        "level": 3,
        "penalty_percent": None,
        "until": None,
        "action": "WITHDRAWAL",
        "apH_clause": "APH 2.25f",
    },
]

# (code, start_event, duration_days, owner_role, penalty_ladder, clause,
#  start_event_configurable, needs_verification)
DEADLINE_RULES = (
    (
        "APPEAL_WINDOW",
        "DECISION_UPLOADED",
        7,
        "REGIONAL_OFFICER",
        [],
        "APH 1.11a, 2.24a",
        True,
        False,
    ),
    (
        "SECURITY_DEPOSIT",
        "SECURITY_DEPOSIT_INTIMATION",
        15,
        "INSTITUTION_ADMIN",
        SECURITY_DEPOSIT_LADDER,
        "APH 2.25f",
        False,
        False,
    ),
    (
        "ENROLMENT_UPLOAD",
        "ENROLMENT_UPLOAD_30NOV",
        0,
        "INSTITUTION_ADMIN",
        [],
        "APH 2.25n",
        False,
        False,
    ),
    (
        "IC_REPORT",
        "IC_REPORT_30JUN",
        0,
        "INSTITUTION_ADMIN",
        [],
        "APH 6.48g",
        False,
        False,
    ),
    (
        "CLOSURE_REVOKE",
        "CLOSURE_REVOKE_10APR",
        0,
        "INSTITUTION_ADMIN",
        [],
        "APH 2.3.3g",
        False,
        False,
    ),
    (
        "SHOW_CAUSE_REPLY",
        "SHOW_CAUSE_ISSUED",
        15,
        "INSTITUTION_ADMIN",
        [],
        "APH 2.23.3",
        True,
        True,
    ),
)


def _in(column: str, values: Sequence[str]) -> str:
    joined = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({joined})"


def _insert_alert_triggers() -> None:
    statement = sa.text(
        """
        INSERT INTO alert_trigger_catalogue
            (code, handler_key, description, "apH_clause", needs_verification)
        VALUES
            (:code, :handler_key, :description, :clause, :needs_verification)
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


def _insert_deadline_rules() -> None:
    statement = sa.text(
        """
        INSERT INTO deadline_rules
            (code, start_event, duration_days, owner_role, penalty_ladder,
             "apH_clause", start_event_configurable, needs_verification)
        VALUES
            (:code, :start_event, :duration_days, :owner_role,
             CAST(:penalty_ladder AS jsonb), :clause, :configurable,
             :needs_verification)
        ON CONFLICT (code) DO NOTHING
        """
    )
    bind = op.get_bind()
    for (
        code,
        start_event,
        duration_days,
        owner_role,
        penalty_ladder,
        clause,
        configurable,
        needs_verification,
    ) in DEADLINE_RULES:
        bind.execute(
            statement,
            {
                "code": code,
                "start_event": start_event,
                "duration_days": duration_days,
                "owner_role": owner_role,
                "penalty_ladder": json.dumps(penalty_ladder),
                "clause": clause,
                "configurable": configurable,
                "needs_verification": needs_verification,
            },
        )


def upgrade() -> None:
    # The trigger vocabulary becomes data. The eight legacy values are copied
    # into the catalogue before the CHECK disappears.
    op.drop_constraint("trigger_type_allowed", "alert_rules", type_="check")

    op.create_table(
        "alert_trigger_catalogue",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("handler_key", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("apH_clause", sa.String(length=64), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_alert_trigger_catalogue"),
        sa.UniqueConstraint("code", name="uq_alert_trigger_catalogue_code"),
    )
    op.create_index(
        op.f("ix_alert_trigger_catalogue_handler_key"),
        "alert_trigger_catalogue",
        ["handler_key"],
        unique=False,
    )

    op.create_table(
        "deadline_rules",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("start_event", sa.String(length=64), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("owner_role", sa.String(length=32), nullable=False),
        sa.Column(
            "penalty_ladder",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("apH_clause", sa.String(length=64), nullable=False),
        sa.Column(
            "start_event_configurable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
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
        sa.PrimaryKeyConstraint("id", name="pk_deadline_rules"),
        sa.UniqueConstraint("code", name="uq_deadline_rules_code"),
        sa.CheckConstraint(
            "duration_days >= 0",
            name="deadline_duration_non_negative",
        ),
    )
    op.create_index(
        op.f("ix_deadline_rules_start_event"),
        "deadline_rules",
        ["start_event"],
        unique=False,
    )
    op.create_check_constraint(
        "user_role",
        "deadline_rules",
        _in("owner_role", ROLE_VALUES),
    )

    op.create_table(
        "decisions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("body", sa.String(length=16), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("decided_on", sa.Date(), nullable=False),
        sa.Column("committee_id", sa.UUID(), nullable=True),
        sa.Column(
            "quorum_met",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("notes", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("apH_clause", sa.String(length=64), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_decisions"),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_decisions_application_id_applications",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["committee_id"],
            ["committees.id"],
            name="fk_decisions_committee_id_committees",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        op.f("ix_decisions_application_id"), "decisions", ["application_id"], unique=False
    )
    op.create_index(
        op.f("ix_decisions_committee_id"), "decisions", ["committee_id"], unique=False
    )
    op.create_index(
        "ix_decisions_application_decided",
        "decisions",
        ["application_id", "decided_on"],
        unique=False,
    )
    op.create_index(
        "ix_decisions_body_outcome",
        "decisions",
        ["body", "outcome"],
        unique=False,
    )
    op.create_check_constraint("decision_body", "decisions", _in("body", DECISION_BODIES))
    op.create_check_constraint(
        "decision_outcome", "decisions", _in("outcome", DECISION_OUTCOMES)
    )

    op.create_table(
        "decision_letters",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("decision_id", sa.UUID(), nullable=True),
        sa.Column("letter_type", sa.String(length=32), nullable=False),
        sa.Column("letter_number", sa.String(length=64), nullable=False),
        sa.Column("issued_on", sa.Date(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("appeal_clock_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("appeal_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("pdf_path", sa.String(length=512), nullable=True),
        sa.Column("acknowledged_by", sa.UUID(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_decision_letters"),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_decision_letters_application_id_applications",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["decision_id"],
            ["decisions.id"],
            name="fk_decision_letters_decision_id_decisions",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["acknowledged_by"],
            ["users.id"],
            name="fk_decision_letters_acknowledged_by_users",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("letter_number", name="uq_decision_letters_letter_number"),
        sa.CheckConstraint(
            "appeal_clock_start IS NULL OR appeal_deadline IS NULL "
            "OR appeal_deadline >= appeal_clock_start",
            name="decision_letter_appeal_window_ordered",
        ),
    )
    op.create_index(
        op.f("ix_decision_letters_application_id"),
        "decision_letters",
        ["application_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_decision_letters_decision_id"),
        "decision_letters",
        ["decision_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_decision_letters_letter_type"),
        "decision_letters",
        ["letter_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_decision_letters_acknowledged_by"),
        "decision_letters",
        ["acknowledged_by"],
        unique=False,
    )
    op.create_index(
        "ix_decision_letters_application_issued",
        "decision_letters",
        ["application_id", "issued_on"],
        unique=False,
    )
    op.create_index(
        "ix_decision_letters_appeal_deadline",
        "decision_letters",
        ["appeal_deadline"],
        unique=False,
    )
    op.create_check_constraint(
        "decision_letter_type",
        "decision_letters",
        _in("letter_type", DECISION_LETTER_TYPES),
    )

    op.create_table(
        "council_ratifications",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("decision_id", sa.UUID(), nullable=False),
        sa.Column("ratified_on", sa.Date(), nullable=False),
        sa.Column("ratified_by", sa.UUID(), nullable=True),
        sa.Column("ec_recommendation_ref", sa.String(length=128), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_council_ratifications"),
        sa.ForeignKeyConstraint(
            ["decision_id"],
            ["decisions.id"],
            name="fk_council_ratifications_decision_id_decisions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ratified_by"],
            ["users.id"],
            name="fk_council_ratifications_ratified_by_users",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "decision_id", name="uq_council_ratifications_decision_id"
        ),
    )
    op.create_index(
        op.f("ix_council_ratifications_ratified_by"),
        "council_ratifications",
        ["ratified_by"],
        unique=False,
    )

    op.create_table(
        "timers",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("deadline_rule_id", sa.UUID(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "fired_levels",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
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
        sa.PrimaryKeyConstraint("id", name="pk_timers"),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_timers_application_id_applications",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["deadline_rule_id"],
            ["deadline_rules.id"],
            name="fk_timers_deadline_rule_id_deadline_rules",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(op.f("ix_timers_application_id"), "timers", ["application_id"], unique=False)
    op.create_index(
        op.f("ix_timers_deadline_rule_id"), "timers", ["deadline_rule_id"], unique=False
    )
    op.create_index(op.f("ix_timers_status"), "timers", ["status"], unique=False)
    op.create_index(
        "ix_timers_application_status",
        "timers",
        ["application_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_timers_status_due",
        "timers",
        ["status", "due_at"],
        unique=False,
    )
    op.create_check_constraint("timer_status", "timers", _in("status", TIMER_STATUSES))

    _insert_alert_triggers()
    _insert_deadline_rules()


def downgrade() -> None:
    # Refuse to recreate the old CHECK if a data-only trigger is in use.
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM alert_rules
                WHERE NOT ({_in("trigger_type", tuple(row[0] for row in ALERT_TRIGGERS))})
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade: alert_rules contains a trigger code that '
                    'is not in the legacy eight-value CHECK';
            END IF;
        END $$;
        """
    )

    op.drop_index("ix_timers_status_due", table_name="timers")
    op.drop_index("ix_timers_application_status", table_name="timers")
    op.drop_index(op.f("ix_timers_status"), table_name="timers")
    op.drop_index(op.f("ix_timers_deadline_rule_id"), table_name="timers")
    op.drop_index(op.f("ix_timers_application_id"), table_name="timers")
    op.drop_table("timers")

    op.drop_index(
        op.f("ix_council_ratifications_ratified_by"),
        table_name="council_ratifications",
    )
    op.drop_table("council_ratifications")

    op.drop_index(
        "ix_decision_letters_appeal_deadline", table_name="decision_letters"
    )
    op.drop_index(
        "ix_decision_letters_application_issued", table_name="decision_letters"
    )
    op.drop_index(
        op.f("ix_decision_letters_acknowledged_by"), table_name="decision_letters"
    )
    op.drop_index(
        op.f("ix_decision_letters_letter_type"), table_name="decision_letters"
    )
    op.drop_index(
        op.f("ix_decision_letters_decision_id"), table_name="decision_letters"
    )
    op.drop_index(
        op.f("ix_decision_letters_application_id"), table_name="decision_letters"
    )
    op.drop_table("decision_letters")

    op.drop_index("ix_decisions_body_outcome", table_name="decisions")
    op.drop_index("ix_decisions_application_decided", table_name="decisions")
    op.drop_index(op.f("ix_decisions_committee_id"), table_name="decisions")
    op.drop_index(op.f("ix_decisions_application_id"), table_name="decisions")
    op.drop_table("decisions")

    op.drop_index(op.f("ix_deadline_rules_start_event"), table_name="deadline_rules")
    op.drop_table("deadline_rules")

    op.drop_index(
        op.f("ix_alert_trigger_catalogue_handler_key"),
        table_name="alert_trigger_catalogue",
    )
    op.drop_table("alert_trigger_catalogue")

    op.create_check_constraint(
        "trigger_type_allowed",
        "alert_rules",
        "trigger_type IN ("
        "'DEADLINE_APPROACHING', "
        "'SLA_BREACHED', "
        "'DEFICIENCY_DUE', "
        "'DEFICIENCY_OVERDUE', "
        "'DOCUMENT_EXPIRING', "
        "'COMPLIANCE_RED', "
        "'APPLICATION_STATUS_CHANGED', "
        "'INSPECTION_SCHEDULED'"
        ")",
    )
