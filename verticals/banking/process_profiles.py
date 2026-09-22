"""Identity profile per Banking workflow.

One row per live workflow binding its sensor, objective, command, events,
persona and world case together, so every surface resolves the same names.
"""
from __future__ import annotations

from dataclasses import dataclass

from verticals.banking.fraud_constants import (
    FRAUD_COMMAND_TYPE,
    FRAUD_FAILURE_EVENT,
    FRAUD_HITL_EVENT,
    FRAUD_HITL_PERSONA,
    FRAUD_OBJECTIVE_TYPE,
    FRAUD_ORCHESTRATOR,
    FRAUD_SCENARIO_STANDARD,
    FRAUD_SENSOR_ID,
    FRAUD_STORY_STANDARD,
    FRAUD_SUCCESS_EVENT,
    FRAUD_WORKFLOW_TYPE,
)
from verticals.banking.support_constants import (
    MERCHANT_COMMAND_TYPE,
    MERCHANT_HITL_EVENT,
    MERCHANT_HITL_PERSONA,
    MERCHANT_ORCHESTRATOR,
    MERCHANT_SUCCESS_EVENT,
    MERCHANT_WORKFLOW_TYPE,
    MULE_COMMAND_TYPE,
    MULE_HITL_EVENT,
    MULE_HITL_PERSONA,
    MULE_ORCHESTRATOR,
    MULE_SUCCESS_EVENT,
    MULE_WORKFLOW_TYPE,
)


@dataclass(frozen=True, slots=True)
class BankingProcessProfile:
    workflow_type: str
    orchestrator: str
    sensor_id: str | None
    objective_type: str | None
    command_type: str
    success_event: str
    failure_event: str
    hitl_persona: str
    hitl_event: str
    scenario_id: str | None
    story_id: str | None


BANKING_PROCESS_PROFILES: dict[str, BankingProcessProfile] = {
    FRAUD_WORKFLOW_TYPE: BankingProcessProfile(
        workflow_type=FRAUD_WORKFLOW_TYPE,
        orchestrator=FRAUD_ORCHESTRATOR,
        sensor_id=FRAUD_SENSOR_ID,
        objective_type=FRAUD_OBJECTIVE_TYPE,
        command_type=FRAUD_COMMAND_TYPE,
        success_event=FRAUD_SUCCESS_EVENT,
        failure_event=FRAUD_FAILURE_EVENT,
        hitl_persona=FRAUD_HITL_PERSONA,
        hitl_event=FRAUD_HITL_EVENT,
        scenario_id=FRAUD_SCENARIO_STANDARD,
        story_id=FRAUD_STORY_STANDARD,
    ),
    MULE_WORKFLOW_TYPE: BankingProcessProfile(
        workflow_type=MULE_WORKFLOW_TYPE,
        orchestrator=MULE_ORCHESTRATOR,
        sensor_id=None,
        objective_type=None,
        command_type=MULE_COMMAND_TYPE,
        success_event=MULE_SUCCESS_EVENT,
        failure_event="command.rejected",
        hitl_persona=MULE_HITL_PERSONA,
        hitl_event=MULE_HITL_EVENT,
        scenario_id=None,
        story_id=None,
    ),
    MERCHANT_WORKFLOW_TYPE: BankingProcessProfile(
        workflow_type=MERCHANT_WORKFLOW_TYPE,
        orchestrator=MERCHANT_ORCHESTRATOR,
        sensor_id=None,
        objective_type=None,
        command_type=MERCHANT_COMMAND_TYPE,
        success_event=MERCHANT_SUCCESS_EVENT,
        failure_event="command.rejected",
        hitl_persona=MERCHANT_HITL_PERSONA,
        hitl_event=MERCHANT_HITL_EVENT,
        scenario_id=None,
        story_id=None,
    ),
}
