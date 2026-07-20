from __future__ import annotations

from api.shared.authority_contracts import AuthorityRow


FASHION_AUTHORITY = {
    "inventory_allocation_manager": AuthorityRow(
        role="inventory_allocation_manager",
        spend_limit_gbp=10_000.0,
        approval_actions=("inventory_allocation_manager_decision",),
        delegate_to="merchandising_director",
    ),
    "merchandising_director": AuthorityRow(
        role="merchandising_director",
        spend_limit_gbp=1_000_000.0,
        approval_actions=("merchandising_director_decision",),
        delegate_to=None,
    ),
    "fulfilment_manager": AuthorityRow(
        role="fulfilment_manager",
        spend_limit_gbp=25_000.0,
        approval_actions=("fulfilment_manager_decision",),
        delegate_to="supply_chain_director",
    ),
    "supply_chain_director": AuthorityRow(
        role="supply_chain_director",
        spend_limit_gbp=1_000_000.0,
        approval_actions=("supply_chain_director_decision",),
        delegate_to=None,
    ),
    "marketplace_operations_director": AuthorityRow(
        role="marketplace_operations_director",
        spend_limit_gbp=500_000.0,
        approval_actions=("marketplace_operations_director_decision",),
        delegate_to=None,
    ),
    "returns_operations_manager": AuthorityRow(
        role="returns_operations_manager",
        spend_limit_gbp=50_000.0,
        approval_actions=("returns_operations_manager_decision",),
        delegate_to=None,
    ),
}

