"""Tests for the find_entities MCP tool (Phase 3 TASK-023)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from api.server.mcp_tools.find_entities import (
    make_find_entities_tool,
    _Params,
    _scan_for_write_verbs,
)
from api.server.services.audit_logger import AuditLogger
from api.server.services.entity_graph import EntityGraph, EntityWrite


@pytest.fixture()
def graph(tmp_path: Path) -> EntityGraph:
    g = EntityGraph(tmp_path / "g.kuzu")
    yield g
    g.close()


@pytest.fixture()
def audit() -> AuditLogger:
    return AuditLogger()


def _invoke(tool, pattern, params=None, limit=100):
    import asyncio
    from copilot.tools import ToolInvocation
    args = {"cypher_pattern": pattern, "params": params, "limit": limit}
    inv = ToolInvocation(
        session_id="t", tool_call_id="t", tool_name=tool.name, arguments=args
    )
    result = asyncio.run(tool.handler(inv))
    return json.loads(result.text_result_for_llm)


@pytest.mark.parametrize("verb", [
    "CREATE", "MERGE", "DELETE", "DETACH", "SET", "REMOVE", "DROP", "CALL",
])
def test_scan_rejects_each_write_verb(verb):
    pattern = f"MATCH (n:Person) {verb} (n) RETURN n"
    assert _scan_for_write_verbs(pattern) == verb


def test_scan_allows_safe_match():
    assert _scan_for_write_verbs("MATCH (n:Person) RETURN n") is None


def test_scan_word_boundary_does_not_false_positive_on_substring():
    # "creator" contains "create" but NOT as a whole word.
    assert _scan_for_write_verbs("MATCH (n) WHERE n.creator = 'x' RETURN n") is None


def _invoke_raw(tool, pattern, params=None, limit=100):
    import asyncio
    from copilot.tools import ToolInvocation
    args = {"cypher_pattern": pattern, "params": params, "limit": limit}
    inv = ToolInvocation(
        session_id="t", tool_call_id="t", tool_name=tool.name, arguments=args
    )
    return asyncio.run(tool.handler(inv))


def test_each_write_verb_rejected_by_tool(graph, audit):
    tool = make_find_entities_tool(graph, audit)
    for verb in ("CREATE", "MERGE", "DELETE", "DETACH", "SET", "REMOVE", "DROP", "CALL"):
        result = _invoke_raw(tool, f"MATCH (n) {verb} (n) RETURN n")
        # The SDK catches our ValueError and surfaces it via the
        # ToolResult.error channel (text_result_for_llm gets a generic
        # "tool produced an error" message).
        assert result.result_type == "failure", verb
        assert "read-only" in (result.error or ""), verb
    # Every denial was audited.
    actions = [e["action"] for e in audit._entries]
    denied = [a for a in actions if a == "governance.find_entities.denied"]
    assert len(denied) == 8


def test_basic_match_returns_rows(graph, audit):
    graph.upsert(EntityWrite(
        kind="Person", id="P-1", attrs={"name": "A"}, source_workflows=("t",),
    ))
    graph.upsert(EntityWrite(
        kind="Person", id="P-2", attrs={"name": "B"}, source_workflows=("t",),
    ))
    tool = make_find_entities_tool(graph, audit)
    out = _invoke(tool, "MATCH (n:Person) RETURN n")
    assert len(out) == 2


def test_limit_honored(graph, audit):
    for i in range(5):
        graph.upsert(EntityWrite(
            kind="Person", id=f"P-{i}", attrs={"name": "x"}, source_workflows=("t",),
        ))
    tool = make_find_entities_tool(graph, audit)
    out = _invoke(tool, "MATCH (n:Person) RETURN n", limit=2)
    assert len(out) == 2


def test_audit_on_success(graph, audit):
    graph.upsert(EntityWrite(
        kind="Person", id="P-1", attrs={"name": "A"}, source_workflows=("t",),
    ))
    tool = make_find_entities_tool(graph, audit)
    _invoke(tool, "MATCH (n:Person) RETURN n")
    actions = [e["action"] for e in audit._entries]
    assert "governance.find_entities" in actions
