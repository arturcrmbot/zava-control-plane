"""Route-level proof for /api/world/{state,events,inject/demand_surge}.

Isolated FastAPI app (world.router only) so these tests never touch the real
lifespan. A fake ActorWorldService covers the primary (actor) authority; a
minimal fake engine covers the aggregate toy fallback. Every test starts from
an explicitly-disabled baseline (world_service/world_engine monkeypatched to
None) so state never leaks from other test modules that share the process-
wide app_state singleton.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.server.routes import world as world_route
from api.server.state import app_state


class FakeRuntime:
    def __init__(self, journal: list, now: float = 123.0) -> None:
        self.journal = journal
        self.now = now


class FakeActorWorldService:
    """Minimal stand-in for ActorWorldService: runtime.journal, snapshot,
    events_after, inject_demand_surge — exactly the surface routes/world.py
    calls."""

    def __init__(self) -> None:
        self.runtime = FakeRuntime(journal=list(range(8)))
        self.inject_calls: list[tuple[float, float]] = []
        self.events_after_calls: list[int] = []

    def snapshot(self) -> dict:
        return {"enabled": True, "scenario": "support", "sim_time": self.runtime.now}

    def events_after(self, after: int) -> list[dict]:
        self.events_after_calls.append(after)
        return [{"seq": i} for i in range(after, len(self.runtime.journal))]

    def inject_demand_surge(self, multiplier: float, duration_minutes: float) -> None:
        self.inject_calls.append((multiplier, duration_minutes))


class FakeEngineState:
    def __init__(self) -> None:
        self.stocks = {"backlog": 12.0}
        self.resources = {"agents": 5.0}
        self.signals = {"pressure": 0.5}
        self.inputs = {"arrival_rate": 3.0}


class FakePack:
    name = "toy"


class FakeWorldEngine:
    """Minimal stand-in for the aggregate WorldEngine: pack.name, state,
    inject(name) — exactly the surface routes/world.py calls."""

    def __init__(self) -> None:
        self.pack = FakePack()
        self.state = FakeEngineState()
        self.injected: list[str] = []

    def inject(self, name: str) -> None:
        self.injected.append(name)


@pytest.fixture
def client(monkeypatch):
    # Explicit disabled baseline: neither authority present, regardless of
    # what other test modules left on the shared app_state singleton.
    monkeypatch.setattr(app_state, "world_service", None, raising=False)
    monkeypatch.setattr(app_state, "world_engine", None, raising=False)
    monkeypatch.setattr(app_state, "world_last_response", None, raising=False)
    app = FastAPI()
    app.include_router(world_route.router)
    return TestClient(app)


def test_state_returns_actor_snapshot_and_last_response(client, monkeypatch):
    fake = FakeActorWorldService()
    monkeypatch.setattr(app_state, "world_service", fake, raising=False)
    monkeypatch.setattr(
        app_state, "world_last_response", {"instance_id": "durable-1"}, raising=False
    )
    response = client.get("/api/world/state")
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["scenario"] == "support"
    assert body["last_response"] == {"instance_id": "durable-1"}


def test_compact_telco_state_omits_bulk_rows_but_preserves_display_totals(
    client, monkeypatch
):
    fake = FakeActorWorldService()
    sessions = [
        {"id": f"ACTIVE-{i:02d}", "status": "active"} for i in range(30)
    ] + [
        {"id": f"REROUTED-{i:02d}", "status": "rerouted"} for i in range(26)
    ] + [
        {"id": f"DEGRADED-{i:02d}", "status": "degraded"} for i in range(2)
    ]
    fake.snapshot = lambda: {
        "enabled": True,
        "scenario": "telco",
        "sessions": sessions,
        "subscribers": [{"id": f"SUB-{i:02d}"} for i in range(40)],
        "subscriptions": [{"id": f"PLAN-{i:02d}"} for i in range(40)],
        "accounts": [
            {"id": "ACC-00001"},
            {"id": "ACC-00002"},
            {"id": "ACC-00003"},
        ],
        "customer_impact": {"account_ids": ["ACC-00003"]},
    }
    monkeypatch.setattr(app_state, "world_service", fake, raising=False)

    response = client.get("/api/world/state?compact=true")

    assert response.status_code == 200
    body = response.json()
    assert body["session_counts"] == {
        "active": 30,
        "rerouted": 26,
        "degraded": 2,
    }
    assert len(body["sessions"]) == 24 + 24 + 2
    assert body["subscriber_count"] == 40
    assert body["subscription_count"] == 40
    assert body["account_count"] == 3
    assert body["accounts"] == [{"id": "ACC-00001"}, {"id": "ACC-00003"}]
    assert "subscribers" not in body
    assert "subscriptions" not in body


def test_events_forwards_after_and_latest_seq(client, monkeypatch):
    fake = FakeActorWorldService()
    monkeypatch.setattr(app_state, "world_service", fake, raising=False)
    response = client.get("/api/world/events?after=3")
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "enabled": True,
        "latest_seq": len(fake.runtime.journal),
        "events": [{"seq": 3}, {"seq": 4}, {"seq": 5}, {"seq": 6}, {"seq": 7}],
    }
    assert fake.events_after_calls == [3]


def test_events_limit_returns_only_the_newest_visual_tail(client, monkeypatch):
    fake = FakeActorWorldService()
    monkeypatch.setattr(app_state, "world_service", fake, raising=False)

    response = client.get("/api/world/events?after=0&limit=3")

    assert response.status_code == 200
    assert response.json() == {
        "enabled": True,
        "latest_seq": len(fake.runtime.journal),
        "events": [{"seq": 5}, {"seq": 6}, {"seq": 7}],
    }
    assert fake.events_after_calls == [0]


def test_inject_demand_surge_uses_defaults_and_custom_values(client, monkeypatch):
    fake = FakeActorWorldService()
    monkeypatch.setattr(app_state, "world_service", fake, raising=False)

    no_body = client.post("/api/world/inject/demand_surge")
    assert no_body.status_code == 200
    assert no_body.json() == {
        "ok": True,
        "sim_time": fake.runtime.now,
        "multiplier": 4,
        "duration_minutes": 90,
    }

    empty_body = client.post("/api/world/inject/demand_surge", json={})
    assert empty_body.status_code == 200
    assert fake.inject_calls[:2] == [(4, 90), (4, 90)]

    custom = client.post(
        "/api/world/inject/demand_surge",
        json={"multiplier": 8, "duration_minutes": 30},
    )
    assert custom.status_code == 200
    assert custom.json() == {
        "ok": True,
        "sim_time": fake.runtime.now,
        "multiplier": 8,
        "duration_minutes": 30,
    }
    assert fake.inject_calls[-1] == (8, 30)


@pytest.mark.parametrize(
    "body",
    [
        {"multiplier": 1},
        {"multiplier": 0.5},
        {"multiplier": -3},
        {"multiplier": "nan"},
        {"multiplier": "inf"},
        {"multiplier": "-inf"},
        {"duration_minutes": 0},
        {"duration_minutes": -5},
        {"duration_minutes": "nan"},
        {"duration_minutes": "inf"},
        {"duration_minutes": "-inf"},
    ],
)
def test_inject_demand_surge_rejects_invalid_values(client, monkeypatch, body):
    fake = FakeActorWorldService()
    monkeypatch.setattr(app_state, "world_service", fake, raising=False)
    response = client.post("/api/world/inject/demand_surge", json=body)
    assert response.status_code == 422
    assert fake.inject_calls == []


def test_disabled_when_no_authority_present(client):
    assert client.get("/api/world/state").json() == {"enabled": False}
    assert client.get("/api/world/events").json() == {
        "enabled": False,
        "latest_seq": 0,
        "events": [],
    }
    body = client.post("/api/world/inject/demand_surge").json()
    assert body["ok"] is False


def test_aggregate_fallback_state_still_works(client, monkeypatch):
    engine = FakeWorldEngine()
    monkeypatch.setattr(app_state, "world_engine", engine, raising=False)

    response = client.get("/api/world/state")
    assert response.status_code == 200
    assert response.json() == {
        "enabled": True,
        "pack": "toy",
        "stocks": {"backlog": 12.0},
        "resources": {"agents": 5.0},
        "signals": {"pressure": 0.5},
        "inputs": {"arrival_rate": 3.0},
        "last_response": None,
    }

    inject_response = client.post("/api/world/inject/demand_surge")
    assert inject_response.status_code == 200
    assert inject_response.json() == {"ok": True, "injected": "demand_surge"}
    assert engine.injected == ["demand_surge"]
