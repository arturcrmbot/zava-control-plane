from __future__ import annotations

from api.shared.authority_contracts import AuthorityRow


FASHION_AUTHORITY = {
    "merchandising_director": AuthorityRow(
        role="merchandising_director",
        spend_limit_gbp=250_000.0,
        approval_actions=(
            "merchandising_director_decision",
            "inventory.transfer.exception",
            "markdown.recommend",
        ),
        delegate_to=None,
    ),
    "inventory_allocation_manager": AuthorityRow(
        role="inventory_allocation_manager",
        spend_limit_gbp=10_000.0,
        approval_actions=("inventory_allocation_manager_decision",),
        delegate_to="merchandising_director",
    ),
    "supply_chain_director": AuthorityRow(
        role="supply_chain_director",
        spend_limit_gbp=250_000.0,
        approval_actions=("supply_chain_director_decision",),
        delegate_to=None,
    ),
    "fulfilment_manager": AuthorityRow(
        role="fulfilment_manager",
        spend_limit_gbp=25_000.0,
        approval_actions=("fulfilment_manager_decision",),
        delegate_to="supply_chain_director",
    ),
    "marketplace_operations_director": AuthorityRow(
        role="marketplace_operations_director",
        spend_limit_gbp=100_000.0,
        approval_actions=("marketplace_operations_director_decision",),
        delegate_to=None,
    ),
    "returns_operations_manager": AuthorityRow(
        role="returns_operations_manager",
        spend_limit_gbp=25_000.0,
        approval_actions=("returns_operations_manager_decision",),
        delegate_to=None,
    ),
}

