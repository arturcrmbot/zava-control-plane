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
from verticals.airline.aog_constants import (
    AOG_COMMAND_TYPE,
    AOG_FAILURE_EVENT,
    AOG_OBJECTIVE_TYPE,
    AOG_ORCHESTRATOR,
    AOG_SENSOR_ID,
    AOG_SUCCESS_EVENT,
    AOG_WORKFLOW_TYPE,
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
from verticals.airline.schedule_constants import (
    SCHED_COMMAND_TYPE,
    SCHED_FAILURE_EVENT,
    SCHED_OBJECTIVE_TYPE,
    SCHED_SENSOR_ID,
    SCHED_SUCCESS_EVENT,
    SCHED_WORKFLOW_TYPE,
)
from verticals.airline.worlds.diagnostics import build_diagnostic_input
from verticals.airline.worlds.scenario import AirlineWorld

PACK_ROOT = Path(__file__).resolve().parents[1]


def build_airline_demo(runtime: object) -> AirlineWorld:
    world = AirlineWorld(seed=runtime.seed, runtime=runtime)
    world.install()
    return world


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
    ObjectiveRoute(
        sensor_id=AOG_SENSOR_ID,
        objective_type=AOG_OBJECTIVE_TYPE,
        allowed_command_types=frozenset({AOG_COMMAND_TYPE}),
        success_event_types=frozenset({AOG_SUCCESS_EVENT}),
        failure_event_types=frozenset({AOG_FAILURE_EVENT}),
        evaluation_timeout_minutes=120.0,
    ),
    ObjectiveRoute(
        sensor_id=SCHED_SENSOR_ID,
        objective_type=SCHED_OBJECTIVE_TYPE,
        allowed_command_types=frozenset({SCHED_COMMAND_TYPE}),
        success_event_types=frozenset({SCHED_SUCCESS_EVENT}),
        failure_event_types=frozenset({SCHED_FAILURE_EVENT}),
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
    ),
    AOG_OBJECTIVE_TYPE: ResponderRegistration(
        objective_type=AOG_OBJECTIVE_TYPE,
        orchestrator=AOG_ORCHESTRATOR,
        workflow_type=AOG_WORKFLOW_TYPE,
        prefix="aog",
        owner_function="engineering-maintenance",
        timeout_seconds=1200.0,
        lifecycle_start_via_bridge=True,
    ),
    SCHED_OBJECTIVE_TYPE: ResponderRegistration(
        objective_type=SCHED_OBJECTIVE_TYPE,
        orchestrator="AirlineScheduleResilienceOrchestrator",
        workflow_type=SCHED_WORKFLOW_TYPE,
        prefix="sched",
        owner_function="network-planning",
        timeout_seconds=900.0,
        lifecycle_start_via_bridge=True,
    ),
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
