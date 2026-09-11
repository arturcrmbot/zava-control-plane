from __future__ import annotations

import base64
import json

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api.server.services.read_route_auth import Actor, require_actor


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("READ_ROUTE_AUTH", "platform")
    monkeypatch.setenv("AUTH_TENANT_ID", "tenant-1")
    app = FastAPI()

    @app.get("/actor")
    async def actor(value: Actor = Depends(require_actor)):
        return {"id": value.id, "role": value.role}

    return TestClient(app)


def principal(*, tenant="tenant-1", role="Zava.CFO", oid="person-1"):
    value = {
        "auth_typ": "aad",
        "role_typ": "roles",
        "claims": [
            {"typ": "tid", "val": tenant},
            {"typ": "oid", "val": oid},
            {"typ": "roles", "val": role},
        ],
    }
    return base64.b64encode(json.dumps(value).encode()).decode()


def test_platform_mode_uses_injected_identity_not_caller_role_headers(client):
    response = client.get("/actor", headers={
        "X-MS-CLIENT-PRINCIPAL": principal(),
        "X-Actor-Id": "spoofed",
        "X-Actor-Role": "gc",
    })
    assert response.status_code == 200
    assert response.json() == {"id": "person-1", "role": "cfo"}


def test_platform_mode_does_not_accept_legacy_headers_as_authentication(client):
    response = client.get("/actor", headers={"X-Actor-Id": "someone", "X-Actor-Role": "cfo"})
    assert response.status_code == 401


def test_platform_mode_rejects_a_different_tenant(client):
    response = client.get("/actor", headers={"X-MS-CLIENT-PRINCIPAL": principal(tenant="other")})
    assert response.status_code == 403


@pytest.mark.parametrize("value", ["not-base64", base64.b64encode(b"[]").decode()])
def test_platform_mode_rejects_malformed_identity(client, value):
    assert client.get("/actor", headers={"X-MS-CLIENT-PRINCIPAL": value}).status_code == 401


def test_unassigned_role_cannot_be_promoted_by_a_caller_header(client):
    response = client.get("/actor", headers={
        "X-MS-CLIENT-PRINCIPAL": principal(role="unrelated-role"),
        "X-Actor-Role": "cfo",
    })
    assert response.status_code == 200
    assert response.json()["role"] == "viewer"


def test_missing_tenant_configuration_fails_closed(client, monkeypatch):
    monkeypatch.delenv("AUTH_TENANT_ID")
    response = client.get("/actor", headers={"X-MS-CLIENT-PRINCIPAL": principal()})
    assert response.status_code == 503
