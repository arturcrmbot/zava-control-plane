from __future__ import annotations

from verticals.airline.worlds.scenario import AirlineWorld

_active_airline_world: AirlineWorld | None = None


def register_active_airline_world(world: AirlineWorld) -> None:
    global _active_airline_world
    if _active_airline_world is not None and _active_airline_world is not world:
        raise RuntimeError("a different active Airline world is already registered")
    _active_airline_world = world


def unregister_active_airline_world(world: AirlineWorld) -> None:
    global _active_airline_world
    if _active_airline_world is world:
        _active_airline_world = None


def resolve_active_airline_world() -> AirlineWorld:
    if _active_airline_world is None:
        raise RuntimeError("no active Airline world is registered")
    return _active_airline_world
