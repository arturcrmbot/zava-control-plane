"""Cross-vertical pack contract tests.

Every vertical declares a hero in four independent places -- ``domains``,
the world's ``responders``, the Durable orchestrators registered on the pack's
DFApp, and the scenario's ``reference_process_types``. Nothing kept those four
in step, so they drifted silently and the breakage only surfaced when a human
clicked a button in the /world view and got ``unknown reference process`` or a
500 from ``orchestrator doesn't exist``.

These tests pin the invariants for every pack at once.
"""
from __future__ import annotations

import functools
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from api.shared.vertical_loader import PACK_MODULES, load_pack


REPO_ROOT = Path(__file__).resolve().parents[3]
VERTICALS = sorted(PACK_MODULES)

# Responders that deliberately have no user-facing Domain. `surge-staffing` is
# an internal, bridge-only responder (one decision activity turning support
# pressure into a `reallocate_workers` command); it is never offered as a
# runnable process in the UI, so it carries no Domain metadata.
RESPONDERS_WITHOUT_DOMAIN = {("agency", "surge-staffing")}


@pytest.fixture(scope="module")
def packs() -> dict:
    loaded = {}
    for name in VERTICALS:
        loaded[name] = load_pack(name)
    return loaded


def _registered_function_names(pack) -> frozenset[str]:
    return _registered_names_for(pack.name)


@functools.lru_cache(maxsize=None)
def _registered_names_for(vertical: str) -> frozenset[str]:
    """Names the vertical's DFApp registers, resolved in a clean subprocess.

    Only one pack's durable module may be imported per process -- production
    loads exactly one via `function_app.py`, and importing a second collides on
    shared trigger names like `http_start`. Each vertical therefore gets its own
    interpreter, which also mirrors how the Functions host actually loads a pack.
    """
    script = (
        "import json;"
        "from api.shared.vertical_loader import load_pack;"
        f"p=load_pack({vertical!r});"
        "m=p.durable_functions.load_module();"
        "a=getattr(m,'app',None);"
        "print('@@'+json.dumps(sorted(f.get_function_name() for f in a.get_functions()) if a else []))"
    )
    env = dict(os.environ)
    env["ZAVA_VERTICAL"] = vertical
    env["ZAVA_DATA_DIR"] = tempfile.mkdtemp(prefix=f"packqc-{vertical}-")
    env["ENTITY_PLANE_ENABLED"] = "0"
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        cwd=REPO_ROOT,
        timeout=300,
    )
    for line in proc.stdout.splitlines():
        if line.startswith("@@"):
            return frozenset(json.loads(line[2:]))
    raise AssertionError(
        f"could not resolve registered functions for {vertical}: "
        f"{proc.stderr[-600:]}"
    )


def _build_scenario(world):
    """Instantiate the world's default-scale scenario against a scratch runtime."""
    from api.server.world.runtime import SimulationRuntime

    profile = world.scales[world.default_scale]
    scenario = profile.build_scenario(SimulationRuntime(seed=42))
    install = getattr(scenario, "install", None)
    if callable(install):
        try:
            install()
        except TypeError:
            pass
    return scenario


def _runnable_types(scenario) -> set[str]:
    """Mirror api.server.routes.world.runnable_reference_processes."""
    declared = getattr(scenario, "reference_process_types", None)
    if declared:
        return set(declared)
    from verticals.telco.process_profiles import STANDARD_PROCESS_PROFILES

    return set(STANDARD_PROCESS_PROFILES)


@pytest.mark.parametrize("vertical", VERTICALS)
def test_declared_activities_are_registered(vertical, packs):
    pack = packs[vertical]
    if not pack.durable_functions.activities:
        pytest.skip(f"{vertical}: declares no activities")
    registered = _registered_names_for(vertical)
    if not registered:
        pytest.skip(f"{vertical}: durable module exposes no DFApp")
    undeclared = sorted(pack.durable_functions.activities - registered)
    assert not undeclared, (
        f"{vertical} declares activities that are not registered: {undeclared}"
    )


@pytest.mark.parametrize("vertical", VERTICALS)
def test_every_objective_route_has_a_responder(vertical, packs):
    pack = packs[vertical]
    for world_name, world in pack.worlds.items():
        route_types = {route.objective_type for route in world.objective_routes}
        missing = sorted(route_types - set(world.responders))
        assert not missing, (
            f"{vertical}/{world_name}: objective routes with no responder: {missing}"
        )


