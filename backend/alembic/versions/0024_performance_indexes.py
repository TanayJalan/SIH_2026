"""performance indexes and document expiry backfill

Revision ID: 0024_performance_indexes
Revises: 0023_alert_trigger_backfill
Create Date: 2026-11-09 12:00:00.000000

Adds the composite indexes used by the dashboard and inbox queries on the
seed data (academic-year/status, alert recipient/channel/created_at, state,
document expiry and deficiency due dates) and backfills ``documents.expiry_date``
from ``valid_until`` so the document-expiry alert scan sees uploads created
before the two fields were kept in sync.

Indexes are created with ``IF NOT EXISTS`` so re-running the migration on a
database where an index already exists is safe. This is a prototype-scale
migration; on a very large production table use ``CREATE INDEX CONCURRENTLY``
outside a transaction.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0024_performance_indexes"
down_revision: str | None = "0023_alert_trigger_backfill"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEXES = (
    (
        "ix_applications_academic_year_status",
        "applications",
        ("academic_year", "status"),
        None,
    ),
    (
        "ix_applications_track_status",
        "applications",
        ("track", "status"),
        None,
    ),
    (
        "ix_institutions_state",
        "institutions",
        ("state",),
        None,
    ),
    (
        "ix_alerts_recipient_channel_created",
        "alerts",
        ("recipient_user_id", "channel", sa.text("created_at DESC")),
        None,
    ),
    (
        "ix_documents_expiry_date",
        "documents",
        ("expiry_date",),
        sa.text("expiry_date IS NOT NULL"),
    ),
    (
        "ix_deficiencies_status_due_date",
        "deficiencies",
        ("status", "due_date"),
        None,
    ),
)


def upgrade() -> None:
    for name, table, columns, where in _INDEXES:
        columns_sql = ", ".join(
            column if isinstance(column, str) else str(column) for column in columns
        )
        where_sql = f" WHERE {where}" if where is not None else ""
        op.execute(
            sa.text(f'CREATE INDEX IF NOT EXISTS "{name}" ON "{table}" ({columns_sql}){where_sql}')
        )

    op.execute(
        sa.text(
            "UPDATE documents SET expiry_date = valid_until "
            "WHERE expiry_date IS NULL AND valid_until IS NOT NULL"
        )
    )


def downgrade() -> None:
    for name, _, _, _ in reversed(_INDEXES):
        op.execute(sa.text(f'DROP INDEX IF EXISTS "{name}"'))
