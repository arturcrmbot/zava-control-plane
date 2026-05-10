"""query_entity MCP tool — fetch one entity by (kind, id).

Whitelists ``kind`` against the eight Plane 1 entity kinds before
interpolating into Cypher (defense-in-depth — a kind from a tool call
is treated as untrusted input).

Plan: plan/feature-agentic-org-phase-3-function-fms.md TASK-022.
"""
from __future__ import annotations
import json

from copilot.tools import ToolInvocation, ToolResult, define_tool
from pydantic import BaseModel, Field

from api.server.services.entity_graph import EntityGraph, _VALID_KINDS
from ._otel import traced_tool


def _validate_kind(kind: str) -> str:
    """Reject any kind not declared by the entity-graph schema."""
    if kind not in _VALID_KINDS:
        raise ValueError(
            f"query_entity: unknown entity kind {kind!r} "
            f"(expected one of {sorted(_VALID_KINDS)})"
        )
    return kind


class _Params(BaseModel):
    kind: str = Field(description="Entity kind (one of the 8 Plane 1 nodes)")
    id: str = Field(description="Primary key id of the entity")


def make_query_entity_tool(graph: EntityGraph):
    """Build the query_entity tool bound to ``graph``."""

    @define_tool(
        name="query_entity",
        description=(
            "Fetch a single entity by (kind, id). kind must be one of the "
            "eight Plane 1 entity kinds: "
            f"{sorted(_VALID_KINDS)}."
        ),
        skip_permission=True,
    )
    @traced_tool("query_entity")
    def query_entity(params: _Params, invocation: ToolInvocation) -> ToolResult:
        kind = _validate_kind(params.kind)
        row = graph.query_one(
            f"MATCH (n:{kind}) WHERE n.id = $id RETURN n",
            {"id": params.id},
        )
        node = row["n"] if row else None
        return ToolResult(
            text_result_for_llm=json.dumps(node, default=str),
            result_type="success",
        )

    return query_entity
