from __future__ import annotations

import os
import subprocess
import sys


SCRIPT = """
from api.functions.graphs.executors.agents._wrapper import SKILLS_DIR
print(SKILLS_DIR)
"""


def _skill_root(vertical: str, tmp_path) -> str:
    environment = os.environ.copy()
    environment.update(
        {
            "AZURE_STORAGE_CONNECTION_STRING": "",
            "ENTITY_PLANE_ENABLED": "0",
            "PORTAL_DATA_DIR": str(tmp_path),
            "ZAVA_VERTICAL": vertical,
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", SCRIPT],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()[-1]


def test_functions_use_the_active_pack_skill_root(tmp_path):
    assert _skill_root("agency", tmp_path).endswith("api/server/skills")
    assert _skill_root("telco", tmp_path).endswith("verticals/telco/skills")
