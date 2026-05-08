"""recall_similar_hires MCP tool — §4.7 episodic memory surface.

Returns past hires for the same `(role_family, jurisdiction)` tuple along
with their outcome (accepted / rejected / withdrew). Spine implementation
queries the in-process state store; cloud target swaps in a Cosmos partition
keyed by `(jurisdiction, role_family)`.
"""
from __future__ import annotations
import json
from typing import Any

from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool
from api.server.state import app_state


@traced_tool("recall.similar_hires")
def recall_similar_hires(role_family: str, jurisdiction: str, limit: int = 5) -> dict:
    trace.get_current_span().set_attribute("zava.recall.role_family", role_family)
    trace.get_current_span().set_attribute("zava.recall.jurisdiction", jurisdiction)

    workflows = app_state.store.list_workflows()
    matches: list[dict[str, Any]] = []
    for w in workflows:
        if getattr(w, "type", None) != "hiring":
            continue
        meta = getattr(w, "metadata", {}) or {}
        if str(meta.get("role_family", "")).lower() != role_family.lower():
            continue
        if str(meta.get("jurisdiction", "")).upper() != jurisdiction.upper():
            continue
        matches.append({
            "workflow_id": w.id,
            "outcome": w.status,
            "decided_at": getattr(w, "completed_at", None),
            "panel_score": meta.get("panel_score"),
            "rejection_reason": meta.get("rejection_reason"),
        })
    matches = matches[-limit:]
    return {
        "role_family": role_family,
        "jurisdiction": jurisdiction,
        "n": len(matches),
        "hires": matches,
    }


class _RecallParams(BaseModel):
    role_family: str = Field(description="Role family slug, e.g. 'senior-data-engineer'.")
    jurisdiction: str = Field(description="Jurisdiction code: 'USA' or 'DE'.")
    limit: int = Field(default=5, description="Max matches to return.")


@define_tool(
    name="recall_similar_hires",
    description=(
        "Episodic memory: return prior hires for the same (role_family, "
        "jurisdiction) and their outcome. Use to ground 'we hired three of "
        "these last year, here's what happened' rationale."
    ),
)
def recall_similar_hires_tool(params: _RecallParams) -> ToolResult:
    record = recall_similar_hires(
        role_family=params.role_family,
        jurisdiction=params.jurisdiction,
        limit=params.limit,
    )
    return ToolResult(text_result_for_llm=json.dumps(record, ensure_ascii=False))
