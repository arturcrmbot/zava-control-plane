"""claim.lookup MCP tool tests — uses monkeypatch over httpx.post."""
from __future__ import annotations
import json
from pathlib import Path

import httpx
import pytest

from api.server.mcp_tools import claim_lookup


SYNTHETIC = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "claims"


def _pick_claim_with(ems: str) -> str:
    for path in sorted(SYNTHETIC.glob("CLM-*.json")):
        c = json.loads(path.read_text(encoding="utf-8"))
        if c.get("ems_source") == ems:
            return c["claim_id"]
    raise RuntimeError(f"no synthetic claim with ems_source={ems}")


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)  # type: ignore[arg-type]


def test_lookup_dispatches_to_workday_via_synthetic_ems_field(monkeypatch):
    monkeypatch.setenv("WORKDAY_MCP_PORT", "4101")
    cid = _pick_claim_with("workday")
    expected = {"claim_id": cid, "ems_source": "workday", "amount": 42.0, "category": "meals"}

    captured: dict = {}

    def fake_post(url, json=None, timeout=None, **kwargs):
        captured["url"] = url
        captured["json"] = json
        return _FakeResponse(200, expected)

    monkeypatch.setattr(httpx, "post", fake_post)
    out = claim_lookup.lookup(cid)
    assert out == expected
    assert captured["url"] == "http://127.0.0.1:4101/mcp/call/getExpenseClaim"
    assert captured["json"] == {"claimId": cid}


def test_lookup_explicit_workday_overrides_synthetic_lookup(monkeypatch):
    monkeypatch.setenv("WORKDAY_MCP_PORT", "4101")
    cid = "CLM-NOT-IN-CORPUS"  # explicit ems means we don't read synthetic
    expected = {"claim_id": cid, "ems_source": "workday"}

    def fake_post(url, json=None, timeout=None, **kwargs):
        return _FakeResponse(200, expected)

    monkeypatch.setattr(httpx, "post", fake_post)
    out = claim_lookup.lookup(cid, ems_source="workday")
    assert out["claim_id"] == cid


def test_lookup_concur_dispatches_via_oauth_bearer(monkeypatch):
    """Concur dispatch hits getExpenseLine on CONCUR_MCP_PORT with a Bearer
    header, then unwraps the `_normalised` payload."""
    monkeypatch.setenv("CONCUR_MCP_PORT", "4102")
    cid = _pick_claim_with("concur")
    normalised = {"claim_id": cid, "ems_source": "concur", "amount": 88.0, "category": "travel"}
    concur_response = {
        "reportItemId": cid, "submitter": "EMP-1",
        "totalAmount": 88.0, "currencyCode": "USD",
        "_normalised": normalised,
    }
    captured: dict = {}

    def fake_post(url, json=None, headers=None, timeout=None, **kwargs):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers or {}
        return _FakeResponse(200, concur_response)

    monkeypatch.setattr(httpx, "post", fake_post)
    out = claim_lookup.lookup(cid)
    assert out == normalised
    assert captured["url"] == "http://127.0.0.1:4102/mcp/call/getExpenseLine"
    assert captured["json"] == {"reportItemId": cid}
    auth = captured["headers"].get("Authorization", "")
    assert auth.lower().startswith("bearer "), auth


def test_lookup_explicit_concur_uses_concur_dispatch(monkeypatch):
    monkeypatch.setenv("CONCUR_MCP_PORT", "4102")
    normalised = {"claim_id": "CLM-XXXX", "ems_source": "concur"}

    def fake_post(url, json=None, headers=None, timeout=None, **kwargs):
        return _FakeResponse(200, {"_normalised": normalised})

    monkeypatch.setattr(httpx, "post", fake_post)
    out = claim_lookup.lookup("CLM-XXXX", ems_source="concur")
    assert out == normalised


def test_lookup_concur_404_raises_key_error(monkeypatch):
    monkeypatch.setenv("CONCUR_MCP_PORT", "4102")
    cid = _pick_claim_with("concur")

    def fake_post(url, json=None, headers=None, timeout=None, **kwargs):
        return _FakeResponse(404, {"error": "expense_line_not_found"})

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(KeyError):
        claim_lookup.lookup(cid)


def test_lookup_unknown_claim_id_raises_key_error():
    with pytest.raises(KeyError):
        claim_lookup.lookup("CLM-9999")


def test_lookup_propagates_remote_404_as_key_error(monkeypatch):
    monkeypatch.setenv("WORKDAY_MCP_PORT", "4101")
    cid = _pick_claim_with("workday")

    def fake_post(url, json=None, timeout=None, **kwargs):
        return _FakeResponse(404, {"error": "claim_not_found"})

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(KeyError):
        claim_lookup.lookup(cid)


def test_lookup_uses_workday_port_env_var(monkeypatch):
    monkeypatch.setenv("WORKDAY_MCP_PORT", "4499")
    cid = _pick_claim_with("workday")
    captured: dict = {}

    def fake_post(url, json=None, timeout=None, **kwargs):
        captured["url"] = url
        return _FakeResponse(200, {"claim_id": cid, "ems_source": "workday"})

    monkeypatch.setattr(httpx, "post", fake_post)
    claim_lookup.lookup(cid)
    assert "4499" in captured["url"]
