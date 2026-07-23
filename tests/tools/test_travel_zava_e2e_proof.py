"""Contract tests for the generated Travel E2E proof runners.

These tests deliberately inspect fresh generator output rather than committed
runner files, so the pack generator remains the only owner of the runners.
They cover the durable proof contract without attempting to run local services.
"""
from __future__ import annotations

import json
import os
import re
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from verticals.travel.generator.render import generate


_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNNER_PATHS = (
    "tools/travel_zava_e2e_proof.sh",
    "tools/travel_zava_e2e_proof.py",
    "tools/travel_zava_browser_proof.mjs",
)
_REQUIRED_BUNDLE_ARTIFACTS = (
    "proof/manifest.json",
    "proof/live-summary.json",
    "proof/replay-summary.json",
    "proof/screenshots/",
    "proof/recordings/",
    "proof/world-snapshot-before.json",
    "proof/world-snapshot-after.json",
    "proof/generation-manifest.json",
    "proof/seller-review.json",
    "proof/consecutive-runs.json",
)
_REQUIRED_MANIFEST_FIELDS = (
    "source_commit",
    "vertical",
    "runtime_fingerprint",
    "live_result",
    "replay_result",
    "substrate_result",
    "demo_result",
    "seller_review",
    "browserErrors",
    "live_summary",
    "replay_summary",
    "consecutive_runs",
)


def _generated_root(tmp_path: Path) -> Path:
    generate(target_root=tmp_path)
    return tmp_path


def _generated_text(root: Path, relative_path: str) -> str:
    return (root / relative_path).read_text(encoding="utf-8")


def _generated_runner_namespace(tmp_path: Path) -> dict[str, object]:
    root = _generated_root(tmp_path)
    return runpy.run_path(str(root / "tools/travel_zava_e2e_proof.py"))


def _clean_run_manifest() -> dict[str, object]:
    return {
        "live_result": "PASS",
        "replay_result": "PASS",
        "substrate_result": "PASS",
        "demo_result": "PASS",
        "seller_review": "PENDING",
        "browserErrors": [],
        "live_summary": {
            "browser": {
                "dropped_workflow_events": 0,
            },
        },
        "replay_summary": {"result": "PASS"},
        "teardown": {"orphan_ports": {}},
        "failures": [],
    }


def test_generated_runner_ledger_records_only_clean_consecutive_runs(
    tmp_path: Path,
) -> None:
    """Two actual clean invocations form an ordered, same-runtime proof pair."""
    namespace = _generated_runner_namespace(tmp_path)
    build_ledger = namespace["build_consecutive_run_ledger"]
    fingerprint = {"python": "3.12.0", "node": "v22.0.0", "runtime": {"vertical": "travel"}}
    first = build_ledger(
        None,
        source_commit="a" * 40,
        runtime_fingerprint=fingerprint,
        run_id="first-real-invocation",
        started_at="2026-07-23T12:00:00+00:00",
        completed_at="2026-07-23T12:01:00+00:00",
        manifest=_clean_run_manifest(),
    )
    second = build_ledger(
        first,
        source_commit="a" * 40,
        runtime_fingerprint=fingerprint,
        run_id="second-real-invocation",
        started_at="2026-07-23T12:02:00+00:00",
        completed_at="2026-07-23T12:03:00+00:00",
        manifest=_clean_run_manifest(),
    )

    assert first["vertical"] == "travel"
    assert len(first["records"]) == 1
    assert len(second["records"]) == 2
    first_record, second_record = second["records"]
    assert first_record["run_id"] == "first-real-invocation"
    assert second_record["run_id"] == "second-real-invocation"
    assert first_record["started_at"] < first_record["completed_at"] < second_record["started_at"]
    for record in second["records"]:
        assert record["source_commit"] == "a" * 40
        assert record["runtime_fingerprint"] == fingerprint
        assert {
            "live_result": "PASS",
            "replay_result": "PASS",
            "substrate_result": "PASS",
            "demo_result": "PASS",
            "seller_review": "PENDING",
            "browserErrors": [],
            "dropped_workflow_events": 0,
            "failures": [],
            "teardown": {"orphan_ports": {}},
        }.items() <= record.items()


