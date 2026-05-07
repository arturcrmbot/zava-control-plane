"""Tests for the registry surface routes (Phase 7 of feature-authority-and-personae-1).

Two routers covered:
  - api/server/routes/personas.py  (read-only PERSONAS surface)
  - api/server/routes/authority.py (proxies to delegated_authority MCP +
    matrix.json read-through)
"""
from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    # Lazy import so module import doesn't pay the FastAPI startup cost
    # when other tests are selected.
    from api.server.main import app
    return TestClient(app)


# --------------------------------------------------------------------------
# /api/personas
# --------------------------------------------------------------------------


def test_list_personas_returns_full_registry(client):
    r = client.get("/api/personas")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 27
    assert "by_archetype" in body and "by_function" in body
    assert body["by_archetype"]["approver"] >= 10
    # Phase 4 + Phase 6 personae using the authority MCP:
    assert body["uses_authority_mcp"] >= 15
    roles = {item["role"] for item in body["items"]}
    assert {"finance_bp", "ssc_reviewer", "controller", "dpo", "gc"} <= roles


def test_personas_by_archetype(client):
    r = client.get("/api/personas/by-archetype")
    assert r.status_code == 200
    body = r.json()
    assert "approver" in body and "subject" in body
    approvers = [p["role"] for p in body["approver"]]
    assert "finance_bp" in approvers and "controller" in approvers


def test_personas_by_function(client):
    r = client.get("/api/personas/by-function")
    assert r.status_code == 200
    body = r.json()
    assert "finance" in body and "procurement" in body and "legal" in body
    finance = [p["role"] for p in body["finance"]]
    assert "controller" in finance and "ssc_reviewer" in finance


def test_get_single_persona(client):
    r = client.get("/api/personas/controller")
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "controller"
    assert body["scope_function"] == "finance"
    assert body["uses_authority_mcp"] is True


def test_get_unknown_persona_404s(client):
    r = client.get("/api/personas/not_a_real_role")
    assert r.status_code == 404


# --------------------------------------------------------------------------
# /api/authority/matrix (no MCP needed — reads from disk)
# --------------------------------------------------------------------------


def test_matrix_read_through(client):
    r = client.get("/api/authority/matrix")
    assert r.status_code == 200
    body = r.json()
    assert body["rule_count"] >= 80
    assert "expense_claim_approval" in body["actions"]
    assert "vendor_kyc_signoff" in body["actions"]
    assert isinstance(body["rules"], list)
    assert all("rule_id" in r for r in body["rules"][:5])


# --------------------------------------------------------------------------
# /api/authority/resolve + /api/authority/check (mock the underlying httpx)
# --------------------------------------------------------------------------


def _stub_post(handler):
    def _post(url, json=None, timeout=None, **kwargs):
        request = httpx.Request("POST", url, json=json)
        response = handler(request)
        response.request = request
        return response
    return _post


def test_authority_resolve_route(client, monkeypatch):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json
        captured["body"] = _json.loads(request.content)
        return httpx.Response(200, json={
            "matched": True,
            "approver_role": "ssc_reviewer",
            "threshold_gbp": 2500,
            "escalation_chain": ["finance_controller"],
            "rule_id": "EXP-003",
            "basis": "Material meals expense.",
        })

    import api.server.mcp_tools.delegated_authority as da
    # Force the HTTP fallback path so the httpx mock is observable
    # (Phase 3 TASK-022 default backend is in-process).
    monkeypatch.setenv("AUTHORITY_MCP_URL", "http://127.0.0.1:4108")
    monkeypatch.setattr(da.httpx, "post", _stub_post(handler))

    r = client.post("/api/authority/resolve", json={
        "action": "expense_claim_approval", "category": "meals", "value": 1000,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["matched"] is True
    assert body["approver_role"] == "ssc_reviewer"
    assert captured["body"]["action"] == "expense_claim_approval"


def test_authority_check_route(client, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "allowed": True,
            "reason": "primary",
            "governing_rule_id": "EXP-003",
        })

    import api.server.mcp_tools.delegated_authority as da
    # Force the HTTP fallback path so the httpx mock is observable
    # (Phase 3 TASK-022 default backend is in-process).
    monkeypatch.setenv("AUTHORITY_MCP_URL", "http://127.0.0.1:4108")
    monkeypatch.setattr(da.httpx, "post", _stub_post(handler))

    r = client.post("/api/authority/check", json={
        "role": "ssc_reviewer", "action": "expense_claim_approval",
        "category": "meals", "value": 1000,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["allowed"] is True
    assert body["governing_rule_id"] == "EXP-003"
