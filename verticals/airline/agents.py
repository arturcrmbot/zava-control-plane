from __future__ import annotations

from api.shared.agent_contracts import AgentRegistryEntry


AIRLINE_AGENTS: dict[str, AgentRegistryEntry] = {
    "network-impact-assessor": AgentRegistryEntry(
        agent_id="network-impact-assessor",
        description=(
            "Explains the synthetic disruption's effects across the hub network."
        ),
        allowed_tools=("airline_read_disruption_evidence",),
    ),
    "recovery-option-ranker": AgentRegistryEntry(
        agent_id="recovery-option-ranker",
        description=(
            "Ranks deterministically feasible synthetic hub recovery options."
        ),
        allowed_tools=("airline_rank_feasible_recovery_options",),
    ),
    "aog-recovery-ranker": AgentRegistryEntry(
        agent_id="aog-recovery-ranker",
        description=(
            "Ranks deterministically admitted synthetic AOG engineering recovery options."
        ),
        allowed_tools=(
            "airline_read_aog_evidence",
            "airline_rank_admitted_aog_options",
        ),
        reversible_only=True,
        max_value_gbp=200_000.0,
        scope_function="engineering-maintenance",
    ),
    "schedule-resilience-ranker": AgentRegistryEntry(
        agent_id="schedule-resilience-ranker",
        description=(
            "Ranks deterministically admitted synthetic schedule resilience options."
        ),
        allowed_tools=(
            "airline_read_schedule_risk_evidence",
            "airline_rank_admitted_resilience_options",
        ),
        reversible_only=True,
        max_value_gbp=300_000.0,
        scope_function="network-planning",
    ),
}
