"""Route-level proof for the Telco operational injectors:

  POST /api/world/inject/weather-risk
  POST /api/world/inject/spare-shortage
  POST /api/world/inject/technician-unavailable

Isolated FastAPI app (world.router only), mirroring
test_world_site_failure_route.py: a fake telco service exposes exactly the
surface routes/world.py calls; a support-only fake (missing these methods)
proves the routes degrade cleanly when the telco world is not selected.
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
        self.weather_calls: list[tuple[str, float, float]] = []
        self.spare_calls: list[tuple[str, str]] = []
        self.technician_calls: list[str] = []
        self.raise_on: str | None = None

    def snapshot(self) -> dict:
        return {"enabled": True, "scenario": "telco"}

    def inject_weather_risk(self, region: str, severity: float, duration_minutes: float) -> str:
        self.weather_calls.append((region, severity, duration_minutes))
        if self.raise_on == "weather":
            raise ValueError(f"unknown region: {region!r}")
        return "WEATHER-0001"

    def inject_spare_shortage(self, region: str, part_kind: str) -> str:
        self.spare_calls.append((region, part_kind))
        if self.raise_on == "spare":
            raise ValueError("spare stock is already at zero")
        return f"SPARE-{region.upper()}-{part_kind.upper()}"

    def inject_technician_unavailable(self, technician_id: str) -> str:
        self.technician_calls.append(technician_id)
        if self.raise_on == "technician":
            raise ValueError(f"technician {technician_id} is not available")
        return technician_id


class FakeSupportService:
    """Support world: no operations-inject attributes at all."""

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


# -- weather-risk -------------------------------------------------------------


def test_weather_risk_is_forwarded_to_telco_world(client, monkeypatch):
    fake = FakeTelcoService()
    monkeypatch.setattr(app_state, "world_service", fake, raising=False)

    response = client.post(
        "/api/world/inject/weather-risk",
        json={"region": "east", "severity": 1.5, "duration_minutes": 30},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["sim_time"] == 77.0
    assert body["event_id"] == "WEATHER-0001"
    assert fake.weather_calls == [("east", 1.5, 30.0)]


@pytest.mark.parametrize(
    "field,value", [("severity", 0), ("severity", -1), ("duration_minutes", 0)]
)
def test_weather_risk_rejects_non_positive_values(client, monkeypatch, field, value):
    fake = FakeTelcoService()
    monkeypatch.setattr(app_state, "world_service", fake, raising=False)
    body = {"region": "east", "severity": 1.0, "duration_minutes": 30}
    body[field] = value

    response = client.post("/api/world/inject/weather-risk", json=body)

    assert response.status_code == 422
    assert fake.weather_calls == []


def test_weather_risk_value_error_is_reported_as_ok_false(client, monkeypatch):
    fake = FakeTelcoService()
    fake.raise_on = "weather"
    monkeypatch.setattr(app_state, "world_service", fake, raising=False)

    response = client.post(
        "/api/world/inject/weather-risk",
        json={"region": "nowhere", "severity": 1.0, "duration_minutes": 30},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert "unknown region" in body["error"]


def test_weather_risk_support_world_degrades_cleanly(client, monkeypatch):
    monkeypatch.setattr(app_state, "world_service", FakeSupportService(), raising=False)
    response = client.post(
        "/api/world/inject/weather-risk",
        json={"region": "east", "severity": 1.0, "duration_minutes": 30},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is False


def test_weather_risk_disabled_when_no_authority_present(client):
    response = client.post(
        "/api/world/inject/weather-risk",
        json={"region": "east", "severity": 1.0, "duration_minutes": 30},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is False


# -- spare-shortage -----------------------------------------------------------


def test_spare_shortage_is_forwarded_to_telco_world(client, monkeypatch):
    fake = FakeTelcoService()
    monkeypatch.setattr(app_state, "world_service", fake, raising=False)

    response = client.post(
        "/api/world/inject/spare-shortage",
        json={"region": "east", "part_kind": "power"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["sim_time"] == 77.0
    assert body["stock_id"] == "SPARE-EAST-POWER"
    assert fake.spare_calls == [("east", "power")]


def test_spare_shortage_value_error_is_reported_as_ok_false(client, monkeypatch):
    fake = FakeTelcoService()
    fake.raise_on = "spare"
    monkeypatch.setattr(app_state, "world_service", fake, raising=False)

    response = client.post(
        "/api/world/inject/spare-shortage",
        json={"region": "west", "part_kind": "radio-unit"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert "already at zero" in body["error"]


def test_spare_shortage_support_world_degrades_cleanly(client, monkeypatch):
    monkeypatch.setattr(app_state, "world_service", FakeSupportService(), raising=False)
    response = client.post(
        "/api/world/inject/spare-shortage",
        json={"region": "east", "part_kind": "power"},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is False


def test_spare_shortage_disabled_when_no_authority_present(client):
    response = client.post(
        "/api/world/inject/spare-shortage",
        json={"region": "east", "part_kind": "power"},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is False


# -- technician-unavailable ----------------------------------------------------


def test_technician_unavailable_is_forwarded_to_telco_world(client, monkeypatch):
    fake = FakeTelcoService()
    monkeypatch.setattr(app_state, "world_service", fake, raising=False)

    response = client.post(
        "/api/world/inject/technician-unavailable",
        json={"technician_id": "TECH-NORTH-01"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["sim_time"] == 77.0
    assert body["technician_id"] == "TECH-NORTH-01"
    assert fake.technician_calls == ["TECH-NORTH-01"]


def test_technician_unavailable_value_error_is_reported_as_ok_false(client, monkeypatch):
    fake = FakeTelcoService()
    fake.raise_on = "technician"
    monkeypatch.setattr(app_state, "world_service", fake, raising=False)

    response = client.post(
        "/api/world/inject/technician-unavailable",
        json={"technician_id": "TECH-WEST-05"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert "not available" in body["error"]


def test_technician_unavailable_support_world_degrades_cleanly(client, monkeypatch):
    monkeypatch.setattr(app_state, "world_service", FakeSupportService(), raising=False)
    response = client.post(
        "/api/world/inject/technician-unavailable",
        json={"technician_id": "TECH-NORTH-01"},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is False


def test_technician_unavailable_disabled_when_no_authority_present(client):
    response = client.post(
        "/api/world/inject/technician-unavailable",
        json={"technician_id": "TECH-NORTH-01"},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is False
