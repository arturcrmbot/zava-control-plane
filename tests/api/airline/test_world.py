from __future__ import annotations

import dataclasses

import pytest

from api.server.world.runtime import SimulationRuntime
from api.shared.world_contracts import validate_world_scene
from verticals.airline.process_profiles import STORY_ID, WORKFLOW_TYPE
from verticals.airline.worlds.diagnostics import build_diagnostic_input
from verticals.airline.worlds.model import Aircraft, Sector
from verticals.airline.worlds.registration import AIRLINE_WORLD
from verticals.airline.worlds.scenario import AirlineWorld


def _world() -> tuple[SimulationRuntime, AirlineWorld]:
    runtime = SimulationRuntime(seed=42)
    world = AirlineWorld(seed=42, runtime=runtime)
    world.install()
    return runtime, world


def test_seed_is_deterministic_and_synthetic() -> None:
    first_runtime, first = _world()
    second_runtime, second = _world()
    assert len(first.aircraft) == 5
    assert len(first.sectors) == 8
    assert len(first.rotations) == 4
    assert len(first.crew_duties) == 6
    assert len(first.slots) == 8
    assert len(first.stands) == 5
    assert len(first.connection_cohorts) == 2
    assert all(record.id.startswith("SYN-") for record in first.aircraft.values())
    assert first.render_state() == second.render_state()
    assert first_runtime.canonical_journal() == second_runtime.canonical_journal()


def test_named_scenario_emits_one_integrated_sensor() -> None:
    runtime, world = _world()
    event = world.activate_scenario("synthetic-hub-cascade")
    sensors = [
        item
        for item in runtime.journal
        if item.type == "sensor.tripped" and item.actor_id == "sensor:integrated_hub_disruption"
    ]
    assert event.type == "airline.hub_disruption.detected"
    assert len(sensors) == 1
    assert sensors[0].payload["workflow_type"] == "integrated-hub-disruption-recovery"
    assert sensors[0].payload["story_id"] == "SYN-STORY-HUB-001"
    assert world.sectors["SYN-SECTOR-IN-001"].delay_minutes == 45
    assert world.stands["SYN-STAND-01"].status == "unavailable"


def test_second_scenario_activation_reuses_source_without_duplicate_sensor() -> None:
    runtime, world = _world()
    first = world.activate_scenario("synthetic-hub-cascade")
    journal_size = len(runtime.journal)

    second = world.activate_scenario("synthetic-hub-cascade")

    assert second is first
    assert len(runtime.journal) == journal_size
    assert (
        sum(
            event.type == "sensor.tripped" and event.actor_id == "sensor:integrated_hub_disruption"
            for event in runtime.journal
        )
        == 1
    )


def test_unknown_scenario_is_rejected_without_mutation() -> None:
    runtime, world = _world()
    before = world.render_state()
    journal_size = len(runtime.journal)

    with pytest.raises(ValueError, match="unsupported Airline scenario"):
        world.activate_scenario("unknown-cascade")

    assert world.render_state() == before
    assert len(runtime.journal) == journal_size


def test_records_are_versioned_journal_backed_and_operationally_linked() -> None:
    runtime, world = _world()
    collections = (
        world.aircraft,
        world.sectors,
        world.rotations,
        world.crew_duties,
        world.slots,
        world.stands,
        world.connection_cohorts,
    )
    event_ids = {event.event_id for event in runtime.journal}

    assert all(
        record.id.startswith("SYN-") and record.version == 1 and record.last_event_id in event_ids
        for records in collections
        for record in records.values()
    )
    sector = world.sectors["SYN-SECTOR-IN-001"]
    assert sector.aircraft_id in world.aircraft
    assert sector.crew_duty_id in world.crew_duties
    assert sector.slot_id in world.slots
    assert sector.stand_id in world.stands

    assert [field.name for field in dataclasses.fields(Aircraft)] == [
        "id",
        "configuration",
        "status",
        "current_station_id",
        "version",
        "last_event_id",
    ]
    assert [field.name for field in dataclasses.fields(Sector)] == [
        "id",
        "origin_id",
        "destination_id",
        "aircraft_id",
        "crew_duty_id",
        "slot_id",
        "stand_id",
        "scheduled_departure",
        "delay_minutes",
        "status",
        "version",
        "last_event_id",
    ]


def test_registration_has_one_route_responder_and_demo_scale() -> None:
    assert AIRLINE_WORLD.name == "airline"
    assert AIRLINE_WORLD.default_scale == "demo"
    assert tuple(AIRLINE_WORLD.scales) == ("demo",)
    assert len(AIRLINE_WORLD.objective_routes) == 1
    assert len(AIRLINE_WORLD.responders) == 1

    route = AIRLINE_WORLD.objective_routes[0]
    responder = next(iter(AIRLINE_WORLD.responders.values()))
    assert route.sensor_id == "sensor:integrated_hub_disruption"
    assert route.objective_type == responder.objective_type
    assert responder.workflow_type == WORKFLOW_TYPE


def test_diagnostic_uses_the_real_scenario_sensor_and_observation() -> None:
    sensor, observation = build_diagnostic_input(WORKFLOW_TYPE)

    assert sensor["type"] == "sensor.tripped"
    assert sensor["actor_id"] == "sensor:integrated_hub_disruption"
    assert sensor["payload"]["story_id"] == STORY_ID
    assert observation["sensor_event_id"] == sensor["event_id"]
    assert observation["source_event_id"] == sensor["cause_event_id"]
    assert observation["sector"]["id"] == "SYN-SECTOR-IN-001"
    assert observation["stand"]["id"] == "SYN-STAND-01"


def test_diagnostic_enriches_a_copy_without_mutating_the_journal_sensor() -> None:
    runtime, world = _world()
    source = world.activate_scenario("synthetic-hub-cascade")
    live_sensor = next(
        event
        for event in runtime.journal
        if event.type == "sensor.tripped" and event.actor_id == "sensor:integrated_hub_disruption"
    )
    live_payload = dict(live_sensor.payload)

    diagnostic_sensor, _ = build_diagnostic_input(WORKFLOW_TYPE)

    assert live_sensor.cause_event_id == source.event_id
    assert live_sensor.trace_id == source.trace_id
    assert "source_sensor_event_id" not in live_sensor.payload
    assert diagnostic_sensor["payload"]["source_sensor_event_id"] == live_sensor.event_id
    assert diagnostic_sensor["payload"] is not live_sensor.payload
    assert live_sensor.payload == live_payload


def test_current_recovery_observation_is_a_public_live_world_surface() -> None:
    _, world = _world()
    world.activate_scenario("synthetic-hub-cascade")

    observation = world.current_recovery_observation()

    assert observation["story_id"] == STORY_ID
    assert observation["evidence_versions"] == {
        actor_id: record.version
        for actor_id, record in {
            **world.aircraft,
            **world.sectors,
            **world.rotations,
            **world.crew_duties,
            **world.slots,
            **world.stands,
            **world.connection_cohorts,
        }.items()
        if actor_id in observation["evidence_versions"]
    }


def test_registered_scene_is_bounded_and_matches_rendered_collections() -> None:
    _, world = _world()
    scene = AIRLINE_WORLD.scene

    assert scene is not None
    assert validate_world_scene(scene) is scene
    assert len(scene["locations"]) == 5
    assert len(scene["layers"]) <= 4
    assert all(location["id"].startswith("SYN-") for location in scene["locations"])
    assert all("Synthetic" in location["label"] for location in scene["locations"])
    assert {layer["state_key"] for layer in scene["layers"]} <= world.render_state().keys()
