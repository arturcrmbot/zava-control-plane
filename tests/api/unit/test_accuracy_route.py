"""Accuracy route tests using FastAPI test client."""
from __future__ import annotations
import time
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from api.server.main import app
from api.server.routes import accuracy as accuracy_route

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


def test_post_run_returns_run_id_and_accepted_status():
    with patch.object(accuracy_route, "_run_harness", AsyncMock(return_value=_fake_report(3))):
        resp = client.post("/api/accuracy/run", json={"sample_size": 3})
    assert resp.status_code == 202
    body = resp.json()
    assert "run_id" in body
    assert body["n"] == 3


def test_get_last_returns_most_recent_complete_report():
    accuracy_route._last_report = None
    fake = _fake_report(3)
    with patch.object(accuracy_route, "_run_harness", AsyncMock(return_value=fake)):
        client.post("/api/accuracy/run", json={"sample_size": 3})
    deadline = time.time() + 5.0
    while time.time() < deadline and accuracy_route._last_report is None:
        time.sleep(0.05)
    resp = client.get("/api/accuracy/last")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["overall_accuracy"] == 1.0


def test_get_last_returns_404_when_no_run_yet(monkeypatch):
    monkeypatch.setattr(accuracy_route, "_last_report", None)
    resp = client.get("/api/accuracy/last")
    assert resp.status_code == 404


def test_post_run_rejects_sample_size_above_corpus():
    resp = client.post("/api/accuracy/run", json={"sample_size": 99999})
    assert resp.status_code == 400
