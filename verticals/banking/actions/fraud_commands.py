"""Banking Hero 1 - typed reimbursement command.

One command type: ``banking.commit_reimbursement_decision``. It is built
only from a deterministically admitted option, re-checks that the option is
still admitted at apply time, mutates the world, and opens an evaluation
that compares the result with taking no action.

Partial application is not possible: either every action in the option
lands, or the command is rejected and nothing is written.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from api.server.world.model import SimulationCommand, SimulationEvent
from verticals.banking.fraud_constants import (
    FRAUD_COMMAND_TYPE,
    FRAUD_FUNCTION,
    FRAUD_ISSUER,
    FRAUD_PSP_LIABILITY_SHARE,
    FRAUD_SUCCESS_EVENT,
)
from verticals.banking.fraud_constraints import (
    ACTION_CREDIT_CUSTOMER,
    ACTION_FREEZE_BENEFICIARY,
    ACTION_OPEN_INVESTIGATION,
    ACTION_RAISE_PSP_SPLIT,
    ACTION_RECORD_REFUSAL,
    OPTION_REFUSE_CAUTION,
    option_for,
)
from verticals.banking.worlds.model import (
    Investigation,
    ReimbursementCommand,
    ReimbursementEvaluation,
)

if TYPE_CHECKING:
    from verticals.banking.worlds.scenario import ZavaBankWorld


def reimbursement_command_id(
    *,
    workflow_id: str,
    decision_id: str,
    option_id: str,
) -> str:
    return f"SYN-APP-CMD-{workflow_id}-{decision_id}-{option_id}"


def build_reimbursement_command(
    world: ZavaBankWorld,
    *,
    claim_id: str,
    option_id: str,
    workflow_id: str,
    decision_id: str,
    persona: str,
) -> SimulationCommand:
    observation = world.observation_for_claim(claim_id)
    result = option_for(observation, option_id)
    if result is None:
        raise ValueError(f"unknown reimbursement option: {option_id!r}")
    if not result.feasible:
        raise ValueError(
            f"reimbursement option {option_id!r} is not admitted: "
            f"{', '.join(result.reasons)}"
        )
    option = result.option
    return SimulationCommand(
        command_id=reimbursement_command_id(
            workflow_id=workflow_id,
            decision_id=decision_id,
            option_id=option_id,
        ),
        trace_id=str(observation["trace_id"]),
        issued_by=FRAUD_ISSUER,
        type=FRAUD_COMMAND_TYPE,
        payload={
            "workflow_id": workflow_id,
            "objective_id": f"SYN-APP-OBJECTIVE-{workflow_id}",
            "decision_id": decision_id,
            "scenario_id": observation["scenario_id"],
            "story_id": observation["story_id"],
            "claim_id": claim_id,
            "persona": persona,
            "option_id": option.option_id,
            "action_category": "synthetic-app-fraud-reimbursement",
            "actions": [action.to_dict() for action in option.actions],
            "evidence_versions": dict(option.evidence_versions),
            "value_gbp": option.value_gbp,
            "expected_event_type": FRAUD_SUCCESS_EVENT,
        },
    )


def _reject(
    world: ZavaBankWorld,
    command: SimulationCommand,
    reason: str,
) -> SimulationEvent:
    return world.runtime.emit(
        "command.rejected",
        actor_id=command.issued_by,
        trace_id=command.trace_id,
        payload={"command": command.to_dict(), "reason": reason},
    )


def apply_reimbursement_command(
    world: ZavaBankWorld,
    command: SimulationCommand,
) -> SimulationEvent:
    payload = command.payload
    claim_id = payload.get("claim_id")
    option_id = payload.get("option_id")
    workflow_id = payload.get("workflow_id")
    decision_id = payload.get("decision_id")
    persona = payload.get("persona")

    claim = world.fraud_claims.get(claim_id) if isinstance(claim_id, str) else None
    if claim is None:
        return _reject(world, command, f"unknown claim {claim_id!r}")

    observation = world.observation_for_claim(claim.id)

    expected_versions = payload.get("evidence_versions")
    if expected_versions != observation.get("evidence_versions"):
        return _reject(
            world, command, "world evidence moved after the approval checkpoint"
        )

    result = option_for(observation, option_id) if isinstance(option_id, str) else None
    if result is None:
        return _reject(world, command, f"unknown reimbursement option {option_id!r}")
    if not result.feasible:
        return _reject(
            world,
            command,
            f"option {option_id!r} is no longer admitted: {', '.join(result.reasons)}",
        )

    option = result.option
    customer = world.customers[claim.customer_id]
    account = world.accounts[customer.account_id]
    beneficiary = world.beneficiaries[claim.beneficiary_id]

    reimbursed = 0.0
    recovered = 0.0
    psp_share = 0.0
    refused = option.option_id == OPTION_REFUSE_CAUTION

    for action in option.actions:
        kind = action.action_type
        amount = float(action.amount_gbp or 0.0)
        if kind == ACTION_CREDIT_CUSTOMER:
            reimbursed = amount
            account.balance_gbp = round(account.balance_gbp + amount, 2)
            account.version += 1
        elif kind == ACTION_FREEZE_BENEFICIARY:
            recovered = min(amount, beneficiary.balance_gbp)
            beneficiary.frozen_gbp = round(beneficiary.frozen_gbp + recovered, 2)
            beneficiary.balance_gbp = round(beneficiary.balance_gbp - recovered, 2)
            beneficiary.status = "frozen"
            beneficiary.version += 1
        elif kind == ACTION_RAISE_PSP_SPLIT:
            psp_share = round(reimbursed * FRAUD_PSP_LIABILITY_SHARE, 2)
        elif kind == ACTION_RECORD_REFUSAL:
            beneficiary.status = "under_review"
            beneficiary.version += 1
        elif kind == ACTION_OPEN_INVESTIGATION:
            investigation_id = f"SYN-INV-{claim.id}"
            if investigation_id not in world.investigations:
                investigation = Investigation(
                    id=investigation_id,
                    subject_id=beneficiary.id,
                    subject_kind="beneficiary",
                    location_id=beneficiary.location_id,
                    opened_by_workflow_id=str(workflow_id),
                    linked_claim_ids=(claim.id,),
                )
                world.investigations[investigation_id] = investigation
                opened = world.runtime.emit(
                    "banking.investigation.opened",
                    actor_id=investigation_id,
                    target_id=beneficiary.id,
                    trace_id=command.trace_id,
                    payload={
                        "claim_id": claim.id,
                        "beneficiary_id": beneficiary.id,
                        "holder_id": beneficiary.holder_id,
                        "holder_kind": beneficiary.holder_kind,
                        "location_id": beneficiary.location_id,
                        "function": "financial-crime",
                    },
                )
                investigation.last_event_id = opened.event_id
        else:
            return _reject(world, command, f"unsupported action {kind!r}")

    claim.status = "refused" if refused else "reimbursed"
    claim.version += 1
    customer.status = "refused" if refused else "reimbursed"
    customer.version += 1

    command_record = ReimbursementCommand(
        id=command.command_id,
        workflow_id=str(workflow_id),
        decision_id=str(decision_id),
        claim_id=claim.id,
        option_id=option.option_id,
        persona=str(persona),
        value_gbp=option.value_gbp,
        action_types=tuple(action.action_type for action in option.actions),
        evidence_versions=option.evidence_versions,
    )
    world.reimbursement_commands[command_record.id] = command_record

    evaluation = ReimbursementEvaluation(
        id=f"SYN-APP-EVAL-{command.command_id}",
        workflow_id=str(workflow_id),
        command_id=command.command_id,
        claim_id=claim.id,
        option_id=option.option_id,
        status="completed",
        invariant_results=(
            "evidence_versions_matched",
            "option_deterministically_admitted",
            "vulnerability_respected",
        ),
        reimbursed_gbp=round(reimbursed, 2),
        recovered_from_beneficiary_gbp=round(recovered, 2),
        receiving_psp_share_gbp=psp_share,
        decided_within_window=claim.reported_at_minutes <= claim.deadline_minutes,
        vulnerability_respected=not (claim.vulnerability_flag and refused),
        synthetic_cost_gbp=round(max(reimbursed - recovered - psp_share, 0.0), 2),
        no_action_customer_loss_gbp=round(claim.amount_gbp, 2),
    )
    world.reimbursement_evaluations[evaluation.id] = evaluation

    applied = world.runtime.emit(
        FRAUD_SUCCESS_EVENT,
        actor_id=claim.id,
        target_id=beneficiary.id,
        trace_id=command.trace_id,
        payload={
            "workflow_id": workflow_id,
            "claim_id": claim.id,
            "option_id": option.option_id,
            "persona": persona,
            "decision_id": decision_id,
            "value_gbp": option.value_gbp,
            "location_id": claim.location_id,
            "function": FRAUD_FUNCTION,
            "mutation_records": {
                "claim": claim.id,
                "customer": customer.id,
                "account": account.id,
                "beneficiary": beneficiary.id,
                "command": command_record.id,
                "evaluation": evaluation.id,
            },
            "evaluation": {
                "reimbursed_gbp": evaluation.reimbursed_gbp,
                "recovered_from_beneficiary_gbp": (
                    evaluation.recovered_from_beneficiary_gbp
                ),
                "receiving_psp_share_gbp": evaluation.receiving_psp_share_gbp,
                "synthetic_cost_gbp": evaluation.synthetic_cost_gbp,
                "no_action_customer_loss_gbp": (
                    evaluation.no_action_customer_loss_gbp
                ),
                "vulnerability_respected": evaluation.vulnerability_respected,
            },
        },
    )
    claim.last_event_id = applied.event_id
    command_record.last_event_id = applied.event_id
    evaluation.last_event_id = applied.event_id
    return applied


def command_payload_summary(command: SimulationCommand) -> dict[str, Any]:
    """Compact view used by the pack's workflow-detail hook."""
    payload = command.payload
    return {
        "claimId": payload.get("claim_id"),
        "optionId": payload.get("option_id"),
        "valueGbp": payload.get("value_gbp"),
        "persona": payload.get("persona"),
        "decisionId": payload.get("decision_id"),
    }
