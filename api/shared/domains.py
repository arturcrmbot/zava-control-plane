"""api/shared/domains.py — compatibility adapter over the active vertical pack.

This module is a thin adapter, not a registry. It:

- re-exports the ``Domain``/``Phase``/``HitlGate``/``RegionOverlay``/
  ``WakeHint`` contract types from :mod:`api.shared.domain_contracts`
- exposes ``DOMAINS`` as the *active pack's* domain mapping only —
  sourced from ``active_runtime().pack.domains``
- exposes the existing lookup helpers (``get``, ``by_prefix``,
  ``resolve_external_event``, ``all_wake_hints``, ``all_personae``,
  ``live_domains``)

Canonical domain declarations live in ``verticals/agency/domains.py`` and
``verticals/telco/domains.py``. This module contains no business-domain
declarations, no all-vertical registry, and does not parse the environment
itself — vertical selection and function back-ref wiring both happen once,
while ``active_runtime()`` builds the selected pack.

Consumers:
- api.server.services.simulator_orchestrator — spawner dispatch
- api.server.services.blueprint_inventory   — visual mind-map composition
- api.server.routes.workflows               — workflow_id-prefix → workflow_type
- api.server.routes.exceptions              — current_phase → external_event fallback
- api.server.services.triage                — wake-event allow-list extension
- api.server.services.fleet_manager_service — domain catalogue inside FM skill
"""
from __future__ import annotations

from api.shared.domain_contracts import (
    Domain,
    HitlGate,
    Phase,
    PhaseKind,
    RegionOverlay,
    WakeHint,
)
from api.shared.vertical_loader import active_runtime

__all__ = [
    "Domain",
    "HitlGate",
    "Phase",
    "PhaseKind",
    "RegionOverlay",
    "WakeHint",
    "DOMAINS",
    "get",
    "by_prefix",
    "resolve_external_event",
    "all_wake_hints",
    "all_personae",
    "live_domains",
]

DOMAINS: dict[str, Domain] = active_runtime().pack.domains


# --------------------------------------------------------------------------
# Lookup helpers — keep call sites readable.
# --------------------------------------------------------------------------


def get(workflow_type: str) -> Domain | None:
    """Return the registered Domain for a workflow_type, or None."""
    return DOMAINS.get(workflow_type)


def by_prefix(workflow_id: str) -> Domain | None:
    """Resolve a workflow_id (e.g. 'VKY-0007') to its Domain via prefix.

    Used by api/server/routes/workflows.py to synthesise minimal records
    when a fleet workflow isn't in the store. (Phase 2 of the plan
    upserts every workflow into the store, so this falls back to a no-op
    in steady state.)
    """
    prefix = workflow_id.split("-", 1)[0] if "-" in workflow_id else workflow_id
    for d in DOMAINS.values():
        if d.workflow_id_prefix == prefix:
            return d
    return None


def resolve_external_event(workflow_type: str, current_phase: str) -> str | None:
    """Map (workflow_type, current_phase) to the Durable external event name.

    Cold-cache fallback for the resolve route when the in-memory
    pending-gate cache has been cleared (e.g. FastAPI restart between
    suspend and operator click). Matches HitlGate.gate_phase exactly,
    case-insensitive, with underscore/space normalisation so
    "Manager Approval" and "manager_approval" both resolve.
    """
    domain = DOMAINS.get(workflow_type)
    if not domain:
        return None
    norm = current_phase.lower().replace(" ", "_")
    for gate in domain.hitl_gates:
        if gate.gate_phase.lower().replace(" ", "_") == norm:
            return gate.external_event
    return None


def all_wake_hints() -> set[str]:
    """Union of every domain's wake-hint event names.

    Triage layer (api/server/services/triage.py) uses this to extend
    `WAKE_TYPES` so per-domain anticipatory events wake the FM without
    each domain needing to edit api/shared/events.py.
    """
    out: set[str] = set()
    for d in DOMAINS.values():
        for wh in d.wake_hints:
            out.add(wh.event)
    return out


def all_personae() -> set[str]:
    """Set of every persona role referenced by any HITL gate.

    Used by the registry validation test to assert every persona has a
    SKILL.md under api/server/personae/.
    """
    out: set[str] = set()
    for d in DOMAINS.values():
        for g in d.hitl_gates:
            out.add(g.persona)
    return out


def live_domains() -> list[Domain]:
    """Return the runtime-spawnable domains (excludes ``stub=True`` entries).

    Use this in any code path that iterates over what the substrate
    actually runs (simulator, FM skill text, blueprint inventory, etc.).
    Reading ``DOMAINS.values()`` directly is fine for documentation /
    org-clone surfaces that need to see the full registry including
    placeholders.
    """
    return [d for d in DOMAINS.values() if not d.stub]
