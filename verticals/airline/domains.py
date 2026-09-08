from __future__ import annotations

from api.shared.domain_contracts import Domain, HitlGate, Phase
from verticals.airline.aog_constants import (
    AOG_DISPLAY_NAME,
    AOG_ORCHESTRATOR,
    AOG_WORKFLOW_TYPE,
    AOG_WORKFLOW_ID_PREFIX,
)
from verticals.airline.schedule_constants import (
    SCHED_DISPLAY_NAME,
    SCHED_HITL_PERSONA,
    SCHED_WORKFLOW_ID_PREFIX,
    SCHED_WORKFLOW_TYPE,
)


WORKFLOW_TYPE = "integrated-hub-disruption-recovery"

AIRLINE_DOMAINS: dict[str, Domain] = {
    WORKFLOW_TYPE: Domain(
        workflow_type=WORKFLOW_TYPE,
        display_name="Integrated Hub Disruption Recovery",
        workflow_id_prefix="AIRHUB",
        orchestrator_name="AirlineIntegratedHubRecoveryOrchestrator",
        operator_surface="operations-control",
        phases=(
            Phase("Detect Hub Disruption", "deterministic"),
            Phase("Assess Network Impact", "agent"),
            Phase("Synthesize Recovery Options", "agent"),
            Phase("Approve Recovery Plan", "hitl"),
            Phase("Commit Recovery Actions", "deterministic"),
            Phase("Verify Recovery Outcome", "deterministic"),
        ),
        hitl_gates=(
            HitlGate(
                "Approve Recovery Plan",
                "duty_operations_manager_decision",
                "duty_operations_manager",
            ),
        ),
        skills=("network-impact-assessor", "recovery-option-ranker"),
        stub=False,
    ),
    AOG_WORKFLOW_TYPE: Domain(
        workflow_type=AOG_WORKFLOW_TYPE,
        display_name=AOG_DISPLAY_NAME,
        workflow_id_prefix=AOG_WORKFLOW_ID_PREFIX,
        orchestrator_name=AOG_ORCHESTRATOR,
        operator_surface="engineering-maintenance",
        phases=(
            Phase("Detect AOG Event", "deterministic"),
            Phase("Check Airworthiness Constraints", "deterministic"),
            Phase("Synthesize Engineering Recovery Options", "agent"),
            Phase("Approve Engineering Recovery", "hitl"),
            Phase("Commit Engineering and Operational Actions", "deterministic"),
            Phase("Verify Recovery State", "deterministic"),
        ),
        hitl_gates=(
            HitlGate(
                "Approve Engineering Recovery",
                "engineering_duty_manager_decision",
                "engineering_duty_manager",
            ),
        ),
        skills=("aog-recovery-ranker",),
        stub=False,
    ),
    SCHED_WORKFLOW_TYPE: Domain(
        workflow_type=SCHED_WORKFLOW_TYPE,
        display_name=SCHED_DISPLAY_NAME,
        workflow_id_prefix=SCHED_WORKFLOW_ID_PREFIX,
        orchestrator_name="AirlineScheduleResilienceOrchestrator",
        operator_surface="network-planning",
        phases=(
            Phase("Detect Schedule Risk Signal", "deterministic"),
            Phase("Assess Network Ripple Effects", "agent"),
            Phase("Synthesize Resilience Options", "agent"),
            Phase("Approve Schedule Adjustment", "hitl"),
            Phase("Commit Schedule Adjustment", "deterministic"),
            Phase("Verify Network Stability", "deterministic"),
        ),
        hitl_gates=(
            HitlGate(
                "Approve Schedule Adjustment",
                "network_operations_director_decision",
                SCHED_HITL_PERSONA,
            ),
        ),
        skills=("schedule-resilience-ranker",),
        stub=False,
    ),
}
