"""The world reference-process route is vertical-agnostic: it runs whatever
process types the active world scenario declares runnable, falling back to the
telco/support standard profiles for scenarios that do not declare their own."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.server.routes import world as world_route
from api.server.state import app_state


class _Runtime:
    now = 42.0


class _FashionScenario:
    reference_process_types = frozenset(
        {"inventory-rebalancing", "returns-disposition"}
    )


class _FashionWorldService:
    runtime = _Runtime()
    scenario = _FashionScenario()

    def __init__(self) -> None:
        self.calls: list[str] = []

    def run_reference_process(self, workflow_type: str) -> dict:
        if workflow_type not in self.scenario.reference_process_types:
            raise ValueError(f"unknown Fashion process: {workflow_type!r}")
        self.calls.append(workflow_type)
        return {
            "case_id": "fashion-inventory-rebalance-auto",
            "root_event_id": "evt-1",
            "sensor_event_id": "evt-2",
            "trace_id": "fashion-inventory-rebalancing-fashion-...",
        }


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(app_state, "world_service", None, raising=False)
    app = FastAPI()
    app.include_router(world_route.router)
    return TestClient(app)


def test_route_runs_a_scenario_declared_fashion_process(client, monkeypatch):
    service = _FashionWorldService()
    monkeypatch.setattr(app_state, "world_service", service, raising=False)

    response = client.post("/api/world/processes/inventory-rebalancing/run")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["workflow_type"] == "inventory-rebalancing"
    assert body["case_id"] == "fashion-inventory-rebalance-auto"
    assert body["sim_time"] == 42.0
    assert service.calls == ["inventory-rebalancing"]


def test_route_rejects_types_the_active_scenario_cannot_run(client, monkeypatch):
    service = _FashionWorldService()
    monkeypatch.setattr(app_state, "world_service", service, raising=False)

    # A telco standard profile is not runnable in the Fashion world.
    rejected = client.post("/api/world/processes/ran-capacity-planning/run")

    assert rejected.json()["ok"] is False
    assert service.calls == []
