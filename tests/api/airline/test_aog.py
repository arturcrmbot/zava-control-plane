"""AOG Engineering Recovery (Hero 2) – focused TDD test suite.

Covers: world seed/reset, scenario causality, duplicate activation,
observation identity, admission invariants, work/spare mutation,
substitution mutation, no aircraft release, version/last_event_id,
causal events, typed records, idempotent replay, stale/tampered
rejection, and cross-handler rejection.
"""
from __future__ import annotations

import copy
import dataclasses

import pytest

from api.server.world.model import SimulationCommand
from api.server.world.runtime import SimulationRuntime
from verticals.airline.aog_constants import (
    AOG_COMMAND_TYPE,
    AOG_ISSUER,
    AOG_SCENARIO_ID,
    AOG_SENSOR_ID,
    AOG_SOURCE_EVENT_TYPE,
    AOG_STORY_ID,
    AOG_WORKFLOW_ID,
    AOG_WORKFLOW_TYPE,
)
from verticals.airline.process_profiles import COMMAND_TYPE as HUB_COMMAND_TYPE
from verticals.airline.process_profiles import SCENARIO_ID as HUB_SCENARIO_ID
from verticals.airline.worlds.model import (
    AogRecoveryCommand,
    AogRecoveryEvaluation,
    ApprovedProvider,
    EngineeringWorkOrder,
    MaintenanceTask,
    Spare,
    SpareMovement,
    TechnicalStatus,
)
from verticals.airline.worlds.scenario import AirlineWorld


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_aog_command_issuer_matches_responder_owner() -> None:
    assert AOG_ISSUER == "engineering-maintenance"

def _world() -> tuple[SimulationRuntime, AirlineWorld]:
    runtime = SimulationRuntime(seed=42)
    world = AirlineWorld(seed=42, runtime=runtime)
    world.install()
    return runtime, world


def _activated_world() -> tuple[SimulationRuntime, AirlineWorld]:
    runtime, world = _world()
    world.activate_scenario(AOG_SCENARIO_ID)
    return runtime, world


def _aog_sensor(runtime: SimulationRuntime) -> dict:
    return next(
        e.to_dict()
        for e in runtime.journal
        if e.type == "sensor.tripped" and e.actor_id == AOG_SENSOR_ID
    )


def _build_aog_command(
    world: AirlineWorld,
    option_id: str,
    *,
    workflow_id: str = AOG_WORKFLOW_ID,
    decision_id: str = "SYN-AOG-DECISION-001",
    persona: str = "engineering_duty_manager",
) -> SimulationCommand:
    return world.command_for_aog_option(
        option_id=option_id,
        workflow_id=workflow_id,
        decision_id=decision_id,
        persona=persona,
    )


# ---------------------------------------------------------------------------
# 1. Deterministic seed / reset
# ---------------------------------------------------------------------------

class TestDeterministicSeed:
    def test_aog_collections_present_after_install(self) -> None:
        _, world = _world()
        assert isinstance(world.technical_statuses, dict)
        assert isinstance(world.maintenance_tasks, dict)
        assert isinstance(world.approved_providers, dict)
        assert isinstance(world.spares, dict)
        assert isinstance(world.engineering_work_orders, dict)
        assert isinstance(world.spare_movements, dict)
        assert isinstance(world.aog_recovery_commands, dict)
        assert isinstance(world.aog_recovery_evaluations, dict)

    def test_seed_42_aog_records_deterministic(self) -> None:
        _, w1 = _world()
        _, w2 = _world()
        assert w1.render_state() == w2.render_state()

    def test_aog_reference_data_has_syn_ids(self) -> None:
        _, world = _world()
        for record in world.technical_statuses.values():
            assert record.id.startswith("SYN-")
        for record in world.maintenance_tasks.values():
            assert record.id.startswith("SYN-")
        for record in world.approved_providers.values():
            assert record.id.startswith("SYN-")
        for record in world.spares.values():
            assert record.id.startswith("SYN-")

    def test_aog_aircraft_substitute_seeded(self) -> None:
        _, world = _world()
        # A320 reserve at hub – the existing SYN-TAIL-005, used as substitute candidate
        sub = world.aircraft["SYN-TAIL-005"]
        assert sub.configuration == "A320"
        assert sub.status == "reserve"
        # SYN-TAIL-006 must NOT exist (removed – only five aircraft in demo world)
        assert "SYN-TAIL-006" not in world.aircraft

    def test_aog_seed_data_present(self) -> None:
        _, world = _world()
        # at least one technical status for tail 003
        tech = [t for t in world.technical_statuses.values() if t.aircraft_id == "SYN-TAIL-003"]
        assert tech
        # at least one maintenance task
        assert world.maintenance_tasks
        # at least one approved provider
        approved = [p for p in world.approved_providers.values() if p.approved]
        assert approved
        # at least one unapproved provider (for infeasible option)
        unapproved = [p for p in world.approved_providers.values() if not p.approved]
        assert unapproved
        # local spare + repositionable spare + untraceable spare
        traceable = [s for s in world.spares.values() if s.traceable]
        untraceable = [s for s in world.spares.values() if not s.traceable]
        assert len(traceable) >= 2
        assert untraceable

    def test_render_state_includes_aog_collections(self) -> None:
        _, world = _world()
        state = world.render_state()
        assert "technical_statuses" in state
        assert "maintenance_tasks" in state
        assert "approved_providers" in state
        assert "spares" in state
        assert "engineering_work_orders" in state
        assert "spare_movements" in state
        assert "aog_recovery_commands" in state
        assert "aog_recovery_evaluations" in state


