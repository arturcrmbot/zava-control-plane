from __future__ import annotations

from api.shared.agent_contracts import AgentRegistryEntry


_TOOLS = {
    "inventory-imbalance-analysis": "electronics_read_inventory",
    "inventory-rebalance-planner": "electronics_prepare_inventory_transfer",
    "promotion-readiness-assessor": "electronics_assess_promotion",
    "markdown-option-advisor": "electronics_prepare_markdown_recommendation",
    "supplier-recovery-planner": "electronics_prepare_supplier_recovery",
    "fulfilment-resolution-advisor": "electronics_prepare_fulfilment_resolution",
    "seller-exception-assessor": "electronics_prepare_seller_suppression",
    "returns-disposition-advisor": "electronics_prepare_return_disposition",
}

ELECTRONICS_AGENTS = {
    agent_id: AgentRegistryEntry(
        agent_id=agent_id,
        allowed_tools=(tool,),
        max_value_gbp=10_000.0 if agent_id == "inventory-rebalance-planner" else None,
        reversible_only=agent_id != "markdown-option-advisor",
        scope_function="shared",
        description=f"Electronics Retail agent for {agent_id.replace('-', ' ')}.",
    )
    for agent_id, tool in _TOOLS.items()
}

