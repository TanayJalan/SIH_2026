"""make the lease, circulation and NDL rules real mandatory rules

Revision ID: 0020_rule_scope_fixes
Revises: 0019_faculty_rule_refinements
Create Date: 2026-10-28 04:30:00.000000

APH 6.17a requires a registered lease of at least 30 years and a live lease at
least as long as the longest course. Owned land satisfies the requirement
through its title. The first rule library exposed those two constraints as
advisory sub-rules of the combined tenure rule, and they reported "data missing"
for every institution that owns its land. They now read derived
``land.lease_tenure_ok`` / ``land.lease_live_ok`` metrics that are true for
owned land, so the rule is always assessed and a real failure blocks a Nil
Deficiency result.

The same release promotes the 25% access-and-circulation rule (Annexure-3 3.2)
and the National Digital Library membership rule (APH 6.54) from advisory to
mandatory, because both are part of the in-scope norm set.

The seed is insert-only, so existing databases keep the old rows. This
migration patches them in place.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0020_rule_scope_fixes"
down_revision: str | None = "0019_faculty_rule_refinements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEASE_TEMPLATE_30 = (
    "Owned land needs no lease; leased land needs a registered lease of at "
    "least 30 years ({clause}): {result}."
)
LEASE_TEMPLATE_LIVE = (
    "The live lease must run at least as long as the longest course "
    "({clause}): {result}."
)


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE compliance_rules
        SET metric_key = 'land.lease_tenure_ok',
            operator = 'EXISTS',
            threshold = 0,
            mandatory = true,
            unit = NULL,
            metric_params = '{{}}'::jsonb,
            penalty_codes = '["7.4f"]'::jsonb,
            explanation_template = $clause${LEASE_TEMPLATE_30}$clause$
        WHERE code = 'APH-LAND-LEASE-30'
        """
    )
    op.execute(
        f"""
        UPDATE compliance_rules
        SET metric_key = 'land.lease_live_ok',
            operator = 'EXISTS',
            threshold = 0,
            mandatory = true,
            unit = NULL,
            metric_params = '{{}}'::jsonb,
            penalty_codes = '["7.4f"]'::jsonb,
            explanation_template = $clause${LEASE_TEMPLATE_LIVE}$clause$
        WHERE code = 'APH-LAND-LEASE-LIVE'
        """
    )
    op.execute(
        """
        UPDATE compliance_rules
        SET mandatory = true
        WHERE code IN ('APH-AREA-CIRCULATION', 'APH-LIB-NDL')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE compliance_rules
        SET metric_key = 'land.lease_years_total',
            operator = '>=',
            threshold = 30,
            mandatory = false,
            unit = 'years',
            penalty_codes = '[]'::jsonb,
            explanation_template = NULL
        WHERE code = 'APH-LAND-LEASE-30'
        """
    )
    op.execute(
        """
        UPDATE compliance_rules
        SET metric_key = 'land.lease_years_live',
            operator = 'RATIO',
            threshold = 1,
            mandatory = false,
            unit = 'ratio',
            metric_params = '{"
                "numerator": "land.lease_years_live",
                "denominator": "land.longest_course_years",
                "compare": ">="
            }'::jsonb,
            penalty_codes = '[]'::jsonb,
            explanation_template = NULL
        WHERE code = 'APH-LAND-LEASE-LIVE'
        """
    )
    op.execute(
        """
        UPDATE compliance_rules
        SET mandatory = false
        WHERE code IN ('APH-AREA-CIRCULATION', 'APH-LIB-NDL')
        """
    )
