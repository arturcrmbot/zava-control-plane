from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

from api.shared.vertical_loader import active_runtime


def _load_replay_conftest():
    conftest_path = Path(__file__).with_name("conftest.py")
    spec = importlib.util.spec_from_file_location("replay_conftest", conftest_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _Collector:
    def __init__(self, path: Path) -> None:
        self.path = path


def _assert_no_repo_local_artifacts(repo_root: Path) -> None:
    replay_dir = Path(__file__).resolve().parent
    artifact_dirs = [
        repo_root / ".collection-runtime",
        repo_root / "cached",
        repo_root / "restored",
        replay_dir / ".collection-runtime",
        replay_dir / "cached",
        replay_dir / "restored",
    ]
    assert [path for path in artifact_dirs if path.exists()] == []


def test_replay_collection_env_guard_sets_and_restores_env(monkeypatch):
    module = _load_replay_conftest()
    replay_dir = Path(__file__).resolve().parent
    repo_root = replay_dir.parents[4]
    collector = _Collector(replay_dir / "test_player.py")

    monkeypatch.setenv("ENTITY_PLANE_ENABLED", "1")
    monkeypatch.setenv("MEMORY_BACKEND", "mem0")
    monkeypatch.setenv("PORTAL_DATA_DIR", str(replay_dir / "restored"))
    active_runtime.cache_clear()
    os.environ["PORTAL_DATA_DIR"] = str(replay_dir / "cached")
    assert active_runtime().data_dir.as_posix().endswith("/cached/agency")
    os.environ["PORTAL_DATA_DIR"] = str(replay_dir / "restored")

    module.pytest_collectstart(collector)
    assert os.getenv("ENTITY_PLANE_ENABLED") == "0"
    assert os.getenv("MEMORY_BACKEND") == "fallback"
    collection_portal_data_dir = Path(os.environ["PORTAL_DATA_DIR"]).resolve()
    assert not collection_portal_data_dir.is_relative_to(repo_root)
    assert collection_portal_data_dir.exists()

    module.pytest_collectstart(_Collector(replay_dir / "nested" / "test_other.py"))
    assert os.getenv("ENTITY_PLANE_ENABLED") == "0"
    assert os.getenv("MEMORY_BACKEND") == "fallback"

    module.pytest_collectreport(_Collector(replay_dir / "nested" / "test_other.py"))
    assert os.getenv("ENTITY_PLANE_ENABLED") == "0"
    assert os.getenv("MEMORY_BACKEND") == "fallback"

    module.pytest_collectreport(collector)
    assert os.getenv("ENTITY_PLANE_ENABLED") == "1"
    assert os.getenv("MEMORY_BACKEND") == "mem0"
    assert os.getenv("PORTAL_DATA_DIR") == str(replay_dir / "restored")
    assert active_runtime().data_dir.as_posix().endswith("/restored/agency")


def test_replay_subprocess_leaves_no_repo_local_artifacts(tmp_path):
    repo_root = Path(__file__).resolve().parents[5]
    replay_player = "tests/api/server/services/replay/test_player.py"
    appstate_wiring = "tests/api/server/test_appstate_entity_wiring.py"
    environment = os.environ.copy()
    environment.update(
        {
            "ENTITY_PLANE_ENABLED": "0",
            "MEMORY_BACKEND": "fallback",
            "PORTAL_DATA_DIR": str(tmp_path / "subprocess-runtime"),
        }
    )

    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            replay_player,
            appstate_wiring,
            "-q",
        ],
        cwd=repo_root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    _assert_no_repo_local_artifacts(repo_root)
