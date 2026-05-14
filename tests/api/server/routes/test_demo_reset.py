"""Tests for POST /api/demo/trigger/reset (v1.2 demo re-run cleanup)."""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.server.services.entity_graph import EntityGraph, EntityWrite
from api.server.state import app_state


HDRS = {"x-actor-role": "executive"}


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("INSIGHT_LOOP_ENABLED", "0")
    g = EntityGraph(tmp_path / "ig.kuzu")
    monkeypatch.setattr(app_state, "entities", g)
    try:
        from api.server.main import app
        yield TestClient(app), g
    finally:
        g.close()


def _seed_money(g: EntityGraph, mid: str, amount: float = 100.0) -> None:
    g.upsert(EntityWrite(
        kind="Money",
        id=mid,
        attrs={
            "kind": "po",
            "amount": float(amount),
            "currency": "GBP",
            "attributes": "{}",
        },
        source_workflows=(),
    ))


def _seed_workflow(g: EntityGraph, wid: str) -> None:
    g.upsert(EntityWrite(
        kind="Workflow",
        id=wid,
        attrs={
            "workflow_type": "ap-invoice",
            "status": "running",
            "attributes": "{}",
        },
        source_workflows=(),
    ))


def _seed_insight(g: EntityGraph, iid: str) -> None:
    g.upsert(EntityWrite(
        kind="Insight",
        id=iid,
        attrs={
            "role": "cfo",
            "scope": "Finance",
            "decided_at": datetime.utcnow(),
            "headline": f"hl-{iid}",
            "body": "b",
            "kpis": json.dumps({}),
            "proposed_actions": json.dumps([]),
            "fingerprint": f"fp-{iid}",
            "attributes": "{}",
        },
        source_workflows=(),
    ))


def _seed_person(
    g: EntityGraph, pid: str, *, employed_to: date | None
) -> None:
    attrs: dict = {
        "name": pid,
        "department": "Tech",
        "attributes": "{}",
    }
    if employed_to is not None:
        attrs["employed_to"] = employed_to
    g.upsert(EntityWrite(
        kind="Person",
        id=pid,
        attrs=attrs,
        source_workflows=(),
    ))


def _money_ids(g: EntityGraph) -> set[str]:
    rows = g.query("MATCH (m:Money) RETURN m.id AS id")
    return {str(r["id"]) for r in rows}


def _workflow_ids(g: EntityGraph) -> set[str]:
    rows = g.query("MATCH (w:Workflow) RETURN w.id AS id")
    return {str(r["id"]) for r in rows}


def _decision_count(g: EntityGraph) -> int:
    rows = g.query("MATCH (d:Decision) RETURN count(d) AS n")
    return int(rows[0]["n"]) if rows else 0


def _insight_count(g: EntityGraph) -> int:
    rows = g.query("MATCH (i:Insight) RETURN count(i) AS n")
    return int(rows[0]["n"]) if rows else 0


def test_reset_removes_demo_money(client):
    c, g = client
    for i in range(3):
        _seed_money(g, f"MONEY-DEMO-aurora-{i}")
    for i in range(3):
        _seed_money(g, f"MONEY-{i}")

    r = c.post("/api/demo/trigger/reset", headers=HDRS)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rows_deleted"]["money"] == 3
    assert body["kept_seed"] is True

    remaining = _money_ids(g)
    assert remaining == {"MONEY-0", "MONEY-1", "MONEY-2"}


def test_reset_removes_demo_workflows(client):
    c, g = client
    for i in range(2):
        _seed_workflow(g, f"WF-AP-DEMO-{i}")
    _seed_workflow(g, "WF-NORMAL-1")

    r = c.post("/api/demo/trigger/reset", headers=HDRS)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rows_deleted"]["workflows"] == 2

    assert _workflow_ids(g) == {"WF-NORMAL-1"}


def test_reset_removes_demo_decisions(client):
    c, g = client
    for i in range(2):
        g.record_decision(
            workflow_id=f"WF-AP-DEMO-{i}",
            phase="ap_clerk_signoff",
            persona_role="ap_clerk",
            verdict="escalate",
            reason="demo",
            decided_at=datetime.utcnow(),
            source_event="demo.in_flight_invoice",
            attributes={},
            decided_on=(),
        )
    g.record_decision(
        workflow_id="WF-NORMAL-1",
        phase="cfo_signoff",
        persona_role="cfo",
        verdict="approve",
        reason="ok",
        decided_at=datetime.utcnow(),
        source_event="workflow.gate.completed",
        attributes={},
        decided_on=(),
    )

    assert _decision_count(g) == 3

    r = c.post("/api/demo/trigger/reset", headers=HDRS)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rows_deleted"]["decisions"] == 2

    assert _decision_count(g) == 1


def test_reset_removes_insights_when_keep_seed_false(client):
    c, g = client
    for i in range(5):
        _seed_insight(g, f"INSIGHT-{i}")
    assert _insight_count(g) == 5

    r = c.post(
        "/api/demo/trigger/reset?keep_seed=false", headers=HDRS,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rows_deleted"]["insights"] == 5
    assert body["kept_seed"] is False

    assert _insight_count(g) == 0


def test_reset_keeps_insights_by_default(client):
    c, g = client
    for i in range(5):
        _seed_insight(g, f"INSIGHT-{i}")
    assert _insight_count(g) == 5

    r = c.post("/api/demo/trigger/reset", headers=HDRS)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rows_deleted"]["insights"] == 0

    assert _insight_count(g) == 5


def test_reset_unattrites_recent_persons(client):
    c, g = client
    today = date.today()
    for i in range(3):
        _seed_person(g, f"PERSON-RECENT-{i}", employed_to=today)
    for i in range(2):
        _seed_person(g, f"PERSON-OLD-{i}", employed_to=date(2025, 1, 1))

    r = c.post("/api/demo/trigger/reset", headers=HDRS)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rows_deleted"]["persons_unattrited"] == 3

    rows = g.query(
        "MATCH (p:Person) RETURN p.id AS id, p.employed_to AS et"
    )
    by_id = {str(r["id"]): r["et"] for r in rows}
    for i in range(3):
        assert by_id[f"PERSON-RECENT-{i}"] is None
    for i in range(2):
        assert by_id[f"PERSON-OLD-{i}"] == date(2025, 1, 1)
