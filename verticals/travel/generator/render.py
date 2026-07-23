"""Deterministic asset renderer for the Travel vertical pack.

This module owns *generation*, not runtime behaviour: it renders the files
that live under `verticals/travel/` and tracks every one of them in
`verticals/travel/generation-manifest.json`, per the compose-org
generation-manifest contract:

- every generated asset is recorded exactly once, with its path, ownership
  classification, input hash, content hash, and generator version;
- outputs outside the pack directory are rejected unless explicitly
  approved (`classify_output_path`);
- generation is deterministic and idempotent — rerunning against the same
  target root produces byte-identical output;
- `clean()` removes only what the manifest lists (plus the manifest file
  itself), and refuses to ever touch anything under a `generator/`
  directory, since that is hand-authored source, never a generation target.

Task 1 rendered only the package marker. Task 3 extended `_planned_assets`
to also render the `verticals/travel/worlds/` package (a deterministic,
synthetic world built on `api.server.world.runtime.SimulationRuntime`)
from string templates in `world_templates.py`. Task 4 extends it again to
render the full eight-process portfolio surface: the pack manifest
modules (`manifest.py`, `domains.py`, `functions.py`, `authority.py`,
`personas.py`, `agents.py`, `seed.py`, `lifecycle.py`, `ui.json`), the
per-process assets (`domains/*.yaml`, `profiles/*.json`, `cases/*.json`,
`skills/*/SKILL.md`), the fourteen persona skills
(`personae/*/SKILL.md`), the authority policy document
(`policies/authority.yaml`), the command dispatcher
(`actions/__init__.py`, `actions/commands.py`), the world routing table
(`worlds/processes.py`, `worlds/registration.py`), the MCP tool module
(`mcps/__init__.py`, `mcps/travel_operations.py`) and the pure durable
process engine (`durable/__init__.py`, `durable/engine.py`,
`durable/orchestrators.py`). Later tasks may extend `_planned_assets`
further after their own failing tests.
"""
from __future__ import annotations

import hashlib
import json
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from verticals.travel.generator.commands_templates import ACTIONS_INIT_PY, ACTIONS_COMMANDS_PY
from verticals.travel.generator.durable_templates import (
    DURABLE_INIT_PY,
    ENGINE_PY,
    render_orchestrators_py,
    render_travel_durable_functions_py,
)
from verticals.travel.generator.knowledge_templates import (
    DETAIL_PY,
    PROJECTIONS_INIT_PY,
    PROJECTIONS_KNOWLEDGE_PY,
)
from verticals.travel.generator.mcp_templates import MCPS_INIT_PY, MCPS_TRAVEL_OPERATIONS_PY
from verticals.travel.generator.pack_templates import (
    LIFECYCLE_PY,
    MANIFEST_PY,
    SEED_PY,
    render_agents_py,
    render_authority_py,
    render_domains_py,
    render_functions_py,
    render_personas_py,
    render_ui_json,
)
from verticals.travel.generator.portfolio import ALL_PERSONA_ROLES, PROCESS_SPECS
from verticals.travel.generator.process_templates import (
    render_worlds_processes_py,
    render_worlds_registration_py,
)
from verticals.travel.generator.proof_templates import (
    TRAVEL_ZAVA_BROWSER_PROOF_MJS,
    TRAVEL_ZAVA_E2E_PROOF_PY,
    TRAVEL_ZAVA_E2E_PROOF_SH,
)
from verticals.travel.generator.recovery_templates import RECOVERY_INIT_PY, RECOVERY_PLANNER_PY
from verticals.travel.generator.scene_templates import render_world_scene_json
from verticals.travel.generator.skill_templates import (
    render_authority_yaml,
    render_case_json,
    render_domain_yaml,
    render_governance_tools_yaml,
    render_persona_skill_md,
    render_profile_json,
    render_skill_md,
)
from verticals.travel.generator.world_templates import (
    WORLDS_DIAGNOSTICS_PY,
    WORLDS_INIT_PY,
    WORLDS_MODEL_PY,
    WORLDS_REFERENCE_DATA_PY,
    WORLDS_SCENARIO_PY,
)

GENERATOR_VERSION = "0.2.0"

