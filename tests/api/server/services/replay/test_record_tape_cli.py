from __future__ import annotations

import asyncio
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
ENTRYPOINT_PATH = REPO_ROOT / "scripts" / "_record_entrypoint.py"
SCRIPT_PATH = REPO_ROOT / "scripts" / "record_tape.sh"


def _load_entrypoint_module():
    spec = importlib.util.spec_from_file_location("scripts__record_entrypoint", ENTRYPOINT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_record_entrypoint_parse_requires_out_and_defaults_min_seconds() -> None:
    entrypoint = _load_entrypoint_module()

    args = entrypoint._parse(["--out", "tapes/demo.tar.gz"])

    assert args.out == Path("tapes/demo.tar.gz")
    assert args.min_seconds == 0


@pytest.mark.asyncio
async def test_wait_for_stop_ignores_early_signal_until_min_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    entrypoint = _load_entrypoint_module()

    stop_event = asyncio.Event()
    observed_messages: list[str] = []
    clock = {"now": 100.0}

    monkeypatch.setattr(entrypoint.time, "monotonic", lambda: clock["now"])

    async def trigger_signals() -> None:
        stop_event.set()
        await asyncio.sleep(0)
        clock["now"] = 112.0
        stop_event.set()

    task = asyncio.create_task(
        entrypoint._wait_for_stop(
            stop_event=stop_event,
            start_mono=100.0,
            min_seconds=10,
            log=lambda message: observed_messages.append(message),
        )
    )
    await trigger_signals()
    await task

    assert observed_messages == ["[record] ignoring early signal — 10s of min duration remain"]


def test_record_tape_rejects_invalid_duration() -> None:
    env = os.environ.copy()
    env["DURATION"] = "10x"
    env["OUT"] = "tapes/invalid.tar.gz"
    env.setdefault("AZURE_STORAGE_CONNECTION_STRING", "")

    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 2
    assert "DURATION must end with s/m/h" in proc.stderr


def test_record_tape_retries_sigterm_until_entrypoint_min_seconds_elapses(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_uv = fake_bin / "uv"
    fake_uv.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "OUT=''\n"
        "MIN_SECONDS=0\n"
        "while (($#)); do\n"
        "  case \"$1\" in\n"
        "    --out) OUT=\"$2\"; shift 2 ;;\n"
        "    --min-seconds) MIN_SECONDS=\"$2\"; shift 2 ;;\n"
        "    *) shift ;;\n"
        "  esac\n"
        "done\n"
        "READY_AT=$(( $(date +%s) + 2 + MIN_SECONDS ))\n"
        "stop() {\n"
        "  local now\n"
        "  now=$(date +%s)\n"
        "  if (( now < READY_AT )); then\n"
        "    return\n"
        "  fi\n"
        "  mkdir -p \"$(dirname \"$OUT\")\"\n"
        "  : > \"$OUT\"\n"
        "  exit 0\n"
        "}\n"
        "trap stop TERM INT\n"
        "while true; do sleep 0.2; done\n",
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)

    out_path = tmp_path / "tape.tar.gz"
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["DURATION"] = "1s"
    env["OUT"] = str(out_path)
    env.setdefault("AZURE_STORAGE_CONNECTION_STRING", "")

    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=8,
    )

    assert proc.returncode == 0
    assert out_path.exists()
