from __future__ import annotations

from api.shared.domain_contracts import Domain, HitlGate, Phase


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
}