_PACK_RELATIVE_ROOT = Path("verticals") / "travel"
_MANIFEST_FILENAME = "generation-manifest.json"
_GENERATOR_DIRNAME = "generator"
_APPROVED_EXTERNAL_OUTPUTS = (
    Path("tools/travel_zava_e2e_proof.sh"),
    Path("tools/travel_zava_e2e_proof.py"),
    Path("tools/travel_zava_browser_proof.mjs"),
)


class ExternalOutputNotApprovedError(PermissionError):
    """A planned output resolves outside the pack root and was not approved."""


class UnsafeCleanupTargetError(RuntimeError):
    """A generation or cleanup target would touch generator source."""


@dataclass(frozen=True)
class PlannedAsset:
    """One asset this generator is about to write.

    `relative_path` is relative to the target root (repo root in
    production, `tmp_path` in tests). `input_recipe` is a canonical,
    deterministic description of the inputs that produced `content` — kept
    distinct from the content itself so `input_hash` and `content_hash`
    track different things.
    """

    relative_path: Path
    content: bytes
    ownership: str  # "generated" | "generated-external"
    input_recipe: str
    executable: bool = False


def _pack_root(target_root: Path) -> Path:
    return target_root / _PACK_RELATIVE_ROOT


def _manifest_path(target_root: Path) -> Path:
    return _pack_root(target_root) / _MANIFEST_FILENAME


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_under_generator_dir(relative_path: Path) -> bool:
    return _GENERATOR_DIRNAME in relative_path.parts


def classify_output_path(
    path: Path,
    *,
    pack_root: Path,
    approved_external: Iterable[Path] = (),
) -> str:
    """Classify a planned output as pack-owned or approved-external.

    Returns "generated" when `path` resolves inside `pack_root`, or
    "generated-external" when it resolves outside `pack_root` but is
    present in `approved_external`. Raises
    `ExternalOutputNotApprovedError` for any other outside-the-pack path.
    """
    resolved = path.resolve()
    resolved_pack_root = pack_root.resolve()
    try:
        resolved.relative_to(resolved_pack_root)
        return "generated"
    except ValueError:
        pass

    approved_resolved = {Path(candidate).resolve() for candidate in approved_external}
    if resolved in approved_resolved:
        return "generated-external"

    raise ExternalOutputNotApprovedError(
        f"{path} is outside the pack root {pack_root} and was not explicitly approved"
    )


def _asset(relative_path: Path, content: str) -> PlannedAsset:
    return PlannedAsset(
        relative_path=relative_path,
        content=content.encode("utf-8"),
        ownership="generated",
        input_recipe=f"asset:{relative_path.as_posix()}",
    )


def _external_asset(relative_path: Path, content: str, *, executable: bool = False) -> PlannedAsset:
    """Describe one allowlisted root-level runner owned by this pack source."""
    return PlannedAsset(
        relative_path=relative_path,
        content=content.encode("utf-8"),
        ownership="generated-external",
        input_recipe=(
            f"proof-template:{relative_path.as_posix()}:"
            f"{_sha256_hex(content.encode('utf-8'))}"
        ),
        executable=executable,
    )


def _world_assets() -> list[PlannedAsset]:
    """The Travel `worlds/` package: a deterministic, synthetic world built
    on `api.server.world.runtime.SimulationRuntime`
    (`model.py`/`reference_data.py`/`scenario.py`, rendered verbatim from
    `world_templates.py`), plus the eight-process routing table
    (`processes.py`/`registration.py`, rendered programmatically from
    `portfolio.py` by `process_templates.py`).
    """
    worlds_root = _PACK_RELATIVE_ROOT / "worlds"
    return [
        _asset(worlds_root / "__init__.py", WORLDS_INIT_PY),
        _asset(worlds_root / "diagnostics.py", WORLDS_DIAGNOSTICS_PY),
        _asset(worlds_root / "model.py", WORLDS_MODEL_PY),
        _asset(worlds_root / "reference_data.py", WORLDS_REFERENCE_DATA_PY),
        _asset(worlds_root / "scenario.py", WORLDS_SCENARIO_PY),
        _asset(worlds_root / "processes.py", render_worlds_processes_py()),
        _asset(worlds_root / "registration.py", render_worlds_registration_py()),
    ]


