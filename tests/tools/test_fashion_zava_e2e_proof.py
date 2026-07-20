"""Proof-contract tests for the live Fashion end-to-end proof.

These assert the *contract and structure* that guarantee the proof is genuinely
live — it boots the shared actor-world stack, drives every workflow through real
runtime routes, derives its verdicts from live observation, and runs genuine
negative probes. The heavy live run itself is `make prove VERTICAL=fashion`.
The manifest-schema test exercises the assembler deterministically."""
import json
import os
import subprocess
from pathlib import Path

from verticals.fashion.process_profiles import FASHION_PROCESS_PROFILES


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "fashion_zava_e2e_proof.sh"
DRIVER = ROOT / "tools" / "fashion_zava_e2e_proof.mjs"
MANIFEST_TOOL = ROOT / "tools" / "fashion_proof_manifest.py"
STACK_LIB = ROOT / "tools" / "lib" / "actor_world_proof_stack.sh"
WORKFLOWS = list(FASHION_PROCESS_PROFILES)


def test_fashion_proof_prints_isolated_stack_config():
    result = subprocess.run(
        ["bash", str(SCRIPT), "--print-config"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    config = json.loads(result.stdout)

    assert config["vertical"] == "fashion"
    assert config["api_port"] == 13301
    assert config["functions_port"] == 17181
    assert config["control_plane_port"] == 15373
    assert config["blueprint_port"] == 15375
    assert config["azurite_ports"] == [12000, 12001, 12002]
    assert config["driver"] == "tools/fashion_zava_e2e_proof.mjs"
    # Isolated from the telco proof ports (11000-2/13101/17171/15273/15275).
    assert config["api_port"] != 13101 and config["functions_port"] != 17171


def test_fashion_proof_sources_parse():
    subprocess.run(["bash", "-n", str(SCRIPT)], cwd=ROOT, check=True)
    subprocess.run(["node", "--check", str(DRIVER)], cwd=ROOT, check=True)


def test_fashion_proof_driver_declares_cross_surface_contract():
    result = subprocess.run(
        ["node", str(DRIVER), "--print-contract"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    contract = json.loads(result.stdout)

    assert contract["vertical"] == "fashion"
    assert contract["workflows"] == WORKFLOWS
    assert contract["surfaces"] == [
        "world",
        "workflow-api",
        "drawer",
        "memory",
        "knowledge",
        "ag-ui",
        "graph",
        "constellation",
    ]
    assert contract["chain"] == [
        "actor_world",
        "sensor",
        "objective",
        "durable",
        "typed_command",
        "world_mutation",
        "evaluation",
    ]


def test_fashion_proof_boots_the_shared_actor_world_stack():
    source = SCRIPT.read_text(encoding="utf-8")

    # Reuses the established stack manager rather than inventing another.
    assert "tools/lib/actor_world_proof_stack.sh" in source
    assert 'PROOF_WORLD="fashion"' in source
    assert "start_azurite" in source
    assert "start_functions_host" in source
    assert "start_fastapi" in source
    # Boots the real Control Plane and Blueprint Vite apps.
    assert "node_modules/.bin/vite" in source
    assert "web/blueprint" in source


def test_fashion_proof_indexes_every_orchestrator():
    source = SCRIPT.read_text(encoding="utf-8")

    expected = {
        profile.orchestrator_name
        for profile in FASHION_PROCESS_PROFILES.values()
    }
    for orchestrator in expected:
        assert orchestrator in source, orchestrator
    assert "did not index" in source  # fail-fast when an orchestrator is absent


def test_fashion_proof_drives_workflows_through_real_runtime_routes():
    driver = DRIVER.read_text(encoding="utf-8")

    assert "/api/world/processes/${type}/run" in driver
    assert "/api/workflows" in driver
    assert "/api/world/events?after=0" in driver
    # Durable evidence read from the real Functions host, not a literal.
    assert "runtime/webhooks/durabletask/instances" in driver
    assert 'runtimeStatus === "Completed"' in driver
    # Entity graph Workflow node verified.
    assert "/api/entities/" in driver and '_label === "Workflow"' in driver


def test_fashion_proof_uses_live_ui_not_a_static_dashboard():
    driver = DRIVER.read_text(encoding="utf-8")

    # Targets the live apps, never a generated local dashboard.
    assert "dashboard.html" not in driver
    assert "CONTROL_PLANE_BASE" in driver and "BLUEPRINT_BASE" in driver
    assert 'getByTestId("world-route")' in driver
    assert 'getByTestId("run-panel")' in driver
    assert "Live · org decisions and insights" in driver
    assert "/api/blueprint/stream" in driver


def test_fashion_proof_runs_genuine_negative_probes():
    source = SCRIPT.read_text(encoding="utf-8")
    driver = DRIVER.read_text(encoding="utf-8")

    # Functions-disabled negative probe: stop the host, probe, restart, recover.
    assert "--probe-functions-disabled" in source
    assert 'kill_tree "$FUNC_PID" "functions-host"' in source
    assert "confirming recovery" in source
    assert "runFunctionsDisabledProbe" in driver
    assert "phantom" in driver.lower()
    assert "HTTP 500" in driver
    # Actor-world-disabled replay probe (Functions + world disabled).
    assert "ZAVA_BLUEPRINT_REPLAY_ONLY=1" in source
    assert 'node "$DRIVER" --replay' in source
    assert "actor world is enabled during actor-world-disabled replay" in driver
    assert "deadLetters" in driver


def test_fashion_proof_fails_fast_and_gates_on_browser_errors():
    driver = DRIVER.read_text(encoding="utf-8")

    assert "class ProofError" in driver
    assert "if (error instanceof ProofError)" in driver
    assert "evidence.browserErrors.length === 0" in driver


def test_fashion_proof_supports_replay_only_validation():
    source = SCRIPT.read_text(encoding="utf-8")

    assert '"--replay-only"' in source
    assert "ZAVA_BLUEPRINT_REPLAY_ONLY=1" in source


def test_fashion_proof_releases_every_port_on_teardown():
    source = SCRIPT.read_text(encoding="utf-8")

    assert "port_listening" in source
    assert "still listening after teardown" in source
    assert "all proof ports released" in source


def _fabricate_evidence(out_dir: Path, *, live="PASS", fd="PASS", replay="PASS"):
    workflows = {
        wtype: {
            "status": "PASS",
            "workflow_id": f"wf-{index}",
            "surfaces": {
                surface: "PASS"
                for surface in (
                    "world",
                    "workflow-api",
                    "drawer",
                    "memory",
                    "knowledge",
                    "ag-ui",
                    "graph",
                    "constellation",
                )
            },
            "chain": {node: "PASS" for node in ("actor_world", "sensor")},
        }
        for index, wtype in enumerate(WORKFLOWS)
    }
    (out_dir / "summary.json").write_text(
        json.dumps({"result": live, "workflows": workflows, "browserErrors": []}),
        encoding="utf-8",
    )
    (out_dir / "functions-disabled.json").write_text(
        json.dumps({"result": fd, "browserErrors": []}), encoding="utf-8"
    )
    (out_dir / "replay-summary.json").write_text(
        json.dumps({"result": replay, "browserErrors": []}), encoding="utf-8"
    )


def _run_manifest(out_dir: Path):
    env = {
        **os.environ,
        "PROOF_OUT_DIR": str(out_dir),
        "SOURCE_COMMIT": "deadbeef",
        "TEARDOWN_STATUS": "PASS",
        "PORTS_RELEASED": "yes",
    }
    return subprocess.run(
        ["uv", "run", "--frozen", "--no-sync", "python", str(MANIFEST_TOOL)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def test_manifest_assembler_emits_required_schema_on_pass(tmp_path):
    _fabricate_evidence(tmp_path)

    result = _run_manifest(tmp_path)
    assert result.returncode == 0, result.stderr

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["vertical"] == "fashion"
    assert manifest["source_commit"] == "deadbeef"
    assert manifest["status"] == "PASS"
    assert manifest["live"] == "PASS"
    assert manifest["replay"] == "PASS"
    assert manifest["browser_errors"] == []
    assert set(manifest["workflows"]) == set(WORKFLOWS)
    assert manifest["replay_probes"] == {
        "functions_disabled": "PASS",
        "actor_world_disabled": "PASS",
    }
    assert manifest["teardown"]["status"] == "PASS"
    assert manifest["evidence_paths"], "evidence_paths must not be empty"


def test_manifest_assembler_fails_when_a_probe_fails(tmp_path):
    _fabricate_evidence(tmp_path, fd="FAIL")

    result = _run_manifest(tmp_path)
    assert result.returncode != 0

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "FAIL"
    assert manifest["replay_probes"]["functions_disabled"] == "FAIL"