def test_generated_runner_ledger_resets_after_failure_or_identity_change(
    tmp_path: Path,
) -> None:
    """A failed or different-source invocation cannot borrow a prior pass."""
    namespace = _generated_runner_namespace(tmp_path)
    build_ledger = namespace["build_consecutive_run_ledger"]
    fingerprint = {"python": "3.12.0", "node": "v22.0.0"}
    first = build_ledger(
        None,
        source_commit="a" * 40,
        runtime_fingerprint=fingerprint,
        run_id="first-real-invocation",
        started_at="2026-07-23T12:00:00+00:00",
        completed_at="2026-07-23T12:01:00+00:00",
        manifest=_clean_run_manifest(),
    )
    changed_source = build_ledger(
        first,
        source_commit="b" * 40,
        runtime_fingerprint=fingerprint,
        run_id="changed-source-invocation",
        started_at="2026-07-23T12:02:00+00:00",
        completed_at="2026-07-23T12:03:00+00:00",
        manifest=_clean_run_manifest(),
    )
    failed_manifest = _clean_run_manifest()
    failed_manifest["demo_result"] = "FAIL"
    failed_manifest["browserErrors"] = ["real browser failure"]
    failed = build_ledger(
        first,
        source_commit="a" * 40,
        runtime_fingerprint=fingerprint,
        run_id="failed-invocation",
        started_at="2026-07-23T12:02:00+00:00",
        completed_at="2026-07-23T12:03:00+00:00",
        manifest=failed_manifest,
    )

    assert [record["run_id"] for record in changed_source["records"]] == [
        "changed-source-invocation",
    ]
    assert failed["records"] == []


def test_generated_runner_manifest_embeds_the_verified_ledger_pair(
    tmp_path: Path,
) -> None:
    """The final manifest points at the durable ledger and carries its pair."""
    root = _generated_root(tmp_path)
    namespace = runpy.run_path(str(root / "tools/travel_zava_e2e_proof.py"))
    python_runner = _generated_text(root, "tools/travel_zava_e2e_proof.py")
    build_ledger = namespace["build_consecutive_run_ledger"]
    ledger_evidence = namespace["consecutive_run_manifest_evidence"]
    fingerprint = {"python": "3.12.0", "node": "v22.0.0"}
    first = build_ledger(
        None,
        source_commit="a" * 40,
        runtime_fingerprint=fingerprint,
        run_id="first-real-invocation",
        started_at="2026-07-23T12:00:00+00:00",
        completed_at="2026-07-23T12:01:00+00:00",
        manifest=_clean_run_manifest(),
    )
    ledger = build_ledger(
        first,
        source_commit="a" * 40,
        runtime_fingerprint=fingerprint,
        run_id="second-real-invocation",
        started_at="2026-07-23T12:02:00+00:00",
        completed_at="2026-07-23T12:03:00+00:00",
        manifest=_clean_run_manifest(),
    )
    evidence = ledger_evidence(ledger)

    assert evidence["path"] == "proof/consecutive-runs.json"
    assert evidence["required_successful_runs"] == 2
    assert evidence["result"] == "PASS"
    assert evidence["verified_pair"] == ledger["records"]
    assert "proof/consecutive-runs.json" in python_runner
    assert python_runner.index("previous_ledger = read_previous_consecutive_run_ledger()") < python_runner.index(
        "\n    clear_proof_root()\n"
    )
    assert python_runner.index("write_json(LEDGER, ledger)") < python_runner.index(
        'write_json(PROOF / "manifest.json", manifest)'
    )


