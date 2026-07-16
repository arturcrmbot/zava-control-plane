from __future__ import annotations

from types import MappingProxyType

from api.shared.agent_contracts import AgentRegistryEntry


KERNEL_AGENTS = MappingProxyType(
    {
        "reflector.entity_reflector": AgentRegistryEntry(
            agent_id="reflector.entity_reflector",
            allowed_tools=(
                "entity.upsert",
                "entity.link",
                "decision.record",
            ),
            reversible_only=False,
            scope_function="shared",
            description="Projects active workflow evidence into the entity graph.",
        ),
    }
)

KNOWN_CAPABILITIES = frozenset(
    {"blueprint", "compose", "knowledge", "memory", "world"}
)
KNOWN_LENSES = frozenset(
    {
        "agency-operations",
        "telco-network",
        "customer-impact",
        "order",
        "control",
    }
)
