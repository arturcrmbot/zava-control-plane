"""Backfill: every Workflow gets a WORKFLOW_IN_PERIOD edge to the Period
whose [starts, ends] range contains its started_at."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from api.server.services.entity_graph import EntityGraph, EntityWrite
from scripts.backfill_workflow_periods import backfill


@pytest.fixture
def graph(tmp_path: Path) -> EntityGraph:
    g = EntityGraph(tmp_path / "g.kuzu")
    g.upsert(EntityWrite(
        kind="Period", id="PER-2026-Q1",
        attrs={
            "kind": "quarter", "label": "FY26 Q1",
            "starts": datetime(2026, 1, 1, 0, 0, 0),
            "ends": datetime(2026, 3, 31, 23, 59, 59),
        },
    ))
    g.upsert(EntityWrite(
        kind="Period", id="PER-2026-Q2",
        attrs={
            "kind": "quarter", "label": "FY26 Q2",
            "starts": datetime(2026, 4, 1, 0, 0, 0),
            "ends": datetime(2026, 6, 30, 23, 59, 59),
        },
    ))
    g.upsert(EntityWrite(
        kind="Workflow", id="WF-INSIDE-Q1",
        attrs={"workflow_type": "ap-invoice", "status": "completed",
               "started_at": datetime(2026, 2, 15, 12, 0, 0)},
    ))
    g.upsert(EntityWrite(
        kind="Workflow", id="WF-INSIDE-Q2",
        attrs={"workflow_type": "ap-invoice", "status": "completed",
               "started_at": datetime(2026, 5, 5, 12, 0, 0)},
    ))
    return g


def test_backfill_links_workflows_to_periods(graph: EntityGraph):
    summary = backfill(graph)
    assert summary["workflow_in_period"] == 2
    rows = graph.query(
        "MATCH (w:Workflow)-[:WORKFLOW_IN_PERIOD]->(p:Period) "
        "RETURN w.id AS wid, p.id AS pid ORDER BY wid"
    )
    assert {"wid": "WF-INSIDE-Q1", "pid": "PER-2026-Q1"} in rows
    assert {"wid": "WF-INSIDE-Q2", "pid": "PER-2026-Q2"} in rows


def test_backfill_idempotent(graph: EntityGraph):
    backfill(graph)
    backfill(graph)
    n = graph.query("MATCH ()-[r:WORKFLOW_IN_PERIOD]->() RETURN count(*) AS c")[0]["c"]
    assert n == 2
