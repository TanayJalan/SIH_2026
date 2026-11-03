"""Annexure-11 course nomenclature and Annexure-14 competent authorities

Revision ID: 0025_annexure_reference
Revises: 0024_complaint_penal_lifecycle
Create Date: 2026-11-02 10:00:00.000000

The demo wizard offers the approved Annexure-11 course names and the
Annexure-14 land/building certificate authorities. Both are reference data, so
they live in their own tables and are loaded from the generated JSON files in
``backend/seeds/aph``. No existing row is touched.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0025_annexure_reference"
down_revision: str | None = "0024_complaint_penal_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Enum columns in this project are VARCHAR backed with a CHECK constraint
# (see ``app/models/types.py``), not native PostgreSQL enum types.
_REGION_VALUES = (
    "CENTRAL",
    "EASTERN",
    "NORTHERN",
    "NORTH_WESTERN",
    "SOUTH_CENTRAL",
    "SOUTHERN",
    "SOUTH_WESTERN",
    "WESTERN",
)


def upgrade() -> None:
    op.create_table(
        "nomenclature_courses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("level", sa.String(64), nullable=False),
        sa.Column("programme_family", sa.String(64), nullable=False),
        sa.Column("course_name", sa.String(255), nullable=False),
        sa.Column("source_section", sa.String(16), nullable=False),
        sa.Column(
            "is_emerging", sa.Boolean(), nullable=False, server_default=sa.text("false")
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
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "level", "programme_family", "course_name",
            name="uq_nomenclature_level_family_course",
        ),
    )
    op.create_index(
        "ix_nomenclature_courses_level", "nomenclature_courses", ["level"], unique=False
    )
    op.create_index(
        "ix_nomenclature_courses_programme_family",
        "nomenclature_courses",
        ["programme_family"],
        unique=False,
    )
    op.create_index(
        "ix_nomenclature_level_family",
        "nomenclature_courses",
        ["level", "programme_family"],
        unique=False,
    )

    op.create_table(
        "competent_authorities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("state", sa.String(100), nullable=False),
        sa.Column(
            "aicte_region",
            sa.String(32),
            nullable=False,
        ),
        sa.Column("land_use_authority", sa.Text(), nullable=True),
        sa.Column("site_plan_authority", sa.Text(), nullable=True),
        sa.Column("building_plan_authority", sa.Text(), nullable=True),
        sa.Column("occupation_authority", sa.Text(), nullable=True),
        sa.Column("source_text", sa.Text(), nullable=True),
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
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("state", name="uq_competent_authorities_state"),
    )
    op.create_index(
        "ix_competent_authorities_state", "competent_authorities", ["state"], unique=False
    )
    op.create_check_constraint(
        "aicte_region",
        "competent_authorities",
        "aicte_region IN ("
        + ", ".join(f"'{value}'" for value in _REGION_VALUES)
        + ")",
    )
    op.create_index(
        "ix_competent_authorities_aicte_region",
        "competent_authorities",
        ["aicte_region"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_competent_authorities_aicte_region", table_name="competent_authorities"
    )
    op.drop_index("ix_competent_authorities_state", table_name="competent_authorities")
    op.drop_table("competent_authorities")
    op.drop_index("ix_nomenclature_level_family", table_name="nomenclature_courses")
    op.drop_index(
        "ix_nomenclature_courses_programme_family", table_name="nomenclature_courses"
    )
    op.drop_index("ix_nomenclature_courses_level", table_name="nomenclature_courses")
    op.drop_table("nomenclature_courses")
