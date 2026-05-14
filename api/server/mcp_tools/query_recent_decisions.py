"""query_recent_decisions MCP tool — most recent Decision nodes for a
persona role, optionally constrained to a function's owned domains.

Reads from the embedded entity graph (Plane 1). When ``function_name``
is supplied, decisions are joined to their parent ``Workflow`` node and
constrained to ``Workflow.workflow_type ∈
FUNCTIONS[function_name].owns_domains``.

Plan: plan/feature-agentic-org-phase-3-function-fms.md TASK-021.
"""
from __future__ import annotations
import json

from copilot.tools import ToolInvocation, ToolResult, define_tool
from pydantic import BaseModel, Field

from api.server.services.entity_graph import EntityGraph
from api.shared.functions import FUNCTIONS
from ._otel import traced_tool


class _Params(BaseModel):
    persona_role: str = Field(description="Persona role to filter decisions by")
    limit: int = Field(default=10, ge=1, le=500)


def make_query_recent_decisions_tool(
    graph: EntityGraph, function_name: str | None = None
):
    """Build a function-scoped query_recent_decisions tool."""
    allowed_types: tuple[str, ...] | None = None
    if function_name is not None:
        if function_name not in FUNCTIONS:
            raise ValueError(f"unknown function: {function_name!r}")
        allowed_types = tuple(FUNCTIONS[function_name].owns_domains)

    tool_name = (
        "query_recent_decisions"
        if function_name is None
        else f"query_recent_decisions_{function_name.replace('-', '_')}"
    )
    description = (
        "Recent Decision nodes for a persona role, ordered by decided_at DESC"
        + (
            f" (scoped to {function_name} domains: {list(allowed_types or [])})."
            if function_name is not None
            else "."
        )
    )

    @define_tool(name=tool_name, description=description, skip_permission=True)
    @traced_tool(tool_name)
    def query_recent_decisions(
        params: _Params, invocation: ToolInvocation
    ) -> ToolResult:
        # LIMIT inlined as int — Kuzu 0.6.1 does not parameter-substitute
        # inside LIMIT (mirrors EntityGraph.find_by_pattern precedent).
        limit_int = int(params.limit)
        if allowed_types:
            cypher = (
                "MATCH (d:Decision), (w:Workflow) "
                "WHERE d.workflow_id = w.id "
                "AND d.persona_role = $pr "
                "AND w.workflow_type IN $domains "
                "RETURN d ORDER BY d.decided_at DESC "
                f"LIMIT {limit_int}"
            )
            rows = graph.query(
                cypher,
                {"pr": params.persona_role, "domains": list(allowed_types)},
            )
        else:
            cypher = (
                "MATCH (d:Decision) "
                "WHERE d.persona_role = $pr "
                "RETURN d ORDER BY d.decided_at DESC "
                f"LIMIT {limit_int}"
            )
            rows = graph.query(cypher, {"pr": params.persona_role})

        decisions = [row["d"] for row in rows]
        return ToolResult(
            text_result_for_llm=json.dumps(
                {
                    "function": function_name,
                    "persona_role": params.persona_role,
                    "count": len(decisions),
                    "decisions": decisions,
                },
                default=str,
            ),
            result_type="success",
        )

    return query_recent_decisions
