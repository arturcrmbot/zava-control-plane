"""Tests for the find_entities MCP tool (Phase 3 TASK-023, refactored c2).

After the c2 repo-coherence remediation the tool no longer accepts
free-form Cypher; it dispatches on a ``pattern_name`` declared in
``api.server.services.find_patterns`` and validates the supplied
``params`` dict against the per-pattern validators.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from copilot.tools import ToolInvocation

from api.server.mcp_tools.find_entities import make_find_entities_tool
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


def _invoke(tool, *, pattern_name: str, params: dict | None = None):
    args = {"pattern_name": pattern_name, "params": params}
    inv = ToolInvocation(
        session_id="t", tool_call_id="t", tool_name=tool.name, arguments=args
    )
    return asyncio.run(tool.handler(inv))


def _seed_persons(graph: EntityGraph, n: int = 2) -> None:
    for i in range(n):
        graph.upsert(EntityWrite(
            kind="Person",
            id=f"P-{i}",
            attrs={"name": f"name-{i}"},
            source_workflows=("t",),
        ))


def test_entities_by_kind_returns_rows(graph, audit):
    _seed_persons(graph, 3)
    tool = make_find_entities_tool(graph, audit)
    result = _invoke(
        tool, pattern_name="entities_by_kind", params={"kind": "Person"}
    )
    rows = json.loads(result.text_result_for_llm)
    assert len(rows) == 3


def test_entities_by_kind_respects_limit(graph, audit):
    _seed_persons(graph, 5)
    tool = make_find_entities_tool(graph, audit)
    result = _invoke(
        tool,
        pattern_name="entities_by_kind",
        params={"kind": "Person", "limit": 2},
    )
    rows = json.loads(result.text_result_for_llm)
    assert len(rows) == 2


def test_entity_by_id(graph, audit):
    _seed_persons(graph, 2)
    tool = make_find_entities_tool(graph, audit)
    result = _invoke(
        tool,
        pattern_name="entity_by_id",
        params={"kind": "Person", "id": "P-1"},
    )
    rows = json.loads(result.text_result_for_llm)
    assert len(rows) == 1
    assert rows[0]["n"]["id"] == "P-1"


def test_entities_touched_by_workflow(graph, audit):
    graph.upsert(EntityWrite(
        kind="Person",
        id="P-W",
        attrs={"name": "Workflow Person"},
        source_workflows=("WF-1",),
    ))
    tool = make_find_entities_tool(graph, audit)
    result = _invoke(
        tool,
        pattern_name="entities_touched_by_workflow",
        params={"workflow_id": "WF-1"},
    )
    rows = json.loads(result.text_result_for_llm)
    ids = [r["n"]["id"] for r in rows]
    assert "P-W" in ids


def test_unknown_pattern_is_denied_and_audited(graph, audit):
    tool = make_find_entities_tool(graph, audit)
    result = _invoke(
        tool, pattern_name="not_a_real_pattern", params={}
    )
    assert result.result_type == "failure"
    assert "find_entities" in (result.error or "")
    actions = [e["action"] for e in audit._entries]
    assert "governance.find_entities.denied" in actions


def test_invalid_param_is_denied_and_audited(graph, audit):
    tool = make_find_entities_tool(graph, audit)
    # 'kind' is not in the eight Plane 1 entity kinds.
    result = _invoke(
        tool,
        pattern_name="entities_by_kind",
        params={"kind": "NotAKind"},
    )
    assert result.result_type == "failure"
    actions = [e["action"] for e in audit._entries]
    assert "governance.find_entities.denied" in actions


def test_missing_required_param_is_denied(graph, audit):
    tool = make_find_entities_tool(graph, audit)
    # entity_by_id requires `id`.
    result = _invoke(
        tool,
        pattern_name="entity_by_id",
        params={"kind": "Person"},
    )
    assert result.result_type == "failure"
    actions = [e["action"] for e in audit._entries]
    assert "governance.find_entities.denied" in actions


def test_audit_on_success(graph, audit):
    _seed_persons(graph, 1)
    tool = make_find_entities_tool(graph, audit)
    _invoke(
        tool, pattern_name="entities_by_kind", params={"kind": "Person"}
    )
    actions = [e["action"] for e in audit._entries]
    assert "governance.find_entities" in actions
