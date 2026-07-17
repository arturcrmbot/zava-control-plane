from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "telco_process_profiles_proof.py"


def _run(*args: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_profile_proof_declares_bounded_contract():
    assert _run("--print-contract") == {
        "workflow_types": 37,
        "hero_workflows": 9,
        "standard_profiles": 28,
        "workflow_engines": 6,
        "skills": 8,
        "mcp_packs": 4,
    }


def test_profile_proof_resolves_every_standard_objective():
    result = _run()

    assert result["result"] == "PASS"
    assert len(result["profiles"]) == 28
    assert {
        row["workflow_type"] for row in result["profiles"]
    } == set(result["workflow_types"])
    assert all(row["objective_status"] == "resolved" for row in result["profiles"])
    assert all(row["evaluation_status"] == "resolved" for row in result["profiles"])
    assert all(row["source_mode"] == "simulated" for row in result["profiles"])
