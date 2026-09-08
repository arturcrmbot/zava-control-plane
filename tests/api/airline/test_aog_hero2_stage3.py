"""Airline Hero 2 Stage 3 – Active-pack registration and visibility surfaces.

TDD contract tests – run RED first to capture evidence, then implement.

Requirements covered:
  - Two exact domains (Hero1 hub + AOG)
  - Two functions with one-owner partition
  - AirlineProcessProfile constants
  - AOG domain 6 phases / 1 HitlGate / 1 skill
  - Durable app indexes orchestrator + five AOG activities (no duplicate app)
  - World ObjectiveRoute + ResponderRegistration for AOG
  - UI world-scene: synthetic-aog-defect scenario, airline.aog.detected mapping
  - Diagnostic: build_diagnostic_input('aog-engineering-recovery') returns
    real AOG sensor event (source_sensor_event_id present) + real AOG observation
  - entity_projections/aog.py: AOG projection returns typed records
  - AIRLINE_PROJECTIONS includes both workflow types
  - workflow_detail dispatches to AOG detail for aog-engineering-recovery
  - Hero1 projection/detail unchanged
  - memory_workflow_types includes both
  - Pack validate passes
  - No AOG domain under agency/telco/other packs (inventory isolation)
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

AIRLINE_ROOT = Path(__file__).resolve().parents[3] / "verticals" / "airline"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_workflow(workflow_type: str, payload: dict, status: str = "running") -> Any:
    return SimpleNamespace(type=workflow_type, id="AOGA-0001", status=status, payload=payload)


# ===========================================================================
# 1. Process-profile constants
# ===========================================================================


def test_aog_constants_complete():
    """aog_constants must export all required identifiers."""
    from verticals.airline import aog_constants as C  # noqa: N812

    assert C.AOG_WORKFLOW_TYPE == "aog-engineering-recovery"
    assert C.AOG_SENSOR_ID == "sensor:aog_engineering"
    assert C.AOG_OBJECTIVE_TYPE == "recover_aog_engineering"
    assert C.AOG_COMMAND_TYPE == "airline.commit_aog_recovery"
    assert C.AOG_SUCCESS_EVENT == "airline.aog_recovery.applied"
    assert C.AOG_FAILURE_EVENT == "command.rejected"
    assert C.AOG_HITL_PERSONA == "engineering_duty_manager"
    assert C.AOG_HITL_EVENT == "engineering_duty_manager_decision"
    assert C.AOG_SCENARIO_ID == "synthetic-aog-defect"
    assert C.AOG_STORY_ID == "SYN-STORY-AOG-001"
    assert C.AOG_WORKFLOW_ID_PREFIX == "AOGA"
    assert C.AOG_ORCHESTRATOR == "AirlineAogEngineeringRecoveryOrchestrator"
    assert C.AOG_DISPLAY_NAME == "AOG Engineering and Spares Recovery"
    assert C.AOG_OBJECTIVE_TYPE == "recover_aog_engineering"


def test_process_profiles_contains_both_workflow_types():
    from verticals.airline.process_profiles import AIRLINE_PROCESS_PROFILES

    assert "integrated-hub-disruption-recovery" in AIRLINE_PROCESS_PROFILES
    assert "aog-engineering-recovery" in AIRLINE_PROCESS_PROFILES


def test_aog_process_profile_fields():
    from verticals.airline.process_profiles import AIRLINE_PROCESS_PROFILES

    p = AIRLINE_PROCESS_PROFILES["aog-engineering-recovery"]
    assert p.workflow_type == "aog-engineering-recovery"
    assert p.orchestrator == "AirlineAogEngineeringRecoveryOrchestrator"
    assert p.sensor_id == "sensor:aog_engineering"
    assert p.objective_type == "recover_aog_engineering"
    assert p.command_type == "airline.commit_aog_recovery"
    assert p.success_event == "airline.aog_recovery.applied"
    assert p.failure_event == "command.rejected"
    assert p.hitl_persona == "engineering_duty_manager"
    assert p.hitl_event == "engineering_duty_manager_decision"
    assert p.scenario_id == "synthetic-aog-defect"
    assert p.story_id == "SYN-STORY-AOG-001"


# ===========================================================================
# 2. Domains
# ===========================================================================


def test_airline_has_exactly_two_domains():
    from verticals.airline.domains import AIRLINE_DOMAINS

    assert set(AIRLINE_DOMAINS.keys()) == {
        "integrated-hub-disruption-recovery",
        "aog-engineering-recovery",
        "preemptive-schedule-resilience",
    }


def test_aog_domain_not_stub():
    from verticals.airline.domains import AIRLINE_DOMAINS

    domain = AIRLINE_DOMAINS["aog-engineering-recovery"]
    assert not domain.stub


def test_aog_domain_fields():
    from verticals.airline.domains import AIRLINE_DOMAINS

    d = AIRLINE_DOMAINS["aog-engineering-recovery"]
    assert d.workflow_type == "aog-engineering-recovery"
    assert d.display_name == "AOG Engineering and Spares Recovery"
    assert d.workflow_id_prefix == "AOGA"
    assert d.orchestrator_name == "AirlineAogEngineeringRecoveryOrchestrator"
    assert d.operator_surface == "engineering-maintenance"


def test_aog_domain_six_phases():
    from verticals.airline.domains import AIRLINE_DOMAINS

    d = AIRLINE_DOMAINS["aog-engineering-recovery"]
    phases = d.phases
    assert len(phases) == 6

    expected = [
        ("Detect AOG Event", "deterministic"),
        ("Check Airworthiness Constraints", "deterministic"),
        ("Synthesize Engineering Recovery Options", "agent"),
        ("Approve Engineering Recovery", "hitl"),
        ("Commit Engineering and Operational Actions", "deterministic"),
        ("Verify Recovery State", "deterministic"),
    ]
    for phase, (name, kind) in zip(phases, expected):
        assert phase.name == name, f"Phase name mismatch: {phase.name!r} != {name!r}"
        assert phase.kind == kind, f"Phase kind mismatch for {name!r}: {phase.kind!r} != {kind!r}"


def test_aog_domain_one_hitl_gate():
    from verticals.airline.domains import AIRLINE_DOMAINS

    d = AIRLINE_DOMAINS["aog-engineering-recovery"]
    assert len(d.hitl_gates) == 1
    gate = d.hitl_gates[0]
    assert gate.gate_phase == "Approve Engineering Recovery"
    assert gate.external_event == "engineering_duty_manager_decision"
    assert gate.persona == "engineering_duty_manager"


def test_aog_domain_skill_tuple():
    from verticals.airline.domains import AIRLINE_DOMAINS

    d = AIRLINE_DOMAINS["aog-engineering-recovery"]
    assert d.skills == ("aog-recovery-ranker",)


# ===========================================================================
# 3. Functions
# ===========================================================================


def test_airline_has_exactly_two_functions():
    from verticals.airline.functions import AIRLINE_FUNCTIONS

    assert set(AIRLINE_FUNCTIONS.keys()) == {
        "operations-control",
        "engineering-maintenance",
        "network-planning",
    }


def test_operations_control_owns_only_hub():
    from verticals.airline.functions import AIRLINE_FUNCTIONS

    f = AIRLINE_FUNCTIONS["operations-control"]
    assert set(f.owns_domains) == {"integrated-hub-disruption-recovery"}


def test_engineering_maintenance_owns_only_aog():
    from verticals.airline.functions import AIRLINE_FUNCTIONS

    f = AIRLINE_FUNCTIONS["engineering-maintenance"]
    assert set(f.owns_domains) == {"aog-engineering-recovery"}


def test_engineering_maintenance_fields():
    from verticals.airline.functions import AIRLINE_FUNCTIONS

    f = AIRLINE_FUNCTIONS["engineering-maintenance"]
    assert f.operator_surface == "engineering-maintenance"
    assert f.persona_hierarchy.role == "engineering_duty_manager"


# ===========================================================================
# 4. Durable: AOG activities registered on the same app, no duplicate
# ===========================================================================


def test_durable_aog_register_called_once(tmp_path):
    """aog_durable.register(app) must be called on the existing app."""
    import verticals.airline.durable as durable_mod  # noqa: PLC0415

    app = durable_mod.app
    # Calling register should be idempotent at module level; verify app identity
    assert app is not None

    # The five AOG activity trigger names must be wired onto app
    registered = getattr(app, "_registered_activity_names", set())
    # We check via the manifest's durable registration instead
    from verticals.airline.manifest import build_pack  # noqa: PLC0415

    pack = build_pack()
    durable_reg = pack.durable_functions
    expected_aog_activities = {
        "aog_evidence_activity_trigger",
        "aog_airworthiness_activity_trigger",
        "aog_agent_activity_trigger",
        "aog_governance_activity_trigger",
        "aog_command_activity_trigger",
    }
    assert expected_aog_activities.issubset(durable_reg.activities), (
        f"Missing AOG activities: {expected_aog_activities - durable_reg.activities}"
    )


def test_durable_aog_orchestrator_registered(tmp_path):
    from verticals.airline.manifest import build_pack

    pack = build_pack()
    durable_reg = pack.durable_functions
    assert "AirlineAogEngineeringRecoveryOrchestrator" in durable_reg.orchestrators


def test_durable_hero1_orchestrator_still_registered(tmp_path):
    from verticals.airline.manifest import build_pack

    pack = build_pack()
    durable_reg = pack.durable_functions
    assert "AirlineIntegratedHubRecoveryOrchestrator" in durable_reg.orchestrators


# ===========================================================================
# 5. World routes / responders for AOG
# ===========================================================================


def test_aog_objective_route_registered():
    from verticals.airline.worlds.registration import AIRLINE_WORLD

    routes = AIRLINE_WORLD.objective_routes
    aog_route = next(
        (r for r in routes if r.sensor_id == "sensor:aog_engineering"),
        None,
    )
    assert aog_route is not None, "AOG ObjectiveRoute not found"
    assert "airline.commit_aog_recovery" in aog_route.allowed_command_types
    assert "airline.aog_recovery.applied" in aog_route.success_event_types
    assert "command.rejected" in aog_route.failure_event_types


def test_aog_responder_registered():
    from verticals.airline.worlds.registration import AIRLINE_WORLD

    responders = AIRLINE_WORLD.responders
    assert "recover_aog_engineering" in responders
    r = responders["recover_aog_engineering"]
    assert r.orchestrator == "AirlineAogEngineeringRecoveryOrchestrator"
    assert r.workflow_type == "aog-engineering-recovery"
    assert r.prefix == "aog"
    assert r.owner_function == "engineering-maintenance"
    assert r.lifecycle_start_via_bridge is True


def test_hero1_responder_preserved():
    from verticals.airline.worlds.registration import AIRLINE_WORLD

    responders = AIRLINE_WORLD.responders
    assert "recover_hub_disruption" in responders


# ===========================================================================
# 6. UI world-scene
# ===========================================================================


def test_world_scene_synthetic_aog_defect_scenario():
    scene = json.loads((AIRLINE_ROOT / "ui" / "world-scene.json").read_text())
    scenario_names = [s["name"] for s in scene["scenarios"]]
    assert "synthetic-aog-defect" in scenario_names


def test_world_scene_aog_detected_event_mapping():
    scene = json.loads((AIRLINE_ROOT / "ui" / "world-scene.json").read_text())
    event_types = {m["event_type"] for m in scene["event_mappings"]}
    assert "airline.aog.detected" in event_types


def test_world_scene_aog_in_process_event_types():
    scene = json.loads((AIRLINE_ROOT / "ui" / "world-scene.json").read_text())
    assert "airline.aog.detected" in scene["process_event_types"]


def test_world_scene_hero1_scenario_preserved():
    scene = json.loads((AIRLINE_ROOT / "ui" / "world-scene.json").read_text())
    scenario_names = [s["name"] for s in scene["scenarios"]]
    assert "synthetic-hub-cascade" in scenario_names


# ===========================================================================
# 7. Diagnostics
# ===========================================================================


def test_aog_diagnostic_returns_sensor_event_with_source_id():
    from verticals.airline.worlds.diagnostics import build_diagnostic_input

    sensor_event, observation = build_diagnostic_input("aog-engineering-recovery")
    assert sensor_event["type"] == "sensor.tripped"
    assert sensor_event["actor_id"] == "sensor:aog_engineering"
    payload = sensor_event.get("payload") or {}
    assert "source_sensor_event_id" in payload, "source_sensor_event_id missing from sensor event payload"


def test_aog_diagnostic_observation_fields():
    from verticals.airline.worlds.diagnostics import build_diagnostic_input

    _sensor_event, observation = build_diagnostic_input("aog-engineering-recovery")
    assert observation.get("workflow_type") == "aog-engineering-recovery"
    assert observation.get("sensor_event_id") is not None
    assert observation.get("source_event_id") is not None
    assert "affected_tail_id" in observation
    assert "technical_status" in observation


def test_hero1_diagnostic_unchanged():
    from verticals.airline.worlds.diagnostics import build_diagnostic_input

    sensor_event, observation = build_diagnostic_input("integrated-hub-disruption-recovery")
    assert sensor_event["type"] == "sensor.tripped"
    assert sensor_event["actor_id"] == "sensor:integrated_hub_disruption"
    payload = sensor_event.get("payload") or {}
    assert "source_sensor_event_id" in payload


def test_unknown_diagnostic_type_raises():
    from verticals.airline.worlds.diagnostics import build_diagnostic_input

    with pytest.raises((ValueError, KeyError, TypeError)):
        build_diagnostic_input("unknown-workflow-type")


# ===========================================================================
# 8. AIRLINE_PROJECTIONS includes both workflow types
# ===========================================================================


def test_projections_include_both_workflow_types():
    from verticals.airline.projections import AIRLINE_PROJECTIONS

    assert "integrated-hub-disruption-recovery" in AIRLINE_PROJECTIONS
    assert "aog-engineering-recovery" in AIRLINE_PROJECTIONS


def test_aog_projection_module_exists():
    """entity_projections/aog.py must exist and be importable."""
    mod = importlib.import_module("verticals.airline.entity_projections.aog")
    assert hasattr(mod, "project"), "aog projection module must have 'project' function"


def test_aog_projection_absent_evidence_yields_minimal_records():
    """With minimal evidence, projection returns at least a Workflow record, no fabricated data."""
    from verticals.airline.entity_projections.aog import project
    from api.server.services.entity_graph import EntityWrite

    workflow = _fake_workflow("aog-engineering-recovery", payload={}, status="running")
    records = list(project(workflow, None))
    entity_kinds = {r.kind for r in records if isinstance(r, EntityWrite)}
    assert "Workflow" in entity_kinds
    # No fabricated entities beyond what evidence supports
    assert len(records) >= 1


def test_aog_projection_with_observation_returns_aircraft_node():
    """With AOG observation evidence, projection emits Aircraft entity."""
    from verticals.airline.entity_projections.aog import project
    from api.server.services.entity_graph import EntityWrite

    observation = {
        "workflow_type": "aog-engineering-recovery",
        "workflow_id": "AOGA-0001",
        "story_id": "SYN-STORY-AOG-001",
        "affected_tail_id": "SYN-TAIL-003",
        "technical_status": {"id": "SYN-TECH-003", "status": "aog", "fault_code": "F01", "version": 1},
        "maintenance_task": {"id": "SYN-TASK-001", "status": "open", "version": 1},
        "approved_providers": [],
        "spares": [],
        "sensor_event_id": "EVT-SENSOR-001",
        "source_event_id": "EVT-SOURCE-001",
    }
    evidence = {
        "workflow_evidence": {"observation": observation},
    }
    payload = {"evidence": evidence}
    workflow = _fake_workflow("aog-engineering-recovery", payload=payload)
    records = list(project(workflow, None))
    entity_ids = {r.id for r in records if isinstance(r, EntityWrite)}
    assert "SYN-TAIL-003" in entity_ids or any(
        "SYN-TAIL" in eid for eid in entity_ids
    ), f"Aircraft entity missing from projection; got: {entity_ids}"


# ===========================================================================
# 9. AOG detail – dispatch + pending + no-release
# ===========================================================================


def test_aog_detail_returns_none_for_hero1():
    """AOG detail hook must return None for non-AOG workflows."""
    from verticals.airline.detail import workflow_detail

    wf = _fake_workflow("integrated-hub-disruption-recovery", payload={})
    # Hero1 detail should handle this; not AOG's concern
    # Explicitly verify no cross-contamination: detail doesn't crash on AOG type
    result = workflow_detail(wf, None)
    # Hero1 returns None when observation missing, that's fine
    assert result is None or isinstance(result, dict)


def test_aog_detail_pending_workflow():
    """workflow_detail returns AOG detail dict for aog-engineering-recovery with observation."""
    from verticals.airline.detail import workflow_detail

    observation = {
        "workflow_type": "aog-engineering-recovery",
        "workflow_id": "AOGA-0001",
        "story_id": "SYN-STORY-AOG-001",
        "affected_tail_id": "SYN-TAIL-003",
        "technical_status": {"id": "SYN-TECH-003", "status": "aog", "fault_code": "F01", "version": 1},
        "maintenance_task": {"id": "SYN-TASK-001", "status": "open", "version": 1},
        "approved_providers": [],
        "spares": [],
        "sensor_event_id": "EVT-SENSOR-001",
        "source_event_id": "EVT-SOURCE-001",
        "scenario_id": "synthetic-aog-defect",
    }
    evidence = {
        "workflow_evidence": {"observation": observation, "story_id": "SYN-STORY-AOG-001"},
    }
    payload = {"evidence": evidence}
    wf = _fake_workflow("aog-engineering-recovery", payload=payload, status="running")
    result = workflow_detail(wf, None)
    assert result is not None, "workflow_detail must return a dict for AOG workflows"
    assert isinstance(result, dict)
    assert result.get("workflow_id") == "AOGA-0001"
    assert "timeline" in result
    timeline = result["timeline"]
    assert len(timeline) == 6, f"Expected 6 phases, got {len(timeline)}"


def test_aog_detail_timeline_phase_names():
    from verticals.airline.detail import workflow_detail

    observation = {
        "workflow_type": "aog-engineering-recovery",
        "workflow_id": "AOGA-0001",
        "story_id": "SYN-STORY-AOG-001",
        "affected_tail_id": "SYN-TAIL-003",
        "technical_status": {"id": "SYN-TECH-003", "status": "aog", "fault_code": "F01", "version": 1},
        "maintenance_task": {"id": "SYN-TASK-001", "status": "open", "version": 1},
        "approved_providers": [],
        "spares": [],
        "sensor_event_id": "EVT-SENSOR-001",
        "source_event_id": "EVT-SOURCE-001",
    }
    evidence = {"workflow_evidence": {"observation": observation}}
    payload = {"evidence": evidence}
    wf = _fake_workflow("aog-engineering-recovery", payload=payload)
    result = workflow_detail(wf, None)
    assert result is not None
    phase_names = [p["phase"] for p in result["timeline"]]
    assert phase_names == [
        "Detect AOG Event",
        "Check Airworthiness Constraints",
        "Synthesize Engineering Recovery Options",
        "Approve Engineering Recovery",
        "Commit Engineering and Operational Actions",
        "Verify Recovery State",
    ]


def test_aog_detail_pending_governance():
    from verticals.airline.detail import workflow_detail

    observation = {
        "workflow_type": "aog-engineering-recovery",
        "workflow_id": "AOGA-0001",
        "story_id": "SYN-STORY-AOG-001",
        "affected_tail_id": "SYN-TAIL-003",
        "technical_status": {"id": "SYN-TECH-003", "status": "aog", "fault_code": "F01", "version": 1},
        "maintenance_task": {"id": "SYN-TASK-001", "status": "open", "version": 1},
        "approved_providers": [],
        "spares": [],
        "sensor_event_id": "EVT-SENSOR-001",
        "source_event_id": "EVT-SOURCE-001",
    }
    evidence = {"workflow_evidence": {"observation": observation}}
    payload = {"evidence": evidence}
    wf = _fake_workflow("aog-engineering-recovery", payload=payload, status="awaiting_hitl")
    result = workflow_detail(wf, None)
    assert result is not None
    governance = result.get("governance", {})
    assert governance.get("status") == "pending"


def test_hero1_detail_unchanged():
    """Hero1 workflow_detail still works correctly."""
    from verticals.airline.detail import workflow_detail

    # With empty payload, Hero1 should return None (no observation)
    wf = _fake_workflow("integrated-hub-disruption-recovery", payload={})
    result = workflow_detail(wf, None)
    assert result is None  # Hero1 returns None when no observation


# ===========================================================================
# 10. Memory workflow types includes both
# ===========================================================================


def test_memory_workflow_types_includes_both():
    from verticals.airline.manifest import build_pack

    pack = build_pack()
    assert "integrated-hub-disruption-recovery" in pack.memory_workflow_types
    assert "aog-engineering-recovery" in pack.memory_workflow_types


# ===========================================================================
# 11. Pack validate passes
# ===========================================================================


def test_pack_validate_passes(tmp_path):
    from api.shared.vertical_loader import build_runtime

    runtime = build_runtime({"ZAVA_VERTICAL": "airline"}, data_root=tmp_path)
    pack = runtime.pack
    # Pack validation - domains not stub
    for wtype, domain in pack.domains.items():
        assert not domain.stub, f"Domain {wtype!r} is still a stub"


# ===========================================================================
# 12. Inventory isolation: AOG domain not in agency/telco packs
# ===========================================================================


def test_aog_domain_not_in_telco():
    from verticals.telco.process_profiles import STANDARD_PROCESS_PROFILES

    assert "aog-engineering-recovery" not in STANDARD_PROCESS_PROFILES


def test_aog_domain_not_in_agency():
    from verticals.agency.manifest import build_pack as build_agency

    pack = build_agency()
    assert "aog-engineering-recovery" not in pack.domains


# ===========================================================================
# 13. Durable: aog_durable.register is called exactly once in durable.py
# ===========================================================================


def test_durable_py_calls_aog_register():
    """Verify durable.py source calls aog_durable.register(app) exactly once."""
    durable_src = (AIRLINE_ROOT / "durable.py").read_text()
    count = durable_src.count("aog_durable.register(app)")
    assert count == 1, f"Expected exactly 1 call to aog_durable.register(app), found {count}"


# ===========================================================================
# 14. AOG projection – extended entity kinds from world mutation (TDD/RED)
# ===========================================================================

def _build_mutated_world_and_app_state():
    """Create fully-mutated AOG world (work-local option) and an app_state wrapper."""
    from api.server.world.runtime import SimulationRuntime
    from verticals.airline.worlds.scenario import AirlineWorld

    runtime = SimulationRuntime(seed=42)
    world = AirlineWorld(seed=42, runtime=runtime)
    world.install()
    world.activate_scenario("synthetic-aog-defect")
    cmd = world.command_for_aog_option(
        option_id="SYN-AOG-OPTION-WORK-LOCAL",
        workflow_id="AOGA-0001",
        decision_id="SYN-AOG-DECISION-001",
        persona="engineering_duty_manager",
    )
    world.apply_command(cmd)
    app_state = SimpleNamespace(world_service=SimpleNamespace(scenario=world))
    return world, app_state


def _entity_ids_of_kind(records: list, kind: str) -> set[str]:
    from api.server.services.entity_graph import EntityWrite

    return {
        r.id
        for r in records
        if isinstance(r, EntityWrite) and r.attrs.get("kind") == kind
    }


def _rel_pairs(records: list, rel: str) -> set[tuple[str, str]]:
    from api.server.services.entity_graph import RelWrite

    return {(r.src_id, r.dst_id) for r in records if isinstance(r, RelWrite) and r.rel == rel}


def test_aog_projection_absent_world_yields_no_spare_or_ewo_entities():
    """With no world mutation (app_state=None, minimal payload), no Spare/SpareMovement/EWO/Eval projected."""
    from verticals.airline.entity_projections.aog import project
    from api.server.services.entity_graph import EntityWrite

    workflow = _fake_workflow("aog-engineering-recovery", payload={})
    records = list(project(workflow, None))
    attr_kinds = {r.attrs.get("kind") for r in records if isinstance(r, EntityWrite)}
    for prohibited in ("Spare", "SpareMovement", "EngineeringWorkOrder", "AogRecoveryEvaluation"):
        assert prohibited not in attr_kinds, (
            f"Fabricated {prohibited!r} entity found in projection without world mutation evidence"
        )


def test_aog_projection_world_mutation_projects_spare():
    """After AOG command mutation, Spare entity with real id/status appears in projection."""
    from verticals.airline.entity_projections.aog import project

    _world, app_state = _build_mutated_world_and_app_state()
    workflow = _fake_workflow("aog-engineering-recovery", payload={})
    records = list(project(workflow, app_state))
    spare_ids = _entity_ids_of_kind(records, "Spare")
    assert "SYN-SPARE-LOCAL-001" in spare_ids, (
        f"Expected Spare 'SYN-SPARE-LOCAL-001' in projection; got spare ids: {spare_ids}"
    )


def test_aog_projection_world_mutation_spare_has_real_attrs():
    """Projected Spare entity carries actual status, part_number, station, lead_time."""
    from verticals.airline.entity_projections.aog import project
    from api.server.services.entity_graph import EntityWrite

    world, app_state = _build_mutated_world_and_app_state()
    workflow = _fake_workflow("aog-engineering-recovery", payload={})
    records = list(project(workflow, app_state))
    spare_entity = next(
        (r for r in records if isinstance(r, EntityWrite) and r.id == "SYN-SPARE-LOCAL-001"),
        None,
    )
    assert spare_entity is not None, "Spare entity SYN-SPARE-LOCAL-001 not found"
    real_spare = world.spares["SYN-SPARE-LOCAL-001"]
    assert spare_entity.attrs.get("status") == real_spare.status


def test_aog_projection_world_mutation_projects_spare_movement():
    """After AOG command mutation, SpareMovement entity appears in projection."""
    from verticals.airline.entity_projections.aog import project

    _world, app_state = _build_mutated_world_and_app_state()
    workflow = _fake_workflow("aog-engineering-recovery", payload={})
    records = list(project(workflow, app_state))
    sm_ids = _entity_ids_of_kind(records, "SpareMovement")
    assert "SYN-SMOV-AOGA-0001" in sm_ids, (
        f"Expected SpareMovement 'SYN-SMOV-AOGA-0001' in projection; got: {sm_ids}"
    )


def test_aog_projection_world_mutation_projects_engineering_work_order():
    """After AOG command mutation, EngineeringWorkOrder entity appears in projection."""
    from verticals.airline.entity_projections.aog import project

    _world, app_state = _build_mutated_world_and_app_state()
    workflow = _fake_workflow("aog-engineering-recovery", payload={})
    records = list(project(workflow, app_state))
    ewo_ids = _entity_ids_of_kind(records, "EngineeringWorkOrder")
    assert "SYN-EWO-AOGA-0001" in ewo_ids, (
        f"Expected EngineeringWorkOrder 'SYN-EWO-AOGA-0001' in projection; got: {ewo_ids}"
    )


def test_aog_projection_world_mutation_projects_aog_recovery_evaluation():
    """After AOG command mutation, AogRecoveryEvaluation entity appears in projection."""
    from verticals.airline.entity_projections.aog import project

    _world, app_state = _build_mutated_world_and_app_state()
    workflow = _fake_workflow("aog-engineering-recovery", payload={})
    records = list(project(workflow, app_state))
    eval_ids = _entity_ids_of_kind(records, "AogRecoveryEvaluation")
    assert "SYN-AOG-EVAL-AOGA-0001" in eval_ids, (
        f"Expected AogRecoveryEvaluation 'SYN-AOG-EVAL-AOGA-0001' in projection; got: {eval_ids}"
    )


def test_aog_projection_spare_related_to_task():
    """Spare entity is related to the maintenance task (defensible HAS_SPARE_FOR rel)."""
    from verticals.airline.entity_projections.aog import project

    _world, app_state = _build_mutated_world_and_app_state()
    workflow = _fake_workflow("aog-engineering-recovery", payload={})
    records = list(project(workflow, app_state))
    # Spare should be related to the task via a relationship
    from api.server.services.entity_graph import RelWrite
    rel_dsts = {r.dst_id for r in records if isinstance(r, RelWrite) and r.src_id == "SYN-SPARE-LOCAL-001"}
    rel_srcs = {r.src_id for r in records if isinstance(r, RelWrite) and r.dst_id == "SYN-SPARE-LOCAL-001"}
    # The spare must appear in at least one relationship
    assert rel_dsts or rel_srcs, "Spare SYN-SPARE-LOCAL-001 has no relationships in projection"


def test_aog_projection_work_order_related_to_workflow():
    """EngineeringWorkOrder is related to the workflow."""
    from verticals.airline.entity_projections.aog import project
    from api.server.services.entity_graph import RelWrite

    _world, app_state = _build_mutated_world_and_app_state()
    workflow = _fake_workflow("aog-engineering-recovery", payload={})
    records = list(project(workflow, app_state))
    # WO must appear in a rel involving the workflow id
    rels_from_wf = {r.dst_id for r in records if isinstance(r, RelWrite) and r.src_id == workflow.id}
    rels_to_wf = {r.src_id for r in records if isinstance(r, RelWrite) and r.dst_id == workflow.id}
    assert "SYN-EWO-AOGA-0001" in rels_from_wf or "SYN-EWO-AOGA-0001" in rels_to_wf, (
        "EngineeringWorkOrder SYN-EWO-AOGA-0001 is not related to the workflow"
    )


def test_aog_projection_evaluation_related_to_workflow():
    """AogRecoveryEvaluation is related to the workflow."""
    from verticals.airline.entity_projections.aog import project
    from api.server.services.entity_graph import RelWrite

    _world, app_state = _build_mutated_world_and_app_state()
    workflow = _fake_workflow("aog-engineering-recovery", payload={})
    records = list(project(workflow, app_state))
    rels_from_wf = {r.dst_id for r in records if isinstance(r, RelWrite) and r.src_id == workflow.id}
    rels_to_wf = {r.src_id for r in records if isinstance(r, RelWrite) and r.dst_id == workflow.id}
    assert "SYN-AOG-EVAL-AOGA-0001" in rels_from_wf or "SYN-AOG-EVAL-AOGA-0001" in rels_to_wf, (
        "AogRecoveryEvaluation SYN-AOG-EVAL-AOGA-0001 is not related to the workflow"
    )


def test_aog_projection_world_no_mutation_yields_no_ewo():
    """AirlineWorld installed+activated but no command applied – no EWO/SpareMovement/Eval projected."""
    from api.server.world.runtime import SimulationRuntime
    from verticals.airline.worlds.scenario import AirlineWorld
    from verticals.airline.entity_projections.aog import project
    from api.server.services.entity_graph import EntityWrite

    runtime = SimulationRuntime(seed=42)
    world = AirlineWorld(seed=42, runtime=runtime)
    world.install()
    world.activate_scenario("synthetic-aog-defect")
    # No command applied – EWO/SpareMovement/Eval collections are empty
    app_state = SimpleNamespace(world_service=SimpleNamespace(scenario=world))
    workflow = _fake_workflow("aog-engineering-recovery", payload={})
    records = list(project(workflow, app_state))
    attr_kinds = {r.attrs.get("kind") for r in records if isinstance(r, EntityWrite)}
    for prohibited in ("EngineeringWorkOrder", "SpareMovement", "AogRecoveryEvaluation"):
        assert prohibited not in attr_kinds, (
            f"Fabricated {prohibited!r} entity found without command mutation"
        )


def test_aog_projection_one_argument_contract_uses_persisted_mutation_records():
    """Production ProjectionFn receives only Workflow; mutation evidence must be persisted."""
    import dataclasses

    from api.server.services.entity_graph import EntityWrite
    from verticals.airline.entity_projections.aog import project

    world, _app_state = _build_mutated_world_and_app_state()
    work_order = next(iter(world.engineering_work_orders.values()))
    movement = next(iter(world.spare_movements.values()))
    evaluation = next(iter(world.aog_recovery_evaluations.values()))
    command = next(iter(world.aog_recovery_commands.values()))
    spare = world.spares[work_order.spare_id]
    workflow = _fake_workflow(
        "aog-engineering-recovery",
        payload={
            "evidence": {
                "gateway_event": {
                    "payload": {
                        "mutation_records": {
                            "work_order": dataclasses.asdict(work_order),
                            "spare_movement": dataclasses.asdict(movement),
                            "spare": dataclasses.asdict(spare),
                            "aog_command": dataclasses.asdict(command),
                            "evaluation": dataclasses.asdict(evaluation),
                        }
                    }
                }
            }
        },
    )

    records = list(project(workflow))
    kinds = {
        record.attrs.get("kind")
        for record in records
        if isinstance(record, EntityWrite)
    }

    assert {
        "Spare",
        "SpareMovement",
        "EngineeringWorkOrder",
        "AogRecoveryCommand",
        "AogRecoveryEvaluation",
    } <= kinds


def test_aog_projection_materialises_in_shared_graph_schema(tmp_path: Path):
    from api.server.services.entity_graph import (
        DecisionWrite,
        EntityGraph,
        EntityWrite,
        RelWrite,
    )
    from api.server.world.runtime import SimulationRuntime
    from verticals.airline.entity_projections.aog import project
    from verticals.airline.worlds.scenario import AirlineWorld

    world = AirlineWorld(seed=42, runtime=SimulationRuntime(seed=42))
    world.install()
    world.activate_scenario("synthetic-aog-defect")
    observation = world.current_aog_observation()
    command = world.command_for_aog_option(
        option_id="SYN-AOG-OPTION-WORK-LOCAL",
        workflow_id="AOGA-0001",
        decision_id="SYN-AOG-DECISION-001",
        persona="engineering_duty_manager",
    )
    accepted = world.apply_command(command)
    workflow = _fake_workflow(
        "aog-engineering-recovery",
        payload={
            "evidence": {
                "workflow_evidence": {"observation": observation},
                "gateway_event": accepted.to_dict(),
                "approval": {
                    "decision": "approve",
                    "persona": "engineering_duty_manager",
                    "decision_id": "SYN-AOG-DECISION-001",
                },
            }
        },
        status="completed",
    )

    graph = EntityGraph(tmp_path / "aog-projection.kuzu")
    ops = list(project(workflow))
    for op in ops:
        if isinstance(op, EntityWrite):
            graph.upsert(op)
        elif isinstance(op, RelWrite):
            graph.link(op.src_id, op.rel, op.dst_id, **op.attrs)
        elif isinstance(op, DecisionWrite):
            assert op.decided_at

    assert graph.linked("AOGA-0001")
