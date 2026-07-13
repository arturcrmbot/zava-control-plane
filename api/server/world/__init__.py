"""Generic organisational world-simulator engine (spec 2026-07-10).

Industry-agnostic: all nouns come from a WorldPack (see contract.py). Off
unless ZAVA_WORLD names a pack. `maybe_start_world` is the lifespan entry.
"""
from __future__ import annotations

import asyncio
import importlib
import os

from api.server.world.contract import WorldPack
from api.server.world.engine import WorldEngine


def active_world_name() -> str | None:
    return os.getenv("ZAVA_WORLD") or None


def load_pack(name: str) -> WorldPack:
    module = importlib.import_module(f"api.server.world.packs.{name}")
    pack = getattr(module, "PACK", None)
    if not isinstance(pack, WorldPack):
        raise RuntimeError(f"world pack {name!r} does not expose PACK: WorldPack")
    return pack


def maybe_start_world(bus, *, on_engine=None, **run_kwargs) -> "asyncio.Task | None":
    """Start the engine iff ZAVA_WORLD is set; else return None.

    `on_engine`, if given, is called with the WorldEngine before the run loop
    starts — the FastAPI lifespan uses it to stash the handle on app_state so
    the world_bridge and the /api/world routes can reach live state.
    """
    name = active_world_name()
    if not name:
        return None
    engine = WorldEngine(load_pack(name), bus)
    if on_engine is not None:
        on_engine(engine)
    return asyncio.create_task(engine.run(**run_kwargs))
