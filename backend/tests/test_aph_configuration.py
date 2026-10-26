"""APH configuration invariants that must hold for every build.

These tests enforce the domain policy from ``AGENTS.md``:

* every compliance rule, workflow transition, fee row and alert rule carries an
  APH clause, or is explicitly marked ``needs_verification``;
* the application-type enum and the seeded routing table agree, so a code
  change cannot silently add or drop an APH application type.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import (
    AlertRule,
    AlertTriggerCatalogue,
    ApplicationType,
    ApplicationTypeRoute,
    ComplianceRule,
    DeadlineRule,
    FeeSchedule,
    RequiredDocument,
    SecurityDepositSchedule,
    SLAConfig,
)
from app.services.workflow import TRANSITIONS


def _missing_clause(rows: list[object]) -> list[str]:
    """Return a readable label for rows without a clause or verification flag."""
    missing: list[str] = []
    for row in rows:
        clause = (getattr(row, "apH_clause", "") or "").strip()
        needs_verification = bool(getattr(row, "needs_verification", False))
        if not clause and not needs_verification:
            label = (
                getattr(row, "code", None)
                or getattr(row, "item_code", None)
                or getattr(row, "action", None)
                or getattr(row, "type", None)
                or getattr(row, "doc_code", None)
                or getattr(row, "programme_family", None)
                or getattr(row, "id", None)
            )
            missing.append(str(label))
    return missing


@pytest.mark.parametrize(
    ("model", "label"),
    [
        (ComplianceRule, "ComplianceRule"),
        (FeeSchedule, "FeeSchedule"),
        (SecurityDepositSchedule, "SecurityDepositSchedule"),
        (AlertRule, "AlertRule"),
        (AlertTriggerCatalogue, "AlertTriggerCatalogue"),
        (DeadlineRule, "DeadlineRule"),
        (RequiredDocument, "RequiredDocument"),
        (ApplicationTypeRoute, "ApplicationTypeRoute"),
        (SLAConfig, "SLAConfig"),
    ],
)
def test_configuration_rows_carry_an_aph_clause(model, label: str) -> None:
    """Configuration rows must cite APH or be explicitly flagged for review."""
    with SessionLocal() as db:
        rows = list(db.scalars(select(model)).all())
    missing = _missing_clause(rows)
    assert not missing, f"{label} rows without an apH_clause: {missing}"


def test_workflow_transitions_carry_an_aph_clause() -> None:
    """Every state-machine transition cites its APH clause or is flagged."""
    missing = _missing_clause(list(TRANSITIONS))
    assert not missing, f"Workflow transitions without an apH_clause: {missing}"


def test_application_type_enum_matches_routing_table() -> None:
    """The enum and the authoritative Table 2.3 routing table must agree."""
    enum_values = {member.value for member in ApplicationType}
    with SessionLocal() as db:
        route_values = set(db.scalars(select(ApplicationTypeRoute.type)).all())
    assert route_values == enum_values
