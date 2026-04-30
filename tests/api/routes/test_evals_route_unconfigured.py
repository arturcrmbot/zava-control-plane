"""When Foundry is not configured, eval endpoints return {configured: false}."""
from __future__ import annotations
from fastapi.testclient import TestClient


def _client(monkeypatch):
    monkeypatch.delenv("AZURE_FOUNDRY_PROJECT_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT", raising=False)
    import sys
    sys.modules.pop("api.server.eval.foundry_client", None)
    from api.server.main import app
    return TestClient(app)


def test_get_evals_returns_configured_false_with_200(monkeypatch):
    c = _client(monkeypatch)
    r = c.get("/api/evals/")
    assert r.status_code == 200
    assert r.json()["configured"] is False
    assert "reason" in r.json()


def test_get_evals_summary_returns_configured_false(monkeypatch):
    c = _client(monkeypatch)
    r = c.get("/api/evals/summary")
    assert r.status_code == 200
    assert r.json()["configured"] is False


def test_get_evals_health_returns_configured_false(monkeypatch):
    c = _client(monkeypatch)
    r = c.get("/api/evals/health")
    assert r.status_code == 200
    assert r.json()["configured"] is False
