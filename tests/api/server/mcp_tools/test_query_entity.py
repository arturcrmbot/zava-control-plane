"""Tests for the query_entity MCP tool (Phase 3 TASK-022)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from api.server.mcp_tools.query_entity import (
    make_query_entity_tool,
    _Params,
    _validate_kind,
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


def test_known_entity_returned(graph):
    graph.upsert(EntityWrite(
        kind="Person", id="PERSON-EMP-0001",
        attrs={"name": "Alice", "email": "a@example.com"},
        source_workflows=("test",),
    ))
    tool = make_query_entity_tool(graph)
    out = _invoke(tool, kind="Person", id="PERSON-EMP-0001")
    assert out["id"] == "PERSON-EMP-0001"
    assert out["name"] == "Alice"


def test_missing_entity_returns_null(graph):
    tool = make_query_entity_tool(graph)
    out = _invoke(tool, kind="Person", id="missing")
    assert out is None


def test_invalid_kind_rejected_by_validator():
    with pytest.raises(ValueError, match="unknown entity kind"):
        _validate_kind("Robot")


def _invoke_raw(tool, **params):
    """Invoke and return the raw ToolResult (so error handling can be inspected)."""
    import asyncio
    from copilot.tools import ToolInvocation
    inv = ToolInvocation(
        session_id="t", tool_call_id="t", tool_name=tool.name, arguments=params
    )
    return asyncio.run(tool.handler(inv))


def test_invalid_kind_in_tool_call_rejected(graph):
    tool = make_query_entity_tool(graph)
    # The SDK catches the ValueError raised by _validate_kind and surfaces
    # it via ToolResult(result_type="failure", error=...).
    result = _invoke_raw(tool, kind="Robot; DROP TABLE Person", id="x")
    assert result.result_type == "failure"
    assert "unknown entity kind" in (result.error or "")
