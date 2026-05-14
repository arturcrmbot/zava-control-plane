"""Phase 2 — Account / CostCentre node tables."""
from __future__ import annotations

from pathlib import Path

import pytest

from api.server.services.entity_graph import EntityGraph, EntityWrite


@pytest.fixture
def graph(tmp_path: Path) -> EntityGraph:
    return EntityGraph(tmp_path / "g.kuzu")


def test_account_node_writeable(graph: EntityGraph):
    graph.upsert(EntityWrite(
        kind="Account", id="ACC-6010",
        attrs={
            "code": "6010",
            "name": "Production cost — external",
            "type": "expense",
            "currency": "GBP",
        },
    ))
    rows = graph.query("MATCH (a:Account {id: 'ACC-6010'}) RETURN a.name AS n")
    assert rows[0]["n"] == "Production cost — external"


def test_costcentre_node_writeable(graph: EntityGraph):
    graph.upsert(EntityWrite(
        kind="CostCentre", id="CC-zava-creative",
        attrs={
            "name": "Zava Creative",
            "subsidiary_id": "ORG-zava-creative",
            "owner_role": "regional_account_lead",
        },
    ))
    rows = graph.query(
        "MATCH (c:CostCentre {id: 'CC-zava-creative'}) RETURN c.name AS n"
    )
    assert rows[0]["n"] == "Zava Creative"
