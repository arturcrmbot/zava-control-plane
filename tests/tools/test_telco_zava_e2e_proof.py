import json
import os
import subprocess
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "telco_zava_e2e_proof.sh"
DRIVER = ROOT / "tools" / "telco_zava_e2e_proof.mjs"
STACK_LIB = ROOT / "tools" / "lib" / "actor_world_proof_stack.sh"


def test_telco_proof_prints_isolated_stack_config():
    result = subprocess.run(
        ["bash", str(SCRIPT), "--print-config"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == {
        "api_port": 13101,
        "azurite_ports": [11000, 11001, 11002],
        "blueprint_port": 15275,
        "control_plane_port": 15273,
        "data_root": f"/tmp/zava-telco-proof-{os.getuid()}",
        "driver": "tools/telco_zava_e2e_proof.mjs",
        "functions_port": 17171,
        "vertical": "telco",
        "world_minutes_per_second": 10,
    }


def test_telco_proof_sources_parse():
    subprocess.run(["bash", "-n", str(SCRIPT)], cwd=ROOT, check=True)
    subprocess.run(["node", "--check", str(DRIVER)], cwd=ROOT, check=True)


def test_telco_proof_supports_replay_only_validation():
    source = SCRIPT.read_text(encoding="utf-8")

    assert '"--replay-only"' in source
    assert '"replay evidence missing: $OUT_DIR/recordings"' in source


def test_telco_proof_driver_declares_cross_surface_contract():
    result = subprocess.run(
        ["node", str(DRIVER), "--print-contract"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == {
        "evidence": [
            "summary.json",
            "world-journal.json",
            "durable-instances.json",
            "entity-graph.json",
            "recordings",
            "screenshots",
            "video",
        ],
        "surfaces": [
            "world",
            "workflow-drawer",
            "memory",
            "knowledge",
            "ag-ui",
            "constellation",
        ],
        "workflows": [
            "network-incident",
            "proactive-customer-care",
            "order-to-activate",
            "outage-risk-management",
            "predictive-site-maintenance",
            "field-repair-dispatch",
            "capacity-optimization",
            "service-ticket-resolution",
            "retention-orchestration",
        ],
        "standard_samples": [
            "core-network-anomaly-management",
            "ran-capacity-planning",
            "billing-dispute-resolution",
            "service-provisioning-activation",
            "revenue-assurance",
            "contact-centre-agent-assist",
        ],
    }


def test_telco_proof_drives_all_four_real_scenarios_and_fails_fast():
    source = DRIVER.read_text(encoding="utf-8")

    for name in (
        "storm-cascade",
        "maintenance-save",
        "capacity-revenue",
        "vulnerable-retention",
    ):
        assert name in source
    assert "if (error instanceof ProofError)" in source


def test_telco_proof_runs_one_standard_profile_per_engine():
    source = DRIVER.read_text(encoding="utf-8")

    for workflow_type in (
        "core-network-anomaly-management",
        "ran-capacity-planning",
        "billing-dispute-resolution",
        "service-provisioning-activation",
        "revenue-assurance",
        "contact-centre-agent-assist",
    ):
        assert workflow_type in source
    assert "/api/world/processes/${type}/run" in source


def test_telco_proof_uses_deterministic_agents_and_indexes_nine_orchestrators():
    source = SCRIPT.read_text(encoding="utf-8")

    assert 'ZAVA_TELCO_AGENT_MODE="deterministic"' in source
    assert 'MAX_OBSERVATORY_EVENTS_PER_SEC="2000"' in source
    assert source.count("Orchestrator") >= 9


def test_telco_proof_queries_workflow_nodes_and_connected_graph_topology():
    source = DRIVER.read_text(encoding="utf-8")

    assert "/api/entities/${encodeURIComponent(workflow.id)}" in source
    assert "workflowNodes" in source
    assert "graph.edges.length > 0" in source


def test_telco_proof_links_control_plane_to_isolated_blueprint():
    source = SCRIPT.read_text(encoding="utf-8")

    assert 'VITE_BLUEPRINT_URL="http://127.0.0.1:$BLUEPRINT_PORT"' in source


def test_telco_replay_checks_only_the_isolated_functions_port():
    source = SCRIPT.read_text(encoding="utf-8")

    assert 'FUNCTIONS_HOST="http://127.0.0.1:$FUNCTIONS_PORT"' in source


def test_actor_world_stack_accepts_isolated_port_overrides(tmp_path):
    command = f"""
      export ACTOR_PROOF_ROOT={tmp_path}
      export ACTOR_PROOF_AZ_BLOB_PORT=11000
      export ACTOR_PROOF_AZ_QUEUE_PORT=11001
      export ACTOR_PROOF_AZ_TABLE_PORT=11002
      export ACTOR_PROOF_FUNCTIONS_PORT=17171
      export ACTOR_PROOF_API_PORT=13101
      source {STACK_LIB}
      printf '%s|%s|%s|%s\\n' "${{AZ_PORTS[*]}}" "$FUNC_PORT" "$API_PORT" "$COMPOSE_DIR"
    """
    result = subprocess.run(
        ["bash", "-c", command],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == (
        f"11000 11001 11002|17171|13101|{tmp_path}"
    )


def test_actor_world_stack_pins_python_functions_worker():
    source = STACK_LIB.read_text(encoding="utf-8")

    assert "FUNCTIONS_WORKER_RUNTIME=python" in source


def test_actor_world_stack_tolerates_transient_azurite_probe_failure(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    azurite = bin_dir / "azurite"
    azurite.write_text(
        "#!/usr/bin/env bash\n"
        "trap 'exit 0' TERM\n"
        "while true; do sleep 1; done\n",
        encoding="utf-8",
    )
    curl = bin_dir / "curl"
    curl.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            count_file="${FAKE_CURL_COUNT}"
            count=0
            [[ -f "$count_file" ]] && count="$(cat "$count_file")"
            count=$((count + 1))
            printf '%s' "$count" > "$count_file"
            [[ "$count" -lt 3 ]] && exit 7
            printf '400'
            """
        ),
        encoding="utf-8",
    )
    azurite.chmod(0o755)
    curl.chmod(0o755)
    command = f"""
      set -e
      export PATH={bin_dir}:$PATH
      export FAKE_CURL_COUNT={tmp_path / "curl-count"}
      export ACTOR_PROOF_ROOT={tmp_path / "run"}
      source {STACK_LIB}
      start_azurite
      kill_tree "$AZ_PID" azurite
    """

    result = subprocess.run(
        ["bash", "-c", command],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Azurite ready" in result.stdout
