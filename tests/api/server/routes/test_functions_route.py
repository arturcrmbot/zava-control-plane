"""Phase 3 IP7 — TASK-040. /api/functions endpoint contracts."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from api.server.main import app
    with TestClient(app) as c:
        yield c


def test_list_functions_returns_ten_non_legacy_entries(client):
    r = client.get("/api/functions")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) == 10
    names = {entry["name"] for entry in body}
    assert "legacy" not in names
    assert "ceo" in names
    # Every entry has the documented shape.
    for entry in body:
        assert {
            "name", "display", "operatorSurface",
            "ownsDomains", "ambientAgents", "kpis", "personaHierarchy",
        } <= entry.keys()
        assert isinstance(entry["personaHierarchy"], dict)
        assert "role" in entry["personaHierarchy"]
        assert "manages" in entry["personaHierarchy"]


def test_owned_domains_resolve_against_DOMAINS(client):
    from api.shared.domains import DOMAINS
    r = client.get("/api/functions")
    for entry in r.json():
        for d in entry["ownsDomains"]:
            assert d in DOMAINS, (
                f"function {entry['name']} declares unknown domain {d}"
            )


def test_legacy_sse_returns_404(client):
    r = client.get("/api/functions/legacy/sse")
    assert r.status_code == 404


def test_unknown_function_sse_returns_404(client):
    r = client.get("/api/functions/does-not-exist/sse")
    assert r.status_code == 404


def test_finance_sse_route_registered(client):
    """Route is registered: a GET to /api/functions/finance/sse does not
    404 (full streaming is exercised by the SSE infrastructure tests).
    We verify routing via the FastAPI app's routes table to avoid hanging
    on a long-lived SSE connection inside TestClient.
    """
    from api.server.main import app
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/api/functions/{name}/sse" in paths
    assert "/api/functions" in paths or "/api/functions/" in paths
