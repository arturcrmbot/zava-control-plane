"""Exercise container process supervision with disposable child processes."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest


ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = ROOT / "deploy" / "entrypoint.sh"


def wait_for(predicate, *, timeout: float = 8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.05)
    pytest.fail("Timed out waiting for entrypoint child process")


@pytest.fixture
def launch_entrypoint(tmp_path):
    processes = []
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir()
    child_script = f"""#!{sys.executable}
import json, os, signal, subprocess, sys, time
from pathlib import Path
name = Path(sys.argv[0]).name
root = Path(os.environ["ENTRYPOINT_TEST_DIR"])
(root / (name + ".pid")).write_text(str(os.getpid()))
def stop(signum, frame):
    (root / (name + ".stopped")).write_text(str(signum))
    raise SystemExit(0)
signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
if name == os.environ.get("IGNORE_TERM_CHILD"):
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
if name == "func" and os.environ.get("SPAWN_WORKER") == "1":
    subprocess.Popen([str(Path(sys.argv[0]).with_name("worker"))])
(root / (name + ".ready")).write_text(json.dumps({{
    "argv": sys.argv[1:],
    "portal_data_dir": os.environ.get("PORTAL_DATA_DIR"),
    "xdg_data_home": os.environ.get("XDG_DATA_HOME"),
    "pythonpath": os.environ.get("PYTHONPATH"),
    "write_xor_execute": os.environ.get("DOTNET_EnableWriteXorExecute"),
}}))
while not (root / (name + ".exit")).exists():
    time.sleep(0.05)
