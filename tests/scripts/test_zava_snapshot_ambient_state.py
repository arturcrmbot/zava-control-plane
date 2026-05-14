"""Pitch-j7: persistent ambient + learning state across restarts.

These tests cover the round-trip of the ``ambient_state.json`` sidecar
inside the zava-snapshot bundle.

We import ``scripts/zava-snapshot.py`` with ``REPO_ROOT`` pinned to a
``tmp_path`` so the live ``data/portal/entity_graph.kuzu`` is never
touched. The ambient-state targets are the *real* in-process modules,
because the dump/restore protocol is wired by import path — that is the
behaviour we want to verify.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import tarfile
from pathlib import Path

import kuzu
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "zava-snapshot.py"


# Mirror of the modules wired into the snapshot bundle (kept in sync
# with ``AMBIENT_STATE_MODULES`` in scripts/zava-snapshot.py).
AMBIENT_MODULES = (
    "api.server.services.ambient_agents.auto_block_rule_learner",
    "api.server.services.classifier_cache",
    "api.server.services.routing_stats",
    "api.server.services.persona_experience",
    "api.server.services.ambient_agents.vendor_block_watcher",
    "api.server.services.ambient_agents.brand_budget_watcher",
    "api.server.services.ambient_agents.subsidiary_capacity_watcher",
)


def _load_snapshot_module(monkeypatch, fake_root: Path):
    spec = importlib.util.spec_from_file_location("zava_snapshot_j7", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "REPO_ROOT", fake_root)
    monkeypatch.setattr(module, "PORTAL_DIR", fake_root / "data" / "portal")
    monkeypatch.setattr(
        module, "KUZU_PATH", fake_root / "data" / "portal" / module.KUZU_DIR_NAME
    )
    monkeypatch.setattr(module, "SNAPSHOT_DIR", fake_root / "data" / "snapshots")
    return module


def _seed_kuzu(kuzu_dir: Path) -> None:
    kuzu_dir.parent.mkdir(parents=True, exist_ok=True)
    db = kuzu.Database(str(kuzu_dir))
    conn = kuzu.Connection(db)
    conn.execute("CREATE NODE TABLE Thing(id INT64, PRIMARY KEY(id));")
    conn.execute("CREATE (:Thing {id: 1});")
    del conn
    del db


def _reset_all_modules() -> None:
    """Wipe every learning module's in-memory state. Each module ships a
    ``_reset_for_tests`` or ``reset`` helper; we use whichever is
    present."""
    for mod_path in AMBIENT_MODULES:
        mod = importlib.import_module(mod_path)
        for fn_name in ("_reset_for_tests", "reset"):
            fn = getattr(mod, fn_name, None)
            if fn is not None:
                fn()
                break


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    (tmp_path / "data" / "portal").mkdir(parents=True)
    module = _load_snapshot_module(monkeypatch, tmp_path)
    _reset_all_modules()
    yield tmp_path, module
    _reset_all_modules()


# ---------------------------------------------------------------------------
# 1. round-trip: state mutated after save is rolled back on restore
# ---------------------------------------------------------------------------


def test_save_then_restore_rolls_back_learned_state(fake_repo):
    root, mod = fake_repo
    _seed_kuzu(root / "data" / "portal" / mod.KUZU_DIR_NAME)

    from api.server.services import classifier_cache, persona_experience, routing_stats
    from api.server.services.ambient_agents import (
        auto_block_rule_learner,
        brand_budget_watcher,
        subsidiary_capacity_watcher,
        vendor_block_watcher,
    )

    # --- seed the "morning run" state we want to preserve --------------
    classifier_cache.remember("sig-A", {"resolution": "auto_close"})
    classifier_cache.lookup("sig-A")  # bump _HITS
    classifier_cache.lookup("sig-MISS")  # bump _MISSES

    routing_stats.record("expense", "approve", "VP-Finance", approved=True)
    routing_stats.record("expense", "approve", "VP-Finance", approved=False)

    persona_experience.record_decision("VP-Finance", "expense")
    persona_experience.record_decision("VP-Finance", "expense")

    auto_block_rule_learner._VENDOR_REJECT_HISTORY["VND-1"] = ["dec-a", "dec-b"]
    auto_block_rule_learner._INSTALLED.add("VND-1")

    vendor_block_watcher._BLOCKED_VENDORS.add("VND-9")
    brand_budget_watcher._BUDGET_EXCEPTIONS_FIRED.add(("brand-acme", "2025-01"))
    subsidiary_capacity_watcher._WATCHER._seen.add(("ORG-zava-media", 14))

    assert mod.cmd_save("morning") == 0

    # --- now mutate state to look like a "long afternoon run" ----------
    classifier_cache.remember("sig-DRIFT", {"resolution": "escalate"})
    classifier_cache.lookup("sig-DRIFT")
    routing_stats.record("expense", "approve", "VP-Finance", approved=False)
    persona_experience.record_decision("VP-Finance", "expense")
    auto_block_rule_learner._INSTALLED.add("VND-DRIFT")
    vendor_block_watcher._BLOCKED_VENDORS.add("VND-DRIFT")
    brand_budget_watcher._BUDGET_EXCEPTIONS_FIRED.add(("brand-drift", "2025-99"))
    subsidiary_capacity_watcher._WATCHER._seen.add(("ORG-zava-data", 23))

    assert mod.cmd_restore("morning") == 0

    # --- assert we are back at the morning baseline --------------------
    assert "sig-A" in classifier_cache._CACHE
    assert "sig-DRIFT" not in classifier_cache._CACHE
    cs = classifier_cache.stats()
    assert cs["hits"] == 1 and cs["misses"] == 1

    snap = routing_stats.snapshot()
    bucket = snap["expense|approve|VP-Finance"]
    assert bucket["total"] == 2 and bucket["approves"] == 1

    assert persona_experience.experience_score("VP-Finance", "expense") == 2

    assert auto_block_rule_learner._INSTALLED == {"VND-1"}
    assert auto_block_rule_learner._VENDOR_REJECT_HISTORY == {
        "VND-1": ["dec-a", "dec-b"]
    }

    assert vendor_block_watcher._BLOCKED_VENDORS == {"VND-9"}
    assert brand_budget_watcher._BUDGET_EXCEPTIONS_FIRED == {
        ("brand-acme", "2025-01")
    }
    assert subsidiary_capacity_watcher._WATCHER._seen == {("ORG-zava-media", 14)}


# ---------------------------------------------------------------------------
# 2. bundle written with a module's state present is loadable into a
#    process where that state is empty
# ---------------------------------------------------------------------------


def test_restore_into_empty_process_loads_one_module(fake_repo):
    root, mod = fake_repo
    _seed_kuzu(root / "data" / "portal" / mod.KUZU_DIR_NAME)

    from api.server.services.ambient_agents import vendor_block_watcher
    vendor_block_watcher._BLOCKED_VENDORS.add("VND-A")
    vendor_block_watcher._BLOCKED_VENDORS.add("VND-B")

    assert mod.cmd_save("blocked") == 0

    # Simulate a fresh process: every module wiped.
    _reset_all_modules()
    assert vendor_block_watcher._BLOCKED_VENDORS == set()

    assert mod.cmd_restore("blocked") == 0
    assert vendor_block_watcher._BLOCKED_VENDORS == {"VND-A", "VND-B"}


# ---------------------------------------------------------------------------
# 3. a bundle missing a module key restores the surviving modules without
#    error (forward compatibility for adding/removing learning modules)
# ---------------------------------------------------------------------------


def test_restore_tolerates_missing_module_key(fake_repo):
    root, mod = fake_repo
    kuzu_dir = root / "data" / "portal" / mod.KUZU_DIR_NAME
    _seed_kuzu(kuzu_dir)

    from api.server.services import persona_experience
    from api.server.services.ambient_agents import vendor_block_watcher

    persona_experience.record_decision("VP-Finance", "expense")
    vendor_block_watcher._BLOCKED_VENDORS.add("VND-X")
    assert mod.cmd_save("partial") == 0

    # Hand-edit the bundle: drop the persona_experience entry and inject
    # an unknown-module entry that should be skipped, not crash.
    bundle = root / "data" / "snapshots" / "partial.tgz"
    extract_dir = root / "_unpack"
    extract_dir.mkdir()
    with tarfile.open(bundle, "r:gz") as tar:
        tar.extractall(extract_dir)
    ambient_path = extract_dir / "ambient_state.json"
    state = json.loads(ambient_path.read_text())
    state.pop("api.server.services.persona_experience", None)
    state["api.server.services.no_such_module_xyz"] = {"foo": 1}
    ambient_path.write_text(json.dumps(state))

    # Repackage.
    bundle.unlink()
    with tarfile.open(bundle, "w:gz") as tar:
        for child in extract_dir.iterdir():
            tar.add(child, arcname=child.name)

    # Wipe everything and restore.
    _reset_all_modules()
    assert vendor_block_watcher._BLOCKED_VENDORS == set()
    assert persona_experience.experience_score("VP-Finance", "expense") == 0

    assert mod.cmd_restore("partial") == 0

    # Surviving module loaded; missing key left at default; unknown key ignored.
    assert vendor_block_watcher._BLOCKED_VENDORS == {"VND-X"}
    assert persona_experience.experience_score("VP-Finance", "expense") == 0
