"""Direct diagnostic input for the hero, used by the replay probe.

The probe must run without the live actor world, so this rebuilds a
deterministic world from the same seed and returns the *real* sensor event
it produced. It never fabricates a sensor reading and never claims a world
mutation.
"""
from __future__ import annotations

from typing import Any

from api.server.world.runtime import SimulationRuntime
from verticals.banking.fraud_constants import (
    FRAUD_SCENARIO_STANDARD,
    FRAUD_SENSOR_ID,
    FRAUD_WORKFLOW_TYPE,
)
from verticals.banking.worlds.scenario import ZavaBankWorld


def _build_fraud_diagnostic() -> tuple[dict[str, Any], dict[str, Any]]:
    runtime = SimulationRuntime(seed=42)
    world = ZavaBankWorld(seed=42, runtime=runtime)
    world.install()
    world.activate_scenario(FRAUD_SCENARIO_STANDARD)
    sensor = next(
        event
        for event in runtime.journal
        if event.type == "sensor.tripped" and event.actor_id == FRAUD_SENSOR_ID
    )
    source_sensor_event = sensor.to_dict()
    observation = world.current_fraud_observation()
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
    if workflow_type == FRAUD_WORKFLOW_TYPE:
        return _build_fraud_diagnostic()
    raise ValueError(f"unsupported Banking diagnostic workflow: {workflow_type!r}")