# ---------------------------------------------------------------------------
# 2. Scenario source + sensor causality / duplicate activation
# ---------------------------------------------------------------------------

class TestAogScenario:
    def test_activate_aog_emits_source_and_sensor(self) -> None:
        runtime, world = _world()
        source = world.activate_scenario(AOG_SCENARIO_ID)
        assert source.type == AOG_SOURCE_EVENT_TYPE
        sensor_events = [
            e for e in runtime.journal
            if e.type == "sensor.tripped" and e.actor_id == AOG_SENSOR_ID
        ]
        assert len(sensor_events) == 1
        sensor = sensor_events[0]
        assert sensor.cause_event_id == source.event_id
        assert sensor.trace_id == source.trace_id

    def test_aog_sensor_payload_has_required_identity(self) -> None:
        runtime, world = _world()
        world.activate_scenario(AOG_SCENARIO_ID)
        sensor = _aog_sensor(runtime)
        payload = sensor["payload"]
        assert payload["workflow_type"] == AOG_WORKFLOW_TYPE
        assert payload["workflow_id"] == AOG_WORKFLOW_ID
        assert payload["story_id"] == AOG_STORY_ID
        assert payload["scenario_id"] == AOG_SCENARIO_ID

    def test_aog_source_event_has_one_trace(self) -> None:
        runtime, world = _world()
        source = world.activate_scenario(AOG_SCENARIO_ID)
        # All events on this trace share the same trace_id
        on_trace = [e for e in runtime.journal if e.trace_id == source.trace_id]
        assert len(on_trace) >= 2  # source + sensor

    def test_duplicate_activation_reuses_source_without_duplicate_sensor(self) -> None:
        """Re-activation is idempotent, matching the Hero 1 contract.

        Both `run_reference_process` and the orchestrator's evidence activity
        activate the scenario, so raising here failed every AOG run mid-flight
        with "AOG scenario 'synthetic-aog-defect' is already active". See
        test_world.test_second_scenario_activation_reuses_source_without_duplicate_sensor.
        """
        runtime, world = _world()
        first = world.activate_scenario(AOG_SCENARIO_ID)
        journal_size = len(runtime.journal)

        second = world.activate_scenario(AOG_SCENARIO_ID)

        assert second is first
        assert len(runtime.journal) == journal_size
        assert (
            sum(
                event.type == "sensor.tripped" and event.actor_id == AOG_SENSOR_ID
                for event in runtime.journal
            )
            == 1
        )

    def test_aog_scenario_marks_tail_003_grounded(self) -> None:
        _, world = _world()
        world.activate_scenario(AOG_SCENARIO_ID)
        tech = next(t for t in world.technical_statuses.values() if t.aircraft_id == "SYN-TAIL-003")
        assert tech.status == "grounded"
        assert world.aircraft["SYN-TAIL-003"].status == "grounded"

    def test_aog_scenario_marks_story_active(self) -> None:
        _, world = _world()
        world.activate_scenario(AOG_SCENARIO_ID)
        assert world.aog_story_status.get(AOG_STORY_ID) == "active"

    def test_aog_activation_writes_version_and_last_event_id(self) -> None:
        runtime, world = _world()
        world.activate_scenario(AOG_SCENARIO_ID)
        event_ids = {e.event_id for e in runtime.journal}
        tail = world.aircraft["SYN-TAIL-003"]
        assert tail.version > 1
        assert tail.last_event_id in event_ids
        tech = next(t for t in world.technical_statuses.values() if t.aircraft_id == "SYN-TAIL-003")
        assert tech.version > 1
        assert tech.last_event_id in event_ids

    def test_hub_scenario_unaffected_by_aog_activation(self) -> None:
        runtime, world = _world()
        world.activate_scenario(HUB_SCENARIO_ID)
        before = len(runtime.journal)
        world.activate_scenario(AOG_SCENARIO_ID)
        # hub disruption sensor still present exactly once
        hub_sensors = [
            e for e in runtime.journal
            if e.type == "sensor.tripped" and e.actor_id == "sensor:integrated_hub_disruption"
        ]
        assert len(hub_sensors) == 1
        # journal grew by at least 2 (source + sensor for AOG)
        assert len(runtime.journal) >= before + 2

    def test_not_installed_world_cannot_activate(self) -> None:
        world = AirlineWorld(seed=42)
        with pytest.raises(RuntimeError):
            world.activate_scenario(AOG_SCENARIO_ID)


