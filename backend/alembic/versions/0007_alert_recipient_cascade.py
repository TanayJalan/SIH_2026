"""alerts: cascade recipient deletion

Revision ID: 0007_alert_recipient_cascade
Revises: 0006_alert_engine
Create Date: 2026-10-23 17:20:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007_alert_recipient_cascade"
down_revision: str | None = "0006_alert_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "fk_alerts_recipient_user_id_users",
        "alerts",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_alerts_recipient_user_id_users",
        "alerts",
        "users",
        ["recipient_user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_alerts_recipient_user_id_users",
        "alerts",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_alerts_recipient_user_id_users",
        "alerts",
        "users",
        ["recipient_user_id"],
        ["id"],
    )
