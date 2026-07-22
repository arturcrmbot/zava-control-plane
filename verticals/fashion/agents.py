from __future__ import annotations

from api.shared.agent_contracts import AgentRegistryEntry


_TOOLS = {
    "inventory-imbalance-analysis": "fashion_read_inventory",
    "inventory-rebalance-planner": "fashion_prepare_inventory_transfer",
    "promotion-readiness-assessor": "fashion_assess_promotion",
    "markdown-option-advisor": "fashion_prepare_markdown_recommendation",
    "supplier-recovery-planner": "fashion_prepare_supplier_recovery",
    "fulfilment-resolution-advisor": "fashion_prepare_fulfilment_resolution",
    "seller-exception-assessor": "fashion_prepare_seller_suppression",
    "returns-disposition-advisor": "fashion_prepare_return_disposition",
}

FASHION_AGENTS = {
    agent_id: AgentRegistryEntry(
        agent_id=agent_id,
        allowed_tools=(tool,),
        max_value_gbp=10_000.0 if agent_id == "inventory-rebalance-planner" else None,
        reversible_only=agent_id != "markdown-option-advisor",
        scope_function="shared",
        description=f"Fashion Retail agent for {agent_id.replace('-', ' ')}.",
    )
    for agent_id, tool in _TOOLS.items()
}

