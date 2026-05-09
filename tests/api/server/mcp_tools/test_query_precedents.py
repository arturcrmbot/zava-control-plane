"""Tests for the Phase 4 IP3 query_precedents MCP tool."""
from __future__ import annotations

from pathlib import Path

import pytest

from api.server.mcp_tools.query_precedents import (
    _DENY_PATTERN,
    _GENERIC_QUERY,
    _load_template,
    make_query_precedents_tool,
)


class _FakeGraph:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.last_cypher: str | None = None
        self.last_params: dict | None = None

    def query(self, cypher: str, params: dict) -> list[dict]:
        self.last_cypher = cypher
        self.last_params = params
        return self.rows


def test_happy_path_returns_rows():
    graph = _FakeGraph([
        {"d": {"id": "dec-1", "decided_at": "2026-05-01"}},
        {"d": {"id": "dec-2", "decided_at": "2026-04-01"}},
    ])
    tool = make_query_precedents_tool(graph)
    rows = tool("ap_clerk", "vendor-99", limit=5)
    assert len(rows) == 2
    assert graph.last_cypher == _GENERIC_QUERY
    assert graph.last_params == {
        "persona_role": "ap_clerk",
        "entity_id": "vendor-99",
        "limit": 5,
    }


def test_empty_path_returns_empty():
    graph = _FakeGraph([])
    tool = make_query_precedents_tool(graph)
    assert tool("ap_clerk", "vendor-no-decisions") == []


def test_deny_list_rejects_write_verbs(tmp_path: Path, monkeypatch):
    """A precedent template containing CREATE/MERGE/etc raises ValueError."""
    bad = tmp_path / "rogue_phase.cypher"
    bad.write_text("CREATE (n:Decision {id: 'x'}) RETURN n", encoding="utf-8")
    # Point the template loader at our tmp dir.
    import api.server.mcp_tools.query_precedents as qp
    monkeypatch.setattr(qp, "_TEMPLATE_DIR", tmp_path)

    with pytest.raises(ValueError, match="write/DDL keyword"):
        qp._load_template("rogue", "phase")


def test_deny_pattern_matches_each_write_verb():
    for verb in ("CREATE", "MERGE", "DELETE", "DETACH", "SET", "REMOVE", "DROP", "CALL"):
        assert _DENY_PATTERN.search(f"some {verb} thing")


def test_existing_template_loads(tmp_path: Path, monkeypatch):
    import api.server.mcp_tools.query_precedents as qp
    tmpl = tmp_path / "expense-claim_approval.cypher"
    tmpl.write_text(
        "MATCH (d:Decision)-[:DECIDED_ON]->(e {id: $entity_id}) RETURN d LIMIT $limit",
        encoding="utf-8",
    )
    monkeypatch.setattr(qp, "_TEMPLATE_DIR", tmp_path)
    cypher = qp._load_template("expense-claim", "approval")
    assert "MATCH" in cypher and "$entity_id" in cypher


def test_workflow_type_phase_routes_to_template(tmp_path: Path, monkeypatch):
    import api.server.mcp_tools.query_precedents as qp
    tmpl = tmp_path / "wt_phase.cypher"
    tmpl.write_text("MATCH (d:Decision) RETURN d LIMIT $limit", encoding="utf-8")
    monkeypatch.setattr(qp, "_TEMPLATE_DIR", tmp_path)
    graph = _FakeGraph([])
    tool = qp.make_query_precedents_tool(graph)
    tool("role", "ent", limit=3, workflow_type="wt", phase="phase")
    assert graph.last_cypher == "MATCH (d:Decision) RETURN d LIMIT $limit"
