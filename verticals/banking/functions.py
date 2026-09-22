"""Zava Bank organisational functions.

Seven functions, mirroring the shape of a universal bank. Each owns a
disjoint slice of the domain registry -- ``validate_pack`` requires the set
of owned workflow types to exactly equal the declared domains, with no
duplicate owner.

Functions are the backbone the visual surfaces hang off: one planet per
function in the cosmic lens, one operator surface per function in the
control plane.
"""
from __future__ import annotations

from api.shared.function_contracts import Function, PersonaTree
from verticals.banking.fraud_constants import FRAUD_WORKFLOW_TYPE
from verticals.banking.support_constants import (
    MERCHANT_WORKFLOW_TYPE,
    MULE_WORKFLOW_TYPE,
)


BANKING_FUNCTIONS: dict[str, Function] = {
    "retail-banking": Function(
        name="retail-banking",
        display="Retail and Business Banking",
        operator_surface="retail-banking",
        owns_domains=(
            FRAUD_WORKFLOW_TYPE,
            "card-dispute-chargeback",
            "collections-and-forbearance",
            "sme-lending-decision",
        ),
        ambient_agents=(),
        kpis=(
            "claims-decided-within-window",
            "customer-funds-restored",
            "vulnerability-protections-upheld",
        ),
        persona_hierarchy=PersonaTree(
            role="fraud_decision_manager",
            manages=(PersonaTree(role="vulnerable_customer_specialist"),),
        ),
    ),
    "payments": Function(
        name="payments",
        display="Payments and Merchant Services",
        operator_surface="payments",
        owns_domains=(
            MERCHANT_WORKFLOW_TYPE,
            "scheme-dispute-resolution",
            "settlement-exception",
        ),
        ambient_agents=(),
        kpis=(
            "rail-availability",
            "settlement-exceptions-cleared",
            "merchant-risk-decisions",
        ),
        persona_hierarchy=PersonaTree(role="payments_operations_lead"),
    ),
    "financial-crime": Function(
        name="financial-crime",
        display="Financial Crime and Compliance",
        operator_surface="financial-crime",
        owns_domains=(
            MULE_WORKFLOW_TYPE,
            "sanctions-alert-triage",
            "suspicious-activity-report",
        ),
        ambient_agents=(),
        kpis=(
            "beneficiary-accounts-restrained",
            "investigations-substantiated",
            "funds-recovered",
        ),
        persona_hierarchy=PersonaTree(role="financial_crime_lead"),
    ),
    "credit-risk": Function(
        name="credit-risk",
        display="Credit and Counterparty Risk",
        operator_surface="credit-risk",
        owns_domains=(
            "counterparty-limit-excess",
            "credit-watchlist-review",
        ),
        ambient_agents=(),
        kpis=(
            "limit-excesses-cleared",
            "time-to-remediate",
            "exposure-within-appetite",
        ),
        persona_hierarchy=PersonaTree(
            role="senior_credit_officer",
            manages=(PersonaTree(role="credit_risk_officer"),),
        ),
    ),
    "markets": Function(
        name="markets",
        display="Markets and Post-Trade",
        operator_surface="markets",
        owns_domains=(
            "collateral-dispute-resolution",
            "post-trade-settlement-fail",
        ),
        ambient_agents=(),
        kpis=(
            "collateral-disputes-resolved",
            "settlement-fail-rate",
        ),
        persona_hierarchy=PersonaTree(role="senior_credit_officer"),
    ),
    "client-governance": Function(
        name="client-governance",
        display="Client Risk and Governance",
        operator_surface="client-governance",
        owns_domains=(
            "client-risk-review",
            "relationship-exit-decision",
        ),
        ambient_agents=(),
        kpis=(
            "cross-function-reviews",
            "exit-consequences-modelled",
        ),
        persona_hierarchy=PersonaTree(role="financial_crime_lead"),
    ),
    "wealth": Function(
        name="wealth",
        display="Private Bank and Wealth",
        operator_surface="wealth",
        owns_domains=(
            "portfolio-suitability-review",
            "kyc-periodic-refresh",
        ),
        ambient_agents=(),
        kpis=(
            "suitability-reviews-current",
            "kyc-refresh-backlog",
        ),
        persona_hierarchy=PersonaTree(role="payments_operations_lead"),
    ),
}
