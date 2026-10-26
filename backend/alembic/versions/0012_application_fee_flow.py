"""application fee flow: Security Deposit rate table

Revision ID: 0012_application_fee_flow
Revises: 0011_committee_expert_pool
Create Date: 2026-10-26 10:00:00.000000

Adds:
  * ``security_deposit_schedules`` – the Table 1.4 base deposit per programme
    family and level, used by the fee calculator (APH Table 1.4, 2.25f).

``documents.signed_with_dsc`` and the application fee columns already exist in
the schema, so no existing table is altered.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_application_fee_flow"
down_revision: str | None = "0011_committee_expert_pool"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "security_deposit_schedules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("programme_family", sa.String(64), nullable=False),
        sa.Column("level", sa.String(32), nullable=False),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column(
            "doubled_for_leased",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
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
        sa.CheckConstraint(
            "amount_paise >= 0",
            name="security_deposit_schedule_amount_non_negative",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "programme_family",
            "level",
            name="uq_security_deposit_schedules_family_level",
        ),
    )
    op.create_index(
        "ix_security_deposit_schedules_programme_family",
        "security_deposit_schedules",
        ["programme_family"],
    )
    op.create_index(
        "ix_security_deposit_schedules_level",
        "security_deposit_schedules",
        ["level"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_security_deposit_schedules_level",
        table_name="security_deposit_schedules",
    )
    op.drop_index(
        "ix_security_deposit_schedules_programme_family",
        table_name="security_deposit_schedules",
    )
    op.drop_table("security_deposit_schedules")
