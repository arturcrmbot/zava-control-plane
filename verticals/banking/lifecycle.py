"""Bind the installed Zava Bank world to the process that serves it."""
from __future__ import annotations

import atexit
import os
from collections.abc import Sequence
from typing import Any

from api.server.world.runtime import SimulationRuntime
from verticals.banking.fraud_constants import FRAUD_SCENARIO_STANDARD
from verticals.banking.worlds.active import (
    register_active_banking_world,
    unregister_active_banking_world,
)
from verticals.banking.worlds.scenario import ZavaBankWorld

_worker_world: ZavaBankWorld | None = None


def bootstrap(_state: Any) -> None:
    return None


async def start(state: Any) -> Sequence[Any]:
    service = getattr(state, "world_service", None)
    world = getattr(service, "scenario", None)
    if world is None:
        return ()
    if not isinstance(world, ZavaBankWorld):
        raise RuntimeError("Banking lifecycle received a non-Banking active world")
    register_active_banking_world(world)

    def stop() -> None:
        current = getattr(service, "scenario", world)
        if isinstance(current, ZavaBankWorld):
            unregister_active_banking_world(current)
        unregister_active_banking_world(world)

    return (stop,)


def ensure_banking_worker_world() -> ZavaBankWorld:
    """Shadow world for the Azure Functions worker process.

    The Functions host runs in its own process and cannot see the FastAPI
    world, so activities rebuild a deterministic shadow from the same seed.
    """
    global _worker_world
    if os.getenv("FUNCTIONS_WORKER_RUNTIME") != "python":
        raise RuntimeError("Banking worker world is only available in a Functions worker")
    if _worker_world is None:
        seed = int(os.getenv("WORLD_SEED", "42"))
        _worker_world = ZavaBankWorld(seed=seed, runtime=SimulationRuntime(seed))
        _worker_world.install()
        _worker_world.activate_scenario(FRAUD_SCENARIO_STANDARD)
    register_active_banking_world(_worker_world)
    return _worker_world


def shutdown_banking_worker_world() -> None:
    global _worker_world
    if _worker_world is None:
        return
    unregister_active_banking_world(_worker_world)
    _worker_world = None


def reset_banking_worker_world() -> ZavaBankWorld:
    shutdown_banking_worker_world()
    return ensure_banking_worker_world()


atexit.register(shutdown_banking_worker_world)
