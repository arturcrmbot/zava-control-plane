"""Tests for /api/webhooks/finance-bp HMAC signature gate (c5)."""
from __future__ import annotations

import hashlib
import hmac
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


SECRET = "finance-bp-test-secret"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("FINANCE_BP_WEBHOOK_SECRET", SECRET)

    # Stub the durable client so a valid-signature happy-path doesn't try to
    # talk to a real Functions host.
    async def _fake_raise(instance_id, event_name, event_data):
        return None
    monkeypatch.setattr(
        "api.server.routes.webhooks_finance_bp.raise_orchestration_event",
        _fake_raise,
    )

    # Stub workflow lookup → return a workflow with an orchestration instance.
    from api.server.routes import webhooks_finance_bp as mod
    fake_wf = SimpleNamespace(orchestration_instance_id="instance-c5")
    monkeypatch.setattr(
        mod.app_state.store,
        "get_workflow",
        lambda _id: fake_wf,
    )

    from api.server.main import app
    return TestClient(app)


def _sign(body: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_valid_signature_returns_200(client):
    # Body is empty (decision is a query param) so we sign empty bytes.
    r = client.post(
        "/api/webhooks/finance-bp/wf-c5-1?decision=approve",
        headers={"X-Finance-BP-Signature": _sign(b"")},
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "workflow_id": "wf-c5-1", "decision": "approve"}


def test_missing_signature_returns_401(client):
    r = client.post("/api/webhooks/finance-bp/wf-c5-2?decision=approve")
    assert r.status_code == 401
    assert r.json()["detail"] == "missing_signature"


def test_bad_signature_returns_401(client):
    r = client.post(
        "/api/webhooks/finance-bp/wf-c5-3?decision=approve",
        headers={"X-Finance-BP-Signature": "deadbeef" * 8},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid_signature"


def test_signature_with_wrong_secret_returns_401(client):
    r = client.post(
        "/api/webhooks/finance-bp/wf-c5-4?decision=reject",
        headers={"X-Finance-BP-Signature": _sign(b"", "not-the-secret")},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid_signature"


def test_unset_secret_returns_401(monkeypatch):
    monkeypatch.delenv("FINANCE_BP_WEBHOOK_SECRET", raising=False)
    from api.server.main import app
    c = TestClient(app)
    r = c.post(
        "/api/webhooks/finance-bp/wf-c5-5?decision=approve",
        headers={"X-Finance-BP-Signature": _sign(b"", "anything")},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "webhook_secret_not_configured"
