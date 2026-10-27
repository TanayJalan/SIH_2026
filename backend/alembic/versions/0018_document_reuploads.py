"""document rejection, replacement versions and deficiency linkage

Revision ID: 0018_document_reuploads
Revises: 0017_rule_clause_citations
Create Date: 2026-10-27 15:30:00.000000

APH 1.4.3 locks a submitted application, but 1.8f communicates deficiencies
through the portal and 2.4 gives the institution a chance to comply before
Scrutiny, Re-Scrutiny or a hearing. APH 1.8g then limits Re-Scrutiny to the
listed deficiencies, so a reviewer must be able to reject one document and the
institution must be able to replace exactly that file.

This migration adds the review trail to ``documents``:

* ``rejection_reason_code`` / ``rejection_comment`` / ``rejected_by`` /
  ``rejected_at`` / ``apH_clause`` record the reviewer decision;
* ``superseded_by`` keeps every earlier version downloadable while marking the
  row the institution replaced;
* ``related_deficiency_id`` ties the document to the deficiency item the
  reviewer opened, so "submit compliance" can require a replacement.

It also appends the ``documents_reuploaded`` guard to the two existing
``submit_compliance`` edges, because compliance cannot be submitted while a
rejected document still awaits its replacement.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0018_document_reuploads"
down_revision: str | None = "0017_rule_clause_citations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REJECTION_REASONS = (
    "UNREADABLE",
    "NO_DSC",
    "EXPIRED",
    "WRONG_DOCUMENT",
    "NAME_MISMATCH",
    "INCOMPLETE",
    "OTHER",
)

REUPLOAD_GUARD = "documents_reuploaded"


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "rejection_reason_code",
            sa.Enum(
                *REJECTION_REASONS,
                name="document_rejection_reason",
                native_enum=False,
                create_constraint=True,
                length=24,
            ),
            nullable=True,
        ),
    )
    op.add_column("documents", sa.Column("rejection_comment", sa.Text(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("rejected_by", sa.UUID(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("apH_clause", sa.String(length=64), nullable=True),
    )
    op.add_column("documents", sa.Column("superseded_by", sa.UUID(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("related_deficiency_id", sa.UUID(), nullable=True),
    )
    op.add_column("documents", sa.Column("signer_name", sa.String(length=255), nullable=True))

    op.create_foreign_key(
        op.f("fk_documents_rejected_by_users"),
        "documents",
        "users",
        ["rejected_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_documents_superseded_by_documents"),
        "documents",
        "documents",
        ["superseded_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_documents_related_deficiency_id_deficiencies"),
        "documents",
        "deficiencies",
        ["related_deficiency_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_documents_rejected_by"), "documents", ["rejected_by"], unique=False
    )
    op.create_index(
        op.f("ix_documents_superseded_by"), "documents", ["superseded_by"], unique=False
    )
    op.create_index(
        op.f("ix_documents_related_deficiency_id"),
        "documents",
        ["related_deficiency_id"],
        unique=False,
    )

    # The guard is data, so it is appended in SQL rather than seeded by code.
    # The ``NOT guard_expr @> ...`` predicate keeps the statement idempotent if
    # the seed already wrote the newer edge definition before this migration
    # ran.
    guard = f'["{REUPLOAD_GUARD}"]'
    op.execute(
        f"""
        UPDATE workflow_transitions
           SET guard_expr = guard_expr || '{guard}'::jsonb,
               updated_at = now()
         WHERE action = 'submit_compliance'
           AND NOT guard_expr @> '{guard}'::jsonb
        """
    )


def downgrade() -> None:
    guard = f'["{REUPLOAD_GUARD}"]'
    element = f'"{REUPLOAD_GUARD}"'
    op.execute(
        f"""
        UPDATE workflow_transitions
           SET guard_expr = (
                   SELECT coalesce(jsonb_agg(value), '[]'::jsonb)
                     FROM jsonb_array_elements(guard_expr) AS value
                    WHERE value <> '{element}'::jsonb
               ),
               updated_at = now()
         WHERE action = 'submit_compliance'
           AND guard_expr @> '{guard}'::jsonb
        """
    )

    op.drop_index(op.f("ix_documents_related_deficiency_id"), table_name="documents")
    op.drop_index(op.f("ix_documents_superseded_by"), table_name="documents")
    op.drop_index(op.f("ix_documents_rejected_by"), table_name="documents")
    op.drop_constraint(
        op.f("fk_documents_related_deficiency_id_deficiencies"),
        "documents",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_documents_superseded_by_documents"), "documents", type_="foreignkey"
    )
    op.drop_constraint(
        op.f("fk_documents_rejected_by_users"), "documents", type_="foreignkey"
    )
    op.drop_column("documents", "signer_name")
    op.drop_column("documents", "related_deficiency_id")
    op.drop_column("documents", "superseded_by")
    op.drop_column("documents", "apH_clause")
    op.drop_column("documents", "rejected_at")
    op.drop_column("documents", "rejected_by")
    op.drop_column("documents", "rejection_comment")
    op.drop_column("documents", "rejection_reason_code")
