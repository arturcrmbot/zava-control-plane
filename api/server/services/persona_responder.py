"""Persona responder service.

Closes generated-domain HITL gates by applying the matching persona's
decision policy against the parked workflow context, then raising the
external event back to the Durable orchestrator.

Architecture
------------
Each persona is one ``api/server/personae/<role>/SKILL.md`` file with
YAML frontmatter declaring:

    name: <role>
    description: <one sentence>
    allowed-tools:
    workflow_label: <human label for the domain>
    external_event: <durable event name to raise>
    decision_policy: |
        <Python source that reads `context` and assigns `decision`+`reason`>

The persona responder discovers all SKILL.md files under
``api/server/personae/`` at attach() time, parses the YAML frontmatter,
and compiles the ``decision_policy`` block into a callable. The body of
each SKILL.md is human-readable prose describing the same rule. The
prose and the executable code are both committed; the *executable* is
the source of truth, the prose tracks it for design-time reading and
for the eventual GHCP-session-driven persona variant (v2).

Auto-close allow-list
---------------------
Default behaviour: **every gate auto-resolves** (the autonomous-org
stance — personas drive every decision, no human in the loop). The
``PERSONA_AUTO_CLOSE`` env var overrides:

* unset, ``*``, or ``all`` (case-insensitive)  → every persona auto-closes
* ``none`` or ``off``                          → every gate stays open
  (the old production-honest default; use this on demo days where a
  real human walks the persona consoles)
* CSV of roles                                  → only those roles auto-close

Legacy demo profiles in ``scripts/profile-*.sh`` still set explicit
CSVs and continue to work.

Hand-built domains (expense / hiring) stamp ``persona`` /
``external_event`` / ``context`` on their suspended payloads (per the
substrate-fix v2). The responder still honours the allow-list, so
production / demo days with real humans keep human-in-the-loop unless
specifically opted in.
"""
from __future__ import annotations

import ast
import asyncio
import os
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

from api.server.services.durable_client import raise_orchestration_event
from api.shared.events import FleetEvent


PERSONAE_DIR = Path(__file__).resolve().parents[2] / "server" / "personae"

# A persona handler takes the parked context dict and returns the resolving
# event payload (e.g. {"decision": "approve", "reason": "in-policy + low band"}).
PersonaHandler = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class PersonaDefinition:
    role: str
    description: str
    workflow_label: str
    external_event: str
    decide: PersonaHandler
    skill_path: Path
    # Pitch D4: per-persona personality knobs. Same role + different humans
    # produce *different* decisions. Defaults are baked in by ``_load_personae``
    # so this dict is always shaped {risk_appetite, thoroughness,
    # escalation_style}; never None, never empty.
    personality: dict[str, str] = field(default_factory=dict)
    # Phase 3.2 of autonomous-domain-insights v1. Optional: when present,
    # the cadence loop fires `domain.summary.requested` events and the
    # responder calls this handler. None for personae without a
    # summary_policy block in their SKILL.md frontmatter (today: all of
    # them; v1 ships the runtime support, v1.1+ adds blocks).
    summarise: PersonaHandler | None = None
    # v1.2: optional first-person voice renderer. When present, called
    # after summary_policy with input {"summary": <dict>} and expected to
    # set ``body = "..."``. The returned string replaces the structured
    # body in the written Insight node. Returning None / not setting body
    # falls through to the structured body.
    voice: PersonaHandler | None = None


# Populated at attach() time.
PERSONA_DEFINITIONS: dict[str, PersonaDefinition] = {}


# Sentinel: when present in the auto-close set, every persona role auto-closes.
_AUTO_CLOSE_ALL = "*"


def _auto_close_set() -> set[str]:
    """Read PERSONA_AUTO_CLOSE env var as a set of persona roles.

    Default (unset / ``*`` / ``all``) → ``{"*"}`` meaning every persona
    auto-closes. ``none`` / ``off`` → empty set (every gate stays open).
    Otherwise → the explicit CSV of roles.
    """
    raw = os.environ.get("PERSONA_AUTO_CLOSE", "").strip()
    if not raw or raw.lower() in {"*", "all"}:
        return {_AUTO_CLOSE_ALL}
    if raw.lower() in {"none", "off"}:
        return set()
    return {part.strip() for part in raw.split(",") if part.strip()}


def _role_auto_closes(role: str, auto_close: set[str] | None = None) -> bool:
    """Membership check that honours the ``*`` everything-auto-closes sentinel."""
    s = _auto_close_set() if auto_close is None else auto_close
    return _AUTO_CLOSE_ALL in s or role in s


# Cache of (role -> parent_role | None) built from every Function.persona_hierarchy
# in api.shared.functions.FUNCTIONS. Built lazily on first call. A role appearing
# in multiple functions resolves to the FIRST hierarchy that lists it (ambiguous
# membership is unusual; roles like `cfo` map to `None` because they sit at the top).
_ESCALATION_PARENT_CACHE: dict[str, str | None] | None = None


def _escalation_parent(role: str) -> str | None:
    """Return the role's parent in the function's persona hierarchy, or None.

    Used by the escalation auto-cascade: when a persona returns ``escalate``
    we re-run the decision as the parent so the workflow doesn't park at
    the lowest tier when a deterministic chain of approvers exists.
    """
    global _ESCALATION_PARENT_CACHE
    if _ESCALATION_PARENT_CACHE is None:
        cache: dict[str, str | None] = {}
        try:
            from api.shared.functions import FUNCTIONS

            def _walk(node, parent):
                if node.role not in cache:
                    cache[node.role] = parent
                for child in (node.manages or ()):
                    _walk(child, node.role)

            for fn in FUNCTIONS.values():
                _walk(fn.persona_hierarchy, None)
        except Exception as ex:
            print(f"[persona_responder] failed to build escalation parent cache: {ex}")
        _ESCALATION_PARENT_CACHE = cache
    return _ESCALATION_PARENT_CACHE.get(role)


def _wait_probability_for(workflow_id: str | None, gate_phase: str | None) -> float:
    """Look up the per-gate wait_probability declared in api/shared/domains.py.

    Resolution: workflow_id → workflow_type → Domain → matching HitlGate.
    Returns 0.0 (legacy auto-close) if anything along the chain is missing
    so unknown gates behave the same as before this change.
    """
    gate = _hitl_gate_for(workflow_id, gate_phase)
    return gate.wait_probability if gate is not None else 0.0


def _hitl_gate_for(workflow_id: str | None, gate_phase: str | None):
    """Resolve a workflow_id + gate_phase to its HitlGate metadata.

    Returns ``None`` if anything along the resolution chain (workflow
    not in store, unknown workflow_type, no matching gate_phase) is
    missing — callers must treat that as "no edge-case behaviour"
    (legacy auto-close path).
    """
    if not (workflow_id and gate_phase):
        return None
    try:
        from api.server.state import app_state
        from api.shared.domains import DOMAINS
        wf = app_state.store.get_workflow(workflow_id)
        if wf is None:
            return None
        domain = DOMAINS.get(getattr(wf, "type", None) or "")
        if domain is None:
            return None
        for g in domain.hitl_gates:
            if g.gate_phase == gate_phase:
                return g
    except Exception:
        return None
    return None


def _workflow_type_for(workflow_id: str | None) -> str | None:
    """Resolve workflow_id → workflow.type (the I4 ``domain`` axis).

    Returns ``None`` when the workflow isn't in the store (tests, partial
    state). Callers are expected to no-op on ``None`` — the in-memory
    routing stats then simply skip recording for that decision.
    """
    if not workflow_id:
        return None
    try:
        from api.server.state import app_state
        wf = app_state.store.get_workflow(workflow_id)
        return getattr(wf, "type", None) if wf is not None else None
    except Exception:
        return None


