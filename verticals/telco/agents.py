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
}
