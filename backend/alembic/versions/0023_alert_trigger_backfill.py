"""backfill the complete alert-trigger catalogue

Revision ID: 0023_alert_trigger_backfill
Revises: 0022_statutory_timer_clocks
Create Date: 2026-10-29 12:00:00.000000

Some databases missed the two statutory warning triggers inserted by
``0013_workflow_definition`` (for example when that edit was applied after the
database had already been stamped). Alerts for the appeal window and the
Security Deposit then silently stopped because ``AlertRule -> catalogue`` could
not resolve their handler.

This data-only migration re-inserts the full catalogue idempotently. It never
deletes a row, so administrator edits and newer trigger codes survive. The same
list is kept in ``app.seed.ALERT_TRIGGERS`` so a fresh seed has identical data.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0023_alert_trigger_backfill"
down_revision: str | None = "0022_statutory_timer_clocks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ALERT_TRIGGERS = (
    (
        "DEADLINE_APPROACHING",
        "DEADLINE_APPROACHING",
        "An application deadline is approaching.",
        "APH 1.2",
        False,
    ),
    (
        "SLA_BREACHED",
        "SLA_BREACHED",
        "A configured processing deadline has passed.",
        "DEMO",
        True,
    ),
    (
        "DEFICIENCY_DUE",
        "DEFICIENCY_DUE",
        "A deficiency response is due.",
        "APH 2.4",
        False,
    ),
    (
        "DEFICIENCY_OVERDUE",
        "DEFICIENCY_OVERDUE",
        "A deficiency response is overdue.",
        "APH 2.25c",
        False,
    ),
    (
        "DOCUMENT_EXPIRING",
        "DOCUMENT_EXPIRING",
        "A document is approaching its expiry date.",
        "APH 6.17h",
        False,
    ),
    (
        "COMPLIANCE_RED",
        "COMPLIANCE_RED",
        "An institution has moved to RED compliance status.",
        "APH 7.13",
        False,
    ),
    (
        "APPLICATION_STATUS_CHANGED",
        "APPLICATION_STATUS_CHANGED",
        "An application moved to a new workflow status.",
        "APH 1.4.3",
        False,
    ),
    (
        "INSPECTION_SCHEDULED",
        "INSPECTION_SCHEDULED",
        "An Expert Visit Committee inspection was scheduled.",
        "APH 1.9a",
        False,
    ),
    (
        "APPEAL_WINDOW_CLOSING",
        "APPEAL_WINDOW_CLOSING",
        "The seven-day appeal window against a Speaking Order is closing.",
        "APH 1.11a",
        False,
    ),
    (
        "APPEAL_EXPIRED",
        "APPEAL_EXPIRED",
        "The seven-day appeal window closed with no appeal.",
        "APH 1.11a",
        False,
    ),
    (
        "DEPOSIT_DUE",
        "DEPOSIT_DUE",
        "The Security Deposit and Affidavit 3 are due after an LoA.",
        "APH 2.25f",
        False,
    ),
    (
        "DEPOSIT_OVERDUE",
        "DEPOSIT_OVERDUE",
        "The Security Deposit clock expired without payment.",
        "APH 2.25f",
        False,
    ),
    (
        "DEPOSIT_PENALTY",
        "DEPOSIT_PENALTY",
        "A Security Deposit ladder step was applied by the scheduler.",
        "APH 2.25f",
        False,
    ),
    (
        "LOA_EXPIRED",
        "LOA_EXPIRED",
        "The two-academic-year LoA validity period ended.",
        "APH 1.10b",
        False,
    ),
)


def upgrade() -> None:
    """Insert any missing catalogue row without touching existing rows."""
    statement = sa.text(
        """
        INSERT INTO alert_trigger_catalogue
            (code, handler_key, description, "apH_clause", needs_verification)
        VALUES (:code, :handler_key, :description, :clause, :needs_verification)
        ON CONFLICT (code) DO NOTHING
        """
    )
    bind = op.get_bind()
    for code, handler_key, description, clause, needs_verification in ALERT_TRIGGERS:
        bind.execute(
            statement,
            {
                "code": code,
                "handler_key": handler_key,
                "description": description,
                "clause": clause,
                "needs_verification": needs_verification,
            },
        )


def downgrade() -> None:
    """No-op: the rows are reference data used by existing alert rules."""
