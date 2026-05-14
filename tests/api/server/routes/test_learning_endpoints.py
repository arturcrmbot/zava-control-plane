"""GET /api/learning/routing-stats and /api/learning/persona-experience.

Both endpoints surface the in-memory I4 + I6 matrices so the j6
"what's-new" panel can render the learning loops in real time. Empty
responses are normal on a cold process.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.server.services import persona_experience, routing_stats


@pytest.fixture
def client():
    from api.server.main import app
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean():
    routing_stats.reset()
    persona_experience.reset()
    yield
    routing_stats.reset()
    persona_experience.reset()


def test_routing_stats_endpoint_empty(client):
    r = client.get("/api/learning/routing-stats")
    assert r.status_code == 200
    body = r.json()
    assert body["stats"] == {}
    assert body["min_samples_for_routing"] == routing_stats.MIN_SAMPLES


def test_routing_stats_endpoint_returns_recorded_rows(client):
    for i in range(6):
        routing_stats.record("ap_invoice", "controller_review", "controller",
                             approved=(i % 2 == 0))
    r = client.get("/api/learning/routing-stats")
    assert r.status_code == 200
    stats = r.json()["stats"]
    assert "ap_invoice|controller_review|controller" in stats
    row = stats["ap_invoice|controller_review|controller"]
    assert row["approves"] == 3
    assert row["total"] == 6
    assert row["approval_rate"] == 0.5


def test_persona_experience_endpoint_empty(client):
    r = client.get("/api/learning/persona-experience")
    assert r.status_code == 200
    assert r.json() == {"experience": {}}


def test_persona_experience_endpoint_returns_matrix(client):
    persona_experience.record_decision("controller", "ap_invoice")
    persona_experience.record_decision("controller", "ap_invoice")
    persona_experience.record_decision("cfo", "expense_claim")

    r = client.get("/api/learning/persona-experience")
    assert r.status_code == 200
    body = r.json()
    assert body["experience"]["controller"]["ap_invoice"] == 2
    assert body["experience"]["cfo"]["expense_claim"] == 1
