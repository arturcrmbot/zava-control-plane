"""GovernanceKernel — the in-process policy core for the substrate.

This module owns the full kernel lifecycle: construction, per-call
evaluation, enforcement-mode toggle, and the sole import of AGT's
``agent_os.policies.PolicyEvaluator``. Per CON-002 of
``plan/feature-agent-governance-toolkit-1.md`` no code outside the
``api.server.services.governance`` package is allowed to import from
``agent_os.*`` / ``agentmesh.*`` directly.

Phase 2 status (TASK-014 / TASK-015)
------------------------------------
- ``__init__`` compiles the policy bundle from
  ``data/synthetic/authority/matrix.json`` + ``data/policies/tools.yaml``
  via :mod:`policy_compiler` and constructs an
  ``agent_os.policies.PolicyEvaluator`` over the resulting document.
- ``evaluate_tool_call`` consults the evaluator and returns a
  :class:`Decision` carrying the matched rule + the bundle's
  ``policy_version`` short hash. Mode is ``log_only`` until Phase 6;
  ``allowed=False`` does not raise yet (TASK-047 wires the raise).
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Literal, Mapping, Optional

from pydantic import BaseModel, Field

from .manifest import ToolManifestEntry, load_tools_yaml
from .policy_compiler import CompiledBundle, compile_bundle
from . import authority as _authority

EnforcementMode = Literal["log_only", "enforce"]

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public records
# ---------------------------------------------------------------------------


class Decision(BaseModel):
    """One evaluation result.

    Field semantics:

    - ``decision_id`` — opaque uuid4. Stable across the lifetime of one
      decision; the audit-blob hash chain references it in Phase 4.
    - ``policy_version`` — first 12 hex chars of sha256(bundle_yaml).
      Phase 1 used the sentinel ``"phase1-noop"``; Phase 2 onwards uses
      the real bundle hash.
    - ``rule_id`` — the AGT ``matched_rule`` name when one matched;
      ``None`` when the default action applied.
    - ``action`` — the AGT action string (``"allow"`` / ``"deny"`` /
      ``"audit"`` / ``"block"``) for forensic traceability.
    - ``enforcement_mode`` — ``"log_only"`` records but does not raise;
      ``"enforce"`` will raise :class:`GovernanceDenied` on
      ``allowed=False`` (Phase 6).
    - ``latency_us`` — wall-clock microseconds spent inside ``evaluate``.
    """

    allowed: bool
    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_version: str = "phase1-noop"
    rule_id: Optional[str] = None
    action: Optional[str] = None
    reason: str = "allow by default"
    enforcement_mode: EnforcementMode = "log_only"
    evaluated_at: float = Field(default_factory=time.time)
    latency_us: int = 0


class GovernanceDenied(RuntimeError):
    """Raised when ``enforce`` mode is on and the policy returns deny.

    Carries the ``Decision`` so callers + the existing exception
    narrative pipeline can render the rule_id and reason. Phase 2:
    nothing raises this — Phase 6 (TASK-047) wires the raise inside
    :meth:`GovernanceKernel.evaluate_tool_call`.
    """

    def __init__(self, decision: Decision) -> None:
        super().__init__(f"governance denied: {decision.reason}")
        self.decision = decision


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _matrix_path() -> Path:
    """Locate ``data/synthetic/authority/matrix.json`` from this file."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "data" / "synthetic" / "authority" / "matrix.json"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "data/synthetic/authority/matrix.json not found; ensure the repo "
        f"layout is intact (searched ancestors of {here})."
    )


def _load_matrix(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or _matrix_path()
    raw = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"{target} must be a JSON list of rules; got {type(raw)}")
    return raw


# ---------------------------------------------------------------------------
# Kernel
# ---------------------------------------------------------------------------


