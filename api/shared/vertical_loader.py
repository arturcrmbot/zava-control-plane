from __future__ import annotations

import os
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import replace
from functools import cache
from importlib import import_module
from pathlib import Path
from types import MappingProxyType

from api.shared.kernel_assets import KNOWN_CAPABILITIES, KNOWN_LENSES
from api.shared.vertical_pack import (
    VerticalPack,
    VerticalRuntime,
)


PACK_MODULES = {
    "agency": "verticals.agency.manifest",
    "telco": "verticals.telco.manifest",
}
LEGACY_WORLD_OWNERS = {"support": "agency", "telco": "telco"}
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SKILL_NAME = re.compile(r"^name:\s*[\"']?([^\"'\n]+)", re.MULTILINE)


def _normalise(value: str | None) -> str | None:
    cleaned = value.strip().lower() if value is not None else ""
    return cleaned or None


def select_vertical(environment: Mapping[str, str]) -> tuple[str, str | None]:
    explicit_vertical = _normalise(environment.get("ZAVA_VERTICAL"))
    world = _normalise(environment.get("ZAVA_WORLD"))
    name = explicit_vertical or LEGACY_WORLD_OWNERS.get(world or "") or "agency"
    if name not in PACK_MODULES:
        raise ValueError(f"unknown vertical {name!r}")
    return name, world


def resolve_data_root(environment: Mapping[str, str]) -> Path:
    raw = (
        _normalise(environment.get("ZAVA_DATA_DIR"))
        or _normalise(environment.get("PORTAL_DATA_DIR"))
        or "data/runtime"
    )
    return Path(raw).expanduser()


def load_pack(name: str) -> VerticalPack:
    module = import_module(PACK_MODULES[name])
    return module.build_pack()


def _freeze_mapping(values: Mapping) -> MappingProxyType:
    return MappingProxyType(dict(values))


def freeze_pack(pack: VerticalPack) -> VerticalPack:
    worlds = {
        name: replace(
            world,
            scales=_freeze_mapping(world.scales),
            responders=_freeze_mapping(world.responders),
        )
        for name, world in pack.worlds.items()
    }
    phase_aliases = {
        workflow_type: _freeze_mapping(aliases)
        for workflow_type, aliases in pack.ui.phase_aliases.items()
    }
    ui = replace(
        pack.ui,
        theme=_freeze_mapping(pack.ui.theme),
        phase_aliases=_freeze_mapping(phase_aliases),
    )
    return replace(
        pack,
        domains=_freeze_mapping(pack.domains),
        organisation_functions=_freeze_mapping(pack.organisation_functions),
        agents=_freeze_mapping(pack.agents),
        authority=_freeze_mapping(pack.authority),
        worlds=_freeze_mapping(worlds),
        projections=_freeze_mapping(pack.projections),
        ui=ui,
    )


