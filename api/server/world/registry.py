"""Static world-pack registry — the single place support/telco specifics live.

Each world name resolves to an immutable :class:`WorldPackRegistration` that
knows how to build its scenario, how fast to pace it by default, and which
objective type / command vocabulary it speaks. ``ActorWorldService.for_world``
reads this table; the ``.support()`` / ``.telco()`` classmethods are thin
compatibility wrappers over it. No dynamic discovery — adding a world is one
literal entry here, exactly like adding a scenario branch used to be, but
without spreading the knowledge across ``main.py`` and the bridge.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from api.server.world.packs.support import SupportConfig, SupportScenario
from api.server.world.packs.telco import NetworkConfig, NetworkScenario
from api.server.world.runtime import SimulationRuntime


@dataclass(frozen=True, slots=True)
class WorldPackRegistration:
    """Immutable declaration of one live actor world."""

    name: str
    build_scenario: Callable[[SimulationRuntime], Any]
    default_minutes_per_second: float
    objective_type: str
    allowed_command_types: frozenset[str]


# The exact proven configs that used to live in ActorWorldService.support/telco.
_SUPPORT_CONFIG = SupportConfig(
    customer_count=1_000,
    worker_count=40,
    reserve_worker_count=10,
    arrival_rate_per_hour=90,
    simulation_minutes=480,
    sla_minutes=30,
    sensor_backlog_threshold=25,
    sensor_recovery_threshold=10,
)

# A long horizon keeps the standing session population alive across an
# interactive proof; the deterministic unit config uses a shorter horizon.
_TELCO_CONFIG = NetworkConfig(
    site_count=12,
    subscriber_count=2_000,
    session_count=2_200,
    site_capacity_mbps=600.0,
    simulation_minutes=20_000.0,
)


WORLD_PACKS: dict[str, WorldPackRegistration] = {
    "support": WorldPackRegistration(
        name="support",
        build_scenario=lambda runtime: SupportScenario(runtime, _SUPPORT_CONFIG),
        default_minutes_per_second=10.0,
        objective_type="support_capacity",
        allowed_command_types=frozenset({"reallocate_workers"}),
    ),
    "telco": WorldPackRegistration(
        name="telco",
        build_scenario=lambda runtime: NetworkScenario(runtime, _TELCO_CONFIG),
        default_minutes_per_second=10.0,
        objective_type="network_service_recovery",
        allowed_command_types=frozenset({"reroute_sessions"}),
    ),
}


def resolve_world_pack(name: str) -> WorldPackRegistration:
    """Return the registration for ``name`` or raise ``ValueError`` if unknown."""
    try:
        return WORLD_PACKS[name]
    except KeyError:
        raise ValueError(
            f"unknown world {name!r}; known worlds: {sorted(WORLD_PACKS)}"
        ) from None
