"""alert engine: rule metadata, dedupe keys and escalation state

Revision ID: 0006_alert_engine
Revises: 0005_compliance_result_status
Create Date: 2026-10-23 17:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_alert_engine"
down_revision: str | None = "0005_compliance_result_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # AlertRule metadata used by the admin screen and the rule engine.
    op.add_column("alert_rules", sa.Column("code", sa.String(length=64), nullable=True))
    op.add_column("alert_rules", sa.Column("name", sa.String(length=255), nullable=True))
    op.add_column(
        "alert_rules",
        sa.Column("description", sa.Text(), server_default="", nullable=False),
    )
    op.add_column(
        "alert_rules",
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.execute(
        "UPDATE alert_rules "
        "SET code = 'LEGACY-' || upper(substr(replace(id::text, '-', ''), 1, 12)) "
        "WHERE code IS NULL"
    )
    op.execute(
        "UPDATE alert_rules "
        "SET name = initcap(replace(trigger_type, '_', ' ')) "
        "WHERE name IS NULL"
    )
    op.alter_column("alert_rules", "code", existing_type=sa.String(length=64), nullable=False)
    op.alter_column("alert_rules", "name", existing_type=sa.String(length=255), nullable=False)
    op.create_unique_constraint("uq_alert_rules_code", "alert_rules", ["code"])
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

    # Alert delivery, dedupe and escalation state.
    op.add_column("alerts", sa.Column("dedupe_key", sa.String(length=255), nullable=True))
    op.add_column("alerts", sa.Column("rule_id", sa.UUID(), nullable=True))
    op.add_column("alerts", sa.Column("parent_alert_id", sa.UUID(), nullable=True))
    op.add_column(
        "alerts",
        sa.Column(
            "escalation_level",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "alerts",
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("alerts", sa.Column("acknowledged_by_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_alerts_rule_id_alert_rules",
        "alerts",
        "alert_rules",
        ["rule_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_alerts_parent_alert_id_alerts",
        "alerts",
        "alerts",
        ["parent_alert_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_alerts_acknowledged_by_id_users",
        "alerts",
        "users",
        ["acknowledged_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint("uq_alerts_dedupe_key", "alerts", ["dedupe_key"])
    op.create_index("ix_alerts_rule_id", "alerts", ["rule_id"], unique=False)
    op.create_index("ix_alerts_parent_alert_id", "alerts", ["parent_alert_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_alerts_parent_alert_id", table_name="alerts")
    op.drop_index("ix_alerts_rule_id", table_name="alerts")
    op.drop_constraint("uq_alerts_dedupe_key", "alerts", type_="unique")
    op.drop_constraint("fk_alerts_acknowledged_by_id_users", "alerts", type_="foreignkey")
    op.drop_constraint("fk_alerts_parent_alert_id_alerts", "alerts", type_="foreignkey")
    op.drop_constraint("fk_alerts_rule_id_alert_rules", "alerts", type_="foreignkey")
    op.drop_column("alerts", "acknowledged_by_id")
    op.drop_column("alerts", "acknowledged_at")
    op.drop_column("alerts", "escalation_level")
    op.drop_column("alerts", "parent_alert_id")
    op.drop_column("alerts", "rule_id")
    op.drop_column("alerts", "dedupe_key")

    op.drop_constraint("trigger_type_allowed", "alert_rules", type_="check")
    op.drop_constraint("uq_alert_rules_code", "alert_rules", type_="unique")
    op.drop_column("alert_rules", "is_active")
    op.drop_column("alert_rules", "description")
    op.drop_column("alert_rules", "name")
    op.drop_column("alert_rules", "code")
