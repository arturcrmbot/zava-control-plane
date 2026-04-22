import time
from fastapi.testclient import TestClient
from api.server.main import app
from api.server.state import app_state
from api.shared.types import (
    Workflow, Vendor, InvoiceData, McpCall, Exception_ as Exception,
)


def _seed(wid: str) -> None:
    app_state.store.upsert_workflow(Workflow(
        id=wid, created_at=time.time(), sla_due_at=time.time() + 3600,
        vendor=Vendor(id="V-1", name="Wayne Enterprises", country="US"),
        invoice=InvoiceData(number="INV-1", amount=12.0, currency="USD", po_ref="P"),
        jurisdiction="US", agency="Ogilvy-US",
    ))
    app_state.store.append_mcp_call(McpCall(
        workflow_id=wid, timestamp=time.time(),
        tool="getVendor", url="http://wd/mcp/call/getVendor",
        method="POST", request={"id": "V-1"}, response={},
        status_code=200, duration_ms=5,
    ))


def test_detail_response_includes_economics_and_mcpcalls() -> None:
    client = TestClient(app)
    _seed("W-DET-1")
    r = client.get("/api/workflows/W-DET-1")
    assert r.status_code == 200
    body = r.json()
    assert "economics" in body
    assert body["economics"]["toolCalls"] >= 1
    assert "mcpCalls" in body
    assert len(body["mcpCalls"]) >= 1
    assert body["mcpCalls"][0]["tool"] == "getVendor"


def test_detail_response_includes_narrative_when_exception_present() -> None:
    client = TestClient(app)
    wid = "W-DET-2"
    _seed(wid)
    exc = Exception(
        id="EXC-N", workflow_id=wid, composed_by="deterministic",
        severity="high", category="validator-blocked",
        summary="blocked test", recommendation="retry",
        confidence=1.0, created_at=time.time(),
    )
    app_state.store.upsert_exception(exc)
    r = client.get(f"/api/workflows/{wid}")
    assert r.status_code == 200
    body = r.json()
    assert "narrative" in body and body["narrative"] is not None
    assert "whatHappened" in body["narrative"]
    assert "whatAgentTried" in body["narrative"]
