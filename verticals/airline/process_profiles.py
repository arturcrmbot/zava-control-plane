from __future__ import annotations

from dataclasses import dataclass


WORKFLOW_TYPE = "integrated-hub-disruption-recovery"
ORCHESTRATOR = "AirlineIntegratedHubRecoveryOrchestrator"
SENSOR_ID = "sensor:integrated_hub_disruption"
OBJECTIVE_TYPE = "recover_hub_disruption"
COMMAND_TYPE = "airline.commit_recovery_plan"
SUCCESS_EVENT = "airline.recovery.applied"
FAILURE_EVENT = "command.rejected"
HITL_PERSONA = "duty_operations_manager"
HITL_EVENT = "duty_operations_manager_decision"
SCENARIO_ID = "synthetic-hub-cascade"
STORY_ID = "SYN-STORY-HUB-001"


@dataclass(frozen=True, slots=True)
class AirlineProcessProfile:
    workflow_type: str
    orchestrator: str
    sensor_id: str
    objective_type: str
    command_type: str
    success_event: str
    failure_event: str
    hitl_persona: str
    hitl_event: str
    scenario_id: str
    story_id: str


AIRLINE_PROCESS_PROFILES: dict[str, AirlineProcessProfile] = {
    WORKFLOW_TYPE: AirlineProcessProfile(
        workflow_type=WORKFLOW_TYPE,
        orchestrator=ORCHESTRATOR,
        sensor_id=SENSOR_ID,
        objective_type=OBJECTIVE_TYPE,
        command_type=COMMAND_TYPE,
        success_event=SUCCESS_EVENT,
        failure_event=FAILURE_EVENT,
        hitl_persona=HITL_PERSONA,
        hitl_event=HITL_EVENT,
        scenario_id=SCENARIO_ID,
        story_id=STORY_ID,
    ),
}
