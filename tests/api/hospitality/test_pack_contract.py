"""Hospitality pack contract: discovery, validation and structural inventory."""
from __future__ import annotations

import json
from pathlib import Path

from api.shared.vertical_loader import (
    build_runtime,
    discover_pack_modules,
    validate_pack,
)

ROOT = Path(__file__).resolve().parents[3]
PACK = ROOT / "verticals" / "hospitality"

WORKFLOWS = (
    "hotel-operations-recovery",
    "room-readiness-coordination",
    "asset-maintenance-response",
    "guest-service-recovery",
    "occupancy-pressure-response",
    "workforce-demand-balancing",
    "food-and-beverage-readiness",
    "energy-anomaly-response",
)
SKILLS = {
    "hotel-impact-assessor",
    "hotel-network-recovery-planner",
    "room-readiness-coordinator",
    "maintenance-response-planner",
    "guest-recovery-advisor",
    "occupancy-pressure-advisor",
    "workforce-balancing-advisor",
    "food-service-readiness-advisor",
    "energy-anomaly-advisor",
}
PERSONAE = {
    "hotel_general_manager",
    "regional_operations_manager",
    "hotel_operations_director",
    "maintenance_manager",
    "estates_director",
    "guest_recovery_manager",
    "commercial_director",
    "workforce_planning_manager",
    "people_operations_director",
    "food_beverage_operations_manager",
    "sustainability_operations_manager",
    "sustainability_director",
}
TOOLS = {
    "hospitality_read_hotel_operations",
    "hospitality_read_room_readiness",
    "hospitality_read_asset_maintenance",
    "hospitality_read_guest_recovery",
    "hospitality_read_occupancy_pressure",
    "hospitality_read_workforce_demand",
    "hospitality_read_food_beverage_readiness",
    "hospitality_read_energy_anomaly",
}


def _pack(tmp_path: Path):
    return build_runtime(
        {"ZAVA_VERTICAL": "hospitality"},
        data_root=tmp_path,
    ).pack


def test_hospitality_pack_is_discovered_and_validates(tmp_path: Path) -> None:
    assert discover_pack_modules()["hospitality"] == (
        "verticals.hospitality.manifest"
    )

    runtime = build_runtime(
        {"ZAVA_VERTICAL": "hospitality"},
        data_root=tmp_path,
    )

    assert runtime.pack.name == "hospitality"
    assert runtime.pack.display_name == "Hospitality"
    assert runtime.pack.manifest_version == "1"
    assert runtime.world_name == "hospitality"
    assert runtime.world_scale_name == "demo"
    validate_pack(runtime.pack)


def test_pack_declares_exactly_eight_non_stub_workflows(tmp_path: Path) -> None:
    pack = _pack(tmp_path)

    assert tuple(pack.domains) == WORKFLOWS
    assert all(not domain.stub for domain in pack.domains.values())
    assert len({d.orchestrator_name for d in pack.domains.values()}) == 8
    assert tuple(pack.memory_workflow_types) == WORKFLOWS
    assert set(pack.projections) == set(WORKFLOWS)


def test_process_profiles_match_domains_commands_and_authority() -> None:
    from verticals.hospitality.authority import HOSPITALITY_AUTHORITY
    from verticals.hospitality.commands import CMD_HOTEL_RECOVERY_EXECUTE
    from verticals.hospitality.domains import HOSPITALITY_DOMAINS
    from verticals.hospitality.process_profiles import (
        HOSPITALITY_PROCESS_PROFILES,
    )

    assert tuple(HOSPITALITY_PROCESS_PROFILES) == WORKFLOWS
    hero = HOSPITALITY_PROCESS_PROFILES["hotel-operations-recovery"]
    assert hero.maturity == "hero"
    assert hero.sensor_id == "sensor:hotel_operations_risk"
    assert hero.objective_type == "hotel_operations_recovery"
    assert hero.command_type == CMD_HOTEL_RECOVERY_EXECUTE
    assert hero.success_event == "hotel.recovery.executed"

    sensors = {p.sensor_id for p in HOSPITALITY_PROCESS_PROFILES.values()}
    objectives = {p.objective_type for p in HOSPITALITY_PROCESS_PROFILES.values()}
    successes = {p.success_event for p in HOSPITALITY_PROCESS_PROFILES.values()}
    assert len(sensors) == len(objectives) == len(successes) == 8

    for workflow_type, profile in HOSPITALITY_PROCESS_PROFILES.items():
        domain = HOSPITALITY_DOMAINS[workflow_type]
        gate = domain.hitl_gates[0]
        assert profile.orchestrator == domain.orchestrator_name
        assert profile.function == domain.function
        assert profile.hitl_persona == gate.persona
        assert profile.hitl_event == gate.external_event
        assert profile.hitl_persona in HOSPITALITY_AUTHORITY
        assert profile.skill in domain.skills


