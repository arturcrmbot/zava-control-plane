"""Tests for POST /api/demo/trigger/full-aurora-arc — v1.2 polish."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.server.services import persona_responder as pr
from api.server.services.entity_graph import EntityGraph, EntityWrite
from api.server.state import app_state


HDRS = {"x-actor-role": "executive"}


def _seed_aurora(g: EntityGraph) -> None:
    """Seed BRAND-aurora well above 85% of FY budget so the CFO summary
    proposes the `freeze-brand-aurora` action on the next tick."""
    g.upsert(EntityWrite(
        kind="Brand",
        id="BRAND-aurora",
        attrs={
            "name": "Aurora",
            "market_segment": "demo",
            "annual_budget_gbp": 100_000.0,
            "budget_remaining_gbp": 10_000.0,
            "attributes": "{}",
        },
        source_workflows=(),
    ))
    g.upsert(EntityWrite(
        kind="Account",
        id="ACC-6010",
        attrs={"code": "6010", "name": "Marketing", "type": "expense", "currency": "GBP"},
        source_workflows=(),
    ))
    g.upsert(EntityWrite(
        kind="Period",
        id="PERIOD-Q1-2026",
        attrs={
            "kind": "quarter",
            "starts": datetime(2026, 1, 1),
            "ends": datetime(2026, 3, 31),
            "label": "Q1 2026",
        },
        source_workflows=(),
    ))
    # 90% spent → above 85% trigger.
    g.upsert(EntityWrite(
        kind="Money",
        id="MONEY-SEED-AURORA",
        attrs={"kind": "po", "amount": 90_000.0, "currency": "GBP", "attributes": "{}"},
        source_workflows=(),
    ))
    g.link("MONEY-SEED-AURORA", "COSTED_TO_BRAND", "BRAND-aurora", posted_at=datetime.utcnow())
    g.link("MONEY-SEED-AURORA", "BOOKED_AGAINST", "ACC-6010", posted_at=datetime.utcnow())
    g.link("MONEY-SEED-AURORA", "BELONGS_TO", "PERIOD-Q1-2026")


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("INSIGHT_LOOP_ENABLED", "0")
    g = EntityGraph(tmp_path / "ig.kuzu")
    _seed_aurora(g)
    monkeypatch.setattr(app_state, "entities", g)
    monkeypatch.setattr(pr, "_lazy_app_graph", lambda: g, raising=False)
    pr.PERSONA_DEFINITIONS = pr._load_personae()
    try:
        from api.server.main import app
        yield TestClient(app), g
    finally:
        g.close()


def test_full_arc_returns_six_phases(client):
    c, _g = client
    r = c.post("/api/demo/trigger/full-aurora-arc", headers=HDRS)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "phases" in body and isinstance(body["phases"], list)
    assert len(body["phases"]) == 6, body
    expected = [
        "overrun", "cfo_observe", "approve",
        "cfo_observe_post", "spawn_invoices", "ceo_synthesise",
    ]
    for ph, name in zip(body["phases"], expected):
        assert ph["phase"] == name, ph
        assert "elapsed_ms" in ph and isinstance(ph["elapsed_ms"], int), ph
    assert "narrative" in body and "Aurora" in body["narrative"]
    assert isinstance(body.get("total_elapsed_ms"), int)


def test_full_arc_records_freeze_decision(client):
    c, g = client
    r = c.post("/api/demo/trigger/full-aurora-arc", headers=HDRS)
    assert r.status_code == 200, r.text
    rows = g.query(
        "MATCH (d:Decision) WHERE d.phase = 'policy_set' AND d.verdict = 'freeze' "
        "RETURN d.id AS id, d.verdict AS verdict, d.phase AS phase"
    )
    assert len(rows) >= 1, f"expected freeze policy_set Decision, got {rows}"


def test_full_arc_records_cascade_decisions(client):
    c, g = client
    r = c.post("/api/demo/trigger/full-aurora-arc?count=3", headers=HDRS)
    assert r.status_code == 200, r.text
    rows = g.query(
        "MATCH (d:Decision)-[:DECIDED_BRAND]->(b:Brand) "
        "WHERE d.persona_role = 'ap_clerk' AND d.verdict = 'escalate' "
        "RETURN d.id AS id, b.id AS brand_id"
    )
    assert len(rows) == 3, f"expected 3 ap_clerk escalate Decisions, got {len(rows)}: {rows}"
    for row in rows:
        assert row.get("brand_id") == "BRAND-aurora", row


def test_full_arc_with_delay_zero_is_fast(client):
    c, _g = client
    r = c.post("/api/demo/trigger/full-aurora-arc?delay_seconds=0", headers=HDRS)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_elapsed_ms"] < 5000, body["total_elapsed_ms"]
