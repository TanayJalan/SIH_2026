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
    WorkflowDefinition,
    WorkflowState,
    WorkflowTransition,
)
from app.models.enums import WorkflowAction
from app.services.workflow_effects import EFFECTS
from app.services.workflow_guards import GUARDS


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
        (WorkflowDefinition, "WorkflowDefinition"),
        (WorkflowState, "WorkflowState"),
        (WorkflowTransition, "WorkflowTransition"),
    ],
)
def test_configuration_rows_carry_an_aph_clause(model, label: str) -> None:
    """Configuration rows must cite APH or be explicitly flagged for review."""
    with SessionLocal() as db:
        rows = list(db.scalars(select(model)).all())
    missing = _missing_clause(rows)
    assert not missing, f"{label} rows without an apH_clause: {missing}"


def test_application_type_enum_matches_routing_table() -> None:
    """The enum and the authoritative Table 2.3 routing table must agree."""
    enum_values = {member.value for member in ApplicationType}
    with SessionLocal() as db:
        route_values = set(db.scalars(select(ApplicationTypeRoute.type)).all())
    assert route_values == enum_values


def test_every_workflow_edge_references_a_seeded_state_and_registered_handler() -> None:
    """Workflow data may only name states, roles, guards and effects that exist.

    This is the guard against a typo in seed data silently disabling a step: an
    unknown guard or effect would fail at request time, so it fails the build
    instead.
    """
    known_actions = {action.value for action in WorkflowAction}
    with SessionLocal() as db:
        definitions = list(db.scalars(select(WorkflowDefinition)).all())
        assert definitions, "No workflow definitions are seeded"
        for definition in definitions:
            states = set(
                db.scalars(
                    select(WorkflowState.code).where(
                        WorkflowState.definition_id == definition.id
                    )
                ).all()
            )
            edges = list(
                db.scalars(
                    select(WorkflowTransition).where(
                        WorkflowTransition.definition_id == definition.id
                    )
                ).all()
            )
            assert edges, f"{definition.key} has no transitions"
            for edge in edges:
                assert edge.from_state in states, (definition.key, edge.from_state)
                assert edge.to_state in states, (definition.key, edge.to_state)
                assert edge.action in known_actions, (definition.key, edge.action)
                unknown_guards = set(edge.guard_expr or []) - set(GUARDS)
                unknown_effects = set(edge.side_effects or []) - set(EFFECTS)
                assert not unknown_guards, (definition.key, edge.action, unknown_guards)
                assert not unknown_effects, (definition.key, edge.action, unknown_effects)


def test_workflow_definition_covers_every_application_type_route() -> None:
    """Every routed APH type must point at a real workflow or be marked unimplemented."""
    with SessionLocal() as db:
        keys = set(db.scalars(select(WorkflowDefinition.key)).all())
        routes = list(db.scalars(select(ApplicationTypeRoute)).all())
    assert routes, "No application type routes are seeded"
    for route in routes:
        if route.not_implemented:
            assert route.not_implemented_note, route.type
            continue
        assert route.workflow_key in keys, (route.type, route.workflow_key)
