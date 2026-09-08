"""Airline Hero 3 – Preemptive Schedule Resilience (TDD, stage 1).

Covers: seed/reset/scenario/sensor/duplicate/observation; pure options and
every invariant rejection; all four admitted action families including monitor;
atomic mutation and versions/last_event_id; typed causal records/events;
idempotency; tampered/stale/identity/value/action/persona rejection without
partial state; cross-command rejection; no collision with Hero1/AOG IDs.
"""
from __future__ import annotations

import copy
import dataclasses

import pytest

from api.server.world.model import SimulationCommand
from api.server.world.runtime import SimulationRuntime
from verticals.airline.aog_constants import (
    AOG_COMMAND_TYPE,
    AOG_SCENARIO_ID,
    AOG_STORY_ID,
)
from verticals.airline.process_profiles import (
    COMMAND_TYPE as HUB_COMMAND_TYPE,
    SCENARIO_ID as HUB_SCENARIO_ID,
    STORY_ID as HUB_STORY_ID,
)
from verticals.airline.schedule_constants import (
    SCHED_AFFECTED_CREW_IDS,
    SCHED_AFFECTED_SECTOR_IDS,
    SCHED_AFFECTED_SLOT_IDS,
    SCHED_BUFFER_MINUTES,
    SCHED_CANCEL_CREW_ID,
    SCHED_CANCEL_ROTATION_ID,
    SCHED_CANCEL_SECTOR_ID,
    SCHED_COMMAND_TYPE,
    SCHED_DECISION_ID,
    SCHED_FCAST_GROUND_ID,
    SCHED_FCAST_SLOT_ID,
    SCHED_HITL_PERSONA,
    SCHED_ISSUER,
    SCHED_MAX_VALUE_GBP,
    SCHED_RESERVE_AIRCRAFT_ID,
    SCHED_RESERVE_CREW_ID,
    SCHED_RISK_SIGNAL_ID,
    SCHED_SCENARIO_ID,
    SCHED_SENSOR_ID,
    SCHED_SOURCE_EVENT_TYPE,
    SCHED_STORY_ID,
    SCHED_SUCCESS_EVENT,
    SCHED_WORKFLOW_ID,
    SCHED_WORKFLOW_TYPE,
)
from verticals.airline.schedule_constraints import (
    SCHED_OPTION_BUFFER_RETIME,
    SCHED_OPTION_CANCEL_LIMITED,
    SCHED_OPTION_INFEASIBLE,
    SCHED_OPTION_MONITOR_RISK,
    SCHED_OPTION_PREPOSITION,
    SchedFeasibilityResult,
    SchedOption,
    admit_schedule_options,
)
from verticals.airline.worlds.model import (
    ForecastConstraint,
    ScheduleAdjustmentCommand,
    ScheduleResilienceEvaluation,
    ScheduleRiskSignal,
)
from verticals.airline.worlds.scenario import AirlineWorld


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _world() -> tuple[SimulationRuntime, AirlineWorld]:
    runtime = SimulationRuntime(seed=42)
    world = AirlineWorld(seed=42, runtime=runtime)
    world.install()
    return runtime, world


def _activated_world() -> tuple[SimulationRuntime, AirlineWorld]:
    runtime, world = _world()
    world.activate_scenario(SCHED_SCENARIO_ID)
    return runtime, world


def _sched_sensor(runtime: SimulationRuntime) -> dict:
    return next(
        e.to_dict()
        for e in runtime.journal
        if e.type == "sensor.tripped" and e.actor_id == SCHED_SENSOR_ID
    )


def _build_sched_command(
    world: AirlineWorld,
    option_id: str,
    *,
    workflow_id: str = SCHED_WORKFLOW_ID,
    decision_id: str = SCHED_DECISION_ID,
    persona: str = SCHED_HITL_PERSONA,
) -> SimulationCommand:
    return world.command_for_schedule_option(
        option_id=option_id,
        workflow_id=workflow_id,
        decision_id=decision_id,
        persona=persona,
    )


# ---------------------------------------------------------------------------
# 1. World seeding
# ---------------------------------------------------------------------------

