"""Tests for the query_fleet_state MCP tool (Phase 3 TASK-019)."""
from __future__ import annotations

import json
import time

from api.server.mcp_tools.query_fleet_state import make_query_fleet_state_tool, _Params
from api.server.services.state_store import StateStore
from api.shared.types import Workflow


def _wf(id: str, type_: str, phase: str = "Intake") -> Workflow:
    return Workflow(
        id=id,
        type=type_,
        status="in_progress",
        current_phase=phase,
        created_at=time.time(),
        sla_due_at=time.time() + 3600,
        jurisdiction="US",
        agency="Ogilvy-US",
    )


def _invoke(tool, **params):
    import asyncio
    from copilot.tools import ToolInvocation
    inv = ToolInvocation(
        session_id="t", tool_call_id="t", tool_name=tool.name, arguments=params
    )
    result = asyncio.run(tool.handler(inv))
    return json.loads(result.text_result_for_llm)


def test_fleet_wide_returns_all_workflows():
    store = StateStore()
    store.upsert_workflow(_wf("W-1", "ap-invoice"))
    store.upsert_workflow(_wf("W-2", "expense-claim"))
    tool = make_query_fleet_state_tool(store)
    out = _invoke(tool)
    assert out["function"] is None
    assert out["total"] == 2
    assert {w["id"] for w in out["workflows"]} == {"W-1", "W-2"}


def test_function_scoped_filters_by_owned_domains():
    store = StateStore()
    store.upsert_workflow(_wf("W-1", "ap-invoice"))      # finance
    store.upsert_workflow(_wf("W-2", "vendor-kyc"))      # finance
    store.upsert_workflow(_wf("W-3", "expense-claim"))   # legacy — excluded
    store.upsert_workflow(_wf("W-4", "creative-campaign"))  # marketing — excluded
    tool = make_query_fleet_state_tool(store, function_name="finance")
    out = _invoke(tool)
    assert out["function"] == "finance"
    assert out["total"] == 2
    assert {w["id"] for w in out["workflows"]} == {"W-1", "W-2"}


def test_by_phase_aggregates():
    store = StateStore()
    store.upsert_workflow(_wf("W-1", "ap-invoice", phase="Intake"))
    store.upsert_workflow(_wf("W-2", "ap-invoice", phase="Intake"))
    store.upsert_workflow(_wf("W-3", "ap-invoice", phase="Decision"))
    tool = make_query_fleet_state_tool(store, function_name="finance")
    out = _invoke(tool)
    assert out["by_phase"] == {"Intake": 2, "Decision": 1}


def test_unknown_function_raises():
    import pytest
    store = StateStore()
    with pytest.raises(ValueError, match="unknown function"):
        make_query_fleet_state_tool(store, function_name="not-a-function")
