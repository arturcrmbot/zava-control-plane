from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from importlib import import_module
import json

import pytest

from api.shared.domain_contracts import Domain, Phase
from api.shared.function_contracts import Function, PersonaTree
from api.shared.vertical_loader import validate_pack
from api.shared.vertical_pack import (
    DurableFunctionRegistration,
    VerticalUiManifest,
)
from api.shared.world_scene_contracts import load_world_scene
from tests.api.shared.vertical_pack_fakes import make_test_pack


def test_domain_contract_is_immutable() -> None:
    contracts = import_module("api.shared.domain_contracts")
    domain = contracts.Domain(
        workflow_type="demo",
        display_name="Demo",
        workflow_id_prefix="DEMO",
        orchestrator_name="DemoOrchestrator",
        operator_surface="demo",
        phases=(contracts.Phase("Intake", "deterministic"),),
        hitl_gates=(),
        skills=(),
    )

    with pytest.raises(FrozenInstanceError):
        domain.function = "ops"


def test_world_registration_declares_named_scales_and_responders() -> None:
    contracts = import_module("api.shared.world_contracts")
    scale = contracts.WorldScaleProfile(
        name="demo",
        build_scenario=lambda _runtime: None,
        default_minutes_per_second=10.0,
    )
    world = contracts.WorldPackRegistration(
        name="demo-world",
        scales={"demo": scale},
        default_scale="demo",
        objective_routes=(),
        responders={},
    )

    assert world.scales["demo"] is scale
    assert world.default_scale == "demo"
    assert world.responders == {}


def test_durable_registration_loads_the_selected_module_lazily() -> None:
    marker = object()
    registration = DurableFunctionRegistration(
        load_module=lambda: marker,
        orchestrators=frozenset(),
        activities=frozenset(),
    )

    assert registration.load_module() is marker


def _domain() -> Domain:
    return Domain(
        workflow_type="demo",
        display_name="Demo",
        workflow_id_prefix="DEMO",
        orchestrator_name="DemoOrchestrator",
        operator_surface="demo",
        phases=(Phase("Intake", "deterministic"),),
        hitl_gates=(),
        skills=(),
    )


def _function(*owned_domains: str) -> Function:
    return Function(
        name="ops",
        display="Operations",
        operator_surface="ops",
        owns_domains=owned_domains,
        ambient_agents=(),
        kpis=(),
        persona_hierarchy=PersonaTree(role="__legacy__"),
    )


def _pack_with_domain(tmp_path):
    return replace(
        make_test_pack("agency", tmp_path),
        domains={"demo": _domain()},
        organisation_functions={"ops": _function("demo")},
        durable_functions=DurableFunctionRegistration(
            load_module=lambda: None,
            orchestrators=frozenset({"DemoOrchestrator"}),
            activities=frozenset(),
        ),
    )


def test_validation_rejects_domain_key_mismatch(tmp_path) -> None:
    pack = _pack_with_domain(tmp_path)
    pack = replace(pack, domains={"wrong": _domain()})

    with pytest.raises(ValueError, match="domain key 'wrong'"):
        validate_pack(pack)


def test_validation_rejects_function_ownership_mismatch(tmp_path) -> None:
    pack = _pack_with_domain(tmp_path)
    pack = replace(pack, organisation_functions={})

    with pytest.raises(ValueError, match="function ownership mismatch"):
        validate_pack(pack)


def test_validation_rejects_missing_domain_orchestrator(tmp_path) -> None:
    pack = _pack_with_domain(tmp_path)
    pack = replace(
        pack,
        durable_functions=DurableFunctionRegistration(
            load_module=lambda: None,
            orchestrators=frozenset(),
            activities=frozenset(),
        ),
    )

    with pytest.raises(ValueError, match="missing orchestrator 'DemoOrchestrator'"):
        validate_pack(pack)


def test_validation_rejects_unknown_runtime_registrations(tmp_path) -> None:
    pack = _pack_with_domain(tmp_path)

    with pytest.raises(ValueError, match="unknown ramp workflow 'missing'"):
        validate_pack(replace(pack, ramp_workflow_types=("missing",)))
    with pytest.raises(ValueError, match="unknown projection workflow 'missing'"):
        validate_pack(replace(pack, projections={"missing": lambda _workflow: ()}))
    with pytest.raises(ValueError, match="unknown memory workflow 'missing'"):
        validate_pack(replace(pack, memory_workflow_types=("missing",)))


