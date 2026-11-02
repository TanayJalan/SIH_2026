"""complaint, penal-action and Security Deposit release lifecycle

Revision ID: 0024_complaint_penal_lifecycle
Revises: 0023_alert_trigger_backfill
Create Date: 2026-11-01 12:00:00.000000

APH 7.10 runs a complaint through PGRC -> SCSC -> show-cause or EVC -> SHC ->
EC with a Speaking Order. APH 7.3/7.4 records the penal action, APH 7.1b makes a
withdrawn institution reapply only after two academic years under a different
name, and APH 7.11 lets it request restoration. APH 6.46 releases the Security
Deposit only after clearances from PGRC, Vigilance and the grants cell.

This migration adds the columns the demo needs to make those steps visible. It
does not change any existing value, so the workflow engine and the seeded cases
keep working unchanged.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0024_complaint_penal_lifecycle"
down_revision: str | None = "0023_alert_trigger_backfill"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Complaints (APH 7.10) -------------------------------------------------
    op.add_column(
        "complaints",
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_complaints_application_id",
        "complaints",
        "applications",
        ["application_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_complaints_application_id", "complaints", ["application_id"], unique=False)
    op.add_column("complaints", sa.Column("complainant_name", sa.String(255), nullable=True))
    op.add_column("complaints", sa.Column("complainant_contact", sa.String(255), nullable=True))
    op.add_column(
        "complaints",
        sa.Column(
            "complainant_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column("complaints", sa.Column("rejection_reason", sa.Text(), nullable=True))
    op.add_column("complaints", sa.Column("rejection_clause", sa.String(64), nullable=True))
    op.add_column("complaints", sa.Column("scsc_decision", sa.String(32), nullable=True))
    op.add_column("complaints", sa.Column("scsc_decided_on", sa.Date(), nullable=True))
    op.add_column("complaints", sa.Column("scsc_notes", sa.Text(), nullable=True))
    op.add_column("complaints", sa.Column("show_cause_issued_on", sa.Date(), nullable=True))
    op.add_column("complaints", sa.Column("show_cause_reply", sa.Text(), nullable=True))
    op.add_column("complaints", sa.Column("show_cause_replied_on", sa.Date(), nullable=True))
    op.add_column("complaints", sa.Column("shc_hearing_on", sa.Date(), nullable=True))
    op.add_column("complaints", sa.Column("shc_findings", sa.Text(), nullable=True))
    op.add_column("complaints", sa.Column("ec_decision", sa.String(32), nullable=True))
    op.add_column("complaints", sa.Column("speaking_order", sa.Text(), nullable=True))
    op.add_column("complaints", sa.Column("decided_on", sa.Date(), nullable=True))

    # Penal actions (APH 7.3 / 7.4 / 7.1b / 7.11) ---------------------------
    op.add_column("penal_actions", sa.Column("order_number", sa.String(64), nullable=True))
    op.add_column("penal_actions", sa.Column("issued_on", sa.Date(), nullable=True))
    op.add_column("penal_actions", sa.Column("hearing_on", sa.Date(), nullable=True))
    op.add_column("penal_actions", sa.Column("hearing_notes", sa.Text(), nullable=True))
    op.add_column(
        "penal_actions",
        sa.Column("hearing_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_penal_actions_hearing_by_user_id",
        "penal_actions",
        "users",
        ["hearing_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("penal_actions", sa.Column("fine_paise", sa.BigInteger(), nullable=True))
    op.add_column("penal_actions", sa.Column("fine_basis", sa.Text(), nullable=True))
    op.add_column(
        "penal_actions",
        sa.Column("consequences", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("penal_actions", sa.Column("restoration_requested_on", sa.Date(), nullable=True))
    op.add_column("penal_actions", sa.Column("restoration_eligible_from", sa.Date(), nullable=True))
    op.add_column("penal_actions", sa.Column("restoration_status", sa.String(32), nullable=True))

    # Security Deposit release (APH 6.46) ----------------------------------
    op.add_column("security_deposits", sa.Column("release_requested_on", sa.Date(), nullable=True))
    op.add_column(
        "security_deposits",
        sa.Column(
            "release_clearances",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column("security_deposits", sa.Column("released_on", sa.Date(), nullable=True))
    op.add_column("security_deposits", sa.Column("noc_number", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("security_deposits", "noc_number")
    op.drop_column("security_deposits", "released_on")
    op.drop_column("security_deposits", "release_clearances")
    op.drop_column("security_deposits", "release_requested_on")

    op.drop_column("penal_actions", "restoration_status")
    op.drop_column("penal_actions", "restoration_eligible_from")
    op.drop_column("penal_actions", "restoration_requested_on")
    op.drop_column("penal_actions", "consequences")
    op.drop_column("penal_actions", "fine_basis")
    op.drop_column("penal_actions", "fine_paise")
    op.drop_constraint("fk_penal_actions_hearing_by_user_id", "penal_actions", type_="foreignkey")
    op.drop_column("penal_actions", "hearing_by_user_id")
    op.drop_column("penal_actions", "hearing_notes")
    op.drop_column("penal_actions", "hearing_on")
    op.drop_column("penal_actions", "issued_on")
    op.drop_column("penal_actions", "order_number")

    op.drop_column("complaints", "decided_on")
    op.drop_column("complaints", "speaking_order")
    op.drop_column("complaints", "ec_decision")
    op.drop_column("complaints", "shc_findings")
    op.drop_column("complaints", "shc_hearing_on")
    op.drop_column("complaints", "show_cause_replied_on")
    op.drop_column("complaints", "show_cause_reply")
    op.drop_column("complaints", "show_cause_issued_on")
    op.drop_column("complaints", "scsc_notes")
    op.drop_column("complaints", "scsc_decided_on")
    op.drop_column("complaints", "scsc_decision")
    op.drop_column("complaints", "rejection_clause")
    op.drop_column("complaints", "rejection_reason")
    op.drop_column("complaints", "complainant_verified")
    op.drop_column("complaints", "complainant_contact")
    op.drop_column("complaints", "complainant_name")
    op.drop_index("ix_complaints_application_id", table_name="complaints")
    op.drop_constraint("fk_complaints_application_id", "complaints", type_="foreignkey")
    op.drop_column("complaints", "application_id")
