"""Banking pack feature flags, read from the environment."""
from __future__ import annotations

import os

_TRUTHY = {"1", "true", "yes", "on"}


def world_life_enabled() -> bool:
    """People live in the world and decide through Laya (implies screening)."""
    return os.environ.get("BANKING_WORLD_LIFE", "0").strip().lower() in _TRUTHY


def world_screening_enabled() -> bool:
    """Phase 2: payments carry references, the bank screens them, and mule
    investigations open because the world noticed (not on a timer)."""
    return (os.environ.get("BANKING_WORLD_SCREENING", "0").strip().lower() in _TRUTHY
            or world_life_enabled())