def validate_pack(pack: VerticalPack) -> None:
    if pack.name not in PACK_MODULES:
        raise ValueError(f"vertical {pack.name!r} is not in PACK_MODULES")
    if pack.default_world is not None and pack.default_world not in pack.worlds:
        raise ValueError(
            f"default world {pack.default_world!r} is not owned by "
            f"vertical {pack.name!r}"
        )
    for world_name, world in pack.worlds.items():
        if world_name != world.name:
            raise ValueError(
                f"vertical {pack.name!r} world key {world_name!r} "
                f"does not match registration {world.name!r}"
            )
        if world.default_scale not in world.scales:
            raise ValueError(
                f"vertical {pack.name!r} world {world_name!r} has unknown "
                f"default scale {world.default_scale!r}"
            )

    for workflow_type, domain in pack.domains.items():
        if workflow_type != domain.workflow_type:
            raise ValueError(
                f"vertical {pack.name!r} domain key {workflow_type!r} "
                f"does not match workflow type {domain.workflow_type!r}"
            )

    owners: dict[str, list[str]] = {}
    for function_name, function in pack.organisation_functions.items():
        if function_name != function.name:
            raise ValueError(
                f"vertical {pack.name!r} function key {function_name!r} "
                f"does not match registration {function.name!r}"
            )
        for workflow_type in function.owns_domains:
            owners.setdefault(workflow_type, []).append(function_name)

    duplicate_owners = {
        workflow_type: function_names
        for workflow_type, function_names in owners.items()
        if len(function_names) > 1
    }
    owned_domains = set(owners)
    expected_domains = set(pack.domains)
    if owned_domains != expected_domains or duplicate_owners:
        raise ValueError(
            f"vertical {pack.name!r} function ownership mismatch: "
            f"missing={sorted(expected_domains - owned_domains)}, "
            f"unknown={sorted(owned_domains - expected_domains)}, "
            f"duplicates={duplicate_owners}"
        )

    responder_orchestrators = {
        responder.orchestrator
        for world in pack.worlds.values()
        for responder in world.responders.values()
    }
    valid_orchestrators = (
        set(pack.durable_functions.orchestrators) | responder_orchestrators
    )
    for workflow_type, domain in pack.domains.items():
        if not domain.stub and domain.orchestrator_name not in valid_orchestrators:
            raise ValueError(
                f"vertical {pack.name!r} missing orchestrator "
                f"{domain.orchestrator_name!r} for domain {workflow_type!r}"
            )

    for workflow_type in pack.ramp_workflow_types:
        domain = pack.domains.get(workflow_type)
        if domain is None or domain.stub:
            raise ValueError(
                f"vertical {pack.name!r} has unknown ramp workflow "
                f"{workflow_type!r}"
            )
    for workflow_type in pack.projections:
        if workflow_type not in pack.domains:
            raise ValueError(
                f"vertical {pack.name!r} has unknown projection workflow "
                f"{workflow_type!r}"
            )
    for workflow_type in pack.memory_workflow_types:
        if workflow_type not in pack.domains:
            raise ValueError(
                f"vertical {pack.name!r} has unknown memory workflow "
                f"{workflow_type!r}"
            )

    unknown_capabilities = sorted(
        set(pack.ui.capabilities) - KNOWN_CAPABILITIES
    )
    if unknown_capabilities:
        raise ValueError(
            f"vertical {pack.name!r} has unknown UI capabilities "
            f"{unknown_capabilities}"
        )
    unknown_lenses = sorted(set(pack.ui.lenses) - KNOWN_LENSES)
    if unknown_lenses:
        raise ValueError(
            f"vertical {pack.name!r} has unknown UI lenses {unknown_lenses}"
        )

    skill_names: set[str] = set()
    for root in pack.skill_roots:
        if not root.is_dir():
            raise ValueError(
                f"vertical {pack.name!r} has missing skill root {str(root)!r}"
            )
        for skill_file in root.glob("*/SKILL.md"):
            match = _SKILL_NAME.search(skill_file.read_text(encoding="utf-8"))
            skill_names.add(
                match.group(1).strip() if match else skill_file.parent.name
            )
    for domain in pack.domains.values():
        for skill_name in domain.skills:
            if skill_name not in skill_names:
                raise ValueError(
                    f"vertical {pack.name!r} domain {domain.workflow_type!r} "
                    f"references missing skill {skill_name!r}"
                )

    def validate_persona(node, function_name: str) -> None:
        if node.role == "__legacy__":
            return
        if not any(
            (root / node.role / "SKILL.md").is_file()
            for root in pack.personae_roots
        ):
            raise ValueError(
                f"vertical {pack.name!r} function {function_name!r} "
                f"references missing persona {node.role!r}"
            )
        for child in node.manages:
            validate_persona(child, function_name)

    for function_name, function in pack.organisation_functions.items():
        validate_persona(function.persona_hierarchy, function_name)

    for module_name in pack.mcp_modules:
        module_path = _REPO_ROOT.joinpath(*module_name.split(".")).with_suffix(
            ".py"
        )
        if not module_path.is_file():
            raise ValueError(
                f"vertical {pack.name!r} has missing MCP module "
                f"{module_name!r}"
            )

    for policy_path in pack.policy_sources:
        if not policy_path.is_file():
            raise ValueError(
                f"vertical {pack.name!r} has missing policy source "
                f"{str(policy_path)!r}"
            )

    for recordings_dir in pack.recordings.curated_dirs:
        if not recordings_dir.is_dir():
            raise ValueError(
                f"vertical {pack.name!r} has missing recordings directory "
                f"{str(recordings_dir)!r}"
            )
        for recording_path in recordings_dir.glob("*.jsonl"):
            workflow_types: set[str] = set()
            for line in recording_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                entry = json.loads(line)
                event = entry.get("event") or {}
                workflow_type = event.get("workflow_type")
                if workflow_type:
                    workflow_types.add(str(workflow_type))
            for workflow_type in workflow_types:
                if workflow_type not in pack.domains:
                    raise ValueError(
                        f"vertical {pack.name!r} recording workflow "
                        f"{workflow_type!r} is not active: "
                        f"{recording_path.name}"
                    )


def build_runtime(
    environment: Mapping[str, str],
    *,
    data_root: Path | None = None,
    pack_loader: Callable[[str], VerticalPack] = load_pack,
) -> VerticalRuntime:
    name, requested_world = select_vertical(environment)
    pack = freeze_pack(pack_loader(name))
    validate_pack(pack)
    world_name = requested_world or pack.default_world
    if world_name is not None and world_name not in pack.worlds:
        raise ValueError(
            f"world {world_name!r} is not owned by vertical {pack.name!r}"
        )

    requested_scale = _normalise(environment.get("ZAVA_WORLD_SCALE"))
    if requested_scale is not None and world_name is None:
        raise ValueError("ZAVA_WORLD_SCALE requires an active world")
    world_scale_name = None
    if world_name is not None:
        world = pack.worlds[world_name]
        world_scale_name = requested_scale or world.default_scale
        if world_scale_name not in world.scales:
            raise ValueError(
                f"unknown scale {world_scale_name!r} for world {world_name!r}"
            )

    root = data_root or resolve_data_root(environment)
    return VerticalRuntime(
        pack=pack,
        world_name=world_name,
        world_scale_name=world_scale_name,
        data_dir=root / pack.name,
        fingerprint=f"{pack.name}:{pack.manifest_version}",
    )


@cache
def active_runtime() -> VerticalRuntime:
    return build_runtime(os.environ, pack_loader=load_pack)
