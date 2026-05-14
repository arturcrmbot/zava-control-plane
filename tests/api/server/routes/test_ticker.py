"""Phase D1 of autonomous-domain-insights v1.1: live ticker route."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.server.services.entity_graph import EntityGraph, EntityWrite
from api.server.state import app_state


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    """Fresh EntityGraph + TestClient with the ticker router mounted.

    Mirrors the test_insights.py fixture pattern: monkeypatch
    ``app_state.entities`` at a tmp Kuzu path so each test gets an
    isolated single-writer DB.
    """
    monkeypatch.setenv("INSIGHT_LOOP_ENABLED", "0")
    g = EntityGraph(tmp_path / "ig.kuzu")
    monkeypatch.setattr(app_state, "entities", g)
    try:
        from api.server.main import app
        yield TestClient(app), g
    finally:
        g.close()


def _seed_decision(g: EntityGraph, *, suffix: str, when: datetime) -> str:
    return g.record_decision(
        workflow_id=f"WF-TICK-{suffix}",
        phase="execute",
        persona_role="ap_clerk",
        verdict="approved",
        reason=f"reason-{suffix}",
        decided_at=when,
        source_event="test",
        attributes={},
    )


def _seed_insight(g: EntityGraph, *, suffix: str, role: str, when: datetime) -> None:
    g.upsert(EntityWrite(
        kind="Insight",
        id=f"INSIGHT-{suffix}",
        attrs={
            "role": role,
            "scope": "Test",
            "decided_at": when,
            "headline": f"headline-{suffix}",
            "body": "",
            "kpis": "{}",
            "proposed_actions": "[]",
            "fingerprint": f"fp-{suffix}",
            "attributes": "{}",
        },
        source_workflows=(),
    ))


def test_recent_returns_decisions_and_insights(client):
    tc, g = client
    base = datetime(2026, 5, 12, 10, 0, 0)
    _seed_decision(g, suffix="a", when=base)
    _seed_decision(g, suffix="b", when=base + timedelta(seconds=10))
    _seed_insight(g, suffix="c", role="cfo", when=base + timedelta(seconds=20))

    r = tc.get("/api/ticker/recent")
    assert r.status_code == 200
    body = r.json()
    items = body["ticker"]
    assert len(items) == 3

    kinds = [it["kind"] for it in items]
    # Newest first; insight at +20s wins, then decision at +10s, then +0s.
    assert kinds == ["Insight", "Decision", "Decision"]
    # decided_at strictly descending.
    timestamps = [it["decided_at"] for it in items]
    assert timestamps == sorted(timestamps, reverse=True)

    insight = items[0]
    assert insight["role"] == "cfo"
    assert insight["headline"] == "headline-c"
    assert insight["fingerprint"] == "fp-c"

    decision = items[1]
    assert decision["persona_role"] == "ap_clerk"
    assert decision["verdict"] == "approved"
    assert decision["workflow_id"] == "WF-TICK-b"
    assert "decided_on" in decision  # bare list when no rels were written


def test_recent_respects_limit(client):
    tc, g = client
    base = datetime(2026, 5, 12, 10, 0, 0)
    for i in range(5):
        _seed_decision(g, suffix=str(i), when=base + timedelta(seconds=i))

    r = tc.get("/api/ticker/recent?limit=2")
    assert r.status_code == 200
    items = r.json()["ticker"]
    assert len(items) == 2
    # Newest two: workflow ids 4 and 3.
    assert [it["workflow_id"] for it in items] == ["WF-TICK-4", "WF-TICK-3"]


def test_recent_empty_graph(client):
    tc, _ = client
    r = tc.get("/api/ticker/recent")
    assert r.status_code == 200
    assert r.json() == {"ticker": []}
