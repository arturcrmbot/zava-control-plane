"""find_entities MCP tool — named, parametrised query templates.

Free-form Cypher (previously gated only by a regex deny-list — bypassable)
has been replaced with a fixed library of named templates declared in
:mod:`api.server.services.find_patterns`. The MCP surface accepts a
``pattern_name`` plus a ``params`` dict; both are validated by the
template registry's per-template param validators before any Cypher
reaches Kuzu.

Plan: ``plan/refactor-repo-coherence-remediation-1.md`` — c2.
"""
from __future__ import annotations
import json
from typing import Any

from copilot.tools import ToolInvocation, ToolResult, define_tool
from pydantic import BaseModel, Field

from api.server.services.audit_logger import AuditLogger
from api.server.services.entity_graph import EntityGraph
from api.server.services.find_patterns import (
    PATTERNS,
    describe_patterns,
    render,
)
from ._otel import traced_tool


def _build_description() -> str:
    """Human-readable per-pattern description for the tool docstring."""
    lines = [
        "Run one of the registered, parametrised entity-graph query "
        "templates. Free-form Cypher is not accepted; pick a "
        "pattern_name and pass its params.",
        "",
        "Available patterns:",
    ]
    for name, info in describe_patterns().items():
        params = ", ".join(info["params"]) or "—"
        lines.append(f"- {name}({params}): {info['describe']}")
    return "\n".join(lines)


class _Params(BaseModel):
    pattern_name: str = Field(
        description=(
            "Name of a registered find_entities query template. "
            "One of: " + ", ".join(sorted(PATTERNS)) + "."
        )
    )
    params: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Parameter dict for the chosen pattern. Each pattern "
            "declares its own required + optional params."
        ),
    )


def make_find_entities_tool(graph: EntityGraph, audit: AuditLogger):
    """Build the find_entities tool bound to ``graph`` + ``audit``."""

    @define_tool(
        name="find_entities",
        description=_build_description(),
        skip_permission=True,
    )
    @traced_tool("find_entities")
    def find_entities(params: _Params, invocation: ToolInvocation) -> ToolResult:
        try:
            cypher, bind = render(params.pattern_name, params.params)
        except (KeyError, ValueError) as ex:
            audit.log(
                "governance.find_entities.denied",
                {
                    "pattern": params.pattern_name,
                    "reason": str(ex),
                },
            )
            raise ValueError(f"find_entities: {ex}") from ex
        rows = graph.query(cypher, bind)
        audit.log(
            "governance.find_entities",
            {
                "pattern": params.pattern_name,
                "row_count": len(rows),
            },
        )
        return ToolResult(
            text_result_for_llm=json.dumps(rows, default=str),
            result_type="success",
        )

    return find_entities
