"""Tests for /api/functions/{name}/ambient + /api/cadences (Phase 4 IP7)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from api.server.main import app
    return TestClient(app)


def test_ambient_for_finance_returns_three_agents(client):
    r = client.get("/api/functions/finance/ambient")
    assert r.status_code == 200
    body = r.json()
    names = {a["name"] for a in body}
    assert {"budget-variance-watcher", "vendor-risk-watcher", "period-close"} <= names
    for a in body:
        assert a["function"] == "finance"
        assert isinstance(a["triggers"], list)
        assert "spawnable_workflow_types" in a
        assert "is_killed" in a
        assert a["is_killed"] is False
        assert "last_trigger_at" in a
        assert "last_spawn_outcome" in a


def test_ambient_unknown_function_404(client):
    r = client.get("/api/functions/not-a-function/ambient")
    assert r.status_code == 404


def test_ambient_legacy_404(client):
    r = client.get("/api/functions/legacy/ambient")
    assert r.status_code == 404


def test_cadences_lists_three_or_more(client):
    r = client.get("/api/cadences")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) >= 3
    names = {c["name"] for c in body}
    assert {"morning-sweep", "period-close", "quarterly-okr"} <= names
    for c in body:
        assert c["fires_ambient_agent"]
        assert c["schedule"]
        # next_run_at may be None if cron parser fails, but must be present
        assert "next_run_at" in c
