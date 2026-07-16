"""api/shared/agents.py — compatibility adapter over the active vertical pack.

This module is a thin adapter, not a registry. It:

- re-exports the ``AgentRegistryEntry`` contract type from
  :mod:`api.shared.agent_contracts`
- exposes ``AGENTS`` as the *active pack's* business-agent mapping plus the
  fixed kernel-identity actor set — sourced from
  ``active_runtime().pack.agents`` merged with :data:`_KERNEL_AGENTS`
- exposes the existing lookup helpers (``get``, ``by_function``,
  ``all_agent_ids``)

Canonical business-agent declarations live in ``verticals/agency/agents.py``
and ``verticals/telco/agents.py``. This module contains no business-agent
declarations, no all-vertical registry, and does not parse the environment
itself — vertical selection happens once, while ``active_runtime()`` builds
the selected pack.

Kernel identity
----------------
``reflector.entity_reflector`` is substrate machinery, not a business
agent: it is the actor id the entity-graph reflector uses to dispatch
projection ops (Person / Organisation upserts + Decision writes), and
``api.server.services.governance.kernel._registry_gate`` denies any actor
that ``AGENTS.get()`` can't resolve. It must be present regardless of
which vertical is active, so it's declared once here — in the adapter —
rather than duplicated (or conditionally filtered) inside either pack's
business-agent module. This keeps kernel identity handling separate from,
and never smuggled into, either pack's business-agent declarations.

Consumers:
- api.server.services.governance.kernel — capability/value/reversibility gate
- api.server.services.dream_pass        — actor lookups for lesson writes
"""
from __future__ import annotations

from api.shared.agent_contracts import AgentRegistryEntry
from api.shared.vertical_loader import active_runtime


__all__ = [
    "AgentRegistryEntry",
    "AGENTS",
    "get",
    "by_function",
    "all_agent_ids",
]


# --------------------------------------------------------------------------
# Kernel-identity actors. Always present, regardless of active vertical —
# these are NOT business agents and must never be declared inside
# verticals/agency/agents.py or verticals/telco/agents.py.
# --------------------------------------------------------------------------

_KERNEL_AGENTS: dict[str, AgentRegistryEntry] = {
    "reflector.entity_reflector": AgentRegistryEntry(
        agent_id="reflector.entity_reflector",
        allowed_tools=("entity.write",),
        max_value_gbp=None,
        reversible_only=False,
        scope_function="shared",
        description=(
            "System actor for EntityReflector — turns FleetEvents into "
            "EntityGraph upserts via the per-domain projection registry."
        ),
    ),
}

AGENTS: dict[str, AgentRegistryEntry] = {
    **active_runtime().pack.agents,
    **_KERNEL_AGENTS,
}


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def get(agent_id: str) -> AgentRegistryEntry | None:
    """Return the registry entry for ``agent_id``, or ``None``."""
    return AGENTS.get(agent_id)


def by_function(scope: str) -> list[AgentRegistryEntry]:
    """All registered agents scoped to ``scope``."""
    return [a for a in AGENTS.values() if a.scope_function == scope]


def all_agent_ids() -> tuple[str, ...]:
    """Sorted tuple of every registered agent_id."""
    return tuple(sorted(AGENTS.keys()))