def _actions_assets() -> list[PlannedAsset]:
    """The Travel `actions/` package: the idempotent, journal-backed
    command dispatcher (`COMMAND_HANDLERS`) for all eight processes,
    rendered verbatim from `commands_templates.py`.
    """
    actions_root = _PACK_RELATIVE_ROOT / "actions"
    return [
        _asset(actions_root / "__init__.py", ACTIONS_INIT_PY),
        _asset(actions_root / "commands.py", ACTIONS_COMMANDS_PY),
    ]


def _pack_manifest_assets() -> list[PlannedAsset]:
    """The nine pack-manifest modules: `manifest.py` (the discoverable
    `VerticalPack` builder), `domains.py`, `functions.py`, `authority.py`,
    `personas.py`, `agents.py`, `seed.py`, `lifecycle.py` and `ui.json`,
    rendered from `portfolio.py` by `pack_templates.py`.
    """
    return [
        _asset(_PACK_RELATIVE_ROOT / "manifest.py", MANIFEST_PY),
        _asset(_PACK_RELATIVE_ROOT / "domains.py", render_domains_py()),
        _asset(_PACK_RELATIVE_ROOT / "functions.py", render_functions_py()),
        _asset(_PACK_RELATIVE_ROOT / "authority.py", render_authority_py()),
        _asset(_PACK_RELATIVE_ROOT / "personas.py", render_personas_py()),
        _asset(_PACK_RELATIVE_ROOT / "agents.py", render_agents_py()),
        _asset(_PACK_RELATIVE_ROOT / "seed.py", SEED_PY),
        _asset(_PACK_RELATIVE_ROOT / "lifecycle.py", LIFECYCLE_PY),
        _asset(_PACK_RELATIVE_ROOT / "ui.json", render_ui_json()),
    ]


def _per_process_assets() -> list[PlannedAsset]:
    """Eight each of `domains/*.yaml`, `profiles/*.json`, `cases/*.json`
    and `skills/*/SKILL.md`, one set per `PROCESS_SPECS` row, rendered by
    `skill_templates.py` from the same portfolio data that drives the
    executable detectors/evaluators/commands -- documentation and
    execution never drift apart.
    """
    assets: list[PlannedAsset] = []
    for spec in PROCESS_SPECS:
        workflow_type = spec.workflow_type
        assets.append(
            _asset(
                _PACK_RELATIVE_ROOT / "domains" / f"{workflow_type}.yaml",
                render_domain_yaml(workflow_type),
            )
        )
        assets.append(
            _asset(
                _PACK_RELATIVE_ROOT / "profiles" / f"{workflow_type}.json",
                render_profile_json(workflow_type),
            )
        )
        assets.append(
            _asset(
                _PACK_RELATIVE_ROOT / "cases" / f"{workflow_type}.json",
                render_case_json(workflow_type),
            )
        )
        assets.append(
            _asset(
                _PACK_RELATIVE_ROOT / "skills" / workflow_type / "SKILL.md",
                render_skill_md(workflow_type),
            )
        )
    return assets


def _persona_assets() -> list[PlannedAsset]:
    """One `personae/<role>/SKILL.md` per authority role (fourteen total:
    the eight process roles plus their six escalation heads), rendered by
    `skill_templates.py`."""
    return [
        _asset(_PACK_RELATIVE_ROOT / "personae" / role / "SKILL.md", render_persona_skill_md(role))
        for role in ALL_PERSONA_ROLES
    ]


def _policy_assets() -> list[PlannedAsset]:
    """The real fourteen-row bounded GBP authority matrix as a reviewable
    policy document, rendered by `skill_templates.py`."""
    return [
        _asset(_PACK_RELATIVE_ROOT / "policies" / "authority.yaml", render_authority_yaml()),
        _asset(
            _PACK_RELATIVE_ROOT / "policies" / "tools.yaml",
            render_governance_tools_yaml(),
        ),
    ]


def _mcp_assets() -> list[PlannedAsset]:
    """The Travel `mcps/` package: real, deterministic, network-free
    query/mutation-planning tool operations, rendered verbatim from
    `mcp_templates.py`."""
    mcps_root = _PACK_RELATIVE_ROOT / "mcps"
    return [
        _asset(mcps_root / "__init__.py", MCPS_INIT_PY),
        _asset(mcps_root / "travel_operations.py", MCPS_TRAVEL_OPERATIONS_PY),
    ]


