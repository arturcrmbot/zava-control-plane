"""Smoke tests for the query_kpi MCP tool stub (Phase 3 TASK-020)."""
from __future__ import annotations

import json

from api.server.mcp_tools.query_kpi import make_query_kpi_tool, _Params


def _invoke(tool):
    import asyncio
    from copilot.tools import ToolInvocation
    inv = ToolInvocation(
        session_id="t", tool_call_id="t", tool_name=tool.name, arguments={}
    )
    result = asyncio.run(tool.handler(inv))
    return json.loads(result.text_result_for_llm)


def test_stub_returns_empty_values_fleet_wide():
    tool = make_query_kpi_tool()
    out = _invoke(tool)
    assert out["values"] == []
    assert out["stub"] is True
    assert out["function"] is None


def test_stub_carries_declared_kpis_when_function_scoped():
    tool = make_query_kpi_tool(function_name="finance")
    out = _invoke(tool)
    assert out["function"] == "finance"
    assert "dso" in out["declared_kpis"]
    assert out["values"] == []


def test_unknown_function_raises():
    import pytest
    with pytest.raises(ValueError, match="unknown function"):
        make_query_kpi_tool(function_name="not-a-function")
