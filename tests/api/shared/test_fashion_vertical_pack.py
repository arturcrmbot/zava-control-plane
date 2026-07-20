from pathlib import Path

from api.shared.vertical_loader import build_runtime
from verticals.fashion.process_profiles import FASHION_PROCESS_PROFILES


EXPECTED_FUNCTIONS = {
    "merchandising-planning",
    "supply-chain-fulfilment",
    "marketplace-operations",
    "customer-returns",
}
EXPECTED_PERSONAS = {
    "merchandising_director",
    "inventory_allocation_manager",
    "supply_chain_director",
    "fulfilment_manager",
    "marketplace_operations_director",
    "returns_operations_manager",
}
EXPECTED_SKILLS = {
    skill
    for profile in FASHION_PROCESS_PROFILES.values()
    for skill in profile.skills
}


def _runtime(tmp_path):
    return build_runtime(
        {"ZAVA_VERTICAL": "fashion"},
        data_root=tmp_path,
    )


def test_fashion_pack_is_automatically_discovered_and_complete(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    pack = runtime.pack

    assert pack.name == "fashion"
    assert runtime.world_name == "fashion"
    assert runtime.world_scale_name == "demo"
    assert set(pack.domains) == set(FASHION_PROCESS_PROFILES)
    assert all(not domain.stub for domain in pack.domains.values())
    assert set(pack.organisation_functions) == EXPECTED_FUNCTIONS
    assert set(pack.agents) == EXPECTED_SKILLS
    assert set(pack.personas) == EXPECTED_PERSONAS
    assert set(pack.authority) == EXPECTED_PERSONAS
    assert set(pack.projections) == set(FASHION_PROCESS_PROFILES)
    assert set(pack.memory_workflow_types) == set(FASHION_PROCESS_PROFILES)
    assert pack.ui.theme["label"] == "Fashion Retail"


def test_fashion_world_routes_each_workflow_to_its_owned_orchestrator(
    tmp_path,
) -> None:
    pack = _runtime(tmp_path).pack
    world = pack.worlds["fashion"]
    routes = {route.objective_type: route for route in world.objective_routes}

    assert set(routes) == {
        profile.objective_type
        for profile in FASHION_PROCESS_PROFILES.values()
    }
    assert set(world.responders) == set(routes)
    for profile in FASHION_PROCESS_PROFILES.values():
        route = routes[profile.objective_type]
        responder = world.responders[profile.objective_type]
        assert route.sensor_id == profile.sensor_id
        assert route.allowed_command_types == frozenset({profile.command_type})
        assert route.success_event_types == frozenset({profile.success_event})
        assert responder.workflow_type == profile.workflow_type
        assert responder.orchestrator == profile.orchestrator_name


def test_fashion_manifest_owns_every_business_asset_root(tmp_path) -> None:
    pack = _runtime(tmp_path).pack

    assert all(
        path.is_relative_to(pack.root)
        for path in (
            *pack.policy_sources,
            *pack.personae_roots,
            *pack.skill_roots,
            *pack.recordings.curated_dirs,
        )
    )
    assert all(
        module.startswith("verticals.fashion.mcp_tools.")
        for module in pack.mcp_modules
    )
    assert Path(pack.root).name == "fashion"
