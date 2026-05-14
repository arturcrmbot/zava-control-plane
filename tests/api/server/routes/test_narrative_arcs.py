"""Tests for the narrative-arcs HUD registry route (Pitch D5).

Covers ``GET /api/personas/narrative-arcs`` — the static, public-read
endpoint that surfaces 5–8 named individuals to the cosmic-lens HUD.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from api.server.main import app
    return TestClient(app)


def test_narrative_arcs_returns_named_individuals(client):
    r = client.get("/api/personas/narrative-arcs")
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, list)
    assert 5 <= len(body) <= 8
    expected_keys = {
        "employee_id", "name", "role", "photo_url",
        "one_liner", "arc", "function",
    }
    for arc in body:
        assert expected_keys <= arc.keys()
        assert arc["employee_id"].startswith("PERSON-EMP-")
        assert arc["photo_url"].startswith("/assets/personae/")
        assert 0 < len(arc["one_liner"]) <= 120
        assert len(arc["arc"]) > len(arc["one_liner"])


def test_narrative_arcs_roles_exist_in_persona_registry(client):
    """Every arc's role must be a real entry in the persona registry —
    otherwise the HUD would render a city that doesn't exist."""
    from api.shared import personas as personas_registry

    body = client.get("/api/personas/narrative-arcs").json()
    registry_roles = set(personas_registry.PERSONAS.keys())
    for arc in body:
        assert arc["role"] in registry_roles, (
            f"narrative arc {arc['name']!r} references unknown role "
            f"{arc['role']!r}"
        )


def test_narrative_arcs_employee_ids_are_unique(client):
    body = client.get("/api/personas/narrative-arcs").json()
    ids = [a["employee_id"] for a in body]
    assert len(ids) == len(set(ids))


def test_narrative_arcs_does_not_collide_with_role_catchall(client):
    """Regression: ``/{role}`` is registered after this route, so a
    request for ``/api/personas/narrative-arcs`` must not 404 as an
    unknown role."""
    r = client.get("/api/personas/narrative-arcs")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
