"""compliance engine: rule bounds, config and institution snapshots

Revision ID: 0004_compliance_engine
Revises: 0003_workflow_engine
Create Date: 2026-10-23 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004_compliance_engine"
down_revision: str | None = "0003_workflow_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "compliance_rules",
        sa.Column("threshold_max", sa.Numeric(12, 4), nullable=True),
    )
    op.drop_constraint("operator_allowed", "compliance_rules", type_="check")
    op.create_check_constraint(
        "operator_allowed",
        "compliance_rules",
        "operator IN ('<', '<=', '=', '>=', '>', '!=', 'BETWEEN', 'EXISTS')",
    )

    op.create_table(
        "compliance_config",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
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
        sa.CheckConstraint(
            "key IN ('severity_weights', 'rag_breakpoints')",
            name=op.f("ck_compliance_config_compliance_config_key_allowed"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_compliance_config")),
    )
    op.create_index(op.f("ix_compliance_config_key"), "compliance_config", ["key"], unique=True)

    op.create_table(
        "compliance_snapshots",
        sa.Column(
            "institution_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "application_id",
            sa.UUID(),
            nullable=True,
        ),
        sa.Column("score", sa.Numeric(5, 2), nullable=False),
        sa.Column(
            "status",
            sa.Enum("GREEN", "AMBER", "RED", name="compliance_health", native_enum=False, length=8, create_constraint=True),
            nullable=False,
        ),
        sa.Column("failed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_critical_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_high_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("missing_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("trigger", sa.String(length=32), server_default="manual", nullable=False),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_compliance_snapshots")),
    )
    op.create_index(
        "ix_compliance_snapshots_institution_id", "compliance_snapshots", ["institution_id"], unique=False
    )
    op.create_index(
        "ix_compliance_snapshots_status", "compliance_snapshots", ["status"], unique=False
    )
    op.create_index(
        "ix_compliance_snapshots_evaluated_at", "compliance_snapshots", ["evaluated_at"], unique=False
    )
    op.create_index(
        "ix_compliance_snapshots_institution_time",
        "compliance_snapshots",
        ["institution_id", "evaluated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_compliance_snapshots_institution_time", table_name="compliance_snapshots")
    op.drop_index("ix_compliance_snapshots_evaluated_at", table_name="compliance_snapshots")
    op.drop_index("ix_compliance_snapshots_status", table_name="compliance_snapshots")
    op.drop_index("ix_compliance_snapshots_institution_id", table_name="compliance_snapshots")
    op.drop_table("compliance_snapshots")
    op.drop_index(op.f("ix_compliance_config_key"), table_name="compliance_config")
    op.drop_table("compliance_config")
    op.drop_constraint("operator_allowed", "compliance_rules", type_="check")
    op.create_check_constraint(
        "operator_allowed",
        "compliance_rules",
        "operator IN ('<', '<=', '=', '>=', '>', '!=')",
    )
    op.drop_column("compliance_rules", "threshold_max")
