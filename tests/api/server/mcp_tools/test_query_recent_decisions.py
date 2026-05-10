"""Tests for the query_recent_decisions MCP tool (Phase 3 TASK-021)."""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import pytest

from api.server.mcp_tools.query_recent_decisions import (
    make_query_recent_decisions_tool,
    _Params,
)
from api.server.services.entity_graph import EntityGraph, EntityWrite


@pytest.fixture()
def graph(tmp_path: Path) -> EntityGraph:
    g = EntityGraph(tmp_path / "g.kuzu")
    yield g
    g.close()


def _invoke(tool, **params):
    import asyncio
    from copilot.tools import ToolInvocation
    inv = ToolInvocation(
        session_id="t", tool_call_id="t", tool_name=tool.name, arguments=params
    )
    result = asyncio.run(tool.handler(inv))
    return json.loads(result.text_result_for_llm)


def _add_decision(g: EntityGraph, did: str, persona: str, wid: str, ts: float):
    # The natural triple (workflow_id, phase, persona_role) is the dedupe
    # key, so vary phase per call to mint distinct decisions.
    g.record_decision(
        workflow_id=wid,
        phase=did,  # unique per call to bypass dedupe
        persona_role=persona,
        verdict="green",
        reason="ok",
        decided_at=datetime.fromtimestamp(ts),
        source_event="x",
        attributes={},
    )


def _add_workflow(g: EntityGraph, wid: str, wtype: str):
    g.upsert(EntityWrite(
        kind="Workflow", id=wid,
        attrs={"workflow_type": wtype, "status": "in_progress"},
    ))


def test_fleet_wide_returns_decisions_ordered_desc(graph):
    _add_workflow(graph, "W-1", "ap-invoice")
    base = time.time()
    _add_decision(graph, "D-1", "ap_clerk", "W-1", base - 100)
    _add_decision(graph, "D-2", "ap_clerk", "W-1", base - 50)
    _add_decision(graph, "D-3", "ap_clerk", "W-1", base)

    tool = make_query_recent_decisions_tool(graph)
    out = _invoke(tool, persona_role="ap_clerk", limit=10)
    # record_decision mints its own ULIDs; check ordering by decided_at.
    ts = [d["decided_at"] for d in out["decisions"]]
    assert ts == sorted(ts, reverse=True)
    assert len(out["decisions"]) == 3


def test_limit_honored(graph):
    _add_workflow(graph, "W-1", "ap-invoice")
    base = time.time()
    for i in range(5):
        _add_decision(graph, f"D-{i}", "ap_clerk", "W-1", base + i)
    tool = make_query_recent_decisions_tool(graph)
    out = _invoke(tool, persona_role="ap_clerk", limit=2)
    assert out["count"] == 2


def test_function_scope_filters_by_owned_domains(graph):
    _add_workflow(graph, "W-FIN", "ap-invoice")          # finance
    _add_workflow(graph, "W-MKT", "creative-campaign")   # marketing
    base = time.time()
    _add_decision(graph, "D-FIN", "controller", "W-FIN", base)
    _add_decision(graph, "D-MKT", "controller", "W-MKT", base + 1)

    tool = make_query_recent_decisions_tool(graph, function_name="finance")
    out = _invoke(tool, persona_role="controller")
    # Only the finance-domain decision survives the workflow_type filter.
    assert out["count"] == 1
    assert out["decisions"][0]["workflow_id"] == "W-FIN"
    assert out["function"] == "finance"


def test_unknown_function_raises(graph):
    with pytest.raises(ValueError, match="unknown function"):
        make_query_recent_decisions_tool(graph, function_name="bogus")
