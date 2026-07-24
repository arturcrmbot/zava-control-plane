from __future__ import annotations

import asyncio
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

_REPLAY_DIR = Path(__file__).resolve().parent
_REPLAY_ENV_VARS = ("ENTITY_PLANE_ENABLED", "MEMORY_BACKEND", "PORTAL_DATA_DIR")
_replay_env_depth = 0
_replay_env_originals: dict[str, str | None] | None = None
_replay_collection_portal_data_dir: Path | None = None


def _collector_path(collector) -> Path | None:
    raw_path = getattr(collector, "path", None) or getattr(collector, "fspath", None)
    if raw_path is None:
        return None
    return Path(str(raw_path)).resolve()


def _is_replay_collector(collector) -> bool:
    path = _collector_path(collector)
    return path is not None and path.is_relative_to(_REPLAY_DIR)


def _set_replay_env() -> None:
    global _replay_env_originals

    if _replay_env_originals is None:
        global _replay_collection_portal_data_dir
        _clear_active_runtime_cache()
        _replay_env_originals = {name: os.environ.get(name) for name in _REPLAY_ENV_VARS}
        os.environ["ENTITY_PLANE_ENABLED"] = "0"
        os.environ["MEMORY_BACKEND"] = "fallback"
        _replay_collection_portal_data_dir = Path(
            tempfile.mkdtemp(prefix="zava-replay-collection-")
        )
        os.environ["PORTAL_DATA_DIR"] = str(_replay_collection_portal_data_dir)


def _restore_replay_env() -> None:
    global _replay_env_originals

    if _replay_env_originals is None:
        return
    for name, original in _replay_env_originals.items():
        if original is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = original
    _replay_env_originals = None
    _clear_active_runtime_cache()


def _clear_active_runtime_cache() -> None:
    vertical_loader = sys.modules.get("api.shared.vertical_loader")
    if vertical_loader is None:
        return
    active_runtime = getattr(vertical_loader, "active_runtime", None)
    if active_runtime is not None:
        active_runtime.cache_clear()


def _cleanup_replay_collection_runtime() -> None:
    global _replay_collection_portal_data_dir

    if _replay_collection_portal_data_dir is None:
        return
    shutil.rmtree(_replay_collection_portal_data_dir, ignore_errors=True)
    _replay_collection_portal_data_dir = None


def pytest_collectstart(collector):
    global _replay_env_depth

    if not _is_replay_collector(collector):
        return

    if _replay_env_depth == 0:
        _set_replay_env()
    _replay_env_depth += 1


def pytest_collectreport(report):
    global _replay_env_depth

    if not _is_replay_collector(report):
        return

    _replay_env_depth -= 1
    if _replay_env_depth == 0:
        _restore_replay_env()


def pytest_sessionfinish(session, exitstatus):  # pragma: no cover - safety net
    _close_replay_app_state_impl()
    _cleanup_replay_collection_runtime()
    _restore_replay_env()


@pytest.fixture(autouse=True)
def _replay_entity_plane_disabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENTITY_PLANE_ENABLED", "0")
    monkeypatch.setenv("MEMORY_BACKEND", "fallback")
    replay_portal_data_dir = Path(tempfile.mkdtemp(prefix="zava-replay-test-"))
    monkeypatch.setenv("PORTAL_DATA_DIR", str(replay_portal_data_dir))
    _clear_active_runtime_cache()
    yield
    _clear_active_runtime_cache()
    shutil.rmtree(replay_portal_data_dir, ignore_errors=True)
    _clear_active_runtime_cache()


@pytest.fixture(scope="module", autouse=True)
def _close_replay_app_state():
    yield
    _close_replay_app_state_impl()


def _close_replay_app_state_impl() -> None:
    state_mod = sys.modules.get("api.server.state")
    if state_mod is None:
        return
    app_state = getattr(state_mod, "app_state", None)
    if app_state is None:
        return
    asyncio.run(app_state.aclose())
