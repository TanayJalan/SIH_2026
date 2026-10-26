"""Render ``docs/WORKFLOW.md`` from the generated APH seed data.

The workflow is data: ``workflow_definitions.json`` is what the application
loads into ``workflow_definitions`` / ``workflow_states`` /
``workflow_transitions``. This script renders the same rows as Mermaid diagrams
and a transition-to-clause table so the documentation cannot drift from the
seed data. Run it after ``scripts/seed_aph.py``:

    python scripts/render_workflow_docs.py

The output is illustrative: every seeded row is prototype data and the
authoritative citation for each edge is its ``apH_clause`` value.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SEEDS = ROOT / "backend" / "seeds" / "aph"
OUTPUT = ROOT / "docs" / "WORKFLOW.md"

TRACK_INTRO = {
    "TRACK_A": (
        "Track A is the Chapter I cycle for a new technical institution and for "
        "an Extension of Approval filed with a Self-Disclosure. Submitting locks "
        "the file; Scrutiny may raise deficiencies; the Expert Visit Committee "
        "(EVC) records a visit video and a report; the Regulation Bureau adds "
        "observations and lists the case before the Executive Committee (EC). "
        "An approval issues an LoA and starts the Security Deposit clock; a "
        "rejection or Letter of Deficiency issues a Speaking Order and opens the "
        "single seven-day appeal window."
    ),
    "TRACK_B": (
        "Track B covers the self-disclosure types. The Regulation Bureau runs an "
        "automatic Deficiency Report (APH 2.3.5a); a Nil Deficiency clears the "
        "case, deficiencies open a compliance window, and a configurable "
        "percentage of cases is sampled for a random EVC. The EC then issues an "
        "EoA with the Approved Intake or a Speaking Order."
    ),
    "TRACK_C": (
        "Track C reuses the Track A edges for an existing institution asking for "
        "a new programme, an intake increase, a change of site or a similar "
        "Chapter II change. Scrutiny follows Chapter II; the EVC runs only when "
        "the routing row requires it; a required Standing Hearing Committee (SHC) "
        "hearing is recorded before the case is listed before the EC."
    ),
    "TRACK_D": (
        "Track D is the year-round closure cycle. Scrutiny is the only review "
        "step before the EC. A closure that fails is recorded as an EoA with "
        "zero intake (APH 2.3.3h); a pending court case, charge sheet or "
        "investigation blocks the decision (APH 2.6e)."
    ),
}


def _load(name: str) -> Any:
    return json.loads((SEEDS / name).read_text(encoding="utf-8"))


def _node(code: str) -> str:
    """Return a Mermaid-safe node id for a state code."""
    return "S_" + "".join(character if character.isalnum() else "_" for character in code)


def _edge_label(transition: dict[str, Any]) -> str:
    label = f"{transition['action']}<br/>{transition['apH_clause']}"
    if transition["guard_expr"]:
        label += "<br/>if " + ", ".join(transition["guard_expr"])
    return label


def _mermaid(definition: dict[str, Any]) -> str:
    lines = ["```mermaid", "flowchart TD"]
    states = sorted(definition["states"], key=lambda state: state["sort_order"])
    for state in states:
        node = _node(state["code"])
        shape = f"{node}([{state['code']}])" if state["is_terminal"] else f"{node}[{state['code']}]"
        lines.append(f"    {shape}")
    lines.append("")
    for transition in definition["transitions"]:
        source = _node(transition["from_state"])
        target = _node(transition["to_state"])
        label = _edge_label(transition).replace('"', "'")
        lines.append(f'    {source} -->|"{label}"| {target}')
    lines.append("```")
    return "\n".join(lines)


def _table(definition: dict[str, Any]) -> str:
    lines = [
        "| From | Action | To | Roles | Guards | APH clause |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for transition in definition["transitions"]:
        roles = ", ".join(transition["allowed_roles"]) or "—"
        guards = ", ".join(transition["guard_expr"]) or "—"
        lines.append(
            "| {from_state} | {action} | {to_state} | {roles} | {guards} | {apH_clause} |".format(
                from_state=transition["from_state"],
                action=transition["action"],
                to_state=transition["to_state"],
                roles=roles,
                guards=guards,
                apH_clause=transition["apH_clause"],
            )
        )
    return "\n".join(lines)


def render() -> str:
    definitions = _load("workflow_definitions.json")
    routes = _load("application_type_routes.json")
    parts: list[str] = [
        "# APH workflow — data-driven state machine",
        "",
        "This document is rendered from `backend/seeds/aph/workflow_definitions.json` by",
        "`python scripts/render_workflow_docs.py`. The running API reads the same rows",
        "through `GET /workflow/definition?type=…` and `GET /workflow/diagram`; the case",
        "file must render its stages from that endpoint rather than from a hard-coded array",
        "(APH Annexure-7).",
        "",
        "Every state and every edge carries an APH clause. Rows marked",
        "`needs_verification = true` in the seed data are listed in",
        "`docs/OPEN_QUESTIONS.md`. All sample institutions are fictional and all",
        "thresholds, dates and fees are illustrative.",
        "",
        "## How the engine works",
        "",
        "1. `workflow_definitions` selects the track; `application_type_routes` decides",
        "   which track an application type follows.",
        "2. `workflow_transitions` is the only source of legal `(state, action, role)`",
        "   combinations. Edges are tried by `priority`; a guard that fails falls through to",
        "   the next edge, which is how the four `ec_decide` outcomes and the EVC / no-EVC",
        "   branches are expressed.",
        "3. Named guards live in `app/services/workflow_guards.py`; named side effects live",
        "   in `app/services/workflow_effects.py`. A guard or effect name that is not",
        "   registered fails loudly at runtime and in `tests/test_aph_configuration.py`.",
        "4. Every action writes exactly one `WorkflowEvent` (carrying the edge's APH clause)",
        "   and one `AuditLog` row in the same transaction.",
        "",
        "## Automatic clock steps",
        "",
        "`app/services/workflow_jobs.py` advances two steps without a human when the",
        "periodic alert scan runs:",
        "",
        "* `finalize_no_appeal` — an LoD/LoR decision becomes final when the seven-day",
        "  appeal window closes with no appeal (APH 1.11a).",
        "* `expire_loa` — an LoA lapses at the end of its two academic years and the",
        "  approval is cancelled (APH 1.10b).",
        "",
        "## Track parameters",
        "",
        "Track behaviour that APH leaves open is stored in `workflow_definitions.config`",
        "as editable JSON: `appeal_start_event`, `security_deposit`,",
        "`random_evc_percent` and `core_branches_required`. The appeal start event and the",
        "Security Deposit ladder also live in `deadline_rules`, so an administrator can",
        "change them without a deployment.",
        "",
    ]

    for definition in definitions:
        key = definition["key"]
        parts.extend(
            [
                f"## {key} — {definition['label']}",
                "",
                TRACK_INTRO.get(key, definition["description"]),
                "",
                f"Config: `{json.dumps(definition['config'], sort_keys=True)}`",
                "",
                "### Diagram",
                "",
                _mermaid(definition),
                "",
                "### States",
                "",
                "| State | Stage | Initial | Terminal | APH clause |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for state in sorted(definition["states"], key=lambda item: item["sort_order"]):
            parts.append(
                f"| {state['code']} | {state['stage']} | "
                f"{'yes' if state['is_initial'] else ''} | "
                f"{'yes' if state['is_terminal'] else ''} | {state['apH_clause']} |"
            )
        parts.extend(["", "### Transitions", "", _table(definition), ""])

    parts.extend(
        [
            "## Application types mapped to a track",
            "",
            "| Application type | Track | Scrutiny | EVC | SHC hearing | Self-disclosure |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for route in routes:
        if route.get("not_implemented"):
            continue
        parts.append(
            f"| {route['type']} | {route.get('workflow_key')} | "
            f"{'yes' if route.get('requires_scrutiny') else 'no'} | "
            f"{'yes' if route.get('requires_evc') else 'no'} | "
            f"{'yes' if route.get('requires_hearing_aa') else 'no'} | "
            f"{'yes' if route.get('requires_self_disclosure') else 'no'} |"
        )

    parts.extend(
        [
            "",
            "## Deliberately not implemented",
            "",
            "These APH Table 2.3 types are seeded with `not_implemented = true`. The API",
            "returns HTTP 503 with the stated note instead of inventing a workflow:",
            "",
            "| Application type | Note |",
            "| --- | --- |",
        ]
    )
    for route in routes:
        if route.get("not_implemented"):
            parts.append(
                f"| {route['type']} | {route.get('not_implemented_note') or '—'} |"
            )
    parts.append("")
    return "\n".join(parts)


def main() -> None:
    OUTPUT.write_text(render(), encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
