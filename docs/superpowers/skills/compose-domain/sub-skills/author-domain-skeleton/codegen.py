"""Orchestrator codegen for author-domain-skeleton (TASK-020).

Pure function :func:`render_orchestrator` that turns a v4 brief into a
Durable orchestrator Python module string. Supports four phase kinds:

* ``deterministic``: ``yield context.call_activity("<phase>_activity", ...)``
* ``agent``: ``yield context.call_activity("<phase>_agent_activity", ...)``
* ``hitl``: ``yield context.wait_for_external_event("<external_event>")``
* ``sub_orchestrator``: ``yield context.call_sub_orchestrator(
  "<TargetOrchestratorName>", <payload_expr>)`` — instrumented with a
  ``workflow.sub_spawned`` audit checkpoint (SEC-002) before each call.

Sub-orchestrator phases sharing a ``parallel_group`` label collapse
into one ``yield context.task_all([...])`` block — the audit
checkpoint is emitted once per child inside the group.

The class-name convention for ``target_orchestrator`` (when not
explicitly overridden) is::

    <PrefixCapWord><TargetWorkflowTypeCapWord>Orchestrator

…with the brief's own ``domain.prefix`` used as a fallback. The brief
should override via ``target_orchestrator`` whenever the convention
doesn't fit (e.g. ``CreativeCampaignOrchestrator`` has no prefix).
"""
from __future__ import annotations

from pathlib import Path

__all__ = [
    "render_orchestrator",
    "render_filename",
    "derive_orchestrator_classname",
]


_TEMPLATE_PATH = (
    Path(__file__).resolve().parents[2] / "templates" / "orchestrator.py.tmpl"
)


def _pascal(s: str) -> str:
    return "".join(part.capitalize() for part in s.replace("_", "-").split("-") if part)


def _snake(s: str) -> str:
    return s.replace("-", "_")


def derive_orchestrator_classname(workflow_type: str, prefix: str | None = None) -> str:
    """Derive the PascalCase orchestrator class name for a workflow_type.

    Convention: ``<PrefixCap><WtCap>Orchestrator``. When ``prefix`` is
    falsy or already a substring of the workflow_type, it's omitted.
    """
    wt_pascal = _pascal(workflow_type)
    if not prefix or prefix.lower() in workflow_type.lower():
        return f"{wt_pascal}Orchestrator"
    return f"{_pascal(prefix)}{wt_pascal}Orchestrator"


def render_filename(brief: dict) -> str:
    """Return ``<workflow_type-snake>.py`` — matches the api/functions/workflows convention."""
    wt = brief["domain"]["workflow_type"]
    return f"{_snake(wt)}.py"


def _payload_expr(payload_from: str) -> str:
    """Translate a brief's ``payload_from`` into a Python expression string.

    * ``python:<expr>`` - the literal Python after the prefix.
    * Anything else is treated as a Cypher snippet that the substrate
      will resolve at runtime via the entity-graph fetch helper. The
      codegen embeds it as ``{"_cypher": "<snippet>", "input": input_dict}``.
    """
    if payload_from.startswith("python:"):
        return payload_from[len("python:"):].strip()
    safe = payload_from.replace('"', '\\"').replace("\n", " ")
    return f'{{"_cypher": "{safe}", "input": input_dict}}'


def _render_sub_call(phase: dict, brief_prefix: str | None) -> str:
    target = phase.get("target_orchestrator") or derive_orchestrator_classname(
        phase["target_workflow_type"], brief_prefix,
    )
    expr = _payload_expr(phase["payload_from"])
    return f'context.call_sub_orchestrator("{target}", {expr})'


def _render_audit_emit(phase: dict, parent_var: str = "workflow_id") -> str:
    """Emit a workflow.sub_spawned checkpoint for one sub-call (SEC-002).

    Audit fires *before* the call so the parent->child link lands even
    if the child fails its first activity.
    """
    target_wt = phase["target_workflow_type"]
    return (
        '    yield context.call_activity("checkpoint_activity_trigger", {\n'
        f'        "workflow_id": {parent_var}, "instance_id": context.instance_id,\n'
        '        "kind": "workflow.sub_spawned",\n'
        f'        "payload": {{"parent_workflow_id": {parent_var}, '
        f'"child_workflow_type": "{target_wt}"}},\n'
        '    })\n'
    )


def _render_phase_block(phase: dict, brief_prefix: str | None) -> str:
    """Render one phase to its `yield` block. parallel_groups handled upstream."""
    name = phase["name"]
    kind = phase["kind"]
    if kind == "deterministic":
        return (
            f'    {name}_result = yield context.call_activity('
            f'"{name}_activity", {{**enriched, "phase": "{name}"}})\n'
        )
    if kind == "agent":
        return (
            f'    {name}_result = yield context.call_activity('
            f'"{name}_agent_activity", {{**enriched, "phase": "{name}"}})\n'
        )
    if kind == "hitl":
        ev = phase.get("external_event") or f"{name}_decision"
        return (
            f'    {name}_result = yield context.wait_for_external_event("{ev}")\n'
        )
    if kind == "sub_orchestrator":
        audit = _render_audit_emit(phase)
        call = _render_sub_call(phase, brief_prefix)
        return f"{audit}    {name}_result = yield {call}\n"
    raise ValueError(f"unknown phase.kind: {kind!r}")