class TestSchedWorldSeed:
    def test_world_installs_risk_signal(self) -> None:
        _, world = _world()
        assert SCHED_RISK_SIGNAL_ID in world.schedule_risk_signals
        sig = world.schedule_risk_signals[SCHED_RISK_SIGNAL_ID]
        assert isinstance(sig, ScheduleRiskSignal)
        assert sig.status == "detected"
        assert sig.story_id == SCHED_STORY_ID
        assert sig.confidence == pytest.approx(0.82)
        assert sig.window_start_minutes == 120
        assert sig.window_end_minutes == 240
        assert sig.last_event_id is not None

    def test_world_installs_forecast_constraints(self) -> None:
        _, world = _world()
        assert SCHED_FCAST_SLOT_ID in world.forecast_constraints
        assert SCHED_FCAST_GROUND_ID in world.forecast_constraints
        slot_c = world.forecast_constraints[SCHED_FCAST_SLOT_ID]
        assert isinstance(slot_c, ForecastConstraint)
        assert slot_c.status == "forecast"
        assert slot_c.station_id == "SYN-HUB-01"
        assert "SYN-SECTOR-OUT-003" in slot_c.affected_sector_ids
        assert "SYN-SECTOR-OUT-004" in slot_c.affected_sector_ids

    def test_seed_42_deterministic_reset(self) -> None:
        _, w1 = _world()
        _, w2 = _world()
        sig1 = w1.schedule_risk_signals[SCHED_RISK_SIGNAL_ID]
        sig2 = w2.schedule_risk_signals[SCHED_RISK_SIGNAL_ID]
        assert sig1.last_event_id == sig2.last_event_id

    def test_no_id_collision_with_hub_scenario(self) -> None:
        assert SCHED_SCENARIO_ID != HUB_SCENARIO_ID
        assert SCHED_STORY_ID != HUB_STORY_ID
        assert SCHED_SENSOR_ID != "sensor:integrated_hub_disruption"

    def test_no_id_collision_with_aog_scenario(self) -> None:
        assert SCHED_SCENARIO_ID != AOG_SCENARIO_ID
        assert SCHED_STORY_ID != AOG_STORY_ID
        assert SCHED_WORKFLOW_ID.startswith("AIRSCHED")
        assert not SCHED_WORKFLOW_ID.startswith("AIRHUB")
        assert not SCHED_WORKFLOW_ID.startswith("AOGA")

    def test_hero1_aog_collections_unchanged_after_sched_seed(self) -> None:
        _, world = _world()
        assert "SYN-TAIL-003" in world.aircraft
        assert "SYN-TECH-003" in world.technical_statuses
        assert "SYN-ROTATION-01" in world.rotations
        # No accidental cross-contamination
        assert len(world.schedule_adjustment_commands) == 0
        assert len(world.schedule_resilience_evaluations) == 0


# ---------------------------------------------------------------------------
# 2. Scenario activation
# ---------------------------------------------------------------------------

class TestSchedScenarioActivation:
    def test_activate_emits_source_event(self) -> None:
        runtime, world = _world()
        source = world.activate_scenario(SCHED_SCENARIO_ID)
        assert source.type == SCHED_SOURCE_EVENT_TYPE
        assert source.payload["scenario_id"] == SCHED_SCENARIO_ID
        assert source.payload["story_id"] == SCHED_STORY_ID
        assert source.payload["workflow_id"] == SCHED_WORKFLOW_ID

    def test_activate_emits_sensor_event_same_trace(self) -> None:
        runtime, world = _world()
        source = world.activate_scenario(SCHED_SCENARIO_ID)
        sensor = _sched_sensor(runtime)
        assert sensor["actor_id"] == SCHED_SENSOR_ID
        assert sensor["payload"]["story_id"] == SCHED_STORY_ID
        assert sensor["payload"]["scenario_id"] == SCHED_SCENARIO_ID
        assert sensor["trace_id"] == source.trace_id
        assert sensor["cause_event_id"] == source.event_id

    def test_activate_marks_story_active(self) -> None:
        _, world = _activated_world()
        assert world.sched_story_status.get(SCHED_STORY_ID) == "active"

    def test_activate_versions_risk_signal(self) -> None:
        _, world = _world()
        original_version = world.schedule_risk_signals[SCHED_RISK_SIGNAL_ID].version
        world.activate_scenario(SCHED_SCENARIO_ID)
        sig = world.schedule_risk_signals[SCHED_RISK_SIGNAL_ID]
        assert sig.version == original_version + 1
        assert sig.status == "active"
        assert sig.last_event_id is not None

    def test_activate_versions_forecast_constraints(self) -> None:
        _, world = _world()
        world.activate_scenario(SCHED_SCENARIO_ID)
        for cid in (SCHED_FCAST_SLOT_ID, SCHED_FCAST_GROUND_ID):
            c = world.forecast_constraints[cid]
            assert c.version == 2
            assert c.status == "active"

    def test_duplicate_activation_reuses_source_without_duplicate_sensor(self) -> None:
        """Re-activation is idempotent, matching the Hero 1 contract.

        Both `run_reference_process` and the orchestrator's evidence activity
        activate the scenario, so raising here failed every schedule-resilience
        run mid-flight. See
        test_world.test_second_scenario_activation_reuses_source_without_duplicate_sensor.
        """
        runtime, world = _activated_world()
        first = world.activate_scenario(SCHED_SCENARIO_ID)
        journal_size = len(runtime.journal)

        second = world.activate_scenario(SCHED_SCENARIO_ID)

        assert second is first
        assert len(runtime.journal) == journal_size
        assert (
            sum(
                event.type == "sensor.tripped" and event.actor_id == SCHED_SENSOR_ID
                for event in runtime.journal
            )
            == 1
        )

    def test_activate_hub_aog_unchanged_after_sched_activation(self) -> None:
        _, world = _activated_world()
        # Hub and AOG scenarios not yet activated
        assert HUB_STORY_ID not in world.disruption_status
        assert AOG_STORY_ID not in world.aog_story_status