# --------------------------------------------------------------------------
# Persona loading from SKILL.md frontmatter
# --------------------------------------------------------------------------


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split a SKILL.md into (frontmatter dict, body text). Returns ({}, text)
    when there is no recognisable frontmatter block."""
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text
    fm_text = "\n".join(lines[1:end])
    body_text = "\n".join(lines[end + 1:])
    try:
        data = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError as ex:
        raise ValueError(f"persona SKILL.md frontmatter is not valid YAML: {ex}") from ex
    if not isinstance(data, dict):
        raise ValueError("persona SKILL.md frontmatter must be a YAML mapping")
    return data, body_text


# Builtins the decision_policy code is allowed to use. Tightly scoped so a
# typo in a SKILL.md can't reach into the FastAPI process beyond computing a
# decision against the context dict.
#
# `authority_check` is the substrate seam to the delegated-authority matrix.
# Personae call it from inside their `decision_policy` block to confirm
# "am I authorised to sign this off?" instead of inlining a numeric
# threshold. Phase 3 TASK-023: this now resolves through
# ``governance.kernel().check_authority(...)`` directly — no HTTP round-trip
# in the default (in-process) path. The Foundry-IQ swap-in seam is
# preserved one layer down: ``delegated_authority.check_authority`` (which
# the kernel does NOT call from here) still falls back to HTTP when
# ``AUTHORITY_MCP_URL`` is set, so the engagement-POC contract is
# unchanged for personae configured against a remote authority MCP.
def _sandbox_authority_check(
    role: str,
    action: str,
    value: float | None = None,
    category: str | None = None,
    business_unit: str | None = None,
    geography: str | None = None,
    requester_role: str | None = None,
) -> dict[str, Any]:
    """Sandbox-callable wrapper around ``governance.kernel().check_authority``.

    Returns a plain dict (not a Pydantic object) so decision_policy code
    can read fields without importing types. Falls back to
    ``{allowed: False, reason: "...", governing_rule_id: None}`` on any
    kernel error — the persona then knows to defer rather than guess.

    When ``AUTHORITY_MCP_URL`` is set in env, defers to the HTTP path
    via ``api.server.mcp_tools.delegated_authority.check_authority`` so
    a Foundry-IQ swap-in is honoured (engagement-POC seam, REQ-002).
    """
    try:
        if os.environ.get("AUTHORITY_MCP_URL"):
            # Engagement-POC swap-in path: keep the HTTP indirection so
            # the same env var that flips the rest of the substrate
            # also flips persona authority lookups.
            from api.server.mcp_tools.delegated_authority import check_authority

            result = check_authority(
                role=role,
                action=action,
                value=value,
                category=category,
                business_unit=business_unit,
                geography=geography,
                requester_role=requester_role,
            )
            return {
                "allowed": result.allowed,
                "reason": result.reason,
                "governing_rule_id": result.governing_rule_id,
            }

        # Default in-process path — TASK-023.
        from api.server.services.governance import kernel

        result = kernel().check_authority(
            role=role,
            action=action,
            value=value,
            category=category,
            business_unit=business_unit,
            geography=geography,
            requester_role=requester_role,
        )
        return {
            "allowed": result.allowed,
            "reason": result.reason,
            "governing_rule_id": result.governing_rule_id,
        }
    except Exception as ex:  # pragma: no cover — defensive only
        return {
            "allowed": False,
            "reason": f"authority resolution failed: {ex}",
            "governing_rule_id": None,
        }


def _sandbox_query_precedents(
    persona_role: str,
    entity_id: str,
    limit: int = 10,
    *,
    workflow_type: str | None = None,
    phase: str | None = None,
) -> list[dict[str, Any]]:
    """Sandbox-safe wrapper around the query_precedents MCP tool.

    Phase 4 IP3 (TASK-016, DEC-OQ1). Persona ``decision_policy`` blocks
    may call ``precedents = query_precedents(persona_role, entity_id,
    limit=10)`` to fetch recent ``Decision`` nodes for the entity. Lazy
    imports keep persona_responder import-light at boot.
    """
    try:
        from api.server.state import app_state
        from api.server.mcp_tools.query_precedents import make_query_precedents_tool

        tool = make_query_precedents_tool(app_state.entities)
        return tool(
            persona_role,
            entity_id,
            limit,
            workflow_type=workflow_type,
            phase=phase,
        )
    except Exception:  # pragma: no cover — degrade to "no precedent"
        return []


def _sandbox_precedent_check(
    workflow_type: str | None = None,
    phase: str | None = None,
    persona_role: str | None = None,
    decided_on: tuple = (),
    *,
    cite_from_decision_id: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Pitch I1: aggregate the persona's recent precedents into a single verdict.

    Returns a dict with keys ``verdict``, ``confidence``, ``n_precedents``,
    ``hits``. When no precedents are found (or the entity-graph plane is
    disabled) returns ``{"verdict": None, "n_precedents": 0,
    "confidence": 0.0, "hits": []}`` so callers can branch on
    ``n_precedents``. ``decided_on`` carries the entity ids the current
    workflow touches; the first id (if any) is used to scope the lookup
    to *this* entity's history (e.g. the same vendor / brand / period).

    The callable is intentionally permissive: any exception in the
    underlying MCP tool degrades silently to "no precedents" so a flaky
    graph never breaks a persona decision.
    """
    try:
        from api.server.state import app_state
        from api.server.mcp_tools.query_precedents import make_query_precedents_tool

        tool = make_query_precedents_tool(app_state.entities)
        entity_id = ""
        if decided_on:
            try:
                entity_id = str(decided_on[0]) if decided_on[0] else ""
            except Exception:
                entity_id = ""
        rows = tool(
            persona_role or "",
            entity_id,
            int(limit),
            workflow_type=workflow_type,
            phase=phase,
            cite_from_decision_id=cite_from_decision_id,
        )
    except Exception:
        rows = []

    verdicts: list[str] = []
    for row in rows or []:
        d = row.get("d") if isinstance(row, dict) else None
        if isinstance(d, dict):
            v = d.get("verdict") or d.get("decision")
            if v:
                verdicts.append(str(v))
    if not verdicts:
        return {"verdict": None, "n_precedents": 0, "confidence": 0.0, "hits": []}

    from collections import Counter
    counts = Counter(verdicts)
    top_verdict, top_count = counts.most_common(1)[0]
    return {
        "verdict": top_verdict,
        "confidence": top_count / len(verdicts),
        "n_precedents": top_count,
        "hits": verdicts,
    }


def _lazy_app_graph():
    """Resolve the live EntityGraph at call-time.

    Lazy because app_state imports persona_responder transitively at boot;
    importing app_state at module top would create a cycle. Tests can
    monkeypatch this function to point at a tmp_path EntityGraph.
    """
    from api.server.state import app_state
    return app_state.entities


_DECISION_BUILTINS: dict[str, Any] = {
    "isinstance": isinstance, "len": len,
    "str": str, "int": int, "float": float, "bool": bool,
    "list": list, "dict": dict, "set": set, "tuple": tuple,
    "min": min, "max": max, "abs": abs, "round": round,
    "any": any, "all": all, "sum": sum,
    "True": True, "False": False, "None": None,
    "authority_check": _sandbox_authority_check,
    "query_precedents": _sandbox_query_precedents,
    "precedent_check": _sandbox_precedent_check,
}


# ---------------------------------------------------------------------------
# AST whitelist — defence in depth on top of _DECISION_BUILTINS.
# ---------------------------------------------------------------------------
#
# _DECISION_BUILTINS replaces ``__builtins__`` so a persona policy cannot
# call ``__import__``, ``eval``, ``exec``, ``getattr``, etc. by name. That
# blocks the obvious attacks, but Python supports reflection escape paths
# that bypass the builtins gate entirely:
#
#   ().__class__.__mro__[1].__subclasses__()  →  walks to arbitrary classes
#   (1).__class__.__bases__                   →  reaches `object`, then the
#                                                full type hierarchy
#   try: 1/0
#   except Exception as e:
#       e.__traceback__.tb_frame.f_globals    →  reaches the caller's globals
#
# All three of these read like "attribute access whose attr name is a
# dunder" — `__class__`, `__bases__`, `__mro__`, `__subclasses__`,
# `__globals__`, `__code__`, `__traceback__`, etc. The AST guard below
# rejects any such access at compile time so the sandbox doesn't rely on
# runtime-only enforcement.
#
# Personae are also forbidden from declaring new modules, classes, or
# global state — none of the 79 shipped personae need any of these.
#
# All three persona blocks (decision_policy, summary_policy, voice_render)
# share this guard via ``_validate_persona_source``.


