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
import httpx
from fastapi.testclient import TestClient
from unittest.mock import MagicMock


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


def test_readiness_is_not_process_liveness(client, monkeypatch):
    from api.server.main import app
    monkeypatch.setattr(app.state, "startup_complete", False, raising=False)
    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["reason"] == "starting"


def test_replay_readiness_does_not_require_functions_or_models(client, monkeypatch):
    from api.server import main
    from api.server.services.replay import player
    monkeypatch.setattr(main.app.state, "startup_complete", True, raising=False)
    monkeypatch.setattr(main, "is_replay", lambda: True)
    active = MagicMock()
    active._task.done.return_value = False
    monkeypatch.setattr(player, "current_player", lambda: active)
    monkeypatch.delenv("DURABLE_EVENT_SECRET", raising=False)
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"ready": True, "mode": "replay"}


def test_live_readiness_requires_responsive_functions(client, monkeypatch, respx_mock):
    from api.server import main
    monkeypatch.setattr(main.app.state, "startup_complete", True, raising=False)
    monkeypatch.setattr(main, "is_replay", lambda: False)
    monkeypatch.setattr(main.app_state.fm, "_started", True)
    monkeypatch.setenv("FUNCTIONS_HOST", "http://functions.test")
    route = respx_mock.get("http://functions.test/api/zava-ready").mock(
        return_value=httpx.Response(503),
    )
    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["reason"] == "functions_unavailable"
    route.mock(return_value=httpx.Response(200, json={"state": "Running"}))
    assert client.get("/readyz").json() == {"ready": True, "mode": "live"}


def test_live_readiness_reports_missing_supervisor(client, monkeypatch):
    from api.server import main
    monkeypatch.setattr(main.app.state, "startup_complete", True, raising=False)
    monkeypatch.setattr(main, "is_replay", lambda: False)
    monkeypatch.setattr(main.app_state.fm, "_started", False)
    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["reason"] == "supervisor_unavailable"


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
