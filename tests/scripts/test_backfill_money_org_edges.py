"""Backfill: every Money row whose attributes JSON contains vendor_id or
client_id should get a PAYS / OWED_BY edge to that Organisation."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from api.server.services.entity_graph import EntityGraph, EntityWrite
from scripts.backfill_money_org_edges import backfill


@pytest.fixture
def graph(tmp_path: Path) -> EntityGraph:
    g = EntityGraph(tmp_path / "g.kuzu")
    g.upsert(EntityWrite(
        kind="Organisation", id="ORG-vendor-globex",
        attrs={"name": "Globex", "kind": "vendor"},
    ))
    g.upsert(EntityWrite(
        kind="Organisation", id="ORG-client-acme",
        attrs={"name": "Acme", "kind": "client"},
    ))
    g.upsert(EntityWrite(
        kind="Money", id="MONEY-INV-1",
        attrs={
            "kind": "invoice", "amount": 1000.0, "currency": "GBP",
            "attributes": json.dumps({"vendor_id": "ORG-vendor-globex"}),
        },
    ))
    g.upsert(EntityWrite(
        kind="Money", id="MONEY-RECHARGE-1",
        attrs={
            "kind": "recharge", "amount": 500.0, "currency": "GBP",
            "attributes": json.dumps({"client_id": "ORG-client-acme"}),
        },
    ))
    return g


def test_backfill_creates_pays_for_invoices(graph: EntityGraph):
    backfill(graph)
    rows = graph.query(
        "MATCH (m:Money)-[:PAYS]->(o:Organisation) "
        "RETURN m.id AS m, o.id AS o"
    )
    assert {"m": "MONEY-INV-1", "o": "ORG-vendor-globex"} in rows


def test_backfill_creates_owed_by_for_recharges(graph: EntityGraph):
    backfill(graph)
    rows = graph.query(
        "MATCH (m:Money)-[:OWED_BY]->(o:Organisation) "
        "RETURN m.id AS m, o.id AS o"
    )
    assert {"m": "MONEY-RECHARGE-1", "o": "ORG-client-acme"} in rows


def test_backfill_idempotent(graph: EntityGraph):
    backfill(graph)
    backfill(graph)
    n = graph.query("MATCH ()-[r:PAYS]->() RETURN count(*) AS c")[0]["c"]
    assert n == 1


def test_backfill_creates_costed_to_brand_for_brand_id(graph: EntityGraph):
    # Add a Brand and a Money row that references it via attributes.brand_id.
    graph.upsert(EntityWrite(
        kind="Brand", id="BRAND-aurora",
        attrs={"name": "Aurora", "market_segment": "fmcg",
               "annual_budget_gbp": 1000.0, "budget_remaining_gbp": 1000.0},
    ))
    graph.upsert(EntityWrite(
        kind="Money", id="MONEY-CAMPAIGN-1",
        attrs={
            "kind": "po", "amount": 500.0, "currency": "GBP",
            "attributes": json.dumps({"brand_id": "BRAND-aurora"}),
        },
    ))
    backfill(graph)
    rows = graph.query(
        "MATCH (m:Money)-[:COSTED_TO_BRAND]->(b:Brand) "
        "RETURN m.id AS m, b.id AS b"
    )
    assert {"m": "MONEY-CAMPAIGN-1", "b": "BRAND-aurora"} in rows
