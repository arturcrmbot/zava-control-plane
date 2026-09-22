"""Process-local handle on the installed Zava Bank world."""
from __future__ import annotations

from verticals.banking.worlds.scenario import ZavaBankWorld

_active_banking_world: ZavaBankWorld | None = None


def register_active_banking_world(world: ZavaBankWorld) -> None:
    global _active_banking_world
    if _active_banking_world is not None and _active_banking_world is not world:
        raise RuntimeError("a different active Banking world is already registered")
    _active_banking_world = world


def unregister_active_banking_world(world: ZavaBankWorld) -> None:
    global _active_banking_world
    if _active_banking_world is world:
        _active_banking_world = None


def resolve_active_banking_world() -> ZavaBankWorld:
    if _active_banking_world is None:
        raise RuntimeError("no active Banking world is registered")
    return _active_banking_world
