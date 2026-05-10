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
from collections import OrderedDict
from pathlib import Path
from typing import Any, Literal, Mapping, Optional

from pydantic import BaseModel, Field

from .manifest import ToolManifestEntry, load_tools_yaml
from .policy_compiler import CompiledBundle, compile_bundle
from . import authority as _authority
from .identity import AgentIdentityStore

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
# JWS Compact (EdDSA) — Phase 5 TASK-038 / TASK-040
# ---------------------------------------------------------------------------


def _b64url(data: bytes) -> str:
    """Base64url-encode without padding (RFC 7515 §2)."""
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    import base64
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _payload_hash(payload: Mapping[str, Any]) -> str:
    """sha256 hex of ``payload`` canonicalised the same way as the audit
    chain (sort_keys=True, default=str). SEC-001 of the plan."""
    import hashlib
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _jws_sign(
    identity: AgentIdentityStore, agent_id: str, body: Mapping[str, Any]
) -> str:
    """Produce a JWS Compact-Serialization string (RFC 7515) with EdDSA.

    Format: ``b64url(header) . b64url(body) . b64url(signature)``.
    Header: ``{"alg":"EdDSA","typ":"JWT","kid":agent_id}``.
    """
    header = {"alg": "EdDSA", "typ": "JWT", "kid": agent_id}
    h = _b64url(json.dumps(header, sort_keys=True).encode("utf-8"))
    p = _b64url(json.dumps(body, sort_keys=True, default=str).encode("utf-8"))
    signing_input = f"{h}.{p}".encode("ascii")
    signature = identity.sign(agent_id, signing_input)
    return f"{h}.{p}.{_b64url(signature)}"


