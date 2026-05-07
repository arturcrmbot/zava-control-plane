"""Phase 6 TASK-048 — enforce-mode capability + reversibility + value gates.

Each of the 4 deny scenarios from the plan:

1. Tool not in actor's ``allowed_tools`` (capability gate).
2. Irreversible tool called by an actor with ``reversible_only=True``.
3. Value above the actor's ``max_value_gbp`` ceiling.
4. Unknown agent_id (not in ``api.shared.agents.AGENTS``).

Plus the env-var contract:

- ``AGT_ENFORCE`` unset / "0" → log_only; deny is recorded but does
  not raise.
- ``AGT_ENFORCE=1`` → enforce; deny raises ``GovernanceDenied``.

These tests are the heart of the enforce-mode contract. They run
without Azurite and without a live Functions worker.
"""
from __future__ import annotations

import os

# Same Azurite-probe short-circuit as the rest of the governance suite.
os.environ.setdefault("AZURE_STORAGE_CONNECTION_STRING", "")

import pytest

from api.server.services.governance import GovernanceDenied, kernel
from api.server.services.governance.kernel import _reset_for_tests


@pytest.fixture(autouse=True)
def _fresh_kernel():
    _reset_for_tests()
    yield
    _reset_for_tests()


# ---------------------------------------------------------------------------
# Log-only mode: gate fires, decision is recorded, NOTHING raises
# ---------------------------------------------------------------------------


