"""Schema-bootstrap test for ``EntityGraph`` (TASK-003).

Covers REQ-001: the constructor opens a Kuzu database and idempotently
creates the eight Plane 1 node tables and ten rel tables.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from api.server.services.entity_graph import EntityGraph, EntityWrite


EXPECTED_NODE_TABLES = {
    "Person",
    "Organisation",
    "Asset",
    "Money",
    "Decision",
    "Place",
    "Period",
    "Workflow",
    # pitch-e1: agency-domain kinds
    "Brand",
    "Campaign",
    "Pitch",
    "MediaPlan",
    "Subsidiary",
    # Phase 2: accounts substrate
    "Account",
    "CostCentre",
    "Insight",
}

EXPECTED_REL_TABLES = {
    "EMPLOYED_BY",
    "MANAGES",
    "OWNS",
    "TRANSACTS",
    "BELONGS_TO",
    "LOCATED_IN",
    "DECIDED_ON",
    "DECIDED_PERSON",
    "DECIDED_MONEY",
    "DECIDED_ASSET",
    "DECIDED_ORG",
    "DECIDED_PERIOD",
    "DECIDED_PLACE",
    "PRECEDENT_OF",
    "TOUCHED",
    "SUB_WORKFLOW_OF",
    # Phase 4.5: workflow-period linkage
    "WORKFLOW_IN_PERIOD",
    # pitch-e1: agency-domain rels
    "BRAND_OF",
    "CAMPAIGN_FOR",
    "EXECUTED_BY",
    "SUPPLIED_BY",
    "PITCH_FOR",
    "RESULTED_IN",
    "PART_OF",
    "DECIDED_BRAND",
    "DECIDED_CAMPAIGN",
    "DECIDED_PITCH",
    "DECIDED_MEDIAPLAN",
    "DECIDED_SUBSIDIARY",
    # Phase 2/3: accounts substrate rels
    "PAYS",
    "OWED_BY",
    "BOOKED_AGAINST",
    "BOOKED_AGAINST_CC",
    "COSTED_TO",
    "COSTED_TO_BRAND",
    # Task 7: generic workflow-recovery topology (industry-neutral)
    "TRIGGERED_BY",
    "AFFECTS_ASSET",
    "RELATED_ASSET",
    "SUPPLIED_BY_ASSET",
    "ISSUED_COMMAND",
    "EVALUATED_BY",
    "APPROVED_BY",
    "RESOLVED_OBJECTIVE",
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


def test_insight_upsert_roundtrip(tmp_path: Path) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    g.upsert(EntityWrite(
        kind="Insight",
        id="INSIGHT-test-1",
        attrs={
            "role": "test",
            "scope": "test_scope",
            "decided_at": datetime.utcnow(),
            "headline": "hello",
            "body": "world",
            "kpis": "{}",
            "proposed_actions": "[]",
            "fingerprint": "abc123",
            "attributes": "{}",
        },
        source_workflows=(),
    ))
    rows = g.query("MATCH (i:Insight) RETURN i.id AS id, i.headline AS h")
    assert rows == [{"id": "INSIGHT-test-1", "h": "hello"}]
