"""Zava Bank domain registry.

Three live workflows and a set of declared-but-unbuilt placeholders.

* ``app-fraud-reimbursement`` is the hero. It is world-owned: an actor-world
  sensor opens its objective, so the ramp loop never spawns it.
* ``mule-account-investigation`` and ``merchant-onboarding-risk`` are the
  supporting processes the ramp loop spawns continuously, which is what
  keeps the organisation busy when nobody is driving a demo.
* ``stub=True`` entries are org-chart reach only. They are not runtime
  spawnable and are excluded from the execution-visibility gate. They are
  declared so the bank renders as an institution, and they are never
  presented as working processes.
"""
from __future__ import annotations

from api.shared.domain_contracts import Domain, HitlGate, Phase
from verticals.banking.fraud_constants import (
    FRAUD_DISPLAY_NAME,
    FRAUD_HITL_EVENT,
    FRAUD_HITL_PERSONA,
    FRAUD_ORCHESTRATOR,
    FRAUD_WORKFLOW_ID_PREFIX,
    FRAUD_WORKFLOW_TYPE,
)
from verticals.banking.support_constants import (
    MERCHANT_DISPLAY_NAME,
    MERCHANT_HITL_EVENT,
    MERCHANT_HITL_PERSONA,
    MERCHANT_ORCHESTRATOR,
    MERCHANT_SPAWNER,
    MERCHANT_REALISTIC_INTERVAL_SECONDS,
    MERCHANT_SKILL,
    MERCHANT_WORKFLOW_ID_PREFIX,
    MERCHANT_WORKFLOW_TYPE,
    MULE_DISPLAY_NAME,
    MULE_HITL_EVENT,
    MULE_HITL_PERSONA,
    MULE_ORCHESTRATOR,
    MULE_SPAWNER,
    MULE_REALISTIC_INTERVAL_SECONDS,
    MULE_SKILL,
    MULE_WORKFLOW_ID_PREFIX,
    MULE_WORKFLOW_TYPE,
)


def _stub(
    workflow_type: str,
    display_name: str,
    prefix: str,
    surface: str,
) -> Domain:
    """A declared corporate process with no runtime implementation."""
    return Domain(
        workflow_type=workflow_type,
        display_name=display_name,
        workflow_id_prefix=prefix,
        orchestrator_name=f"Banking{prefix}Orchestrator",
        operator_surface=surface,
        phases=(),
        hitl_gates=(),
        skills=(),
        stub=True,
    )


BANKING_DOMAINS: dict[str, Domain] = {
    # --- Hero: world-owned, sensor-triggered --------------------------------
    FRAUD_WORKFLOW_TYPE: Domain(
        workflow_type=FRAUD_WORKFLOW_TYPE,
        display_name=FRAUD_DISPLAY_NAME,
        workflow_id_prefix=FRAUD_WORKFLOW_ID_PREFIX,
        orchestrator_name=FRAUD_ORCHESTRATOR,
        operator_surface="retail-banking",
        phases=(
            Phase("Scope Fraud Claim", "deterministic"),
            Phase("Trace Beneficiary Path", "deterministic"),
            Phase("Assess Claim Evidence", "agent"),
            Phase("Decide Reimbursement", "hitl"),
            Phase("Execute Reimbursement and Recovery", "deterministic"),
            Phase("Verify Reimbursement Outcome", "deterministic"),
        ),
        hitl_gates=(
            HitlGate(
                "Decide Reimbursement",
                FRAUD_HITL_EVENT,
                FRAUD_HITL_PERSONA,
            ),
        ),
        skills=("claim-evidence-assessor",),
        stub=False,
    ),
    # --- Supporting: ramp-spawned ------------------------------------------
    MULE_WORKFLOW_TYPE: Domain(
        workflow_type=MULE_WORKFLOW_TYPE,
        display_name=MULE_DISPLAY_NAME,
        workflow_id_prefix=MULE_WORKFLOW_ID_PREFIX,
        orchestrator_name=MULE_ORCHESTRATOR,
        operator_surface="financial-crime",
        phases=(
            Phase("Assemble Beneficiary Evidence", "deterministic"),
            Phase("Analyse Mule Network", "agent"),
            Phase("Approve Account Disposition", "hitl"),
            Phase("Commit Disposition", "deterministic"),
            Phase("Verify Disposition", "deterministic"),
        ),
        hitl_gates=(
            HitlGate(
                "Approve Account Disposition",
                MULE_HITL_EVENT,
                MULE_HITL_PERSONA,
            ),
        ),
        skills=(MULE_SKILL,),
        stub=False,
        spawn_fn=MULE_SPAWNER,
        realistic_interval_seconds=MULE_REALISTIC_INTERVAL_SECONDS,
    ),
    MERCHANT_WORKFLOW_TYPE: Domain(
        workflow_type=MERCHANT_WORKFLOW_TYPE,
        display_name=MERCHANT_DISPLAY_NAME,
        workflow_id_prefix=MERCHANT_WORKFLOW_ID_PREFIX,
        orchestrator_name=MERCHANT_ORCHESTRATOR,
        operator_surface="payments",
        phases=(
            Phase("Collect Merchant Application", "deterministic"),
            Phase("Assess Merchant Risk", "agent"),
            Phase("Approve Onboarding Decision", "hitl"),
            Phase("Commit Merchant Decision", "deterministic"),
            Phase("Verify Merchant State", "deterministic"),
        ),
        hitl_gates=(
            HitlGate(
                "Approve Onboarding Decision",
                MERCHANT_HITL_EVENT,
                MERCHANT_HITL_PERSONA,
            ),
        ),
        skills=(MERCHANT_SKILL,),
        stub=False,
        spawn_fn=MERCHANT_SPAWNER,
        realistic_interval_seconds=MERCHANT_REALISTIC_INTERVAL_SECONDS,
    ),
    # --- Declared corporate reach (not implemented) -------------------------
    **{
        domain.workflow_type: domain
        for domain in (
            _stub("card-dispute-chargeback", "Card Dispute and Chargeback",
                  "BCDC", "retail-banking"),
            _stub("collections-and-forbearance", "Collections and Forbearance",
                  "BCOL", "retail-banking"),
            _stub("sme-lending-decision", "SME Lending Decision",
                  "BSME", "retail-banking"),
            _stub("scheme-dispute-resolution", "Scheme Dispute Resolution",
                  "BSDR", "payments"),
            _stub("settlement-exception", "Settlement Exception",
                  "BSET", "payments"),
            _stub("counterparty-limit-excess", "Counterparty Limit Excess",
                  "BCLE", "credit-risk"),
            _stub("credit-watchlist-review", "Credit Watchlist Review",
                  "BCWR", "credit-risk"),
            _stub("collateral-dispute-resolution", "Collateral Dispute Resolution",
                  "BCDR", "markets"),
            _stub("post-trade-settlement-fail", "Post-Trade Settlement Fail",
                  "BPTS", "markets"),
            _stub("sanctions-alert-triage", "Sanctions Alert Triage",
                  "BSAT", "financial-crime"),
            _stub("suspicious-activity-report", "Suspicious Activity Report",
                  "BSAR", "financial-crime"),
            _stub("client-risk-review", "Client Risk Review",
                  "BCRR", "client-governance"),
            _stub("relationship-exit-decision", "Relationship Exit Decision",
                  "BRED", "client-governance"),
            _stub("portfolio-suitability-review", "Portfolio Suitability Review",
                  "BPSR", "wealth"),
            _stub("kyc-periodic-refresh", "KYC Periodic Refresh",
                  "BKYC", "wealth"),
        )
    },
}