def _durable_assets() -> list[PlannedAsset]:
    """The Travel `durable/` package: the pure, framework-free phase-plan
    engine (`engine.py`) and the eight distinct orchestrator functions
    (`orchestrators.py`), plus (Task 6) the real Azure Durable Functions
    module (`functions.py`) -- one genuine `DFApp` carrying the flight-
    disruption-recovery hero's real orchestrator and activities, which
    `__init__.py` now re-exports as `app` -- all rendered by
    `durable_templates.py`."""
    durable_root = _PACK_RELATIVE_ROOT / "durable"
    return [
        _asset(durable_root / "__init__.py", DURABLE_INIT_PY),
        _asset(durable_root / "engine.py", ENGINE_PY),
        _asset(durable_root / "orchestrators.py", render_orchestrators_py()),
        _asset(durable_root / "functions.py", render_travel_durable_functions_py()),
    ]


def _recovery_assets() -> list[PlannedAsset]:
    """The Travel `recovery/` package (Task 6): the pure, pack-owned
    flight-disruption-recovery option planner
    (`plan_recovery_options`/`RecoveryOption`), rendered verbatim from
    `recovery_templates.py`. Reads only its own `observation` argument --
    no world reference, I/O or randomness -- so it is safe to call
    directly from the real Durable `TravelRecoveryPlanOptions` activity.
    """
    recovery_root = _PACK_RELATIVE_ROOT / "recovery"
    return [
        _asset(recovery_root / "__init__.py", RECOVERY_INIT_PY),
        _asset(recovery_root / "planner.py", RECOVERY_PLANNER_PY),
    ]


def _knowledge_assets() -> list[PlannedAsset]:
    """The Travel `projections/` package (Task 7 Required A) -- the
    pack-owned Knowledge-graph projection for `flight-disruption-recovery`,
    registered on `VerticalPack.projections` by `pack_templates.py`'s
    `MANIFEST_PY` template -- plus the top-level `detail.py` module
    carrying the `workflow_detail` hook `VerticalPack.workflow_detail_hook`
    exposes (Task 7 Required B). Both rendered verbatim from
    `knowledge_templates.py`."""
    projections_root = _PACK_RELATIVE_ROOT / "projections"
    return [
        _asset(projections_root / "__init__.py", PROJECTIONS_INIT_PY),
        _asset(projections_root / "knowledge.py", PROJECTIONS_KNOWLEDGE_PY),
        _asset(_PACK_RELATIVE_ROOT / "detail.py", DETAIL_PY),
    ]


def _scene_assets() -> list[PlannedAsset]:
    """The Travel `ui/world-scene.json` spatial scene (Task 8): the
    pack-owned scene naming the real seeded origin airports/destinations/
    hotels and binding every real snapshot collection a generic spatial
    world renderer needs, rendered verbatim from `scene_templates.py`.
    `ui.json`'s `render_ui_json()` points at this exact relative path.
    """
    return [
        _asset(_PACK_RELATIVE_ROOT / "ui" / "world-scene.json", render_world_scene_json()),
    ]


def _proof_runner_assets() -> list[PlannedAsset]:
    """The three approved external proof entrypoints owned by Travel source."""
    return [
        _external_asset(
            Path("tools/travel_zava_e2e_proof.sh"),
            TRAVEL_ZAVA_E2E_PROOF_SH,
            executable=True,
        ),
        _external_asset(Path("tools/travel_zava_e2e_proof.py"), TRAVEL_ZAVA_E2E_PROOF_PY),
        _external_asset(Path("tools/travel_zava_browser_proof.mjs"), TRAVEL_ZAVA_BROWSER_PROOF_MJS),
    ]


def _planned_assets() -> list[PlannedAsset]:
    """The static, deterministic set of assets this generator produces.

    Extend this list in later tasks. Every entry must resolve inside the
    pack root and must never point into `generator/` (hand-authored
    source) — both are enforced in `_render_record`.
    """
    init_relative = _PACK_RELATIVE_ROOT / "__init__.py"
    init_content = (
        b'"""Travel vertical pack (generated by verticals.travel.generator).\n\n'
        b"Do not hand-edit. Regenerate via "
        b"`uv run python -m verticals.travel.generator`.\n"
        b'"""\n'
    )
    return [
        PlannedAsset(
            relative_path=init_relative,
            content=init_content,
            ownership="generated",
            input_recipe=f"asset:{init_relative.as_posix()}",
        ),
        *_world_assets(),
        *_actions_assets(),
        *_pack_manifest_assets(),
        *_per_process_assets(),
        *_persona_assets(),
        *_policy_assets(),
        *_mcp_assets(),
        *_durable_assets(),
        *_recovery_assets(),
        *_knowledge_assets(),
        *_scene_assets(),
        *_proof_runner_assets(),
    ]


