import time
from api.shared.types import (
    Workflow, Vendor, InvoiceData, ActionLedgerEntry, Exception_ as Exception
)
from api.server.services.exception_narrative import compose


def _wf() -> Workflow:
    return Workflow(
        id="INV-0001", created_at=time.time(), sla_due_at=time.time() + 3600,
        vendor=Vendor(id="V-1", name="Wayne Enterprises", country="US"),
        invoice=InvoiceData(number="INV-980444", amount=12529.88,
                            currency="USD", po_ref="PO-10004"),
        jurisdiction="US", agency="Ogilvy-US", current_phase="Routing",
    )


def _exc(category: str) -> Exception:
    return Exception(
        id="EXC-1", workflow_id="INV-0001", composed_by="deterministic",
        severity="high", category=category,
        summary="Validator 'validate_gl_active' blocked workflow",
        recommendation="Re-route to a GL specialist",
        confidence=1.0, created_at=time.time(),
    )


def test_compose_validator_blocked() -> None:
    w = _wf()
    exc = _exc("validator-blocked")
    ledger = [
        ActionLedgerEntry(workflow_id=w.id, timestamp=time.time(),
                          actor_kind="agent", actor_id="phase:Intake",
                          action="phase.completed:Intake", revocable=False, details={}),
        ActionLedgerEntry(workflow_id=w.id, timestamp=time.time(),
                          actor_kind="agent", actor_id="validator:validate_gl_active",
                          action="validator.blocked", revocable=False,
                          details={"reason": "GL-9999 not in active set"}),
    ]
    n = compose(w, exc, ledger)
    assert "Wayne Enterprises" in n["whatHappened"]
    assert "12,529.88" in n["whatHappened"] or "12529.88" in n["whatHappened"]
    assert len(n["whatAgentTried"]) >= 1
    assert "GL specialist" in n["agentRecommendation"] or \
           "Re-route" in n["agentRecommendation"]


def test_compose_threshold_exceeded() -> None:
    w = _wf()
    exc = _exc("threshold-exceeded")
    exc.summary = "Amount exceeds threshold for Ogilvy-US"
    exc.recommendation = "Escalate to L2 approver"
    n = compose(w, exc, ledger=[])
    assert n["whatHappened"]
    assert isinstance(n["whatAgentTried"], list)
    assert "L2" in n["agentRecommendation"] or "Escalate" in n["agentRecommendation"]
