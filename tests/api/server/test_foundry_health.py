"""Tests for /api/foundry/health pre-demo sanity route."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.server.routes.foundry import router


def _client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_health_returns_envelope(monkeypatch):
    """Even with no env, the route should return a structured envelope.

    The 'ok' flag will be False (most checks failing) but the route itself
    must not raise.
    """
    for k in ("APPLICATIONINSIGHTS_CONNECTION_STRING",
              "AZURE_FOUNDRY_PROJECT_ENDPOINT",
              "AZURE_OPENAI_ENDPOINT",
              "AZURE_OPENAI_DEPLOYMENT",
              "AZURE_STORAGE_AUDIT_ACCOUNT"):
        monkeypatch.delenv(k, raising=False)

    res = _client().get("/api/foundry/health")
    assert res.status_code == 200
    body = res.json()
    assert "ok" in body
    assert "checks" in body
    check_names = {c["name"] for c in body["checks"]}
    assert check_names == {
        "application_insights", "foundry_eval_sdk",
        "audit_blob", "model_pricing",
    }
    assert body["ok"] is False  # nothing configured
    assert body["online_eval_subscriber"]["active"] is False


def test_health_appi_check_passes_when_env_set(monkeypatch):
    monkeypatch.setenv(
        "APPLICATIONINSIGHTS_CONNECTION_STRING",
        "InstrumentationKey=00000000-0000-0000-0000-000000000000;",
    )
    res = _client().get("/api/foundry/health")
    body = res.json()
    appi = next(c for c in body["checks"] if c["name"] == "application_insights")
    assert appi["ok"] is True


def test_health_links_present():
    res = _client().get("/api/foundry/health")
    body = res.json()
    assert body["links"]["foundry_tracing"].startswith("https://ai.azure.com")


def test_health_model_pricing_check_always_ok():
    """Pricing table is in-process; should always succeed."""
    res = _client().get("/api/foundry/health")
    body = res.json()
    pricing = next(c for c in body["checks"] if c["name"] == "model_pricing")
    assert pricing["ok"] is True
    assert "azure" in pricing["detail"].lower()
