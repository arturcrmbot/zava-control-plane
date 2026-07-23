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
    lifecycle_start_via_bridge: bool = False


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
    build_diagnostic_input: (
        Callable[[str], tuple[dict[str, Any], dict[str, Any]]] | None
    ) = None
