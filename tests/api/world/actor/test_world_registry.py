"""Registry proof: ActorWorldService.for_world resolves the static world-pack
table, rejects unknown worlds, and keeps the support/telco configs and actors
exactly as the .support()/.telco() compatibility wrappers produced them.
"""
from __future__ import annotations

import pytest

from api.server.services.event_bus import EventBus
from api.server.world.registry import WORLD_PACKS, resolve_world_pack
from api.server.world.service import ActorWorldService


def test_registry_declares_only_support_and_telco():
    assert set(WORLD_PACKS) == {"support", "telco"}
    assert WORLD_PACKS["support"].objective_type == "support_capacity"
    assert WORLD_PACKS["support"].allowed_command_types == frozenset({"reallocate_workers"})
    assert WORLD_PACKS["telco"].objective_type == "network_service_recovery"
    assert WORLD_PACKS["telco"].allowed_command_types == frozenset({"reroute_sessions"})


def test_resolve_unknown_world_rejects():
    with pytest.raises(ValueError, match="unknown world 'mystery'"):
        resolve_world_pack("mystery")


def test_for_world_unknown_rejects():
    with pytest.raises(ValueError, match="unknown world"):
        ActorWorldService.for_world("mystery", seed=42, bus=EventBus())


def test_for_world_support_matches_compatibility_wrapper():
    world = ActorWorldService.for_world("support", seed=42, bus=EventBus(), speed=1000)
    assert world.scenario_name == "support"
    assert world.registration is WORLD_PACKS["support"]
    snapshot = world.snapshot()
    assert len(snapshot["customers"]) == 1_000
    assert len(snapshot["workers"]) == 40
    # reserve_worker_count=10 → WRK-0031..WRK-0040 sit in TEAM-RESERVE
    reserve = [w for w in snapshot["workers"] if w["team_id"] == "TEAM-RESERVE"]
    assert len(reserve) == 10


def test_for_world_telco_matches_compatibility_wrapper():
    world = ActorWorldService.for_world("telco", seed=42, bus=EventBus(), speed=1000)
    assert world.scenario_name == "telco"
    assert world.registration is WORLD_PACKS["telco"]
    snapshot = world.snapshot()
    assert len(snapshot["sites"]) == 12
    assert len(snapshot["subscribers"]) == 2_000
    assert len(snapshot["sessions"]) == 2_200


def test_for_world_speed_defaults_to_registration_when_none():
    world = ActorWorldService.for_world("support", seed=42, bus=EventBus())
    assert world.minutes_per_second == WORLD_PACKS["support"].default_minutes_per_second


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), float("-inf")])
def test_for_world_rejects_non_positive_or_non_finite_speed(value):
    with pytest.raises(ValueError):
        ActorWorldService.for_world("support", seed=42, bus=EventBus(), speed=value)