# ---------------------------------------------------------------------------
# 3. AOG observation identity / version evidence
# ---------------------------------------------------------------------------

class TestAogObservation:
    def test_observation_unavailable_before_activation(self) -> None:
        _, world = _world()
        with pytest.raises(Exception):
            world.current_aog_observation()

    def test_observation_has_required_identity_fields(self) -> None:
        _, world = _activated_world()
        obs = world.current_aog_observation()
        assert obs["workflow_type"] == AOG_WORKFLOW_TYPE
        assert obs["workflow_id"] == AOG_WORKFLOW_ID
        assert obs["story_id"] == AOG_STORY_ID
        assert obs["scenario_id"] == AOG_SCENARIO_ID
        assert obs["trace_id"]
        assert obs["sensor_event_id"]
        assert obs["source_event_id"]

    def test_observation_has_affected_records(self) -> None:
        _, world = _activated_world()
        obs = world.current_aog_observation()
        assert obs["affected_tail_id"] == "SYN-TAIL-003"
        assert obs["rotation_id"] == "SYN-ROTATION-03"
        assert obs["technical_status"]
        assert obs["maintenance_task"]
        assert obs["approved_providers"]
        assert obs["spares"]
        assert obs["substitute_candidate"]

    def test_observation_has_evidence_versions(self) -> None:
        _, world = _activated_world()
        obs = world.current_aog_observation()
        versions = obs["evidence_versions"]
        assert isinstance(versions, dict)
        # must include the grounded tail and its technical status
        assert "SYN-TAIL-003" in versions
        assert any(k.startswith("SYN-TECH-") for k in versions)

    def test_observation_has_evidence_event_ids(self) -> None:
        _, world = _activated_world()
        obs = world.current_aog_observation()
        assert isinstance(obs["evidence_event_ids"], list)
        assert len(obs["evidence_event_ids"]) >= 2

    def test_observation_has_no_action_baseline(self) -> None:
        _, world = _activated_world()
        obs = world.current_aog_observation()
        assert isinstance(obs["no_action_baseline"], dict)

    def test_observation_has_maximum_value(self) -> None:
        _, world = _activated_world()
        obs = world.current_aog_observation()
        assert isinstance(obs["maximum_value_gbp"], (int, float))
        assert obs["maximum_value_gbp"] > 0

    def test_observation_maximum_value_is_200k(self) -> None:
        _, world = _activated_world()
        obs = world.current_aog_observation()
        assert obs["maximum_value_gbp"] == 200_000.0

    def test_observation_versions_match_current_world_records(self) -> None:
        _, world = _activated_world()
        obs = world.current_aog_observation()
        versions = obs["evidence_versions"]
        tail = world.aircraft["SYN-TAIL-003"]
        assert versions.get(tail.id) == tail.version


# ---------------------------------------------------------------------------
# 4. Pure admission / fail-closed invariants
# ---------------------------------------------------------------------------