# ---------------------------------------------------------------------------
# 3. Observation
# ---------------------------------------------------------------------------

class TestSchedObservation:
    def test_observation_fails_before_activation(self) -> None:
        from verticals.airline.worlds.scenario import RecoveryObservationUnavailableError
        _, world = _world()
        with pytest.raises(RecoveryObservationUnavailableError):
            world.current_schedule_observation()

    def test_observation_standard_identity_fields(self) -> None:
        _, world = _activated_world()
        obs = world.current_schedule_observation()
        assert obs["workflow_type"] == SCHED_WORKFLOW_TYPE
        assert obs["workflow_id"] == SCHED_WORKFLOW_ID
        assert obs["story_id"] == SCHED_STORY_ID
        assert obs["scenario_id"] == SCHED_SCENARIO_ID
        assert obs["sched_story_active"] is True
        assert obs["maximum_value_gbp"] == SCHED_MAX_VALUE_GBP

    def test_observation_includes_affected_sectors(self) -> None:
        _, world = _activated_world()
        obs = world.current_schedule_observation()
        affected_ids = {s["id"] for s in obs["affected_sectors"]}
        assert "SYN-SECTOR-OUT-003" in affected_ids
        assert "SYN-SECTOR-OUT-004" in affected_ids

    def test_observation_includes_reserve_resources(self) -> None:
        _, world = _activated_world()
        obs = world.current_schedule_observation()
        assert obs["reserve_aircraft"]["id"] == SCHED_RESERVE_AIRCRAFT_ID
        assert obs["reserve_crew"]["id"] == SCHED_RESERVE_CREW_ID

    def test_observation_includes_evidence_versions(self) -> None:
        _, world = _activated_world()
        obs = world.current_schedule_observation()
        ev = obs["evidence_versions"]
        assert isinstance(ev, dict)
        assert SCHED_RISK_SIGNAL_ID in ev
        for sid in SCHED_AFFECTED_SECTOR_IDS:
            assert sid in ev

    def test_observation_has_forecast_confidence(self) -> None:
        _, world = _activated_world()
        obs = world.current_schedule_observation()
        assert obs["forecast_confidence"] == pytest.approx(0.82)
        assert obs["max_cancellations_permitted"] == 1

    def test_observation_has_no_action_baseline(self) -> None:
        _, world = _activated_world()
        obs = world.current_schedule_observation()
        baseline = obs["no_action_baseline"]
        assert isinstance(baseline, dict)
        assert "predicted_delays" in baseline
        assert "predicted_cancellations" in baseline

    def test_observation_has_sensor_and_source_event_ids(self) -> None:
        _, world = _activated_world()
        obs = world.current_schedule_observation()
        assert obs["sensor_event_id"] is not None
        assert obs["source_event_id"] is not None
        assert obs["trace_id"] is not None


# ---------------------------------------------------------------------------
# 4. Options and invariants
# ---------------------------------------------------------------------------

