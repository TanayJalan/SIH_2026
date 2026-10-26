"""Read-only workflow definition and diagram endpoints.

The case file and the documentation must never hard-code the list of stages:
both read it from ``workflow_states`` / ``workflow_transitions`` through these
endpoints. ``GET /workflow/diagram`` renders the same rows as Mermaid so
``docs/WORKFLOW.md`` can be checked against the running configuration
(APH Annexure-7).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.dependencies import CurrentUser, DbSession
from app.models.application_type_route import ApplicationTypeRoute
from app.models.workflow_definition import WorkflowDefinition
from app.schemas.common import ErrorResponse
from app.schemas.workflow import (
    WorkflowDefinitionRead,
    WorkflowDiagramRead,
    WorkflowStateRead,
    WorkflowTransitionRead,
)

router = APIRouter(prefix="/workflow", tags=["workflow-definition"])


def _load_definitions(db: DbSession) -> list[WorkflowDefinition]:
    return list(
        db.scalars(
            select(WorkflowDefinition)
            .options(
                selectinload(WorkflowDefinition.states),
                selectinload(WorkflowDefinition.transitions),
            )
            .where(WorkflowDefinition.is_active.is_(True))
            .order_by(WorkflowDefinition.key.asc())
        ).all()
    )


def _resolve_definition(db: DbSession, key: str) -> WorkflowDefinition:
    """Resolve a workflow key or an application type to its definition."""
    route_key: str | None = None
    route = db.scalar(
        select(ApplicationTypeRoute).where(ApplicationTypeRoute.type == key)
    )
    if route is not None:
        route_key = route.workflow_key
    wanted = route_key or key

    definition = db.scalar(
        select(WorkflowDefinition)
        .options(
            selectinload(WorkflowDefinition.states),
            selectinload(WorkflowDefinition.transitions),
        )
        .where(
            WorkflowDefinition.key == wanted,
            WorkflowDefinition.is_active.is_(True),
        )
    )
    if definition is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"No workflow is configured for {key!r}",
        )
    return definition


def _read(definition: WorkflowDefinition) -> WorkflowDefinitionRead:
    states = sorted(definition.states, key=lambda state: state.sort_order)
    transitions = sorted(
        definition.transitions,
        key=lambda edge: (edge.from_state.value, edge.priority, edge.action),
    )
    return WorkflowDefinitionRead(
        key=definition.key,
        label=definition.label,
        track=definition.track,
        description=definition.description,
        config=definition.config or {},
        apH_clause=definition.apH_clause,
        needs_verification=definition.needs_verification,
        states=[WorkflowStateRead.model_validate(state) for state in states],
        transitions=[
            WorkflowTransitionRead.model_validate(edge) for edge in transitions
        ],
    )


@router.get(
    "/definition",
    response_model=WorkflowDefinitionRead,
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
    summary="Read the workflow definition for an application type or track",
)
def get_definition(
    current_user: CurrentUser,
    db: DbSession,
    type_: str = Query(
        ...,
        alias="type",
        description="Application type code (for example EOA_SELF_DISCLOSURE) or track key.",
    ),
) -> WorkflowDefinitionRead:
    """Return every state and edge the case file must render."""
    return _read(_resolve_definition(db, type_))


@router.get(
    "/diagram",
    response_model=WorkflowDiagramRead,
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
    summary="Render the workflow as a Mermaid diagram",
)
def get_diagram(
    current_user: CurrentUser,
    db: DbSession,
    type_: str | None = Query(
        default=None,
        alias="type",
        description="Limit the diagram to one application type or track key.",
    ),
) -> WorkflowDiagramRead:
    """Render one or all active definitions as a Mermaid flowchart."""
    if type_ is not None:
        definitions = [_resolve_definition(db, type_)]
    else:
        definitions = _load_definitions()
    if not definitions:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No workflow is configured")

    lines = ["flowchart TD"]
    for definition in definitions:
        lines.extend(_mermaid_lines(definition))
    return WorkflowDiagramRead(
        definitions=[definition.key for definition in definitions],
        mermaid="\n".join(lines),
    )


def _mermaid_lines(definition: WorkflowDefinition) -> list[str]:
    """Render one definition as Mermaid nodes and labelled edges."""
    prefix = f"{definition.key.lower()}_"

    states = sorted(definition.states, key=lambda state: state.sort_order)
    lines = [f"    subgraph {prefix.rstrip('_')}[\"{_quote(definition.label)}\"]"]
    for state in states:
        label = f"{state.code.value} - {state.label}"
        if state.is_terminal:
            lines.append(f'        {prefix}{state.code.value}(["{_quote(label)}"])')
        elif state.is_initial:
            lines.append(f'        {prefix}{state.code.value}(["{_quote(label)}"])')
        else:
            lines.append(f'        {prefix}{state.code.value}["{_quote(label)}"]')
    for edge in sorted(
        definition.transitions,
        key=lambda item: (item.from_state.value, item.priority, item.action),
    ):
        line = (
            f"        {prefix}{edge.from_state.value} -->"
            f"|{edge.action} {edge.apH_clause}| {prefix}{edge.to_state.value}"
        )
        lines.append(line)
    lines.append("    end")
    return lines


def _quote(text: str) -> str:
    """Escape a Mermaid label."""
    return text.replace('"', "'")
