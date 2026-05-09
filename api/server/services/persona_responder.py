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
Default behaviour: **every gate stays open**. A persona only closes a
gate if its role is in the ``PERSONA_AUTO_CLOSE`` env var (CSV).
Production-honest default: nothing closes itself. Demo profiles set
the allow-list explicitly. See ``scripts/profile-friday.sh`` and
``scripts/profile-autonomous.sh``.

Hand-built domains (expense / hiring) stamp ``persona`` /
``external_event`` / ``context`` on their suspended payloads (per the
substrate-fix v2). The responder still honours the allow-list, so
production / demo days with real humans keep human-in-the-loop unless
specifically opted in.
"""
from __future__ import annotations

import asyncio
import os
import textwrap
from dataclasses import dataclass
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


# Populated at attach() time.
PERSONA_DEFINITIONS: dict[str, PersonaDefinition] = {}


def _auto_close_set() -> set[str]:
    """Read PERSONA_AUTO_CLOSE env var as a set of persona roles. Default empty
    — every gate stays open unless explicitly opted in."""
    raw = os.environ.get("PERSONA_AUTO_CLOSE", "").strip()
    if not raw:
        return set()
    return {part.strip() for part in raw.split(",") if part.strip()}


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


_DECISION_BUILTINS: dict[str, Any] = {
    "isinstance": isinstance, "len": len,
    "str": str, "int": int, "float": float, "bool": bool,
    "list": list, "dict": dict, "set": set, "tuple": tuple,
    "min": min, "max": max, "abs": abs, "round": round,
    "any": any, "all": all, "sum": sum,
    "True": True, "False": False, "None": None,
    "authority_check": _sandbox_authority_check,
    "query_precedents": _sandbox_query_precedents,
}


def _compile_decision_policy(role: str, source: str) -> PersonaHandler:
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
    try:
        code = compile(cleaned, f"<persona:{role}:decision_policy>", "exec")
    except SyntaxError as ex:
        raise ValueError(f"persona '{role}' decision_policy fails to compile: {ex}") from ex

    def decide(context: dict[str, Any]) -> dict[str, Any]:
        ns: dict[str, Any] = {"context": context, "decision": None, "reason": None}
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
            if not external_event or not isinstance(decision_src, str):
                print(f"[persona_responder] {skill_path}: missing external_event or "
                      f"decision_policy in frontmatter; skipping")
                continue
            decide = _compile_decision_policy(str(role), decision_src)
            out[str(role)] = PersonaDefinition(
                role=str(role),
                description=str(description),
                workflow_label=str(workflow_label),
                external_event=str(external_event),
                decide=decide,
                skill_path=skill_path,
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


async def _handle_hitl(event: FleetEvent) -> None:
    """Apply the matching persona's decision policy and raise the resolving event.

    Skipped silently for any persona NOT in PERSONA_AUTO_CLOSE, so real
    humans can drive the gate via the existing portal/UI flows.
    """
    data = event.model_dump()
    persona_role = data.get("persona")
    external_event_override = data.get("external_event")
    instance_id = data.get("instance_id")
    context = data.get("context") or {}

    # No persona contract on this gate (UI-driven legacy path) → nothing to do.
    if not (persona_role and instance_id):
        return

    auto_close = _auto_close_set()
    if persona_role not in auto_close:
        # Real human is supposed to drive this gate. Stay out of their way.
        return

    persona = PERSONA_DEFINITIONS.get(persona_role)
    if persona is None:
        print(f"[persona_responder] AUTO_CLOSE includes {persona_role!r} but no "
              f"SKILL.md defines that persona; gate stays open")
        return

    try:
        decision_payload = persona.decide(context)
    except Exception as ex:
        print(f"[persona_responder] persona {persona_role!r} crashed: {ex}")
        return

    event_name = external_event_override or persona.external_event
    decision_str = decision_payload.get("decision")

    # Phase 6 of feature-fleet-domain-substrate-1: when a persona returns
    # `escalate`, do NOT raise the orchestration event. The Durable gate
    # stays parked; we publish a richer FleetEvent so the FM picks it up
    # via triage.should_wake (workflow.hitl.escalated is in WAKE_TYPES).
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
        return

    print(
        f"[persona_responder] {persona_role} decided "
        f"{decision_str!r} for {data.get('workflow_id')} "
        f"({data.get('reason')}); raising {event_name!r}"
    )

    try:
        await raise_orchestration_event(instance_id, event_name, decision_payload)
    except Exception as ex:
        print(
            f"[persona_responder] failed to raise {event_name!r} on "
            f"instance {instance_id}: {ex}"
        )


def attach(bus) -> Callable[[], None]:
    """Subscribe the persona responder to the EventBus.

    Loads (or reloads) PERSONA_DEFINITIONS from disk so SKILL.md edits
    take effect on the next FastAPI restart. Returns an unsubscribe
    callable for teardown. Wired from api/server/main.py lifespan.
    """
    global PERSONA_DEFINITIONS
    PERSONA_DEFINITIONS = _load_personae()
    auto = _auto_close_set()
    print(
        f"[persona_responder] loaded {len(PERSONA_DEFINITIONS)} personae "
        f"({sorted(PERSONA_DEFINITIONS.keys())}); "
        f"AUTO_CLOSE={sorted(auto) if auto else '(empty — every gate stays open)'}"
    )

    loop = asyncio.get_event_loop()

    def _on_event(event: FleetEvent) -> None:
        if event.type != "workflow.hitl.requested":
            return
        try:
            loop.create_task(_handle_hitl(event))
        except RuntimeError:
            pass

    return bus.on_any(_on_event)
