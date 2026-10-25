"""expert pool and committee-member selection service tables

Revision ID: 0011_committee_expert_pool
Revises: 0010_decisions_deadlines
Create Date: 2026-10-25 10:00:00.000000

Adds:
  * ``expert_pool`` table – the candidate panel for automated committee
    member selection (APH 1.8a, 1.9a, Annexure-16 16.3–16.7).

No existing tables are altered.  The ``CommitteeService`` uses this table
together with the existing ``committees`` and ``committee_members`` tables.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_committee_expert_pool"
down_revision: str | None = "0010_decisions_deadlines"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "expert_pool",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("designation", sa.String(128), nullable=False),
        sa.Column("institution_name", sa.String(255), nullable=True),
        sa.Column("state", sa.String(100), nullable=False),
        sa.Column("aicte_region", sa.String(32), nullable=False),
        sa.Column("email", sa.String(320), nullable=True, unique=True),
        sa.Column(
            "seat_tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("years_experience", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "is_retired_hc_judge",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "recent_assignment_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_fictional", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "apH_clause",
            sa.String(64),
            nullable=False,
            server_default=sa.text("'APH 1.8a'"),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_expert_pool_is_active", "expert_pool", ["is_active"])
    op.create_index("ix_expert_pool_state", "expert_pool", ["state"])
    op.create_index("ix_expert_pool_aicte_region", "expert_pool", ["aicte_region"])


def downgrade() -> None:
    op.drop_index("ix_expert_pool_aicte_region", table_name="expert_pool")
    op.drop_index("ix_expert_pool_state", table_name="expert_pool")
    op.drop_index("ix_expert_pool_is_active", table_name="expert_pool")
    op.drop_table("expert_pool")
