from __future__ import annotations

import pytest

from api.server.services.event_bus import EventBus
from api.server.world.registry import (
    resolve_objective_route,
    resolve_world_pack,
)
from api.server.world.service import ActorWorldService
from api.shared.vertical_loader import build_runtime


@pytest.fixture
def agency_runtime(tmp_path):
    return build_runtime(
        {"ZAVA_WORLD": "support"},
        data_root=tmp_path,
    )


@pytest.fixture
def telco_runtime(tmp_path):
    return build_runtime(
        {"ZAVA_VERTICAL": "telco"},
        data_root=tmp_path,
    )


def test_each_vertical_declares_only_its_world(
    agency_runtime,
    telco_runtime,
):
    assert set(agency_runtime.pack.worlds) == {"support"}
    assert set(telco_runtime.pack.worlds) == {"telco"}

    support_route = agency_runtime.pack.worlds["support"].objective_routes[0]
    assert support_route.sensor_id == "sensor:support_pressure"
    assert support_route.objective_type == "support_capacity"
    assert support_route.allowed_command_types == frozenset(
        {"reallocate_workers"}
    )

    telco_route = telco_runtime.pack.worlds["telco"].objective_routes[0]
    assert telco_route.sensor_id == "sensor:network_anomaly"
    assert telco_route.objective_type == "network_service_recovery"
    assert telco_route.allowed_command_types == frozenset(
        {"reroute_sessions"}
    )


def test_resolve_objective_route_rejects_unknown_sensor(telco_runtime):
    with pytest.raises(
        ValueError,
        match="no objective route for sensor 'sensor:unknown'",
    ):
        resolve_objective_route(
            telco_runtime.pack.worlds["telco"],
            "sensor:unknown",
        )


def test_world_resolution_rejects_cross_pack_access(
    agency_runtime,
    telco_runtime,
):
    with pytest.raises(
        ValueError,
        match="world 'telco' is not owned by vertical 'agency'",
    ):
        resolve_world_pack(agency_runtime, "telco")
    with pytest.raises(
        ValueError,
        match="world 'support' is not owned by vertical 'telco'",
    ):
        resolve_world_pack(telco_runtime, "support")


def test_for_runtime_unknown_world_rejects(agency_runtime):
    with pytest.raises(ValueError, match="world 'mystery' is not owned"):
        ActorWorldService.for_runtime(
            agency_runtime,
            world_name="mystery",
            seed=42,
            bus=EventBus(),
        )


def test_for_runtime_support_preserves_compatibility_config(agency_runtime):
    world = ActorWorldService.for_runtime(
        agency_runtime,
        seed=42,
        bus=EventBus(),
        speed=1000,
    )
    assert world.scenario_name == "support"
    assert world.scale_name == "demo"
    assert world.registration is agency_runtime.pack.worlds["support"]
    snapshot = world.snapshot()
    assert len(snapshot["customers"]) == 1_000
    assert len(snapshot["workers"]) == 40
    reserve = [
        worker
        for worker in snapshot["workers"]
        if worker["team_id"] == "TEAM-RESERVE"
    ]
    assert len(reserve) == 10


def test_for_runtime_telco_preserves_compatibility_config(telco_runtime):
    world = ActorWorldService.for_runtime(
        telco_runtime,
        seed=42,
        bus=EventBus(),
        speed=1000,
    )
    assert world.scenario_name == "telco"
    assert world.scale_name == "demo"
    assert world.registration is telco_runtime.pack.worlds["telco"]
    snapshot = world.snapshot()
    assert len(snapshot["sites"]) == 12
    assert len(snapshot["subscribers"]) == 2_000
    assert len(snapshot["sessions"]) == 2_200


def test_for_runtime_speed_defaults_to_scale(agency_runtime):
    world = ActorWorldService.for_runtime(
        agency_runtime,
        seed=42,
        bus=EventBus(),
    )
    scale = agency_runtime.pack.worlds["support"].scales["demo"]
    assert world.minutes_per_second == scale.default_minutes_per_second


@pytest.mark.parametrize(
    "value",
    [0, -1, float("nan"), float("inf"), float("-inf")],
)
def test_for_runtime_rejects_non_positive_or_non_finite_speed(
    agency_runtime,
    value,
):
    with pytest.raises(ValueError):
        ActorWorldService.for_runtime(
            agency_runtime,
            seed=42,
            bus=EventBus(),
            speed=value,
        )
