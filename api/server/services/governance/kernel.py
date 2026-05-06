"""GovernanceKernel — the in-process policy core for the substrate.

This module owns the full kernel lifecycle: construction, per-call
evaluation, enforcement-mode toggle, and the sole import of AGT's
``agent_os.policies.PolicyEvaluator``. Per CON-002 of
``plan/feature-agent-governance-toolkit-1.md`` no code outside the
``api.server.services.governance`` package is allowed to import from
``agent_os.*`` / ``agentmesh.*`` directly.

Phase 1 scope
-------------
- ``Decision`` Pydantic record + ``GovernanceDenied`` exception are the
  full public contract; the call-site decorators in Phase 2 (TASK-016
  / TASK-017) wire to them and never break their shape.
- ``GovernanceKernel.evaluate_tool_call`` returns ``allowed=True`` for
  every input. The compiled policy bundle lands in Phase 2 (TASK-014)
  inside ``__init__``; no change to ``evaluate_tool_call``'s signature.
- The ``enforcement_mode`` field is wired but every Phase-1 decision
  is recorded as ``"log_only"`` regardless of env. Phase 6 (TASK-047)
  reads the ``AGT_ENFORCE`` env var.

Reentrancy + safety
-------------------
- Kernel state is read-mostly: ``policy_version`` and the underlying
  ``PolicyEvaluator`` are set once at construction. ``evaluate_tool_call``
  is a pure function of ``(policy bundle, request tuple)``.
- Per PAT-002, the kernel may add a 60s decision cache later; today
  there is no cache because there is no policy.
- ``GovernanceDenied`` is a subclass of ``RuntimeError`` so existing
  ``except Exception`` blocks in the substrate degrade safely.
"""
from __future__ import annotations

import os
import threading
import time
import uuid
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

EnforcementMode = Literal["log_only", "enforce"]


# ---------------------------------------------------------------------------
# Public records
# ---------------------------------------------------------------------------


class Decision(BaseModel):
    """One evaluation result.

    Every successful call to ``GovernanceKernel.evaluate_tool_call``
    produces a ``Decision``. The instance is recorded onto the
    ``actionLedger`` (Phase 4) and propagated to the existing ``mcp.call``
    timeline event payload so the Control Plane can render it.

    Field semantics:

    - ``decision_id`` — opaque uuid4. Stable across the lifetime of one
      decision; the audit-blob hash chain will reference it in Phase 4.
    - ``policy_version`` — sha256 hex (12-char prefix) of the compiled
      policy bundle that produced this decision. Phase 1 returns the
      sentinel ``"phase1-noop"`` since no policy is loaded yet; Phase 2
      replaces this with the real bundle hash from
      ``policy_compiler.compile_bundle``.
    - ``rule_id`` — the AGT ``matched_rule`` name when ``allowed=False``
      or when ``allowed=True`` matched a non-default rule; ``None``
      when the default action applied.
    - ``enforcement_mode`` — what the kernel did. ``"log_only"`` means
      the decision was recorded but not enforced; ``"enforce"`` means a
      deny would have raised ``GovernanceDenied`` (Phase 6).
    - ``latency_us`` — wall-clock microseconds spent inside ``evaluate``.
    """

    allowed: bool
    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_version: str = "phase1-noop"
    rule_id: Optional[str] = None
    reason: str = "phase 1 — kernel allows everything by design"
    enforcement_mode: EnforcementMode = "log_only"
    evaluated_at: float = Field(default_factory=time.time)
    latency_us: int = 0


class GovernanceDenied(RuntimeError):
    """Raised when ``enforce`` mode is on and the policy returns deny.

    Carries the ``Decision`` so callers + the existing exception
    narrative pipeline (``api/server/services/exception_factory.py``)
    can render the rule_id and reason as the workflow exception body.

    In Phase 1 nothing raises this — the class exists so callers in
    Phase 2 can ``except GovernanceDenied`` without an import scramble.
    """

    def __init__(self, decision: Decision) -> None:
        super().__init__(f"governance denied: {decision.reason}")
        self.decision = decision