def _render_record(target_root: Path, asset: PlannedAsset) -> dict:
    if _is_under_generator_dir(asset.relative_path):
        raise UnsafeCleanupTargetError(
            f"refusing to generate into generator source path: {asset.relative_path}"
        )

    absolute_path = target_root / asset.relative_path
    ownership = classify_output_path(
        absolute_path,
        pack_root=_pack_root(target_root),
        approved_external=(target_root / path for path in _APPROVED_EXTERNAL_OUTPUTS),
    )
    if ownership != asset.ownership:
        raise ExternalOutputNotApprovedError(
            f"{asset.relative_path} was declared {asset.ownership!r}, classified as {ownership!r}"
        )

    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(asset.content)
    if asset.executable:
        absolute_path.chmod(absolute_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return {
        "path": asset.relative_path.as_posix(),
        "ownership": asset.ownership,
        "input_hash": _sha256_hex(asset.input_recipe.encode("utf-8")),
        "content_hash": _sha256_hex(asset.content),
        "generator_version": GENERATOR_VERSION,
    }


def generate(target_root: Path) -> dict:
    """Deterministically (re)generate the Travel pack's generated assets.

    Writes each planned asset under `target_root`, then writes
    `generation-manifest.json` recording every generated asset exactly
    once. Safe to call repeatedly: output is byte-identical across runs
    for a fixed generator version.
    """
    target_root = Path(target_root)
    records = [_render_record(target_root, asset) for asset in _planned_assets()]
    records.sort(key=lambda record: record["path"])

    manifest = {
        "generator_version": GENERATOR_VERSION,
        "records": records,
    }

    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    manifest_path = _manifest_path(target_root)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_bytes(manifest_bytes)

    return manifest


def clean(target_root: Path) -> list[Path]:
    """Remove every asset the current manifest lists, plus the manifest itself.

    Never removes anything not listed in the manifest, and refuses to
    touch any path under a `generator/` directory (hand-authored source)
    even if a corrupted or malicious manifest were to list one. Every
    listed path is resolved and confined: absolute paths and `..`
    traversal outside `target_root` are always rejected, and pack-owned
    ("generated") records must additionally resolve inside the Travel
    pack root. Only a record explicitly marked "generated-external" may
    resolve outside the pack root, and even then only within
    `target_root` — reserved for future approved external assets.
    """
    target_root = Path(target_root)
    pack_root = _pack_root(target_root)
    manifest_path = _manifest_path(target_root)
    removed: list[Path] = []
    if not manifest_path.is_file():
        return removed

    resolved_target_root = target_root.resolve()
    resolved_pack_root = pack_root.resolve()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for record in manifest.get("records", []):
        raw_path = record.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            raise UnsafeCleanupTargetError(
                f"refusing to clean malformed manifest path: {raw_path!r}"
            )

        relative_path = Path(raw_path)
        if relative_path.is_absolute():
            raise UnsafeCleanupTargetError(
                f"refusing to clean absolute manifest path: {raw_path}"
            )
        if _is_under_generator_dir(relative_path):
            raise UnsafeCleanupTargetError(
                f"refusing to clean generator source path: {relative_path}"
            )

        candidate = (target_root / relative_path).resolve()
        allowed_root = (
            resolved_target_root
            if record.get("ownership") == "generated-external"
            else resolved_pack_root
        )
        try:
            candidate.relative_to(allowed_root)
        except ValueError as exc:
            raise UnsafeCleanupTargetError(
                f"refusing to clean manifest path outside {allowed_root}: {raw_path}"
            ) from exc

        if candidate.is_file():
            candidate.unlink()
            removed.append(candidate)

    manifest_path.unlink()
    removed.append(manifest_path)
    return removed
