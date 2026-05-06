"""Phase 1 wiring smoke tests for the Governance kernel.

Per plan/feature-agent-governance-toolkit-1.md TASK-005. Asserts:

- The kernel singleton is a singleton (idempotent ``kernel()``).
- ``evaluate_tool_call`` returns a Decision shaped exactly as the public
  contract Phase 2 will rely on.
- ``GovernanceDenied`` is raisable and carries the Decision.
- AGT's ``agent_os.policies.PolicyEvaluator`` imports cleanly inside
  the project venv (proves CON-002 is honoured before Phase 2 wires it
  in).
- ``init_governance()`` is idempotent and returns the same instance.
"""
from __future__ import annotations

import os

import pytest

from api.server.services.governance import (
    Decision,
    GovernanceDenied,
    GovernanceKernel,
    init_governance,
    kernel,
)
from api.server.services.governance.kernel import _reset_for_tests


@pytest.fixture(autouse=True)
def _fresh_kernel():
    """Each test gets a fresh kernel singleton."""
    _reset_for_tests()
    yield
    _reset_for_tests()


def test_kernel_is_singleton() -> None:
    """``kernel()`` returns the same instance on subsequent calls."""
    a = kernel()
    b = kernel()
    assert a is b
    assert isinstance(a, GovernanceKernel)


def test_init_governance_is_idempotent() -> None:
    """Calling the boot hook twice yields the same kernel."""
    a = init_governance()
    b = init_governance()
    assert a is b
    assert a is kernel()


def test_evaluate_tool_call_returns_allow_in_phase_1() -> None:
    """Phase 1 default is allow-everything; this is intentional and load-bearing
    for the Phase-2 wiring step that introduces no behavioural change."""
    decision = kernel().evaluate_tool_call(
        actor="finance-agent",
        tool="concur.list_claims",
        args={"limit": 5},
        workflow_id="EXP-DEMO-01",
    )
    assert isinstance(decision, Decision)
    assert decision.allowed is True
    assert decision.policy_version == "phase1-noop"
    assert decision.enforcement_mode == "log_only"
    assert decision.rule_id is None
    assert decision.decision_id  # non-empty uuid
    assert decision.latency_us >= 1


def test_decision_id_is_unique_per_call() -> None:
    k = kernel()
    d1 = k.evaluate_tool_call(actor="a", tool="t", args={})
    d2 = k.evaluate_tool_call(actor="a", tool="t", args={})
    assert d1.decision_id != d2.decision_id


def test_governance_denied_carries_decision() -> None:
    """The exception type that Phase 6 will raise on a deny is constructible
    and exposes the underlying Decision so the existing exception narrative
    pipeline can render it."""
    decision = Decision(allowed=False, reason="not in allowed_tools")
    err = GovernanceDenied(decision)
    assert err.decision is decision
    assert "not in allowed_tools" in str(err)
    # Subclass of RuntimeError so existing `except Exception` blocks
    # degrade safely (Phase 6 handlers will narrow to GovernanceDenied).
    assert isinstance(err, RuntimeError)


def test_enforcement_mode_reads_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """Plan REQ-008: AGT_ENFORCE flips the mode from log_only to enforce.
    Phase 6 starts honouring it inside ``evaluate_tool_call``; Phase 1
    just exposes the property correctly."""
    monkeypatch.delenv("AGT_ENFORCE", raising=False)
    assert kernel().enforcement_mode == "log_only"

    for truthy in ("1", "true", "TRUE", "yes"):
        monkeypatch.setenv("AGT_ENFORCE", truthy)
        # Re-read property; the kernel does not cache.
        assert kernel().enforcement_mode == "enforce", f"value={truthy!r}"

    monkeypatch.setenv("AGT_ENFORCE", "0")
    assert kernel().enforcement_mode == "log_only"


def test_agt_policy_evaluator_importable() -> None:
    """The README quickstart symbols MUST import cleanly. This is the
    plan's explicit RISK-001 surface probe asserted as a unit test —
    if AGT drifts in Public Preview and removes any of these names,
    Phase 2 cannot proceed and CI surfaces it here first."""
    from agent_os.policies import (  # noqa: F401 — import probe
        PolicyAction,
        PolicyCondition,
        PolicyDecision,
        PolicyDefaults,
        PolicyDocument,
        PolicyEvaluator,
        PolicyOperator,
        PolicyRule,
    )


def test_agentmesh_identity_importable() -> None:
    """Phase 5 needs the JWS / Ed25519 primitives. Probe early."""
    from agentmesh.identity import (  # noqa: F401
        AgentDID,
        Credential,
        CredentialManager,
        KeyStore,
        SoftwareKeyStore,
    )
