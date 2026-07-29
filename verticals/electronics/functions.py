from __future__ import annotations

from api.shared.function_contracts import Function, PersonaTree


ELECTRONICS_FUNCTIONS: dict[str, Function] = {
    "merchandising-planning": Function(
        name="merchandising-planning",
        display="Merchandising & Planning",
        operator_surface="merchandising-planning",
        owns_domains=(
            "inventory-rebalancing",
            "demand-spike-response",
            "promotion-readiness",
            "markdown-governance",
        ),
        ambient_agents=("inventory-imbalance-analysis",),
        kpis=(
            "full-price-sell-through",
            "lost-sales",
            "weeks-of-supply",
            "margin-exposure",
        ),
        persona_hierarchy=PersonaTree(
            role="merchandising_director",
            manages=(PersonaTree(role="inventory_allocation_manager"),),
        ),
    ),
    "supply-chain-fulfilment": Function(
        name="supply-chain-fulfilment",
        display="Supply Chain & Fulfilment",
        operator_surface="supply-chain-fulfilment",
        owns_domains=(
            "supplier-delay-recovery",
            "fulfilment-exception-resolution",
        ),
        ambient_agents=(),
        kpis=("on-time-availability", "transfer-lead-time", "cost-to-serve"),
        persona_hierarchy=PersonaTree(
            role="supply_chain_director",
            manages=(PersonaTree(role="fulfilment_manager"),),
        ),
    ),
    "marketplace-operations": Function(
        name="marketplace-operations",
        display="Marketplace Operations",
        operator_surface="marketplace-operations",
        owns_domains=("marketplace-seller-exception",),
        ambient_agents=(),
        kpis=("seller-fulfilment-rate", "stock-accuracy", "partner-response-time"),
        persona_hierarchy=PersonaTree(role="marketplace_operations_director"),
    ),
    "customer-returns": Function(
        name="customer-returns",
        display="Customer Returns",
        operator_surface="customer-returns",
        owns_domains=("returns-disposition",),
        ambient_agents=(),
        kpis=("repair-cycle-time", "recovery-value", "waste-avoided"),
        persona_hierarchy=PersonaTree(role="returns_operations_manager"),
    ),
}

