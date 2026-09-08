"""TDD RED → GREEN tests for Airline Hero3 active-pack registration.

Tests cover:
  1. Pack contract: 3 domains / 3 functions / 3 profiles / schedule non-stub
  2. Partition: network-planning owns only schedule domain
  3. Manifest: 6 schedule activities + AirlineScheduleResilienceOrchestrator
  4. World registration: 3 routes / 3 responders
  5. Schedule route + responder exact identity
  6. Schedule diagnostic: real sensor + observation from seed-42 world
  7. UI world-scene: synthetic-schedule-restriction scenario present
  8. Schedule projection: observed entities / absent-ok / monitor option / eval
  9. Schedule detail: pending / completed / monitor
 10. Manifest memory_workflow_types: 3 entries
 11. Generation-manifest: entity_projections/schedule.py present
 12. validate_pack passes with schedule registered
 13. Agency / telco pack isolation
 14. Hero1 + AOG regression
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from api.server.services.entity_graph import DecisionWrite, EntityWrite, RelWrite
from api.server.world.runtime import SimulationRuntime
from api.shared.types import Workflow
from api.shared.vertical_loader import build_runtime, validate_pack
from verticals.airline.schedule_constants import (
    SCHED_COMMAND_TYPE,
    SCHED_DECISION_ID,
    SCHED_DISPLAY_NAME,
    SCHED_FAILURE_EVENT,
    SCHED_HITL_PERSONA,
    SCHED_OBJECTIVE_TYPE,
    SCHED_RISK_SIGNAL_ID,
    SCHED_SCENARIO_ID,
    SCHED_SENSOR_ID,
    SCHED_STORY_ID,
    SCHED_SUCCESS_EVENT,
    SCHED_WORKFLOW_ID,
    SCHED_WORKFLOW_ID_PREFIX,
    SCHED_WORKFLOW_TYPE,
)

PACK_ROOT = Path(__file__).resolve().parents[3] / "verticals" / "airline"
DESIGN_COMMIT = "b50713ed2b6324ac917402a41fc6e9c08c5c5262"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_workflow(
    workflow_type: str,
    *,
    status: str = "running",
    payload: dict | None = None,
    workflow_id: str = SCHED_WORKFLOW_ID,
) -> Workflow:
    return Workflow.model_construct(
        id=workflow_id,
        type=workflow_type,
        status=status,
        current_phase="Detect Schedule Risk Signal",
        created_at=1.0,
        sla_due_at=2.0,
        jurisdiction="Synthetic",
        agency="Synthetic Airline Operations",
        payload=payload or {},
        orchestration_instance_id="sched-instance-1",
    )


def _sched_world() -> tuple[SimulationRuntime, Any]:
    from verticals.airline.worlds.scenario import AirlineWorld
    runtime = SimulationRuntime(seed=42)
    world = AirlineWorld(seed=42, runtime=runtime)
    world.install()
    world.activate_scenario(SCHED_SCENARIO_ID)
    return runtime, world


# ---------------------------------------------------------------------------
# 1. Pack contract: domains
# ---------------------------------------------------------------------------


class TestScheduleDomain:
    def test_schedule_domain_is_present_in_airline_domains(self) -> None:
        from verticals.airline.domains import AIRLINE_DOMAINS
        assert SCHED_WORKFLOW_TYPE in AIRLINE_DOMAINS

    def test_schedule_domain_is_non_stub(self) -> None:
        from verticals.airline.domains import AIRLINE_DOMAINS
        assert AIRLINE_DOMAINS[SCHED_WORKFLOW_TYPE].stub is False

    def test_schedule_domain_display_name(self) -> None:
        from verticals.airline.domains import AIRLINE_DOMAINS
        assert AIRLINE_DOMAINS[SCHED_WORKFLOW_TYPE].display_name == SCHED_DISPLAY_NAME

    def test_schedule_domain_orchestrator(self) -> None:
        from verticals.airline.domains import AIRLINE_DOMAINS
        assert AIRLINE_DOMAINS[SCHED_WORKFLOW_TYPE].orchestrator_name == "AirlineScheduleResilienceOrchestrator"

    def test_schedule_domain_prefix(self) -> None:
        from verticals.airline.domains import AIRLINE_DOMAINS
        assert AIRLINE_DOMAINS[SCHED_WORKFLOW_TYPE].workflow_id_prefix == SCHED_WORKFLOW_ID_PREFIX

    def test_schedule_domain_six_phases_exact_kinds(self) -> None:
        from verticals.airline.domains import AIRLINE_DOMAINS
        domain = AIRLINE_DOMAINS[SCHED_WORKFLOW_TYPE]
        assert tuple(ph.kind for ph in domain.phases) == (
            "deterministic",
            "agent",
            "agent",
            "hitl",
            "deterministic",
            "deterministic",
        )

    def test_schedule_domain_phase_names(self) -> None:
        from verticals.airline.domains import AIRLINE_DOMAINS
        domain = AIRLINE_DOMAINS[SCHED_WORKFLOW_TYPE]
        names = [ph.name for ph in domain.phases]
        assert names == [
            "Detect Schedule Risk Signal",
            "Assess Network Ripple Effects",
            "Synthesize Resilience Options",
            "Approve Schedule Adjustment",
            "Commit Schedule Adjustment",
            "Verify Network Stability",
        ]

    def test_schedule_domain_hitl_gate(self) -> None:
        from verticals.airline.domains import AIRLINE_DOMAINS
        domain = AIRLINE_DOMAINS[SCHED_WORKFLOW_TYPE]
        assert len(domain.hitl_gates) == 1
        gate = domain.hitl_gates[0]
        assert gate.gate_phase == "Approve Schedule Adjustment"
        assert gate.persona == SCHED_HITL_PERSONA

    def test_schedule_domain_operator_surface(self) -> None:
        from verticals.airline.domains import AIRLINE_DOMAINS
        assert AIRLINE_DOMAINS[SCHED_WORKFLOW_TYPE].operator_surface == "network-planning"

    def test_schedule_domain_skill(self) -> None:
        from verticals.airline.domains import AIRLINE_DOMAINS
        assert "schedule-resilience-ranker" in AIRLINE_DOMAINS[SCHED_WORKFLOW_TYPE].skills

    def test_exactly_three_domains(self) -> None:
        from verticals.airline.domains import AIRLINE_DOMAINS
        assert len(AIRLINE_DOMAINS) == 3
        assert set(AIRLINE_DOMAINS.keys()) == {
            "integrated-hub-disruption-recovery",
            "aog-engineering-recovery",
            SCHED_WORKFLOW_TYPE,
        }


# ---------------------------------------------------------------------------
# 2. Pack contract: functions / partition
# ---------------------------------------------------------------------------


class TestNetworkPlanningFunction:
    def test_network_planning_function_exists(self) -> None:
        from verticals.airline.functions import AIRLINE_FUNCTIONS
        assert "network-planning" in AIRLINE_FUNCTIONS

    def test_network_planning_owns_schedule_domain(self) -> None:
        from verticals.airline.functions import AIRLINE_FUNCTIONS
        fn = AIRLINE_FUNCTIONS["network-planning"]
        assert SCHED_WORKFLOW_TYPE in fn.owns_domains

    def test_network_planning_owns_only_schedule_domain(self) -> None:
        from verticals.airline.functions import AIRLINE_FUNCTIONS
        fn = AIRLINE_FUNCTIONS["network-planning"]
        assert fn.owns_domains == (SCHED_WORKFLOW_TYPE,)

    def test_network_planning_persona_hierarchy(self) -> None:
        from verticals.airline.functions import AIRLINE_FUNCTIONS
        fn = AIRLINE_FUNCTIONS["network-planning"]
        assert fn.persona_hierarchy.role == "network_operations_director"

    def test_three_functions_total(self) -> None:
        from verticals.airline.functions import AIRLINE_FUNCTIONS
        assert set(AIRLINE_FUNCTIONS.keys()) == {
            "operations-control",
            "engineering-maintenance",
            "network-planning",
        }

    def test_operations_control_unchanged(self) -> None:
        from verticals.airline.functions import AIRLINE_FUNCTIONS
        fn = AIRLINE_FUNCTIONS["operations-control"]
        assert "integrated-hub-disruption-recovery" in fn.owns_domains

    def test_engineering_maintenance_unchanged(self) -> None:
        from verticals.airline.functions import AIRLINE_FUNCTIONS
        fn = AIRLINE_FUNCTIONS["engineering-maintenance"]
        assert "aog-engineering-recovery" in fn.owns_domains

    def test_partition_is_disjoint(self) -> None:
        """Every domain is owned by exactly one function."""
        from verticals.airline.functions import AIRLINE_FUNCTIONS
        all_owned: list[str] = []
        for fn in AIRLINE_FUNCTIONS.values():
            all_owned.extend(fn.owns_domains)
        # No duplicates
        assert len(all_owned) == len(set(all_owned))


# ---------------------------------------------------------------------------
# 3. Pack contract: process profiles
# ---------------------------------------------------------------------------


class TestScheduleProcessProfile:
    def test_schedule_profile_exists(self) -> None:
        from verticals.airline.process_profiles import AIRLINE_PROCESS_PROFILES
        assert SCHED_WORKFLOW_TYPE in AIRLINE_PROCESS_PROFILES

    def test_schedule_profile_sensor_id(self) -> None:
        from verticals.airline.process_profiles import AIRLINE_PROCESS_PROFILES
        assert AIRLINE_PROCESS_PROFILES[SCHED_WORKFLOW_TYPE].sensor_id == SCHED_SENSOR_ID

    def test_schedule_profile_orchestrator(self) -> None:
        from verticals.airline.process_profiles import AIRLINE_PROCESS_PROFILES
        assert AIRLINE_PROCESS_PROFILES[SCHED_WORKFLOW_TYPE].orchestrator == "AirlineScheduleResilienceOrchestrator"

    def test_schedule_profile_objective_type(self) -> None:
        from verticals.airline.process_profiles import AIRLINE_PROCESS_PROFILES
        assert AIRLINE_PROCESS_PROFILES[SCHED_WORKFLOW_TYPE].objective_type == SCHED_OBJECTIVE_TYPE

    def test_schedule_profile_command_type(self) -> None:
        from verticals.airline.process_profiles import AIRLINE_PROCESS_PROFILES
        assert AIRLINE_PROCESS_PROFILES[SCHED_WORKFLOW_TYPE].command_type == SCHED_COMMAND_TYPE

    def test_schedule_profile_success_event(self) -> None:
        from verticals.airline.process_profiles import AIRLINE_PROCESS_PROFILES
        assert AIRLINE_PROCESS_PROFILES[SCHED_WORKFLOW_TYPE].success_event == SCHED_SUCCESS_EVENT

    def test_schedule_profile_failure_event(self) -> None:
        from verticals.airline.process_profiles import AIRLINE_PROCESS_PROFILES
        assert AIRLINE_PROCESS_PROFILES[SCHED_WORKFLOW_TYPE].failure_event == SCHED_FAILURE_EVENT

    def test_schedule_profile_hitl_persona(self) -> None:
        from verticals.airline.process_profiles import AIRLINE_PROCESS_PROFILES
        assert AIRLINE_PROCESS_PROFILES[SCHED_WORKFLOW_TYPE].hitl_persona == SCHED_HITL_PERSONA

    def test_schedule_profile_scenario_id(self) -> None:
        from verticals.airline.process_profiles import AIRLINE_PROCESS_PROFILES
        assert AIRLINE_PROCESS_PROFILES[SCHED_WORKFLOW_TYPE].scenario_id == SCHED_SCENARIO_ID

    def test_schedule_profile_story_id(self) -> None:
        from verticals.airline.process_profiles import AIRLINE_PROCESS_PROFILES
        assert AIRLINE_PROCESS_PROFILES[SCHED_WORKFLOW_TYPE].story_id == SCHED_STORY_ID

    def test_three_process_profiles(self) -> None:
        from verticals.airline.process_profiles import AIRLINE_PROCESS_PROFILES
        assert len(AIRLINE_PROCESS_PROFILES) == 3
        assert SCHED_WORKFLOW_TYPE in AIRLINE_PROCESS_PROFILES


# ---------------------------------------------------------------------------
# 4. Manifest: activities + orchestrators + memory types
# ---------------------------------------------------------------------------


EXPECTED_SCHED_ACTIVITIES = {
    "sched_evidence_activity_trigger",
    "sched_assess_agent_activity_trigger",
    "sched_admission_activity_trigger",
    "sched_synthesize_agent_activity_trigger",
    "sched_governance_activity_trigger",
    "sched_command_activity_trigger",
}


class TestManifestScheduleRegistration:
    def test_sched_activities_in_manifest(self, tmp_path: Path) -> None:
        pack = build_runtime({"ZAVA_VERTICAL": "airline"}, data_root=tmp_path).pack
        assert EXPECTED_SCHED_ACTIVITIES <= pack.durable_functions.activities

    def test_sched_orchestrator_in_manifest(self, tmp_path: Path) -> None:
        pack = build_runtime({"ZAVA_VERTICAL": "airline"}, data_root=tmp_path).pack
        assert "AirlineScheduleResilienceOrchestrator" in pack.durable_functions.orchestrators

    def test_schedule_in_memory_workflow_types(self, tmp_path: Path) -> None:
        pack = build_runtime({"ZAVA_VERTICAL": "airline"}, data_root=tmp_path).pack
        assert SCHED_WORKFLOW_TYPE in pack.memory_workflow_types

    def test_three_memory_workflow_types(self, tmp_path: Path) -> None:
        pack = build_runtime({"ZAVA_VERTICAL": "airline"}, data_root=tmp_path).pack
        assert len(pack.memory_workflow_types) == 3

    def test_existing_activities_preserved(self, tmp_path: Path) -> None:
        pack = build_runtime({"ZAVA_VERTICAL": "airline"}, data_root=tmp_path).pack
        assert "airline_evidence_activity_trigger" in pack.durable_functions.activities
        assert "aog_evidence_activity_trigger" in pack.durable_functions.activities

    def test_sched_projection_registered(self, tmp_path: Path) -> None:
        pack = build_runtime({"ZAVA_VERTICAL": "airline"}, data_root=tmp_path).pack
        assert SCHED_WORKFLOW_TYPE in pack.projections


# ---------------------------------------------------------------------------
# 5. World registration: 3 routes + 3 responders
# ---------------------------------------------------------------------------


class TestWorldRegistration:
    def test_three_objective_routes(self) -> None:
        from verticals.airline.worlds.registration import AIRLINE_WORLD
        assert len(AIRLINE_WORLD.objective_routes) == 3

    def test_three_responders(self) -> None:
        from verticals.airline.worlds.registration import AIRLINE_WORLD
        assert len(AIRLINE_WORLD.responders) == 3

    def test_schedule_route_sensor_id(self) -> None:
        from verticals.airline.worlds.registration import AIRLINE_WORLD
        route = next(
            (r for r in AIRLINE_WORLD.objective_routes if r.sensor_id == SCHED_SENSOR_ID),
            None,
        )
        assert route is not None, f"No route with sensor_id={SCHED_SENSOR_ID!r}"

    def test_schedule_route_objective_type(self) -> None:
        from verticals.airline.worlds.registration import AIRLINE_WORLD
        route = next(
            r for r in AIRLINE_WORLD.objective_routes if r.sensor_id == SCHED_SENSOR_ID
        )
        assert route.objective_type == SCHED_OBJECTIVE_TYPE

    def test_schedule_route_command_type(self) -> None:
        from verticals.airline.worlds.registration import AIRLINE_WORLD
        route = next(
            r for r in AIRLINE_WORLD.objective_routes if r.sensor_id == SCHED_SENSOR_ID
        )
        assert SCHED_COMMAND_TYPE in route.allowed_command_types

    def test_schedule_route_success_event(self) -> None:
        from verticals.airline.worlds.registration import AIRLINE_WORLD
        route = next(
            r for r in AIRLINE_WORLD.objective_routes if r.sensor_id == SCHED_SENSOR_ID
        )
        assert SCHED_SUCCESS_EVENT in route.success_event_types

    def test_schedule_responder_exists(self) -> None:
        from verticals.airline.worlds.registration import AIRLINE_WORLD
        assert SCHED_OBJECTIVE_TYPE in AIRLINE_WORLD.responders

    def test_schedule_responder_prefix_sched(self) -> None:
        from verticals.airline.worlds.registration import AIRLINE_WORLD
        r = AIRLINE_WORLD.responders[SCHED_OBJECTIVE_TYPE]
        assert r.prefix == "sched"

    def test_schedule_responder_owner_function_network_planning(self) -> None:
        from verticals.airline.worlds.registration import AIRLINE_WORLD
        r = AIRLINE_WORLD.responders[SCHED_OBJECTIVE_TYPE]
        assert r.owner_function == "network-planning"

    def test_schedule_responder_lifecycle_bridge(self) -> None:
        from verticals.airline.worlds.registration import AIRLINE_WORLD
        r = AIRLINE_WORLD.responders[SCHED_OBJECTIVE_TYPE]
        assert r.lifecycle_start_via_bridge is True

    def test_schedule_responder_orchestrator(self) -> None:
        from verticals.airline.worlds.registration import AIRLINE_WORLD
        r = AIRLINE_WORLD.responders[SCHED_OBJECTIVE_TYPE]
        assert r.orchestrator == "AirlineScheduleResilienceOrchestrator"

    def test_hero1_route_unchanged(self) -> None:
        from verticals.airline.worlds.registration import AIRLINE_WORLD
        route = next(
            r for r in AIRLINE_WORLD.objective_routes if r.sensor_id == "sensor:integrated_hub_disruption"
        )
        assert route.objective_type == "recover_hub_disruption"

    def test_aog_route_unchanged(self) -> None:
        from verticals.airline.worlds.registration import AIRLINE_WORLD
        route = next(
            r for r in AIRLINE_WORLD.objective_routes if r.sensor_id == "sensor:aog_engineering"
        )
        assert route.objective_type == "recover_aog_engineering"


# ---------------------------------------------------------------------------
# 6. Schedule diagnostic
# ---------------------------------------------------------------------------


class TestScheduleDiagnostic:
    def test_diagnostic_raises_for_unknown_type(self) -> None:
        from verticals.airline.worlds.diagnostics import build_diagnostic_input
        with pytest.raises(ValueError, match="unsupported"):
            build_diagnostic_input("unknown-workflow-type")

    def test_schedule_diagnostic_returns_sensor_event(self) -> None:
        from verticals.airline.worlds.diagnostics import build_diagnostic_input
        sensor, _obs = build_diagnostic_input(SCHED_WORKFLOW_TYPE)
        assert sensor["type"] == "sensor.tripped"
        assert sensor["actor_id"] == SCHED_SENSOR_ID

    def test_schedule_diagnostic_sensor_story_id(self) -> None:
        from verticals.airline.worlds.diagnostics import build_diagnostic_input
        sensor, _obs = build_diagnostic_input(SCHED_WORKFLOW_TYPE)
        assert sensor["payload"]["story_id"] == SCHED_STORY_ID

    def test_schedule_diagnostic_observation_has_risk_signal(self) -> None:
        from verticals.airline.worlds.diagnostics import build_diagnostic_input
        _sensor, obs = build_diagnostic_input(SCHED_WORKFLOW_TYPE)
        assert obs["risk_signal"]["id"] == SCHED_RISK_SIGNAL_ID

    def test_schedule_diagnostic_observation_workflow_type(self) -> None:
        from verticals.airline.worlds.diagnostics import build_diagnostic_input
        _sensor, obs = build_diagnostic_input(SCHED_WORKFLOW_TYPE)
        assert obs["workflow_type"] == SCHED_WORKFLOW_TYPE

    def test_schedule_diagnostic_source_sensor_event_id_enriched(self) -> None:
        from verticals.airline.worlds.diagnostics import build_diagnostic_input
        sensor, _obs = build_diagnostic_input(SCHED_WORKFLOW_TYPE)
        assert "source_sensor_event_id" in sensor["payload"]
        assert sensor["payload"]["source_sensor_event_id"] == sensor["event_id"]

    def test_hero1_diagnostic_unchanged(self) -> None:
        from verticals.airline.worlds.diagnostics import build_diagnostic_input
        sensor, obs = build_diagnostic_input("integrated-hub-disruption-recovery")
        assert sensor["actor_id"] == "sensor:integrated_hub_disruption"
        assert obs["sector"]["id"] == "SYN-SECTOR-IN-001"

    def test_aog_diagnostic_unchanged(self) -> None:
        from verticals.airline.worlds.diagnostics import build_diagnostic_input
        sensor, obs = build_diagnostic_input("aog-engineering-recovery")
        assert sensor["actor_id"] == "sensor:aog_engineering"


# ---------------------------------------------------------------------------
# 7. UI world-scene: schedule scenario present
# ---------------------------------------------------------------------------


class TestWorldSceneScheduleScenario:
    def test_scene_has_schedule_scenario(self) -> None:
        from verticals.airline.worlds.registration import AIRLINE_WORLD
        names = {s["name"] for s in AIRLINE_WORLD.scene["scenarios"]}
        assert SCHED_SCENARIO_ID in names

    def test_scene_still_has_hub_and_aog_scenarios(self) -> None:
        from verticals.airline.worlds.registration import AIRLINE_WORLD
        names = {s["name"] for s in AIRLINE_WORLD.scene["scenarios"]}
        assert {"synthetic-hub-cascade", "synthetic-aog-defect"} <= names

    def test_scene_schedule_scenario_source_event_mapping(self) -> None:
        """Schedule scenario must map airline.schedule_risk.detected source event type."""
        from verticals.airline.worlds.registration import AIRLINE_WORLD
        sched = next(
            s for s in AIRLINE_WORLD.scene["scenarios"] if s["name"] == SCHED_SCENARIO_ID
        )
        assert sched.get("source_event_type") == "airline.schedule_risk.detected"

    def test_scene_schedule_scenario_process_event_type(self) -> None:
        """Schedule scenario must have a process event type."""
        from verticals.airline.worlds.registration import AIRLINE_WORLD
        sched = next(
            s for s in AIRLINE_WORLD.scene["scenarios"] if s["name"] == SCHED_SCENARIO_ID
        )
        assert sched.get("process_event_type") is not None


# ---------------------------------------------------------------------------
# 8. Schedule projection
# ---------------------------------------------------------------------------


def _minimal_sched_observation() -> dict:
    from verticals.airline.worlds.scenario import AirlineWorld
    runtime = SimulationRuntime(seed=42)
    world = AirlineWorld(seed=42, runtime=runtime)
    world.install()
    world.activate_scenario(SCHED_SCENARIO_ID)
    return world.current_schedule_observation()


def _sched_workflow_completed(
    observation: dict,
    command: dict | None = None,
    evaluation_id: str | None = None,
) -> Workflow:
    evidence: dict[str, Any] = {
        "workflow_evidence": {
            "workflow_id": SCHED_WORKFLOW_ID,
            "story_id": SCHED_STORY_ID,
            "source_mode": "simulated",
            "observation": observation,
        }
    }
    if command:
        evidence["command"] = command
        evidence["approval"] = {
            "decision": "approve",
            "persona": SCHED_HITL_PERSONA,
            "decision_id": SCHED_DECISION_ID,
            "selected_option_id": "SCHED_OPTION_BUFFER_RETIME",
            "workflow_id": SCHED_WORKFLOW_ID,
        }
    if evaluation_id:
        evidence["evaluation"] = {
            "status": "pending_world_event_pipeline",
            "evaluation_id": evaluation_id,
        }
    return Workflow.model_construct(
        id=SCHED_WORKFLOW_ID,
        type=SCHED_WORKFLOW_TYPE,
        status="completed",
        current_phase="Verify Network Stability",
        created_at=1.0,
        sla_due_at=2.0,
        jurisdiction="Synthetic",
        agency="Synthetic Airline Operations",
        payload={"evidence": evidence},
        orchestration_instance_id="sched-instance-1",
    )


class TestScheduleProjection:
    def test_projection_module_importable(self) -> None:
        from verticals.airline.entity_projections import schedule  # noqa: F401

    def test_projection_always_emits_workflow_node(self, tmp_path: Path) -> None:
        pack = build_runtime({"ZAVA_VERTICAL": "airline"}, data_root=tmp_path).pack
        wf = _fake_workflow(SCHED_WORKFLOW_TYPE)
        ops = list(pack.projections[SCHED_WORKFLOW_TYPE](wf))
        assert any(
            isinstance(op, EntityWrite) and op.kind == "Workflow" and op.id == SCHED_WORKFLOW_ID
            for op in ops
        )

    def test_projection_absent_observation_emits_only_workflow(self, tmp_path: Path) -> None:
        pack = build_runtime({"ZAVA_VERTICAL": "airline"}, data_root=tmp_path).pack
        wf = _fake_workflow(SCHED_WORKFLOW_TYPE)
        ops = list(pack.projections[SCHED_WORKFLOW_TYPE](wf))
        entity_writes = [op for op in ops if isinstance(op, EntityWrite)]
        # Only workflow node – no fabricated evidence
        assert all(op.id == SCHED_WORKFLOW_ID for op in entity_writes)

    def test_projection_observed_emits_risk_signal(self, tmp_path: Path) -> None:
        pack = build_runtime({"ZAVA_VERTICAL": "airline"}, data_root=tmp_path).pack
        obs = _minimal_sched_observation()
        wf = _sched_workflow_completed(obs)
        ops = list(pack.projections[SCHED_WORKFLOW_TYPE](wf))
        ids = {op.id for op in ops if isinstance(op, EntityWrite)}
        assert SCHED_RISK_SIGNAL_ID in ids

    def test_projection_observed_emits_affected_sectors(self, tmp_path: Path) -> None:
        pack = build_runtime({"ZAVA_VERTICAL": "airline"}, data_root=tmp_path).pack
        obs = _minimal_sched_observation()
        wf = _sched_workflow_completed(obs)
        ops = list(pack.projections[SCHED_WORKFLOW_TYPE](wf))
        ids = {op.id for op in ops if isinstance(op, EntityWrite)}
        assert "SYN-SECTOR-OUT-003" in ids
        assert "SYN-SECTOR-OUT-004" in ids

    def test_projection_observed_emits_reserve_resources(self, tmp_path: Path) -> None:
        pack = build_runtime({"ZAVA_VERTICAL": "airline"}, data_root=tmp_path).pack
        obs = _minimal_sched_observation()
        wf = _sched_workflow_completed(obs)
        ops = list(pack.projections[SCHED_WORKFLOW_TYPE](wf))
        ids = {op.id for op in ops if isinstance(op, EntityWrite)}
        assert "SYN-TAIL-005" in ids  # reserve aircraft
        assert "SYN-DUTY-006" in ids  # reserve crew

    def test_projection_without_command_no_command_node(self, tmp_path: Path) -> None:
        pack = build_runtime({"ZAVA_VERTICAL": "airline"}, data_root=tmp_path).pack
        obs = _minimal_sched_observation()
        wf = _sched_workflow_completed(obs)
        ops = list(pack.projections[SCHED_WORKFLOW_TYPE](wf))
        command_nodes = [
            op for op in ops
            if isinstance(op, EntityWrite) and op.kind == "ScheduleAdjustmentCommand"
        ]
        assert command_nodes == []

    def test_projection_with_command_emits_command_node(self, tmp_path: Path) -> None:
        pack = build_runtime({"ZAVA_VERTICAL": "airline"}, data_root=tmp_path).pack
        obs = _minimal_sched_observation()
        cmd = {"command_id": "CMD-SCHED-001", "command_type": SCHED_COMMAND_TYPE}
        wf = _sched_workflow_completed(obs, command=cmd)
        ops = list(pack.projections[SCHED_WORKFLOW_TYPE](wf))
        ids = {op.id for op in ops if isinstance(op, EntityWrite)}
        assert "CMD-SCHED-001" in ids

    def test_projection_decision_write_from_approval(self, tmp_path: Path) -> None:
        pack = build_runtime({"ZAVA_VERTICAL": "airline"}, data_root=tmp_path).pack
        obs = _minimal_sched_observation()
        cmd = {"command_id": "CMD-SCHED-001", "command_type": SCHED_COMMAND_TYPE}
        wf = _sched_workflow_completed(obs, command=cmd)
        ops = list(pack.projections[SCHED_WORKFLOW_TYPE](wf))
        dec = [op for op in ops if isinstance(op, DecisionWrite)]
        assert len(dec) == 1
        assert dec[0].persona_role == SCHED_HITL_PERSONA

    def test_projection_world_emits_evaluation_if_present(self, tmp_path: Path) -> None:
        pack = build_runtime({"ZAVA_VERTICAL": "airline"}, data_root=tmp_path).pack
        obs = _minimal_sched_observation()
        # Activate schedule scenario in a real world to create an evaluation
        from verticals.airline.worlds.scenario import AirlineWorld
        from verticals.airline.schedule_constraints import SCHED_OPTION_BUFFER_RETIME
        runtime = SimulationRuntime(seed=42)
        world = AirlineWorld(seed=42, runtime=runtime)
        world.install()
        world.activate_scenario(SCHED_SCENARIO_ID)
        obs = world.current_schedule_observation()
        cmd = world.command_for_schedule_option(
            option_id=SCHED_OPTION_BUFFER_RETIME,
            workflow_id=SCHED_WORKFLOW_ID,
            decision_id=SCHED_DECISION_ID,
            persona=SCHED_HITL_PERSONA,
        )
        world.apply_command(cmd)
        evaluations = [
            ev for ev in world.schedule_resilience_evaluations.values()
            if ev.workflow_id == SCHED_WORKFLOW_ID
        ]
        assert len(evaluations) > 0

        wf = Workflow.model_construct(
            id=SCHED_WORKFLOW_ID,
            type=SCHED_WORKFLOW_TYPE,
            status="completed",
            current_phase="Verify Network Stability",
            created_at=1.0,
            sla_due_at=2.0,
            jurisdiction="Synthetic",
            agency="Synthetic Airline Operations",
            payload={"evidence": {"workflow_evidence": {"observation": obs}}},
            orchestration_instance_id="sched-1",
        )
        state = SimpleNamespace(world_service=SimpleNamespace(scenario=world))
        from verticals.airline.entity_projections.schedule import project
        ops = list(project(wf, state))
        eval_nodes = [
            op
            for op in ops
            if isinstance(op, EntityWrite)
            and "Evaluation" in str(op.attrs.get("kind"))
        ]
        assert len(eval_nodes) > 0

    def test_projection_materialises_in_shared_graph_schema(self, tmp_path: Path) -> None:
        from api.server.services.entity_graph import (
            DecisionWrite,
            EntityGraph,
            RelWrite,
        )
        from verticals.airline.entity_projections.schedule import project
        from verticals.airline.schedule_constraints import SCHED_OPTION_BUFFER_RETIME
        from verticals.airline.worlds.scenario import AirlineWorld

        world = AirlineWorld(seed=42, runtime=SimulationRuntime(seed=42))
        world.install()
        world.activate_scenario(SCHED_SCENARIO_ID)
        observation = world.current_schedule_observation()
        command = world.command_for_schedule_option(
            option_id=SCHED_OPTION_BUFFER_RETIME,
            workflow_id=SCHED_WORKFLOW_ID,
            decision_id=SCHED_DECISION_ID,
            persona=SCHED_HITL_PERSONA,
        )
        accepted = world.apply_command(command)
        workflow = Workflow.model_construct(
            id=SCHED_WORKFLOW_ID,
            type=SCHED_WORKFLOW_TYPE,
            status="completed",
            current_phase="Verify Network Stability",
            created_at=1.0,
            sla_due_at=2.0,
            jurisdiction="Synthetic",
            agency="Synthetic Airline Operations",
            payload={
                "evidence": {
                    "workflow_evidence": {"observation": observation},
                    "gateway_event": accepted.to_dict(),
                    "command": command.to_dict(),
                    "approval": {
                        "decision": "approve",
                        "persona": SCHED_HITL_PERSONA,
                        "decision_id": SCHED_DECISION_ID,
                    },
                }
            },
            orchestration_instance_id="sched-instance-1",
        )

        graph = EntityGraph(tmp_path / "schedule-projection.kuzu")
        ops = list(project(workflow))
        for op in ops:
            if isinstance(op, EntityWrite):
                graph.upsert(op)
            elif isinstance(op, RelWrite):
                graph.link(op.src_id, op.rel, op.dst_id, **op.attrs)
            elif isinstance(op, DecisionWrite):
                assert op.decided_at

        assert graph.linked(SCHED_WORKFLOW_ID)


# ---------------------------------------------------------------------------
# 9. Schedule detail: pending / completed / monitor
# ---------------------------------------------------------------------------


class TestScheduleDetail:
    def _obs(self) -> dict:
        return _minimal_sched_observation()

    def test_detail_returns_none_for_unknown_type(self) -> None:
        from verticals.airline.detail import workflow_detail
        wf = _fake_workflow("unknown-type")
        result = workflow_detail(wf, None)
        assert result is None

    def test_detail_dispatches_schedule_type(self) -> None:
        from verticals.airline.detail import workflow_detail
        obs = self._obs()
        payload = {"evidence": {"workflow_evidence": {"observation": obs}}}
        wf = _fake_workflow(SCHED_WORKFLOW_TYPE, payload=payload)
        result = workflow_detail(wf, None)
        assert result is not None
        assert isinstance(result, dict)
        assert result["workflow_id"] == SCHED_WORKFLOW_ID

    def test_detail_pending_no_mutations_no_evaluation(self) -> None:
        from verticals.airline.detail import workflow_detail
        obs = self._obs()
        payload = {"evidence": {"workflow_evidence": {"observation": obs}}}
        wf = _fake_workflow(SCHED_WORKFLOW_TYPE, status="awaiting_hitl", payload=payload)
        result = workflow_detail(wf, None)
        assert result is not None
        assert result.get("mutations") is None
        assert result.get("evaluation") is None

    def test_detail_governance_pending_status(self) -> None:
        from verticals.airline.detail import workflow_detail
        obs = self._obs()
        payload = {"evidence": {"workflow_evidence": {"observation": obs}}}
        wf = _fake_workflow(SCHED_WORKFLOW_TYPE, status="awaiting_hitl", payload=payload)
        result = workflow_detail(wf, None)
        assert result is not None
        assert result["governance"]["status"] == "pending"

    def test_detail_story_fields(self) -> None:
        from verticals.airline.detail import workflow_detail
        obs = self._obs()
        payload = {"evidence": {"workflow_evidence": {"observation": obs}}}
        wf = _fake_workflow(SCHED_WORKFLOW_TYPE, payload=payload)
        result = workflow_detail(wf, None)
        assert result is not None
        assert result["story"]["story_id"] == SCHED_STORY_ID
        assert result["story"]["scenario_id"] == SCHED_SCENARIO_ID

    def test_detail_timeline_six_phases(self) -> None:
        from verticals.airline.detail import workflow_detail
        obs = self._obs()
        payload = {"evidence": {"workflow_evidence": {"observation": obs}}}
        wf = _fake_workflow(SCHED_WORKFLOW_TYPE, payload=payload)
        result = workflow_detail(wf, None)
        assert result is not None
        assert len(result["timeline"]) == 6

    def test_detail_timeline_phase_names(self) -> None:
        from verticals.airline.detail import workflow_detail
        obs = self._obs()
        payload = {"evidence": {"workflow_evidence": {"observation": obs}}}
        wf = _fake_workflow(SCHED_WORKFLOW_TYPE, payload=payload)
        result = workflow_detail(wf, None)
        assert result is not None
        names = [p["phase"] for p in result["timeline"]]
        assert names == [
            "Detect Schedule Risk Signal",
            "Assess Network Ripple Effects",
            "Synthesize Resilience Options",
            "Approve Schedule Adjustment",
            "Commit Schedule Adjustment",
            "Verify Network Stability",
        ]

    def test_detail_forecast_baseline_present(self) -> None:
        from verticals.airline.detail import workflow_detail
        obs = self._obs()
        payload = {"evidence": {"workflow_evidence": {"observation": obs}}}
        wf = _fake_workflow(SCHED_WORKFLOW_TYPE, payload=payload)
        result = workflow_detail(wf, None)
        assert result is not None
        assert "baseline" in result
        assert result["baseline"]["risk_signal_id"] == SCHED_RISK_SIGNAL_ID

    def test_detail_hero1_type_unaffected(self) -> None:
        from verticals.airline.detail import workflow_detail
        wf = _fake_workflow("integrated-hub-disruption-recovery", workflow_id="AIRHUB-0001")
        result = workflow_detail(wf, None)
        # Hero1 returns None if observation missing
        assert result is None or isinstance(result, dict)

    def test_detail_aog_type_unaffected(self) -> None:
        from verticals.airline.detail import workflow_detail
        obs = {
            "workflow_type": "aog-engineering-recovery",
            "workflow_id": "AOGA-0001",
            "story_id": "SYN-STORY-AOG-001",
            "affected_tail_id": "SYN-TAIL-003",
            "technical_status": {"id": "SYN-TECH-003", "status": "aog"},
            "maintenance_task": {"id": "SYN-TASK-001", "status": "open"},
            "approved_providers": [],
            "sensor_event_id": "EVT-001",
            "source_event_id": "EVT-002",
        }
        payload = {"evidence": {"workflow_evidence": {"observation": obs}}}
        wf = _fake_workflow("aog-engineering-recovery", workflow_id="AOGA-0001", payload=payload)
        result = workflow_detail(wf, None)
        assert result is not None
        assert result["workflow_id"] == "AOGA-0001"


# ---------------------------------------------------------------------------
# 10. Generation manifest: schedule.py file present
# ---------------------------------------------------------------------------


class TestGenerationManifest:
    def test_schedule_projection_in_generation_manifest(self) -> None:
        manifest = json.loads((PACK_ROOT / "generation-manifest.json").read_text(encoding="utf-8"))
        paths = {r["path"] for r in manifest["records"]}
        assert "verticals/airline/entity_projections/schedule.py" in paths

    def test_schedule_detail_module_in_generation_manifest(self) -> None:
        manifest = json.loads((PACK_ROOT / "generation-manifest.json").read_text(encoding="utf-8"))
        paths = {r["path"] for r in manifest["records"]}
        assert any("schedule_detail" in p or "sched_detail" in p for p in paths)

    def test_generation_manifest_is_current(self) -> None:
        """All actual files in the airline pack are listed in the manifest."""
        manifest = json.loads((PACK_ROOT / "generation-manifest.json").read_text(encoding="utf-8"))
        recorded = {r["path"] for r in manifest["records"]}
        actual = {
            str(p.relative_to(PACK_ROOT.parents[1]))
            for p in PACK_ROOT.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and not p.name.endswith((".pyc", ".pyo"))
        }
        assert recorded == actual

    def test_all_manifest_records_are_bespoke(self) -> None:
        manifest = json.loads((PACK_ROOT / "generation-manifest.json").read_text(encoding="utf-8"))
        assert all(r["ownership"] == "bespoke" for r in manifest["records"])


# ---------------------------------------------------------------------------
# 11. validate_pack passes
# ---------------------------------------------------------------------------


def test_validate_pack_with_schedule_registered(tmp_path: Path) -> None:
    runtime = build_runtime({"ZAVA_VERTICAL": "airline"}, data_root=tmp_path)
    validate_pack(runtime.pack)  # must not raise


# ---------------------------------------------------------------------------
# 12. Agency / telco isolation
# ---------------------------------------------------------------------------


def test_agency_pack_unaffected_by_airline_hero3(tmp_path: Path) -> None:
    """Agency pack must not be affected by airline Hero3 changes."""
    from api.shared.vertical_loader import build_runtime as _build
    runtime = _build({"ZAVA_VERTICAL": "agency"}, data_root=tmp_path)
    assert runtime.pack.name == "agency"
    assert "preemptive-schedule-resilience" not in (runtime.pack.domains or {})


def test_telco_pack_unaffected_by_airline_hero3(tmp_path: Path) -> None:
    runtime = build_runtime({"ZAVA_VERTICAL": "telco"}, data_root=tmp_path)
    assert runtime.pack.name == "telco"
    assert "preemptive-schedule-resilience" not in (runtime.pack.domains or {})


# ---------------------------------------------------------------------------
# 13. Hero1 + AOG regression
# ---------------------------------------------------------------------------


class TestHero1AogRegression:
    def test_hero1_domain_unchanged(self) -> None:
        from verticals.airline.domains import AIRLINE_DOMAINS
        domain = AIRLINE_DOMAINS["integrated-hub-disruption-recovery"]
        assert domain.stub is False
        assert domain.orchestrator_name == "AirlineIntegratedHubRecoveryOrchestrator"

    def test_aog_domain_unchanged(self) -> None:
        from verticals.airline.domains import AIRLINE_DOMAINS
        domain = AIRLINE_DOMAINS["aog-engineering-recovery"]
        assert domain.stub is False
        assert domain.orchestrator_name == "AirlineAogEngineeringRecoveryOrchestrator"

    def test_hero1_process_profile_unchanged(self) -> None:
        from verticals.airline.process_profiles import AIRLINE_PROCESS_PROFILES
        p = AIRLINE_PROCESS_PROFILES["integrated-hub-disruption-recovery"]
        assert p.sensor_id == "sensor:integrated_hub_disruption"
        assert p.command_type == "airline.commit_recovery_plan"

    def test_aog_process_profile_unchanged(self) -> None:
        from verticals.airline.process_profiles import AIRLINE_PROCESS_PROFILES
        p = AIRLINE_PROCESS_PROFILES["aog-engineering-recovery"]
        assert p.sensor_id == "sensor:aog_engineering"
        assert p.command_type == "airline.commit_aog_recovery"

    def test_hero1_responder_prefix_unchanged(self) -> None:
        from verticals.airline.worlds.registration import AIRLINE_WORLD
        r = AIRLINE_WORLD.responders["recover_hub_disruption"]
        assert r.prefix == "ihdr"

    def test_aog_responder_prefix_unchanged(self) -> None:
        from verticals.airline.worlds.registration import AIRLINE_WORLD
        r = AIRLINE_WORLD.responders["recover_aog_engineering"]
        assert r.prefix == "aog"
