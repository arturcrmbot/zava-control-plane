"""Phase 7 TASK-053 — kernel decision registry + audit-chain resolution.

Asserts:

- Every Decision returned by ``evaluate_tool_call`` is recorded in the
  in-process registry and re-fetchable via ``resolve_decision``.
- The registry honours its FIFO eviction cap.
- ``AuditLogger.verify_chain`` flips ``decisions_resolvable`` to False
  when a chain contains a decision_id the kernel doesn't know about,
  and returns True for chains with zero decision_ids.
- When the recorded ``policy_version`` differs from the kernel's, the
  entry is unresolved.
"""
from __future__ import annotations

import os

# Same Azurite-probe short-circuit as the rest of the governance suite.
os.environ.setdefault("AZURE_STORAGE_CONNECTION_STRING", "")

import pytest

from api.server.services.audit_logger import AuditLogger
from api.server.services.governance import kernel
from api.server.services.governance.kernel import _reset_for_tests


@pytest.fixture(autouse=True)
def _fresh_kernel():
    _reset_for_tests()
    yield
    _reset_for_tests()


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_evaluate_tool_call_registers_decision() -> None:
    k = kernel()
    decision = k.evaluate_tool_call(
        actor="rag-classifier", tool="claim.lookup", args={}, workflow_id="WF-1"
    )
    assert k.resolve_decision(decision.decision_id) is decision


def test_resolve_decision_returns_none_for_unknown_id() -> None:
    assert kernel().resolve_decision("not-a-real-decision-id") is None


def test_resolve_decision_handles_blank_input() -> None:
    assert kernel().resolve_decision("") is None
    assert kernel().resolve_decision(None) is None  # type: ignore[arg-type]


def test_registry_evicts_in_fifo_order(monkeypatch) -> None:
    monkeypatch.setenv("AGT_DECISION_REGISTRY_MAX", "3")
    _reset_for_tests()
    k = kernel()
    decisions = [
        k.evaluate_tool_call(
            actor="rag-classifier", tool="claim.lookup", args={}, workflow_id="WF-X"
        )
        for _ in range(5)
    ]
    # Cap is 3, so the oldest two should have been evicted.
    assert k.decision_registry_size == 3
    assert k.resolve_decision(decisions[0].decision_id) is None
    assert k.resolve_decision(decisions[1].decision_id) is None
    assert k.resolve_decision(decisions[2].decision_id) is decisions[2]
    assert k.resolve_decision(decisions[-1].decision_id) is decisions[-1]


# ---------------------------------------------------------------------------
# verify_chain — decisions_resolvable
# ---------------------------------------------------------------------------


def test_verify_chain_decisions_resolvable_true_for_chain_without_decision_ids() -> None:
    """Chains with zero governance decision_ids are vacuously resolvable."""
    log = AuditLogger()
    for i in range(3):
        log.log("act", {"workflow_id": "WF-NO-GOV", "i": i})
    report = log.verify_chain("WF-NO-GOV")
    assert report.decisions_resolvable is True
    assert report.unresolved_decisions_at is None


def test_verify_chain_resolves_real_decision_id() -> None:
    """When a decision_id from the kernel actually appears in an entry,
    verify_chain resolves it and decisions_resolvable stays True."""
    decision = kernel().evaluate_tool_call(
        actor="rag-classifier", tool="claim.lookup", args={}, workflow_id="WF-OK"
    )

    log = AuditLogger()
    log.log("mcp.call", {
        "workflow_id": "WF-OK",
        "tool": "claim.lookup",
        "governance": {
            "decision_id": decision.decision_id,
            "policy_version": decision.policy_version,
            "allowed": decision.allowed,
        },
    })
    report = log.verify_chain("WF-OK")
    assert report.chain_intact is True
    assert report.decisions_resolvable is True
    assert report.unresolved_decisions_at is None


def test_verify_chain_flags_unknown_decision_id() -> None:
    """A decision_id the kernel has no record of fails resolution."""
    log = AuditLogger()
    log.log("mcp.call", {
        "workflow_id": "WF-BAD",
        "tool": "claim.lookup",
        "governance": {
            "decision_id": "00000000-0000-0000-0000-deadbeefdead",
            "policy_version": "abcdef012345",
        },
    })
    report = log.verify_chain("WF-BAD")
    assert report.chain_intact is True
    assert report.decisions_resolvable is False
    assert report.unresolved_decisions_at == [0]
    assert "decision" not in (report.reason or "")  # reason is for chain breaks


def test_verify_chain_flags_policy_version_mismatch() -> None:
    """Decision_id resolves but recorded policy_version differs from
    what the kernel has on file → entry counts as unresolved (tamper
    or stale-bundle indicator)."""
    decision = kernel().evaluate_tool_call(
        actor="rag-classifier", tool="claim.lookup", args={}, workflow_id="WF-PV"
    )

    log = AuditLogger()
    log.log("mcp.call", {
        "workflow_id": "WF-PV",
        "tool": "claim.lookup",
        "governance": {
            "decision_id": decision.decision_id,
            # Deliberately wrong policy_version.
            "policy_version": "ffffffffffff",
        },
    })
    report = log.verify_chain("WF-PV")
    assert report.decisions_resolvable is False
    assert report.unresolved_decisions_at == [0]


def test_verify_chain_top_level_decision_id_shape() -> None:
    """Entries that record decision_id + policy_version at the top level
    of details (instead of nested under 'governance') resolve too."""
    decision = kernel().evaluate_tool_call(
        actor="rag-classifier", tool="claim.lookup", args={}, workflow_id="WF-TOP"
    )

    log = AuditLogger()
    log.log("mcp.call", {
        "workflow_id": "WF-TOP",
        "tool": "claim.lookup",
        "decision_id": decision.decision_id,
        "policy_version": decision.policy_version,
    })
    report = log.verify_chain("WF-TOP")
    assert report.decisions_resolvable is True
