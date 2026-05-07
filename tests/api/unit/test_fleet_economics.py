import time
import pytest
from fastapi.testclient import TestClient
from api.server.main import app
from api.server.state import app_state
from api.shared.types import Workflow, Vendor, InvoiceData, OtelSpan


@pytest.fixture(autouse=True)
def _isolate_store() -> None:
    # Other unit tests leave workflows in the shared in-memory store; the
    # aggregate rollup is global, so reset before this test to make counts
    # deterministic.
    app_state.store._workflows.clear()
    app_state.store._spans.clear()


def _wf(wid: str, status: str = "in_progress") -> Workflow:
    return Workflow(
        id=wid, status=status,
        created_at=time.time(), sla_due_at=time.time() + 3600,
        vendor=Vendor(id="V", name="V", country="US"),
        invoice=InvoiceData(number="N", amount=1.0, currency="USD", po_ref="P"),
        jurisdiction="US", agency="Ag",
    )


def test_fleet_economics_endpoint_rolls_up_active_only() -> None:
    app_state.store.upsert_workflow(_wf("F-1"))
    app_state.store.upsert_workflow(_wf("F-2", status="awaiting_hitl"))
    app_state.store.upsert_workflow(_wf("F-3", status="completed"))
    for wid in ("F-1", "F-2", "F-3"):
        app_state.store.append_span(OtelSpan(
            trace_id=wid, span_id="s", name="executor.a",
            start_ms=0, end_ms=1000,
            # economics.compute() now derives cost from real OTEL token
            # telemetry rather than counting calls. Stamp gen_ai.* attrs so
            # the rollup produces a non-zero cost we can assert against.
            attributes={
                "workflow.id": wid,
                "executor.type": "agent",
                "gen_ai.system": "github_copilot",
                "gen_ai.request.model": "gpt-4.1",
                "gen_ai.usage.input_tokens": 1000,
                "gen_ai.usage.output_tokens": 500,
            },
        ))
    r = TestClient(app).get("/api/fleet/economics")
    assert r.status_code == 200
    body = r.json()
    # active workflows contribute (F-1 + F-2); completed (F-3) excluded
    assert body["activeWorkflowCount"] == 2
    assert body["totalModelCalls"] == 2
    assert body["totalComputeCostUsd"] > 0.0
    assert body["averageCostPerWorkflow"] == \
        round(body["totalComputeCostUsd"] / 2, 2)