def _validate_persona_source(source: str, role: str, kind: str) -> None:
    """Parse ``source`` and reject sandbox-escape AST patterns.

    Called before ``compile()`` for every persona policy block. Raises
    ``ValueError`` with a clear message identifying the role + kind +
    line number if the source contains:

    * Attribute access whose attr name is a dunder (``__class__``,
      ``__mro__``, ``__globals__``, ``__traceback__``, ...). These are
      the reflection paths that bypass ``_DECISION_BUILTINS``.
    * ``import`` or ``from ... import ...`` statements — never needed by
      a persona policy and would (if `__import__` were available) reach
      arbitrary modules.
    * ``class`` definitions — not needed and a vector for shadowing
      sandbox helpers.
    * ``global`` / ``nonlocal`` declarations — would let a policy mutate
      module-scope state.

    Existing personae (audited at the time of this guard's introduction)
    use **zero** of these patterns, so adding the gate is a strict
    no-op for the shipped surface.
    """
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError as ex:
        raise ValueError(
            f"persona '{role}' {kind} fails to parse: {ex}"
        ) from ex

    tag = f"persona '{role}' {kind}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            attr = node.attr
            if attr.startswith("__") and attr.endswith("__"):
                raise ValueError(
                    f"{tag}: forbidden in persona sandbox at line "
                    f"{node.lineno}: dunder attribute access "
                    f"'.{attr}' (sandbox-escape vector)"
                )
        elif isinstance(node, ast.Import):
            names = ", ".join(alias.name for alias in node.names)
            raise ValueError(
                f"{tag}: forbidden in persona sandbox at line "
                f"{node.lineno}: `import {names}` statement"
            )
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or "."
            raise ValueError(
                f"{tag}: forbidden in persona sandbox at line "
                f"{node.lineno}: `from {mod} import ...` statement"
            )
        elif isinstance(node, ast.ClassDef):
            raise ValueError(
                f"{tag}: forbidden in persona sandbox at line "
                f"{node.lineno}: `class {node.name}` definition"
            )
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            kw = "global" if isinstance(node, ast.Global) else "nonlocal"
            raise ValueError(
                f"{tag}: forbidden in persona sandbox at line "
                f"{node.lineno}: `{kw}` declaration"
            )


# Pitch D4: per-persona personality knobs. Same role + different humans
# (Aisha vs. Marcus) produce *different* decisions. SKILL.md frontmatter
# may declare `personality:` with any subset of these keys; missing keys
# fall back to the trio below.
_DEFAULT_PERSONALITY: dict[str, str] = {
    "risk_appetite": "balanced",       # conservative | balanced | aggressive
    "thoroughness": "medium",          # low | medium | high
    "escalation_style": "standard",    # quick | standard | reluctant
}


def _resolve_personality(raw: Any) -> dict[str, str]:
    """Coerce a SKILL.md ``personality:`` block into a fully-shaped dict.

    Always returns a dict with exactly the three keys in
    ``_DEFAULT_PERSONALITY``. Unknown keys in the source block are
    dropped. Non-dict / missing input → all defaults. Non-string values
    are coerced via ``str()`` so a typo like ``risk_appetite: True``
    doesn't blow up the loader.
    """
    out = dict(_DEFAULT_PERSONALITY)
    if isinstance(raw, dict):
        for key in _DEFAULT_PERSONALITY:
            if key in raw and raw[key] is not None:
                out[key] = str(raw[key])
    return out


def _compile_decision_policy(
    role: str,
    source: str,
    personality: dict[str, str] | None = None,
) -> PersonaHandler:
    """Compile a ``decision_policy`` source block into a callable that takes
    a context dict and returns ``{"decision", "reason"}``.

    The source runs in an isolated namespace where only ``context`` is in
    scope plus a small whitelist of safe builtins. The source MUST assign
    ``decision`` (str: "approve" | "reject" | "escalate") and ``reason``
    (str). Any exception falls back to a reject with the exception text
    as the reason — the orchestrator never sits forever on a broken
    persona policy.

    The ``escalate`` verdict (Phase 6 of feature-fleet-domain-substrate-1)
    means the persona refuses to auto-decide; the responder leaves the
    Durable gate open and emits a richer FleetEvent so the FM picks it up
    via triage.
    """
    cleaned = textwrap.dedent(source)
    # Pitch D4: lock in the personality dict at compile time so each
    # PersonaDefinition's `decide()` carries its own humans-are-different
    # knobs without a per-call lookup. Always shaped, never None.
    persona_personality: dict[str, str] = dict(personality or _DEFAULT_PERSONALITY)
    _validate_persona_source(cleaned, role, "decision_policy")
    try:
        code = compile(cleaned, f"<persona:{role}:decision_policy>", "exec")
    except SyntaxError as ex:
        raise ValueError(f"persona '{role}' decision_policy fails to compile: {ex}") from ex

    def decide(context: dict[str, Any]) -> dict[str, Any]:
        from api.server.services.policy_lookup import active_policies_for as _apf
        ns: dict[str, Any] = {
            "context": context,
            "decision": None,
            "reason": None,
            # D4: per-persona personality knobs are always in scope so a
            # decision_policy can branch on `personality.get('risk_appetite')`
            # etc. Pass a copy so a misbehaving policy can't mutate the
            # PersonaDefinition's stored dict.
            "personality": dict(persona_personality),
            "graph": _lazy_app_graph(),
            "active_policies_for": _apf,
        }
        try:
            exec(code, {"__builtins__": _DECISION_BUILTINS}, ns)
        except Exception as ex:
            return {"decision": "reject", "reason": f"persona handler error: {ex}"}
        decision = ns.get("decision")
        reason = ns.get("reason")
        if decision not in {"approve", "reject", "escalate"}:
            return {"decision": "reject",
                    "reason": f"persona '{role}' produced invalid decision={decision!r} "
                              f"(expected 'approve' | 'reject' | 'escalate')"}
        out: dict[str, Any] = {
            "decision": str(decision),
            "reason": str(reason or ""),
        }
        # Optional `extra` dict from the policy: merge into the resolving
        # event payload so multi-gate personae (e.g. creative_director)
        # can pass per-gate context downstream — transcripts after voice
        # intake, locked_route after concept_lock, etc. Existing personae
        # that don't define `extra` are unaffected.
        extra = ns.get("extra")
        if isinstance(extra, dict):
            for k, v in extra.items():
                if k not in out:
                    out[k] = v
        return out

    return decide


def _compile_summary_policy(role: str, source: str) -> PersonaHandler:
    """Compile a `summary_policy` source block into a callable.

    Same sandbox shape as decision_policy (graph + active_policies_for in
    namespace, _DECISION_BUILTINS as builtins). The source MUST assign
    `summary` (a dict with keys: headline, body, kpis, proposed_actions,
    fingerprint) OR set `summary = None` to indicate no change since last
    Insight (the responder skips writing in that case).

    The handler is invoked with `context = {"last_insight": <dict|None>}`
    so the source can compare its computed fingerprint against the prior
    one and short-circuit by returning None.
    """
    cleaned = textwrap.dedent(source)
    _validate_persona_source(cleaned, role, "summary_policy")
    try:
        code = compile(cleaned, f"<persona:{role}:summary_policy>", "exec")
    except SyntaxError as ex:
        raise ValueError(f"persona '{role}' summary_policy fails to compile: {ex}") from ex

    def summarise(context: dict[str, Any]) -> dict[str, Any]:
        from api.server.services.policy_lookup import active_policies_for as _apf
        ns: dict[str, Any] = {
            "context": context,
            "summary": None,
            "graph": _lazy_app_graph(),
            "active_policies_for": _apf,
        }
        try:
            exec(code, {"__builtins__": _DECISION_BUILTINS}, ns)
        except Exception as ex:
            return {"error": f"persona '{role}' summary_policy error: {ex}"}
        out = ns.get("summary")
        if out is None:
            return {"skip": True}
        if not isinstance(out, dict):
            return {"error": f"persona '{role}' summary_policy returned {type(out).__name__}, want dict"}
        out.setdefault("headline", "")
        out.setdefault("body", "")
        out.setdefault("kpis", {})
        out.setdefault("proposed_actions", [])
        if "fingerprint" not in out:
            return {"error": f"persona '{role}' summary_policy missing 'fingerprint'"}
        return out

    return summarise


