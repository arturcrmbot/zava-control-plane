from __future__ import annotations

from typing import Any

from api.server.world.runtime import SimulationRuntime
from verticals.airline.aog_constants import (
    AOG_SCENARIO_ID,
    AOG_SENSOR_ID,
    AOG_WORKFLOW_TYPE,
)
from verticals.airline.process_profiles import SCENARIO_ID, SENSOR_ID, WORKFLOW_TYPE
from verticals.airline.schedule_constants import (
    SCHED_SCENARIO_ID,
    SCHED_SENSOR_ID,
    SCHED_WORKFLOW_TYPE,
)
from verticals.airline.worlds.scenario import AirlineWorld


def _build_hub_diagnostic() -> tuple[dict[str, Any], dict[str, Any]]:
    runtime = SimulationRuntime(seed=42)
    world = AirlineWorld(seed=42, runtime=runtime)
    world.install()
    world.activate_scenario(SCENARIO_ID)
    sensor = next(
        event
        for event in runtime.journal
        if event.type == "sensor.tripped" and event.actor_id == SENSOR_ID
    )
    source_sensor_event = sensor.to_dict()
    observation = world.build_observation(source_sensor_event, now=runtime.now)
    diagnostic_sensor_event = {
        **source_sensor_event,
        "payload": {
            **(source_sensor_event.get("payload") or {}),
            "source_sensor_event_id": source_sensor_event["event_id"],
        },
    }
    return diagnostic_sensor_event, observation


def _build_aog_diagnostic() -> tuple[dict[str, Any], dict[str, Any]]:
    runtime = SimulationRuntime(seed=42)
    world = AirlineWorld(seed=42, runtime=runtime)
    world.install()
    world.activate_scenario(AOG_SCENARIO_ID)
    sensor = next(
        event
        for event in runtime.journal
        if event.type == "sensor.tripped" and event.actor_id == AOG_SENSOR_ID
    )
    source_sensor_event = sensor.to_dict()
    observation = world.current_aog_observation()
    diagnostic_sensor_event = {
        **source_sensor_event,
        "payload": {
            **(source_sensor_event.get("payload") or {}),
            "source_sensor_event_id": source_sensor_event["event_id"],
        },
    }
    return diagnostic_sensor_event, observation


def _build_schedule_diagnostic() -> tuple[dict[str, Any], dict[str, Any]]:
    runtime = SimulationRuntime(seed=42)
    world = AirlineWorld(seed=42, runtime=runtime)
    world.install()
    world.activate_scenario(SCHED_SCENARIO_ID)
    sensor = next(
        event
        for event in runtime.journal
        if event.type == "sensor.tripped" and event.actor_id == SCHED_SENSOR_ID
    )
    source_sensor_event = sensor.to_dict()
    observation = world.current_schedule_observation()
    diagnostic_sensor_event = {
        **source_sensor_event,
        "payload": {
            **(source_sensor_event.get("payload") or {}),
            "source_sensor_event_id": source_sensor_event["event_id"],
        },
    }
    return diagnostic_sensor_event, observation


def build_diagnostic_input(
    workflow_type: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if workflow_type == WORKFLOW_TYPE:
        return _build_hub_diagnostic()
    if workflow_type == AOG_WORKFLOW_TYPE:
        return _build_aog_diagnostic()
    if workflow_type == SCHED_WORKFLOW_TYPE:
        return _build_schedule_diagnostic()
    raise ValueError(
        f"unsupported Airline diagnostic workflow: {workflow_type!r}"
    )
