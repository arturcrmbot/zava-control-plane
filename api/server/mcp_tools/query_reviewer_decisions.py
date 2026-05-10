"""query_reviewer_decisions MCP tool — surfaces SSC reviewer decisions from
the audit ledger so the Fleet Manager can detect autonomy-worthy clusters.

Dual-surface (plain Python `query()` + SDK-native Tool) per the project's
MCP tool convention. Reads `app_state.store.list_workflows()` and walks
each workflow's `action_ledger` for entries with `action == "reviewer.decision"`.
"""
from __future__ import annotations
import json
from collections import Counter
from typing import Optional

from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool
from api.server.state import app_state


@traced_tool("query.reviewer_decisions")
def query(category: Optional[str] = None, limit: int = 100) -> dict:
    """Return reviewer decisions and a per-policy-clause cluster summary."""
    span = trace.get_current_span()
    if category:
        span.set_attribute("zava.query.category", category)
    span.set_attribute("zava.query.limit", limit)

    decisions: list[dict] = []
    for w in app_state.store.list_workflows():
        for entry in (w.action_ledger or []):
            if entry.action != "reviewer.decision":
                continue
            details = entry.details or {}
            if category and details.get("category") != category:
                continue
            decisions.append({
                "workflow_id": w.id,
                "decided_at": entry.timestamp,
                "decided_by": entry.actor_id,
                "decision": details.get("recommendation") or details.get("decision"),
                "policy_clause": details.get("policy_clause"),
                "category": details.get("category"),
                "verdict": getattr(w, "verdict", None),
            })
    decisions.sort(key=lambda d: d["decided_at"], reverse=True)
    decisions = decisions[:limit]

    # Cluster by policy_clause + decision so the FM skill can reason about
    # autonomy candidates: "100 amber meals UK claims, 92% accepted as
    # justified — propose autonomy on §3.1 UK".
    clusters = Counter(
        (d["policy_clause"], d["decision"]) for d in decisions if d["policy_clause"]
    )
    top_clusters = [
        {"policy_clause": pc, "decision": dec, "count": c}
        for (pc, dec), c in clusters.most_common(10)
    ]

    span.set_attribute("zava.query.result_count", len(decisions))
    return {"decisions": decisions, "clusters": top_clusters, "n": len(decisions)}


class _Params(BaseModel):
    category: Optional[str] = Field(
        default=None,
        description="Filter to this expense category (e.g. 'meals', 'travel').",
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of decisions to return.",
    )


@define_tool(
    name="query_reviewer_decisions",
    description=(
        "List recent SSC reviewer decisions and cluster them by policy clause + decision. "
        "Use to identify candidates for autonomy promotion."
    ),
)
def query_reviewer_decisions_tool(params: _Params) -> ToolResult:
    out = query(category=params.category, limit=params.limit)
    return ToolResult(text_result_for_llm=json.dumps(out, ensure_ascii=False))
