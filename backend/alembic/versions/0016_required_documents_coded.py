"""drop the pre-doc-code document checklist rows

Revision ID: 0016_required_documents_coded
Revises: 0015_demo_rules_illustrative
Create Date: 2026-10-27 12:05:00.000000

Early releases seeded ``required_documents`` before the ``doc_code`` column
existed, so installations created then hold rows with a NULL code next to the
coded Annexure-2 catalogue. The compliance engine keys uploads on the APH
document code, so those rows can never be matched and were reported as missing
documents on otherwise complete applications.

The coded catalogue is now the single source of truth and is restored by
``python -m app.seed`` after the migration. The legacy rows are reference data,
never application uploads.

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0016_required_documents_coded"
down_revision: str | None = "0015_demo_rules_illustrative"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("DELETE FROM required_documents WHERE doc_code IS NULL"))


def downgrade() -> None:
    # The deleted rows carried no document code and were superseded by the
    # coded catalogue; they cannot be recreated faithfully. Re-run the seed to
    # load the current checklist.
    pass
