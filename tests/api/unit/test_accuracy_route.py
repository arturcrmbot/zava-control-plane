"""Accuracy route tests using FastAPI test client.

After the Foundry-eval cutover the route is backed by api.server.eval.batch_runner
and gated by foundry_client.is_configured(). When Foundry is unconfigured:
- POST /api/accuracy/run returns 503
- GET /api/accuracy/last returns {configured: false} (HTTP 200)
- GET /api/accuracy/{run_id} returns {configured: false} (HTTP 200)
"""
from __future__ import annotations
import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.server.main import app


client = TestClient(app)


def _fake_report(n: int = 3) -> dict:
    return {
        "run_id": "r-test", "n": n, "overall_accuracy": 1.0, "per_category": {},
        "confusion_matrix": {
            "green": {"green": n, "amber": 0, "red": 0},
            "amber": {"green": 0, "amber": 0, "red": 0},
            "red": {"green": 0, "amber": 0, "red": 0},
        },
        "per_claim": [],
    }


# --- Unconfigured (default test environment) -------------------------------

def test_post_run_returns_503_when_foundry_not_configured(monkeypatch):
    monkeypatch.delenv("AZURE_FOUNDRY_PROJECT_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT", raising=False)
    resp = client.post("/api/accuracy/run", json={"sample_size": 3})
    assert resp.status_code == 503
    detail = resp.json()["detail"]
    assert detail["configured"] is False
    assert "Foundry" in detail["reason"]


def test_get_last_returns_configured_false_when_unconfigured(monkeypatch):
    monkeypatch.delenv("AZURE_FOUNDRY_PROJECT_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT", raising=False)
    resp = client.get("/api/accuracy/last")
    assert resp.status_code == 200
    assert resp.json()["configured"] is False


def test_get_by_run_id_returns_configured_false_when_unconfigured(monkeypatch):
    monkeypatch.delenv("AZURE_FOUNDRY_PROJECT_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT", raising=False)
    resp = client.get("/api/accuracy/acc-deadbeef")
    assert resp.status_code == 200
    assert resp.json()["configured"] is False


# --- Configured (env vars set + batch_runner mocked) -----------------------

@pytest.fixture
def _configured(monkeypatch):
    monkeypatch.setenv("AZURE_FOUNDRY_PROJECT_ENDPOINT", "https://example.cognitiveservices.azure.com")
    monkeypatch.setenv("AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT", "gpt-4o")
    yield


def test_post_run_returns_run_id_and_accepted_status(_configured):
    from api.server.eval import batch_runner
    from api.functions.graphs.executors.agents import agent_rag_classifier
    # The route schedules a background task that pre-classifies every claim
    # via rag_execute (real Copilot call) BEFORE handing rows to
    # batch_runner.run. TestClient awaits background tasks before unblocking
    # the caller, so without mocking rag_execute the test would hang on the
    # first GHCP call. Patch both.
    fake_classify = AsyncMock(return_value={
        "classification": {"verdict": "green", "reasoning": "ok",
                           "policy_clause": "T-1"},
    })
    with patch.object(batch_runner, "run", AsyncMock(return_value=_fake_report(3))), \
         patch.object(agent_rag_classifier, "execute", fake_classify):
        resp = client.post("/api/accuracy/run", json={"sample_size": 3})
    assert resp.status_code == 202
    body = resp.json()
    assert "run_id" in body
    assert body["n"] == 3


def test_get_last_returns_404_when_configured_but_no_runs(_configured, tmp_path, monkeypatch):
    # Point default_store at a fresh sqlite so no prior batch run exists.
    from api.server.eval.store import EvalStore
    fresh = EvalStore(db_path=str(tmp_path / "fresh.sqlite"))
    monkeypatch.setattr("api.server.eval.store._default", fresh)
    monkeypatch.setattr("api.server.routes.accuracy.default_store", lambda: fresh)
    resp = client.get("/api/accuracy/last")
    assert resp.status_code == 404


def test_post_run_rejects_sample_size_above_corpus(_configured):
    resp = client.post("/api/accuracy/run", json={"sample_size": 99999})
    assert resp.status_code == 400
