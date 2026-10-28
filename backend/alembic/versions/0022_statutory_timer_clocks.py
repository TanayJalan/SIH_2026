"""statutory timer clocks and their alert triggers

Revision ID: 0022_statutory_timer_clocks
Revises: 0021_rule_explanation_templates
Create Date: 2026-10-28 12:00:00.000000

Makes the APH section 5 clocks event-driven reference data:

  * ``SECURITY_DEPOSIT`` starts when the Executive Committee recommends the
    LoA (APH 2.25f), not when the letter is uploaded;
  * ``LOA_VALIDITY`` is a new clock started by the LoA letter (APH 1.10b);
  * the expiry and penalty steps get catalogue triggers so the scheduler can
    raise them through the same rule-driven alert engine;
  * the old seven-day deposit reminder is retired in favour of the day-10 and
    day-14 rows seeded by ``app.seed``.

The 730-day LoA duration is an approximation of "two academic years" and is
marked ``needs_verification`` (see docs/OPEN_QUESTIONS.md).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0022_statutory_timer_clocks"
down_revision: str | None = "0021_rule_explanation_templates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ALERT_TRIGGERS = (
    (
        "APPEAL_EXPIRED",
        "APPEAL_EXPIRED",
        "The seven-day appeal window closed with no appeal.",
        "APH 1.11a",
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

# (code, start_event, duration_days, owner_role, penalty_ladder, clause,
#  start_event_configurable, needs_verification)
DEADLINE_RULES = (
    (
        "LOA_VALIDITY",
        "LOA_ISSUED",
        730,
        "INSTITUTION_ADMIN",
        [],
        "APH 1.10b",
        False,
        True,
    ),
)


def _insert_alert_triggers() -> None:
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


def _insert_deadline_rules() -> None:
    statement = sa.text(
        """
        INSERT INTO deadline_rules
            (code, start_event, duration_days, owner_role, penalty_ladder,
             "apH_clause", start_event_configurable, needs_verification)
        VALUES
            (:code, :start_event, :duration_days, :owner_role,
             CAST(:penalty_ladder AS jsonb), :clause, :configurable,
             :needs_verification)
        ON CONFLICT (code) DO NOTHING
        """
    )
    bind = op.get_bind()
    for (
        code,
        start_event,
        duration_days,
        owner_role,
        _penalty_ladder,
        clause,
        configurable,
        needs_verification,
    ) in DEADLINE_RULES:
        bind.execute(
            statement,
            {
                "code": code,
                "start_event": start_event,
                "duration_days": duration_days,
                "owner_role": owner_role,
                "penalty_ladder": "[]",
                "clause": clause,
                "configurable": configurable,
                "needs_verification": needs_verification,
            },
        )


def upgrade() -> None:
    _insert_alert_triggers()
    _insert_deadline_rules()
    op.execute(
        """
        UPDATE deadline_rules
        SET start_event = 'EC_RECOMMENDS_LOA'
        WHERE code = 'SECURITY_DEPOSIT'
        """
    )
    op.execute(
        """
        UPDATE alert_rules
        SET is_active = false
        WHERE code = 'DEPOSIT-DUE-7'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE alert_rules
        SET is_active = true
        WHERE code = 'DEPOSIT-DUE-7'
        """
    )
    op.execute(
        """
        UPDATE deadline_rules
        SET start_event = 'DECISION_UPLOADED'
        WHERE code = 'SECURITY_DEPOSIT'
        """
    )
    op.execute("DELETE FROM deadline_rules WHERE code = 'LOA_VALIDITY'")
    catalogued = ", ".join(f"'{row[0]}'" for row in ALERT_TRIGGERS)
    op.execute(f"DELETE FROM alert_trigger_catalogue WHERE code IN ({catalogued})")