def test_generated_browser_contract_proves_exact_workflow_detail_before_and_after_hitl(
    tmp_path: Path,
) -> None:
    """Playwright must prove the real detail panel, not only API state or pixels."""
    root = _generated_root(tmp_path)
    browser_runner = _generated_text(root, "tools/travel_zava_browser_proof.mjs")

    assert 'section[aria-label="Workflow detail"]' in browser_runner
    assert "visibleWorkflowDetail" in browser_runner
    assert "visible_workflow_id" in browser_runner
    assert "workflow-detail-pending.png" in browser_runner
    assert "workflow-detail-completed.png" in browser_runner
    assert "pending.packDetail?.hitl" not in browser_runner
    assert "workflow_id=${encodeURIComponent(workflowId)}" in browser_runner
    assert "HITL gate audit" in browser_runner
    assert "visible_hitl_audit" in browser_runner
    assert "workflow-detail-status" in browser_runner
    assert browser_runner.index("writePending({") < browser_runner.rindex(
        "assertPendingWorkflowDetail("
    )
    assert 'pendingDetail.panel.getByRole("button", { name: "Approve" })' in browser_runner
    assert 'completedDetail.panel.getByRole("button", { name: "Approve" })' in browser_runner
    assert "awaiting_hitl" in browser_runner
    assert '"outcome"' in browser_runner
    assert '"approved"' in browser_runner
    assert "typed command" in browser_runner.lower()
    assert "terminal evaluation" in browser_runner.lower()

    for visible_term in (
        "disruption id",
        "DIS-flight_cancellation-FLT-ZV204",
        "sensor id",
        "sensor:flight_cancellation_impact",
        "evidence event ids",
        "operations_controller",
        "head_of_operations",
        "travel_operations_check_flight_disruption",
        "reaccommodate_travellers",
        "alternatives",
        "capacity evidence",
        "new flight capacity",
        "incremental cost gbp",
        "material changes",
        "requires approval",
        "required role",
        "decision actor",
        "command id",
        "evaluation",
        "resolved",
    ):
        assert visible_term in browser_runner
    ordered_phases = (
        "detect",
        "assess_impact",
        "search_alternatives",
        "bound_options",
        "approve_material_change",
        "reaccommodate",
        "notify",
        "evaluate",
    )
    positions = [browser_runner.index(phase) for phase in ordered_phases]
    assert positions == sorted(positions)


def test_generated_runner_ledger_rejects_naive_or_mixed_timezone_timestamps(
    tmp_path: Path,
) -> None:
    """Malformed prior timestamps reset the ledger instead of crashing a proof."""
    namespace = _generated_runner_namespace(tmp_path)
    ordered_timestamps = namespace["ordered_timestamps"]

    assert ordered_timestamps(
        "2026-07-23T12:00:00",
        "2026-07-23T12:01:00+00:00",
    ) is False
    assert ordered_timestamps(
        "2026-07-23T12:00:00",
        "2026-07-23T12:01:00",
    ) is False


def test_generated_runner_fingerprint_covers_proof_and_workflow_detail_inputs(
    tmp_path: Path,
) -> None:
    """Uncommitted proof/UI changes cannot inherit a stale consecutive pass."""
    root = _generated_root(tmp_path)
    python_runner = _generated_text(root, "tools/travel_zava_e2e_proof.py")

    assert '"proof_contract"' in python_runner
    assert "hashlib.sha256" in python_runner
    for input_path in (
        "tools/travel_zava_e2e_proof.py",
        "tools/travel_zava_browser_proof.mjs",
        "verticals/travel/generation-manifest.json",
        "web/client/routes/SpatialWorld.tsx",
    ):
        assert input_path in python_runner


def test_generator_owns_the_three_external_proof_runners_and_records_hashes(
    tmp_path: Path,
) -> None:
    """Proof runners are approved external generated outputs, never hand edits."""
    manifest = generate(target_root=tmp_path)
    records = {record["path"]: record for record in manifest["records"]}

    assert set(_RUNNER_PATHS) <= set(records)
    for relative_path in _RUNNER_PATHS:
        record = records[relative_path]
        assert record["ownership"] == "generated-external"
        assert re.fullmatch(r"[0-9a-f]{64}", record["input_hash"])
        assert re.fullmatch(r"[0-9a-f]{64}", record["content_hash"])
        assert (tmp_path / relative_path).is_file()
    assert os.access(tmp_path / "tools/travel_zava_e2e_proof.sh", os.X_OK)


