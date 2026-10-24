"""application workspace: required documents and upload metadata

Revision ID: 0002_application_workspace
Revises: 0001_initial
Create Date: 2026-10-22 21:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_application_workspace"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REQUIRED_DOCUMENTS = [
    ("NEW", "AFFILIATION_CERTIFICATE", True),
    ("NEW", "LAND_OWNERSHIP_DOCUMENT", True),
    ("NEW", "BUILDING_PLAN_APPROVAL", True),
    ("NEW", "FACULTY_DETAILS", True),
    ("NEW", "FINANCIAL_STATEMENT", True),
    ("NEW", "MANDATORY_DISCLOSURE", True),
    ("NEW", "NAAC_NBA_CERTIFICATE", False),
    ("EXTENSION", "AFFILIATION_CERTIFICATE", True),
    ("EXTENSION", "LAND_OWNERSHIP_DOCUMENT", True),
    ("EXTENSION", "BUILDING_PLAN_APPROVAL", True),
    ("EXTENSION", "FACULTY_DETAILS", True),
    ("EXTENSION", "FINANCIAL_STATEMENT", True),
    ("EXTENSION", "MANDATORY_DISCLOSURE", True),
    ("EXTENSION", "NAAC_NBA_CERTIFICATE", False),
    ("INTAKE_CHANGE", "EXISTING_APPROVAL_LETTER", True),
    ("INTAKE_CHANGE", "FACULTY_DETAILS", True),
    ("INTAKE_CHANGE", "INFRASTRUCTURE_PLAN", True),
    ("INTAKE_CHANGE", "FINANCIAL_STATEMENT", True),
    ("INTAKE_CHANGE", "MANDATORY_DISCLOSURE", True),
    ("INTAKE_CHANGE", "NAAC_NBA_CERTIFICATE", False),
]

_SLA_CONFIGS = [
    ("APPLICATION", 30, 20, "REGIONAL_HEAD"),
    ("DOCUMENT_VERIFICATION", 10, 7, "SCRUTINY_OFFICER"),
    ("SCRUTINY", 15, 10, "REGIONAL_HEAD"),
    ("INSPECTION", 20, 14, "REGIONAL_HEAD"),
    ("DECISION", 10, 7, "SUPER_ADMIN"),
]


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "content_type",
            sa.String(length=100),
            server_default="application/octet-stream",
            nullable=False,
        ),
    )
    op.add_column(
        "documents",
        sa.Column("size_bytes", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.create_check_constraint(
        "ck_documents_size_bytes_non_negative",
        "documents",
        "size_bytes >= 0",
    )

    op.create_table(
        "required_documents",
        sa.Column(
            "application_type",
            sa.Enum(
                "NEW",
                "EXTENSION",
                "INTAKE_CHANGE",
                name="application_type",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("doc_type", sa.String(length=100), nullable=False),
        sa.Column("mandatory", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_required_documents")),
        sa.UniqueConstraint(
            "application_type",
            "doc_type",
            name="uq_required_documents_application_type_doc_type",
        ),
    )
    op.create_index(
        op.f("ix_required_documents_application_type"),
        "required_documents",
        ["application_type"],
        unique=False,
    )

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            INSERT INTO required_documents (application_type, doc_type, mandatory)
            VALUES (:application_type, :doc_type, :mandatory)
            ON CONFLICT (application_type, doc_type) DO NOTHING
            """
        ),
        [
            {"application_type": application_type, "doc_type": doc_type, "mandatory": mandatory}
            for application_type, doc_type, mandatory in _REQUIRED_DOCUMENTS
        ],
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO sla_configs (stage, duration_days, escalation_after_days, escalate_to_role)
            VALUES (:stage, :duration_days, :escalation_after_days, :escalate_to_role)
            ON CONFLICT (stage) DO NOTHING
            """
        ),
        [
            {
                "stage": stage,
                "duration_days": duration_days,
                "escalation_after_days": escalation_after_days,
                "escalate_to_role": escalate_to_role,
            }
            for stage, duration_days, escalation_after_days, escalate_to_role in _SLA_CONFIGS
        ],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_required_documents_application_type"),
        table_name="required_documents",
    )
    op.drop_table("required_documents")
    op.drop_constraint(
        "ck_documents_size_bytes_non_negative",
        "documents",
        type_="check",
    )
    op.drop_column("documents", "size_bytes")
    op.drop_column("documents", "content_type")