def _jws_verify(
    identity: AgentIdentityStore, jws: str
) -> tuple[bool, dict[str, Any] | None]:
    """Verify a JWS Compact string. Returns (ok, decoded_body_or_None).

    Returns ``(False, None)`` on any malformation, unknown ``kid``, or
    signature failure. The caller (:meth:`GovernanceKernel.verify_jws`)
    additionally checks ``iss`` and ``payload_hash``.
    """
    try:
        h_b64, p_b64, s_b64 = jws.split(".")
    except ValueError:
        return False, None
    try:
        header = json.loads(_b64url_decode(h_b64))
        body = json.loads(_b64url_decode(p_b64))
        signature = _b64url_decode(s_b64)
    except Exception:
        return False, None
    if header.get("alg") != "EdDSA":
        return False, None
    kid = header.get("kid")
    if not isinstance(kid, str) or not identity.has(kid):
        return False, None
    signing_input = f"{h_b64}.{p_b64}".encode("ascii")
    if not identity.verify(kid, signing_input, signature):
        return False, None
    return True, body


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

        # Phase 5 (TASK-037): Ed25519 identity store. Construction is
        # idempotent — second boot loads keys from
        # ``azurite-data/agt-keys/`` (dev) or
        # ``data/governance/agent-pubkeys/`` (prod). Lazy import of
        # AGENTS to avoid pulling api.shared.agents at module-load time.
        from api.shared.agents import all_agent_ids
        self._identity = AgentIdentityStore(all_agent_ids())

        # Phase 7 TASK-053: in-process decision registry. Every Decision
        # returned by :meth:`evaluate_tool_call` is recorded here keyed
        # by its ``decision_id`` so :class:`AuditLogger.verify_chain`
        # (and the Evidence chip) can prove that every decision_id in
        # the audit chain corresponds to a real evaluation against the
        # live policy bundle. FIFO eviction — the registry is a
        # bounded LRU-ish cap; entries beyond ``AGT_DECISION_REGISTRY_MAX``
        # (default 50_000) are dropped in insertion order. The cap
        # exists so a long-running process can't grow the registry
        # without bound; for a fresh demo (a few thousand workflows
        # at most) every decision stays resolvable end-to-end.
        try:
            cap = int(os.environ.get("AGT_DECISION_REGISTRY_MAX", "50000"))
        except ValueError:
            cap = 50000
        self._decision_registry_cap = max(1, cap)
        self._decisions: "OrderedDict[str, Decision]" = OrderedDict()
        self._decisions_lock = threading.Lock()

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
        mode = self.enforcement_mode

        # Phase 7 TASK-052: kill switch is checked FIRST so an operator
        # pause beats every other rule. Active kills produce a deny
        # with a kill:<kill_id> rule_id; lazy expiry happens inside
        # is_killed() so a kill that just timed out doesn't fire.
        from .kill_switch import kill_switch_store
        kill = kill_switch_store.is_killed(actor or "unknown", tool)
        if kill is not None:
            decision = Decision(
                allowed=False,
                policy_version=self.policy_version,
                rule_id=f"kill:{kill.kill_id}",
                action="deny",
                reason=(
                    f"operator kill switch active: actor={kill.actor!r} "
                    f"tool={kill.tool!r} reason={kill.reason!r} "
                    f"expires_in={int(kill.remaining_seconds())}s"
                ),
                enforcement_mode=mode,
                latency_us=int(latency_us),
            )
            self._register_decision(decision)
            if mode == "enforce":
                raise GovernanceDenied(decision)
            return decision

        # Phase 6 TASK-047: capability + reversibility + value gates.
        # The AGT bundle handles tool registration + matrix audits; the
        # registry-driven gates live in Python because PolicyCondition is
        # single-field-only (no AND), and the registry is the source of
        # truth for per-agent allowlists / value ceilings anyway.
        gate = self._registry_gate(
            actor=actor,
            tool=tool,
            value=context.get("value"),
            tool_entry=manifest_entry,
        )
        if gate is not None:
            decision = Decision(
                allowed=False,
                policy_version=self.policy_version,
                rule_id=gate[0],
                action="deny",
                reason=gate[1],
                enforcement_mode=mode,
                latency_us=int(latency_us),
            )
            self._register_decision(decision)
            if mode == "enforce":
                raise GovernanceDenied(decision)
            return decision

        decision = Decision(
            allowed=bool(result.allowed),
            policy_version=self.policy_version,
            rule_id=result.matched_rule,
            action=action_str,
            reason=result.reason or "",
            enforcement_mode=mode,
            latency_us=int(latency_us),
        )
        self._register_decision(decision)
        if mode == "enforce" and not decision.allowed:
            raise GovernanceDenied(decision)
        return decision

    # --- Decision registry (Phase 7 TASK-053) -------------------------------

    def _register_decision(self, decision: Decision) -> None:
        """Record one Decision in the in-process registry.

        FIFO eviction at ``_decision_registry_cap``. Cheap (one OrderedDict
        insert + maybe one popitem under a small lock); never raises into
        the caller — registry failures degrade to "decision not
        resolvable later" rather than breaking the tool call.
        """
        try:
            with self._decisions_lock:
                self._decisions[decision.decision_id] = decision
                self._decisions.move_to_end(decision.decision_id)
                while len(self._decisions) > self._decision_registry_cap:
                    self._decisions.popitem(last=False)
        except Exception:  # pragma: no cover — defensive
            log.warning(
                "governance: _register_decision failed for %s",
                decision.decision_id,
            )

    def resolve_decision(self, decision_id: str) -> Decision | None:
        """Return the recorded :class:`Decision` for ``decision_id``, or
        ``None`` when the registry has no record (process restart, cap
        eviction, or unknown id).

        :class:`AuditLogger.verify_chain` calls this for every
        ``decision_id`` it finds inside an entry's details — when a
        decision resolves AND the recorded ``policy_version`` matches
        what's stored on the entry, the chain's ``decisions_resolvable``
        chip stays green.
        """
        if not isinstance(decision_id, str) or not decision_id:
            return None
        with self._decisions_lock:
            return self._decisions.get(decision_id)

    @property
    def decision_registry_size(self) -> int:
        """Current number of decisions retained in the registry. Useful
        for tests + a future ``/api/governance/health`` route."""
        with self._decisions_lock:
            return len(self._decisions)

    def _registry_gate(
        self,
        *,
        actor: str,
        tool: str,
        value: Any,
        tool_entry: ToolManifestEntry | None,
    ) -> tuple[str, str] | None:
        """Phase 6 TASK-047 — registry-driven enforcement gates.

        Returns ``(rule_id, reason)`` to deny, or ``None`` to fall
        through to the AGT bundle. Gates checked in order:

          1. Unknown actor (not in :data:`AGENTS`).
          2. Tool not in actor's ``allowed_tools``.
          3. Actor is ``reversible_only=True`` and the tool's manifest
             entry says ``reversible=false``.
          4. Tool carries a numeric value, the actor has a non-None
             ``max_value_gbp``, and value > that ceiling.
          5. Unknown tool — only enforced when the actor IS registered
             (an unknown tool from an unknown actor falls through; the
             "unknown actor" message is more useful).

        ``unknown-agent`` (the default fallback in call_mcp) is treated
        as a special "log-only" actor — the gate skips for it so
        un-attributed calls don't break under enforce mode (they still
        get audited via the AGT bundle's tool rule). Phase 7 may
        tighten this further.
        """
        # Soft escape hatch: the un-attributed default actor is allowed
        # through so legacy code paths that haven't been registry-mapped
        # don't auto-deny under enforce. Real agents (everything in
        # AGENTS) get the full gate treatment.
        if actor in (None, "", "unknown", "unknown-agent"):
            return None

        from api.shared.agents import get as _get_agent  # local: avoids cycles

        agent_entry = _get_agent(actor)
        if agent_entry is None:
            return (
                f"deny:unknown_agent:{actor}",
                f"actor {actor!r} not in api.shared.agents.AGENTS registry",
            )

        if tool_entry is None:
            # Tool isn't in the manifest. Don't auto-deny on this path —
            # SEC-004's CI catches missing manifest entries; runtime
            # treats it as "we don't know enough to gate".
            return None

        if tool not in agent_entry.allowed_tools:
            return (
                f"deny:capability:{actor}:{tool}",
                (
                    f"actor {actor!r} not authorised for tool {tool!r} "
                    f"(allowed_tools: {list(agent_entry.allowed_tools)!r})"
                ),
            )

        if agent_entry.reversible_only and not tool_entry.reversible:
            return (
                f"deny:reversibility:{actor}:{tool}",
                (
                    f"actor {actor!r} is reversible_only=True but tool "
                    f"{tool!r} is non-reversible per data/policies/tools.yaml"
                ),
            )

        if (
            agent_entry.max_value_gbp is not None
            and value is not None
        ):
            try:
                v = float(value)
            except (TypeError, ValueError):
                v = None
            if v is not None and v > agent_entry.max_value_gbp:
                return (
                    f"deny:value_ceiling:{actor}:{tool}",
                    (
                        f"value GBP {v} exceeds {actor!r}'s max_value_gbp "
                        f"of {agent_entry.max_value_gbp}"
                    ),
                )

        return None

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

    # --- Identity (Phase 5 — TASK-038 / TASK-040) ----------------------------

    @property
    def identity(self) -> AgentIdentityStore:
        """The kernel's keystore. Exposed for tests + for
        :class:`AuditLogger` (which signs entries via this seam)."""
        return self._identity

    def sign_action(
        self,
        agent_id: str,
        action: str,
        payload: dict[str, Any],
    ) -> str:
        """Return a JWS Compact-Serialization signed by ``agent_id``.

        Header: ``{"alg":"EdDSA","typ":"JWT","kid":"<agent_id>"}``.
        Body: ``{"iss":<agent_id>, "action":<action>,
                 "payload_hash":<sha256(canonical_json(payload))>,
                 "iat":<unix epoch seconds>}``.

        The caller (TASK-039 inside ``AuditLogger.log()``) writes the
        return value to ``entry["actor_jws"]`` BEFORE the chain hash is
        computed, so the JWS is part of the hashed payload.
        """
        body = {
            "iss": agent_id,
            "action": action,
            "payload_hash": _payload_hash(payload),
            "iat": int(time.time()),
        }
        return _jws_sign(self._identity, agent_id, body)

    def verify_jws(
        self,
        agent_id: str,
        jws: str,
        expected_payload: dict[str, Any],
    ) -> bool:
        """Verify a JWS Compact string.

        Returns True iff:
          - The signature validates against ``agent_id``'s public key.
          - The header's ``kid`` matches ``agent_id``.
          - The body's ``iss`` matches ``agent_id``.
          - The body's ``payload_hash`` matches ``sha256(canonical_json(expected_payload))``.

        Pure read of the in-memory pubkey map; no Key Vault round-trip.
        """
        ok, body = _jws_verify(self._identity, jws)
        if not ok or body is None:
            return False
        if body.get("iss") != agent_id:
            return False
        if body.get("payload_hash") != _payload_hash(expected_payload):
            return False
        return True


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