def test_validation_rejects_unknown_ui_vocabulary(tmp_path) -> None:
    pack = _pack_with_domain(tmp_path)

    with pytest.raises(ValueError, match="unknown UI capabilities"):
        validate_pack(
            replace(
                pack,
                ui=VerticalUiManifest(
                    capabilities=frozenset({"mystery"}),
                    lenses=(),
                    theme={},
                    phase_aliases={},
                ),
            )
        )
    with pytest.raises(ValueError, match="unknown UI lenses"):
        validate_pack(
            replace(
                pack,
                ui=VerticalUiManifest(
                    capabilities=frozenset(),
                    lenses=("mystery",),
                    theme={},
                    phase_aliases={},
                ),
            )
        )


def test_validation_rejects_missing_pack_assets(tmp_path) -> None:
    pack = _pack_with_domain(tmp_path)
    domain = replace(_domain(), skills=("missing-skill",))
    pack = replace(pack, domains={"demo": domain})

    with pytest.raises(ValueError, match="missing skill 'missing-skill'"):
        validate_pack(pack)

    missing_persona = replace(
        pack,
        domains={"demo": _domain()},
        organisation_functions={
            "ops": replace(
                _function("demo"),
                persona_hierarchy=PersonaTree(role="missing-persona"),
            )
        },
    )
    with pytest.raises(ValueError, match="missing persona 'missing-persona'"):
        validate_pack(missing_persona)

    with pytest.raises(ValueError, match="missing MCP module 'missing.module'"):
        validate_pack(
            replace(
                _pack_with_domain(tmp_path),
                mcp_modules=("missing.module",),
            )
        )


def test_validation_rejects_missing_policy_and_foreign_recording(tmp_path) -> None:
    pack = _pack_with_domain(tmp_path)
    with pytest.raises(ValueError, match="missing policy source"):
        validate_pack(
            replace(pack, policy_sources=(tmp_path / "missing.yaml",))
        )

    recordings = tmp_path / "recordings"
    recordings.mkdir()
    (recordings / "foreign.jsonl").write_text(
        json.dumps(
            {
                "ts_offset_ms": 0,
                "event": {
                    "type": "workflow.started",
                    "workflow_type": "foreign",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="recording workflow 'foreign'"):
        validate_pack(
            replace(
                pack,
                recordings=replace(
                    pack.recordings,
                    curated_dirs=(recordings,),
                ),
            )
        )


def _write_scene_source(root, relative: str = "ui/world-scene.json"):
    data = {
        "version": "1",
        "title": "Demo Scene",
        "locations": [{"id": "hub", "label": "Hub", "x": 0.1, "y": 0.1}],
        "actor_bindings": [
            {
                "collection": "units",
                "kind": "unit",
                "id_field": "id",
                "state_field": "status",
                "location_field": "current_hub_id",
            }
        ],
        "event_mappings": [
            {
                "event_type": "unit.moved",
                "animation_type": "move",
                "actor_id_field": "payload.unit_id",
            }
        ],
    }
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_validation_accepts_a_pack_owned_world_scene(tmp_path) -> None:
    pack = _pack_with_domain(tmp_path)
    source_path = _write_scene_source(pack.root)
    scene = load_world_scene(source_path, pack_root=pack.root)
    pack = replace(pack, ui=replace(pack.ui, world_scene=scene))

    validate_pack(pack)


def test_validation_rejects_world_scene_missing_from_disk(tmp_path) -> None:
    pack = _pack_with_domain(tmp_path)
    source_path = _write_scene_source(pack.root)
    scene = load_world_scene(source_path, pack_root=pack.root)
    source_path.unlink()
    pack = replace(pack, ui=replace(pack.ui, world_scene=scene))

    with pytest.raises(ValueError, match="missing world scene source"):
        validate_pack(pack)


def test_validation_rejects_world_scene_outside_pack_root(tmp_path) -> None:
    pack = _pack_with_domain(tmp_path)
    other_root = tmp_path / "elsewhere"
    source_path = _write_scene_source(other_root)
    scene = load_world_scene(source_path, pack_root=other_root)
    pack = replace(pack, ui=replace(pack.ui, world_scene=scene))

    with pytest.raises(ValueError, match="outside pack root"):
        validate_pack(pack)


def test_validation_rejects_unresolved_skill_tool(tmp_path) -> None:
    skills = tmp_path / "skills"
    skill_dir = skills / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: demo-skill\n"
        "description: demo\n"
        "allowed-tools: missing_tool\n"
        "---\n",
        encoding="utf-8",
    )
    pack = _pack_with_domain(tmp_path)
    pack = replace(
        pack,
        domains={
            "demo": replace(_domain(), skills=("demo-skill",))
        },
        skill_roots=(skills,),
    )

    with pytest.raises(ValueError, match="unresolved tool 'missing_tool'"):
        validate_pack(pack)

    validate_pack(
        replace(
            pack,
            external_capabilities=frozenset({"missing_tool"}),
        )
    )
