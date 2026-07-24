"""Legacy lessons package kept only for shared Mem0 helpers and cadence utilities."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ["build_default_memory"]


def __getattr__(name: str) -> Any:
    if name == "build_default_memory":
        return import_module("api.server.services.lessons.mem0_store").build_default_memory
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
