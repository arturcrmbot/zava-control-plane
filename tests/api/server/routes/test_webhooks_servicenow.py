"""Tests for /api/webhooks/servicenow HMAC signature gate (c5)."""
from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient


SECRET = "servicenow-test-secret"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SERVICENOW_WEBHOOK_SECRET", SECRET)
    from api.server.main import app
    return TestClient(app)


def _sign(body: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _payload() -> bytes:
    # workflow_id=None keeps the route a pure no-op so we don't need to seed
    # app_state. The signature gate runs first either way.
    return json.dumps({
        "incident_id": "INC-c5-1",
        "status": "comment",
        "note": "hello",
    }).encode("utf-8")


def test_valid_signature_returns_200(client):
    body = _payload()
    r = client.post(
        "/api/webhooks/servicenow",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-ServiceNow-Signature": _sign(body),
        },
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "ignored": "no_workflow_correlation"}


def test_valid_signature_with_sha256_prefix_returns_200(client):
    body = _payload()
    r = client.post(
        "/api/webhooks/servicenow",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-ServiceNow-Signature": "sha256=" + _sign(body),
        },
    )
    assert r.status_code == 200, r.text


def test_missing_signature_returns_401(client):
    r = client.post(
        "/api/webhooks/servicenow",
        content=_payload(),
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "missing_signature"


def test_bad_signature_returns_401(client):
    r = client.post(
        "/api/webhooks/servicenow",
        content=_payload(),
        headers={
            "Content-Type": "application/json",
            "X-ServiceNow-Signature": "deadbeef" * 8,
        },
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid_signature"


def test_signature_over_different_body_returns_401(client):
    # Sign a different body than the one we send → tampered request.
    other = json.dumps({"incident_id": "OTHER", "status": "comment"}).encode("utf-8")
    r = client.post(
        "/api/webhooks/servicenow",
        content=_payload(),
        headers={
            "Content-Type": "application/json",
            "X-ServiceNow-Signature": _sign(other),
        },
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid_signature"


def test_unset_secret_returns_401(monkeypatch):
    monkeypatch.delenv("SERVICENOW_WEBHOOK_SECRET", raising=False)
    from api.server.main import app
    c = TestClient(app)
    body = _payload()
    r = c.post(
        "/api/webhooks/servicenow",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-ServiceNow-Signature": _sign(body, "anything"),
        },
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "webhook_secret_not_configured"
