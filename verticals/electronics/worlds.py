from __future__ import annotations

import json
from pathlib import Path

from api.shared.world_contracts import (
    ObjectiveRoute,
    ResponderRegistration,
    WorldPackRegistration,
    WorldScaleProfile,
    validate_world_scene,
)
from verticals.electronics.process_profiles import ELECTRONICS_PROCESS_PROFILES


PACK_ROOT = Path(__file__).resolve().parent


def build_electronics_demo(runtime):
    from verticals.electronics.world import ElectronicsScenario

    return ElectronicsScenario(runtime)


_SCENE = validate_world_scene(
    json.loads((PACK_ROOT / "ui" / "world-scene.json").read_text(encoding="utf-8"))
)

ELECTRONICS_WORLD = WorldPackRegistration(
    name="electronics",
    scales={
        "demo": WorldScaleProfile(
            name="demo",
            build_scenario=build_electronics_demo,
            default_minutes_per_second=12.0,
        )
    },
    default_scale="demo",
    objective_routes=tuple(
        ObjectiveRoute(
            sensor_id=profile.sensor_id,
            objective_type=profile.objective_type,
            allowed_command_types=frozenset({profile.command_type}),
            success_event_types=frozenset({profile.success_event}),
            failure_event_types=frozenset({"command.rejected"}),
            evaluation_timeout_minutes=180.0,
        )
        for profile in ELECTRONICS_PROCESS_PROFILES.values()
    ),
    responders={
        profile.objective_type: ResponderRegistration(
            objective_type=profile.objective_type,
            orchestrator=profile.orchestrator,
            workflow_type=profile.workflow_type,
            prefix=profile.prefix,
            owner_function=profile.function,
            timeout_seconds=900.0,
            observation_key="retail_case",
        )
        for profile in ELECTRONICS_PROCESS_PROFILES.values()
    },
    scene=_SCENE,
)

ELECTRONICS_WORLDS = {"electronics": ELECTRONICS_WORLD}
