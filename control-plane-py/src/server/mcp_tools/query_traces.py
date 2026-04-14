# src/server/mcp_tools/query_traces.py
from __future__ import annotations
import json
from pydantic import BaseModel, Field
from copilot.tools import define_tool, ToolInvocation, ToolResult
from src.server.services.state_store import StateStore


class QueryTracesParams(BaseModel):
    workflow_id: str = Field(description="Workflow ID to fetch spans for")
    phase: str | None = Field(default=None, description="Optional phase filter")


def make_query_traces_tool(store: StateStore):
    @define_tool(description="OTEL spans for a workflow.", skip_permission=True)
    def query_traces(params: QueryTracesParams, invocation: ToolInvocation) -> ToolResult:
        spans = store.get_spans(params.workflow_id)
        if params.phase:
            spans = [s for s in spans if s.attributes.get("workflow.phase") == params.phase]
        result = [s.model_dump() for s in spans]
        return ToolResult(text_result_for_llm=json.dumps(result, default=str), result_type="success")

    return query_traces
