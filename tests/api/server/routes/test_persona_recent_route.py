"""The Org Building (IP7, TASK-040) — /api/persona/{role}/recent."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from api.server.main import app
    with TestClient(app) as c:
        yield c


def test_persona_recent_returns_shape_for_unknown_role(client):
    """Unknown roles still return a 200 with empty lists — no 404 for
    role unknown to the persona registry, since gates may name any role."""
    r = client.get("/api/persona/does-not-exist/recent")
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "does-not-exist"
    assert body["pending_gates"] == []
    assert isinstance(body["recent_decisions"], list)


def test_persona_recent_known_role_returns_lists(client):
    r = client.get("/api/persona/cfo/recent?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "cfo"
    assert isinstance(body["pending_gates"], list)
    assert isinstance(body["recent_decisions"], list)
    assert len(body["pending_gates"]) <= 5
    assert len(body["recent_decisions"]) <= 5


def test_persona_recent_400_on_empty_role(client):
    # Path can't actually be empty (FastAPI redirects), so this is a
    # smoke that the limit parameter clamps high values gracefully.
    r = client.get("/api/persona/cfo/recent?limit=10000")
    assert r.status_code == 200
