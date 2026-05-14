"""Tests for build_function_fm_tools factory (Phase 3 TASK-024)."""
from __future__ import annotations

from pathlib import Path

import pytest

from api.server.mcp_tools import build_function_fm_tools
from api.server.services.audit_logger import AuditLogger
from api.server.services.entity_graph import EntityGraph
from api.server.services.state_store import StateStore


@pytest.fixture()
def graph(tmp_path: Path) -> EntityGraph:
    g = EntityGraph(tmp_path / "g.kuzu")
    yield g
    g.close()


def test_returns_five_tools_for_finance(graph):
    store = StateStore()
    audit = AuditLogger()
    tools = build_function_fm_tools(store, audit, graph, "finance")
    assert len(tools) == 5
    names = [t.name for t in tools]
    # The first three carry the function suffix; query_entity / find_entities
    # are graph-only and stay un-suffixed.
    assert names[0] == "query_fleet_state_finance"
    assert names[1] == "query_kpi_finance"
    assert names[2] == "query_recent_decisions_finance"
    assert names[3] == "query_entity"
    assert names[4] == "find_entities"


def test_returns_distinct_instances_per_function(graph):
    store = StateStore()
    audit = AuditLogger()
    fin = build_function_fm_tools(store, audit, graph, "finance")
    hr = build_function_fm_tools(store, audit, graph, "hr")
    assert fin[0] is not hr[0]
    assert fin[0].name == "query_fleet_state_finance"
    assert hr[0].name == "query_fleet_state_hr"


def test_unknown_function_rejected(graph):
    store = StateStore()
    audit = AuditLogger()
    with pytest.raises(ValueError, match="unknown function"):
        build_function_fm_tools(store, audit, graph, "bogus")
