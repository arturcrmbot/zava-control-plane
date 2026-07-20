from __future__ import annotations

from api.shared.world_contracts import (
    ObjectiveRoute,
    ResponderRegistration,
    WorldPackRegistration,
    WorldScaleProfile,
)
from verticals.fashion.process_profiles import FASHION_PROCESS_PROFILES


def build_fashion_demo(runtime):
    from verticals.fashion.world import FashionScenario

    return FashionScenario.demo(runtime)


FASHION_WORLD = WorldPackRegistration(
    name="fashion",
    scales={
        "demo": WorldScaleProfile(
            name="demo",
            build_scenario=build_fashion_demo,
            default_minutes_per_second=60.0,
        ),
    },
    default_scale="demo",
    objective_routes=tuple(
        ObjectiveRoute(
            sensor_id=profile.sensor_id,
            objective_type=profile.objective_type,
            allowed_command_types=frozenset({profile.command_type}),
            success_event_types=frozenset({profile.success_event}),
            failure_event_types=frozenset({"command.rejected"}),
            evaluation_timeout_minutes=120.0,
        )
        for profile in FASHION_PROCESS_PROFILES.values()
    ),
    responders={
        profile.objective_type: ResponderRegistration(
            objective_type=profile.objective_type,
            orchestrator=profile.orchestrator_name,
            workflow_type=profile.workflow_type,
            prefix=profile.workflow_id_prefix.lower(),
            owner_function=profile.function.replace("-", "_"),
            timeout_seconds=900.0,
            observation_key="case",
        )
        for profile in FASHION_PROCESS_PROFILES.values()
    },
)

FASHION_WORLDS = {"fashion": FASHION_WORLD}