raise SystemExit(int((root / (name + ".exit")).read_text()))
"""
    for name in ("func", "uvicorn", "worker"):
        target = binary_dir / name
        target.write_text(child_script)
        target.chmod(0o755)
    # Map the container's WORKDIR for host-side tests without requiring /app.
    bash_env = tmp_path / "bash-env"
    bash_env.write_text(
        'cd() { if [[ "${1:-}" == /app ]]; then builtin cd "$ENTRYPOINT_TEST_DIR"; '
        'else builtin cd "$@"; fi; }\n'
    )

    def launch(**overrides):
        env = {
            key: value for key, value in os.environ.items()
            if not key.startswith(("DOTNET_", "COMPlus_", "ZAVA_FUNCTIONS_"))
        }
        env.update(
            PATH=f"{binary_dir}{os.pathsep}{env['PATH']}",
            HOME=str(tmp_path / "home"),
            XDG_DATA_HOME=str(tmp_path / "local-data"),
            ENTRYPOINT_TEST_DIR=str(tmp_path),
            BASH_ENV=str(bash_env),
            FUNC_PORTAL_DATA_DIR=str(tmp_path / "functions-data"),
            PORTAL_DATA_DIR=str(tmp_path / "api-data"),
            ZAVA_MODE="live",
            FUNC_PORT="17071",
            PORT="18080",
        )
        for key, value in overrides.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        log = (tmp_path / "entrypoint.log").open("w")
        process = subprocess.Popen(
            ["bash", str(ENTRYPOINT)], cwd=tmp_path, env=env,
            stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        processes.append((process, log))
        return process, tmp_path

    yield launch
    for process, log in processes:
        for pid_file in tmp_path.glob("*.pid"):
            try:
                os.kill(int(pid_file.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)
        log.close()


@pytest.mark.parametrize("failed_child,status", [("func", 7), ("uvicorn", 9), ("func", 0), ("uvicorn", 0)])
def test_live_exits_when_either_service_exits(launch_entrypoint, failed_child, status):
    process, work = launch_entrypoint(SPAWN_WORKER="1")
    wait_for(lambda: all((work / f"{name}.ready").exists() for name in ("func", "uvicorn", "worker")))
    (work / f"{failed_child}.exit").write_text(str(status))

    wait_for(lambda: process.poll() is not None)

    assert process.returncode == (status or 1)
    other = "uvicorn" if failed_child == "func" else "func"
    assert (work / f"{other}.stopped").exists()
    assert (work / "worker.stopped").exists()


@pytest.mark.parametrize("signum,status", [(signal.SIGTERM, 143), (signal.SIGINT, 130)])
def test_signals_stop_both_services_and_functions_worker(launch_entrypoint, signum, status):
    process, work = launch_entrypoint(SPAWN_WORKER="1")
    wait_for(lambda: all((work / f"{name}.ready").exists() for name in ("func", "uvicorn", "worker")))

    process.send_signal(signum)
    wait_for(lambda: process.poll() is not None)

    assert process.returncode == status
    assert all((work / f"{name}.stopped").exists() for name in ("func", "uvicorn", "worker"))


def test_replay_execs_only_the_api(launch_entrypoint):
    process, work = launch_entrypoint(ZAVA_MODE="replay")
    wait_for(lambda: (work / "uvicorn.ready").exists())

    assert not (work / "func.pid").exists()
    assert int((work / "uvicorn.pid").read_text()) == process.pid
    process.send_signal(signal.SIGTERM)
    assert process.wait(timeout=5) == 0


def test_shutdown_is_bounded_for_an_unresponsive_worker(launch_entrypoint):
    process, work = launch_entrypoint(SPAWN_WORKER="1", IGNORE_TERM_CHILD="worker")
    wait_for(lambda: all((work / f"{name}.ready").exists() for name in ("func", "uvicorn", "worker")))
    (work / "func.exit").write_text("7")

    wait_for(lambda: process.poll() is not None)

    assert process.returncode == 7
    assert (work / "uvicorn.stopped").exists()
    assert not (work / "worker.stopped").exists()


def test_creates_default_local_application_data_directory(launch_entrypoint):
    process, work = launch_entrypoint(XDG_DATA_HOME=None)
    wait_for(lambda: (work / "func.ready").exists())
    func = json.loads((work / "func.ready").read_text())

    assert func["xdg_data_home"] == str(work / "home" / ".local" / "share")
    assert Path(func["xdg_data_home"]).is_dir()
    process.send_signal(signal.SIGTERM)
    wait_for(lambda: process.poll() is not None)


@pytest.mark.parametrize("compat,explicit,expected", [("0", "", None), ("1", "", "0"), ("1", "1", "1")])
def test_functions_native_compatibility_is_opt_in(launch_entrypoint, compat, explicit, expected):
    overrides = {"ZAVA_FUNCTIONS_QEMU_COMPAT": compat}
    if explicit:
        overrides["DOTNET_EnableWriteXorExecute"] = explicit
    process, work = launch_entrypoint(**overrides)
    wait_for(lambda: (work / "func.ready").exists() and (work / "uvicorn.ready").exists())
    func = json.loads((work / "func.ready").read_text())
    api = json.loads((work / "uvicorn.ready").read_text())

    assert func["write_xor_execute"] == expected
    assert api["write_xor_execute"] == (explicit or None)
    assert Path(func["xdg_data_home"]).is_dir()
    assert func["portal_data_dir"] == str(work / "functions-data")
    assert api["portal_data_dir"] == str(work / "api-data")
    assert func["pythonpath"] == "/app"
    assert func["argv"] == ["host", "start", "--port", "17071", "--no-build"]
    assert api["argv"] == ["api.server.main:app", "--host", "0.0.0.0", "--port", "18080", "--workers", "1"]
    process.send_signal(signal.SIGTERM)
    wait_for(lambda: process.poll() is not None)


def test_runtime_pins_the_verified_core_tools_package():
    dockerfile = (ROOT / "deploy" / "Dockerfile").read_text()
    assert "ARG AZURE_FUNCTIONS_CORE_TOOLS_VERSION=4.9.0-1" in dockerfile
    assert 'azure-functions-core-tools-4="${AZURE_FUNCTIONS_CORE_TOOLS_VERSION}"' in dockerfile


def test_runtime_precaches_bundles_from_project_host_configuration():
    runtime = (ROOT / "deploy" / "Dockerfile").read_text().split("AS runtime", 1)[1]
    assert "ARG AZURE_FUNCTIONS_EXTENSION_BUNDLE_VERSION=4.17.0" in runtime
    assert "03978c7058cdf22458e23570e944a4f2636afe5ad2808081a53c3644332b7fbf" in runtime
    assert "https://cdn.functions.azure.com/public/ExtensionBundles/" in runtime
    assert "sha256sum --check" in runtime
    assert runtime.index("python -m zipfile -e") < runtime.index("COPY --from=py-build /app /app")
    assert "/root/.azure-functions-core-tools/Functions/ExtensionBundles/" in runtime
    version_range = json.loads((ROOT / "host.json").read_text())["extensionBundle"]["version"]
    minimum, maximum = (
        tuple(int(part) for part in version.strip().split("."))
        for version in version_range[1:-1].split(",")
    )
    assert minimum <= (4, 17, 0) < maximum