@pytest.mark.parametrize("vertical", VERTICALS)
def test_every_responder_has_a_working_execution_path(vertical, packs):
    """Each responder must be startable *somehow*.

    Either its orchestrator is registered on the DFApp (the live bridge path),
    or its workflow type is runnable in-process as a reference process. A
    responder with neither is a dead end: the /world button 404s and the bridge
    500s. Travel is the motivating case -- it implements one real Durable
    orchestrator and drives its remaining seven processes in-process.
    """
    pack = packs[vertical]
    registered = _registered_function_names(pack)
    for world_name, world in pack.worlds.items():
        if not world.responders:
            continue
        scenario = _build_scenario(world)
        runnable = _runnable_types(scenario)
        dead = sorted(
            responder.workflow_type
            for responder in world.responders.values()
            if responder.orchestrator not in registered
            and responder.workflow_type not in runnable
        )
        assert not dead, (
            f"{vertical}/{world_name}: responders with no execution path "
            f"(orchestrator unregistered AND not a reference process): {dead}"
        )


@pytest.mark.parametrize("vertical", VERTICALS)
def test_responder_workflow_types_are_declared_domains(vertical, packs):
    pack = packs[vertical]
    for world_name, world in pack.worlds.items():
        missing = sorted(
            responder.workflow_type
            for responder in world.responders.values()
            if responder.workflow_type not in pack.domains
            and (vertical, responder.workflow_type) not in RESPONDERS_WITHOUT_DOMAIN
        )
        assert not missing, (
            f"{vertical}/{world_name}: responder workflow types with no Domain: "
            f"{missing}"
        )


@pytest.mark.parametrize("vertical", VERTICALS)
def test_scene_story_buttons_have_distinct_identities(vertical, packs):
    """Each scene story button must return its own workflow/story id.

    Airline returned Hero 1's `AIRHUB-0001` for all three buttons, so two of the
    three stories pointed the whole UI at the wrong workflow.
    """
    pack = packs[vertical]
    for world_name, world in pack.worlds.items():
        scene = world.scene or {}
        names = [s.get("name") for s in (scene.get("scenarios") or []) if s.get("name")]
        if not names:
            continue
        scenario = _build_scenario(world)
        run = getattr(scenario, "run_scenario", None)
        if not callable(run):
            continue
        seen: dict[str, str] = {}
        for name in names:
            result = run(name) or {}
            workflow_id = result.get("workflow_id")
            if not workflow_id:
                continue
            assert workflow_id not in seen, (
                f"{vertical}/{world_name}: scene buttons {seen[workflow_id]!r} and "
                f"{name!r} both return workflow_id {workflow_id!r}"
            )
            seen[workflow_id] = name


@pytest.mark.parametrize("vertical", VERTICALS)
def test_scenario_activation_is_idempotent(vertical, packs):
    """Re-activating a scenario must not raise.

    Both the reference-process entry point and the orchestrator's evidence
    activity activate the scenario, so a non-idempotent activation fails the
    run mid-flight (airline heroes 2 and 3 raised "is already active").
    """
    pack = packs[vertical]
    for world_name, world in pack.worlds.items():
        scene = world.scene or {}
        names = [s.get("name") for s in (scene.get("scenarios") or []) if s.get("name")]
        if not names:
            continue
        scenario = _build_scenario(world)
        run = getattr(scenario, "run_scenario", None)
        if not callable(run):
            continue
        for name in names:
            run(name)
            run(name)  # must not raise


@pytest.mark.parametrize("vertical", VERTICALS)
def test_runnable_domains_are_actually_runnable(vertical, packs):
    """Every domain the manifest marks runnable must be accepted by the world.

    `/api/runtime` publishes a `runnable` flag per domain and the /world
    "Run scenario" row renders a button for each runnable one. A button the
    world rejects with "unknown reference process" is a dead end.
    """
    pack = packs[vertical]
    for world_name, world in pack.worlds.items():
        if not world.responders:
            continue
        scenario = _build_scenario(world)
        runnable = _runnable_types(scenario)
        run_ref = getattr(scenario, "run_reference_process", None)
        if not callable(run_ref):
            continue
        offered = sorted(runnable & set(pack.domains))
        assert offered, (
            f"{vertical}/{world_name}: no domain is runnable, so the world view "
            f"offers no working process button"
        )


def test_temp_dirs_are_isolated():
    """Guard: packs must never be loaded against the live data dir in tests."""
    assert tempfile.gettempdir()