class TestAogAdmission:
    def test_admission_returns_feasibility_results(self) -> None:
        from verticals.airline.aog_constraints import admit_aog_options
        _, world = _activated_world()
        obs = world.current_aog_observation()
        results = admit_aog_options(obs)
        assert isinstance(results, tuple)
        assert len(results) >= 3

    def test_at_least_two_feasible_options(self) -> None:
        from verticals.airline.aog_constraints import admit_aog_options
        _, world = _activated_world()
        obs = world.current_aog_observation()
        feasible = [r for r in admit_aog_options(obs) if r.feasible]
        assert len(feasible) >= 2

    def test_infeasible_option_present(self) -> None:
        from verticals.airline.aog_constraints import admit_aog_options
        _, world = _activated_world()
        obs = world.current_aog_observation()
        infeasible = [r for r in admit_aog_options(obs) if not r.feasible]
        assert infeasible
        # infeasible result has a reason
        assert all(r.reasons for r in infeasible)

    def test_work_local_spare_option_feasible(self) -> None:
        from verticals.airline.aog_constraints import (
            AOG_OPTION_WORK_LOCAL,
            admit_aog_options,
        )
        _, world = _activated_world()
        obs = world.current_aog_observation()
        result = next(r for r in admit_aog_options(obs) if r.option.option_id == AOG_OPTION_WORK_LOCAL)
        assert result.feasible, result.reasons

    def test_work_repo_spare_option_feasible(self) -> None:
        from verticals.airline.aog_constraints import (
            AOG_OPTION_WORK_REPO,
            admit_aog_options,
        )
        _, world = _activated_world()
        obs = world.current_aog_observation()
        result = next(r for r in admit_aog_options(obs) if r.option.option_id == AOG_OPTION_WORK_REPO)
        assert result.feasible, result.reasons

    def test_substitute_option_feasible(self) -> None:
        from verticals.airline.aog_constraints import (
            AOG_OPTION_SUBSTITUTE,
            admit_aog_options,
        )
        _, world = _activated_world()
        obs = world.current_aog_observation()
        result = next(r for r in admit_aog_options(obs) if r.option.option_id == AOG_OPTION_SUBSTITUTE)
        assert result.feasible, result.reasons

    def test_infeasible_option_rejected_with_reason(self) -> None:
        from verticals.airline.aog_constraints import (
            AOG_OPTION_UNAPPROVED,
            admit_aog_options,
        )
        _, world = _activated_world()
        obs = world.current_aog_observation()
        result = next(r for r in admit_aog_options(obs) if r.option.option_id == AOG_OPTION_UNAPPROVED)
        assert not result.feasible
        assert result.reasons

    def test_stale_evidence_versions_rejected(self) -> None:
        from verticals.airline.aog_constraints import admit_aog_options
        _, world = _activated_world()
        obs = world.current_aog_observation()
        tampered = dict(obs)
        versions = dict(obs["evidence_versions"])
        # bump one version to make it stale
        key = next(iter(versions))
        versions[key] = versions[key] + 99
        tampered["evidence_versions"] = versions
        for result in admit_aog_options(tampered):
            if result.feasible:
                # any previously feasible option should now fail evidence check
                assert "evidence versions" in result.reasons

    def test_no_action_without_activation(self) -> None:
        from verticals.airline.aog_constraints import admit_aog_options
        _, world = _world()
        obs = {
            "workflow_type": AOG_WORKFLOW_TYPE,
            "story_id": AOG_STORY_ID,
            "evidence_versions": {},
            "maximum_value_gbp": 200_000.0,
            "aog_story_active": False,
        }
        for result in admit_aog_options(obs):
            assert not result.feasible


# ---------------------------------------------------------------------------
# 5. Work order + spare mutation
# ---------------------------------------------------------------------------

