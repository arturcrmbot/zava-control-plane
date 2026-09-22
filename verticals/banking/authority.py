"""Zava Bank authority declarations.

The governance kernel synthesises a matrix rule per (role, action) pair from
these rows, with a value band of ``0 .. spend_limit_gbp``. Actions that are
themselves HITL external-event names are skipped by the kernel, which is why
each row lists both its decision event and the typed command it authorises:
the command is the action the workflow actually checks.

Every limit is a synthetic demo assumption.

The claims manager's limit is deliberately below the synthetic reimbursement
cap of GBP 85,000. That gap is the point: a capped claim above GBP 50,000 is
refused by the real authority matrix and escalates, rather than quietly
being approved because a demo needed it to be.
"""
from __future__ import annotations

from api.shared.authority_contracts import AuthorityRow
from verticals.banking.fraud_constants import (
    FRAUD_COMMAND_TYPE,
    FRAUD_ESCALATION_ROLE,
    FRAUD_HITL_EVENT,
    FRAUD_MANAGER_LIMIT_GBP,
)
from verticals.banking.support_constants import (
    MERCHANT_COMMAND_TYPE,
    MERCHANT_HITL_EVENT,
    MERCHANT_MAX_VALUE_GBP,
    MULE_COMMAND_TYPE,
    MULE_HITL_EVENT,
    MULE_MAX_VALUE_GBP,
)


BANKING_AUTHORITY: dict[str, AuthorityRow] = {
    "fraud_decision_manager": AuthorityRow(
        role="fraud_decision_manager",
        spend_limit_gbp=FRAUD_MANAGER_LIMIT_GBP,
        approval_actions=(FRAUD_HITL_EVENT, FRAUD_COMMAND_TYPE),
        delegate_to=FRAUD_ESCALATION_ROLE,
    ),
    "financial_crime_lead": AuthorityRow(
        role="financial_crime_lead",
        spend_limit_gbp=MULE_MAX_VALUE_GBP,
        approval_actions=(MULE_HITL_EVENT, MULE_COMMAND_TYPE, FRAUD_COMMAND_TYPE),
        delegate_to=None,
    ),
    "payments_operations_lead": AuthorityRow(
        role="payments_operations_lead",
        spend_limit_gbp=MERCHANT_MAX_VALUE_GBP,
        approval_actions=(MERCHANT_HITL_EVENT, MERCHANT_COMMAND_TYPE),
        delegate_to=None,
    ),
    "credit_risk_officer": AuthorityRow(
        role="credit_risk_officer",
        spend_limit_gbp=5_000_000.0,
        approval_actions=(
            "credit_risk_officer_decision",
            "banking.commit_limit_remediation",
        ),
        delegate_to="senior_credit_officer",
    ),
    "senior_credit_officer": AuthorityRow(
        role="senior_credit_officer",
        spend_limit_gbp=50_000_000.0,
        approval_actions=(
            "senior_credit_officer_decision",
            "banking.commit_limit_remediation",
        ),
        delegate_to=None,
    ),
}
