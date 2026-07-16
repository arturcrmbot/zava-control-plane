from __future__ import annotations

from types import MappingProxyType

from api.shared.all_agents import AgentRegistryEntry, ScopeFunction
from api.shared.all_agents import AGENTS as ALL_AGENTS
from api.shared.vertical_loader import active_runtime


AGENTS = MappingProxyType(
    {
        "reflector.entity_reflector": ALL_AGENTS["reflector.entity_reflector"],
        **active_runtime().pack.agents,
    }
)


def get(agent_id: str) -> AgentRegistryEntry | None:
    return AGENTS.get(agent_id)


def by_function(scope: ScopeFunction) -> list[AgentRegistryEntry]:
    return [
        agent
        for agent in AGENTS.values()
        if agent.scope_function == scope
    ]


def all_agent_ids() -> tuple[str, ...]:
    return tuple(sorted(AGENTS))