class TestWorkOrderMutation:
    def _apply_work_option(self, option_id: str) -> tuple[AirlineWorld, dict]:
        from verticals.airline.aog_constraints import admit_aog_options
        runtime, world = _activated_world()
        obs = world.current_aog_observation()
        result = next(r for r in admit_aog_options(obs) if r.option.option_id == option_id)
        assert result.feasible
        cmd = _build_aog_command(world, option_id)
        accepted_event = world.apply_command(cmd)
        return world, accepted_event.to_dict()

    def test_work_local_creates_engineering_work_order(self) -> None:
        from verticals.airline.aog_constraints import AOG_OPTION_WORK_LOCAL
        world, _ = self._apply_work_option(AOG_OPTION_WORK_LOCAL)
        assert world.engineering_work_orders

    def test_work_local_creates_spare_movement(self) -> None:
        from verticals.airline.aog_constraints import AOG_OPTION_WORK_LOCAL
        world, _ = self._apply_work_option(AOG_OPTION_WORK_LOCAL)
        assert world.spare_movements

    def test_work_local_reserves_spare(self) -> None:
        from verticals.airline.aog_constraints import AOG_OPTION_WORK_LOCAL
        world, _ = self._apply_work_option(AOG_OPTION_WORK_LOCAL)
        reserved = [s for s in world.spares.values() if s.status == "reserved"]
        assert reserved

    def test_work_local_technical_status_work_in_progress(self) -> None:
        from verticals.airline.aog_constraints import AOG_OPTION_WORK_LOCAL
        world, _ = self._apply_work_option(AOG_OPTION_WORK_LOCAL)
        tech = next(t for t in world.technical_statuses.values() if t.aircraft_id == "SYN-TAIL-003")
        assert tech.status == "work_in_progress"

    def test_work_local_tail_003_still_grounded(self) -> None:
        from verticals.airline.aog_constraints import AOG_OPTION_WORK_LOCAL
        world, _ = self._apply_work_option(AOG_OPTION_WORK_LOCAL)
        # aircraft must NOT be released
        assert world.aircraft["SYN-TAIL-003"].status in {"grounded", "work_in_progress"}

    def test_work_local_no_aircraft_release(self) -> None:
        from verticals.airline.aog_constraints import AOG_OPTION_WORK_LOCAL
        world, _ = self._apply_work_option(AOG_OPTION_WORK_LOCAL)
        evals = list(world.aog_recovery_evaluations.values())
        assert evals
        assert evals[0].aircraft_released_by_ai is False

    def test_work_repo_creates_spare_movement_from_hub(self) -> None:
        from verticals.airline.aog_constraints import AOG_OPTION_WORK_REPO
        world, _ = self._apply_work_option(AOG_OPTION_WORK_REPO)
        movements = list(world.spare_movements.values())
        assert movements
        # movement should come from HUB (repositionable spare)
        from verticals.airline.worlds.reference_data import HUB_ID
        assert any(m.from_station_id == HUB_ID for m in movements)

    def test_spare_movement_destination_follows_affected_aircraft_station(self) -> None:
        from verticals.airline.aog_constants import AOG_AFFECTED_TAIL_ID
        from verticals.airline.aog_constraints import AOG_OPTION_WORK_LOCAL
        world, _ = self._apply_work_option(AOG_OPTION_WORK_LOCAL)
        movements = list(world.spare_movements.values())
        assert movements, "spare movement must be created"
        aircraft = world.aircraft[AOG_AFFECTED_TAIL_ID]
        movement = movements[0]
        assert movement.to_station_id == aircraft.current_station_id, (
            f"spare movement destination must follow affected aircraft station: "
            f"expected {aircraft.current_station_id!r}, got {movement.to_station_id!r}"
        )
        assert movement.to_station_id is not None, (
            "to_station_id must not be None (cannot silently become empty)"
        )


# ---------------------------------------------------------------------------
# 6. Substitution mutation
# ---------------------------------------------------------------------------

class TestSubstituteMutation:
    def _apply_substitute(self) -> tuple[AirlineWorld, dict]:
        from verticals.airline.aog_constraints import AOG_OPTION_SUBSTITUTE
        runtime, world = _activated_world()
        cmd = _build_aog_command(world, AOG_OPTION_SUBSTITUTE)
        event = world.apply_command(cmd)
        return world, event.to_dict()

    def test_substitute_assigns_tail005_to_outbound_sector(self) -> None:
        world, _ = self._apply_substitute()
        sector = world.sectors["SYN-SECTOR-OUT-003"]
        assert sector.aircraft_id == "SYN-TAIL-005"

    def test_substitute_keeps_tail003_grounded(self) -> None:
        world, _ = self._apply_substitute()
        assert world.aircraft["SYN-TAIL-003"].status == "grounded"

    def test_substitute_technical_status_unchanged(self) -> None:
        world, _ = self._apply_substitute()
        tech = next(t for t in world.technical_statuses.values() if t.aircraft_id == "SYN-TAIL-003")
        # still grounded – not released to service
        assert tech.status in {"grounded"}

    def test_substitute_creates_engineering_coordination_record(self) -> None:
        world, _ = self._apply_substitute()
        # coordination record for grounded tail should exist
        wo = [w for w in world.engineering_work_orders.values() if w.spare_id is None]
        assert wo

    def test_substitute_no_aircraft_release(self) -> None:
        world, _ = self._apply_substitute()
        evals = list(world.aog_recovery_evaluations.values())
        assert evals
        assert evals[0].aircraft_released_by_ai is False

    def test_substitute_evaluation_records_sectors_protected(self) -> None:
        world, _ = self._apply_substitute()
        evals = list(world.aog_recovery_evaluations.values())
        assert evals[0].sectors_protected >= 1


# ---------------------------------------------------------------------------
# 7. Record versioning / last_event_id causal stamping
# ---------------------------------------------------------------------------

