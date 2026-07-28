from __future__ import annotations

from typing import Any

from api.server.world.runtime import SimulationRuntime
from verticals.airline.process_profiles import SCENARIO_ID, SENSOR_ID, WORKFLOW_TYPE
from verticals.airline.worlds.scenario import AirlineWorld


def build_diagnostic_input(
    workflow_type: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if workflow_type != WORKFLOW_TYPE:
        raise ValueError(
            f"unsupported Airline diagnostic workflow: {workflow_type!r}"
        )

    runtime = SimulationRuntime(seed=42)
    world = AirlineWorld(seed=42, runtime=runtime)
    world.install()
    world.activate_scenario(SCENARIO_ID)
    sensor = next(
        event
        for event in runtime.journal
        if event.type == "sensor.tripped" and event.actor_id == SENSOR_ID
    )
    sensor_event = sensor.to_dict()
    observation = world.build_observation(sensor_event, now=runtime.now)
    return sensor_event, observation
