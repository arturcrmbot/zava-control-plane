"""Zava Bank agent registry.

Each entry is bounded: a fixed allow-list of pack-owned synthetic tools, a
reversible-only flag, and a value ceiling matching the persona whose decision
the agent's output feeds. Agents rank and explain; they never admit an option
the deterministic layer refused, and never authorise value.
"""
from __future__ import annotations

from api.shared.agent_contracts import AgentRegistryEntry
from verticals.banking.fraud_constants import FRAUD_REIMBURSEMENT_CAP_GBP
from verticals.banking.support_constants import (
    MERCHANT_MAX_VALUE_GBP,
    MERCHANT_SKILL,
    MULE_MAX_VALUE_GBP,
    MULE_SKILL,
)


BANKING_AGENTS: dict[str, AgentRegistryEntry] = {
    "claim-evidence-assessor": AgentRegistryEntry(
        agent_id="claim-evidence-assessor",
        description=(
            "Ranks deterministically admitted synthetic APP fraud "
            "reimbursement options and explains the trade-offs."
        ),
        allowed_tools=(
            "banking_read_claim_evidence",
            "banking_rank_admitted_claim_options",
        ),
        reversible_only=True,
        max_value_gbp=FRAUD_REIMBURSEMENT_CAP_GBP,
        scope_function="retail-banking",
    ),
    MULE_SKILL: AgentRegistryEntry(
        agent_id=MULE_SKILL,
        description=(
            "Explains synthetic beneficiary-account linkage and ranks "
            "deterministically admitted disposition options."
        ),
        allowed_tools=(
            "banking_read_case_evidence",
            "banking_rank_admitted_case_options",
        ),
        reversible_only=True,
        max_value_gbp=MULE_MAX_VALUE_GBP,
        scope_function="financial-crime",
    ),
    MERCHANT_SKILL: AgentRegistryEntry(
        agent_id=MERCHANT_SKILL,
        description=(
            "Explains synthetic merchant application risk and ranks "
            "deterministically admitted onboarding options."
        ),
        allowed_tools=(
            "banking_read_case_evidence",
            "banking_rank_admitted_case_options",
        ),
        reversible_only=True,
        max_value_gbp=MERCHANT_MAX_VALUE_GBP,
        scope_function="payments",
    ),
}
