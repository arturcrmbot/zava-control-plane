"""Hospitality golden slice: scenario install, hero run, observation, command."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from api.server.world.model import SimulationCommand
from api.server.world.runtime import SimulationRuntime
from verticals.hospitality.process_profiles import HOSPITALITY_PROCESS_PROFILES
from verticals.hospitality.worlds import (
    HOSPITALITY_WORLD,
    HospitalityScenario,
    build_hospitality_demo,
)

HERO = "hotel-operations-recovery"
BOUNDS = {
    "room_blocks": 24,
    "critical_assets": 18,
    "work_orders": 12,
    "coverage": 12,
    "arrivals": 12,
}


@pytest.fixture()
def scenario() -> HospitalityScenario:
    runtime = SimulationRuntime(seed=20260728)
    built = build_hospitality_demo(runtime)
    built.install()
    return built


def test_scenario_installs_and_renders_a_bounded_scene(
    scenario: HospitalityScenario,
) -> None:
    assert scenario.reference_process_types == tuple(HOSPITALITY_PROCESS_PROFILES)

    state = scenario.render_state()
    scene_layers = {layer["state_key"] for layer in HOSPITALITY_WORLD.scene["layers"]}
    assert scene_layers <= set(state)

    for key, limit in BOUNDS.items():
        assert key in state, f"render_state is missing scene layer {key!r}"
        assert len(state[key]) <= limit, f"{key} exceeds the bounded scene budget"
        for item in state[key]:
            assert item["id"]
            assert item["location_id"] in {
                location["id"] for location in HOSPITALITY_WORLD.scene["locations"]
            }
            assert item["status"]

    # No unbounded room/booking dumps.
    assert len(state["room_blocks"]) == 24
    assert "rooms" not in state
    assert "bookings" not in state

    # A heartbeat generator keeps the shared world service alive without
    # auto-triggering the outage.
    assert scenario.runtime.env.peek() != float("inf")
    assert not any(
        event.type == "hotel.operations-risk.detected"
        for event in scenario.runtime.journal
    )


def test_hero_run_emits_one_sensor_event_from_the_real_outage(
    scenario: HospitalityScenario,
) -> None:
    profile = HOSPITALITY_PROCESS_PROFILES[HERO]

    result = scenario.run_reference_process(HERO)

    tripped = [
        event
        for event in scenario.runtime.journal
        if event.type == "sensor.tripped" and event.actor_id == profile.sensor_id
    ]
    assert len(tripped) == 1
    event = tripped[0]
    assert result["event_id"] == event.event_id
    assert result["trace_id"] == event.trace_id
    assert result["case_id"] == "CASE-HOPREC-001"
    assert event.payload["workflow_type"] == HERO
    assert event.payload["world_event_id"].startswith("EVT-HOSP-")
    assert event.payload["measurements"]["affected_rooms"] == 18
    assert event.payload["measurements"]["arrivals_in_4h"] == 44
    assert event.target_id == "HOTEL-RIVERSIDE-CENTRAL"

    # A repeat run does not fabricate a second outage.
    scenario.run_reference_process(HERO)
    assert (
        len(
            [
                e
                for e in scenario.runtime.journal
                if e.type == "sensor.tripped" and e.actor_id == profile.sensor_id
            ]
        )
        == 1
    )


def test_hero_observation_carries_real_evidence(
    scenario: HospitalityScenario,
) -> None:
    scenario.run_reference_process(HERO)
    profile = HOSPITALITY_PROCESS_PROFILES[HERO]
    sensor_event = next(
        event.to_dict()
        for event in scenario.runtime.journal
        if event.type == "sensor.tripped" and event.actor_id == profile.sensor_id
    )

    observation = scenario.build_observation(sensor_event, now=12.0)

    assert observation["workflow_type"] == HERO
    assert observation["trace_id"] == sensor_event["trace_id"]
    assert observation["event_ids"] == [sensor_event["event_id"]]
    assert "HOTEL-RIVERSIDE-CENTRAL" in observation["actor_ids"]
    assert "ASSET-RIVC-HW-01" in observation["actor_ids"]
    assert observation["as_of_sim_time"] == 12.0
    assert observation["typed_command"] == "hotel.recovery.execute"
    assert observation["mcp_tools"] == ["hospitality_read_hotel_operations"]
    assert observation["policy"]["decision"] == "approval_required"
    assert observation["authority"]["persona"] == "regional_operations_manager"
    assert observation["case"]["id"] == "CASE-HOPREC-001"

    plan = observation["recovery_plan"]
    assert plan["rooms_to_restore"] == 8
    assert plan["relocations"] == 10
    assert plan["shift_moves"] == 2
    assert plan["work_order_id"] == "WO-RIVC-001"
    assert observation["measurements"]["affected_rooms"] == 18


def test_approved_hero_command_mutates_the_live_world_exactly_once(
    scenario: HospitalityScenario,
) -> None:
    scenario.run_reference_process(HERO)
    profile = HOSPITALITY_PROCESS_PROFILES[HERO]
    sensor_event = next(
        event.to_dict()
        for event in scenario.runtime.journal
        if event.type == "sensor.tripped" and event.actor_id == profile.sensor_id
    )
    observation = scenario.build_observation(sensor_event, now=12.0)

    command = SimulationCommand(
        command_id="cmd-HOPREC-0001-hotel-recovery-execute",
        trace_id=observation["trace_id"],
        issued_by=profile.function,
        type=profile.command_type,
        payload={
            "workflow_type": HERO,
            "workflow_id": "HOPREC-0001",
            "approval_decision": "approve",
            "approval_reference": "REF-HOPREC-0001",
            "evidence_digest": "sha256:hero-evidence",
            "skill_outputs": {"hotel-network-recovery-planner": {"phase": "plan"}},
        },
    )

    before = scenario.world.snapshot()
    accepted = scenario.apply_command(command)

    assert accepted.type == profile.success_event
    assert accepted.type == "hotel.recovery.executed"
    assert accepted.payload["workflow_id"] == "HOPREC-0001"
    assert accepted.payload["command_id"] == command.command_id
    assert accepted.payload["measurements"]["rooms_restored"] == 8
    assert accepted.payload["measurements"]["bookings_relocated"] == 10
    assert accepted.payload["measurements"]["shifts_reallocated"] == 2

    after = scenario.world.snapshot()
    restored = sum(
        1
        for room_id, room in after["rooms"].items()
        if before["rooms"][room_id]["status"] == "unavailable"
        and room["status"] != "unavailable"
    )
    assert restored == 8
    relocated = sum(
        1
        for booking_id, booking in after["bookings"].items()
        if booking["hotel_id"] != before["bookings"][booking_id]["hotel_id"]
    )
    assert relocated == 10

    # Idempotent replay: no second mutation, no second success event.
    replay = scenario.apply_command(command)
    assert replay.type == "command.duplicate"
    assert scenario.world.snapshot()["rooms"] == after["rooms"]
    assert (
        len(
            [
                event
                for event in scenario.runtime.journal
                if event.type == profile.success_event
            ]
        )
        == 1
    )


def test_unapproved_hero_command_is_rejected(
    scenario: HospitalityScenario,
) -> None:
    scenario.run_reference_process(HERO)
    profile = HOSPITALITY_PROCESS_PROFILES[HERO]

    rejected = scenario.apply_command(
        SimulationCommand(
            command_id="cmd-HOPREC-9999-hotel-recovery-execute",
            trace_id="hosp-ops-reject",
            issued_by=profile.function,
            type=profile.command_type,
            payload={
                "workflow_type": HERO,
                "workflow_id": "HOPREC-9999",
                "approval_decision": "deny",
                "evidence_digest": "sha256:hero-evidence",
            },
        )
    )

    assert rejected.type == "command.rejected"
    assert rejected.payload["reason"]


@pytest.mark.parametrize(
    "workflow_type",
    [w for w in HOSPITALITY_PROCESS_PROFILES if w != HERO],
)
def test_every_support_process_is_structurally_executable(
    scenario: HospitalityScenario,
    workflow_type: str,
) -> None:
    profile = HOSPITALITY_PROCESS_PROFILES[workflow_type]

    result = scenario.run_reference_process(workflow_type)

    event = next(
        event
        for event in scenario.runtime.journal
        if event.event_id == result["event_id"]
    )
    assert event.type == "sensor.tripped"
    assert event.actor_id == profile.sensor_id
    assert event.payload["diagnostic"] is True

    observation = scenario.build_observation(event.to_dict(), now=5.0)
    assert observation["workflow_type"] == workflow_type
    assert observation["actor_ids"]
    assert observation["typed_command"] == profile.command_type

    applied = scenario.apply_command(
        SimulationCommand(
            command_id=f"cmd-{profile.prefix}-0001",
            trace_id=observation["trace_id"],
            issued_by=profile.function,
            type=profile.command_type,
            payload={
                "workflow_type": workflow_type,
                "workflow_id": f"{profile.prefix.upper()}-0001",
                "approval_decision": "approve",
                "approval_reference": f"REF-{profile.prefix.upper()}-0001",
                "evidence_digest": "sha256:support-evidence",
                "skill_outputs": {profile.skill: {"phase": "assess"}},
            },
        )
    )
    assert applied.type == profile.success_event