def _compile_voice_render(role: str, source: str) -> PersonaHandler:
    """Compile a `voice_render` source block into a callable.

    Receives `context = {"summary": <dict>}` (the dict returned by
    summary_policy). The source MUST set `body = "<string>"`.
    Errors return {"body": None}; the responder falls through to the
    structured body in that case.
    """
    cleaned = textwrap.dedent(source)
    _validate_persona_source(cleaned, role, "voice_render")
    try:
        code = compile(cleaned, f"<persona:{role}:voice_render>", "exec")
    except SyntaxError as ex:
        raise ValueError(f"persona '{role}' voice_render fails to compile: {ex}") from ex

    def render(context: dict[str, Any]) -> dict[str, Any]:
        ns: dict[str, Any] = {
            "context": context,
            "summary": context.get("summary") or {},
            "body": None,
        }
        try:
            exec(code, {"__builtins__": _DECISION_BUILTINS}, ns)
        except Exception:
            return {"body": None}
        body = ns.get("body")
        return {"body": str(body) if isinstance(body, str) else None}

    return render


def personae_with_summary_policy() -> list[PersonaDefinition]:
    """Return loaded personae whose SKILL.md declared a summary_policy block."""
    return [p for p in PERSONA_DEFINITIONS.values() if p.summarise is not None]


def _load_personae() -> dict[str, PersonaDefinition]:
    """Walk PERSONAE_DIR for SKILL.md files; load + compile each."""
    out: dict[str, PersonaDefinition] = {}
    if not PERSONAE_DIR.exists():
        return out
    for skill_path in sorted(PERSONAE_DIR.glob("*/SKILL.md")):
        try:
            text = skill_path.read_text(encoding="utf-8")
            fm, _body = _split_frontmatter(text)
            role = fm.get("name") or skill_path.parent.name
            description = fm.get("description") or ""
            workflow_label = fm.get("workflow_label") or "?"
            external_event = fm.get("external_event")
            decision_src = fm.get("decision_policy")
            personality = _resolve_personality(fm.get("personality"))
            if not external_event or not isinstance(decision_src, str):
                print(f"[persona_responder] {skill_path}: missing external_event or "
                      f"decision_policy in frontmatter; skipping")
                continue
            decide = _compile_decision_policy(str(role), decision_src, personality)
            summary_src = fm.get("summary_policy")
            summarise = None
            if isinstance(summary_src, str) and summary_src.strip():
                try:
                    summarise = _compile_summary_policy(str(role), summary_src)
                except ValueError as ex:
                    print(f"[persona_responder] {skill_path}: {ex}")
            voice_src = fm.get("voice_render")
            voice = None
            if isinstance(voice_src, str) and voice_src.strip():
                try:
                    voice = _compile_voice_render(str(role), voice_src)
                except ValueError as ex:
                    print(f"[persona_responder] {skill_path}: {ex}")
            out[str(role)] = PersonaDefinition(
                role=str(role),
                description=str(description),
                workflow_label=str(workflow_label),
                external_event=str(external_event),
                decide=decide,
                skill_path=skill_path,
                personality=personality,
                summarise=summarise,
                voice=voice,
            )
        except Exception as ex:
            print(f"[persona_responder] failed to load {skill_path}: {ex}")
    _validate_against_registry(out)
    return out


def _validate_against_registry(loaded: dict[str, "PersonaDefinition"]) -> None:
    """Cross-check loaded personae against api.shared.personas.PERSONAS.

    Warnings only (never raises) so a missing registry entry doesn't
    block startup. Surfaces three classes of drift:
      - registry entry without a SKILL.md (someone added to the registry
        but didn't graduate the persona file)
      - SKILL.md without a registry entry (someone graduated a persona
        without updating the registry)
      - registry's `external_event_default` differs from SKILL.md's
        `external_event`
    """
    try:
        from api.shared.personas import PERSONAS
    except Exception as ex:  # pragma: no cover — defensive only
        print(f"[persona_responder] could not import persona registry: {ex}")
        return

    loaded_roles = set(loaded.keys())
    registry_roles = set(PERSONAS.keys())

    for missing in registry_roles - loaded_roles:
        print(f"[persona_responder] registry has '{missing}' but no SKILL.md exists")
    for stray in loaded_roles - registry_roles:
        print(f"[persona_responder] SKILL.md '{stray}' has no registry entry "
              f"in api.shared.personas.PERSONAS")
    for role in loaded_roles & registry_roles:
        skill = loaded[role]
        reg = PERSONAS[role]
        if reg.external_event_default and reg.external_event_default != skill.external_event:
            print(f"[persona_responder] {role}: registry external_event_default="
                  f"{reg.external_event_default!r} differs from SKILL.md external_event="
                  f"{skill.external_event!r}")


# --------------------------------------------------------------------------
# Bus subscription
# --------------------------------------------------------------------------


async def _cascade_to_delegate(
    *,
    persona_role: str,
    workflow_id: str | None,
    gate_phase: str | None,
    context: dict[str, Any],
    instance_id: str | None,
    event_name: str,
    cascade_depth: int,
    auto_close: set[str],
    reason: str,
) -> None:
    """Cascade the gate handling to the persona's nominated delegate.

    Pitch-c6: shared helper for the sick / holiday / timeout long-tail
    rolls. Mirrors the safety checks of the escalate auto-cascade path
    (depth limit, target exists, target is in auto-close, target has a
    SKILL.md). On any failed check we log + leave the gate open.

    Pitch-h3 (cross-domain entanglement): the cascade target is now
    resolved against the d2 ``AUTHORITY`` matrix first — if the persona
    has an explicit ``delegate_to`` set, route there instead of the
    function-hierarchy parent. This makes OOO / sick / holiday flow to
    the human who is actually covering, not just up the org tree. Falls
    back to ``_escalation_parent`` when ``delegate_to`` is unset so the
    legacy behaviour is preserved for personae without an entry. When
    the cascade fires for a person-availability reason (``ooo`` /
    ``sick`` / ``holiday``) we also emit a ``persona.delegated``
    FleetEvent so the cosmic-lens consumers can surface the hand-off
    ("Marcus on holiday → Daniel covers") as a toast.
    """
    if cascade_depth >= 5:
        print(
            f"[persona_responder] [{reason}] cascade depth limit reached "
            f"for {workflow_id} (started at {persona_role})"
        )
        return

    # H3: prefer the AUTHORITY.delegate_to override; fall back to the
    # persona-hierarchy parent for personae without an explicit delegate.
    target_role: str | None = None
    via_authority = False
    delegate_role: str | None = None
    parent_role: str | None = None
    try:
        from api.shared.authority import delegate_for
        delegate_role = delegate_for(persona_role)
    except Exception:
        delegate_role = None
    parent_role = _escalation_parent(persona_role)

    # I4: when both options exist, the routing optimiser may pick the
    # better-performing candidate. Pass the more-junior delegate first so
    # ties favour pushing work down (the I4 headline). Falls back to the
    # legacy delegate→parent precedence when the optimiser has no opinion.
    workflow_type = _workflow_type_for(workflow_id)
    optimiser_pick: str | None = None
    if delegate_role and parent_role and delegate_role != parent_role:
        try:
            from api.server.services import routing_stats
            optimiser_pick = routing_stats.preferred_role(
                workflow_type, gate_phase,
                [delegate_role, parent_role],
            )
        except Exception:
            optimiser_pick = None
    if optimiser_pick:
        target_role = optimiser_pick
        via_authority = (target_role == delegate_role)
    elif delegate_role:
        target_role = delegate_role
        via_authority = True
    else:
        target_role = parent_role
    if not target_role:
        print(
            f"[persona_responder] [{reason}] {persona_role} has no delegate "
            f"or hierarchy parent; cannot cascade {workflow_id}"
        )
        return
    if not _role_auto_closes(target_role, auto_close):
        print(
            f"[persona_responder] [{reason}] cascade target {target_role!r} "
            f"is not in PERSONA_AUTO_CLOSE; leaving gate open"
        )
        return
    if PERSONA_DEFINITIONS.get(target_role) is None:
        print(
            f"[persona_responder] [{reason}] cascade target {target_role!r} "
            f"has no SKILL.md; leaving gate open"
        )
        return
    print(
        f"[persona_responder] [{reason}] cascade hop {cascade_depth + 1}: "
        f"{persona_role} → {target_role} for {workflow_id} "
        f"(via={'authority' if via_authority else 'hierarchy'})"
    )

    # H3: emit persona.delegated for person-availability cascades so the
    # cosmic lens can render a "X on holiday → Y covers" toast. Timeout /
    # escalation cascades intentionally do NOT emit this — they are not
    # human-availability events.
    if reason in {"ooo", "sick", "holiday"}:
        try:
            from api.server.state import app_state
            app_state.bus.emit(FleetEvent(
                type="persona.delegated",
                workflow_id=workflow_id,
                from_role=persona_role,
                to_role=target_role,
                reason=reason,
                phase=gate_phase,
                instance_id=instance_id,
                via="authority" if via_authority else "hierarchy",
            ))
        except Exception as ex:
            print(f"[persona_responder] failed to emit persona.delegated: {ex}")

    cascade_event = FleetEvent(
        type="workflow.hitl.requested",
        workflow_id=workflow_id,
        persona=target_role,
        phase=gate_phase,
        context=context,
        instance_id=instance_id,
        external_event=event_name or None,
        _cascade_depth=cascade_depth + 1,
    )
    await _handle_hitl(cascade_event)


