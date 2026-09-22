"""Banking Hero 1 - APP Fraud Reimbursement constants.

Focused constants for the app-fraud-reimbursement workflow. Do not import
limit_constants or process_profiles here; Hero 1 stays independently
importable so its unit tests do not drag Hero 2 into the import graph.

Public-source context (operating reality only, never a real record):
UK Payment Systems Regulator mandatory reimbursement applies to Faster
Payments and CHAPS payments made on or after 7 October 2024, requires a
decision within five business days, caps reimbursement per claim, splits
liability equally between sending and receiving payment service providers,
and forbids refusing a vulnerable customer under the consumer standard of
caution. Every identifier, amount, threshold and record below is synthetic.
"""
from __future__ import annotations

# --- Identity -------------------------------------------------------------

FRAUD_WORKFLOW_TYPE = "app-fraud-reimbursement"
FRAUD_DISPLAY_NAME = "APP Fraud Reimbursement"
FRAUD_WORKFLOW_ID_PREFIX = "BAPP"
FRAUD_ORCHESTRATOR = "BankingAppFraudReimbursementOrchestrator"
FRAUD_SENSOR_ID = "sensor:app_fraud_claim"
FRAUD_OBJECTIVE_TYPE = "resolve_app_fraud_claim"
FRAUD_COMMAND_TYPE = "banking.commit_reimbursement_decision"
FRAUD_SUCCESS_EVENT = "banking.reimbursement.applied"
FRAUD_FAILURE_EVENT = "command.rejected"
FRAUD_SOURCE_EVENT_TYPE = "banking.app_fraud.claim_raised"
FRAUD_HITL_PERSONA = "fraud_decision_manager"
FRAUD_HITL_EVENT = "fraud_decision_manager_decision"
FRAUD_HITL_CATEGORY = "synthetic-app-fraud-reimbursement"
FRAUD_ISSUER = "retail-banking"
FRAUD_FUNCTION = "retail-banking"

# --- Synthetic demo thresholds -------------------------------------------
# Statutory-shaped cap expressed as a synthetic demo assumption. The
# deterministic admission never admits a reimbursement above this value.
FRAUD_REIMBURSEMENT_CAP_GBP = 85_000.0

# The claims manager's delegated authority sits deliberately BELOW the cap,
# mirroring the ordinary banking pattern where a statutory ceiling and a
# personal delegation are different numbers. A capped claim above this value
# is refused by the governance kernel and escalates.
FRAUD_MANAGER_LIMIT_GBP = 50_000.0
FRAUD_ESCALATION_ROLE = "financial_crime_lead"

# Decision window used by the deterministic scope and evaluation phases.
FRAUD_DECISION_WINDOW_BUSINESS_DAYS = 5

# --- Scenarios ------------------------------------------------------------
# Three cases share one sensor, one objective type and one orchestrator.
# They differ only in the synthetic claim they activate, which is what makes
# the three outcomes a property of the evidence rather than of the code path.

FRAUD_SCENARIO_STANDARD = "synthetic-app-fraud-claim"
FRAUD_SCENARIO_VULNERABLE = "synthetic-app-fraud-vulnerable"
FRAUD_SCENARIO_OVER_DELEGATION = "synthetic-app-fraud-over-delegation"

FRAUD_SCENARIOS: tuple[str, ...] = (
    FRAUD_SCENARIO_STANDARD,
    FRAUD_SCENARIO_VULNERABLE,
    FRAUD_SCENARIO_OVER_DELEGATION,
)

FRAUD_STORY_STANDARD = "SYN-STORY-APP-001"
FRAUD_STORY_VULNERABLE = "SYN-STORY-APP-002"
FRAUD_STORY_OVER_DELEGATION = "SYN-STORY-APP-003"

FRAUD_STORY_BY_SCENARIO: dict[str, str] = {
    FRAUD_SCENARIO_STANDARD: FRAUD_STORY_STANDARD,
    FRAUD_SCENARIO_VULNERABLE: FRAUD_STORY_VULNERABLE,
    FRAUD_SCENARIO_OVER_DELEGATION: FRAUD_STORY_OVER_DELEGATION,
}

FRAUD_WORKFLOW_ID = "BAPP-0001"
FRAUD_DECISION_ID = "SYN-APP-DECISION-001"

# --- Synthetic records ----------------------------------------------------

FRAUD_RAIL_FPS = "SYN-RAIL-FPS"
FRAUD_RAIL_CHAPS = "SYN-RAIL-CHAPS"

# Claim under the manager's delegation, no vulnerability flag.
FRAUD_CLAIM_STANDARD = "SYN-CLAIM-0031"
FRAUD_CLAIM_STANDARD_CUSTOMER = "SYN-CUST-0007"
FRAUD_CLAIM_STANDARD_PAYMENT = "SYN-PAY-0031"
FRAUD_CLAIM_STANDARD_AMOUNT_GBP = 18_400.0

# Vulnerable customer: refusal is never deterministically admitted.
FRAUD_CLAIM_VULNERABLE = "SYN-CLAIM-0032"
FRAUD_CLAIM_VULNERABLE_CUSTOMER = "SYN-CUST-0004"
FRAUD_CLAIM_VULNERABLE_PAYMENT = "SYN-PAY-0032"
FRAUD_CLAIM_VULNERABLE_AMOUNT_GBP = 6_750.0

# Above the cap: deterministic admission caps it, and the capped value still
# exceeds the claims manager's delegated authority.
FRAUD_CLAIM_OVER_DELEGATION = "SYN-CLAIM-0033"
FRAUD_CLAIM_OVER_DELEGATION_CUSTOMER = "SYN-CUST-0011"
FRAUD_CLAIM_OVER_DELEGATION_PAYMENT = "SYN-PAY-0033"
FRAUD_CLAIM_OVER_DELEGATION_AMOUNT_GBP = 92_000.0

FRAUD_CLAIM_BY_SCENARIO: dict[str, str] = {
    FRAUD_SCENARIO_STANDARD: FRAUD_CLAIM_STANDARD,
    FRAUD_SCENARIO_VULNERABLE: FRAUD_CLAIM_VULNERABLE,
    FRAUD_SCENARIO_OVER_DELEGATION: FRAUD_CLAIM_OVER_DELEGATION,
}

# Beneficiary ("mule") accounts the traced funds landed in. SYN-BENE-002 is
# held by SYN-CORP-014, the same synthetic corporate client that carries the
# Hero 2 counterparty exposure. One client, two ends of the bank.
FRAUD_BENEFICIARY_STANDARD = "SYN-BENE-002"
FRAUD_BENEFICIARY_VULNERABLE = "SYN-BENE-001"
FRAUD_BENEFICIARY_OVER_DELEGATION = "SYN-BENE-003"

FRAUD_SHARED_CORPORATE_CLIENT = "SYN-CORP-014"
FRAUD_RECEIVING_PSP = "SYN-PSP-002"

# Liability is shared equally between the sending and receiving providers.
FRAUD_PSP_LIABILITY_SHARE = 0.5