class TestVersioning:
    def test_work_order_versions_all_mutated_records(self) -> None:
        from verticals.airline.aog_constraints import AOG_OPTION_WORK_LOCAL
        runtime, world = _activated_world()
        baseline_tail_version = world.aircraft["SYN-TAIL-003"].version
        cmd = _build_aog_command(world, AOG_OPTION_WORK_LOCAL)
        world.apply_command(cmd)
        # tech status versioned
        tech = next(t for t in world.technical_statuses.values() if t.aircraft_id == "SYN-TAIL-003")
        assert tech.version > 1
        # spare versioned
        reserved = [s for s in world.spares.values() if s.status == "reserved"]
        assert all(s.version > 1 for s in reserved)

    def test_last_event_id_stamps_mutated_records(self) -> None:
        from verticals.airline.aog_constraints import AOG_OPTION_WORK_LOCAL
        runtime, world = _activated_world()
        cmd = _build_aog_command(world, AOG_OPTION_WORK_LOCAL)
        world.apply_command(cmd)
        event_ids = {e.event_id for e in runtime.journal}
        tech = next(t for t in world.technical_statuses.values() if t.aircraft_id == "SYN-TAIL-003")
        assert tech.last_event_id in event_ids
        aog_cmd = list(world.aog_recovery_commands.values())[0]
        assert aog_cmd.last_event_id in event_ids
        aog_eval = list(world.aog_recovery_evaluations.values())[0]
        assert aog_eval.last_event_id in event_ids

    def test_typed_command_and_evaluation_records_stored(self) -> None:
        from verticals.airline.aog_constraints import AOG_OPTION_WORK_LOCAL
        _, world = _activated_world()
        cmd = _build_aog_command(world, AOG_OPTION_WORK_LOCAL)
        world.apply_command(cmd)
        assert world.aog_recovery_commands
        assert world.aog_recovery_evaluations
        cmd_rec = list(world.aog_recovery_commands.values())[0]
        eval_rec = list(world.aog_recovery_evaluations.values())[0]
        assert isinstance(cmd_rec, AogRecoveryCommand)
        assert isinstance(eval_rec, AogRecoveryEvaluation)


# ---------------------------------------------------------------------------
# 8. Causal events
# ---------------------------------------------------------------------------

class TestCausalEvents:
    def test_recovery_applied_then_command_accepted(self) -> None:
        from verticals.airline.aog_constants import AOG_SUCCESS_EVENT
        from verticals.airline.aog_constraints import AOG_OPTION_WORK_LOCAL
        runtime, world = _activated_world()
        cmd = _build_aog_command(world, AOG_OPTION_WORK_LOCAL)
        accepted = world.apply_command(cmd)
        assert accepted.type == "command.accepted"
        applied = next(
            e for e in runtime.journal if e.type == AOG_SUCCESS_EVENT
        )
        assert accepted.cause_event_id == applied.event_id

    def test_recovery_applied_event_on_sensor_trace(self) -> None:
        from verticals.airline.aog_constants import AOG_SUCCESS_EVENT
        from verticals.airline.aog_constraints import AOG_OPTION_WORK_LOCAL
        runtime, world = _activated_world()
        obs = world.current_aog_observation()
        cmd = _build_aog_command(world, AOG_OPTION_WORK_LOCAL)
        world.apply_command(cmd)
        applied = next(e for e in runtime.journal if e.type == AOG_SUCCESS_EVENT)
        assert applied.trace_id == obs["trace_id"]


# ---------------------------------------------------------------------------
# 9. Idempotent replay
# ---------------------------------------------------------------------------

class TestIdempotentReplay:
    def test_replay_same_command_returns_same_event(self) -> None:
        from verticals.airline.aog_constraints import AOG_OPTION_WORK_LOCAL
        runtime, world = _activated_world()
        cmd = _build_aog_command(world, AOG_OPTION_WORK_LOCAL)
        result1 = world.apply_command(cmd)
        journal_size = len(runtime.journal)
        result2 = world.apply_command(cmd)
        assert result2 == result1
        assert len(runtime.journal) == journal_size  # no new events

    def test_replay_does_not_change_state(self) -> None:
        from verticals.airline.aog_constraints import AOG_OPTION_WORK_LOCAL
        _, world = _activated_world()
        cmd = _build_aog_command(world, AOG_OPTION_WORK_LOCAL)
        world.apply_command(cmd)
        state_after_first = world.render_state()
        world.apply_command(cmd)
        assert world.render_state() == state_after_first

    def test_replay_does_not_duplicate_spare_reservation(self) -> None:
        from verticals.airline.aog_constraints import AOG_OPTION_WORK_LOCAL
        _, world = _activated_world()
        cmd = _build_aog_command(world, AOG_OPTION_WORK_LOCAL)
        world.apply_command(cmd)
        world.apply_command(cmd)
        reserved = [s for s in world.spares.values() if s.status == "reserved"]
        # exactly the spare chosen – not duplicated
        assert len(reserved) == 1


