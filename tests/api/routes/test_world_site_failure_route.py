"""Route-level proof for POST /api/world/inject/site_failure (telco).

Isolated FastAPI app (world.router only). A fake telco service exposes exactly
the surface routes/world.py calls; a support-only fake (no inject_site_failure)
proves the route degrades cleanly when the telco world is not selected.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.server.routes import world as world_route
from api.server.state import app_state


class FakeRuntime:
    def __init__(self, now: float = 77.0) -> None:
        self.journal: list = []
        self.now = now


class FakeTelcoService:
    def __init__(self) -> None:
        self.runtime = FakeRuntime()
        self.calls: list[str | None] = []
        self.capacity_calls: list[tuple[str, float]] = []
        self.raise_on: str | None = None

    def snapshot(self) -> dict:
        return {"enabled": True, "scenario": "telco"}

    def inject_site_failure(self, site_id: str | None = None) -> str:
        self.calls.append(site_id)
        if self.raise_on is not None and site_id == self.raise_on:
            raise ValueError(f"site {site_id} is not healthy")
        return site_id or "SITE-03"

    def inject_capacity_pressure(self, site_id: str, utilization: float) -> str:
        self.capacity_calls.append((site_id, utilization))
        return site_id


class FakeSupportService:
    """Support world: no inject_site_failure attribute at all."""

    def __init__(self) -> None:
        self.runtime = FakeRuntime()

    def snapshot(self) -> dict:
        return {"enabled": True, "scenario": "support"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(app_state, "world_service", None, raising=False)
    monkeypatch.setattr(app_state, "world_engine", None, raising=False)
    monkeypatch.setattr(app_state, "world_last_response", None, raising=False)
    app = FastAPI()
    app.include_router(world_route.router)
    return TestClient(app)


def test_default_site_failure_uses_deterministic_site(client, monkeypatch):
    fake = FakeTelcoService()
    monkeypatch.setattr(app_state, "world_service", fake, raising=False)

    no_body = client.post("/api/world/inject/site_failure")
    assert no_body.status_code == 200
    assert no_body.json() == {"ok": True, "sim_time": 77.0, "site_id": "SITE-03"}
    assert fake.calls == [None]


def test_explicit_site_id_is_forwarded(client, monkeypatch):
    fake = FakeTelcoService()
    monkeypatch.setattr(app_state, "world_service", fake, raising=False)
    response = client.post("/api/world/inject/site_failure", json={"site_id": "SITE-07"})
    assert response.status_code == 200
    assert response.json() == {"ok": True, "sim_time": 77.0, "site_id": "SITE-07"}
    assert fake.calls == ["SITE-07"]


def test_capacity_pressure_is_forwarded_to_telco_world(client, monkeypatch):
    fake = FakeTelcoService()
    monkeypatch.setattr(app_state, "world_service", fake, raising=False)

    response = client.post(
        "/api/world/inject/capacity_pressure",
        json={"site_id": "SITE-12", "utilization": 0.95},
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "sim_time": 77.0,
        "site_id": "SITE-12",
        "utilization": 0.95,
    }
    assert fake.capacity_calls == [("SITE-12", 0.95)]


@pytest.mark.parametrize("utilization", [0.89, 1.01])
def test_capacity_pressure_rejects_values_outside_exception_range(
    client, monkeypatch, utilization
):
    fake = FakeTelcoService()
    monkeypatch.setattr(app_state, "world_service", fake, raising=False)

    response = client.post(
        "/api/world/inject/capacity_pressure",
        json={"site_id": "SITE-12", "utilization": utilization},
    )

    assert response.status_code == 422
    assert fake.capacity_calls == []


def test_value_error_is_reported_as_ok_false(client, monkeypatch):
    fake = FakeTelcoService()
    fake.raise_on = "SITE-07"
    monkeypatch.setattr(app_state, "world_service", fake, raising=False)
    response = client.post("/api/world/inject/site_failure", json={"site_id": "SITE-07"})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert "not healthy" in body["error"]


def test_support_world_without_site_failure_degrades_cleanly(client, monkeypatch):
    monkeypatch.setattr(app_state, "world_service", FakeSupportService(), raising=False)
    response = client.post("/api/world/inject/site_failure")
    assert response.status_code == 200
    assert response.json()["ok"] is False


def test_disabled_when_no_authority_present(client):
    response = client.post("/api/world/inject/site_failure")
    assert response.status_code == 200
    assert response.json()["ok"] is False
