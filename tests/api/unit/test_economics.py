import time
from api.shared.types import Workflow, OtelSpan, McpCall, Vendor, InvoiceData
from api.server.services.economics import compute


def _wf(wid: str, age_s: float = 100.0) -> Workflow:
    return Workflow(
        id=wid, created_at=time.time() - age_s, sla_due_at=time.time() + 3600,
        vendor=Vendor(id="V-1", name="Vendor", country="US"),
        invoice=InvoiceData(number="N", amount=1.0, currency="USD", po_ref="P"),
        jurisdiction="US", agency="Ag-1",
    )


def test_compute_with_no_activity() -> None:
    w = _wf("W-1", age_s=0.0)
    eco = compute(w, spans=[], mcp_calls=[])
    assert eco["modelCalls"] == 0
    assert eco["toolCalls"] == 0
    assert eco["computeCostUsd"] == 0.0
    assert eco["slaToken"].startswith("SLA-")
    assert eco["daysElapsed"] >= 0.0


def test_compute_accumulates_agent_and_tool_counts() -> None:
    w = _wf("W-2")
    spans = [
        OtelSpan(trace_id="t", span_id=f"s{i}", name="executor.a", start_ms=0, end_ms=1000,
                 attributes={"workflow.id": "W-2", "executor.type": "agent"})
        for i in range(3)
    ] + [
        OtelSpan(trace_id="t", span_id=f"d{i}", name="executor.d", start_ms=0, end_ms=500,
                 attributes={"workflow.id": "W-2", "executor.type": "deterministic"})
        for i in range(2)
    ]
    calls = [
        McpCall(workflow_id="W-2", timestamp=0, tool="t", url="u",
                method="POST", request={}, response={}, status_code=200, duration_ms=5)
        for _ in range(4)
    ]
    eco = compute(w, spans=spans, mcp_calls=calls)
    assert eco["modelCalls"] == 3
    assert eco["toolCalls"] == 4
    assert eco["computeCostUsd"] > 0.0
