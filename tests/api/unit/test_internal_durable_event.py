from fastapi.testclient import TestClient
from api.server.main import app


def test_mcp_call_event_appends_to_store() -> None:
    client = TestClient(app)
    r = client.post("/internal/durable-event", json={
        "workflow_id": "W-T1",
        "instance_id": "I-T1",
        "kind": "mcp.call",
        "payload": {
            "tool": "getVendor",
            "url": "http://wd/mcp/call/getVendor",
            "method": "POST",
            "request": {"vendorId": "V-1"},
            "response": {"id": "V-1"},
            "status_code": 200,
            "duration_ms": 11,
        },
    })
    assert r.status_code == 200
    from api.server.state import app_state
    calls = app_state.store.get_mcp_calls("W-T1")
    assert len(calls) == 1
    assert calls[0].tool == "getVendor"
    assert calls[0].response == {"id": "V-1"}
