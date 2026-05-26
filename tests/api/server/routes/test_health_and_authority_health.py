"""Regression tests for the catch-all-safe /healthz route and the
in-process-aware /api/authority/health route.

Background: a production deploy of the substrate (see
zava-control-plane.yellowstone-… troubleshooting May 2026) mounted
``StaticFiles(directory=..., html=True)`` at ``/`` to serve the
React bundle. That mount served ``index.html`` for any unmatched
path, including ``/healthz`` and unknown ``/api/*`` paths, masking
both real backend failures and operator typos. The fix is two
explicit routes registered before the SPA mount.

Separately, ``/api/authority/health`` always proxied HTTP to the
optional Node MCP sidecar even when ``resolve``/``check`` actually
ran in-process via the governance kernel (see
``api.server.routes.authority.authority_health`` docstring). When
the sidecar isn't deployed (the default since Phase 3 TASK-022) the
endpoint reported red even though authority was fully functional.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from api.server.main import app

    return TestClient(app)


def test_healthz_returns_json_ok(client):
    """/healthz must return JSON (not the SPA index.html), regardless of
    static-file mount order downstream."""
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json() == {"ok": True}


def test_api_health_still_returns_json_ok(client):
    """Sister endpoint /api/health stays unchanged."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json() == {"ok": True}


def test_authority_health_green_when_in_process_kernel_loaded(
    client, monkeypatch
):
    """With ``AUTHORITY_MCP_URL`` unset, /api/authority/health must
    report the in-process governance kernel — not 503 a nonexistent
    MCP sidecar."""
    monkeypatch.delenv("AUTHORITY_MCP_URL", raising=False)

    resp = client.get("/api/authority/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["backend"] == "in-process"
    assert body["rule_count"] > 0


def test_authority_health_proxies_http_when_url_set(client, monkeypatch):
    """When ``AUTHORITY_MCP_URL`` IS set, we still proxy the MCP /health
    so engagement-POC deploys (Foundry-IQ swap-in) keep working.

    We point at a guaranteed-unreachable URL and expect 503 with the
    legacy ``authority MCP unreachable at …`` detail.
    """
    monkeypatch.setenv("AUTHORITY_MCP_URL", "http://127.0.0.1:1")

    resp = client.get("/api/authority/health")
    assert resp.status_code == 503
    assert "authority MCP unreachable at" in resp.json()["detail"]
