"""Catalogue-backed alert-trigger lookup and validation.

The trigger vocabulary is data, not code: ``alert_trigger_catalogue`` maps a
statutory trigger code to an engine handler. Adding a new APH trigger therefore
needs a catalogue row and an alert rule, not a migration or an engine branch.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.alert import AlertRule, AlertTriggerCatalogue


class UnknownAlertTriggerError(ValueError):
    """Raised when a rule references a trigger absent from the catalogue."""


def list_triggers(db: Session) -> list[AlertTriggerCatalogue]:
    """Return the trigger catalogue in code order."""
    return list(
        db.scalars(
            select(AlertTriggerCatalogue).order_by(AlertTriggerCatalogue.code)
        ).all()
    )


def get_trigger(db: Session, code: str) -> AlertTriggerCatalogue | None:
    """Return one catalogue row, or ``None`` when the code is unknown."""
    return db.scalar(
        select(AlertTriggerCatalogue).where(AlertTriggerCatalogue.code == code)
    )


def validate_trigger(db: Session, code: str) -> AlertTriggerCatalogue:
    """Return the catalogue row for ``code`` or raise ``UnknownAlertTriggerError``."""
    trigger = get_trigger(db, code)
    if trigger is None:
        raise UnknownAlertTriggerError(
            f"Unknown alert trigger {code!r}; add it to alert_trigger_catalogue first."
        )
    return trigger


def rules_for_handler(db: Session, handler_key: str) -> list[AlertRule]:
    """Return active rules whose catalogue trigger maps to ``handler_key``."""
    return list(
        db.scalars(
            select(AlertRule)
            .join(
                AlertTriggerCatalogue,
                AlertTriggerCatalogue.code == AlertRule.trigger_type,
            )
            .where(
                AlertTriggerCatalogue.handler_key == handler_key,
                AlertRule.is_active.is_(True),
            )
            .order_by(AlertRule.days_before.desc(), AlertRule.code.asc())
        ).all()
    )


def first_rule_for_handler(db: Session, handler_key: str) -> AlertRule | None:
    """Return the first active rule for a handler, or ``None``."""
    rules = rules_for_handler(db, handler_key)
    return rules[0] if rules else None
