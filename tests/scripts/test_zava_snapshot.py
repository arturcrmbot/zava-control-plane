"""Tests for scripts/zava-snapshot.py.

Each test runs the script against an isolated REPO_ROOT under tmp_path so
the live `data/portal/entity_graph.kuzu` is never touched.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import kuzu
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "zava-snapshot.py"


def _load_module(monkeypatch, fake_root: Path):
    """Import scripts/zava-snapshot.py with REPO_ROOT pinned to fake_root."""
    spec = importlib.util.spec_from_file_location("zava_snapshot", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "REPO_ROOT", fake_root)
    monkeypatch.setattr(module, "PORTAL_DIR", fake_root / "data" / "portal")
    monkeypatch.setattr(module, "KUZU_PATH", fake_root / "data" / "portal" / module.KUZU_DIR_NAME)
    monkeypatch.setattr(module, "SNAPSHOT_DIR", fake_root / "data" / "snapshots")
    return module


def _seed_kuzu(kuzu_dir: Path, n_nodes: int = 3) -> None:
    """Create a tiny Kuzu DB with a `Thing` node table + N rows."""
    kuzu_dir.parent.mkdir(parents=True, exist_ok=True)
    db = kuzu.Database(str(kuzu_dir))
    conn = kuzu.Connection(db)
    conn.execute("CREATE NODE TABLE Thing(id INT64, name STRING, PRIMARY KEY(id));")
    for i in range(n_nodes):
        conn.execute(f"CREATE (:Thing {{id: {i}, name: 'n{i}'}});")
    del conn
    del db


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    (tmp_path / "data" / "portal").mkdir(parents=True)
    module = _load_module(monkeypatch, tmp_path)
    return tmp_path, module


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


def test_save_then_list_shows_snapshot(fake_repo, capsys):
    root, mod = fake_repo
    _seed_kuzu(root / "data" / "portal" / mod.KUZU_DIR_NAME)

    assert mod.cmd_save("morning") == 0
    bundle = root / "data" / "snapshots" / "morning.tgz"
    assert bundle.exists()

    capsys.readouterr()
    assert mod.cmd_list() == 0
    out = capsys.readouterr().out
    assert "morning" in out


def test_bundle_contains_meta_and_empty_ambient_state(fake_repo):
    root, mod = fake_repo
    _seed_kuzu(root / "data" / "portal" / mod.KUZU_DIR_NAME)
    assert mod.cmd_save("snap1") == 0
    bundle = root / "data" / "snapshots" / "snap1.tgz"

    with tarfile.open(bundle, "r:gz") as tar:
        names = set(tar.getnames())
        assert "meta.json" in names
        assert "ambient_state.json" in names
        assert any(n.startswith("entity_graph.kuzu") for n in names)

        ambient = json.load(tar.extractfile("ambient_state.json"))
        assert isinstance(ambient, dict)
        # pitch-j7: snapshot now captures live ambient + learning state.
        # In a clean test process the modules' state is empty but their
        # namespaces are still represented.
        for mod_path in (
            "api.server.services.classifier_cache",
            "api.server.services.routing_stats",
            "api.server.services.persona_experience",
            "api.server.services.ambient_agents.vendor_block_watcher",
            "api.server.services.ambient_agents.brand_budget_watcher",
            "api.server.services.ambient_agents.auto_block_rule_learner",
            "api.server.services.ambient_agents.subsidiary_capacity_watcher",
        ):
            assert mod_path in ambient

        meta = json.load(tar.extractfile("meta.json"))
        assert meta["name"] == "snap1"
        assert sorted(meta["ambient_state_keys"]) == sorted(ambient.keys())
        assert "created_at" in meta
        assert "kuzu_size_bytes" in meta
        assert "substrate_version" in meta


def test_save_restore_roundtrip_preserves_counts(fake_repo):
    root, mod = fake_repo
    kuzu_dir = root / "data" / "portal" / mod.KUZU_DIR_NAME
    _seed_kuzu(kuzu_dir, n_nodes=5)

    before = mod._read_counts(kuzu_dir)
    assert before.get("nodes") == 5

    assert mod.cmd_save("rt") == 0

    # mutate live DB so restore has something to overwrite
    db = kuzu.Database(str(kuzu_dir))
    conn = kuzu.Connection(db)
    conn.execute("CREATE (:Thing {id: 999, name: 'extra'});")
    del conn
    del db
    mutated = mod._read_counts(kuzu_dir)
    assert mutated.get("nodes") == 6

    assert mod.cmd_restore("rt") == 0
    after = mod._read_counts(kuzu_dir)
    assert after.get("nodes") == before.get("nodes") == 5

    # backup preserved
    assert (root / "data" / "portal" / f"{mod.KUZU_DIR_NAME}.bak").exists()


def test_restore_into_locked_db_exits_nonzero(fake_repo, capsys):
    root, mod = fake_repo
    kuzu_dir = root / "data" / "portal" / mod.KUZU_DIR_NAME
    _seed_kuzu(kuzu_dir)
    assert mod.cmd_save("locked") == 0

    # Hold an exclusive flock on the .lock file to simulate a running engine.
    import fcntl
    lock_path = kuzu_dir / ".lock"
    if not lock_path.exists():
        lock_path.write_bytes(b"")
    fh = open(lock_path, "rb")
    fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
    try:
        rc = mod.cmd_restore("locked")
    finally:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        fh.close()

    assert rc != 0
    err = capsys.readouterr().err
    assert "lock" in err.lower() or "running" in err.lower()


def test_info_prints_meta(fake_repo, capsys):
    root, mod = fake_repo
    _seed_kuzu(root / "data" / "portal" / mod.KUZU_DIR_NAME)
    assert mod.cmd_save("inspect-me") == 0
    capsys.readouterr()
    assert mod.cmd_info("inspect-me") == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["name"] == "inspect-me"


def test_cli_help_runs():
    """Smoke-test the script's actual CLI entrypoint via subprocess."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--help"],
        capture_output=True, text=True, check=True, timeout=10,
    )
    assert "save" in result.stdout
    assert "restore" in result.stdout
    assert "list" in result.stdout
    assert "info" in result.stdout
