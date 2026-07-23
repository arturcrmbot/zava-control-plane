from __future__ import annotations

import importlib
import json
from pathlib import Path

from api.shared.vertical_loader import build_runtime, discover_pack_modules, validate_pack


ROOT = Path(__file__).resolve().parents[3]
PACK = ROOT / "verticals" / "fashion"
WORKFLOWS = (
    "inventory-rebalancing",
    "demand-spike-response",
    "promotion-readiness",
    "markdown-governance",
    "supplier-delay-recovery",
    "fulfilment-exception-resolution",
    "marketplace-seller-exception",
    "returns-disposition",
)
FUNCTION_OWNERS = {
    "merchandising-planning": WORKFLOWS[:4],
    "supply-chain-fulfilment": WORKFLOWS[4:6],
    "marketplace-operations": WORKFLOWS[6:7],
    "customer-returns": WORKFLOWS[7:],
}
PERSONAS = {
    "merchandising_director",
    "inventory_allocation_manager",
    "supply_chain_director",
    "fulfilment_manager",
    "marketplace_operations_director",
    "returns_operations_manager",
}
SKILLS = {
    "inventory-imbalance-analysis",
    "inventory-rebalance-planner",
    "promotion-readiness-assessor",
    "markdown-option-advisor",
    "supplier-recovery-planner",
    "fulfilment-resolution-advisor",
    "seller-exception-assessor",
    "returns-disposition-advisor",
}


def test_fashion_pack_is_discovered_and_validates(tmp_path: Path) -> None:
    assert discover_pack_modules()["fashion"] == "verticals.fashion.manifest"

    runtime = build_runtime(
        {"ZAVA_VERTICAL": "fashion"},
        data_root=tmp_path,
    )

    assert runtime.pack.name == "fashion"
    assert runtime.pack.display_name == "Fashion Retail"
    assert runtime.world_name == "fashion"
    assert runtime.world_scale_name == "demo"
    assert runtime.fingerprint.startswith("fashion:")
    validate_pack(runtime.pack)


def test_fashion_declares_exactly_eight_non_stub_workflows(tmp_path: Path) -> None:
    pack = build_runtime(
        {"ZAVA_VERTICAL": "fashion"},
        data_root=tmp_path,
    ).pack

    assert tuple(pack.domains) == WORKFLOWS
    assert all(not domain.stub for domain in pack.domains.values())
    assert len({domain.orchestrator_name for domain in pack.domains.values()}) == 8
    assert all(domain.phases for domain in pack.domains.values())
    assert pack.domains["inventory-rebalancing"].phases[-1].name == "Verify Outcome"


def test_functions_personas_authority_and_skills_are_pack_owned(
    tmp_path: Path,
) -> None:
    pack = build_runtime(
        {"ZAVA_VERTICAL": "fashion"},
        data_root=tmp_path,
    ).pack

    assert {
        name: function.owns_domains
        for name, function in pack.organisation_functions.items()
    } == FUNCTION_OWNERS
    assert set(pack.personas) == PERSONAS
    assert set(pack.authority) == PERSONAS
    assert all(path.is_relative_to(PACK) for path in pack.personae_roots)
    assert all(path.is_relative_to(PACK) for path in pack.skill_roots)
    assert {
        path.parent.name
        for root in pack.skill_roots
        for path in root.glob("*/SKILL.md")
    } == SKILLS


def test_each_workflow_has_distinct_operational_contract(tmp_path: Path) -> None:
    pack = build_runtime(
        {"ZAVA_VERTICAL": "fashion"},
        data_root=tmp_path,
    ).pack
    profiles = importlib.import_module("verticals.fashion.process_profiles")
    cases = importlib.import_module("verticals.fashion.reference_cases")
    actions = importlib.import_module("verticals.fashion.reference_actions")
    world = pack.worlds["fashion"]

    assert tuple(profiles.FASHION_PROCESS_PROFILES) == WORKFLOWS
    assert tuple(cases.FASHION_REFERENCE_CASES) == WORKFLOWS
    assert tuple(actions.FASHION_REFERENCE_ACTIONS) == WORKFLOWS
    assert len({profile.sensor_id for profile in profiles.FASHION_PROCESS_PROFILES.values()}) == 8
    assert len({profile.command_type for profile in profiles.FASHION_PROCESS_PROFILES.values()}) == 8
    assert {route.sensor_id for route in world.objective_routes} == {
        profile.sensor_id for profile in profiles.FASHION_PROCESS_PROFILES.values()
    }
    assert set(world.responders) == {
        profile.objective_type for profile in profiles.FASHION_PROCESS_PROFILES.values()
    }
    assert set(pack.projections) == set(WORKFLOWS)
    assert set(pack.memory_workflow_types) == set(WORKFLOWS)


def test_pack_has_one_valid_recording_per_workflow(tmp_path: Path) -> None:
    pack = build_runtime(
        {"ZAVA_VERTICAL": "fashion"},
        data_root=tmp_path,
    ).pack
    recordings = sorted((PACK / "recordings").glob("*.jsonl"))

    assert len(recordings) == 8
    observed: set[str] = set()
    for path in recordings:
        entries = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert entries
        workflow_types = {
            entry["event"]["workflow_type"]
            for entry in entries
            if entry.get("event", {}).get("workflow_type")
        }
        assert len(workflow_types) == 1
        observed.update(workflow_types)
    assert observed == set(WORKFLOWS)
    validate_pack(pack)


def test_org_brief_preserves_signed_research_and_vision() -> None:
    brief = (PACK / "org-brief.yaml").read_text(encoding="utf-8")

    for signed_term in (
        "UK/EU multi-brand retailer",
        "owned",
        "concession",
        "marketplace",
        "inventory-rebalancing",
        "seed: 42",
        "autonomous",
        "seller_review: PENDING",
    ):
        assert signed_term in brief


def test_fashion_python_never_imports_other_verticals() -> None:
    leaked: list[str] = []
    for path in PACK.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if "verticals.agency" in source or "verticals.telco" in source:
            leaked.append(str(path.relative_to(ROOT)))

    assert leaked == []


def test_governance_manifest_declares_every_fashion_mcp_tool() -> None:
    from api.server.services.governance.manifest import load_tools_yaml

    tools = load_tools_yaml(str(PACK / "policies" / "tools.yaml"))

    assert set(tools) == {
        "fashion_read_inventory",
        "fashion_prepare_inventory_transfer",
        "fashion_assess_promotion",
        "fashion_prepare_markdown_recommendation",
        "fashion_prepare_supplier_recovery",
        "fashion_prepare_fulfilment_resolution",
        "fashion_prepare_seller_suppression",
        "fashion_prepare_return_disposition",
    }