def _render_parallel_block(group: str, phases: list[dict], brief_prefix: str | None) -> str:
    """Render a `task_all` block over multiple sub_orchestrator phases."""
    audits = "".join(_render_audit_emit(p) for p in phases)
    calls = ",\n        ".join(_render_sub_call(p, brief_prefix) for p in phases)
    return (
        f"    # parallel_group: {group}\n"
        f"{audits}"
        f"    {group}_results = yield context.task_all([\n"
        f"        {calls},\n"
        f"    ])\n"
    )


def _group_phases(phases: list[dict]) -> list[tuple[str | None, list[dict]]]:
    """Walk phases, collapsing same-`parallel_group` sub_orchestrator runs.

    Returns a list of ``(group_or_None, [phases])``. Singletons keep
    their original position; grouped runs (>=2 entries with the same
    ``parallel_group`` and ``kind: sub_orchestrator``) are emitted at
    the position of the first member.
    """
    out: list[tuple[str | None, list[dict]]] = []
    seen_groups: set[str] = set()
    for p in phases:
        grp = p.get("parallel_group") if p.get("kind") == "sub_orchestrator" else None
        if grp:
            if grp in seen_groups:
                continue
            seen_groups.add(grp)
            members = [
                q for q in phases
                if q.get("kind") == "sub_orchestrator" and q.get("parallel_group") == grp
            ]
            if len(members) > 1:
                out.append((grp, members))
                continue
            # Single member with a label — render as a singleton.
            out.append((None, [p]))
        else:
            out.append((None, [p]))
    return out


def render_orchestrator(brief: dict) -> str:
    """Render the orchestrator Python module body for ``brief``.

    Output is a self-contained string defining
    ``<workflow_type_snake>_orchestration(context)``. The caller is
    responsible for `ast.parse(body)` validation and for landing the
    file under ``api/functions/workflows/``.
    """
    domain = brief["domain"]
    workflow_type = domain["workflow_type"]
    prefix = domain.get("prefix", "")
    display_name = domain.get("display_name", workflow_type)
    snake = _snake(workflow_type)
    phases = brief.get("phases") or []

    blocks: list[str] = []
    for grp, members in _group_phases(phases):
        if grp is not None and len(members) > 1:
            blocks.append(_render_parallel_block(grp, members, prefix))
        else:
            blocks.append(_render_phase_block(members[0], prefix))

    phase_blocks = "\n".join(blocks)
    phase_list = " -> ".join(p["name"] for p in phases) or "(no phases)"

    return f'''"""Auto-generated orchestrator for {display_name} ({workflow_type}).

Rendered by compose-domain v4 author-domain-skeleton codegen
(TASK-020). Phases:
  {phase_list}

This module is rendered as a string for validation by
``ast.parse``; graduate.sh writes it to
``api/functions/workflows/{snake}.py``.
"""
from __future__ import annotations
from collections.abc import Generator
from typing import Any

import azure.durable_functions as df


def {snake}_orchestration(context: df.DurableOrchestrationContext) -> Generator[Any, Any, dict]:
    """Orchestrate the {display_name} workflow."""
    input_dict = context.get_input() or {{}}
    workflow_id = input_dict.get("workflow_id", "?")
    workflow_type = input_dict.get("type", "{workflow_type}")
    enriched = {{
        **input_dict,
        "workflow_id": workflow_id,
        "instance_id": context.instance_id,
    }}

    yield context.call_activity("checkpoint_activity_trigger", {{
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.started",
        "payload": {{"workflow_type": workflow_type}},
    }})

{phase_blocks}
    yield context.call_activity("checkpoint_activity_trigger", {{
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.completed",
        "payload": {{"workflow_type": workflow_type}},
    }})

    return {{"status": "completed", "workflow_type": workflow_type}}
'''


# ---------------------------------------------------------------- TASK-021
# Per-HITL-phase precedent_query .cypher renderer. Mirrors the
# `decision-mapping` codegen template but driven straight off `phases`
# (so meta-workflow briefs without a `decisions:` block still get one
# precedent file per HITL gate).

_PRECEDENT_TEMPLATE = """\
// Auto-generated by compose-domain v4 author-domain-skeleton codegen.
// Workflow: {workflow_type}
// Phase:    {phase}
// Persona:  {persona}
//
// Bind params:
//   $entity_id  - entity id the current workflow's persona is reasoning about
//   $limit      - max precedents to return (caller chooses)
MATCH (d:Decision)-[:DECIDED_ON]->(e {{id: $entity_id}})
WHERE d.persona_role = '{persona}'
  AND d.workflow_type = '{workflow_type}'
RETURN d
ORDER BY d.decided_at DESC
LIMIT $limit
"""


def render_precedent_filename(brief: dict, phase: dict) -> str:
    return f"{brief['domain']['workflow_type']}_{phase['name']}.cypher"


def render_precedent_cypher(brief: dict, phase: dict) -> str:
    return _PRECEDENT_TEMPLATE.format(
        workflow_type=brief["domain"]["workflow_type"],
        phase=phase["name"],
        persona=phase.get("persona", "unknown"),
    )


def emit_precedent_files(brief: dict, target_dir: Path) -> list[Path]:
    """Render one .cypher per HITL phase, skipping files that already exist.

    Returns the list of paths created. Existing files are left intact —
    domain authors may override the auto-generated query in place.
    """
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    for phase in brief.get("phases") or []:
        if phase.get("kind") != "hitl":
            continue
        path = target_dir / render_precedent_filename(brief, phase)
        if path.exists():
            continue
        path.write_text(render_precedent_cypher(brief, phase))
        created.append(path)
    return created
