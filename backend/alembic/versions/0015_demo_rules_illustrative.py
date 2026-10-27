"""make the legacy DEMO-* rules advisory

Revision ID: 0015_demo_rules_illustrative
Revises: 0014_compliance_rule_library
Create Date: 2026-10-27 11:40:00.000000

Before the APH rule library, the seeded ``DEMO-*`` thresholds were the only
compliance rules and were evaluated as if they were AICTE norms. They are now
project-only illustrative thresholds: advisory, flagged for verification and
never able to block a Nil Deficiency conclusion.

Fresh databases get these flags from ``seeds/aph/compliance_rules.json``. This
migration corrects rows created by earlier releases, where the seed was
insert-only and therefore never touched the existing records.

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015_demo_rules_illustrative"
down_revision: str | None = "0014_compliance_rule_library"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE compliance_rules
               SET illustrative = true,
                   mandatory = false,
                   needs_verification = true,
                   updated_at = now()
             WHERE code LIKE 'DEMO-%'
               AND illustrative = false
            """
        )
    )


def downgrade() -> None:
    # The previous flags cannot be reconstructed: an administrator may have
    # edited them after the upgrade, and restoring "mandatory" for an
    # illustrative demo threshold would silently reintroduce false
    # deficiencies. The downgrade therefore leaves the rows untouched.
    pass
