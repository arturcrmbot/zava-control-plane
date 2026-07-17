from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.server.routes import world as world_route
from api.server.state import app_state


class _Runtime:
    now = 17.0


class _Service:
    runtime = _Runtime()

    def __init__(self):
        self.calls = []

    def run_reference_process(self, workflow_type):
        self.calls.append(workflow_type)
        return {
            "case_id": "CASE-OSS03-0001",
            "root_event_id": "evt-1",
            "sensor_event_id": "evt-2",
        }


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(app_state, "world_service", None, raising=False)
    app = FastAPI()
    app.include_router(world_route.router)
    return TestClient(app)


def test_reference_process_route_starts_declared_profile(client, monkeypatch):
    service = _Service()
    monkeypatch.setattr(app_state, "world_service", service, raising=False)

    response = client.post("/api/world/processes/ran-capacity-planning/run")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "workflow_type": "ran-capacity-planning",
        "case_id": "CASE-OSS03-0001",
        "root_event_id": "evt-1",
        "sensor_event_id": "evt-2",
        "sim_time": 17.0,
    }
    assert service.calls == ["ran-capacity-planning"]


def test_reference_process_route_rejects_unknown_or_hero_process(
    client,
    monkeypatch,
):
    service = _Service()
    monkeypatch.setattr(app_state, "world_service", service, raising=False)

    unknown = client.post("/api/world/processes/not-real/run")
    hero = client.post("/api/world/processes/network-incident/run")

    assert unknown.json()["ok"] is False
    assert hero.json()["ok"] is False
    assert service.calls == []