def test_generated_runner_contract_has_permanent_make_route_and_no_direct_start(
    tmp_path: Path,
) -> None:
    """The primary path is sensor-driven and make prove remains the entrypoint."""
    root = _generated_root(tmp_path)
    shell_runner = _generated_text(root, "tools/travel_zava_e2e_proof.sh")
    python_runner = _generated_text(root, "tools/travel_zava_e2e_proof.py")
    makefile = (_REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    combined = f"{shell_runner}\n{python_runner}"

    assert 'tools/$(VERTICAL)_zava_e2e_proof.sh' in makefile
    assert 'ZAVA_VERTICAL="$(VERTICAL)" "tools/$(VERTICAL)_zava_e2e_proof.sh"' in makefile
    assert "actor world" in combined.lower()
    assert "rising-edge" in combined.lower()
    assert "typed command" in combined.lower()
    assert not re.search(r"/processes/[^\"'\s]*/run", combined)
    assert not re.search(r"(?:start[-_ ]?(?:workflow|orchestration)|workflow[-_ ]?start)", combined, re.I)
    assert "run-process" not in combined.lower()


def test_generated_runner_contract_writes_separate_machine_results_and_pending_seller_review(
    tmp_path: Path,
) -> None:
    """Substrate, demo, and operator-owned seller review cannot imply each other."""
    root = _generated_root(tmp_path)
    python_runner = _generated_text(root, "tools/travel_zava_e2e_proof.py")

    for artifact in _REQUIRED_BUNDLE_ARTIFACTS:
        assert artifact in python_runner
    for field in _REQUIRED_MANIFEST_FIELDS:
        assert field in python_runner
    assert '"seller_review": "PENDING"' in python_runner
    assert "substrate_result" in python_runner
    assert "demo_result" in python_runner
    assert "seller_review" in python_runner
    assert "video" not in python_runner.lower()


def test_generated_runner_contract_asserts_exact_cross_surface_ids_and_semantic_visual_deltas(
    tmp_path: Path,
) -> None:
    """Visual evidence is tied to real actor IDs and journal events, not counters."""
    root = _generated_root(tmp_path)
    python_runner = _generated_text(root, "tools/travel_zava_e2e_proof.py")
    browser_runner = _generated_text(root, "tools/travel_zava_browser_proof.mjs")
    combined = f"{python_runner}\n{browser_runner}"

    for required in (
        "workflow_id",
        "actor_id",
        "journal_event",
        "world-snapshot-before.json",
        "world-snapshot-after.json",
        "Memory",
        "Knowledge",
        "AG-UI",
        "Constellation",
        "selected_actor",
        "changed_relationship",
        "auto-fired",
        "Relationship search",
        "knowledge-edge-BKG-4-RELATED_ASSET-FLT-ZV205",
    ):
        assert required in combined


def test_generated_runner_contract_covers_replay_browser_continuity_and_clean_teardown(
    tmp_path: Path,
) -> None:
    """Both disabled-service probes and zero-error/port gates are mandatory."""
    root = _generated_root(tmp_path)
    python_runner = _generated_text(root, "tools/travel_zava_e2e_proof.py")
    browser_runner = _generated_text(root, "tools/travel_zava_browser_proof.mjs")
    combined = f"{python_runner}\n{browser_runner}"

    for required in (
        "functions-disabled",
        "actor-world-disabled",
        "phantom",
        "dead letter",
        "browserErrors",
        "dropped_workflow_events",
        "7071",
        "3101",
        "5273",
        "restart",
    ):
        assert required in combined
    assert "recordVideo" not in browser_runner
    assert "video" not in browser_runner.lower()
    assert 'waitUntil: "domcontentloaded"' in browser_runner
    assert "waitUntil: \"networkidle\"" not in browser_runner
    assert "start_new_session=True" in python_runner
    assert "os.killpg" in python_runner


def test_disabled_world_probe_resolves_its_real_durable_hitl_gate(
    tmp_path: Path,
) -> None:
    """The allowed direct diagnostic proves Durable completion, not just start."""
    root = _generated_root(tmp_path)
    python_runner = _generated_text(root, "tools/travel_zava_e2e_proof.py")
    probe_start = python_runner.index("def actor_world_disabled_probe")
    probe_end = python_runner.index("\ndef restart_recovery_probe", probe_start)
    probe = python_runner[probe_start:probe_end]

    assert 'wait_for_status(workflow_id, "awaiting_hitl")' in probe
    assert "approve_gate(workflow_id" in probe
    assert 'wait_for_status(workflow_id, "completed")' in probe


def test_generated_runner_reads_agui_sse_only_through_terminal_event(
    tmp_path: Path,
) -> None:
    """The infinite AG-UI stream must close at RUN_FINISHED, not time out."""
    root = _generated_root(tmp_path)
    python_runner = _generated_text(root, "tools/travel_zava_e2e_proof.py")
    capture_start = python_runner.index("def capture_agui")
    capture_end = python_runner.index("\ndef capture_constellation", capture_start)
    capture = python_runner[capture_start:capture_end]

    assert "httpx.stream(" in capture
    assert "iter_lines()" in capture
    assert "RUN_FINISHED" in capture
    assert 'httpx.get(f"{API}/api/workflows/{workflow_id}/agui"' not in capture


def test_client_vite_ignores_ephemeral_travel_proof_runtime() -> None:
    """Proof runtime writes must not reload the live semantic browser session."""
    vite_config = (_REPO_ROOT / "vite.config.ts").read_text(encoding="utf-8")

    assert "**/.travel-proof-runtime/**" in vite_config


def test_generated_teardown_removes_ephemeral_runtime(tmp_path: Path) -> None:
    namespace = _generated_runner_namespace(tmp_path)
    teardown = namespace["teardown"]
    runtime_root = tmp_path / ".travel-proof-runtime"
    runtime_root.mkdir()
    (runtime_root / "state.sqlite").write_bytes(b"runtime")
    shutdown_calls: list[str] = []

    teardown.__globals__["RUNTIME"] = runtime_root
    teardown.__globals__["lsof_pids"] = lambda _port: []
    orphan_ports = teardown(
        SimpleNamespace(shutdown=lambda: shutdown_calls.append("shutdown"))
    )

    assert shutdown_calls == ["shutdown"]
    assert orphan_ports == {}
    assert not runtime_root.exists()


def test_git_ignores_ephemeral_travel_proof_runtime() -> None:
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", ".travel-proof-runtime/state.sqlite"],
        cwd=_REPO_ROOT,
        check=False,
    )

    assert ignored.returncode == 0


