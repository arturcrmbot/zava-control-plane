"""Tests for query_function_fm MCP tool (Phase 4 IP6 TASK-029, DEC-OQ2).

Asserts the pure-Python ``query_function_fm`` handler resolves a named
``FunctionFleetManager`` from a stand-in app_state, returns the stub
response, and projects the latest KPI snapshot row per metric.
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from api.server.mcp_tools.query_function_fm import (
    _latest_per_metric,
    make_query_function_fm_tool,
    query_function_fm,
)
from api.server.services.kpi_store import KpiStore


@pytest.fixture
def kpi_store(tmp_path):
    store = KpiStore(tmp_path / "kpis.sqlite")
    store.publish("finance", "dso", 32.0, "2026-04", schema_version=1)
    # Two snapshots for the same metric — the later one must win.
    time.sleep(0.01)
    store.publish("finance", "dso", 28.0, "2026-05", schema_version=1)
    store.publish("finance", "dpo", 41.0, "2026-05", schema_version=1)
    store.publish("hr", "time-to-hire", 22.0, "2026-05", schema_version=1)
    return store


@pytest.fixture
def app_state(kpi_store):
    """Minimal duck-typed app_state with kpi_store + function_fms map."""
    return SimpleNamespace(
        kpi_store=kpi_store,
        function_fms={
            "finance": object(),  # opaque — we only check it is registered
            "hr": object(),
        },
    )


def test_latest_per_metric_picks_latest():
    rows = [
        {"metric": "dso", "value": 30, "captured_at": 100.0},
        {"metric": "dso", "value": 28, "captured_at": 200.0},
        {"metric": "dpo", "value": 41, "captured_at": 150.0},
    ]
    out = _latest_per_metric(rows)
    by_metric = {r["metric"]: r for r in out}
    assert by_metric["dso"]["value"] == 28
    assert by_metric["dpo"]["value"] == 41


def test_query_function_fm_returns_stub_payload(app_state):
    out = query_function_fm(app_state, "finance", "what's our DSO?")
    assert out["function"] == "finance"
    assert out["prompt"] == "what's our DSO?"
    assert "stub" in out["response"]
    snapshot = {r["metric"]: r["value"] for r in out["kpi_snapshot"]}
    assert snapshot == {"dso": 28.0, "dpo": 41.0}


def test_query_function_fm_filters_to_function(app_state):
    out = query_function_fm(app_state, "hr", "headcount?")
    metrics = {r["metric"] for r in out["kpi_snapshot"]}
    assert metrics == {"time-to-hire"}


def test_query_function_fm_unknown_function_raises(app_state):
    with pytest.raises(ValueError, match="unknown function"):
        query_function_fm(app_state, "not-a-thing", "?")


def test_query_function_fm_unregistered_function_raises(kpi_store):
    state = SimpleNamespace(kpi_store=kpi_store, function_fms={})  # empty
    with pytest.raises(LookupError):
        query_function_fm(state, "finance", "?")


def test_make_tool_handler_returns_success_json(app_state):
    tool = make_query_function_fm_tool(app_state)
    from copilot.tools import ToolInvocation
    inv = ToolInvocation(
        session_id="t", tool_call_id="t", tool_name=tool.name,
        arguments={"function": "finance", "prompt": "DSO?"},
    )
    result = asyncio.run(tool.handler(inv))
    payload = json.loads(result.text_result_for_llm)
    assert payload["function"] == "finance"
    assert "kpi_snapshot" in payload


def test_make_tool_handler_returns_error_for_unknown(app_state):
    tool = make_query_function_fm_tool(app_state)
    from copilot.tools import ToolInvocation
    inv = ToolInvocation(
        session_id="t", tool_call_id="t", tool_name=tool.name,
        arguments={"function": "nope", "prompt": "?"},
    )
    result = asyncio.run(tool.handler(inv))
    assert result.result_type == "error"
    payload = json.loads(result.text_result_for_llm)
    assert "error" in payload
