"""Tests for /internal/durable-event HMAC signature gate (c4).

Mirrors the c5 webhook tests' style — same env-var-set / sign / post pattern.
The route accepts arbitrary workflow_id/kind/payload, so this gate is the
only thing standing between an exposed substrate and arbitrary durable
orchestration drivers.
"""
from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient


SECRET = "durable-event-test-secret"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DURABLE_EVENT_SECRET", SECRET)
    from api.server.main import app
    return TestClient(app)


def _sign(body: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _payload() -> bytes:
    # mcp.call kind is a leaf path that doesn't compose any HITL exception
    # or mutate the workflow store beyond appending an MCP call — keeps the
    # test focused on the auth gate.
    return json.dumps({
        "workflow_id": "W-HMAC-1",
        "instance_id": None,
        "kind": "mcp.call",
        "payload": {
            "tool": "noop",
            "url": "http://example/mcp/noop",
            "method": "POST",
            "request": {},
            "response": {},
            "status_code": 200,
            "duration_ms": 1,
        },
    }).encode("utf-8")


def test_valid_signature_returns_200(client):
    body = _payload()
    r = client.post(
        "/internal/durable-event",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Durable-Event-Signature": _sign(body),
        },
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"received": True}


def test_valid_signature_with_sha256_prefix_returns_200(client):
    body = _payload()
    r = client.post(
        "/internal/durable-event",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Durable-Event-Signature": "sha256=" + _sign(body),
        },
    )
    assert r.status_code == 200, r.text


def test_missing_signature_returns_401(client):
    r = client.post(
        "/internal/durable-event",
        content=_payload(),
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "missing_signature"


def test_bad_signature_returns_401(client):
    r = client.post(
        "/internal/durable-event",
        content=_payload(),
        headers={
            "Content-Type": "application/json",
            "X-Durable-Event-Signature": "deadbeef" * 8,
        },
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid_signature"


def test_signature_over_different_body_returns_401(client):
    # Sign a different body than the one we send → tampered request.
    other = json.dumps({
        "workflow_id": "OTHER",
        "kind": "mcp.call",
        "payload": {},
    }).encode("utf-8")
    r = client.post(
        "/internal/durable-event",
        content=_payload(),
        headers={
            "Content-Type": "application/json",
            "X-Durable-Event-Signature": _sign(other),
        },
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid_signature"


def test_secret_unset_returns_401(monkeypatch):
    monkeypatch.delenv("DURABLE_EVENT_SECRET", raising=False)
    from api.server.main import app
    c = TestClient(app)
    body = _payload()
    r = c.post(
        "/internal/durable-event",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Durable-Event-Signature": _sign(body, "anything"),
        },
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "webhook_secret_not_configured"
