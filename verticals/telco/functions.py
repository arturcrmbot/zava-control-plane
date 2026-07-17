"""verticals/telco/functions.py — Telco organisational function registry.

Canonical Telco ``Function`` declarations. Agency's functions live in
``verticals/agency/functions.py`` and are never imported here.
"""
from __future__ import annotations

from api.shared.function_contracts import Function, PersonaTree
from verticals.telco.process_profiles import STANDARD_PROCESS_PROFILES


def _standard_domains(function_name: str) -> tuple[str, ...]:
    return tuple(
        profile.workflow_type
        for profile in STANDARD_PROCESS_PROFILES.values()
        if profile.function == function_name
    )


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
        ) + _standard_domains("network-operations"),
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
    "service-operations": Function(
        name="service-operations",
        display="Service Operations",
        operator_surface="service-operations",
        owns_domains=_standard_domains("service-operations"),
        ambient_agents=(),
        kpis=(
            "right-first-time",
            "case-resolution-time",
            "resource-utilization",
        ),
        persona_hierarchy=PersonaTree(role="service_ops_manager"),
    ),
    "customer-success": Function(
        name="customer-success",
        display="Customer Success",
        operator_surface="customer-success",
        owns_domains=(
            "proactive-customer-care",
            "service-ticket-resolution",
            "retention-orchestration",
        ) + _standard_domains("customer-success"),
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
    "commercial-risk": Function(
        name="commercial-risk",
        display="Commercial Risk",
        operator_surface="commercial-risk",
        owns_domains=_standard_domains("commercial-risk"),
        ambient_agents=(),
        kpis=(
            "revenue-protected",
            "risk-case-resolution",
            "fair-treatment-compliance",
        ),
        persona_hierarchy=PersonaTree(role="commercial_risk_director"),
    ),
}
