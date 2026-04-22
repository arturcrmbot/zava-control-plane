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
