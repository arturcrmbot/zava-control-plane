"""find_entities MCP tool — read-only Cypher passthrough with a write-verb
deny-list.

Wraps :meth:`EntityGraph.find_by_pattern` (which appends ``LIMIT`` if the
caller's pattern lacks one) and rejects any pattern that contains a
write or DDL keyword. Successful and denied calls are both audited so
governance can monitor query patterns over time.

Plan: plan/feature-agentic-org-phase-3-function-fms.md TASK-023.
"""
from __future__ import annotations
import json
import re
from typing import Any

from copilot.tools import ToolInvocation, ToolResult, define_tool
from pydantic import BaseModel, Field

from api.server.services.audit_logger import AuditLogger
from api.server.services.entity_graph import EntityGraph
from ._otel import traced_tool


# Word-boundary scan so identifiers that happen to contain a banned
# verb (e.g. "creator") aren't false-positives.
_WRITE_VERBS = ("CREATE", "MERGE", "DELETE", "DETACH", "SET", "REMOVE", "DROP", "CALL")
_DENY_PATTERN = re.compile(
    r"\b(" + "|".join(_WRITE_VERBS) + r")\b", re.IGNORECASE
)


class _Params(BaseModel):
    cypher_pattern: str = Field(
        description="A complete MATCH ... RETURN ... Cypher pattern. Read-only."
    )
    params: dict[str, Any] | None = Field(default=None)
    limit: int = Field(default=100, ge=1, le=1000)


def _scan_for_write_verbs(pattern: str) -> str | None:
    """Return the first matched write verb, or None if the pattern is safe."""
    m = _DENY_PATTERN.search(pattern)
    return m.group(1).upper() if m else None


def make_find_entities_tool(graph: EntityGraph, audit: AuditLogger):
    """Build the find_entities tool bound to ``graph`` + ``audit``."""

    @define_tool(
        name="find_entities",
        description=(
            "Run a read-only Cypher MATCH pattern against the entity graph. "
            "Write/DDL verbs (CREATE, MERGE, DELETE, DETACH, SET, REMOVE, "
            "DROP, CALL) are rejected. LIMIT is auto-appended if missing."
        ),
        skip_permission=True,
    )
    @traced_tool("find_entities")
    def find_entities(params: _Params, invocation: ToolInvocation) -> ToolResult:
        offending = _scan_for_write_verbs(params.cypher_pattern)
        if offending is not None:
            audit.log(
                "governance.find_entities.denied",
                {
                    "pattern": params.cypher_pattern,
                    "verb": offending,
                },
            )
            raise ValueError(
                "find_entities: read-only — write/DDL keyword not permitted "
                f"({offending})"
            )
        rows = graph.find_by_pattern(
            params.cypher_pattern, params.params, limit=params.limit
        )
        audit.log(
            "governance.find_entities",
            {
                "pattern": params.cypher_pattern,
                "row_count": len(rows),
                "limit": params.limit,
            },
        )
        return ToolResult(
            text_result_for_llm=json.dumps(rows, default=str),
            result_type="success",
        )

    return find_entities
