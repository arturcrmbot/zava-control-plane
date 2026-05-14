from fastapi.testclient import TestClient
from tests.api._helpers.durable_event import signed_post
from api.server.main import app


def test_mcp_call_event_appends_to_store() -> None:
    client = TestClient(app)
    r = signed_post(client, {
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
    # Read the store via the route module, not via a fresh
    # `from api.server.state import app_state` — other tests
    # (notably test_portal_voice) sys.modules.pop the state module and
    # re-import, which mints a new AppState. The route was wired to the
    # original app_state at app-import time, so re-importing here would
    # land us on a different (empty) singleton.
    from api.server.routes.internal_durable_event import app_state
    calls = app_state.store.get_mcp_calls("W-T1")
    assert len(calls) == 1
    assert calls[0].tool == "getVendor"
    assert calls[0].response == {"id": "V-1"}