class TestSchedOptions:
    def _obs(self) -> dict:
        _, world = _activated_world()
        return world.current_schedule_observation()

    def test_buffer_retime_feasible(self) -> None:
        results = admit_schedule_options(self._obs())
        r = next(r for r in results if r.option.option_id == SCHED_OPTION_BUFFER_RETIME)
        assert r.feasible, r.reasons
        assert r.option.value_gbp == pytest.approx(45_000.0)

    def test_preposition_feasible(self) -> None:
        results = admit_schedule_options(self._obs())
        r = next(r for r in results if r.option.option_id == SCHED_OPTION_PREPOSITION)
        assert r.feasible, r.reasons
        assert r.option.value_gbp == pytest.approx(75_000.0)

    def test_cancel_limited_feasible(self) -> None:
        results = admit_schedule_options(self._obs())
        r = next(r for r in results if r.option.option_id == SCHED_OPTION_CANCEL_LIMITED)
        assert r.feasible, r.reasons
        assert r.option.value_gbp == pytest.approx(110_000.0)

    def test_monitor_risk_feasible_zero_cost(self) -> None:
        results = admit_schedule_options(self._obs())
        r = next(r for r in results if r.option.option_id == SCHED_OPTION_MONITOR_RISK)
        assert r.feasible, r.reasons
        assert r.option.value_gbp == pytest.approx(0.0)

    def test_infeasible_option_rejected(self) -> None:
        results = admit_schedule_options(self._obs())
        r = next(r for r in results if r.option.option_id == SCHED_OPTION_INFEASIBLE)
        assert not r.feasible
        assert len(r.reasons) > 0

    def test_story_not_active_blocks_all_non_monitor_options(self) -> None:
        _, world = _world()  # not activated
        # We can't call current_schedule_observation but we can manually build a minimal obs
        obs = {
            "sched_story_active": False,
            "forecast_confidence": 0.82,
            "max_cancellations_permitted": 1,
            "evidence_versions": {},
            "maximum_value_gbp": SCHED_MAX_VALUE_GBP,
            "affected_sectors": [],
            "affected_slots": [],
            "affected_crew": [],
            "affected_aircraft": [],
            "reserve_aircraft": {},
            "reserve_crew": {},
            "risk_signal": {},
            "forecast_constraints": [],
            "sectors": [],
        }
        results = admit_schedule_options(obs)
        for r in results:
            if r.option.option_id != SCHED_OPTION_MONITOR_RISK:
                assert not r.feasible, f"{r.option.option_id} should be infeasible when story inactive"

    def test_stale_evidence_blocks_buffer_retime(self) -> None:
        obs = self._obs()
        # Tamper one version
        tampered = dict(obs)
        ev = dict(obs["evidence_versions"])
        sid = "SYN-SECTOR-OUT-003"
        ev[sid] = ev[sid] + 99
        tampered["evidence_versions"] = ev
        results = admit_schedule_options(tampered)
        r = next(r for r in results if r.option.option_id == SCHED_OPTION_BUFFER_RETIME)
        assert not r.feasible
        assert any("evidence" in reason for reason in r.reasons)

    def test_already_cancelled_sector_blocks_cancel_limited(self) -> None:
        obs = self._obs()
        # Simulate sector already cancelled
        tampered_sectors = [
            dict(s, status="cancelled") if s["id"] == SCHED_CANCEL_SECTOR_ID else s
            for s in obs["affected_sectors"]
        ]
        tampered = dict(obs, affected_sectors=tampered_sectors)
        results = admit_schedule_options(tampered)
        r = next(r for r in results if r.option.option_id == SCHED_OPTION_CANCEL_LIMITED)
        assert not r.feasible

    def test_zero_cancellations_permitted_blocks_cancel_limited(self) -> None:
        obs = self._obs()
        tampered = dict(obs, max_cancellations_permitted=0)
        results = admit_schedule_options(tampered)
        r = next(r for r in results if r.option.option_id == SCHED_OPTION_CANCEL_LIMITED)
        assert not r.feasible

    def test_reserve_aircraft_overlap_blocks_preposition(self) -> None:
        obs = self._obs()
        # Add a sector with reserve aircraft
        fake_sector = {
            "id": "SYN-SECTOR-FAKE-001",
            "aircraft_id": SCHED_RESERVE_AIRCRAFT_ID,
            "status": "scheduled",
        }
        tampered = dict(obs, sectors=list(obs["sectors"]) + [fake_sector])
        results = admit_schedule_options(tampered)
        r = next(r for r in results if r.option.option_id == SCHED_OPTION_PREPOSITION)
        assert not r.feasible
        assert any("overlap" in reason for reason in r.reasons)

    def test_over_cap_value_blocked(self) -> None:
        obs = self._obs()
        tampered = dict(obs, maximum_value_gbp=30_000.0)
        results = admit_schedule_options(tampered)
        # Buffer retime at 45k should be blocked by 30k cap
        r = next(r for r in results if r.option.option_id == SCHED_OPTION_BUFFER_RETIME)
        assert not r.feasible
        assert any("bounded" in reason for reason in r.reasons)


# ---------------------------------------------------------------------------
# 5. Command construction
# ---------------------------------------------------------------------------

