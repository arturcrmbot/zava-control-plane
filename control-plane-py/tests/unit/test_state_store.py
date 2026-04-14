import time
from src.server.services.state_store import StateStore
from src.shared.types import Workflow, Vendor, InvoiceData, ActionLedgerEntry


def mk_workflow(id: str, **overrides) -> Workflow:
    base = dict(
        id=id, created_at=time.time(), sla_due_at=time.time() + 3600,
        vendor=Vendor(id="V-001", name="Acme", country="US"),
        invoice=InvoiceData(number="INV-001", amount=1000, currency="USD", po_ref="PO-10001"),
        jurisdiction="US-CA", agency="Ogilvy-US",
    )
    base.update(overrides)
    return Workflow(**base)


def test_upsert_and_get():
    s = StateStore()
    s.upsert_workflow(mk_workflow("A"))
    assert s.get_workflow("A").id == "A"


def test_list_with_filters():
    s = StateStore()
    s.upsert_workflow(mk_workflow("A", status="awaiting_hitl"))
    s.upsert_workflow(mk_workflow("B", status="completed"))
    awaiting = s.list_workflows(status="awaiting_hitl")
    assert len(awaiting) == 1
    assert awaiting[0].id == "A"


def test_append_ledger():
    s = StateStore()
    s.upsert_workflow(mk_workflow("A"))
    s.append_ledger("A", ActionLedgerEntry(
        workflow_id="A", timestamp=1, actor_kind="agent",
        actor_id="finance-agent", action="intake.started",
        revocable=True, details={}
    ))
    assert len(s.get_workflow("A").action_ledger) == 1
