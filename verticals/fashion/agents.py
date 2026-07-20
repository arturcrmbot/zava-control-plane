from __future__ import annotations

from api.shared.agent_contracts import AgentRegistryEntry


FASHION_AGENTS = {
    "inventory-imbalance-analysis": AgentRegistryEntry(
        agent_id="inventory-imbalance-analysis",
        allowed_tools=("fashion_query_demand", "fashion_query_inventory"),
        max_value_gbp=10_000.0,
        scope_function="shared",
        description="Explains demand, availability, ownership, and stock imbalance.",
    ),
    "inventory-rebalance-planner": AgentRegistryEntry(
        agent_id="inventory-rebalance-planner",
        allowed_tools=(
            "fashion_query_inventory",
            "fashion_query_policies",
            "fashion_prepare_command",
        ),
        max_value_gbp=10_000.0,
        scope_function="shared",
        description="Ranks bounded stock actions without mutating inventory.",
    ),
    "promotion-readiness-assessor": AgentRegistryEntry(
        agent_id="promotion-readiness-assessor",
        allowed_tools=(
            "fashion_query_demand",
            "fashion_query_inventory",
            "fashion_query_policies",
        ),
        scope_function="shared",
        description="Assesses stock, content, and channel promotion readiness.",
    ),
    "markdown-option-advisor": AgentRegistryEntry(
        agent_id="markdown-option-advisor",
        allowed_tools=(
            "fashion_query_demand",
            "fashion_query_inventory",
            "fashion_query_policies",
        ),
        reversible_only=True,
        scope_function="shared",
        description="Proposes reviewed markdown options without changing price.",
    ),
    "supplier-recovery-planner": AgentRegistryEntry(
        agent_id="supplier-recovery-planner",
        allowed_tools=(
            "fashion_query_inventory",
            "fashion_query_partners",
            "fashion_query_policies",
        ),
        scope_function="shared",
        description="Ranks substitute, split, expedite, and replan actions.",
    ),
    "fulfilment-resolution-advisor": AgentRegistryEntry(
        agent_id="fulfilment-resolution-advisor",
        allowed_tools=(
            "fashion_query_inventory",
            "fashion_query_orders",
            "fashion_query_policies",
        ),
        scope_function="shared",
        description="Plans reroute, split, or explicit cancellation outcomes.",
    ),
    "seller-exception-assessor": AgentRegistryEntry(
        agent_id="seller-exception-assessor",
        allowed_tools=(
            "fashion_query_partners",
            "fashion_query_orders",
            "fashion_query_policies",
        ),
        scope_function="shared",
        description="Assesses seller correction, suppression, and escalation.",
    ),
    "returns-disposition-advisor": AgentRegistryEntry(
        agent_id="returns-disposition-advisor",
        allowed_tools=(
            "fashion_query_returns",
            "fashion_query_inventory",
            "fashion_query_policies",
        ),
        scope_function="shared",
        description="Ranks restock, refurbish, vendor, recycle, and reject paths.",
    ),
}