class TestSchedCommandConstruction:
    def _activated(self) -> tuple[SimulationRuntime, AirlineWorld]:
        return _activated_world()

    def _cmd(self, option_id: str) -> SimulationCommand:
        _, world = self._activated()
        return _build_sched_command(world, option_id)

    def test_buffer_retime_command_type(self) -> None:
        cmd = self._cmd(SCHED_OPTION_BUFFER_RETIME)
        assert cmd.type == SCHED_COMMAND_TYPE

    def test_preposition_command_workflow_prefix(self) -> None:
        cmd = self._cmd(SCHED_OPTION_PREPOSITION)
        assert cmd.payload["workflow_id"].startswith("AIRSCHED")

    def test_monitor_risk_command_zero_value(self) -> None:
        cmd = self._cmd(SCHED_OPTION_MONITOR_RISK)
        assert cmd.payload["value_gbp"] == pytest.approx(0.0)

    def test_cancel_limited_command_canonical_ids(self) -> None:
        cmd = self._cmd(SCHED_OPTION_CANCEL_LIMITED)
        assert cmd.payload["scenario_id"] == SCHED_SCENARIO_ID
        assert cmd.payload["story_id"] == SCHED_STORY_ID
        assert cmd.payload["persona"] == SCHED_HITL_PERSONA

    def test_infeasible_option_raises_on_command_build(self) -> None:
        _, world = self._activated()
        with pytest.raises(ValueError):
            _build_sched_command(world, SCHED_OPTION_INFEASIBLE)

    def test_command_issuer_is_canonical(self) -> None:
        cmd = self._cmd(SCHED_OPTION_BUFFER_RETIME)
        assert SCHED_ISSUER == "network-planning"
        assert cmd.issued_by == SCHED_ISSUER

    def test_command_value_within_cap(self) -> None:
        for opt in (SCHED_OPTION_BUFFER_RETIME, SCHED_OPTION_PREPOSITION, SCHED_OPTION_CANCEL_LIMITED):
            cmd = self._cmd(opt)
            assert cmd.payload["value_gbp"] <= SCHED_MAX_VALUE_GBP


# ---------------------------------------------------------------------------
# 6. Buffer/retime mutations
# ---------------------------------------------------------------------------

class TestBufferRetimeMutation:
    def _run(self) -> tuple[AirlineWorld, SimulationCommand]:
        _, world = _activated_world()
        cmd = _build_sched_command(world, SCHED_OPTION_BUFFER_RETIME)
        world.apply_command(cmd)
        return world, cmd

    def test_affected_sectors_departure_retimed(self) -> None:
        world, _ = self._run()
        s3 = world.sectors["SYN-SECTOR-OUT-003"]
        s4 = world.sectors["SYN-SECTOR-OUT-004"]
        assert s3.scheduled_departure == pytest.approx(170.0 + SCHED_BUFFER_MINUTES)
        assert s4.scheduled_departure == pytest.approx(180.0 + SCHED_BUFFER_MINUTES)

    def test_affected_slots_updated(self) -> None:
        world, _ = self._run()
        slot7 = world.slots["SYN-SLOT-07"]
        slot8 = world.slots["SYN-SLOT-08"]
        assert slot7.scheduled_time == pytest.approx(170.0 + SCHED_BUFFER_MINUTES)
        assert slot8.scheduled_time == pytest.approx(180.0 + SCHED_BUFFER_MINUTES)

    def test_reserve_resources_unchanged(self) -> None:
        world, _ = self._run()
        assert world.aircraft[SCHED_RESERVE_AIRCRAFT_ID].status == "reserve"
        assert world.crew_duties[SCHED_RESERVE_CREW_ID].status == "reserve"

    def test_sector_versions_incremented(self) -> None:
        world, _ = self._run()
        assert world.sectors["SYN-SECTOR-OUT-003"].version == 2
        assert world.sectors["SYN-SECTOR-OUT-004"].version == 2
        assert world.slots["SYN-SLOT-07"].version == 2
        assert world.slots["SYN-SLOT-08"].version == 2

    def test_last_event_id_stamped(self) -> None:
        world, _ = self._run()
        s3 = world.sectors["SYN-SECTOR-OUT-003"]
        assert s3.last_event_id is not None
        assert s3.last_event_id == world.sectors["SYN-SECTOR-OUT-004"].last_event_id

    def test_typed_command_record_stored(self) -> None:
        world, cmd = self._run()
        assert len(world.schedule_adjustment_commands) == 1
        rec = next(iter(world.schedule_adjustment_commands.values()))
        assert isinstance(rec, ScheduleAdjustmentCommand)
        assert rec.option_id == SCHED_OPTION_BUFFER_RETIME

    def test_evaluation_record_stored(self) -> None:
        world, _ = self._run()
        assert len(world.schedule_resilience_evaluations) == 1
        ev = next(iter(world.schedule_resilience_evaluations.values()))
        assert isinstance(ev, ScheduleResilienceEvaluation)
        assert ev.status == "pass"
        assert ev.selected_action == "buffer_retime"

    def test_story_resolved(self) -> None:
        world, _ = self._run()
        assert world.sched_story_status.get(SCHED_STORY_ID) == "resolved"

    def test_success_event_emitted(self) -> None:
        runtime, world = _activated_world()
        cmd = _build_sched_command(world, SCHED_OPTION_BUFFER_RETIME)
        world.apply_command(cmd)
        success = next(e for e in runtime.journal if e.type == SCHED_SUCCESS_EVENT)
        assert success.payload["option_id"] == SCHED_OPTION_BUFFER_RETIME

    def test_command_accepted_event_emitted(self) -> None:
        runtime, world = _activated_world()
        cmd = _build_sched_command(world, SCHED_OPTION_BUFFER_RETIME)
        world.apply_command(cmd)
        accepted = next(e for e in runtime.journal if e.type == "command.accepted")
        assert accepted.payload["option_id"] == SCHED_OPTION_BUFFER_RETIME


