"""query_kpi MCP tool — Phase 4 IP2 (TASK-012).

Reads from :class:`api.server.services.kpi_store.KpiStore`. When bound
to a ``function_name``, the tool filters to that function's snapshots
and includes the function's declared KPI list for context. If no store
is supplied (test paths, fleet-wide singleton without a configured
store), falls back to the empty-list contract Phase 3 shipped.
"""
from __future__ import annotations
import json

from copilot.tools import ToolInvocation, ToolResult, define_tool
from pydantic import BaseModel, Field

from api.shared.functions import FUNCTIONS
from ._otel import traced_tool


class _Params(BaseModel):
    metric: str | None = Field(default=None)
    since: str | None = Field(default=None)


def make_query_kpi_tool(kpi_store=None, function_name: str | None = None):
    """Build a query_kpi tool bound to ``kpi_store`` + ``function_name``.

    ``kpi_store`` is a :class:`KpiStore` (or duck-type with ``query``).
    A ``None`` store keeps the Phase 3 stub contract (empty list).
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
        "Return published KPI snapshot rows. Args: metric (optional), "
        "since (optional ISO period string, e.g. '2026-Q1' or '2026-05'). "
        "Each row carries function, metric, period, value, schema_version, "
        "captured_at."
        + (
            f" Bound to function {function_name!r} which declares KPIs: {declared}."
            if function_name is not None
            else ""
        )
    )

    @define_tool(name=tool_name, description=description, skip_permission=True)
    @traced_tool(tool_name)
    def query_kpi(params: _Params, invocation: ToolInvocation) -> ToolResult:
        if kpi_store is None:
            payload = {
                "function": function_name,
                "declared_kpis": declared,
                "values": [],
                "stub": True,
            }
        else:
            rows = kpi_store.query(
                function=function_name, metric=params.metric, since=params.since,
            )
            payload = {
                "function": function_name,
                "declared_kpis": declared,
                "values": rows,
            }
        return ToolResult(
            text_result_for_llm=json.dumps(payload, default=str),
            result_type="success",
        )

    return query_kpi
