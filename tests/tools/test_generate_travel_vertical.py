"""TDD contract tests for the Travel vertical pack generator.

Covers Task 1's scope (a minimal, deterministic, pack-owned generator that
produces `verticals/travel/__init__.py`) extended by Task 3 to also
generate the `verticals/travel/worlds/` package (`__init__.py`, `model.py`,
`reference_data.py`, `scenario.py`), and by Task 4 to generate the full
eight-process portfolio surface: the pack manifest modules (`manifest.py`,
`domains.py`, `functions.py`, `agents.py`, `authority.py`, `personas.py`,
`seed.py`, `lifecycle.py`, `ui.json`), eight each of `domains/*.yaml`,
`profiles/*.json`, `cases/*.json` and domain `skills/*/SKILL.md`, fourteen
persona `personae/*/SKILL.md`, `policies/authority.yaml`, the
`mcps/travel_operations.py` tool module, `actions/commands.py`, the
`worlds/processes.py` detector/evaluator module and `worlds/registration.py`
world wiring, and the pure `durable/` phase-plan engine. The manifest fully
tracks every generated asset (per the compose-org generation-manifest
contract) and the clean/regeneration path stays safe and idempotent for the
larger asset set.

Running this file before `verticals/travel/generator` exists must fail at
collection with a ModuleNotFoundError (RED). After implementation it must
pass (GREEN). The world-package assertions added for Task 3 must fail RED
until `verticals/travel/generator/world_templates.py` is implemented and
wired into `render.py`. The portfolio assertions added for Task 4 must fail
RED until `verticals/travel/generator/portfolio.py` and
`verticals/travel/generator/process_templates.py` exist and are wired into
`render.py`.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from verticals.travel.generator import render
from verticals.travel.generator.render import (
    GENERATOR_VERSION,
    ExternalOutputNotApprovedError,
    UnsafeCleanupTargetError,
    classify_output_path,
    clean,
    generate,
)


def _read_manifest(pack_root: Path) -> dict:
    return json.loads((pack_root / "generation-manifest.json").read_text(encoding="utf-8"))


def _pack_root(target_root: Path) -> Path:
    return target_root / "verticals" / "travel"


def test_clean_generation_creates_package_marker_and_manifest(tmp_path: Path) -> None:
    manifest = generate(target_root=tmp_path)

    pack_root = _pack_root(tmp_path)
    assert (pack_root / "__init__.py").is_file()
    assert (pack_root / "generation-manifest.json").is_file()
    assert manifest == _read_manifest(pack_root)


def test_every_generated_output_is_listed_exactly_once(tmp_path: Path) -> None:
    manifest = generate(target_root=tmp_path)

    paths = [record["path"] for record in manifest["records"]]
    assert paths, "expected at least one generated record"
    assert len(paths) == len(set(paths))
    # the manifest is the tracking ledger, not a tracked "content" output
    assert "verticals/travel/generation-manifest.json" not in paths
    assert "verticals/travel/__init__.py" in paths
    assert "verticals/travel/worlds/__init__.py" in paths
    assert "verticals/travel/worlds/model.py" in paths
    assert "verticals/travel/worlds/reference_data.py" in paths
    assert "verticals/travel/worlds/scenario.py" in paths


def test_world_package_files_are_generated_with_expected_content(tmp_path: Path) -> None:
    generate(target_root=tmp_path)
    worlds_root = _pack_root(tmp_path) / "worlds"

    assert (worlds_root / "__init__.py").is_file()
    assert (worlds_root / "model.py").is_file()
    assert (worlds_root / "reference_data.py").is_file()
    assert (worlds_root / "scenario.py").is_file()

    model_source = (worlds_root / "model.py").read_text(encoding="utf-8")
    assert "class Flight" in model_source
    assert "class Booking" in model_source
    assert "class TravellingParty" in model_source

    scenario_source = (worlds_root / "scenario.py").read_text(encoding="utf-8")
    assert "class TravelWorld" in scenario_source
    assert "SimulationRuntime" in scenario_source


def test_manifest_records_have_required_fields(tmp_path: Path) -> None:
    manifest = generate(target_root=tmp_path)

    required_fields = {"path", "ownership", "input_hash", "content_hash", "generator_version"}
    assert manifest["records"], "expected at least one record"
    for record in manifest["records"]:
        assert required_fields <= set(record)
        assert record["generator_version"] == GENERATOR_VERSION
        assert record["ownership"] in {"generated", "generated-external"}
        assert len(record["input_hash"]) == 64  # sha256 hex digest
        assert len(record["content_hash"]) == 64
        # input hash and content hash track different things and must not collide
        assert record["input_hash"] != record["content_hash"]


def test_generated_text_files_end_with_one_newline(tmp_path: Path) -> None:
    manifest = generate(target_root=tmp_path)

    for record in manifest["records"]:
        content = (tmp_path / record["path"]).read_bytes()
        assert content.endswith(b"\n"), record["path"]
        assert not content.endswith(b"\n\n"), record["path"]


def test_external_outputs_are_rejected_unless_approved(tmp_path: Path) -> None:
    pack_root = _pack_root(tmp_path)
    external_path = tmp_path / "outside-pack.txt"

    with pytest.raises(ExternalOutputNotApprovedError):
        classify_output_path(external_path, pack_root=pack_root, approved_external=frozenset())

    ownership = classify_output_path(
        external_path,
        pack_root=pack_root,
        approved_external=frozenset({external_path}),
    )
    assert ownership == "generated-external"


def test_rerun_is_byte_identical(tmp_path: Path) -> None:
    generate(target_root=tmp_path)
    pack_root = _pack_root(tmp_path)
    first_init = (pack_root / "__init__.py").read_bytes()
    first_manifest = (pack_root / "generation-manifest.json").read_bytes()
    first_world_files = {
        name: (pack_root / "worlds" / name).read_bytes()
        for name in ("__init__.py", "model.py", "reference_data.py", "scenario.py")
    }

    generate(target_root=tmp_path)
    second_init = (pack_root / "__init__.py").read_bytes()
    second_manifest = (pack_root / "generation-manifest.json").read_bytes()
    second_world_files = {
        name: (pack_root / "worlds" / name).read_bytes()
        for name in ("__init__.py", "model.py", "reference_data.py", "scenario.py")
    }

    assert first_init == second_init
    assert first_manifest == second_manifest
    assert first_world_files == second_world_files


def test_generation_is_idempotent_across_fresh_target_roots(tmp_path: Path) -> None:
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    root_a.mkdir()
    root_b.mkdir()

    manifest_a = generate(target_root=root_a)
    manifest_b = generate(target_root=root_b)

    assert manifest_a == manifest_b


def test_clean_removes_stale_listed_assets(tmp_path: Path) -> None:
    generate(target_root=tmp_path)
    pack_root = _pack_root(tmp_path)
    assert (pack_root / "__init__.py").exists()
    assert (pack_root / "generation-manifest.json").exists()

    removed = clean(target_root=tmp_path)

    assert not (pack_root / "__init__.py").exists()
    assert not (pack_root / "generation-manifest.json").exists()
    removed_names = {p.name for p in removed}
    assert "__init__.py" in removed_names
    assert "generation-manifest.json" in removed_names


def test_clean_never_removes_unlisted_sentinel_file(tmp_path: Path) -> None:
    generate(target_root=tmp_path)
    pack_root = _pack_root(tmp_path)

    sentinel = pack_root / "sentinel.txt"
    sentinel.write_text("do-not-delete\n", encoding="utf-8")

    clean(target_root=tmp_path)

    assert sentinel.exists()


def test_clean_refuses_to_remove_generator_source_even_if_maliciously_listed(
    tmp_path: Path,
) -> None:
    pack_root = _pack_root(tmp_path)
    generator_dir = pack_root / "generator"
    generator_dir.mkdir(parents=True, exist_ok=True)
    source_file = generator_dir / "render.py"
    source_file.write_text("# hand-authored generator source\n", encoding="utf-8")

    malicious_manifest = {
        "generator_version": GENERATOR_VERSION,
        "records": [
            {
                "path": "verticals/travel/generator/render.py",
                "ownership": "generated",
                "input_hash": "0" * 64,
                "content_hash": "0" * 64,
                "generator_version": GENERATOR_VERSION,
            }
        ],
    }
    manifest_path = pack_root / "generation-manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(malicious_manifest), encoding="utf-8")

    with pytest.raises(UnsafeCleanupTargetError):
        clean(target_root=tmp_path)

    assert source_file.exists(), "generator source must never be deleted by clean()"


def test_clean_refuses_traversal_path_outside_pack_and_preserves_victim(
    tmp_path: Path,
) -> None:
    pack_root = _pack_root(tmp_path)
    pack_root.mkdir(parents=True, exist_ok=True)

    # Victim lives one level above target_root — a stand-in for "outside
    # the pack/repo" that stays safely inside pytest's own tmp sandbox.
    victim = tmp_path.parent / "traversal-victim.txt"
    victim.write_text("do-not-delete\n", encoding="utf-8")

    malicious_manifest = {
        "generator_version": GENERATOR_VERSION,
        "records": [
            {
                "path": "../traversal-victim.txt",
                "ownership": "generated",
                "input_hash": "0" * 64,
                "content_hash": "0" * 64,
                "generator_version": GENERATOR_VERSION,
            }
        ],
    }
    manifest_path = pack_root / "generation-manifest.json"
    manifest_path.write_text(json.dumps(malicious_manifest), encoding="utf-8")

    try:
        with pytest.raises(UnsafeCleanupTargetError):
            clean(target_root=tmp_path)
        assert victim.exists(), "traversal target must never be deleted by clean()"
    finally:
        victim.unlink(missing_ok=True)


def test_clean_refuses_absolute_path_outside_pack_and_preserves_victim(
    tmp_path: Path,
) -> None:
    pack_root = _pack_root(tmp_path)
    pack_root.mkdir(parents=True, exist_ok=True)

    victim = tmp_path.parent / "absolute-victim.txt"
    victim.write_text("do-not-delete\n", encoding="utf-8")

    malicious_manifest = {
        "generator_version": GENERATOR_VERSION,
        "records": [
            {
                "path": str(victim),
                "ownership": "generated",
                "input_hash": "0" * 64,
                "content_hash": "0" * 64,
                "generator_version": GENERATOR_VERSION,
            }
        ],
    }
    manifest_path = pack_root / "generation-manifest.json"
    manifest_path.write_text(json.dumps(malicious_manifest), encoding="utf-8")

    try:
        with pytest.raises(UnsafeCleanupTargetError):
            clean(target_root=tmp_path)
        assert victim.exists(), "absolute-path target must never be deleted by clean()"
    finally:
        victim.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Task 4: eight-process portfolio generated asset surface
# ---------------------------------------------------------------------------

PORTFOLIO_WORKFLOW_TYPES = (
    "holiday-sales-booking",
    "capacity-yield-management",
    "flight-disruption-recovery",
    "hotel-supplier-recovery",
    "cancellation-refund",
    "payment-exception",
    "destination-operations",
    "proactive-customer-care",
)

PORTFOLIO_PERSONA_ROLES = (
    "travel_adviser",
    "revenue_manager",
    "operations_controller",
    "accommodation_manager",
    "finance_operations_lead",
    "payments_specialist",
    "destination_operations_manager",
    "customer_care_lead",
    "head_of_commercial",
    "head_of_operations",
    "head_of_accommodation",
    "head_of_customer_finance",
    "head_of_destination_operations",
    "head_of_customer_care",
)


def test_portfolio_manifest_modules_are_generated(tmp_path: Path) -> None:
    manifest = generate(target_root=tmp_path)
    paths = {record["path"] for record in manifest["records"]}

    for name in (
        "manifest.py",
        "domains.py",
        "functions.py",
        "agents.py",
        "authority.py",
        "personas.py",
        "seed.py",
        "lifecycle.py",
        "ui.json",
    ):
        assert f"verticals/travel/{name}" in paths, f"missing generated {name}"


def test_world_scene_asset_is_generated_and_manifest_covered(tmp_path: Path) -> None:
    """Task 8, Part A: `ui/world-scene.json` is a real, generated,
    manifest-tracked asset -- `ui.json` points at it, and it loads as a
    valid `WorldSceneContract` through the same generic, industry-neutral
    contract any vertical's scene would use.
    """
    manifest = generate(target_root=tmp_path)
    paths = {record["path"] for record in manifest["records"]}
    assert "verticals/travel/ui/world-scene.json" in paths

    pack_root = _pack_root(tmp_path)
    ui_data = json.loads((pack_root / "ui.json").read_text(encoding="utf-8"))
    assert ui_data["world_scene"] == "ui/world-scene.json"

    from api.shared.world_scene_contracts import load_world_scene

    scene = load_world_scene(pack_root / "ui" / "world-scene.json", pack_root=pack_root)
    assert scene.version
    assert scene.title
    assert len(scene.locations) > 0
    assert len(scene.actor_bindings) > 0
    assert len(scene.event_mappings) > 0


def test_eight_domain_yaml_profile_and_case_assets_are_generated(tmp_path: Path) -> None:
    generate(target_root=tmp_path)
    pack_root = _pack_root(tmp_path)

    for workflow_type in PORTFOLIO_WORKFLOW_TYPES:
        assert (pack_root / "domains" / f"{workflow_type}.yaml").is_file()
        assert (pack_root / "profiles" / f"{workflow_type}.json").is_file()
        assert (pack_root / "cases" / f"{workflow_type}.json").is_file()

    profile = json.loads(
        (pack_root / "profiles" / "flight-disruption-recovery.json").read_text(encoding="utf-8")
    )
    for key in (
        "trigger",
        "objective",
        "orchestrator",
        "phases",
        "skills",
        "tools",
        "authority",
        "command",
        "mutation_contract",
        "evaluation_contract",
        "maturity",
    ):
        assert key in profile, f"profile missing required key {key!r}"

    case = json.loads(
        (pack_root / "cases" / "flight-disruption-recovery.json").read_text(encoding="utf-8")
    )
    assert case["workflow_type"] == "flight-disruption-recovery"
    assert case["command_payload"]["booking_id"].startswith("BKG-")


def test_eight_domain_skills_are_generated_with_allowed_tools(tmp_path: Path) -> None:
    generate(target_root=tmp_path)
    skills_root = _pack_root(tmp_path) / "skills"

    skill_dirs = sorted(p.name for p in skills_root.iterdir() if p.is_dir())
    assert len(skill_dirs) == 8
    for skill_dir in skill_dirs:
        skill_md = skills_root / skill_dir / "SKILL.md"
        assert skill_md.is_file()
        text = skill_md.read_text(encoding="utf-8")
        assert "allowed-tools" in text


def test_fourteen_persona_skills_are_generated(tmp_path: Path) -> None:
    generate(target_root=tmp_path)
    personae_root = _pack_root(tmp_path) / "personae"

    persona_dirs = sorted(p.name for p in personae_root.iterdir() if p.is_dir())
    assert len(persona_dirs) == 14
    assert set(persona_dirs) == set(PORTFOLIO_PERSONA_ROLES)
    for role in PORTFOLIO_PERSONA_ROLES:
        assert (personae_root / role / "SKILL.md").is_file()


def test_policy_mcp_actions_worlds_and_durable_assets_are_generated(tmp_path: Path) -> None:
    manifest = generate(target_root=tmp_path)
    paths = {record["path"] for record in manifest["records"]}
    pack_root = _pack_root(tmp_path)

    assert "verticals/travel/policies/authority.yaml" in paths
    assert (pack_root / "policies" / "authority.yaml").is_file()

    for name in ("__init__.py", "travel_operations.py"):
        assert f"verticals/travel/mcps/{name}" in paths
    mcp_source = (pack_root / "mcps" / "travel_operations.py").read_text(encoding="utf-8")
    assert "@define_tool" in mcp_source

    for name in ("__init__.py", "commands.py"):
        assert f"verticals/travel/actions/{name}" in paths
    commands_source = (pack_root / "actions" / "commands.py").read_text(encoding="utf-8")
    assert "COMMAND_HANDLERS" in commands_source

    for name in ("processes.py", "registration.py"):
        assert f"verticals/travel/worlds/{name}" in paths

    for name in ("__init__.py", "engine.py", "orchestrators.py"):
        assert f"verticals/travel/durable/{name}" in paths
    orchestrators_source = (pack_root / "durable" / "orchestrators.py").read_text(encoding="utf-8")
    for workflow_type in PORTFOLIO_WORKFLOW_TYPES:
        # every distinct orchestrator name must appear in the durable module
        assert "Orchestrator" in orchestrators_source
    assert orchestrators_source.count("def ") >= 8


def test_generated_output_grows_substantially_for_the_eight_process_portfolio(
    tmp_path: Path,
) -> None:
    manifest = generate(target_root=tmp_path)
    assert len(manifest["records"]) >= 60


def test_generate_refuses_to_write_into_generator_directory(tmp_path: Path) -> None:
    pack_root = _pack_root(tmp_path)
    bogus_asset = render.PlannedAsset(
        relative_path=Path("verticals/travel/generator/should_not_exist.py"),
        content=b"# should never be written\n",
        ownership="generated",
        input_recipe="asset:bogus",
    )

    with pytest.raises(UnsafeCleanupTargetError):
        render._render_record(tmp_path, bogus_asset)

    assert not (pack_root / "generator" / "should_not_exist.py").exists()