# ---------------------------------------------------------------------------
# 7. Preposition mutations
# ---------------------------------------------------------------------------

class TestPrepositionMutation:
    def _run(self) -> tuple[AirlineWorld, SimulationCommand]:
        _, world = _activated_world()
        cmd = _build_sched_command(world, SCHED_OPTION_PREPOSITION)
        world.apply_command(cmd)
        return world, cmd

    def test_reserve_aircraft_prepositioned(self) -> None:
        world, _ = self._run()
        assert world.aircraft[SCHED_RESERVE_AIRCRAFT_ID].status == "prepositioned"

    def test_reserve_crew_prepositioned(self) -> None:
        world, _ = self._run()
        assert world.crew_duties[SCHED_RESERVE_CREW_ID].status == "prepositioned"

    def test_operational_sectors_unchanged(self) -> None:
        world, _ = self._run()
        for sid in SCHED_AFFECTED_SECTOR_IDS:
            assert world.sectors[sid].status == "scheduled"
            assert world.sectors[sid].version == 1  # not mutated by preposition

    def test_reserve_versions_incremented(self) -> None:
        world, _ = self._run()
        assert world.aircraft[SCHED_RESERVE_AIRCRAFT_ID].version == 2
        assert world.crew_duties[SCHED_RESERVE_CREW_ID].version == 2

    def test_last_event_id_stamped(self) -> None:
        world, _ = self._run()
        ac = world.aircraft[SCHED_RESERVE_AIRCRAFT_ID]
        crew = world.crew_duties[SCHED_RESERVE_CREW_ID]
        assert ac.last_event_id is not None
        assert ac.last_event_id == crew.last_event_id

    def test_evaluation_aircraft_crew_feasibility_restored(self) -> None:
        world, _ = self._run()
        ev = next(iter(world.schedule_resilience_evaluations.values()))
        assert ev.aircraft_feasibility_restored is True
        assert ev.crew_feasibility_restored is True

    def test_story_resolved(self) -> None:
        world, _ = self._run()
        assert world.sched_story_status.get(SCHED_STORY_ID) == "resolved"


# ---------------------------------------------------------------------------
# 8. Cancel limited mutations
# ---------------------------------------------------------------------------

class TestCancelLimitedMutation:
    def _run(self) -> tuple[AirlineWorld, SimulationCommand]:
        _, world = _activated_world()
        cmd = _build_sched_command(world, SCHED_OPTION_CANCEL_LIMITED)
        world.apply_command(cmd)
        return world, cmd

    def test_cancel_sector_cancelled(self) -> None:
        world, _ = self._run()
        assert world.sectors[SCHED_CANCEL_SECTOR_ID].status == "cancelled"

    def test_cancel_rotation_partial(self) -> None:
        world, _ = self._run()
        assert world.rotations[SCHED_CANCEL_ROTATION_ID].status == "partial"

    def test_cancel_crew_duty_adjusted(self) -> None:
        world, _ = self._run()
        crew = world.crew_duties[SCHED_CANCEL_CREW_ID]
        # remaining_duty_minutes should increase (freed)
        assert crew.remaining_duty_minutes > 340  # original = 340

    def test_other_sectors_unchanged(self) -> None:
        world, _ = self._run()
        assert world.sectors["SYN-SECTOR-OUT-003"].status == "scheduled"
        assert world.sectors["SYN-SECTOR-IN-004"].status == "scheduled"

    def test_cancel_sector_version_incremented(self) -> None:
        world, _ = self._run()
        assert world.sectors[SCHED_CANCEL_SECTOR_ID].version == 2
        assert world.rotations[SCHED_CANCEL_ROTATION_ID].version == 2
        assert world.crew_duties[SCHED_CANCEL_CREW_ID].version == 2

    def test_last_event_id_stamped(self) -> None:
        world, _ = self._run()
        s = world.sectors[SCHED_CANCEL_SECTOR_ID]
        r = world.rotations[SCHED_CANCEL_ROTATION_ID]
        c = world.crew_duties[SCHED_CANCEL_CREW_ID]
        assert s.last_event_id is not None
        assert s.last_event_id == r.last_event_id == c.last_event_id

    def test_evaluation_reflects_cancellation(self) -> None:
        world, _ = self._run()
        ev = next(iter(world.schedule_resilience_evaluations.values()))
        assert ev.selected_action == "cancel_limited"
        assert ev.status == "pass"


# ---------------------------------------------------------------------------
# 9. Monitor risk mutations
# ---------------------------------------------------------------------------

