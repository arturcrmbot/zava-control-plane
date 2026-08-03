from __future__ import annotations

import atexit
import os
from collections.abc import Sequence
from typing import Any

from api.server.world.runtime import SimulationRuntime
from verticals.airline.worlds.active import (
    register_active_airline_world,
    unregister_active_airline_world,
)
from verticals.airline.worlds.scenario import AirlineWorld

_worker_world: AirlineWorld | None = None


def bootstrap(_state: Any) -> None:
    return None


async def start(state: Any) -> Sequence[Any]:
    service = getattr(state, "world_service", None)
    world = getattr(service, "scenario", None)
    if world is None:
        return ()
    if not isinstance(world, AirlineWorld):
        raise RuntimeError("Airline lifecycle received a non-Airline active world")
    register_active_airline_world(world)

    def stop() -> None:
        current = getattr(service, "scenario", world)
        if isinstance(current, AirlineWorld):
            unregister_active_airline_world(current)
        unregister_active_airline_world(world)

    return (stop,)


def ensure_airline_worker_world() -> AirlineWorld:
    global _worker_world
    if os.getenv("FUNCTIONS_WORKER_RUNTIME") != "python":
        raise RuntimeError("Airline worker world is only available in a Functions worker")
    if _worker_world is None:
        seed = int(os.getenv("WORLD_SEED", "42"))
        _worker_world = AirlineWorld(
            seed=seed,
            runtime=SimulationRuntime(seed),
        )
        _worker_world.install()
        _worker_world.activate_scenario("synthetic-hub-cascade")
    register_active_airline_world(_worker_world)
    return _worker_world


def shutdown_airline_worker_world() -> None:
    global _worker_world
    if _worker_world is None:
        return
    unregister_active_airline_world(_worker_world)
    _worker_world = None


atexit.register(shutdown_airline_worker_world)
