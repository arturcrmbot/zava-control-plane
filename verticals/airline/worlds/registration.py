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
from verticals.airline.process_profiles import (
    COMMAND_TYPE,
    FAILURE_EVENT,
    OBJECTIVE_TYPE,
    ORCHESTRATOR,
    SENSOR_ID,
    SUCCESS_EVENT,
    WORKFLOW_TYPE,
)
from verticals.airline.worlds.diagnostics import build_diagnostic_input
from verticals.airline.worlds.scenario import AirlineWorld

PACK_ROOT = Path(__file__).resolve().parents[1]


def build_airline_demo(runtime: object) -> AirlineWorld:
    return AirlineWorld(seed=runtime.seed, runtime=runtime)


_SCENE = validate_world_scene(
    json.loads(
        (PACK_ROOT / "ui" / "world-scene.json").read_text(encoding="utf-8")
    )
)

_ROUTES = (
    ObjectiveRoute(
        sensor_id=SENSOR_ID,
        objective_type=OBJECTIVE_TYPE,
        allowed_command_types=frozenset({COMMAND_TYPE}),
        success_event_types=frozenset({SUCCESS_EVENT}),
        failure_event_types=frozenset({FAILURE_EVENT}),
        evaluation_timeout_minutes=90.0,
    ),
)

_RESPONDERS = {
    OBJECTIVE_TYPE: ResponderRegistration(
        objective_type=OBJECTIVE_TYPE,
        orchestrator=ORCHESTRATOR,
        workflow_type=WORKFLOW_TYPE,
        prefix="ihdr",
        owner_function="operations-control",
        timeout_seconds=900.0,
        lifecycle_start_via_bridge=True,
    )
}

_SCALES = {
    "demo": WorldScaleProfile(
        name="demo",
        build_scenario=build_airline_demo,
        default_minutes_per_second=2.0,
    )
}

AIRLINE_WORLD = WorldPackRegistration(
    name="airline",
    scales=_SCALES,
    default_scale="demo",
    objective_routes=_ROUTES,
    responders=_RESPONDERS,
    build_diagnostic_input=build_diagnostic_input,
    scene=_SCENE,
)

AIRLINE_WORLDS = {"airline": AIRLINE_WORLD}