def test_skills_personae_and_tools_are_pack_owned(tmp_path: Path) -> None:
    pack = _pack(tmp_path)

    skill_dirs = {p.parent.name for p in (PACK / "skills").glob("*/SKILL.md")}
    assert skill_dirs == SKILLS
    persona_dirs = {
        p.parent.name for p in (PACK / "personae").glob("*/SKILL.md")
    }
    assert persona_dirs == PERSONAE
    assert set(pack.personas) == PERSONAE

    declared = {
        skill
        for domain in pack.domains.values()
        for skill in domain.skills
    }
    assert declared == SKILLS

    module = (PACK / "mcp_tools" / "operations.py").read_text(encoding="utf-8")
    for tool in TOOLS:
        assert f'name="{tool}"' in module

    policy = (PACK / "policies" / "tools.yaml").read_text(encoding="utf-8")
    for tool in TOOLS:
        assert f"id: {tool}" in policy


def test_world_registration_scene_and_routes(tmp_path: Path) -> None:
    pack = _pack(tmp_path)

    world = pack.worlds["hospitality"]
    assert pack.default_world == "hospitality"
    assert "demo" in world.scales
    assert len(world.objective_routes) == 8
    assert len({r.objective_type for r in world.objective_routes}) == 8
    assert len(world.responders) == 8
    assert {r.workflow_type for r in world.responders.values()} == set(WORKFLOWS)
    for route in world.objective_routes:
        assert route.failure_event_types == frozenset({"command.rejected"})

    scene = world.scene
    assert scene is not None
    assert [location["id"] for location in scene["locations"]] == [
        "HOTEL-RIVERSIDE-CENTRAL",
        "HOTEL-AIRPORT-NORTH",
        "HOTEL-CITY-GATE",
        "HOTEL-HARBOUR-VIEW",
        "HOTEL-MESSE-CENTRAL",
        "HOTEL-RHINE-PARK",
    ]
    event_types = {m["event_type"] for m in scene["event_mappings"]}
    assert {
        "hotel.operations-risk.detected",
        "sensor.tripped",
        "hotel.recovery.executed",
    } <= event_types


def test_no_cross_pack_business_imports() -> None:
    other_packs = ("fashion", "travel", "telco", "agency", "electronics")
    for path in sorted(PACK.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for other in other_packs:
            assert f"verticals.{other}" not in text, (
                f"{path} imports cross-pack module verticals.{other}"
            )


def test_generation_manifest_records_every_pack_file() -> None:
    ledger = json.loads(
        (PACK / "generation-manifest.json").read_text(encoding="utf-8")
    )
    recorded = {record["path"] for record in ledger["records"]}
    for record in ledger["records"]:
        assert (ROOT / record["path"]).exists(), (
            f"generation-manifest records a missing path {record['path']}"
        )
    for required in (
        "verticals/hospitality/manifest.py",
        "verticals/hospitality/process_profiles.py",
        "verticals/hospitality/worlds.py",
        "verticals/hospitality/durable.py",
        "verticals/hospitality/lifecycle.py",
        "verticals/hospitality/projections.py",
        "verticals/hospitality/ui/world-scene.json",
    ):
        assert required in recorded
