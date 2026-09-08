from __future__ import annotations

from dataclasses import dataclass

from verticals.airline.aog_constants import (
    AOG_COMMAND_TYPE,
    AOG_DISPLAY_NAME,
    AOG_FAILURE_EVENT,
    AOG_HITL_EVENT,
    AOG_HITL_PERSONA,
    AOG_OBJECTIVE_TYPE,
    AOG_ORCHESTRATOR,
    AOG_SCENARIO_ID,
    AOG_SENSOR_ID,
    AOG_STORY_ID,
    AOG_SUCCESS_EVENT,
    AOG_WORKFLOW_TYPE,
)
from verticals.airline.schedule_constants import (
    SCHED_COMMAND_TYPE,
    SCHED_FAILURE_EVENT,
    SCHED_HITL_PERSONA,
    SCHED_OBJECTIVE_TYPE,
    SCHED_SCENARIO_ID,
    SCHED_SENSOR_ID,
    SCHED_STORY_ID,
    SCHED_SUCCESS_EVENT,
    SCHED_WORKFLOW_TYPE,
)


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
GOLDEN_WORKFLOW_ID = "AIRHUB-0001"
GOLDEN_DECISION_ID = "SYN-DECISION-001"

_SCHED_HITL_EVENT = "network_operations_director_decision"
_SCHED_ORCHESTRATOR = "AirlineScheduleResilienceOrchestrator"


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
    AOG_WORKFLOW_TYPE: AirlineProcessProfile(
        workflow_type=AOG_WORKFLOW_TYPE,
        orchestrator=AOG_ORCHESTRATOR,
        sensor_id=AOG_SENSOR_ID,
        objective_type=AOG_OBJECTIVE_TYPE,
        command_type=AOG_COMMAND_TYPE,
        success_event=AOG_SUCCESS_EVENT,
        failure_event=AOG_FAILURE_EVENT,
        hitl_persona=AOG_HITL_PERSONA,
        hitl_event=AOG_HITL_EVENT,
        scenario_id=AOG_SCENARIO_ID,
        story_id=AOG_STORY_ID,
    ),
    SCHED_WORKFLOW_TYPE: AirlineProcessProfile(
        workflow_type=SCHED_WORKFLOW_TYPE,
        orchestrator=_SCHED_ORCHESTRATOR,
        sensor_id=SCHED_SENSOR_ID,
        objective_type=SCHED_OBJECTIVE_TYPE,
        command_type=SCHED_COMMAND_TYPE,
        success_event=SCHED_SUCCESS_EVENT,
        failure_event=SCHED_FAILURE_EVENT,
        hitl_persona=SCHED_HITL_PERSONA,
        hitl_event=_SCHED_HITL_EVENT,
        scenario_id=SCHED_SCENARIO_ID,
        story_id=SCHED_STORY_ID,
    ),
}
