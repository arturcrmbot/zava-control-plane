"""Seed a tiny accounts-substrate fixture into an EntityGraph.

Designed for the ``/api/accounts/summary`` route tests — keeps the data
set tiny so each test materialises in milliseconds (no full DataPack
run).

Layout: 2 GL accounts (one expense, one revenue), 2 cost centres
(matched 1:1 with subsidiaries), 2 Money rows (one invoice booked to
the expense account + costed to a CC; one commission booked to the
revenue account + costed to a different CC), 1 Period the money
belongs to.

Period.starts / Period.ends are TIMESTAMP columns in the Kuzu schema
(see ``_NODE_TABLES`` in ``api/server/services/entity_graph.py``); we
deliberately omit them here so ``_build_set_clauses`` doesn't try to
write a STRING into a TIMESTAMP — the route tests only need the Period
node to exist and carry a ``label`` for the group-by-period assertion.
"""
from __future__ import annotations

from api.server.services.entity_graph import EntityGraph, EntityWrite


def seed_account_demo(graph: EntityGraph) -> None:
    graph.upsert(EntityWrite(
        kind="Period", id="PER-2026-Q1",
        attrs={"label": "FY26 Q1", "kind": "quarter"},
    ))
    graph.upsert(EntityWrite(
        kind="Organisation", id="ORG-zava-creative",
        attrs={"name": "Zava Creative", "kind": "subsidiary"},
    ))
    graph.upsert(EntityWrite(
        kind="Organisation", id="ORG-zava-media",
        attrs={"name": "Zava Media", "kind": "subsidiary"},
    ))
    graph.upsert(EntityWrite(
        kind="CostCentre", id="CC-zava-creative",
        attrs={"name": "Zava Creative", "subsidiary_id": "ORG-zava-creative",
               "owner_role": "regional_account_lead"},
    ))
    graph.upsert(EntityWrite(
        kind="CostCentre", id="CC-zava-media",
        attrs={"name": "Zava Media", "subsidiary_id": "ORG-zava-media",
               "owner_role": "regional_account_lead"},
    ))
    graph.upsert(EntityWrite(
        kind="Account", id="ACC-6010",
        attrs={"code": "6010", "name": "Production cost — external",
               "type": "expense", "currency": "GBP"},
    ))
    graph.upsert(EntityWrite(
        kind="Account", id="ACC-4100",
        attrs={"code": "4100", "name": "Revenue — media commission",
               "type": "revenue", "currency": "GBP"},
    ))
    graph.upsert(EntityWrite(
        kind="Money", id="MONEY-INV-1",
        attrs={"kind": "invoice", "amount": 1000.0, "currency": "GBP",
               "period": "PER-2026-Q1"},
    ))
    graph.upsert(EntityWrite(
        kind="Money", id="MONEY-COM-1",
        attrs={"kind": "commission", "amount": 5000.0, "currency": "GBP",
               "period": "PER-2026-Q1"},
    ))
    graph.link("MONEY-INV-1", "BOOKED_AGAINST", "ACC-6010")
    graph.link("MONEY-INV-1", "COSTED_TO", "CC-zava-creative")
    graph.link("MONEY-INV-1", "BELONGS_TO", "PER-2026-Q1")
    graph.link("MONEY-COM-1", "BOOKED_AGAINST", "ACC-4100")
    graph.link("MONEY-COM-1", "COSTED_TO", "CC-zava-media")
    graph.link("MONEY-COM-1", "BELONGS_TO", "PER-2026-Q1")
    graph.upsert(EntityWrite(
        kind="Brand", id="BRAND-aurora",
        attrs={"name": "Aurora", "market_segment": "fmcg",
               "annual_budget_gbp": 1000.0, "budget_remaining_gbp": 1000.0},
    ))
    graph.link("BRAND-aurora", "BRAND_OF", "ORG-zava-creative")
    graph.link("MONEY-INV-1", "COSTED_TO_BRAND", "BRAND-aurora")