# ---------------------------------------------------------------------------
# 10. Stale / tampered rejection without partial mutation
# ---------------------------------------------------------------------------

class TestTamperedRejection:
    def test_wrong_persona_rejected(self) -> None:
        """Stage-1: exact persona check – 'duty_operations_manager' is not the AOG persona."""
        from verticals.airline.aog_constraints import AOG_OPTION_WORK_LOCAL
        _, world = _activated_world()
        cmd = _build_aog_command(world, AOG_OPTION_WORK_LOCAL, persona="duty_operations_manager")
        event = world.apply_command(cmd)
        assert event.type == "command.rejected"
        assert not world.aog_recovery_commands

    def test_value_exceeding_aog_max_rejected(self) -> None:
        """Value must not exceed AOG_MAX_VALUE_GBP = 200,000."""
        from verticals.airline.aog_constraints import AOG_OPTION_WORK_LOCAL
        _, world = _activated_world()
        cmd = _build_aog_command(world, AOG_OPTION_WORK_LOCAL)
        bad_payload = dict(cmd.payload)
        bad_payload["value_gbp"] = 200_001.0
        tampered = SimulationCommand(
            command_id=cmd.command_id + "-xcap",
            trace_id=cmd.trace_id,
            issued_by=cmd.issued_by,
            type=cmd.type,
            payload=bad_payload,
        )
        event = world.apply_command(tampered)
        assert event.type == "command.rejected"
        assert not world.engineering_work_orders

    def test_wrong_command_type_rejected(self) -> None:
        from verticals.airline.aog_constraints import AOG_OPTION_WORK_LOCAL
        _, world = _activated_world()
        cmd = _build_aog_command(world, AOG_OPTION_WORK_LOCAL)
        tampered = SimulationCommand(
            command_id=cmd.command_id,
            trace_id=cmd.trace_id,
            issued_by=cmd.issued_by,
            type="airline.commit_recovery_plan",  # Hero 1 type
            payload=cmd.payload,
        )
        event = world.apply_command(tampered)
        assert event.type == "command.rejected"
        assert not world.aog_recovery_commands

    def test_stale_evidence_versions_in_command_rejected(self) -> None:
        from verticals.airline.aog_constraints import AOG_OPTION_WORK_LOCAL
        _, world = _activated_world()
        cmd = _build_aog_command(world, AOG_OPTION_WORK_LOCAL)
        bad_payload = dict(cmd.payload)
        versions = dict(cmd.payload["evidence_versions"])
        key = next(iter(versions))
        versions[key] = versions[key] + 99
        bad_payload["evidence_versions"] = versions
        tampered = SimulationCommand(
            command_id=cmd.command_id,
            trace_id=cmd.trace_id,
            issued_by=cmd.issued_by,
            type=cmd.type,
            payload=bad_payload,
        )
        event = world.apply_command(tampered)
        assert event.type == "command.rejected"

    def test_tampered_value_rejected_no_partial_mutation(self) -> None:
        from verticals.airline.aog_constraints import AOG_OPTION_WORK_LOCAL
        _, world = _activated_world()
        cmd = _build_aog_command(world, AOG_OPTION_WORK_LOCAL)
        bad_payload = dict(cmd.payload)
        bad_payload["value_gbp"] = 9_999_999.0
        tampered = SimulationCommand(
            command_id=cmd.command_id + "-tampered",
            trace_id=cmd.trace_id,
            issued_by=cmd.issued_by,
            type=cmd.type,
            payload=bad_payload,
        )
        event = world.apply_command(tampered)
        assert event.type == "command.rejected"
        # no work order created
        assert not world.engineering_work_orders

    def test_unknown_option_rejected(self) -> None:
        _, world = _activated_world()
        obs = world.current_aog_observation()
        from verticals.airline.actions.aog_commands import aog_recovery_command_id
        cmd = SimulationCommand(
            command_id=aog_recovery_command_id(
                workflow_id=AOG_WORKFLOW_ID,
                decision_id="SYN-AOG-DECISION-001",
                option_id="SYN-AOG-OPTION-UNKNOWN",
            ),
            trace_id=str(obs["trace_id"]),
            issued_by="operations-control",
            type=AOG_COMMAND_TYPE,
            payload={
                "workflow_id": AOG_WORKFLOW_ID,
                "decision_id": "SYN-AOG-DECISION-001",
                "option_id": "SYN-AOG-OPTION-UNKNOWN",
                "story_id": AOG_STORY_ID,
                "scenario_id": AOG_SCENARIO_ID,
                "persona": "duty_operations_manager",
                "value_gbp": 10_000.0,
                "evidence_versions": obs["evidence_versions"],
                "actions": [],
                "objective_id": f"SYN-AOG-OBJECTIVE-{AOG_WORKFLOW_ID}",
            },
        )
        event = world.apply_command(cmd)
        assert event.type == "command.rejected"


