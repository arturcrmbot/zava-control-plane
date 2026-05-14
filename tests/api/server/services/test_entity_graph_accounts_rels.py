"""Phase 2 — Money↔Account / Money↔Org / Money↔CostCentre rel tables."""
from __future__ import annotations

from pathlib import Path

import pytest

from api.server.services.entity_graph import EntityGraph, EntityWrite, RelWrite


@pytest.fixture
def graph(tmp_path: Path) -> EntityGraph:
    g = EntityGraph(tmp_path / "g.kuzu")
    g.upsert(EntityWrite(
        kind="Money", id="MONEY-INV-1",
        attrs={"kind": "invoice", "amount": 1000.0, "currency": "GBP"},
    ))
    g.upsert(EntityWrite(
        kind="Organisation", id="ORG-vendor-globex",
        attrs={"name": "Globex", "kind": "vendor"},
    ))
    g.upsert(EntityWrite(
        kind="Account", id="ACC-6010",
        attrs={"code": "6010", "name": "External production", "type": "expense"},
    ))
    g.upsert(EntityWrite(
        kind="CostCentre", id="CC-zava-creative",
        attrs={"name": "Zava Creative", "subsidiary_id": "ORG-zava-creative"},
    ))
    return g


def test_pays_money_to_org(graph: EntityGraph):
    graph.link("MONEY-INV-1", "PAYS", "ORG-vendor-globex")
    rows = graph.query(
        "MATCH (m:Money)-[:PAYS]->(o:Organisation) "
        "RETURN m.id AS m, o.id AS o"
    )
    assert rows == [{"m": "MONEY-INV-1", "o": "ORG-vendor-globex"}]


def test_booked_against_account(graph: EntityGraph):
    graph.link("MONEY-INV-1", "BOOKED_AGAINST", "ACC-6010")
    assert graph.query(
        "MATCH (m:Money)-[:BOOKED_AGAINST]->(a:Account) RETURN count(*) AS c"
    )[0]["c"] == 1


def test_costed_to_costcentre(graph: EntityGraph):
    graph.link("MONEY-INV-1", "COSTED_TO", "CC-zava-creative")
    # Plan §2.2 had `(c:CostCentre) RETURN count(*) AS c` — Kuzu 0.6.1 rejects
    # the alias collision ("Cannot evaluate expression with type
    # AGGREGATE_FUNCTION"). Renamed the node alias to `cc`; semantics unchanged.
    assert graph.query(
        "MATCH (m:Money)-[:COSTED_TO]->(cc:CostCentre) RETURN count(*) AS c"
    )[0]["c"] == 1