async def _handle_hitl(event: FleetEvent) -> None:
    """Apply the matching persona's decision policy and raise the resolving event.

    Skipped silently for any persona NOT in PERSONA_AUTO_CLOSE, so real
    humans can drive the gate via the existing portal/UI flows.

    v2 (Org Ops view): emits ``persona.thinking`` BEFORE deciding so the live
    activity stream can show the gate is open and the persona is reasoning;
    then emits ``persona.decided`` AFTER deciding. When ``DEMO_LOUD=1`` the
    responder waits a random 2-8s between thinking and deciding so the
    visualisation actually shows time passing rather than instant flips.

    v3 (escalation auto-cascade): when a persona returns ``escalate`` AND
    the ``PERSONA_ESCALATION_AUTO_CASCADE`` env flag is set (default "1"),
    the responder looks up the persona's parent in the function's persona
    hierarchy and re-runs the decision policy as that parent — preserving
    the *original* external_event so the parent's verdict unblocks the
    original gate. This stops escalation chains piling up at the AP-clerk /
    line-manager tier when the controller / CFO would have approved
    deterministically. Capped at 5 hops to prevent loops.
    """
    import random as _rand

    data = event.model_dump()
    persona_role = data.get("persona")
    external_event_override = data.get("external_event")
    instance_id = data.get("instance_id")
    context = data.get("context") or {}
    workflow_id = data.get("workflow_id")
    gate_phase = data.get("phase") or context.get("phase")
    cascade_depth = int(data.get("_cascade_depth") or 0)

    # No persona contract on this gate (UI-driven legacy path) → nothing to do.
    if not (persona_role and instance_id):
        return

    auto_close = _auto_close_set()
    if not _role_auto_closes(persona_role, auto_close):
        # Real human is supposed to drive this gate. Stay out of their way.
        return

    # Pitch-h3 (cross-domain entanglement): hand-flagged OOO is
    # deterministic. If d2's AUTHORITY matrix marks the persona as
    # ``ooo_today=True``, treat the gate exactly as if a sick roll just
    # hit — cascade to the explicit ``delegate_to`` (or hierarchy parent
    # as fallback) BEFORE rolling the probabilistic sick / holiday /
    # override / timeout dice. This makes "Marcus is on holiday" route
    # unconditionally rather than waiting for a 1-in-N roll.
    try:
        from api.shared.authority import is_ooo
        persona_is_ooo = is_ooo(persona_role)
    except Exception:
        persona_is_ooo = False
    if persona_is_ooo:
        print(
            f"[persona_responder] [ooo] {persona_role} is OOO today "
            f"(AUTHORITY.ooo_today=True) for {workflow_id} "
            f"gate={gate_phase}; cascading to delegate"
        )
        await _cascade_to_delegate(
            persona_role=persona_role,
            workflow_id=workflow_id,
            gate_phase=gate_phase,
            context=context,
            instance_id=instance_id,
            event_name=external_event_override or "",
            cascade_depth=cascade_depth,
            auto_close=auto_close,
            reason="ooo",
        )
        return

    # Pitch-c6: long-tail HITL personae. Roll 4 independent dice (sick,
    # holiday, override, timeout) — the FIRST that hits wins; the rest
    # are skipped for this gate hit. Defaults are 0.0 so gates without
    # tactical edge-case probabilities behave exactly as before.
    gate_meta = _hitl_gate_for(workflow_id, gate_phase)
    override_invert = False
    if gate_meta is not None:
        sick_hit = _rand.random() < gate_meta.sick_probability
        holiday_hit = _rand.random() < gate_meta.holiday_probability
        override_hit = _rand.random() < gate_meta.override_probability
        timeout_hit = _rand.random() < gate_meta.timeout_probability
        first_hit = next(
            (name for name, hit in (
                ("sick", sick_hit),
                ("holiday", holiday_hit),
                ("override", override_hit),
                ("timeout", timeout_hit),
            ) if hit),
            None,
        )
        if first_hit == "sick":
            print(
                f"[persona_responder] [sick] {persona_role} is sick today "
                f"for {workflow_id} gate={gate_phase}; cascading to delegate"
            )
            await _cascade_to_delegate(
                persona_role=persona_role,
                workflow_id=workflow_id,
                gate_phase=gate_phase,
                context=context,
                instance_id=instance_id,
                event_name=external_event_override or "",
                cascade_depth=cascade_depth,
                auto_close=auto_close,
                reason="sick",
            )
            return
        if first_hit == "holiday":
            print(
                f"[persona_responder] [holiday] {persona_role} is on holiday "
                f"for {workflow_id} gate={gate_phase}; cascading to delegate"
            )
            await _cascade_to_delegate(
                persona_role=persona_role,
                workflow_id=workflow_id,
                gate_phase=gate_phase,
                context=context,
                instance_id=instance_id,
                event_name=external_event_override or "",
                cascade_depth=cascade_depth,
                auto_close=auto_close,
                reason="holiday",
            )
            return
        if first_hit == "timeout":
            print(
                f"[persona_responder] [timeout] {persona_role} timed out "
                f"for {workflow_id} gate={gate_phase}; emitting "
                f"workflow.hitl.timeout + cascading to parent"
            )
            try:
                from api.server.state import app_state
                app_state.bus.emit(FleetEvent(
                    type="workflow.hitl.timeout",
                    workflow_id=workflow_id,
                    persona=persona_role,
                    phase=gate_phase,
                    instance_id=instance_id,
                    external_event=external_event_override,
                ))
            except Exception as ex:
                print(f"[persona_responder] failed to emit hitl.timeout: {ex}")
            await _cascade_to_delegate(
                persona_role=persona_role,
                workflow_id=workflow_id,
                gate_phase=gate_phase,
                context=context,
                instance_id=instance_id,
                event_name=external_event_override or "",
                cascade_depth=cascade_depth,
                auto_close=auto_close,
                reason="timeout",
            )
            return
        if first_hit == "override":
            # Defer inversion until after persona.decide() returns.
            override_invert = True

    # C4: per-gate wait_probability. If the gate would otherwise auto-close,
    # roll the die. On "wait" the gate stays open and produces a real
    # workflow.exception.detected + workflow.hitl.requested pair (already
    # emitted upstream by internal_durable_event.py when the gate trips).
    wait_p = _wait_probability_for(workflow_id, gate_phase)
    if wait_p > 0.0 and _rand.random() < wait_p:
        log_msg = (
            f"[persona_responder] wait_probability {wait_p:.2f} fired for "
            f"workflow_id={workflow_id} gate={gate_phase} "
            f"persona={persona_role} — leaving gate open"
        )
        print(log_msg)
        return

    persona = PERSONA_DEFINITIONS.get(persona_role)
    if persona is None:
        print(f"[persona_responder] AUTO_CLOSE includes {persona_role!r} but no "
              f"SKILL.md defines that persona; gate stays open")
        return

    # v2: announce that the persona is thinking. The ops view reads this to
    # show a "thinking..." pill in the persona strip + a typing indicator in
    # the conversations view + a slow-pulse on the river's gate chip.
    try:
        from api.server.state import app_state
        app_state.bus.emit(FleetEvent(
            type="persona.thinking",
            workflow_id=workflow_id,
            persona=persona_role,
            phase=gate_phase,
            instance_id=instance_id,
            external_event=external_event_override or persona.external_event,
            personality=dict(persona.personality),
        ))
    except Exception as ex:  # pragma: no cover — bus emit is best-effort
        print(f"[persona_responder] failed to emit persona.thinking: {ex}")

    # v2: simulate human reaction time so the demo isn't a blur. Off by
    # default in tests / production-honest mode; on when DEMO_LOUD=1.
    if os.environ.get("DEMO_LOUD", "0") == "1":
        delay = _rand.uniform(2.0, 8.0)
        await asyncio.sleep(delay)

    try:
        decision_payload = persona.decide(context)
    except Exception as ex:
        print(f"[persona_responder] persona {persona_role!r} crashed: {ex}")
        return

    event_name = external_event_override or persona.external_event
    decision_str = decision_payload.get("decision")

    # Pitch-c6: override roll won — invert the persona's policy decision
    # to demo human defiance. approve→reject, reject→approve,
    # escalate→approve. Keep the original reason but mark with a tag
    # so logs + decision-stash callers can see the override clearly.
    if override_invert:
        invert_map = {"approve": "reject", "reject": "approve", "escalate": "approve"}
        original_decision = decision_str
        new_decision = invert_map.get(decision_str or "", decision_str)
        original_reason = decision_payload.get("reason") or ""
        decision_payload = dict(decision_payload)
        decision_payload["decision"] = new_decision
        decision_payload["reason"] = f"[override] {original_reason}".strip()
        print(
            f"[persona_responder] [override] {persona_role} overrode policy "
            f"for {workflow_id} gate={gate_phase}: "
            f"{original_decision!r} → {new_decision!r}"
        )
        decision_str = new_decision

    # Phase 6 of feature-fleet-domain-substrate-1: when a persona returns
    # `escalate`, do NOT raise the orchestration event by default. The
    # Durable gate stays parked; we publish a richer FleetEvent so the FM
    # picks it up via triage.should_wake (workflow.hitl.escalated is in
    # WAKE_TYPES). v3: with PERSONA_ESCALATION_AUTO_CASCADE=1 (default)
    # we ALSO retry the decision as the persona's hierarchy parent so a
    # deterministic chain doesn't pile up at the lowest tier.
    if decision_str == "escalate":
        print(
            f"[persona_responder] {persona_role} ESCALATED "
            f"{data.get('workflow_id')} ({decision_payload.get('reason')}); "
            f"gate {event_name!r} stays open for FM/operator"
        )
        try:
            from api.server.state import app_state
            app_state.bus.emit(FleetEvent(
                type="workflow.hitl.escalated",
                workflow_id=data.get("workflow_id"),
                persona=persona_role,
                reason=decision_payload.get("reason"),
                context=context,
                instance_id=instance_id,
                external_event=event_name,
            ))
        except Exception as ex:
            print(f"[persona_responder] failed to emit hitl.escalated: {ex}")

        # Auto-cascade up the persona hierarchy.
        if os.environ.get("PERSONA_ESCALATION_AUTO_CASCADE", "1") != "1":
            return
        if cascade_depth >= 5:
            print(
                f"[persona_responder] cascade depth limit reached for "
                f"{workflow_id} (started at {persona_role}); leaving gate open"
            )
            return
        parent_role = _escalation_parent(persona_role)
        if not parent_role:
            print(
                f"[persona_responder] {persona_role} has no parent in any "
                f"function hierarchy; cannot cascade {workflow_id}"
            )
            return
        if not _role_auto_closes(parent_role, auto_close):
            print(
                f"[persona_responder] cascade target {parent_role!r} is not "
                f"in PERSONA_AUTO_CLOSE; leaving gate open"
            )
            return
        if PERSONA_DEFINITIONS.get(parent_role) is None:
            print(
                f"[persona_responder] cascade target {parent_role!r} has no "
                f"SKILL.md; leaving gate open"
            )
            return
        print(
            f"[persona_responder] cascade hop {cascade_depth + 1}: "
            f"{persona_role} → {parent_role} for {workflow_id} (preserving "
            f"original event {event_name!r})"
        )
        # Build a synthetic event addressed at the parent persona but
        # carrying the ORIGINAL external_event so the parent's verdict
        # unblocks the original gate.
        cascade_event = FleetEvent(
            type="workflow.hitl.requested",
            workflow_id=workflow_id,
            persona=parent_role,
            phase=gate_phase,
            context=context,
            instance_id=instance_id,
            external_event=event_name,
            _cascade_depth=cascade_depth + 1,
        )
        await _handle_hitl(cascade_event)
        return

    print(
        f"[persona_responder] {persona_role} decided "
        f"{decision_str!r} for {data.get('workflow_id')} "
        f"({data.get('reason')}); raising {event_name!r}"
    )

    # Phase 1 sub-phase 3 follow-up — stash the decision into
    # workflow.payload['decisions'] so the entity-graph projection's
    # ``find_decision`` helper can pick it up when ``workflow.completed``
    # fires. The Durable external event we raise below carries the verdict
    # to the orchestrator but doesn't write it back to the Workflow record;
    # without this stash, projections see no decisions and Decision nodes
    # never materialise. Gate the write so it's a silent no-op when the
    # workflow isn't in the store (e.g. tests, half-torn-down state).
    if workflow_id and gate_phase:
        try:
            from api.server.state import app_state
            import datetime as _dt
            w = app_state.store.get_workflow(workflow_id)
            if w is not None:
                if not isinstance(w.payload, dict):
                    w.payload = {}
                decisions = list(w.payload.get("decisions") or [])
                # Idempotent on the natural key (phase, persona_role) — re-emits
                # of the same gate update in place rather than appending dupes.
                key = (str(gate_phase).lower(), str(persona_role).lower())
                decisions = [
                    d for d in decisions
                    if (str(d.get("phase", "")).lower(),
                        str(d.get("persona_role", "")).lower()) != key
                ]
                decisions.append({
                    "phase": gate_phase,
                    "persona_role": persona_role,
                    "verdict": decision_str,
                    "reason": decision_payload.get("reason"),
                    "decided_at": _dt.datetime.now(tz=_dt.timezone.utc).isoformat(),
                    "source_event": event_name,
                })
                w.payload["decisions"] = decisions
                app_state.store.upsert_workflow(w)
        except Exception as ex:
            print(f"[persona_responder] failed to stash decision: {ex}")

    # v2: announce the decision. Ops live stream renders a green/red row;
    # conversations view shows the message as @persona; river highlights the
    # gate chip and slides the workflow forward.
    try:
        from api.server.state import app_state
        app_state.bus.emit(FleetEvent(
            type="persona.decided",
            workflow_id=workflow_id,
            persona=persona_role,
            phase=gate_phase,
            verdict=decision_str,
            reason=decision_payload.get("reason"),
            instance_id=instance_id,
            external_event=event_name,
            personality=dict(persona.personality),
        ))
    except Exception as ex:
        print(f"[persona_responder] failed to emit persona.decided: {ex}")

    # I4 / I6: record the decision into the routing optimiser + per-persona
    # experience matrix so future cascades + tie-breaks have data to learn
    # from. Best-effort — never blocks the orchestration event.
    try:
        domain = _workflow_type_for(workflow_id)
        from api.server.services import routing_stats
        routing_stats.record(
            domain, gate_phase, persona_role,
            approved=(decision_str == "approve"),
        )
    except Exception as ex:  # pragma: no cover — defensive only
        print(f"[persona_responder] routing_stats.record failed: {ex}")
    try:
        domain = _workflow_type_for(workflow_id)
        from api.server.services import persona_experience
        persona_experience.record_decision(persona_role, domain)
    except Exception as ex:  # pragma: no cover — defensive only
        print(f"[persona_responder] persona_experience.record failed: {ex}")

    # Dream-pass producer: write a working-memory entry for every
    # persona decision so the cadence loop has signal to consolidate.
    # Best-effort; never blocks the orchestration event.
    try:
        from api.server.services.memory.working_memory_writer import (
            write_decision_memory,
        )
        signals: dict = {}
        if isinstance(context, dict):
            for k in ("voice_score", "cv_score", "amount", "risk", "country"):
                if context.get(k) is not None:
                    signals[k] = context.get(k)
        write_decision_memory(
            domain=_workflow_type_for(workflow_id),
            persona_role=persona_role,
            verdict=str(decision_str or ""),
            reason=str(decision_payload.get("reason") or "") or None,
            workflow_id=workflow_id,
            gate_phase=gate_phase,
            signals=signals or None,
        )
    except Exception as ex:  # pragma: no cover — defensive only
        print(f"[persona_responder] write_decision_memory failed: {ex}")

    # pitch-j3: per-domain decision-latency trend. Compute the wall-time
    # between workflow.created_at and now (the moment we resolved the
    # gate) and record it into kpi_history under
    # ``decision_latency_seconds`` namespaced by workflow_type. This is
    # cheap, best-effort, and silent on missing pieces (no workflow,
    # unknown type, stale store) so it never blocks the orchestration
    # event.
    try:
        from api.server.state import app_state as _ja_state
        wf = (
            _ja_state.store.get_workflow(workflow_id)
            if workflow_id
            else None
        )
        wf_type = (
            getattr(wf, "type", None) if wf is not None else None
        ) or _workflow_type_for(workflow_id)
        created_at = getattr(wf, "created_at", None) if wf is not None else None
        if wf_type and created_at is not None:
            import time as _jt
            latency = max(0.0, _jt.time() - float(created_at))
            from api.server.services import kpi_history
            kpi_history.record(
                "decision_latency_seconds", latency, dim=str(wf_type)
            )
    except Exception as ex:  # pragma: no cover — defensive only
        print(f"[persona_responder] kpi_history.record latency failed: {ex}")

    try:
        delivered = await raise_orchestration_event(instance_id, event_name, decision_payload)
    except Exception as ex:
        print(
            f"[persona_responder] failed to raise {event_name!r} on "
            f"instance {instance_id}: {ex}"
        )
        return

    if delivered is False:
        # Orchestration is gone (404) — typically a zombie left from an
        # Azurite wipe across boots. The persona has decided but no live
        # orchestration is listening. Mark the workflow completed in the
        # store directly so it stops sitting in awaiting_hitl forever and
        # so the demo keeps moving. The decision payload is preserved on
        # workflow.payload['decisions'] above.
        try:
            from api.server.state import app_state
            wf = app_state.store.get_workflow(workflow_id) if workflow_id else None
            if wf is not None and wf.status == "awaiting_hitl":
                wf.status = "completed"
                wf.active_exception_id = None
                payload = dict(wf.payload or {})
                orphans = payload.get("orphan_resolutions") or []
                orphans.append({
                    "event_name": event_name,
                    "verdict": str(decision_payload.get("verdict")) if isinstance(decision_payload, dict) else None,
                    "persona": persona_role,
                    "reason": "orchestration_404_zombie",
                })
                payload["orphan_resolutions"] = orphans
                wf.payload = payload
                app_state.store.upsert_workflow(wf)
                print(
                    f"[persona_responder] orchestration {instance_id} not "
                    f"found (404) — auto-completed zombie workflow "
                    f"{workflow_id} after {persona_role}'s {decision_payload.get('verdict') if isinstance(decision_payload, dict) else '?'} verdict"
                )
        except Exception as ex:
            print(
                f"[persona_responder] failed to auto-complete orphan "
                f"workflow {workflow_id}: {ex}"
            )


