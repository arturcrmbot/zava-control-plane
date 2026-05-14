"""Phase 4 Task 4.2: every rel carries a decided_at timestamp.

Verifies the link() default-stamp behaviour and the schema column
presence — caller can pass an explicit decided_at, or get one stamped
automatically.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from api.server.services.entity_graph import EntityGraph, EntityWrite


@pytest.fixture
def graph(tmp_path: Path) -> EntityGraph:
    g = EntityGraph(tmp_path / "g.kuzu")
    g.upsert(EntityWrite(kind="Person", id="P-1", attrs={"name": "Alice"}))
    g.upsert(EntityWrite(kind="Asset", id="A-1", attrs={"kind": "laptop"}))
    return g


def test_link_default_stamps_decided_at(graph: EntityGraph):
    before = datetime.utcnow()
    graph.link("P-1", "OWNS", "A-1")
    after = datetime.utcnow()
    rows = graph.query("MATCH (p:Person)-[r:OWNS]->(a:Asset) RETURN r.decided_at AS ts")
    assert len(rows) == 1
    ts = rows[0]["ts"]
    assert ts is not None
    # ts is a kuzu TIMESTAMP — should round-trip to datetime
    assert before <= ts <= after, f"expected {before} <= {ts} <= {after}"


def test_link_explicit_decided_at_preserved(graph: EntityGraph):
    explicit = datetime(2026, 1, 1, 12, 0, 0)
    graph.link("P-1", "OWNS", "A-1", decided_at=explicit)
    rows = graph.query("MATCH (p:Person)-[r:OWNS]->(a:Asset) RETURN r.decided_at AS ts")
    assert rows[0]["ts"] == explicit


def test_record_decision_promotes_known_keys_to_columns(graph: EntityGraph):
    """Phase 4 Task 4.3: known JSON attribute keys land on typed columns."""
    import json

    graph.record_decision(
        workflow_id="WF-001",
        phase="ap_clerk_signoff",
        persona_role="ap_clerk",
        verdict="escalate",
        reason="over delegation cap",
        decided_at=datetime(2026, 5, 12, 10, 0, 0),
        source_event="workflow.hitl.requested",
        attributes={
            "amount_gbp": 12000.0,
            "currency_pair": "GBP/USD",
            "vendor_id": "ORG-vendor-globex",
            "irrelevant_extra": "still goes into JSON blob",
        },
        decided_on=(),
    )
    rows = graph.query(
        "MATCH (d:Decision) RETURN d.amount_gbp AS amt, d.vendor_id AS v, "
        "d.currency_pair AS cp, d.notional_gbp AS notional, "
        "d.client_brand AS brand, d.attributes AS j"
    )
    assert len(rows) == 1
    assert rows[0]["amt"] == 12000.0
    assert rows[0]["v"] == "ORG-vendor-globex"
    assert rows[0]["cp"] == "GBP/USD"
    # Unset typed columns stay NULL.
    assert rows[0]["notional"] is None
    assert rows[0]["brand"] is None
    # Untyped key still in JSON blob alongside the promoted ones.
    j = json.loads(rows[0]["j"])
    assert j["irrelevant_extra"] == "still goes into JSON blob"
    assert j["amount_gbp"] == 12000.0


def test_record_decision_empty_typed_keys_skipped(graph: EntityGraph):
    """Empty-string / None typed values are skipped (Kuzu strict-types)."""
    graph.record_decision(
        workflow_id="WF-002",
        phase="cfo_signoff",
        persona_role="cfo",
        verdict="approve",
        reason="ok",
        decided_at=datetime(2026, 5, 13, 9, 0, 0),
        source_event="workflow.signoff.approved",
        attributes={"vendor_id": "", "amount_gbp": None, "client_brand": "Zava"},
        decided_on=(),
    )
    rows = graph.query(
        "MATCH (d:Decision {workflow_id: 'WF-002'}) "
        "RETURN d.vendor_id AS v, d.amount_gbp AS amt, d.client_brand AS b"
    )
    assert rows[0]["v"] is None
    assert rows[0]["amt"] is None
    assert rows[0]["b"] == "Zava"
