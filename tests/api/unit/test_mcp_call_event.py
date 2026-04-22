from api.server.services.state_store import StateStore
from api.shared.types import McpCall


def test_append_and_get_mcp_calls() -> None:
    store = StateStore()
    call = McpCall(
        workflow_id="W-1", timestamp=1.0,
        tool="getVendor", url="http://x/mcp/call/getVendor",
        method="POST", request={"vendorId": "V-1"},
        response={"id": "V-1"}, status_code=200, duration_ms=42,
    )
    store.append_mcp_call(call)
    got = store.get_mcp_calls("W-1")
    assert len(got) == 1
    assert got[0].tool == "getVendor"
    assert got[0].status_code == 200
    # workflow isolation
    assert store.get_mcp_calls("W-2") == []


import pytest


@pytest.mark.asyncio
async def test_call_mcp_emits_webhook(monkeypatch) -> None:
    from api.functions.graphs import _common

    # Fake httpx.AsyncClient: returns a dummy 200 response.
    class FakeResp:
        status_code = 200
        is_success = True
        text = ""
        def json(self): return {"id": "V-1"}

    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json, timeout): return FakeResp()

    monkeypatch.setattr(_common, "httpx", type("_", (), {"AsyncClient": FakeClient}))

    emitted: list[dict] = []
    async def fake_emit(wid, iid, kind, payload):
        emitted.append({"wid": wid, "iid": iid, "kind": kind, "payload": payload})
    monkeypatch.setattr("api.functions.webhook.emit", fake_emit)

    result = await _common.call_mcp(
        "http://mcp", "getVendor", {"vendorId": "V-1"},
        workflow_id="W-1", instance_id="I-1",
    )
    assert result == {"id": "V-1"}
    assert len(emitted) == 1
    e = emitted[0]
    assert e["kind"] == "mcp.call"
    assert e["wid"] == "W-1"
    assert e["payload"]["tool"] == "getVendor"
    assert e["payload"]["status_code"] == 200
    assert e["payload"]["method"] == "POST"
    assert e["payload"]["request"] == {"vendorId": "V-1"}
    assert "duration_ms" in e["payload"]
