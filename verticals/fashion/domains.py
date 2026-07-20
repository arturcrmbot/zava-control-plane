from __future__ import annotations

from api.shared.domain_contracts import Domain, HitlGate, Phase
from verticals.fashion.process_profiles import FASHION_PROCESS_PROFILES


FASHION_DOMAINS = {
    profile.workflow_type: Domain(
        workflow_type=profile.workflow_type,
        display_name=profile.display_name,
        workflow_id_prefix=profile.workflow_id_prefix,
        orchestrator_name=profile.orchestrator_name,
        operator_surface=profile.function,
        phases=tuple(Phase(phase.name, phase.kind) for phase in profile.phases),
        hitl_gates=(
            HitlGate(
                next(
                    phase.name
                    for phase in profile.phases
                    if phase.kind == "hitl"
                ),
                profile.hitl_event,
                profile.hitl_persona,
                wait_probability=0.0,
            ),
        ),
        skills=profile.skills,
        realistic_interval_seconds=86_400,
    )
    for profile in FASHION_PROCESS_PROFILES.values()
}