async def _handle_summary_request(event: FleetEvent) -> None:
    """Handle a `domain.summary.requested` FleetEvent.

    Looks up the persona by role; reads its last Insight from the graph;
    runs its summary_policy; compares the returned fingerprint with the
    last Insight's; writes a new Insight only on change.

    Phase 3.3 of autonomous-domain-insights v1.
    """
    import json
    import uuid
    from datetime import datetime
    from api.server.services.entity_graph import EntityWrite

    role = (event.payload or {}).get("role")
    if not isinstance(role, str) or not role:
        return
    persona = PERSONA_DEFINITIONS.get(role)
    if persona is None or persona.summarise is None:
        return

    graph = _lazy_app_graph()
    last = _latest_insight_for_role(graph, role)
    try:
        out = persona.summarise({"last_insight": last})
    except Exception as ex:  # pragma: no cover — defensive
        print(f"[persona_responder] summary {role!r} raised: {ex}")
        return
    if not isinstance(out, dict):
        return
    if out.get("error"):
        print(f"[persona_responder] summary {role!r}: {out['error']}")
        return
    if out.get("skip"):
        return

    new_fp = out.get("fingerprint")
    if last is not None and new_fp == last.get("fingerprint"):
        return  # no change

    # v1.2: humanise the body via voice_render when the persona declared one.
    if persona.voice is not None:
        try:
            voiced = persona.voice({"summary": out})
        except Exception as ex:  # pragma: no cover — defensive
            print(f"[persona_responder] voice {role!r} raised: {ex}")
            voiced = None
        if isinstance(voiced, dict):
            spoken = voiced.get("body")
            if isinstance(spoken, str) and spoken:
                out["body"] = spoken

    insight_id = f"INSIGHT-{role}-{uuid.uuid4().hex[:12]}"
    decided_at = datetime.utcnow()
    graph.upsert(EntityWrite(
        kind="Insight",
        id=insight_id,
        attrs={
            "role": role,
            "scope": persona.workflow_label or role,
            "decided_at": decided_at,
            "headline": str(out.get("headline", ""))[:512],
            "body": str(out.get("body", "")),
            "kpis": json.dumps(out.get("kpis") or {}, default=str),
            "proposed_actions": json.dumps(out.get("proposed_actions") or [], default=str),
            "fingerprint": str(new_fp or ""),
            "attributes": json.dumps(out.get("attributes") or {}, default=str),
        },
        source_workflows=(),
    ))

    # Persona-in-the-loop: every proposed_action self-applies, gated only
    # by the AGT matrix (kernel.check_authority). No human approval step.
    proposed = out.get("proposed_actions") or []
    if proposed:
        try:
            from api.server.services.policy_application import apply_proposed_actions
            apply_proposed_actions(role, list(proposed))
        except Exception as ex:  # pragma: no cover — defensive
            print(f"[persona_responder] apply_proposed_actions {role!r} raised: {ex}")

    # Dream-pass producer: a persona summary is an observation. Write it
    # to the working-memory store of the persona's domain so the cadence
    # loop has signal. Domain is `persona.workflow_label` when set.
    try:
        from api.server.services.memory.working_memory_writer import (
            write_summary_memory,
        )
        domain = persona.workflow_label or role
        write_summary_memory(
            domain=domain,
            persona_role=role,
            headline=str(out.get("headline", "") or "")[:512],
            body=str(out.get("body", "") or "") or None,
        )
    except Exception as ex:  # pragma: no cover — defensive
        print(f"[persona_responder] write_summary_memory {role!r} raised: {ex}")


