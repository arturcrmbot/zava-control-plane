"""Tests for deterministic exception composition and Fleet Manager augmentation."""
from __future__ import annotations
import time
from api.server.services.state_store import StateStore
from api.server.services.exception_factory import (
    compose_hitl_exception, compose_validator_exception
)
from api.server.mcp_tools.compose_exception import _find_open_exception_for_workflow
from api.shared.types import Workflow, Vendor, InvoiceData


def _mk_workflow(store: StateStore, wid: str) -> None:
    store.upsert_workflow(Workflow(
        id=wid,
        created_at=time.time(), sla_due_at=time.time() + 3600,
        vendor=Vendor(id="V-001", name="Acme", country="US"),
        invoice=InvoiceData(number="INV-001", amount=1000, currency="USD", po_ref="PO-10001"),
        jurisdiction="US-CA", agency="Ogilvy-US",
    ))


def test_compose_hitl_exception_creates_deterministic_record():
    s = StateStore()
    _mk_workflow(s, "WF-1")
    e = compose_hitl_exception(s, "WF-1", "amount above auto-approve threshold")
    assert e.workflow_id == "WF-1"
    assert e.composed_by == "deterministic"
    assert e.category == "threshold-exceeded"
    assert e.severity == "medium"
    assert e.confidence == 1.0
    assert e.related_policy_refs == []
    actions = sorted(o.action for o in e.options)
    assert actions == ["approve", "reject"]
    # Persisted and discoverable via list_exceptions
    assert s.get_exception(e.id) is e
    assert e in s.list_exceptions()


def test_compose_validator_exception_creates_deterministic_record():
    s = StateStore()
    _mk_workflow(s, "WF-2")
    e = compose_validator_exception(s, "WF-2", "sanctions-screen", "vendor flagged")
    assert e.workflow_id == "WF-2"
    assert e.composed_by == "deterministic"
    assert e.category == "validator-blocked"
    assert e.severity == "high"
    assert e.confidence == 1.0
    assert "sanctions-screen" in e.summary
    assert s.get_exception(e.id) is e


def test_find_open_exception_returns_most_recent_for_workflow():
    s = StateStore()
    _mk_workflow(s, "WF-3")
    _mk_workflow(s, "WF-4")
    e1 = compose_hitl_exception(s, "WF-3", "first")
    # Ensure distinct created_at ordering
    e1.created_at = time.time() - 10
    s.upsert_exception(e1)
    e2 = compose_validator_exception(s, "WF-3", "dup-check", "second")
    e_other = compose_hitl_exception(s, "WF-4", "unrelated")
    found = _find_open_exception_for_workflow(s, "WF-3")
    assert found is not None
    assert found.id == e2.id
    # Resolved ones are excluded
    s.resolve_exception(e2.id, "tester")
    found2 = _find_open_exception_for_workflow(s, "WF-3")
    assert found2 is not None
    assert found2.id == e1.id
    # Unrelated workflow still finds its own
    assert _find_open_exception_for_workflow(s, "WF-4").id == e_other.id
    # No exception yet for unknown workflow
    assert _find_open_exception_for_workflow(s, "WF-NONE") is None


def test_deterministic_factory_does_not_duplicate_store_entries():
    """One factory call -> exactly one exception in the store."""
    s = StateStore()
    _mk_workflow(s, "WF-5")
    before = len(s.list_exceptions())
    e = compose_hitl_exception(s, "WF-5", "threshold")
    after = len(s.list_exceptions())
    assert after - before == 1
    # Workflow's active_exception_id is now set
    assert s.get_workflow("WF-5").active_exception_id == e.id
