"""Coverage for the read-route actor gate (task c6-audit-evals-entities-authz).

Verifies enforce mode: 401 without ``X-Actor-Id``, 200 with one — for at
least one endpoint per protected route file (audit, evals, entities,
cities). Default-mode behaviour is exercised by the existing per-route
tests (e.g. test_cities.py, test_entities_*.py) which still pass without
sending the header.

Also verifies the per-role projector redacts ``prompt`` / ``response``
shaped fields on audit payloads for non-privileged roles, and leaves
them intact for ``cfo`` / ``gc``.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.server.main import app
from api.server.services.read_route_auth import project_for_role
from api.server.state import app_state


client = TestClient(app)


@pytest.fixture
def enforce(monkeypatch):
    monkeypatch.setenv("READ_ROUTE_AUTH", "enforce")
    yield


# --- Enforce-mode 401 / 200 for one endpoint per file ----------------------


@pytest.mark.parametrize(
    "path",
    [
        "/api/audit",
        "/api/evals/health",
        "/api/entities/_pulse",
        "/api/cities",
    ],
)
def test_enforce_mode_rejects_unauthenticated(enforce, path):
    r = client.get(path)
    assert r.status_code == 401, f"{path} returned {r.status_code}: {r.text}"
    assert "missing_actor" in r.json()["detail"]


@pytest.mark.parametrize(
    "path",
    [
        "/api/audit",
        "/api/evals/health",
        "/api/entities/_pulse",
        "/api/cities",
    ],
)
def test_enforce_mode_accepts_actor_header(enforce, path):
    r = client.get(path, headers={"X-Actor-Id": "u-1", "X-Actor-Role": "viewer"})
    assert r.status_code == 200, f"{path} returned {r.status_code}: {r.text}"


# --- Default mode: no header required (legacy ergonomics) ------------------


def test_default_mode_allows_no_header(monkeypatch):
    # No READ_ROUTE_AUTH env → handler stamps "local-dev" and serves.
    monkeypatch.delenv("READ_ROUTE_AUTH", raising=False)
    r = client.get("/api/cities")
    assert r.status_code == 200


# --- Per-role projector ----------------------------------------------------


def test_project_for_role_redacts_for_non_privileged():
    payload = [
        {
            "action": "persona.responded",
            "details": {
                "persona": "ap_clerk",
                "prompt": "raw prompt body",
                "response": "raw response body",
                "nested": {"prompt_text": "deeper", "ok": 1},
            },
        }
    ]
    out = project_for_role(payload, "viewer")
    assert out[0]["details"]["prompt"] == "[redacted]"
    assert out[0]["details"]["response"] == "[redacted]"
    assert out[0]["details"]["nested"]["prompt_text"] == "[redacted]"
    assert out[0]["details"]["nested"]["ok"] == 1
    assert out[0]["details"]["persona"] == "ap_clerk"


def test_project_for_role_passthrough_for_cfo():
    payload = {"prompt": "raw", "response": "raw"}
    out = project_for_role(payload, "cfo")
    assert out["prompt"] == "raw"
    assert out["response"] == "raw"


def test_audit_endpoint_redacts_for_non_privileged_role():
    # Inject one synthetic entry carrying prompt/response into the live
    # audit list, then verify the projector kicks in for a non-privileged
    # role and is bypassed for cfo. Cleans up after itself so other audit
    # tests aren't polluted.
    entries = app_state.audit.list()
    baseline = len(entries)
    app_state.audit._entries.append({
        "action": "test.entry",
        "details": {"prompt": "secret-prompt", "response": "secret-response"},
        "timestamp": 0.0,
    })
    try:
        r1 = client.get("/api/audit", headers={"X-Actor-Role": "viewer"})
        assert r1.status_code == 200
        latest = r1.json()[-1]
        assert latest["details"]["prompt"] == "[redacted]"
        assert latest["details"]["response"] == "[redacted]"

        r2 = client.get("/api/audit", headers={"X-Actor-Role": "cfo"})
        assert r2.status_code == 200
        latest2 = r2.json()[-1]
        assert latest2["details"]["prompt"] == "secret-prompt"
        assert latest2["details"]["response"] == "secret-response"
    finally:
        app_state.audit._entries.pop()
        assert len(app_state.audit.list()) == baseline
