"""workflow engine: statuses, overlays, events and deficiency responses

Revision ID: 0003_workflow_engine
Revises: 0002_application_workspace
Create Date: 2026-10-23 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_workflow_engine"
down_revision: str | None = "0002_application_workspace"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_STATUSES = (
    "DRAFT",
    "SUBMITTED",
    "DOCUMENT_VERIFICATION",
    "SCRUTINY",
    "DEFICIENCY_RAISED",
    "DEFICIENCY_RESPONDED",
    "INSPECTION_SCHEDULED",
    "INSPECTION_DONE",
    "COMMITTEE_REVIEW",
    "APPROVED",
    "CONDITIONALLY_APPROVED",
    "REJECTED",
)
_OLD_STATUSES = (
    "DRAFT",
    "SUBMITTED",
    "DOCUMENT_VERIFICATION",
    "SCRUTINY",
    "DEFICIENCY_RAISED",
    "INSPECTION_SCHEDULED",
    "INSPECTION_COMPLETED",
    "DECISION_PENDING",
    "APPROVED",
    "REJECTED",
    "WITHDRAWN",
)
_NEW_STAGES = (
    "APPLICATION",
    "DOCUMENT_VERIFICATION",
    "SCRUTINY",
    "DEFICIENCY",
    "INSPECTION",
    "COMMITTEE_REVIEW",
    "DECISION",
    "COMPLETED",
)
_OLD_STAGES = (
    "APPLICATION",
    "DOCUMENT_VERIFICATION",
    "SCRUTINY",
    "INSPECTION",
    "DECISION",
    "COMPLETED",
)


def _in_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.add_column(
        "applications",
        sa.Column("stage_entered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column(
            "is_withdrawn",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "applications",
        sa.Column(
            "is_escalated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "workflow_events",
        sa.Column("action", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "workflow_events",
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "deficiencies",
        sa.Column("response_document_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "deficiencies",
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "deficiencies",
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.drop_constraint("application_status", "applications", type_="check")
    op.drop_constraint("workflow_stage", "applications", type_="check")
    op.drop_constraint("workflow_stage", "sla_configs", type_="check")
    op.drop_constraint("application_status_from", "workflow_events", type_="check")
    op.drop_constraint("application_status_to", "workflow_events", type_="check")

    # Withdrawal and escalation become overlays instead of primary statuses.
    op.execute(
        "UPDATE applications SET is_withdrawn = true WHERE status = 'WITHDRAWN'"
    )
    op.execute(
        "UPDATE applications SET is_escalated = true WHERE status = 'ESCALATED'"
    )
    op.execute(
        "UPDATE applications SET status = 'SUBMITTED' "
        "WHERE status IN ('WITHDRAWN', 'ESCALATED')"
    )
    op.execute(
        "UPDATE applications SET status = 'INSPECTION_DONE' "
        "WHERE status = 'INSPECTION_COMPLETED'"
    )
    op.execute(
        "UPDATE applications SET status = 'COMMITTEE_REVIEW' "
        "WHERE status = 'DECISION_PENDING'"
    )
    op.execute(
        "UPDATE applications SET stage_entered_at = updated_at "
        "WHERE stage_entered_at IS NULL"
    )

    for column in ("from_status", "to_status"):
        op.execute(
            f"UPDATE workflow_events SET {column} = 'INSPECTION_DONE' "
            f"WHERE {column} = 'INSPECTION_COMPLETED'"
        )
        op.execute(
            f"UPDATE workflow_events SET {column} = 'COMMITTEE_REVIEW' "
            f"WHERE {column} = 'DECISION_PENDING'"
        )
        op.execute(
            f"UPDATE workflow_events SET {column} = 'SUBMITTED' "
            f"WHERE {column} IN ('WITHDRAWN', 'ESCALATED')"
        )

    op.execute(
        "INSERT INTO sla_configs "
        "(id, stage, duration_days, escalation_after_days, escalate_to_role, created_at, updated_at) "
        "VALUES (gen_random_uuid(), 'DEFICIENCY', 7, 5, 'REGIONAL_HEAD', now(), now()) "
        "ON CONFLICT (stage) DO NOTHING"
    )
    op.execute(
        "INSERT INTO sla_configs "
        "(id, stage, duration_days, escalation_after_days, escalate_to_role, created_at, updated_at) "
        "VALUES (gen_random_uuid(), 'COMMITTEE_REVIEW', 10, 7, 'SUPER_ADMIN', now(), now()) "
        "ON CONFLICT (stage) DO NOTHING"
    )

    op.create_check_constraint(
        "application_status",
        "applications",
        f"status IN ({_in_list(_NEW_STATUSES)})",
    )
    op.create_check_constraint(
        "workflow_stage",
        "applications",
        f"current_stage IN ({_in_list(_NEW_STAGES)})",
    )
    op.create_check_constraint(
        "workflow_stage",
        "sla_configs",
        f"stage IN ({_in_list(_NEW_STAGES)})",
    )
    op.create_check_constraint(
        "application_status_from",
        "workflow_events",
        f"from_status IS NULL OR from_status IN ({_in_list(_NEW_STATUSES)})",
    )
    op.create_check_constraint(
        "application_status_to",
        "workflow_events",
        f"to_status IN ({_in_list(_NEW_STATUSES)})",
    )

    op.create_foreign_key(
        None,
        "deficiencies",
        "documents",
        ["response_document_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_deficiencies_response_document_id"),
        "deficiencies",
        ["response_document_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_deficiencies_response_document_id"),
        table_name="deficiencies",
    )
    op.drop_constraint(
        "response_document_id_documents",
        "deficiencies",
        type_="foreignkey",
    )

    op.drop_constraint("application_status", "applications", type_="check")
    op.drop_constraint("workflow_stage", "applications", type_="check")
    op.drop_constraint("workflow_stage", "sla_configs", type_="check")
    op.drop_constraint("application_status_from", "workflow_events", type_="check")
    op.drop_constraint("application_status_to", "workflow_events", type_="check")

    op.execute(
        "UPDATE applications SET status = 'INSPECTION_COMPLETED' "
        "WHERE status = 'INSPECTION_DONE'"
    )
    op.execute(
        "UPDATE applications SET status = 'DECISION_PENDING' "
        "WHERE status = 'COMMITTEE_REVIEW'"
    )
    op.execute(
        "UPDATE applications SET status = 'DEFICIENCY_RAISED' "
        "WHERE status = 'DEFICIENCY_RESPONDED'"
    )
    op.execute(
        "UPDATE applications SET status = 'APPROVED' "
        "WHERE status = 'CONDITIONALLY_APPROVED'"
    )
    op.execute(
        "UPDATE applications SET status = 'WITHDRAWN' WHERE is_withdrawn = true"
    )
    for column in ("from_status", "to_status"):
        op.execute(
            f"UPDATE workflow_events SET {column} = 'INSPECTION_COMPLETED' "
            f"WHERE {column} = 'INSPECTION_DONE'"
        )
        op.execute(
            f"UPDATE workflow_events SET {column} = 'DECISION_PENDING' "
            f"WHERE {column} = 'COMMITTEE_REVIEW'"
        )
        op.execute(
            f"UPDATE workflow_events SET {column} = 'DEFICIENCY_RAISED' "
            f"WHERE {column} = 'DEFICIENCY_RESPONDED'"
        )
        op.execute(
            f"UPDATE workflow_events SET {column} = 'APPROVED' "
            f"WHERE {column} = 'CONDITIONALLY_APPROVED'"
        )

    op.execute(
        "DELETE FROM sla_configs WHERE stage IN ('DEFICIENCY', 'COMMITTEE_REVIEW')"
    )

    op.create_check_constraint(
        "application_status",
        "applications",
        f"status IN ({_in_list(_OLD_STATUSES)})",
    )
    op.create_check_constraint(
        "workflow_stage",
        "applications",
        f"current_stage IN ({_in_list(_OLD_STAGES)})",
    )
    op.create_check_constraint(
        "workflow_stage",
        "sla_configs",
        f"stage IN ({_in_list(_OLD_STAGES)})",
    )
    op.create_check_constraint(
        "application_status_from",
        "workflow_events",
        f"from_status IS NULL OR from_status IN ({_in_list(_OLD_STATUSES)})",
    )
    op.create_check_constraint(
        "application_status_to",
        "workflow_events",
        f"to_status IN ({_in_list(_OLD_STATUSES)})",
    )

    op.drop_column("deficiencies", "closed_at")
    op.drop_column("deficiencies", "responded_at")
    op.drop_column("deficiencies", "response_document_id")
    op.drop_column("workflow_events", "details")
    op.drop_column("workflow_events", "action")
    op.drop_column("applications", "is_escalated")
    op.drop_column("applications", "is_withdrawn")
    op.drop_column("applications", "stage_entered_at")
