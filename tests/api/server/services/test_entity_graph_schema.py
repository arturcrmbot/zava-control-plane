"""Schema-bootstrap test for ``EntityGraph`` (TASK-003).

Covers REQ-001: the constructor opens a Kuzu database and idempotently
creates the eight Plane 1 node tables and ten rel tables.
"""
from __future__ import annotations

from pathlib import Path

from api.server.services.entity_graph import EntityGraph


EXPECTED_NODE_TABLES = {
    "Person",
    "Organisation",
    "Asset",
    "Money",
    "Decision",
    "Place",
    "Period",
    "Workflow",
}

EXPECTED_REL_TABLES = {
    "EMPLOYED_BY",
    "MANAGES",
    "OWNS",
    "TRANSACTS",
    "BELONGS_TO",
    "LOCATED_IN",
    "DECIDED_ON",
    "PRECEDENT_OF",
    "TOUCHED",
    "SUB_WORKFLOW_OF",
}


def _list_tables(graph: EntityGraph) -> dict[str, set[str]]:
    """Return ``{"NODE": {…}, "REL": {…}}`` from ``CALL show_tables()``."""
    result = graph.conn.execute("CALL show_tables() RETURN *")
    columns = result.get_column_names()
    name_idx = columns.index("name")
    type_idx = columns.index("type")
    nodes: set[str] = set()
    rels: set[str] = set()
    while result.has_next():
        row = result.get_next()
        if row[type_idx] == "NODE":
            nodes.add(row[name_idx])
        elif row[type_idx] == "REL":
            rels.add(row[name_idx])
    return {"NODE": nodes, "REL": rels}


def test_constructor_creates_database_file(tmp_path: Path) -> None:
    db_path = tmp_path / "g.kuzu"
    assert not db_path.exists()
    graph = EntityGraph(db_path)
    # Kuzu materialises a small directory tree (or file) at db_path on first
    # write. Either way the path now exists.
    assert db_path.exists()
    # Sanity: the schema actually landed.
    tables = _list_tables(graph)
    assert tables["NODE"] == EXPECTED_NODE_TABLES
    assert tables["REL"] == EXPECTED_REL_TABLES


def test_reconstructing_on_same_path_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "g.kuzu"
    first = EntityGraph(db_path)
    # Close the connection/db handles before reopening — Kuzu permits a
    # single writer per database directory.
    first.close()
    second = EntityGraph(db_path)  # must not raise
    tables = _list_tables(second)
    assert tables["NODE"] == EXPECTED_NODE_TABLES
    assert tables["REL"] == EXPECTED_REL_TABLES


def test_close_is_idempotent(tmp_path: Path) -> None:
    graph = EntityGraph(tmp_path / "g.kuzu")
    # Multiple closes should not raise.
    graph.close()
    graph.close()  # should be a no-op


def test_show_tables_lists_exact_expected_tables(tmp_path: Path) -> None:
    graph = EntityGraph(tmp_path / "g.kuzu")
    tables = _list_tables(graph)
    # Exact equality — no extra tables, no missing tables.
    assert tables["NODE"] == EXPECTED_NODE_TABLES, (
        f"unexpected node tables: extra={tables['NODE'] - EXPECTED_NODE_TABLES}, "
        f"missing={EXPECTED_NODE_TABLES - tables['NODE']}"
    )
    assert tables["REL"] == EXPECTED_REL_TABLES, (
        f"unexpected rel tables: extra={tables['REL'] - EXPECTED_REL_TABLES}, "
        f"missing={EXPECTED_REL_TABLES - tables['REL']}"
    )
