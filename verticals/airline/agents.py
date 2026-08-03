from __future__ import annotations

from api.shared.agent_contracts import AgentRegistryEntry


AIRLINE_AGENTS: dict[str, AgentRegistryEntry] = {
    "network-impact-assessor": AgentRegistryEntry(
        agent_id="network-impact-assessor",
        description=(
            "Explains the synthetic disruption's effects across the hub network."
        ),
    ),
    "recovery-option-ranker": AgentRegistryEntry(
        agent_id="recovery-option-ranker",
        description=(
            "Ranks deterministically feasible synthetic hub recovery options."
        ),
    ),
}