class GovernanceKernel:
    """In-process policy kernel. Singleton via :func:`kernel`.

    Construction is cheap and idempotent: ``init_governance()`` (in
    ``boot.py``) constructs once at app startup and stashes on the
    module global so subsequent calls return the same instance.
    """

    def __init__(
        self,
        *,
        matrix_path: Path | None = None,
        tools_path: str | None = None,
    ) -> None:
        self._lock = threading.Lock()

        # Late import keeps this module importable even if AGT is
        # absent at module-load time (the kernel constructor is the
        # boot-time choke).
        from agent_os.policies import PolicyEvaluator  # noqa: WPS433

        tools = load_tools_yaml(tools_path)
        matrix = _load_matrix(matrix_path)
        bundle: CompiledBundle = compile_bundle(matrix=matrix, tools=tools)

        self._tools: Mapping[str, ToolManifestEntry] = tools
        self._matrix: list[dict[str, Any]] = matrix
        self._bundle: CompiledBundle = bundle
        self._evaluator: PolicyEvaluator = PolicyEvaluator(policies=[bundle.document])

    # --- Public properties ---------------------------------------------------

    @property
    def policy_version(self) -> str:
        """sha256(:12) of the compiled bundle."""
        return self._bundle.short_version

    @property
    def policy_version_full(self) -> str:
        """Full sha256 hex of the compiled bundle. Used in audit entries."""
        return self._bundle.version_hash

    @property
    def rule_count(self) -> int:
        """Number of rules in the compiled bundle (excludes defaults)."""
        return self._bundle.rule_count

    @property
    def enforcement_mode(self) -> EnforcementMode:
        """``"enforce"`` iff env var ``AGT_ENFORCE`` is truthy. Phase 6 flips
        the demo profile to enforce by default; Phase 2 always logs only."""
        if os.environ.get("AGT_ENFORCE", "").strip() in ("1", "true", "TRUE", "yes"):
            return "enforce"
        return "log_only"

    @property
    def known_tools(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools.keys()))

    # --- Evaluation ----------------------------------------------------------

    def evaluate_tool_call(
        self,
        actor: str,
        tool: str,
        args: dict | None = None,
        workflow_id: str | None = None,
    ) -> Decision:
        """Evaluate one tool call.

        Builds an AGT request context from ``(actor, tool, args)``,
        extracts the ``value`` per the tool's manifest ``value_field``,
        and calls :meth:`PolicyEvaluator.evaluate`. Phase 2 always
        records ``log_only`` and never raises; Phase 6 (TASK-047) flips
        the raise on ``allowed=False`` when ``enforcement_mode ==
        "enforce"``.
        """
        t0 = time.perf_counter_ns()
        request_args = args or {}
        manifest_entry = self._tools.get(tool)

        context: dict[str, Any] = {
            "actor": actor or "unknown",
            "tool": tool,
            "workflow_id": workflow_id,
            "args": request_args,
            "reversible": (
                manifest_entry.reversible if manifest_entry is not None else None
            ),
            "scope_function": (
                manifest_entry.scope_function if manifest_entry is not None else None
            ),
        }

        if manifest_entry is not None and manifest_entry.value_field:
            context["value"] = _extract_dotted(
                request_args, manifest_entry.value_field
            )
        else:
            context["value"] = None

        try:
            result = self._evaluator.evaluate(context)
        except Exception:  # pragma: no cover — surface eval failure
            log.exception(
                "governance: PolicyEvaluator raised on tool=%s actor=%s",
                tool, actor,
            )
            raise

        latency_us = max(1, (time.perf_counter_ns() - t0) // 1000)
        action_str = getattr(result.action, "value", str(result.action))

        return Decision(
            allowed=bool(result.allowed),
            policy_version=self.policy_version,
            rule_id=result.matched_rule,
            action=action_str,
            reason=result.reason or "",
            enforcement_mode=self.enforcement_mode,
            latency_us=int(latency_us),
        )

    # --- Authority resolution (Phase 3 — TASK-020) ---------------------------

    def resolve_approver(
        self,
        action: str,
        value: float | None = None,
        category: str | None = None,
        requester_role: str | None = None,
        business_unit: str | None = None,
        geography: str | None = None,
    ) -> _authority.ApproverResolution:
        """First-match authority resolution against the matrix.

        Pure in-process walk. Byte-identical semantics to the Node mock at
        ``mocks/authority-mcp/resolver.ts`` (proven by
        ``tests/api/server/services/governance/test_authority_parity.py``).
        Used by :mod:`api.server.mcp_tools.delegated_authority` and the
        Authority routes; the HTTP fallback is only used when
        ``AUTHORITY_MCP_URL`` is set (engagement-POC swap-in seam).
        """
        return _authority.resolve(
            self._matrix,
            action=action,
            value=value,
            category=category,
            requester_role=requester_role,
            business_unit=business_unit,
            geography=geography,
        )

    def check_authority(
        self,
        role: str,
        action: str,
        value: float | None = None,
        category: str | None = None,
        requester_role: str | None = None,
        business_unit: str | None = None,
        geography: str | None = None,
    ) -> _authority.AuthorityCheck:
        """Does ``role`` have authority for the given request? Walks via
        :meth:`resolve_approver` and inspects the matched rule's
        ``approver_role`` + ``escalation_chain``."""
        return _authority.check(
            self._matrix,
            role=role,
            action=action,
            value=value,
            category=category,
            requester_role=requester_role,
            business_unit=business_unit,
            geography=geography,
        )


# ---------------------------------------------------------------------------
# Args helpers
# ---------------------------------------------------------------------------


def _extract_dotted(payload: Mapping[str, Any], path: str) -> Any:
    """Walk a dotted JSON path through nested dicts. Returns ``None`` if
    any segment is missing or a non-dict is hit mid-walk. Tolerant by
    design — value_field may legitimately be absent on a particular call."""
    if not path:
        return None
    cursor: Any = payload
    for part in path.split("."):
        if isinstance(cursor, Mapping) and part in cursor:
            cursor = cursor[part]
        else:
            return None
    return cursor


# ---------------------------------------------------------------------------
# Module singleton
# ---------------------------------------------------------------------------


_KERNEL: GovernanceKernel | None = None
_KERNEL_LOCK = threading.Lock()


def kernel() -> GovernanceKernel:
    """Return (and lazily construct) the module-level singleton.

    Most callers should prefer :func:`init_governance` from ``boot.py``
    at app startup; ``kernel()`` is the read-side getter every other
    call site uses. Idempotent and thread-safe.
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
