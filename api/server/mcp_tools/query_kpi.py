"""query_kpi MCP tool — STUB.

The KPI store lands in Phase 4 of the overall plan
(plan/feature-agentic-org-phase-4-ceo-fm.md TASK-008). Until then, this
tool returns an empty list so per-function FMs can be wired with the
correct surface today and switch over to a real ``kpi_store`` in Phase 4
without changing the SKILL prompt.

Plan: plan/feature-agentic-org-phase-3-function-fms.md TASK-020.
"""
from __future__ import annotations
import json

from copilot.tools import ToolInvocation, ToolResult, define_tool
from pydantic import BaseModel

from api.shared.functions import FUNCTIONS
from ._otel import traced_tool


class _Params(BaseModel):
    pass


def make_query_kpi_tool(kpi_store=None, function_name: str | None = None):
    """Build a (currently stubbed) query_kpi tool.

    ``kpi_store`` is accepted for forward-compat with Phase 4 wiring; it
    is ignored today. The returned tool always resolves to ``[]``.
    """
    if function_name is not None and function_name not in FUNCTIONS:
        raise ValueError(f"unknown function: {function_name!r}")

    tool_name = (
        "query_kpi"
        if function_name is None
        else f"query_kpi_{function_name.replace('-', '_')}"
    )
    declared = (
        list(FUNCTIONS[function_name].kpis) if function_name is not None else []
    )
    description = (
        "STUB — returns an empty KPI list. The kpi_store lands in Phase 4 "
        "(plan/feature-agentic-org-phase-4-ceo-fm.md TASK-008)."
        + (
            f" Function {function_name} declares KPIs: {declared}."
            if function_name is not None
            else ""
        )
    )

    @define_tool(name=tool_name, description=description, skip_permission=True)
    @traced_tool(tool_name)
    def query_kpi(params: _Params, invocation: ToolInvocation) -> ToolResult:
        return ToolResult(
            text_result_for_llm=json.dumps(
                {
                    "function": function_name,
                    "declared_kpis": declared,
                    "values": [],
                    "stub": True,
                }
            ),
            result_type="success",
        )

    return query_kpi
