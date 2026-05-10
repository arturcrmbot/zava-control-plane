"""audit_query MCP tool — broad ledger-query surface over the in-memory
audit store.

Wraps `app_state.store.list_workflows()`'s per-workflow `action_ledger` with
filters on `since` / `until` (UNIX timestamps), `actor_kind` ("agent" | "human"),
`workflow_id`, and `limit`. Returns chronological (newest-first) entries.

Dual-surface (plain Python `query()` + SDK-native Tool) per the project's
MCP tool convention.
"""
from __future__ import annotations
import json
from typing import Optional

from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool
from api.server.state import app_state


@traced_tool("audit.query")
def query(
    *,
    since: Optional[float] = None,
    until: Optional[float] = None,
    actor_kind: Optional[str] = None,
    workflow_id: Optional[str] = None,
    limit: int = 200,
) -> dict:
    """Return chronological audit-ledger entries matching the supplied filters."""
    span = trace.get_current_span()
    if since is not None:
        span.set_attribute("zava.audit.since", since)
    if until is not None:
        span.set_attribute("zava.audit.until", until)
    if actor_kind:
        span.set_attribute("zava.audit.actor_kind", actor_kind)
    if workflow_id:
        span.set_attribute("zava.audit.workflow_id", workflow_id)
    span.set_attribute("zava.audit.limit", limit)

    entries: list[dict] = []
    for w in app_state.store.list_workflows():
        if workflow_id and w.id != workflow_id:
            continue
        for e in (w.action_ledger or []):
            if since is not None and e.timestamp < since:
                continue
            if until is not None and e.timestamp > until:
                continue
            if actor_kind and e.actor_kind != actor_kind:
                continue
            entries.append({
                "workflow_id": w.id,
                "timestamp": e.timestamp,
                "actor_kind": e.actor_kind,
                "actor_id": e.actor_id,
                "action": e.action,
                "details": e.details,
            })
    entries.sort(key=lambda x: x["timestamp"], reverse=True)
    total = len(entries)
    out_entries = entries[:limit]
    span.set_attribute("zava.audit.result_count", len(out_entries))
    return {"entries": out_entries, "n": total}


class _Params(BaseModel):
    since: Optional[float] = Field(
        default=None,
        description="Lower-bound UNIX timestamp; entries earlier than this are excluded.",
    )
    until: Optional[float] = Field(
        default=None,
        description="Upper-bound UNIX timestamp; entries later than this are excluded.",
    )
    actor_kind: Optional[str] = Field(
        default=None,
        description="Filter to 'agent' or 'human' actors.",
    )
    workflow_id: Optional[str] = Field(
        default=None,
        description="Filter to a single workflow's ledger.",
    )
    limit: int = Field(
        default=200,
        ge=1,
        le=2000,
        description="Maximum number of entries to return (newest-first).",
    )


@define_tool(
    name="audit_query",
    description=(
        "Query the immutable audit ledger across workflows with optional filters "
        "(since, until, actor_kind, workflow_id, limit). Returns chronological "
        "(newest-first) ledger entries plus the total match count."
    ),
)
def audit_query_tool(params: _Params) -> ToolResult:
    out = query(
        since=params.since,
        until=params.until,
        actor_kind=params.actor_kind,
        workflow_id=params.workflow_id,
        limit=params.limit,
    )
    return ToolResult(text_result_for_llm=json.dumps(out, ensure_ascii=False))