class TestLogOnlyGate:
    """In log-only mode the registry gate produces a deny Decision but
    MUST NOT raise. The chokepoints record the decision and proceed."""

    def test_capability_deny_recorded_not_raised(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("AGT_ENFORCE", raising=False)
        # rag-classifier is registered, but does NOT have postGLEntry.
        decision = kernel().evaluate_tool_call(
            actor="rag-classifier",
            tool="postGLEntry",
            args={"amount": 100.0},
        )
        assert decision.allowed is False
        assert decision.action == "deny"
        assert decision.rule_id == "deny:capability:rag-classifier:postGLEntry"
        assert "not authorised" in decision.reason
        assert decision.enforcement_mode == "log_only"

    def test_unknown_agent_deny_recorded_not_raised(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("AGT_ENFORCE", raising=False)
        decision = kernel().evaluate_tool_call(
            actor="ghost-agent",
            tool="claim.lookup",
            args={},
        )
        assert decision.allowed is False
        assert decision.rule_id == "deny:unknown_agent:ghost-agent"

    def test_unknown_agent_actor_soft_passes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The ``unknown-agent`` literal is the soft escape hatch for
        un-attributed legacy paths (call_mcp default). It MUST NOT be
        treated as an unknown agent — gate skips, AGT bundle audits."""
        monkeypatch.delenv("AGT_ENFORCE", raising=False)
        decision = kernel().evaluate_tool_call(
            actor="unknown-agent",
            tool="claim.lookup",
            args={},
        )
        assert decision.allowed is True
        assert decision.rule_id == "tool:claim.lookup"


# ---------------------------------------------------------------------------
# Enforce mode: deny RAISES GovernanceDenied with a populated Decision
# ---------------------------------------------------------------------------


class TestEnforceMode:
    """When ``AGT_ENFORCE=1``, deny decisions raise. The exception
    carries the Decision so the existing exception narrative pipeline
    can render rule_id + reason as a workflow exception body."""

    @pytest.fixture(autouse=True)
    def _enforce_on(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AGT_ENFORCE", "1")

    def test_capability_gate_raises(self) -> None:
        with pytest.raises(GovernanceDenied) as excinfo:
            kernel().evaluate_tool_call(
                actor="rag-classifier",
                tool="postGLEntry",  # not in rag-classifier's allowed_tools
                args={"amount": 50.0},
            )
        d = excinfo.value.decision
        assert d.allowed is False
        assert d.rule_id.startswith("deny:capability:")
        assert d.enforcement_mode == "enforce"

    def test_unknown_agent_gate_raises(self) -> None:
        with pytest.raises(GovernanceDenied) as excinfo:
            kernel().evaluate_tool_call(
                actor="ghost-agent",
                tool="claim.lookup",
                args={},
            )
        assert excinfo.value.decision.rule_id == "deny:unknown_agent:ghost-agent"

    def test_unknown_agent_actor_does_not_raise(self) -> None:
        """Soft escape hatch: 'unknown-agent' literal still skips the
        gate even under enforce. This is intentional so legacy code
        paths that haven't been registry-mapped don't break the demo."""
        decision = kernel().evaluate_tool_call(
            actor="unknown-agent",
            tool="claim.lookup",
            args={},
        )
        assert decision.allowed is True
        assert decision.enforcement_mode == "enforce"

    def test_registered_actor_with_allowed_tool_passes(self) -> None:
        decision = kernel().evaluate_tool_call(
            actor="rag-classifier",
            tool="claim.lookup",  # in rag-classifier's allowed_tools
            args={},
        )
        assert decision.allowed is True
        assert decision.rule_id == "tool:claim.lookup"
        assert decision.enforcement_mode == "enforce"

    def test_unknown_tool_falls_through(self) -> None:
        """Unknown tool from a registered actor MUST NOT auto-deny —
        SEC-004's CI gate catches missing manifest entries; runtime
        treats unknown tools as 'we don't know enough to gate', so
        callers don't get surprise denies on tools that haven't been
        formally registered yet."""
        decision = kernel().evaluate_tool_call(
            actor="rag-classifier",
            tool="never.heard.of.this.tool",
            args={},
        )
        assert decision.allowed is True


# ---------------------------------------------------------------------------
# Reversibility gate (uses a registered agent + irreversible tool)
# ---------------------------------------------------------------------------


def test_reversibility_gate_denies_irreversible_for_reversible_only_actor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All current AGENTS have ``reversible_only=True``. So if an agent
    is hand-allowed an irreversible tool (capability gate passes), the
    reversibility gate MUST still deny."""
    monkeypatch.setenv("AGT_ENFORCE", "1")
    _reset_for_tests()
    k = kernel()

    # Patch rag-classifier in-memory to allow postGLEntry (irreversible
    # per tools.yaml). The reversibility gate should still fire.
    from api.shared.agents import AGENTS, AgentRegistryEntry

    original = AGENTS["rag-classifier"]
    monkeypatch.setitem(
        AGENTS,
        "rag-classifier",
        AgentRegistryEntry(
            agent_id="rag-classifier",
            allowed_tools=original.allowed_tools + ("postGLEntry",),
            max_value_gbp=None,
            reversible_only=True,  # explicit
            scope_function="finance",
            description="patched for test",
        ),
    )

    with pytest.raises(GovernanceDenied) as excinfo:
        k.evaluate_tool_call(
            actor="rag-classifier",
            tool="postGLEntry",
            args={"amount": 100.0},
        )
    d = excinfo.value.decision
    assert d.rule_id == "deny:reversibility:rag-classifier:postGLEntry"
    assert "non-reversible" in d.reason


# ---------------------------------------------------------------------------
# Value-ceiling gate
# ---------------------------------------------------------------------------


def test_value_ceiling_gate_denies_when_above(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Set max_value_gbp on a registered agent + allow it an
    irreversible tool with a value_field; call > ceiling → deny."""
    monkeypatch.setenv("AGT_ENFORCE", "1")
    _reset_for_tests()
    k = kernel()

    from api.shared.agents import AGENTS, AgentRegistryEntry

    monkeypatch.setitem(
        AGENTS,
        "rag-classifier",
        AgentRegistryEntry(
            agent_id="rag-classifier",
            allowed_tools=("postGLEntry",),
            max_value_gbp=1000.0,
            reversible_only=False,  # so reversibility doesn't intercept
            scope_function="finance",
            description="patched for test",
        ),
    )

    with pytest.raises(GovernanceDenied) as excinfo:
        k.evaluate_tool_call(
            actor="rag-classifier",
            tool="postGLEntry",
            args={"amount": 5000.0},
        )
    d = excinfo.value.decision
    assert d.rule_id == "deny:value_ceiling:rag-classifier:postGLEntry"
    assert "exceeds" in d.reason


def test_value_ceiling_gate_allows_when_under(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGT_ENFORCE", "1")
    _reset_for_tests()
    k = kernel()

    from api.shared.agents import AGENTS, AgentRegistryEntry

    monkeypatch.setitem(
        AGENTS,
        "rag-classifier",
        AgentRegistryEntry(
            agent_id="rag-classifier",
            allowed_tools=("postGLEntry",),
            max_value_gbp=1000.0,
            reversible_only=False,
            scope_function="finance",
            description="patched for test",
        ),
    )

    decision = k.evaluate_tool_call(
        actor="rag-classifier",
        tool="postGLEntry",
        args={"amount": 500.0},
    )
    assert decision.allowed is True
