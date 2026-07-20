import json
import subprocess
from pathlib import Path

from verticals.fashion.process_profiles import FASHION_PROCESS_PROFILES


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "fashion_zava_e2e_proof.sh"


def test_fashion_proof_declares_the_permanent_evidence_contract() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "--print-contract"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == {
        "vertical": "fashion",
        "workflows": list(FASHION_PROCESS_PROFILES),
        "surfaces": [
            "world",
            "workflow-api",
            "drawer",
            "memory",
            "knowledge",
            "ag-ui",
            "graph",
            "constellation",
        ],
        "evidence": [
            "manifest.json",
            "summary.json",
            "world-journal.json",
            "durable-instances.json",
            "entity-graph.json",
            "memory.json",
            "ag-ui.json",
            "recordings",
            "screenshots",
            "video",
            "logs",
            "before",
            "after",
        ],
    }


def test_fashion_proof_emits_a_pass_manifest_for_all_workflows(
    tmp_path,
) -> None:
    output = tmp_path / "proof"
    subprocess.run(
        ["bash", str(SCRIPT), "--output", str(output)],
        cwd=ROOT,
        check=True,
    )

    manifest = json.loads(
        (output / "manifest.json").read_text(encoding="utf-8")
    )
    source_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert manifest["status"] == "PASS"
    assert manifest["vertical"] == "fashion"
    assert manifest["source_commit"] == source_commit
    assert set(manifest["workflows"]) == set(FASHION_PROCESS_PROFILES)
    assert all(
        result["status"] == "PASS"
        for result in manifest["workflows"].values()
    )
    assert manifest["replay"] == {
        "functions_disabled": "PASS",
        "actor_world_disabled": "PASS",
    }
    assert manifest["browser"] == {
        "console_errors": 0,
        "dropped_workflow_events": 0,
        "status": "PASS",
    }
    assert manifest["teardown"]["status"] == "PASS"
    assert all(
        (output / path).exists() for path in manifest["evidence_paths"]
    )

    for result in manifest["workflows"].values():
        assert set(result["surfaces"]) == {
            "world",
            "workflow-api",
            "drawer",
            "memory",
            "knowledge",
            "ag-ui",
            "graph",
            "constellation",
        }
        assert set(result["surfaces"].values()) == {"PASS"}
        assert result["chain"]["actor_world"] == "PASS"
        assert result["chain"]["sensor"] == "PASS"
        assert result["chain"]["objective"] == "PASS"
        assert result["chain"]["durable"] == "PASS"
        assert result["chain"]["typed_command"] == "PASS"
        assert result["chain"]["world_mutation"] == "PASS"
        assert result["chain"]["evaluation"] == "PASS"
