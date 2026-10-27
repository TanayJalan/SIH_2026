"""compliance rule library: clause metadata, aggregates and norm config

Revision ID: 0014_compliance_rule_library
Revises: 0013_workflow_definition
Create Date: 2026-10-27 10:00:00.000000

Adds the columns the APH rule library needs (mandatory/illustrative flags,
per-rule weight, unit, explanation template, aggregate operands and APH 7.4
penalty codes), widens the operator whitelist for the safe aggregate
operators, and allows the calculator configuration keys.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0014_compliance_rule_library"
down_revision: str | None = "0013_workflow_definition"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OPERATORS = (
    "'<', '<=', '=', '==', '>=', '>', '!=', 'BETWEEN', 'EXISTS', "
    "'RATIO', 'SUM', 'COUNT', 'DATE_NOT_EXPIRED'"
)

_CONFIG_KEYS = (
    "'severity_weights', 'rag_breakpoints', 'committee_compositions', "
    "'fsr_ratios', 'cadre_ratios', 'area_norms', 'bandwidth_tiers', "
    "'library_norms', 'pc_ratios', 'penalty_actions'"
)


def upgrade() -> None:
    op.add_column(
        "compliance_rules",
        sa.Column(
            "mandatory",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "compliance_rules",
        sa.Column(
            "illustrative",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "compliance_rules",
        sa.Column("weight", sa.Numeric(8, 2), nullable=True),
    )
    op.add_column(
        "compliance_rules",
        sa.Column("unit", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "compliance_rules",
        sa.Column("explanation_template", sa.Text(), nullable=True),
    )
    op.add_column(
        "compliance_rules",
        sa.Column(
            "metric_params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "compliance_rules",
        sa.Column(
            "penalty_codes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.alter_column("compliance_rules", "operator", type_=sa.String(length=32))

    op.drop_constraint("operator_allowed", "compliance_rules", type_="check")
    op.create_check_constraint(
        "operator_allowed",
        "compliance_rules",
        f"operator IN ({_OPERATORS})",
    )

    op.drop_constraint(
        "compliance_config_key_allowed", "compliance_config", type_="check"
    )
    op.create_check_constraint(
        "compliance_config_key_allowed",
        "compliance_config",
        f"key IN ({_CONFIG_KEYS})",
    )


def downgrade() -> None:
    op.drop_constraint(
        "compliance_config_key_allowed", "compliance_config", type_="check"
    )
    op.create_check_constraint(
        "compliance_config_key_allowed",
        "compliance_config",
        "key IN ('severity_weights', 'rag_breakpoints', 'committee_compositions')",
    )

    op.drop_constraint("operator_allowed", "compliance_rules", type_="check")
    op.create_check_constraint(
        "operator_allowed",
        "compliance_rules",
        "operator IN ('<', '<=', '=', '==', '>=', '>', '!=', 'BETWEEN', 'EXISTS')",
    )
    op.alter_column("compliance_rules", "operator", type_=sa.String(length=8))

    op.drop_column("compliance_rules", "penalty_codes")
    op.drop_column("compliance_rules", "metric_params")
    op.drop_column("compliance_rules", "explanation_template")
    op.drop_column("compliance_rules", "unit")
    op.drop_column("compliance_rules", "weight")
    op.drop_column("compliance_rules", "illustrative")
    op.drop_column("compliance_rules", "mandatory")