# ---------------------------------------------------------------------------
# Kernel
# ---------------------------------------------------------------------------


class GovernanceKernel:
    """In-process policy kernel. Singleton via ``kernel()``.

    Phase 1 implementation is deliberately empty of policy: every
    ``evaluate_tool_call`` returns ``allowed=True`` so wiring this into
    the two chokepoints in Phase 2 is a no-op behaviourally. The
    ``policy_version`` field is the sentinel ``"phase1-noop"``.

    Construction is cheap and idempotent: ``init_governance()`` (in
    ``boot.py``) constructs once at app startup and stashes on the
    module global so subsequent calls return the same instance.
    """

    def __init__(self) -> None:
        # Phase 2 (TASK-014) populates these from policy_compiler:
        self._policy_version: str = "phase1-noop"
        self._evaluator: Any = None  # placeholder for agent_os PolicyEvaluator
        self._lock = threading.Lock()

    # --- Public properties ---------------------------------------------------

    @property
    def policy_version(self) -> str:
        """sha256(:12) of the compiled bundle, or ``"phase1-noop"`` pre-Phase 2."""
        return self._policy_version

    @property
    def enforcement_mode(self) -> EnforcementMode:
        """``"enforce"`` iff env var ``AGT_ENFORCE`` is truthy. Phase 6 flips
        the demo profile to enforce by default; Phase 1 always logs only."""
        if os.environ.get("AGT_ENFORCE", "").strip() in ("1", "true", "TRUE", "yes"):
            return "enforce"
        return "log_only"

    # --- Evaluation ----------------------------------------------------------

    def evaluate_tool_call(
        self,
        actor: str,
        tool: str,
        args: dict | None = None,
        workflow_id: str | None = None,
    ) -> Decision:
        """Evaluate one tool call. Phase 1: always allows.

        Signature is the public contract Phase 2 must preserve:
        ``call_mcp`` ([api/functions/graphs/_common.py](../../../functions/graphs/_common.py))
        and the ``@traced_tool`` decorator
        ([api/server/mcp_tools/_otel.py](../../mcp_tools/_otel.py)) are
        the only two callers. Both will pass ``actor`` (the requesting
        agent_id), ``tool`` (the MCP tool name), ``args`` (the request
        body), and the optional ``workflow_id`` for audit attribution.

        Returns a ``Decision`` instance. Never raises in Phase 1; the
        ``GovernanceDenied`` raise lands in Phase 6 (TASK-047) inside
        this same method when ``enforcement_mode == "enforce"`` and
        ``decision.allowed is False``.
        """
        t0 = time.perf_counter_ns()
        # Args is accepted for signature stability; Phase 1 doesn't read it.
        del actor, tool, args, workflow_id
        latency_us = max(1, (time.perf_counter_ns() - t0) // 1000)
        return Decision(
            allowed=True,
            policy_version=self._policy_version,
            enforcement_mode=self.enforcement_mode,
            latency_us=int(latency_us),
        )


# ---------------------------------------------------------------------------
# Module singleton
# ---------------------------------------------------------------------------


_KERNEL: GovernanceKernel | None = None
_KERNEL_LOCK = threading.Lock()


def kernel() -> GovernanceKernel:
    """Return (and lazily construct) the module-level singleton.

    Most callers should prefer ``init_governance()`` from ``boot.py`` at
    app startup; ``kernel()`` is the read-side getter every other call
    site uses. Idempotent and thread-safe.
    """
    global _KERNEL
    if _KERNEL is not None:
        return _KERNEL
    with _KERNEL_LOCK:
        if _KERNEL is None:
            _KERNEL = GovernanceKernel()
    return _KERNEL


def _reset_for_tests() -> None:
    """Test-only: drop the singleton so each test gets a fresh kernel."""
    global _KERNEL
    with _KERNEL_LOCK:
        _KERNEL = None
