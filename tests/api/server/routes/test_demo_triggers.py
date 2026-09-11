"""Tests for /api/demo/trigger/* — autonomous-domain-insights v1.1 Phase A4."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.server.services.entity_graph import EntityGraph, EntityWrite
from api.server.state import app_state


def _seed_brand(g: EntityGraph, brand_id: str, *, budget: float, spend: float) -> None:
    g.upsert(EntityWrite(
        kind="Brand",
        id=brand_id,
        attrs={
            "name": brand_id.replace("BRAND-", "").title(),
            "market_segment": "demo",
            "annual_budget_gbp": float(budget),
            "budget_remaining_gbp": float(budget - spend),
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
    if spend > 0:
        mid = f"MONEY-SEED-{brand_id}"
        g.upsert(EntityWrite(
            kind="Money",
            id=mid,
            attrs={"kind": "po", "amount": float(spend), "currency": "GBP", "attributes": "{}"},
            source_workflows=(),
        ))
        g.link(mid, "COSTED_TO_BRAND", brand_id)
        g.link(mid, "BOOKED_AGAINST", "ACC-6010")
        g.link(mid, "BELONGS_TO", "PERIOD-Q1-2026")


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


HDRS = {"x-actor-role": "executive"}


def test_brand_overrun_inserts_money_rows(client):
    c, g = client
    # Brand at 50% of a £100k budget = £50k spent, target 0.95 leaves £45k gap.
    _seed_brand(g, "BRAND-test", budget=100_000.0, spend=50_000.0)

    r = c.post(
        "/api/demo/trigger/brand-overrun?brand_id=BRAND-test&target_pct=0.95",
        headers=HDRS,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["brand_id"] == "BRAND-test"
    assert body["before_pct"] == pytest.approx(0.5, rel=1e-3)
    assert body["after_pct"] >= 0.95 - 1e-6
    assert len(body["money_ids"]) == 5
    assert body["gap_filled_gbp"] == pytest.approx(45_000.0, rel=1e-3)

    rows = g.query(
        "MATCH (m:Money)-[:COSTED_TO_BRAND]->(b:Brand) "
        "WHERE b.id = 'BRAND-test' RETURN sum(m.amount) AS s"
    )
    total = float(rows[0]["s"])
    assert total / 100_000.0 >= 0.95 - 1e-6


def test_brand_overrun_no_op_when_already_at_target(client):
    c, g = client
    _seed_brand(g, "BRAND-test", budget=100_000.0, spend=95_000.0)

    r = c.post(
        "/api/demo/trigger/brand-overrun?brand_id=BRAND-test&target_pct=0.95",
        headers=HDRS,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["money_ids"] == []
    assert body["gap_filled_gbp"] == 0.0
    assert "already at" in (body.get("message") or "")
    assert body["before_pct"] == pytest.approx(0.95, rel=1e-3)


def test_in_flight_invoices_schedules_real_durable_workflows(client, monkeypatch):
    c, g = client
    _seed_brand(g, "BRAND-test", budget=100_000.0, spend=10_000.0)

    scheduled = []

    async def _schedule(payload, function_name, instance_id=None):
        scheduled.append((payload, function_name, instance_id))
        return {"id": instance_id, "_started": True}

    monkeypatch.setattr(
        "api.server.services.durable_client.schedule_new_orchestration",
        _schedule,
    )

    r = c.post(
        "/api/demo/trigger/in-flight-invoices?brand_id=BRAND-test&count=2",
        headers=HDRS,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] == 2
    assert len(body["spawned_workflow_ids"]) == 2
    assert body["queue_status"] == "queued"
    assert len(scheduled) == 2
    assert all(call[1] == "FleetApInvoiceOrchestrator" for call in scheduled)
    assert all(call[0]["invoice"]["brand_id"] == "BRAND-test" for call in scheduled)
    assert all(
        app_state.store.get_workflow(workflow_id) is not None
        for workflow_id in body["spawned_workflow_ids"]
    )


def test_invoice_batch_failure_reports_already_started_work(client, monkeypatch):
    c, _graph = client
    started = []

    async def schedule(payload, function_name, instance_id=None):
        if started:
            raise RuntimeError("Functions stopped")
        started.append(payload["workflow_id"])
        return {"id": instance_id, "_started": True}

    monkeypatch.setattr(
        "api.server.services.durable_client.schedule_new_orchestration", schedule,
    )
    response = c.post(
        "/api/demo/trigger/in-flight-invoices?brand_id=BRAND-test&count=3",
        headers=HDRS,
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["started_workflow_ids"] == started
    assert detail["requested_count"] == 3
    assert detail["failed_item"] == 2
    assert app_state.store.get_workflow(started[0]) is not None


def test_aurora_convenience_route_calls_both(client, monkeypatch):
    c, g = client
    _seed_brand(g, "BRAND-aurora", budget=100_000.0, spend=40_000.0)

    scheduled = []

    async def _schedule(payload, function_name, instance_id=None):
        scheduled.append((payload, function_name, instance_id))
        return {"id": instance_id, "_started": True}

    monkeypatch.setattr(
        "api.server.services.durable_client.schedule_new_orchestration",
        _schedule,
    )

    r = c.post("/api/demo/trigger/aurora-overrun", headers=HDRS)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["brand_id"] == "BRAND-aurora"
    assert len(body["money_ids"]) == 5
    assert len(body["spawned_workflow_ids"]) == 3
    assert body["count"] == 3

    assert len(scheduled) == 3
