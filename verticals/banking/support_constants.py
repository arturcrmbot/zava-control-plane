"""Banking supporting-process constants.

Two supporting processes run alongside Hero 1. They exist so the bank keeps
working when nobody is driving it: the ramp loop spawns them continuously,
which is what makes the organisation read as always-on rather than as a
single scripted story.

Each keeps a distinct trigger, orchestrator, typed command, persona and
success event. They share deterministic machinery; they do not share
identity or evidence.
"""
from __future__ import annotations

# --- Mule account investigation (Financial Crime) -------------------------

MULE_WORKFLOW_TYPE = "mule-account-investigation"
MULE_DISPLAY_NAME = "Mule Account Investigation"
MULE_WORKFLOW_ID_PREFIX = "BMUL"
MULE_ORCHESTRATOR = "BankingMuleAccountInvestigationOrchestrator"
MULE_COMMAND_TYPE = "banking.commit_mule_disposition"
MULE_SUCCESS_EVENT = "banking.mule_disposition.applied"
MULE_HITL_PERSONA = "financial_crime_lead"
MULE_HITL_EVENT = "financial_crime_lead_decision"
MULE_HITL_CATEGORY = "synthetic-mule-disposition"
MULE_FUNCTION = "financial-crime"
MULE_SKILL = "mule-network-analyst"
MULE_MAX_VALUE_GBP = 250_000.0
MULE_SPAWNER = "verticals.banking.spawners.spawn_mule_investigation_workflow"

# --- Merchant onboarding risk (Payments) ----------------------------------

MERCHANT_WORKFLOW_TYPE = "merchant-onboarding-risk"
MERCHANT_DISPLAY_NAME = "Merchant Onboarding Risk"
MERCHANT_WORKFLOW_ID_PREFIX = "BMER"
MERCHANT_ORCHESTRATOR = "BankingMerchantOnboardingRiskOrchestrator"
MERCHANT_COMMAND_TYPE = "banking.commit_merchant_decision"
MERCHANT_SUCCESS_EVENT = "banking.merchant_decision.applied"
MERCHANT_HITL_PERSONA = "payments_operations_lead"
MERCHANT_HITL_EVENT = "payments_operations_lead_decision"
MERCHANT_HITL_CATEGORY = "synthetic-merchant-onboarding"
MERCHANT_FUNCTION = "payments"
MERCHANT_SKILL = "merchant-risk-assessor"
MERCHANT_MAX_VALUE_GBP = 120_000.0
MERCHANT_SPAWNER = (
    "verticals.banking.spawners.spawn_merchant_onboarding_workflow"
)

# Real-world cadence per process, in seconds. The ramp loop divides this by
# DEMO_TIME_WARP_FACTOR (default 60) to get the demo spawn interval, so these
# are "how often this happens in the real bank", not "how often a rocket
# appears".
#
# Every live process does real agent work, and an agent session takes real
# time. Opening cases faster than the bank can actually think starves every
# session, including the hero's. 5400 -> a case every 90 demo-seconds;
# 7200 -> every 120.
#
# Model requests are also a metered resource. Under LLM_RUNTIME=ghcp the
# Copilot request quota is finite, and opening background cases every few
# seconds will exhaust it and starve the hero. If a heavier steady state is
# wanted, move to a runtime with its own quota rather than speeding this up.
MULE_REALISTIC_INTERVAL_SECONDS = 5_400
MERCHANT_REALISTIC_INTERVAL_SECONDS = 7_200