def _latest_insight_for_role(graph, role: str) -> dict | None:
    rows = graph.query(
        "MATCH (i:Insight {role: $role}) "
        "RETURN i.id AS id, i.fingerprint AS fingerprint, "
        "       i.headline AS headline, i.body AS body, "
        "       i.kpis AS kpis, i.proposed_actions AS proposed_actions, "
        "       i.decided_at AS decided_at "
        "ORDER BY i.decided_at DESC LIMIT 1",
        {"role": role},
    )
    return rows[0] if rows else None


async def _insight_loop_tick(bus) -> None:
    """One tick of the insight cadence loop — emit a `domain.summary.requested`
    event per persona with a summary_policy block. Tests call this directly
    to skip the asyncio.sleep gating in `_insight_loop`.
    """
    for persona in personae_with_summary_policy():
        try:
            bus.emit(FleetEvent(
                type="domain.summary.requested",
                payload={"role": persona.role},
            ))
        except Exception as ex:  # pragma: no cover — defensive
            print(f"[persona_responder] insight tick emit failed for {persona.role}: {ex}")


async def _insight_loop(bus) -> None:
    """Periodic loop: every INSIGHT_REFRESH_SECONDS, emit a summary
    request per persona with a summary_policy. Cancelled by attach()'s
    teardown closure. Disabled entirely when INSIGHT_LOOP_ENABLED=0.
    """
    interval = float(os.environ.get("INSIGHT_REFRESH_SECONDS", "300"))
    if interval <= 0:
        return
    while True:
        try:
            await asyncio.sleep(interval)
            await _insight_loop_tick(bus)
        except asyncio.CancelledError:
            raise
        except Exception as ex:  # pragma: no cover — defensive
            print(f"[persona_responder] insight loop error: {ex}")
            await asyncio.sleep(1.0)


