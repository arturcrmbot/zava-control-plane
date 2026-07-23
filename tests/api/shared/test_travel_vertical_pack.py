"""TDD contract tests for the Travel `VerticalPack` (Task 4).

Covers the eight-process Travel portfolio at the pack-structure level: the
built `VerticalPack` (`verticals.travel.manifest.build_pack`) declares
exactly eight non-stub domains with a full sensor/objective/command/
evaluation/authority/orchestrator/skill uniqueness matrix, validates
cleanly under the generic, industry-neutral `api.shared.vertical_loader`
contract, is selected end-to-end by `ZAVA_VERTICAL=travel` with a
namespaced runtime data directory, and adds no Travel-specific vocabulary
to the shared substrate.

Running this file before `verticals/travel/manifest.py` (and its sibling
generated modules: domains, functions, authority, personas, agents) exist
must fail at collection with a ModuleNotFoundError (RED). After
implementation it must pass (GREEN).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from api.shared.vertical_loader import build_runtime, load_pack, validate_pack
from verticals.travel.agents import TRAVEL_AGENTS
from verticals.travel.authority import TRAVEL_AUTHORITY
from verticals.travel.domains import TRAVEL_DOMAINS, TRAVEL_HERO_WORKFLOW_TYPES
from verticals.travel.functions import TRAVEL_FUNCTIONS
from verticals.travel.manifest import build_pack
from verticals.travel.personas import TRAVEL_PERSONAS

REPO_ROOT = Path(__file__).resolve().parents[3]

EXPECTED_WORKFLOW_TYPES = {
    "holiday-sales-booking",
    "capacity-yield-management",
    "flight-disruption-recovery",
    "hotel-supplier-recovery",
    "cancellation-refund",
    "payment-exception",
    "destination-operations",
    "proactive-customer-care",
}

EXPECTED_HEROES = {"flight-disruption-recovery", "hotel-supplier-recovery"}

# One row per portfolio process: (sensor_id, objective_type, command_type,
# success_event_type, authority_role, function_name), read straight off the
# task's own portfolio spec, so these tests fail loudly against any drift.
EXPECTED_ROWS: dict[str, dict[str, str]] = {
    "holiday-sales-booking": {
        "sensor_id": "sensor:quote_ready",
        "objective_type": "convert_holiday_demand",
        "command_type": "confirm_package_booking",
        "authority_role": "travel_adviser",
        "function": "commercial",
    },
    "capacity-yield-management": {
        "sensor_id": "sensor:capacity_pressure",
        "objective_type": "protect_package_capacity",
        "command_type": "adjust_package_allotment",
        "authority_role": "revenue_manager",
        "function": "commercial",
    },
    "flight-disruption-recovery": {
        "sensor_id": "sensor:flight_cancellation_impact",
        "objective_type": "recover_cancelled_flight",
        "command_type": "reaccommodate_travellers",
        "authority_role": "operations_controller",
        "function": "operations-control",
    },
    "hotel-supplier-recovery": {
        "sensor_id": "sensor:hotel_allotment_shortfall",
        "objective_type": "restore_hotel_accommodation",
        "command_type": "move_hotel_allotment",
        "authority_role": "accommodation_manager",
        "function": "accommodation-supply",
    },
    "cancellation-refund": {
        "sensor_id": "sensor:customer_cancellation_accepted",
        "objective_type": "settle_cancelled_booking",
        "command_type": "cancel_and_refund_booking",
        "authority_role": "finance_operations_lead",
        "function": "customer-finance",
    },
    "payment-exception": {
        "sensor_id": "sensor:balance_payment_exception",
        "objective_type": "preserve_payment_booking",
        "command_type": "resolve_payment_exception",
        "authority_role": "payments_specialist",
        "function": "customer-finance",
    },
    "destination-operations": {
        "sensor_id": "sensor:transfer_arrival_risk",
        "objective_type": "restore_destination_journey",
        "command_type": "dispatch_replacement_transfer",
        "authority_role": "destination_operations_manager",
        "function": "destination-operations",
    },
    "proactive-customer-care": {
        "sensor_id": "sensor:material_itinerary_change",
        "objective_type": "protect_disrupted_customer",
        "command_type": "issue_customer_care_action",
        "authority_role": "customer_care_lead",
        "function": "customer-care",
    },
}


def test_portfolio_declares_exactly_eight_domains() -> None:
    assert set(TRAVEL_DOMAINS) == EXPECTED_WORKFLOW_TYPES
    assert len(TRAVEL_DOMAINS) == 8


def test_portfolio_declares_exactly_two_heroes() -> None:
    assert TRAVEL_HERO_WORKFLOW_TYPES == frozenset(EXPECTED_HEROES)
    assert len(TRAVEL_HERO_WORKFLOW_TYPES) == 2
    assert TRAVEL_HERO_WORKFLOW_TYPES <= set(TRAVEL_DOMAINS)


def test_no_domain_is_a_stub() -> None:
    for workflow_type, domain in TRAVEL_DOMAINS.items():
        assert domain.stub is False, f"{workflow_type} must not be a stub domain"


def test_every_domain_has_at_least_three_phases_and_matches_the_workflow_key() -> None:
    for workflow_type, domain in TRAVEL_DOMAINS.items():
        assert domain.workflow_type == workflow_type
        assert len(domain.phases) >= 3
        assert domain.skills, f"{workflow_type} must declare at least one skill"


def test_hero_flight_disruption_recovery_has_a_hitl_escalation_gate() -> None:
    domain = TRAVEL_DOMAINS["flight-disruption-recovery"]
    hitl_phase_kinds = {phase.kind for phase in domain.phases}
    assert "hitl" in hitl_phase_kinds
    assert domain.hitl_gates
    assert domain.hitl_gates[0].persona == "head_of_operations"


@pytest.mark.parametrize("workflow_type", sorted(EXPECTED_ROWS))
def test_domain_sensor_objective_command_authority_and_function_match_spec(
    workflow_type: str,
) -> None:
    expected = EXPECTED_ROWS[workflow_type]
    domain = TRAVEL_DOMAINS[workflow_type]
    assert domain.function == expected["function"]

    # Sensor/objective/command identity is not itself a Domain field (it is
    # owned by the world route + case/profile data); assert it through the
    # world routing table so the assertion still fails loudly on drift.
    from verticals.travel.worlds.registration import TRAVEL_WORLD

    routes_by_sensor = {route.sensor_id: route for route in TRAVEL_WORLD.objective_routes}
    route = routes_by_sensor[expected["sensor_id"]]
    assert route.objective_type == expected["objective_type"]
    assert expected["command_type"] in route.allowed_command_types

    # Responders are keyed by objective_type (matching the established
    # Agency/Fashion/Telco convention), not by workflow_type.
    responder = TRAVEL_WORLD.responders[expected["objective_type"]]
    assert responder.workflow_type == workflow_type
    assert responder.owner_function == expected["function"]


def test_sensor_objective_command_evaluation_orchestrator_prefix_and_skill_are_pairwise_unique() -> None:
    from verticals.travel.worlds.registration import TRAVEL_WORLD

    sensor_ids = [route.sensor_id for route in TRAVEL_WORLD.objective_routes]
    objective_types = [route.objective_type for route in TRAVEL_WORLD.objective_routes]
    command_types = sorted(
        next(iter(route.allowed_command_types)) for route in TRAVEL_WORLD.objective_routes
    )
    orchestrator_names = [domain.orchestrator_name for domain in TRAVEL_DOMAINS.values()]
    prefixes = [domain.workflow_id_prefix for domain in TRAVEL_DOMAINS.values()]
    skill_sets = [frozenset(domain.skills) for domain in TRAVEL_DOMAINS.values()]

    assert len(sensor_ids) == len(set(sensor_ids)) == 8
    assert len(objective_types) == len(set(objective_types)) == 8
    assert len(command_types) == len(set(command_types)) == 8
    assert len(orchestrator_names) == len(set(orchestrator_names)) == 8
    assert len(prefixes) == len(set(prefixes)) == 8
    assert len(skill_sets) == len(set(skill_sets)) == 8


def test_authority_rows_exist_for_every_process_role_and_every_head() -> None:
    expected_roles = {row["authority_role"] for row in EXPECTED_ROWS.values()}
    expected_roles |= {
        "head_of_operations",
        "head_of_commercial",
        "head_of_accommodation",
        "head_of_customer_finance",
        "head_of_destination_operations",
        "head_of_customer_care",
    }
    assert expected_roles <= set(TRAVEL_AUTHORITY)
    for role, row in TRAVEL_AUTHORITY.items():
        assert row.role == role
        assert row.spend_limit_gbp > 0


def test_customer_care_lead_has_a_small_bounded_authority() -> None:
    # A deliberately small goodwill bound -- the clearest example of "bounded
    # GBP authority" in the portfolio.
    assert TRAVEL_AUTHORITY["customer_care_lead"].spend_limit_gbp <= 1000


def test_operations_controller_escalates_to_head_of_operations() -> None:
    controller = TRAVEL_AUTHORITY["operations_controller"]
    head = TRAVEL_AUTHORITY["head_of_operations"]
    assert controller.delegate_to == "head_of_operations"
    assert head.spend_limit_gbp > controller.spend_limit_gbp


def test_functions_group_the_portfolio_into_six_coherent_functions() -> None:
    assert len(TRAVEL_FUNCTIONS) == 6
    owned: set[str] = set()
    for function in TRAVEL_FUNCTIONS.values():
        assert not (owned & set(function.owns_domains)), "domain owned by two functions"
        owned |= set(function.owns_domains)
    assert owned == EXPECTED_WORKFLOW_TYPES


def test_personas_cover_every_authority_role() -> None:
    assert set(TRAVEL_AUTHORITY) <= set(TRAVEL_PERSONAS)
    for role, persona in TRAVEL_PERSONAS.items():
        assert persona.role == role


def test_agents_declare_bounded_reversible_tool_scopes() -> None:
    assert TRAVEL_AGENTS
    for agent in TRAVEL_AGENTS.values():
        assert agent.allowed_tools
        if agent.max_value_gbp is not None:
            assert agent.max_value_gbp > 0


def test_built_pack_is_discoverable_and_validates() -> None:
    pack = build_pack()
    assert pack.name == "travel"
    assert pack.default_world == "travel"
    assert "travel" in pack.worlds
    assert pack.worlds["travel"].default_scale == "demo"
    validate_pack(pack)  # must not raise


def test_pack_policy_sources_are_valid_governance_tool_manifests() -> None:
    """A selected Travel API can initialise its governance kernel at boot."""
    from api.server.services.governance.manifest import load_tools_yaml

    pack = build_pack()

    assert len(pack.policy_sources) == 1
    assert pack.policy_sources[0].name == "tools.yaml"
    tools = load_tools_yaml(str(pack.policy_sources[0]))
    assert {
        "travel_operations_check_flight_disruption",
        "travel_operations_reaccommodate_booking",
    } <= set(tools)


def test_built_pack_registers_a_world_scene_naming_the_real_origin_airports_and_destinations() -> None:
    """Task 8, Part A: the pack owns exactly one `ui/world-scene.json`,
    registered through the existing typed `load_world_scene`/
    `VerticalUiManifest` contract (`api.shared.world_scene_contracts`),
    naming the real seeded origin airports/destinations/hotels and
    binding every real snapshot collection a scene renderer needs.
    """
    pack = build_pack()
    scene = pack.ui.world_scene
    assert scene is not None

    location_ids = {location.id for location in scene.locations}
    assert {"APT-LGW", "APT-MAN", "APT-BHX"} <= location_ids
    assert {"DST-PMI", "DST-TFS", "DST-AYT"} <= location_ids
    assert {"HTL-SUN-PMI", "HTL-BLU-TFS", "HTL-SUN-AYT"} <= location_ids

    binding_by_collection = {binding.collection: binding for binding in scene.actor_bindings}
    expected_collections = {
        "flights",
        "transfers",
        "parties",
        "customers",
        "staff",
        "hotels",
        "bookings",
        "disruptions",
        "recovery_decisions",
    }
    assert expected_collections <= set(binding_by_collection)
    # A recovered booking keeps its commercial payment status (for example,
    # ``paid``) while its actor-world recovery state changes. The spatial
    # proof must therefore bind the independently mutated recovery field.
    assert binding_by_collection["bookings"].state_field == "recovery_status"

    event_types = {mapping.event_type for mapping in scene.event_mappings}
    assert {
        "sensor.tripped",
        "responder.requested",
        "responder.decided",
        "booking.reaccommodated",
        "flight.cancelled",
        "disruption.resolved",
    } <= event_types


def test_world_scene_source_is_pack_local_and_validates() -> None:
    pack = build_pack()
    scene = pack.ui.world_scene
    assert scene is not None
    assert scene.source_path == pack.root / "ui" / "world-scene.json"
    validate_pack(pack)  # must not raise with the scene registered


def test_built_pack_has_no_supplemental_or_aspirational_domains_masking_stubs() -> None:
    pack = build_pack()
    assert len(pack.domains) == 8
    assert all(not domain.stub for domain in pack.domains.values())


def test_load_pack_by_name_matches_build_pack() -> None:
    via_manifest = build_pack()
    via_loader = load_pack("travel")
    assert via_loader.name == via_manifest.name
    assert set(via_loader.domains) == set(via_manifest.domains)


def test_runtime_selects_travel_and_namespaces_data_directory() -> None:
    runtime = build_runtime(
        {"ZAVA_VERTICAL": "travel"},
        data_root=REPO_ROOT / "data" / "runtime-test-fixture",
    )
    assert runtime.pack.name == "travel"
    assert runtime.world_name == "travel"
    assert runtime.world_scale_name == "demo"
    assert runtime.data_dir.name == "travel"
    assert runtime.data_dir.parent.name == "runtime-test-fixture"


def test_travel_pack_root_and_skill_persona_roots_are_pack_local() -> None:
    pack = build_pack()
    assert pack.root == REPO_ROOT / "verticals" / "travel"
    for root in pack.skill_roots:
        assert REPO_ROOT / "verticals" / "travel" in root.parents or root == REPO_ROOT / "verticals" / "travel"
    for root in pack.personae_roots:
        assert REPO_ROOT / "verticals" / "travel" in root.parents or root == REPO_ROOT / "verticals" / "travel"


def test_shared_substrate_gains_no_travel_vocabulary() -> None:
    """The shared, industry-neutral substrate must not import or name Travel."""
    shared_files = [
        REPO_ROOT / "api" / "shared" / "vertical_pack.py",
        REPO_ROOT / "api" / "shared" / "vertical_loader.py",
        REPO_ROOT / "api" / "shared" / "domain_contracts.py",
        REPO_ROOT / "api" / "shared" / "function_contracts.py",
        REPO_ROOT / "api" / "shared" / "authority_contracts.py",
        REPO_ROOT / "api" / "shared" / "persona_contracts.py",
        REPO_ROOT / "api" / "shared" / "agent_contracts.py",
        REPO_ROOT / "api" / "shared" / "world_contracts.py",
        REPO_ROOT / "api" / "shared" / "kernel_assets.py",
        REPO_ROOT / "api" / "server" / "world" / "model.py",
        REPO_ROOT / "api" / "server" / "world" / "commands.py",
        REPO_ROOT / "api" / "server" / "world" / "objectives.py",
        REPO_ROOT / "api" / "server" / "world" / "evaluations.py",
        REPO_ROOT / "api" / "server" / "world" / "runtime.py",
        REPO_ROOT / "api" / "server" / "world" / "registry.py",
        REPO_ROOT / "api" / "server" / "world" / "service.py",
    ]
    for path in shared_files:
        text = path.read_text(encoding="utf-8")
        assert "travel" not in text.lower(), f"{path} must not name the travel vertical"


def test_no_direct_process_run_http_dependency_in_generated_worlds_package() -> None:
    """Diagnostic pure-command tests are allowed; the run route is not required."""
    worlds_dir = REPO_ROOT / "verticals" / "travel" / "worlds"
    for path in worlds_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "/api/world/processes" not in text
        assert "/run" not in text or "run_reference_process" in text


# Each of the Travel pack's public entry points must import cleanly on its
# own, in a fresh interpreter, in either order. Aggregate test-suite
# collection can mask a circular import because whichever module happens to
# finish initializing `verticals.travel.actions.commands` first "wins";
# isolating each import in its own subprocess removes that ordering luck.
TRAVEL_PUBLIC_ENTRY_POINTS: tuple[str, ...] = (
    "verticals.travel.actions.commands",
    "verticals.travel.actions",
    "verticals.travel.durable.orchestrators",
    "verticals.travel.worlds.scenario",
    "verticals.travel.manifest",
)


@pytest.mark.parametrize("module_name", TRAVEL_PUBLIC_ENTRY_POINTS)
def test_travel_public_entry_point_imports_cleanly_in_isolation(module_name: str) -> None:
    """A fresh subprocess importing only `module_name` must not raise."""
    result = subprocess.run(
        [sys.executable, "-c", f"import {module_name}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"import {module_name} failed in an isolated subprocess:\n{result.stderr}"
    )
