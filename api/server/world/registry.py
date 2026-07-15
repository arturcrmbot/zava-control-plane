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
class ObjectiveRoute:
    """Static routing and outcome contract for one world sensor."""

    sensor_id: str
    objective_type: str
    allowed_command_types: frozenset[str]
    success_event_types: frozenset[str]
    failure_event_types: frozenset[str]
    evaluation_timeout_minutes: float


@dataclass(frozen=True, slots=True)
class WorldPackRegistration:
    """Immutable declaration of one live actor world."""

    name: str
    build_scenario: Callable[[SimulationRuntime], Any]
    default_minutes_per_second: float
    objective_routes: tuple[ObjectiveRoute, ...]


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
        objective_routes=(
            ObjectiveRoute(
                sensor_id="sensor:support_pressure",
                objective_type="support_capacity",
                allowed_command_types=frozenset({"reallocate_workers"}),
                success_event_types=frozenset({"worker.reallocated"}),
                failure_event_types=frozenset({"ticket.abandoned"}),
                evaluation_timeout_minutes=30.0,
            ),
        ),
    ),
    "telco": WorldPackRegistration(
        name="telco",
        build_scenario=lambda runtime: NetworkScenario(runtime, _TELCO_CONFIG),
        default_minutes_per_second=10.0,
        objective_routes=(
            ObjectiveRoute(
                sensor_id="sensor:network_anomaly",
                objective_type="network_service_recovery",
                allowed_command_types=frozenset({"reroute_sessions"}),
                success_event_types=frozenset({"site.recovered"}),
                failure_event_types=frozenset({"command.rejected"}),
                evaluation_timeout_minutes=30.0,
            ),
            ObjectiveRoute(
                sensor_id="sensor:customer_impact",
                objective_type="proactive_customer_care",
                allowed_command_types=frozenset({"apply_customer_remediation"}),
                success_event_types=frozenset({"care.completed"}),
                failure_event_types=frozenset({"command.rejected"}),
                evaluation_timeout_minutes=60.0,
            ),
            ObjectiveRoute(
                sensor_id="sensor:service_order",
                objective_type="order_to_activate",
                allowed_command_types=frozenset({"activate_service_order"}),
                success_event_types=frozenset({"order.activated"}),
                failure_event_types=frozenset({"command.rejected"}),
                evaluation_timeout_minutes=60.0,
            ),
        ),
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


def resolve_objective_route(
    registration: WorldPackRegistration, sensor_id: str
) -> ObjectiveRoute:
    """Resolve one sensor to its declared objective route."""
    for route in registration.objective_routes:
        if route.sensor_id == sensor_id:
            return route
    raise ValueError(
        f"no objective route for sensor {sensor_id!r} in world {registration.name!r}"
    )