class TestMonitorRiskMutation:
    def _run(self) -> tuple[AirlineWorld, SimulationCommand]:
        _, world = _activated_world()
        cmd = _build_sched_command(world, SCHED_OPTION_MONITOR_RISK)
        world.apply_command(cmd)
        return world, cmd

    def test_risk_signal_marked_monitored(self) -> None:
        world, _ = self._run()
        sig = world.schedule_risk_signals[SCHED_RISK_SIGNAL_ID]
        assert sig.status == "monitored"

    def test_no_operational_sector_mutation(self) -> None:
        world, _ = self._run()
        for sid in SCHED_AFFECTED_SECTOR_IDS:
            assert world.sectors[sid].version == 1  # unchanged
        for slid in SCHED_AFFECTED_SLOT_IDS:
            assert world.slots[slid].version == 1
        for cid in SCHED_AFFECTED_CREW_IDS:
            assert world.crew_duties[cid].version == 1

    def test_reserve_resources_unchanged(self) -> None:
        world, _ = self._run()
        assert world.aircraft[SCHED_RESERVE_AIRCRAFT_ID].status == "reserve"
        assert world.crew_duties[SCHED_RESERVE_CREW_ID].status == "reserve"

    def test_command_persisted(self) -> None:
        world, _ = self._run()
        assert len(world.schedule_adjustment_commands) == 1

    def test_evaluation_persisted(self) -> None:
        world, _ = self._run()
        assert len(world.schedule_resilience_evaluations) == 1
        ev = next(iter(world.schedule_resilience_evaluations.values()))
        assert ev.selected_action == "monitor_risk"
        assert ev.synthetic_cost_gbp == pytest.approx(0.0)

    def test_sched_story_monitored(self) -> None:
        world, _ = self._run()
        assert world.sched_story_status.get(SCHED_STORY_ID) == "monitored"

    def test_risk_signal_last_event_stamped(self) -> None:
        world, _ = self._run()
        sig = world.schedule_risk_signals[SCHED_RISK_SIGNAL_ID]
        assert sig.last_event_id is not None
        assert sig.version == 3  # seeded=1, activated=2, monitored=3


# ---------------------------------------------------------------------------
# 10. Idempotency
# ---------------------------------------------------------------------------

class TestSchedIdempotency:
    @pytest.mark.parametrize("option_id", [
        SCHED_OPTION_BUFFER_RETIME,
        SCHED_OPTION_PREPOSITION,
        SCHED_OPTION_CANCEL_LIMITED,
        SCHED_OPTION_MONITOR_RISK,
    ])
    def test_idempotent_replay(self, option_id: str) -> None:
        _, world = _activated_world()
        cmd = _build_sched_command(world, option_id)
        result1 = world.apply_command(cmd)
        result2 = world.apply_command(copy.deepcopy(cmd))
        assert result1.event_id == result2.event_id


# ---------------------------------------------------------------------------
# 11. Rejection without partial state
# ---------------------------------------------------------------------------

