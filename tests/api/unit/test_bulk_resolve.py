import time
from fastapi.testclient import TestClient
from api.server.main import app
from api.server.state import app_state
from api.shared.types import (
    Exception_ as Exception, ExceptionOption, Workflow, Vendor, InvoiceData,
)


def _wf(wid: str) -> Workflow:
    return Workflow(
        id=wid, created_at=time.time(), sla_due_at=time.time() + 3600,
        vendor=Vendor(id="V-1", name="V", country="US"),
        invoice=InvoiceData(number="N", amount=1.0, currency="USD", po_ref="P"),
        jurisdiction="US", agency="Ag",
    )


def test_bulk_resolve_accepts_reroute_gl_action() -> None:
    client = TestClient(app)
    # seed a workflow + an open exception
    app_state.store.upsert_workflow(_wf("W-R1"))
    e = Exception(
        id="EXC-R1", workflow_id="W-R1", composed_by="deterministic",
        severity="high", category="validator-blocked",
        summary="s", recommendation="r", confidence=1.0, created_at=time.time(),
        options=[ExceptionOption(label="Re-route", action="reroute-gl",
                                 recommended=True)],
    )
    app_state.store.upsert_exception(e)
    r = client.post("/api/exceptions/bulk-resolve", json={
        "exceptionIds": ["EXC-R1"],
        "resolution": "reroute-gl",
        "resolvedBy": "controller@wpp",
    })
    assert r.status_code == 200, r.text
    assert r.json()["resolved"] == 1
    assert app_state.store.get_exception("EXC-R1").resolved_at is not None


def test_bulk_resolve_accepts_request_info_action() -> None:
    client = TestClient(app)
    app_state.store.upsert_workflow(_wf("W-R2"))
    e = Exception(
        id="EXC-R2", workflow_id="W-R2", composed_by="deterministic",
        severity="high", category="threshold-exceeded",
        summary="s", recommendation="r", confidence=1.0, created_at=time.time(),
        options=[ExceptionOption(label="Request info", action="request-info")],
    )
    app_state.store.upsert_exception(e)
    r = client.post("/api/exceptions/bulk-resolve", json={
        "exceptionIds": ["EXC-R2"],
        "resolution": "request-info",
        "resolvedBy": "controller@wpp",
    })
    assert r.status_code == 200, r.text
    assert app_state.store.get_exception("EXC-R2").resolved_at is not None
