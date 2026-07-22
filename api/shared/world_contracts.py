from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ObjectiveRoute:
    sensor_id: str
    objective_type: str
    allowed_command_types: frozenset[str]
    success_event_types: frozenset[str]
    failure_event_types: frozenset[str]
    evaluation_timeout_minutes: float


@dataclass(frozen=True, slots=True)
class ResponderRegistration:
    objective_type: str
    orchestrator: str
    workflow_type: str
    prefix: str
    owner_function: str
    timeout_seconds: float
    observation_key: str = "observation"


@dataclass(frozen=True, slots=True)
class WorldScaleProfile:
    name: str
    build_scenario: Callable[[Any], Any]
    default_minutes_per_second: float


@dataclass(frozen=True, slots=True)
class WorldPackRegistration:
    name: str
    scales: Mapping[str, WorldScaleProfile]
    default_scale: str
    objective_routes: tuple[ObjectiveRoute, ...]
    responders: Mapping[str, ResponderRegistration]
    scene: Mapping[str, Any] | None = None


def validate_world_scene(scene: Mapping[str, Any]) -> Mapping[str, Any]:
    if scene.get("schema_version") != 1:
        raise ValueError("world scene schema_version must be 1")

    locations = scene.get("locations")
    if not isinstance(locations, list) or not locations:
        raise ValueError("world scene locations must be a non-empty list")
    location_ids: set[str] = set()
    for location in locations:
        if not isinstance(location, Mapping):
            raise ValueError("world scene locations must contain objects")
        missing = {
            "id",
            "label",
            "kind",
            "x",
            "y",
            "width",
            "height",
        } - set(location)
        if missing:
            raise ValueError(
                f"world scene location missing fields: {sorted(missing)}"
            )
        location_id = str(location["id"])
        if location_id in location_ids:
            raise ValueError(f"world scene duplicate location id {location_id!r}")
        location_ids.add(location_id)

    layers = scene.get("layers")
    if not isinstance(layers, list) or not layers:
        raise ValueError("world scene layers must be a non-empty list")
    layer_keys: set[str] = set()
    for layer in layers:
        if not isinstance(layer, Mapping):
            raise ValueError("world scene layers must contain objects")
        missing = {
            "state_key",
            "kind",
            "label",
            "id_field",
            "location_field",
            "status_field",
            "colour",
        } - set(layer)
        if missing:
            raise ValueError(
                f"world scene layer missing fields: {sorted(missing)}"
            )
        layer_keys.add(str(layer["state_key"]))

    event_mappings = scene.get("event_mappings")
    if not isinstance(event_mappings, list) or not event_mappings:
        raise ValueError("world scene event_mappings must be a non-empty list")
    for mapping in event_mappings:
        if not isinstance(mapping, Mapping):
            raise ValueError("world scene event_mappings must contain objects")
        missing = {"event_type", "layer", "animation"} - set(mapping)
        if missing:
            raise ValueError(
                f"world scene event_mapping missing fields: {sorted(missing)}"
            )
        if str(mapping["layer"]) not in layer_keys:
            raise ValueError(
                f"world scene event_mapping references unknown layer "
                f"{mapping['layer']!r}"
            )

    return scene
