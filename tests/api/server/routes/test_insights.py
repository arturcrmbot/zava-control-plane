"""Phase 6 of autonomous-domain-insights v1: HTTP routes."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.server.services.entity_graph import EntityGraph, EntityWrite
from api.server.state import app_state


@pytest.fixture
def client_with_insight(tmp_path: Path, monkeypatch):
    # Mirror the sibling _accounts_fixtures.py pattern: bypass the env-var-
    # too-late problem by monkeypatching app_state.entities at a fresh tmp
    # path (Kuzu single-writer lock requires unique paths per fixture).
    monkeypatch.setenv("INSIGHT_LOOP_ENABLED", "0")
    g = EntityGraph(tmp_path / "ig.kuzu")
    monkeypatch.setattr(app_state, "entities", g)

    g.upsert(EntityWrite(
        kind="Insight",
        id="INSIGHT-cfo-1",
        attrs={
            "role": "cfo",
            "scope": "Finance",
            "decided_at": datetime.utcnow(),
            "headline": "All brands within budget",
            "body": "calm",
            "kpis": json.dumps({"budget_used_pct": 0.62}),
            "proposed_actions": json.dumps([]),
            "fingerprint": "fp-cfo-1",
            "attributes": "{}",
        },
        source_workflows=(),
    ))

    try:
        from api.server.main import app
        yield TestClient(app)
    finally:
        g.close()


def test_latest_for_role_returns_insight(client_with_insight):
    r = client_with_insight.get(
        "/api/personas/cfo/insights/latest",
        headers={"x-actor-role": "executive"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "cfo"
    assert body["headline"] == "All brands within budget"
    assert body["kpis"] == {"budget_used_pct": 0.62}
    assert body["proposed_actions"] == []


def test_latest_for_role_returns_404_when_none(client_with_insight):
    r = client_with_insight.get(
        "/api/personas/nobody/insights/latest",
        headers={"x-actor-role": "executive"},
    )
    assert r.status_code == 404


def test_latest_per_role_returns_one_per_role(client_with_insight):
    app_state.entities.upsert(EntityWrite(
        kind="Insight",
        id="INSIGHT-hr_director-1",
        attrs={
            "role": "hr_director",
            "scope": "HR",
            "decided_at": datetime.utcnow(),
            "headline": "Headcount steady",
            "body": "",
            "kpis": "{}",
            "proposed_actions": "[]",
            "fingerprint": "fp-hr-1",
            "attributes": "{}",
        },
        source_workflows=(),
    ))

    r = client_with_insight.get(
        "/api/personas/insights/latest",
        headers={"x-actor-role": "executive"},
    )
    assert r.status_code == 200
    body = r.json()
    roles = sorted(item["role"] for item in body["insights"])
    assert roles == ["cfo", "hr_director"]
    # Response must already be sorted by role name alphabetically.
    assert [item["role"] for item in body["insights"]] == ["cfo", "hr_director"]


def test_approve_route_no_longer_exists(client_with_insight):
    """Persona-in-the-loop: there is no operator approval click. Both
    POST surfaces are gone — the cadence loop self-applies via
    :mod:`api.server.services.policy_application` instead."""
    r = client_with_insight.post(
        "/api/personas/cfo/actions/anything/approve",
        headers={"x-actor-role": "executive"},
    )
    assert r.status_code in (404, 405)


def test_latest_per_role_returns_empty_when_no_insights(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("INSIGHT_LOOP_ENABLED", "0")
    g = EntityGraph(tmp_path / "ig_empty.kuzu")
    monkeypatch.setattr(app_state, "entities", g)
    try:
        from api.server.main import app
        client = TestClient(app)
        r = client.get(
            "/api/personas/insights/latest",
            headers={"x-actor-role": "executive"},
        )
        assert r.status_code == 200
        assert r.json() == {"insights": []}
    finally:
        g.close()