class TestSchedRejection:
    def _activated(self) -> AirlineWorld:
        _, world = _activated_world()
        return world

    def _build_valid(self, world: AirlineWorld, option_id: str = SCHED_OPTION_BUFFER_RETIME) -> SimulationCommand:
        return _build_sched_command(world, option_id)

    def _assert_rejected_no_mutation(
        self,
        world: AirlineWorld,
        bad_cmd: SimulationCommand,
        *,
        option_id: str = SCHED_OPTION_BUFFER_RETIME,
    ) -> None:
        """Command must be rejected and no schedule records mutated."""
        event = world.apply_command(bad_cmd)
        assert event.type == "command.rejected"
        # Sectors not mutated
        for sid in SCHED_AFFECTED_SECTOR_IDS:
            assert world.sectors[sid].version == 1
        for slid in SCHED_AFFECTED_SLOT_IDS:
            assert world.slots[slid].version == 1

    def test_wrong_command_type_rejected(self) -> None:
        world = self._activated()
        cmd = self._build_valid(world)
        bad = SimulationCommand(
            command_id=cmd.command_id,
            trace_id=cmd.trace_id,
            issued_by=cmd.issued_by,
            type="airline.commit_wrong_type",
            payload=cmd.payload,
        )
        self._assert_rejected_no_mutation(world, bad)

    def test_wrong_persona_rejected(self) -> None:
        world = self._activated()
        cmd = _build_sched_command(world, SCHED_OPTION_BUFFER_RETIME)
        bad_payload = dict(cmd.payload, persona="duty_operations_manager")
        bad = dataclasses.replace(cmd, payload=bad_payload)
        self._assert_rejected_no_mutation(world, bad)

    def test_wrong_issuer_rejected(self) -> None:
        world = self._activated()
        cmd = _build_sched_command(world, SCHED_OPTION_BUFFER_RETIME)
        bad = dataclasses.replace(cmd, issued_by="unauthorized-actor")
        self._assert_rejected_no_mutation(world, bad)

    def test_wrong_workflow_prefix_rejected(self) -> None:
        world = self._activated()
        cmd = _build_sched_command(world, SCHED_OPTION_BUFFER_RETIME)
        bad_payload = dict(cmd.payload, workflow_id="WRONG-0001")
        bad = dataclasses.replace(cmd, payload=bad_payload)
        self._assert_rejected_no_mutation(world, bad)

    def test_stale_evidence_rejected(self) -> None:
        world = self._activated()
        cmd = _build_sched_command(world, SCHED_OPTION_BUFFER_RETIME)
        ev = dict(cmd.payload["evidence_versions"])
        sid = "SYN-SECTOR-OUT-003"
        ev[sid] = ev[sid] + 99
        bad_payload = dict(cmd.payload, evidence_versions=ev)
        bad = dataclasses.replace(cmd, payload=bad_payload)
        self._assert_rejected_no_mutation(world, bad)

    def test_tampered_value_rejected(self) -> None:
        world = self._activated()
        cmd = _build_sched_command(world, SCHED_OPTION_BUFFER_RETIME)
        bad_payload = dict(cmd.payload, value_gbp=1.0)
        bad = dataclasses.replace(cmd, payload=bad_payload)
        self._assert_rejected_no_mutation(world, bad)

    def test_value_over_cap_rejected(self) -> None:
        world = self._activated()
        cmd = _build_sched_command(world, SCHED_OPTION_BUFFER_RETIME)
        bad_payload = dict(cmd.payload, value_gbp=SCHED_MAX_VALUE_GBP + 1.0)
        bad = dataclasses.replace(cmd, payload=bad_payload)
        self._assert_rejected_no_mutation(world, bad)

    def test_wrong_trace_rejected(self) -> None:
        world = self._activated()
        cmd = _build_sched_command(world, SCHED_OPTION_BUFFER_RETIME)
        bad = dataclasses.replace(cmd, trace_id="wrong-trace-id-xyz")
        self._assert_rejected_no_mutation(world, bad)

    def test_wrong_scenario_rejected(self) -> None:
        world = self._activated()
        cmd = _build_sched_command(world, SCHED_OPTION_BUFFER_RETIME)
        bad_payload = dict(cmd.payload, scenario_id="wrong-scenario")
        bad = dataclasses.replace(cmd, payload=bad_payload)
        self._assert_rejected_no_mutation(world, bad)

    def test_wrong_story_rejected(self) -> None:
        world = self._activated()
        cmd = _build_sched_command(world, SCHED_OPTION_BUFFER_RETIME)
        bad_payload = dict(cmd.payload, story_id="wrong-story")
        bad = dataclasses.replace(cmd, payload=bad_payload)
        self._assert_rejected_no_mutation(world, bad)


# ---------------------------------------------------------------------------
# 12. Cross-command rejection
# ---------------------------------------------------------------------------

class TestSchedCrossCommandRejection:
    def test_hub_command_rejected_by_schedule_handler(self) -> None:
        from verticals.airline.actions.schedule_commands import apply_schedule_adjustment_command
        _, world = _activated_world()
        hub_cmd = SimulationCommand(
            command_id="SYN-HUB-CMD-FAKE",
            trace_id="trace-hub",
            issued_by=SCHED_ISSUER,
            type=HUB_COMMAND_TYPE,
            payload={"option_id": "some-option"},
        )
        event = apply_schedule_adjustment_command(world, hub_cmd)
        assert event.type == "command.rejected"

    def test_aog_command_rejected_by_schedule_handler(self) -> None:
        from verticals.airline.actions.schedule_commands import apply_schedule_adjustment_command
        _, world = _activated_world()
        aog_cmd = SimulationCommand(
            command_id="SYN-AOG-CMD-FAKE",
            trace_id="trace-aog",
            issued_by=SCHED_ISSUER,
            type=AOG_COMMAND_TYPE,
            payload={"option_id": "some-option"},
        )
        event = apply_schedule_adjustment_command(world, aog_cmd)
        assert event.type == "command.rejected"

    def test_sched_command_rejected_by_hub_handler(self) -> None:
        """Schedule command must not be processed by the hub command handler."""
        from verticals.airline.actions.commands import apply_recovery_command
        _, world = _activated_world()
        sched_cmd = SimulationCommand(
            command_id="SYN-SCHED-CMD-FAKE",
            trace_id="trace-sched",
            issued_by=SCHED_ISSUER,
            type=SCHED_COMMAND_TYPE,
            payload={"option_id": "some-option"},
        )
        event = apply_recovery_command(world, sched_cmd)
        assert event.type == "command.rejected"