# ---------------------------------------------------------------------------
# 11. Cross-handler rejection
# ---------------------------------------------------------------------------

class TestCrossHandlerRejection:
    def test_hero1_handler_rejects_aog_command(self) -> None:
        """Hero 1 apply_recovery_command must reject an AOG command type."""
        from verticals.airline.actions.commands import apply_recovery_command
        from verticals.airline.aog_constraints import AOG_OPTION_WORK_LOCAL
        runtime, world = _activated_world()
        # Also activate hub disruption so Hero 1 handler is in right state
        world.activate_scenario("synthetic-hub-cascade")
        cmd = _build_aog_command(world, AOG_OPTION_WORK_LOCAL)
        # Hero 1 handler should reject the AOG command type
        event = apply_recovery_command(world, cmd)
        assert event.type == "command.rejected"

    def test_aog_handler_rejects_hero1_command(self) -> None:
        """AOG apply_aog_recovery_command must reject a Hero 1 command type."""
        from verticals.airline.actions.aog_commands import apply_aog_recovery_command
        from verticals.airline.process_profiles import (
            GOLDEN_WORKFLOW_ID,
            SCENARIO_ID,
            SENSOR_ID,
            STORY_ID,
        )
        runtime, world = _activated_world()
        world.activate_scenario("synthetic-hub-cascade")
        hub_obs = world.current_recovery_observation()
        from verticals.airline.actions.commands import recovery_command_id
        hero1_cmd = SimulationCommand(
            command_id=recovery_command_id(
                workflow_id=GOLDEN_WORKFLOW_ID,
                decision_id="SYN-DECISION-001",
                option_id="SYN-OPTION-CANCEL",
            ),
            trace_id=str(hub_obs["trace_id"]),
            issued_by="operations-control",
            type=HUB_COMMAND_TYPE,
            payload={
                "workflow_id": GOLDEN_WORKFLOW_ID,
                "decision_id": "SYN-DECISION-001",
                "option_id": "SYN-OPTION-CANCEL",
                "story_id": STORY_ID,
                "scenario_id": SCENARIO_ID,
                "persona": "duty_operations_manager",
                "value_gbp": 145_000.0,
                "evidence_versions": hub_obs["evidence_versions"],
                "actions": [{"action_type": "cancel_sector", "sector_id": "SYN-SECTOR-OUT-001", "resource_id": None, "minutes": None}],
                "objective_id": f"SYN-OBJECTIVE-{GOLDEN_WORKFLOW_ID}",
                "disruption_id": "SYN-DISRUPTION-HUB-001",
                "action_category": "integrated_hub_recovery",
                "expected_event_type": "airline.recovery.applied",
                "expected_evaluation_type": "airline.recovery.evaluation",
            },
        )
        event = apply_aog_recovery_command(world, hero1_cmd)
        assert event.type == "command.rejected"


# ---------------------------------------------------------------------------
# 12. Evaluation record completeness
# ---------------------------------------------------------------------------

class TestEvaluationRecord:
    def test_evaluation_has_all_required_fields(self) -> None:
        from verticals.airline.aog_constraints import AOG_OPTION_WORK_LOCAL
        _, world = _activated_world()
        cmd = _build_aog_command(world, AOG_OPTION_WORK_LOCAL)
        world.apply_command(cmd)
        evals = list(world.aog_recovery_evaluations.values())
        assert evals
        ev = evals[0]
        assert isinstance(ev.sectors_protected, int)
        assert isinstance(ev.projected_aog_duration_minutes, int)
        assert isinstance(ev.spare_lead_time_minutes, int)
        assert isinstance(ev.approved_provider_coverage, bool)
        assert isinstance(ev.synthetic_recovery_cost_gbp, float)
        assert ev.aircraft_released_by_ai is False
        assert ev.status in {"pass", "fail"}
        assert ev.invariant_results

    def test_evaluation_fields_as_dataclass(self) -> None:
        fields = [f.name for f in dataclasses.fields(AogRecoveryEvaluation)]
        assert "aircraft_released_by_ai" in fields
        assert "sectors_protected" in fields
        assert "projected_aog_duration_minutes" in fields
        assert "spare_lead_time_minutes" in fields
        assert "approved_provider_coverage" in fields
        assert "synthetic_recovery_cost_gbp" in fields
        assert "invariant_results" in fields