def test_browser_observes_the_hitl_gate_before_the_runner_approves_it(
    tmp_path: Path,
) -> None:
    """The browser and operator path must not race past the real HITL state."""
    root = _generated_root(tmp_path)
    python_runner = _generated_text(root, "tools/travel_zava_e2e_proof.py")
    browser_runner = _generated_text(root, "tools/travel_zava_browser_proof.mjs")
    live_start = python_runner.index("def run_live_chain")
    live_end = python_runner.index("\ndef reset_api", live_start)
    live = python_runner[live_start:live_end]

    assert "browser-pending.json" in browser_runner
    assert "browser-pending.json" in python_runner
    assert live.index("wait_for_browser_pending(workflow_id)") < live.index("approve_gate(workflow_id, active_exception)")
    assert '"browser semantic proof completion"' in live
    assert "browser.process.poll() is not None" in live


def test_generated_proof_runner_sources_are_executable_syntax(tmp_path: Path) -> None:
    """Generated runners must be runnable files, not a documentation-only contract."""
    root = _generated_root(tmp_path)
    python_runner = root / "tools/travel_zava_e2e_proof.py"
    browser_runner = root / "tools/travel_zava_browser_proof.mjs"

    subprocess.run([sys.executable, "-m", "py_compile", str(python_runner)], check=True)
    subprocess.run(["node", "--check", str(browser_runner)], check=True)


def test_manifest_schema_fixture_preserves_independent_result_values() -> None:
    """The required fields intentionally permit substrate and demo disagreement."""
    manifest = {
        "source_commit": "deadbeef",
        "vertical": "travel",
        "runtime_fingerprint": {"python": "3.12"},
        "live_result": "PASS",
        "replay_result": "FAIL",
        "substrate_result": "PASS",
        "demo_result": "FAIL",
        "seller_review": "PENDING",
        "browserErrors": [],
        "live_summary": {"workflow_id": "travel-flight-recovery-001"},
        "replay_summary": {"functions_disabled": "PASS"},
        "consecutive_runs": {
            "path": "proof/consecutive-runs.json",
            "required_successful_runs": 2,
            "result": "INCOMPLETE",
            "verified_pair": [],
        },
    }

    encoded = json.dumps(manifest)
    decoded = json.loads(encoded)
    assert set(_REQUIRED_MANIFEST_FIELDS) <= set(decoded)
    assert decoded["substrate_result"] != decoded["demo_result"]
    assert decoded["seller_review"] == "PENDING"
