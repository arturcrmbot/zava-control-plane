from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def test_env_loader_preserves_explicit_empty_values_without_indirect_expansion(tmp_path):
    helper = ROOT / "scripts/lib/compose-start.sh"
    assert "${!" not in helper.read_text()
    (tmp_path / ".env").write_text("ZAVA_TEST_SETTING=from-file\nZAVA_TEST_OTHER=loaded\n")
    env = {
        **os.environ,
        "ZAVA_REPO_ROOT": str(tmp_path),
        "ZAVA_TEST_SETTING": "",
    }
    result = subprocess.run(
        ["bash", "-c", 'source "$1"; _export_env_file; printf "%s|%s" "$ZAVA_TEST_SETTING" "$ZAVA_TEST_OTHER"', "bash", str(helper)],
        env=env, check=True, capture_output=True, text=True,
    )
    assert result.stdout == "|loaded"


def test_local_demo_services_bind_to_loopback():
    helper = (ROOT / "scripts/lib/compose-start.sh").read_text()
    boot = (ROOT / "scripts/boot-demo.sh").read_text()
    scripts = json.loads((ROOT / "package.json").read_text())["scripts"]
    assert "--host 127.0.0.1 --port 3101" in helper
    assert helper.count("Kestrel__Endpoints__Local__Url=http://127.0.0.1:7071") == 2
    assert "--blobHost 127.0.0.1 --queueHost 127.0.0.1 --tableHost 127.0.0.1" in boot
    for name in ("demo:ui", "demo:portal", "demo:blueprint"):
        assert "--host 127.0.0.1" in scripts[name]
