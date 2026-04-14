# src/server/mcp_tools/query_fleet.py
from __future__ import annotations
import json
from pydantic import BaseModel, Field
from copilot.tools import define_tool, ToolInvocation, ToolResult
from src.server.services.state_store import StateStore


class QueryFleetParams(BaseModel):
    phase: str | None = Field(default=None, description="Filter to a specific workflow phase")
    agency: str | None = Field(default=None, description="Filter to a specific agency")
    has_exception: bool | None = Field(default=None, description="Filter to workflows with active exceptions")


def make_query_fleet_tool(store: StateStore):
    @define_tool(description="Aggregated state of the workflow fleet.", skip_permission=True)
    def query_fleet(params: QueryFleetParams, invocation: ToolInvocation) -> ToolResult:
        items = store.list_workflows(
            phase=params.phase, agency=params.agency, has_exception=params.has_exception
        )
        excs = store.list_exceptions()
        by_phase: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for w in items:
            by_phase[w.current_phase] = by_phase.get(w.current_phase, 0) + 1
            by_status[w.status] = by_status.get(w.status, 0) + 1
        result = {
            "total": len(items),
            "by_phase": by_phase,
            "by_status": by_status,
            "open_exception_count": len(excs),
            "recent_exceptions": [
                {"id": e.id, "workflow_id": e.workflow_id, "category": e.category, "severity": e.severity}
                for e in excs[-5:]
            ],
        }
        return ToolResult(text_result_for_llm=json.dumps(result), result_type="success")

    return query_fleet
