from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.server.routes import world as world_route
from api.server.state import app_state


SCENARIOS = {
    "storm-cascade": "sensor:outage_risk",
    "maintenance-save": "sensor:asset_failure_risk",
    "capacity-revenue": "sensor:site_congestion",
    "vulnerable-retention": "sensor:ticket_pressure",
}


class _Runtime:
    now = 12.0
    journal: list = []


class _Service:
    seed = 42
    runtime = _Runtime()

    def __init__(self):
        self.calls: list[str] = []

    def run_scenario(self, name: str) -> dict:
        self.calls.append(name)
        return {
            "scenario_id": f"{name}-42",
            "root_event_id": "evt-00000001",
            "seed": self.seed,
            "expected_first_sensor": SCENARIOS[name],
        }


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(app_state, "world_service", None, raising=False)
    monkeypatch.setattr(app_state, "world_engine", None, raising=False)
    app = FastAPI()
    app.include_router(world_route.router)
    return TestClient(app)


@pytest.mark.parametrize("name,expected_sensor", SCENARIOS.items())
def test_telco_scenario_endpoint_returns_replayable_contract(
    client,
    monkeypatch,
    name,
    expected_sensor,
):
    service = _Service()
    monkeypatch.setattr(app_state, "world_service", service, raising=False)

    response = client.post(f"/api/world/scenarios/{name}")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "scenario_id": f"{name}-42",
        "root_event_id": "evt-00000001",
        "seed": 42,
        "expected_first_sensor": expected_sensor,
    }
    assert service.calls == [name]


def test_unknown_telco_scenario_is_rejected(client, monkeypatch):
    service = _Service()
    monkeypatch.setattr(app_state, "world_service", service, raising=False)

    response = client.post("/api/world/scenarios/not-real")

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert service.calls == []


def test_telco_scenario_endpoint_requires_live_telco_world(client):
    response = client.post("/api/world/scenarios/storm-cascade")

    assert response.status_code == 200
    assert response.json()["ok"] is False