def attach(bus) -> Callable[[], None]:
    """Subscribe the persona responder to the EventBus.

    Loads (or reloads) PERSONA_DEFINITIONS from disk so SKILL.md edits
    take effect on the next FastAPI restart. Returns an unsubscribe
    callable for teardown. Wired from api/server/main.py lifespan.
    """
    global PERSONA_DEFINITIONS
    PERSONA_DEFINITIONS = _load_personae()
    auto = _auto_close_set()
    if _AUTO_CLOSE_ALL in auto:
        auto_label = "(ALL — every persona auto-closes)"
    elif not auto:
        auto_label = "(empty — every gate stays open)"
    else:
        auto_label = str(sorted(auto))
    print(
        f"[persona_responder] loaded {len(PERSONA_DEFINITIONS)} personae "
        f"({sorted(PERSONA_DEFINITIONS.keys())}); "
        f"AUTO_CLOSE={auto_label}"
    )

    loop = asyncio.get_event_loop()

    def _on_event(event: FleetEvent) -> None:
        if event.type == "workflow.hitl.requested":
            try:
                loop.create_task(_handle_hitl(event))
            except RuntimeError:
                pass
            return
        if event.type == "domain.summary.requested":
            try:
                loop.create_task(_handle_summary_request(event))
            except RuntimeError:
                pass
            return

    unsubscribe = bus.on_any(_on_event)

    # Drain workflows already parked at HITL gates from previous sessions.
    # Fire-and-forget — sweep_pending_hitl tolerates partial state and only
    # closes gates whose persona is in the auto-close set.
    try:
        loop.create_task(sweep_pending_hitl())
    except RuntimeError:
        pass

    # Periodic background sweep so any HITL gate that opens but isn't closed
    # by the event-driven path (e.g. cascade chains that take >5 hops, or
    # workflows whose orchestration was wiped between boots) gets resolved
    # within ~30s. Without this, the simulator visibly piles up at any
    # busy persona — most often the AP-clerk → controller → CFO chain at
    # Finance — and the constellation looks 'frozen'.
    sweep_interval = float(os.environ.get("PERSONA_SWEEP_INTERVAL_SECONDS", "30"))
    sweep_enabled = sweep_interval > 0 and os.environ.get(
        "PERSONA_SWEEP_LOOP_ENABLED", "1"
    ) not in ("0", "false", "False")

    async def _sweep_loop() -> None:
        while True:
            try:
                await asyncio.sleep(sweep_interval)
                await sweep_pending_hitl()
            except asyncio.CancelledError:
                raise
            except Exception as ex:  # pragma: no cover — defensive
                print(f"[persona_responder] periodic sweep failed: {ex}")

    sweep_task: asyncio.Task | None = None
    if sweep_enabled:
        try:
            sweep_task = loop.create_task(_sweep_loop())
            print(
                f"[persona_responder] periodic HITL sweep enabled "
                f"every {sweep_interval}s"
            )
        except RuntimeError:
            pass

    insight_enabled = os.environ.get("INSIGHT_LOOP_ENABLED", "1") not in ("0", "false", "False")
    insight_task: asyncio.Task | None = None
    if insight_enabled:
        try:
            insight_task = loop.create_task(_insight_loop(bus))
            interval = float(os.environ.get("INSIGHT_REFRESH_SECONDS", "300"))
            print(
                f"[persona_responder] insight cadence loop enabled "
                f"every {interval}s"
            )
        except RuntimeError:
            pass

    def _unsubscribe_with_sweep() -> None:
        unsubscribe()
        if sweep_task is not None and not sweep_task.done():
            sweep_task.cancel()
        if insight_task is not None and not insight_task.done():
            insight_task.cancel()

    return _unsubscribe_with_sweep


async def sweep_pending_hitl(*, max_concurrency: int = 8) -> dict[str, int]:
    """Resolve every workflow currently in ``awaiting_hitl`` whose persona
    is in the auto-close set.

    Reconstructs the FleetEvent the responder would have seen when the gate
    was first opened, then runs the same ``_handle_hitl`` path. Used to
    drain backlog accumulated before auto-close was enabled, and on every
    server start so a restart doesn't leave the queue stuck.
    """
    from api.server.state import app_state
    from api.server.services import pending_gates
    try:
        from api.shared.domains import DOMAINS  # type: ignore
        domains_by_type = DOMAINS if isinstance(DOMAINS, dict) else {}
    except Exception:
        domains_by_type = {}

    auto = _auto_close_set()
    if not auto:
        return {"considered": 0, "swept": 0, "skipped": 0}

    workflows = [w for w in app_state.store.list_workflows()
                 if w.status == "awaiting_hitl"]

    sem = asyncio.Semaphore(max_concurrency)
    counters = {"considered": len(workflows), "swept": 0, "skipped": 0}

    async def _sweep_one(w) -> None:
        async with sem:
            payload = w.payload or {}
            ctx = payload.get("hitl_context") or {}
            persona_role = (
                ctx.get("persona")
                or payload.get("persona")
                or None
            )
            if not persona_role:
                domain = domains_by_type.get(w.type)
                if domain is not None:
                    gates = getattr(domain, "hitl_gates", None) or []
                    for gate in gates:
                        if getattr(gate, "gate_phase", None) == w.current_phase:
                            persona_role = (getattr(gate, "persona", None)
                                            or getattr(gate, "persona_role", None))
                            break
                    if not persona_role and gates:
                        cand = (getattr(gates[0], "persona", None)
                                or getattr(gates[0], "persona_role", None))
                        persona_role = cand
            if not persona_role or not _role_auto_closes(persona_role, auto):
                counters["skipped"] += 1
                return
            instance_id = getattr(w, "orchestration_instance_id", None)
            if not instance_id:
                counters["skipped"] += 1
                return
            cache = pending_gates.get(w.id) or {}
            external_event = (
                ctx.get("external_event")
                or payload.get("external_event")
                or cache.get("external_event")
            )
            phase = w.current_phase or cache.get("phase")
            sweep_context = dict(ctx)
            if phase and "phase" not in sweep_context:
                sweep_context["phase"] = phase
            event = FleetEvent(
                type="workflow.hitl.requested",
                workflow_id=w.id,
                persona=persona_role,
                external_event=external_event,
                instance_id=instance_id,
                context=sweep_context,
                phase=phase,
            )
            try:
                await _handle_hitl(event)
                counters["swept"] += 1
            except Exception as ex:
                counters["skipped"] += 1
                print(f"[persona_responder] sweep failed for {w.id}: {ex}")

    await asyncio.gather(*[_sweep_one(w) for w in workflows])
    print(f"[persona_responder] sweep_pending_hitl: {counters}")
    return counters
