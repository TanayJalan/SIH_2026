"""compliance results: persist per-rule status and explanation

Revision ID: 0005_compliance_result_status
Revises: 0004_compliance_engine
Create Date: 2026-10-23 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_compliance_result_status"
down_revision: str | None = "0004_compliance_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OPERATOR_ALLOWED = (
    "operator IN ('<', '<=', '=', '==', '>=', '>', '!=', 'BETWEEN', 'EXISTS')"
)
_LEGACY_OPERATOR_ALLOWED = (
    "operator IN ('<', '<=', '=', '>=', '>', '!=', 'BETWEEN', 'EXISTS')"
)


def upgrade() -> None:
    op.add_column(
        "compliance_results",
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="PASS",
            nullable=False,
        ),
    )
    op.add_column(
        "compliance_results",
        sa.Column("message", sa.Text(), nullable=True),
    )
    op.alter_column(
        "compliance_results",
        "observed_value",
        existing_type=sa.Numeric(12, 4),
        nullable=True,
    )
    op.execute(
        "UPDATE compliance_results "
        "SET status = CASE WHEN passed THEN 'PASS' ELSE 'FAIL' END"
    )
    op.create_check_constraint(
        "status_allowed",
        "compliance_results",
        "status IN ('PASS', 'FAIL', 'NOT_ASSESSED')",
    )

    op.drop_constraint(
        "operator_allowed",
        "compliance_rules",
        type_="check",
    )
    op.create_check_constraint(
        "operator_allowed",
        "compliance_rules",
        _OPERATOR_ALLOWED,
    )


def downgrade() -> None:
    op.drop_constraint(
        "operator_allowed",
        "compliance_rules",
        type_="check",
    )
    # ``==`` is an alias for ``=``; normalise it before restoring the legacy
    # constraint so a downgrade cannot fail on a rule created with ``==``.
    op.execute("UPDATE compliance_rules SET operator = '=' WHERE operator = '=='")
    op.create_check_constraint(
        "operator_allowed",
        "compliance_rules",
        _LEGACY_OPERATOR_ALLOWED,
    )

    op.drop_constraint(
        "status_allowed",
        "compliance_results",
        type_="check",
    )
    op.execute("DELETE FROM compliance_results WHERE observed_value IS NULL")
    op.alter_column(
        "compliance_results",
        "observed_value",
        existing_type=sa.Numeric(12, 4),
        nullable=False,
    )
    op.drop_column("compliance_results", "message")
    op.drop_column("compliance_results", "status")
