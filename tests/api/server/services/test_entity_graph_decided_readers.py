"""Regression: readers must aggregate every DECIDED_<KIND> shard.

Phase 1.5 sharded the writer's ``DECIDED_ON`` rel into per-target-kind
tables (``DECIDED_PERSON``, ``DECIDED_MONEY``, …). Two reader paths still
hard-coded ``[:DECIDED_ON]`` post-shard and silently went blank:

  1. ``query_precedents`` MCP tool — generic precedent lookup.
  2. ``/api/entities/_pulse`` — KnowledgePulse activity strip's
     ``links_per_min`` aggregate.

This module pins the post-fix behaviour: write a Decision linked to a
``Money`` target via :meth:`EntityGraph.record_decision`, then assert
both readers see it.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from api.server.mcp_tools.query_precedents import make_query_precedents_tool
from api.server.services.entity_graph import EntityGraph, EntityWrite


@pytest.fixture
def graph(tmp_path: Path) -> EntityGraph:
    return EntityGraph(tmp_path / "g.kuzu")


def test_query_precedents_finds_decision_via_sharded_decided_rel(
    graph: EntityGraph,
) -> None:
    # Seed a non-Person target so the writer routes through DECIDED_MONEY,
    # not the legacy DECIDED_ON table — exactly the case the old reader
    # missed.
    money_id = "MONEY-INV-0001"
    graph.upsert(EntityWrite(kind="Money", id=money_id, attrs={"amount": 1234}))

    decision_id = graph.record_decision(
        workflow_id="WF-AP-1",
        phase="approve",
        persona_role="ap_clerk",
        verdict="approved",
        reason="ok",
        decided_at=datetime(2026, 5, 10, 9, 0),
        source_event="evt-1",
        attributes={},
        decided_on=(money_id,),
    )

    # Sanity: writer landed the rel in DECIDED_MONEY, not DECIDED_ON.
    in_money = graph.query(
        "MATCH (d:Decision)-[:DECIDED_MONEY]->(m:Money) "
        "WHERE d.id = $id RETURN m.id AS mid",
        {"id": decision_id},
    )
    assert in_money and in_money[0]["mid"] == money_id

    tool = make_query_precedents_tool(graph)
    rows = tool("ap_clerk", money_id, limit=10)
    ids = [r["d"]["id"] for r in rows]
    assert decision_id in ids, (
        f"generic precedent query missed sharded DECIDED_MONEY rel; "
        f"got rows={rows!r}"
    )


def test_pulse_links_rate_includes_sharded_decided_shards(
    graph: EntityGraph,
    monkeypatch,
) -> None:
    """The ``/_pulse`` ``links_per_min`` aggregate must sum activity across
    every DECIDED_<KIND> shard, not just the legacy DECIDED_ON name.
    """
    money_id = "MONEY-INV-PULSE"
    graph.upsert(EntityWrite(kind="Money", id=money_id, attrs={"amount": 50}))

    # record_decision → link() → _record_activity("DECIDED_MONEY")
    graph.record_decision(
        workflow_id="WF-PULSE-1",
        phase="approve",
        persona_role="ap_clerk",
        verdict="approved",
        reason="ok",
        decided_at=datetime(2026, 5, 10, 9, 0),
        source_event="evt-pulse",
        attributes={},
        decided_on=(money_id,),
    )

    # Stand up a minimal app_state pointing at our tmp graph and call the
    # _pulse handler directly (avoids spinning up FastAPI test client +
    # bootstrapping the full app for one route).
    from api.server.routes import entities as entities_route

    class _FakeAppState:
        entities = graph

    monkeypatch.setattr(entities_route, "app_state", _FakeAppState())

    import asyncio

    payload = asyncio.run(entities_route.entities_pulse())

    assert payload["links_per_min"] > 0, (
        "pulse links_per_min did not include the DECIDED_MONEY rel — "
        f"payload={payload!r}"
    )
