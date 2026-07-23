from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]


@pytest.mark.parametrize("vertical", ["telco", "fashion"])
def test_inactive_agency_ambient_agents_are_not_discovered(
    vertical: str,
) -> None:
    result = subprocess.run(
        [
            "uv",
            "run",
            "--frozen",
            "--no-sync",
            "python",
            "-c",
            (
                "import json; "
                "from api.server.services.ambient_agents import AMBIENT_AGENTS; "
                "print(json.dumps(sorted(AMBIENT_AGENTS)))"
            ),
        ],
        cwd=ROOT,
        env={**os.environ, "ZAVA_VERTICAL": vertical},
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == []

