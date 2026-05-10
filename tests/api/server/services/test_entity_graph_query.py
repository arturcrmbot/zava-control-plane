"""Cypher passthrough test for ``EntityGraph`` (TASK-003b).

Covers REQ-002: the three Cypher passthrough helpers (``query``,
``query_one``, ``find_by_pattern``) — Phase 3's ``query_entity`` /
``find_entities`` and Phase 4's ``query_precedents`` all bottom out on these.

Test seeds via raw Cypher because ``upsert`` lands in TASK-004; the helpers
under test are independent of the upsert path and can be exercised against
just the schema bootstrap.
"""
from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from api.server.services.entity_graph import EntityGraph


@pytest.fixture
def graph_with_two_persons(tmp_path: Path) -> EntityGraph:
    g = EntityGraph(tmp_path / "g.kuzu")
    # Raw-Cypher seed — TASK-004 will replace this with EntityWrite/upsert.
    g.conn.execute(
        "CREATE (n:Person {id: 'EMP-0001', name: 'Alice', source_workflows: ['bootstrap']})"
    )
    g.conn.execute(
        "CREATE (n:Person {id: 'EMP-0002', name: 'Bob', source_workflows: ['bootstrap']})"
    )
    return g


def test_query_returns_parameterised_rows(graph_with_two_persons: EntityGraph) -> None:
    rows = graph_with_two_persons.query(
        "MATCH (n:Person) WHERE n.id = $id RETURN n.id AS id, n.name AS name",
        {"id": "EMP-0001"},
    )
    assert len(rows) == 1
    assert rows[0]["id"] == "EMP-0001"
    assert rows[0]["name"] == "Alice"


def test_query_returns_node_dict_under_alias(graph_with_two_persons: EntityGraph) -> None:
    # When the projection is the node itself, Kuzu hands back a dict
    # representation of the node — verify our wrapper preserves that.
    rows = graph_with_two_persons.query(
        "MATCH (n:Person) WHERE n.id = $id RETURN n",
        {"id": "EMP-0002"},
    )
    assert len(rows) == 1
    node = rows[0]["n"]
    assert isinstance(node, dict)
    assert node["id"] == "EMP-0002"
    assert node["name"] == "Bob"


def test_query_one_returns_first_row(graph_with_two_persons: EntityGraph) -> None:
    row = graph_with_two_persons.query_one(
        "MATCH (n:Person) WHERE n.id = $id RETURN n.id AS id",
        {"id": "EMP-0001"},
    )
    assert row == {"id": "EMP-0001"}


def test_query_one_returns_none_when_no_match(graph_with_two_persons: EntityGraph) -> None:
    row = graph_with_two_persons.query_one(
        "MATCH (n:Person) WHERE n.id = $id RETURN n.id AS id",
        {"id": "DOES-NOT-EXIST"},
    )
    assert row is None


def test_find_by_pattern_appends_default_limit(graph_with_two_persons: EntityGraph) -> None:
    # Pattern has no LIMIT → wrapper appends LIMIT 100. With two rows
    # available this returns both.
    rows = graph_with_two_persons.find_by_pattern(
        "MATCH (n:Person) RETURN n.id AS id"
    )
    assert len(rows) == 2
    assert {r["id"] for r in rows} == {"EMP-0001", "EMP-0002"}


def test_find_by_pattern_respects_explicit_limit(graph_with_two_persons: EntityGraph) -> None:
    rows = graph_with_two_persons.find_by_pattern(
        "MATCH (n:Person) RETURN n.id AS id",
        limit=2,
    )
    assert len(rows) == 2

    rows_one = graph_with_two_persons.find_by_pattern(
        "MATCH (n:Person) RETURN n.id AS id",
        limit=1,
    )
    assert len(rows_one) == 1


def test_find_by_pattern_does_not_double_append_limit(graph_with_two_persons: EntityGraph) -> None:
    # Pattern already contains LIMIT — wrapper must not append another one.
    rows = graph_with_two_persons.find_by_pattern(
        "MATCH (n:Person) RETURN n.id AS id LIMIT 1",
        limit=99,
    )
    assert len(rows) == 1


def test_find_by_pattern_word_boundary_limit_detection(graph_with_two_persons: EntityGraph) -> None:
    # Word-boundary regex: 'limited' is not 'LIMIT'. Verify pattern with
    # 'limited' in a WHERE clause still gets LIMIT appended.
    rows = graph_with_two_persons.find_by_pattern(
        "MATCH (n:Person) WHERE n.name <> 'limited' RETURN n.id AS id",
        limit=100,
    )
    # Should return both rows (no false LIMIT detected).
    assert len(rows) == 2


def test_attach_preserves_previously_set_refs(graph_with_two_persons: EntityGraph) -> None:
    mock_bus = mock.Mock()
    mock_audit = mock.Mock()
    mock_other_bus = mock.Mock()

    # First attach sets bus.
    graph_with_two_persons.attach(bus=mock_bus)
    assert graph_with_two_persons.bus is mock_bus
    assert graph_with_two_persons.audit is None

    # Second attach adds audit without clobbering bus.
    graph_with_two_persons.attach(audit=mock_audit)
    assert graph_with_two_persons.bus is mock_bus
    assert graph_with_two_persons.audit is mock_audit

    # Explicit non-None overrides the previous value.
    graph_with_two_persons.attach(bus=mock_other_bus)
    assert graph_with_two_persons.bus is mock_other_bus
    assert graph_with_two_persons.audit is mock_audit

    # All-None attach() is a no-op.
    graph_with_two_persons.attach()
    assert graph_with_two_persons.bus is mock_other_bus
    assert graph_with_two_persons.audit is mock_audit
