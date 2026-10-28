"""family-scoped adjunct caps and final faculty rules

Revision ID: 0019_faculty_rule_refinements
Revises: 0018_document_reuploads
Create Date: 2026-10-28 04:00:00.000000

APH 6.14d caps adjunct/Professor-of-Practice posts at 15% of the required
faculty, but allows 20% for Design and 30% for Planning. The first rule
library used one flat 15% threshold, so a compliant Design or Planning
institution would have been marked deficient. The cap is now calculated per
programme group from the editable ``adjunct_caps`` configuration, and the rule
evaluates the number of posts above the allowance.

The same release adds the rules for the minimum Professor-of-Practice share
(APH 6.14d), regular-versus-contractual appointments (APH 6.14e) and a
Principal/Director vacancy longer than 12 months (APH 7.4b). The last two only
existed as metrics before.

The seed is insert-only so an existing database keeps the old adjunct rule and
never receives the new configuration key. This migration patches the existing
row and installs ``adjunct_caps`` when it is missing; ``python -m app.seed``
adds the new rule rows afterwards.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0019_faculty_rule_refinements"
down_revision: str | None = "0018_document_reuploads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONFIG_KEYS = (
    "'severity_weights', 'rag_breakpoints', 'committee_compositions', "
    "'fsr_ratios', 'cadre_ratios', 'adjunct_caps', 'area_norms', "
    "'bandwidth_tiers', 'library_norms', 'pc_ratios', 'penalty_actions'"
)

OLD_CONFIG_KEYS = (
    "'severity_weights', 'rag_breakpoints', 'committee_compositions', "
    "'fsr_ratios', 'cadre_ratios', 'area_norms', 'bandwidth_tiers', "
    "'library_norms', 'pc_ratios', 'penalty_actions'"
)

ADJUNCT_DESCRIPTION = (
    "Adjunct faculty and Professors of Practice together may not exceed the "
    "permitted share of required faculty: 15% generally, 20% for Design and "
    "30% for Planning (APH 6.14d)."
)
ADJUNCT_TEMPLATE = (
    "Adjunct and Professor-of-Practice posts above the permitted share: "
    "{observed} {unit}. {clause} allows 15% of required faculty, 20% for "
    "Design and 30% for Planning."
)
OLD_ADJUNCT_DESCRIPTION = (
    "Adjunct faculty and Professors of Practice together may not exceed 15% "
    "of required faculty (Design 20%, Planning 30%)."
)


def upgrade() -> None:
    op.drop_constraint(
        "compliance_config_key_allowed", "compliance_config", type_="check"
    )
    op.create_check_constraint(
        "compliance_config_key_allowed",
        "compliance_config",
        f"key IN ({CONFIG_KEYS})",
    )

    op.execute(
        """
        INSERT INTO compliance_config (id, key, value)
        SELECT gen_random_uuid(), 'adjunct_caps',
               '{"default_pct": 15, "min_professors_of_practice_pct": 10,
                 "by_family": {"DESIGN": 20, "PLANNING": 30}}'::jsonb
        WHERE NOT EXISTS (
            SELECT 1 FROM compliance_config WHERE key = 'adjunct_caps'
        )
        """
    )

    op.execute(
        sa.text(
            """
            UPDATE compliance_rules
            SET metric_key = 'faculty.adjunct_excess',
                operator = '<=',
                threshold = 0,
                unit = 'posts',
                description = :description,
                explanation_template = :template
            WHERE code = 'APH-FAC-ADJUNCT-CAP'
            """
        ).bindparams(description=ADJUNCT_DESCRIPTION, template=ADJUNCT_TEMPLATE)
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE compliance_rules
            SET metric_key = 'faculty.adjunct_pct',
                threshold = 15,
                unit = NULL,
                description = :description,
                explanation_template = NULL
            WHERE code = 'APH-FAC-ADJUNCT-CAP'
            """
        ).bindparams(description=OLD_ADJUNCT_DESCRIPTION)
    )
    op.execute(
        "DELETE FROM compliance_config WHERE key = 'adjunct_caps'"
    )
    op.drop_constraint(
        "compliance_config_key_allowed", "compliance_config", type_="check"
    )
    op.create_check_constraint(
        "compliance_config_key_allowed",
        "compliance_config",
        f"key IN ({OLD_CONFIG_KEYS})",
    )
