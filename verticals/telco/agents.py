"""verticals/telco/agents.py — Telco vertical machine-agent registry.

Canonical Telco ``AgentRegistryEntry`` declarations. This module owns
Telco's agent identities exclusively — Agency's 18 business agent ids live
in ``verticals/agency/agents.py`` and are never imported here. The single
kernel-identity actor (``reflector.entity_reflector``) is declared once in
the ``api.shared.agents`` compatibility adapter, not in either pack.

Consumers (via the ``api.shared.agents`` compatibility adapter):
- api.server.services.governance.kernel — capability/value/reversibility gate
"""
from __future__ import annotations

from api.shared.agent_contracts import AgentRegistryEntry


TELCO_AGENTS: dict[str, AgentRegistryEntry] = {
    # ---------------- Telco customer care ----------------
    "proactive-customer-care-entitlement": AgentRegistryEntry(
        agent_id="proactive-customer-care-entitlement",
        allowed_tools=("customer_care_policy_lookup",),
        max_value_gbp=None,
        reversible_only=True,
        scope_function="shared",
        description=(
            "Telco care entitlement agent — reads governed policy for each "
            "impacted commercial account."
        ),
    ),
    "proactive-customer-care-execution": AgentRegistryEntry(
        agent_id="proactive-customer-care-execution",
        allowed_tools=(
            "customer_care_prepare_notification",
            "customer_care_prepare_credit",
        ),
        max_value_gbp=None,
        reversible_only=True,
        scope_function="shared",
        description=(
            "Telco care execution agent — prepares notification and credit "
            "actions for authoritative world validation."
        ),
    ),
    "outage-risk-planning": AgentRegistryEntry(
        agent_id="outage-risk-planning",
        scope_function="shared",
        description="Plans proportionate resource pre-staging from weather risk.",
    ),
    "site-failure-diagnosis": AgentRegistryEntry(
        agent_id="site-failure-diagnosis",
        scope_function="shared",
        description="Diagnoses imminent network asset failure from telemetry.",
    ),
    "field-resource-matching": AgentRegistryEntry(
        agent_id="field-resource-matching",
        scope_function="shared",
        description="Matches ready work orders to technicians and spare stock.",
    ),
    "capacity-action-planner": AgentRegistryEntry(
        agent_id="capacity-action-planner",
        scope_function="shared",
        description="Selects proportionate actions for congested sites.",
    ),
    "ticket-root-cause-correlation": AgentRegistryEntry(
        agent_id="ticket-root-cause-correlation",
        scope_function="shared",
        description="Correlates service tickets with network and order events.",
    ),
    "churn-driver-analysis": AgentRegistryEntry(
        agent_id="churn-driver-analysis",
        scope_function="shared",
        description="Explains churn risk from service experience evidence.",
    ),
    "retention-offer-selection": AgentRegistryEntry(
        agent_id="retention-offer-selection",
        scope_function="shared",
        description="Selects fair retention remedies for evidenced service failures.",
    ),
    "evidence-correlator": AgentRegistryEntry(
        agent_id="evidence-correlator",
        allowed_tools=(
            "network_query_state",
            "network_query_impact",
            "operations_query_case",
            "commercial_query_customer",
            "commercial_query_order_revenue",
            "twin_query_external_signal",
        ),
        scope_function="shared",
        description="Correlates supplied Telco evidence into causal groups.",
    ),
    "risk-impact-assessor": AgentRegistryEntry(
        agent_id="risk-impact-assessor",
        allowed_tools=(
            "network_query_impact",
            "commercial_query_customer",
            "twin_forecast",
        ),
        scope_function="shared",
        description="Assesses operational and commercial impact.",
    ),
    "next-best-action-planner": AgentRegistryEntry(
        agent_id="next-best-action-planner",
        allowed_tools=(
            "network_validate_action",
            "operations_search_runbook",
            "commercial_evaluate_entitlement",
            "twin_compare_scenarios",
        ),
        scope_function="shared",
        description="Ranks declared actions by effect and risk.",
    ),
    "resource-matcher": AgentRegistryEntry(
        agent_id="resource-matcher",
        allowed_tools=(
            "operations_match_resources",
            "network_query_state",
            "commercial_query_order_revenue",
        ),
        scope_function="shared",
        description="Matches supplied resources to process constraints.",
    ),
    "policy-entitlement-evaluator": AgentRegistryEntry(
        agent_id="policy-entitlement-evaluator",
        allowed_tools=(
            "commercial_evaluate_entitlement",
            "commercial_query_customer",
            "operations_query_case",
        ),
        scope_function="shared",
        description="Evaluates policy, entitlement and approval evidence.",
    ),
    "exception-resolution-advisor": AgentRegistryEntry(
        agent_id="exception-resolution-advisor",
        allowed_tools=(
            "operations_query_case",
            "operations_search_runbook",
            "network_query_impact",
            "commercial_query_order_revenue",
        ),
        scope_function="shared",
        description="Proposes bounded resolution for evidenced exceptions.",
    ),
    "communication-drafter": AgentRegistryEntry(
        agent_id="communication-drafter",
        allowed_tools=(
            "commercial_query_customer",
            "operations_query_case",
        ),
        scope_function="shared",
        description="Drafts evidence-grounded customer and operator communication.",
    ),
    "scenario-comparator": AgentRegistryEntry(
        agent_id="scenario-comparator",
        allowed_tools=(
            "twin_forecast",
            "twin_compare_scenarios",
            "network_query_state",
            "commercial_query_order_revenue",
        ),
        scope_function="shared",
        description="Compares supplied forecasts and what-if scenarios.",
    ),
}
