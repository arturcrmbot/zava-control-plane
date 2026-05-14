"""query_fleet_state MCP tool — function-scoped fleet snapshot.

Returns workflows-in-flight aggregated by phase and listed individually.
When ``function_name`` is supplied, the result is filtered to workflow
``type`` values claimed by that function via
``FUNCTIONS[function_name].owns_domains``. When ``function_name`` is
``None``, the result spans the entire fleet (no filter).

Mirrors the shape of :func:`make_query_fleet_tool` so the Fleet Manager
SKILL can introspect both surfaces with the same expectations
(``{total, by_phase, workflows}``).

Plan: plan/feature-agentic-org-phase-3-function-fms.md TASK-019.
"""
from __future__ import annotations
import json

from copilot.tools import ToolInvocation, ToolResult, define_tool
from pydantic import BaseModel, Field

from api.server.services.state_store import StateStore
from api.shared.functions import FUNCTIONS
from ._otel import traced_tool


class _Params(BaseModel):
    phase: str | None = Field(
        default=None, description="Filter to a specific workflow phase"
    )


def make_query_fleet_state_tool(store: StateStore, function_name: str | None = None):
    """Build a function-scoped query_fleet_state tool.

    ``function_name=None`` is fleet-wide. Otherwise, only workflows whose
    ``type`` is in ``FUNCTIONS[function_name].owns_domains`` are counted.
    """
    allowed_types: frozenset[str] | None = None
    if function_name is not None:
        if function_name not in FUNCTIONS:
            raise ValueError(f"unknown function: {function_name!r}")
        allowed_types = frozenset(FUNCTIONS[function_name].owns_domains)

    tool_name = (
        "query_fleet_state"
        if function_name is None
        else f"query_fleet_state_{function_name.replace('-', '_')}"
    )
    description = (
        "Workflows currently in flight"
        + (
            f" — scoped to the {function_name} function "
            f"(domains: {sorted(allowed_types or [])})."
            if function_name is not None
            else " (fleet-wide)."
        )
    )

    @define_tool(name=tool_name, description=description, skip_permission=True)
    @traced_tool(tool_name)
    def query_fleet_state(params: _Params, invocation: ToolInvocation) -> ToolResult:
        items = store.list_workflows(phase=params.phase)
        if allowed_types is not None:
            items = [w for w in items if w.type in allowed_types]
        by_phase: dict[str, int] = {}
        workflows: list[dict] = []
        for w in items:
            by_phase[w.current_phase] = by_phase.get(w.current_phase, 0) + 1
            workflows.append(
                {
                    "id": w.id,
                    "type": w.type,
                    "status": w.status,
                    "current_phase": w.current_phase,
                    "verdict": getattr(w, "verdict", None),
                }
            )
        result = {
            "function": function_name,
            "total": len(items),
            "by_phase": by_phase,
            "workflows": workflows,
        }
        return ToolResult(text_result_for_llm=json.dumps(result), result_type="success")

    return query_fleet_state
