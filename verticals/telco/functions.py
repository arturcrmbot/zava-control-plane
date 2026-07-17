"""verticals/telco/functions.py — Telco organisational function registry.

Canonical Telco ``Function`` declarations. Agency's functions live in
``verticals/agency/functions.py`` and are never imported here.
"""
from __future__ import annotations

from api.shared.function_contracts import Function, PersonaTree


TELCO_FUNCTIONS: dict[str, Function] = {
    "network-operations": Function(
        name="network-operations",
        display="Network Operations",
        operator_surface="network-operations",
        owns_domains=(
            "network-incident",
            "order-to-activate",
            "outage-risk-management",
            "predictive-site-maintenance",
            "field-repair-dispatch",
            "capacity-optimization",
        ),
        ambient_agents=(),
        kpis=(
            "availability-pct",
            "mttr",
            "activation-time",
            "prevented-outages",
            "work-order-completion",
            "capacity-headroom",
        ),
        persona_hierarchy=PersonaTree(
            role="network_ops_director",
            manages=(PersonaTree(role="delivery_lead"),),
        ),
    ),
    "customer-success": Function(
        name="customer-success",
        display="Customer Success",
        operator_surface="customer-success",
        owns_domains=(
            "proactive-customer-care",
            "service-ticket-resolution",
            "retention-orchestration",
        ),
        ambient_agents=(),
        kpis=(
            "nps",
            "proactive-resolution-pct",
            "credit-cost",
            "ticket-resolution-time",
            "retention-acceptance",
        ),
        persona_hierarchy=PersonaTree(
            role="cs_director",
            manages=(
                PersonaTree(
                    role="cs_account_director",
                    manages=(
                        PersonaTree(
                            role="cs_manager",
                            manages=(PersonaTree(role="cs_specialist"),),
                        ),
                    ),
                ),
            ),
        ),
    ),
}
