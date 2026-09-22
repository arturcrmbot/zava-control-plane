"""Zava Bank personae.

``scope_function`` is a closed vocabulary on ``api.shared.persona_contracts``
(finance | hr | it | procurement | legal | legal_privacy | commercial |
candidate), so banking roles map onto it rather than inventing new values.

Every authority band here is a synthetic demo assumption. None of them
describes a real institution's delegation.
"""
from __future__ import annotations

from api.shared.persona_contracts import Persona
from verticals.banking.fraud_constants import (
    FRAUD_HITL_EVENT,
    FRAUD_MANAGER_LIMIT_GBP,
)


BANKING_PERSONAS: dict[str, Persona] = {
    "fraud_decision_manager": Persona(
        role="fraud_decision_manager",
        archetype="approver",
        scope_function="finance",
        workflow_label="Fraud Decision Manager",
        external_event_default=FRAUD_HITL_EVENT,
        default_authority_band=(
            f"synthetic-up-to-GBP-{int(FRAUD_MANAGER_LIMIT_GBP)}"
        ),
        uses_authority_mcp=True,
        description=(
            "Owns the synthetic reimbursement decision on an authorised "
            "push payment fraud claim. Approves only within a delegated "
            "authority that sits deliberately below the synthetic "
            "reimbursement cap, so a large capped claim escalates rather "
            "than being signed off here. Never refuses a customer carrying "
            "a vulnerability marker."
        ),
        display_color="#2563eb",
    ),
    "financial_crime_lead": Persona(
        role="financial_crime_lead",
        archetype="approver",
        scope_function="legal",
        workflow_label="Financial Crime Lead",
        external_event_default="financial_crime_lead_decision",
        default_authority_band="synthetic-up-to-GBP-250000",
        uses_authority_mcp=True,
        description=(
            "Escalation point for reimbursement decisions above the claims "
            "manager's delegation, and owner of synthetic mule-account "
            "investigation outcomes."
        ),
        display_color="#dc2626",
    ),
    "payments_operations_lead": Persona(
        role="payments_operations_lead",
        archetype="approver",
        scope_function="commercial",
        workflow_label="Payments Operations Lead",
        external_event_default="payments_operations_lead_decision",
        default_authority_band="synthetic-up-to-GBP-120000",
        uses_authority_mcp=True,
        description=(
            "Owns synthetic merchant and receiving-provider risk decisions "
            "across the payment estate."
        ),
        display_color="#0891b2",
    ),
    "vulnerable_customer_specialist": Persona(
        role="vulnerable_customer_specialist",
        archetype="reviewer",
        scope_function="commercial",
        workflow_label="Vulnerable Customer Specialist",
        external_event_default="vulnerable_customer_specialist_decision",
        default_authority_band="non-monetary",
        uses_authority_mcp=False,
        description=(
            "Determines whether a synthetic customer carries a vulnerability "
            "marker. The determination is never delegated to a model and is "
            "never overridden by a ranking."
        ),
        display_color="#7c3aed",
    ),
    "credit_risk_officer": Persona(
        role="credit_risk_officer",
        archetype="approver",
        scope_function="finance",
        workflow_label="Credit Risk Officer",
        external_event_default="credit_risk_officer_decision",
        default_authority_band="synthetic-up-to-GBP-5000000",
        uses_authority_mcp=True,
        description=(
            "Clears small, short-duration synthetic counterparty limit "
            "excesses within a delegated tier."
        ),
        display_color="#16a34a",
    ),
    "senior_credit_officer": Persona(
        role="senior_credit_officer",
        archetype="approver",
        scope_function="finance",
        workflow_label="Senior Credit Officer",
        external_event_default="senior_credit_officer_decision",
        default_authority_band="synthetic-up-to-GBP-50000000",
        uses_authority_mcp=True,
        description=(
            "Owns material or prolonged synthetic counterparty limit excess "
            "decisions above the officer tier."
        ),
        display_color="#ea580c",
    ),
}
