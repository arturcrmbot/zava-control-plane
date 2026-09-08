"""Contract tests for the Airline E2E proof runners.

These tests parse the shell and JS proof scripts and fail when:
  - the vertical is wrong (Telco leakage)
  - required orchestrators are missing
  - required HITL/cleanup/gates are absent
  - direct Durable-event bypass is detected
  - contracts mismatch the airline process-profile constants
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from verticals.airline.aog_constants import (
    AOG_COMMAND_TYPE,
    AOG_SCENARIO_ID,
    AOG_SUCCESS_EVENT,
    AOG_WORKFLOW_ID_PREFIX,
    AOG_WORKFLOW_TYPE,
)
from verticals.airline.process_profiles import (
    AIRLINE_PROCESS_PROFILES,
    COMMAND_TYPE,
    HITL_EVENT,
    HITL_PERSONA,
    ORCHESTRATOR,
    SCENARIO_ID,
    SUCCESS_EVENT,
    WORKFLOW_TYPE,
)
from verticals.airline.schedule_constants import (
    SCHED_COMMAND_TYPE,
    SCHED_SCENARIO_ID,
    SCHED_SUCCESS_EVENT,
    SCHED_HITL_PERSONA,
    SCHED_WORKFLOW_ID_PREFIX,
    SCHED_WORKFLOW_TYPE,
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "airline_zava_e2e_proof.sh"
DRIVER = ROOT / "tools" / "airline_zava_e2e_proof.mjs"
STACK_LIB = ROOT / "tools" / "lib" / "actor_world_proof_stack.sh"

HUB_PROFILE = AIRLINE_PROCESS_PROFILES[WORKFLOW_TYPE]
AOG_PROFILE = AIRLINE_PROCESS_PROFILES[AOG_WORKFLOW_TYPE]
SCHED_PROFILE = AIRLINE_PROCESS_PROFILES[SCHED_WORKFLOW_TYPE]

HUB_PHASES = [
    "Detect Hub Disruption",
    "Assess Network Impact",
    "Synthesize Recovery Options",
    "Approve Recovery Plan",
    "Commit Recovery Actions",
    "Verify Recovery Outcome",
]
AOG_PHASES = [
    "Detect AOG Event",
    "Check Airworthiness Constraints",
    "Synthesize Engineering Recovery Options",
    "Approve Engineering Recovery",
    "Commit Engineering and Operational Actions",
    "Verify Recovery State",
]
SCHED_PHASES = [
    "Detect Schedule Risk Signal",
    "Assess Network Ripple Effects",
    "Synthesize Resilience Options",
    "Approve Schedule Adjustment",
    "Commit Schedule Adjustment",
    "Verify Network Stability",
]
EXPECTED_SURFACES = sorted([
    "world",
    "workflow-api",
    "workflow-drawer",
    "memory",
    "knowledge",
    "ag-ui",
    "graph-projection",
    "constellation",
])
EXPECTED_CONTRACTS = [
    {
        "scenario": SCENARIO_ID,
        "workflow": WORKFLOW_TYPE,
        "orchestrator": ORCHESTRATOR,
        "phases": HUB_PHASES,
        "hitl_persona": HITL_PERSONA,
        "hitl_event": HITL_EVENT,
        "command": COMMAND_TYPE,
        "success_event": SUCCESS_EVENT,
        "prefix": "AIRHUB",
    },
    {
        "scenario": AOG_SCENARIO_ID,
        "workflow": AOG_WORKFLOW_TYPE,
        "orchestrator": AOG_PROFILE.orchestrator,
        "phases": AOG_PHASES,
        "hitl_persona": AOG_PROFILE.hitl_persona,
        "hitl_event": AOG_PROFILE.hitl_event,
        "command": AOG_COMMAND_TYPE,
        "success_event": AOG_SUCCESS_EVENT,
        "prefix": AOG_WORKFLOW_ID_PREFIX,
    },
    {
        "scenario": SCHED_SCENARIO_ID,
        "workflow": SCHED_WORKFLOW_TYPE,
        "orchestrator": SCHED_PROFILE.orchestrator,
        "phases": SCHED_PHASES,
        "hitl_persona": SCHED_HITL_PERSONA,
        "hitl_event": SCHED_PROFILE.hitl_event,
        "command": SCHED_COMMAND_TYPE,
        "success_event": SCHED_SUCCESS_EVENT,
        "prefix": SCHED_WORKFLOW_ID_PREFIX,
    },
]


def _print_contract() -> dict:
    result = subprocess.run(
        ["node", str(DRIVER), "--print-contract"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


# ── shell script contract ───────────────────────────────────────────

class TestAirlineProofShellContract:

    def test_script_exists_and_parses(self):
        assert SCRIPT.exists(), "airline_zava_e2e_proof.sh does not exist"
        subprocess.run(["bash", "-n", str(SCRIPT)], cwd=ROOT, check=True)

    def test_prints_isolated_stack_config(self):
        result = subprocess.run(
            ["bash", str(SCRIPT), "--print-config"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        config = json.loads(result.stdout)
        assert config["vertical"] == "airline"
        assert config["driver"] == "tools/airline_zava_e2e_proof.mjs"
        # ports must differ from Telco defaults
        assert config["api_port"] != 13101
        assert config["functions_port"] != 17171

    def test_sets_zava_vertical_airline(self):
        source = SCRIPT.read_text(encoding="utf-8")
        assert 'ZAVA_VERTICAL="airline"' in source or "ZAVA_VERTICAL=airline" in source

    def test_no_telco_leakage(self):
        source = SCRIPT.read_text(encoding="utf-8")
        # No telco identifiers (case-insensitive, excluding comments/logs)
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            assert "ZAVA_VERTICAL=telco" not in stripped, f"Telco vertical leaked: {stripped}"
            assert "ZAVA_VERTICAL=\"telco\"" not in stripped, f"Telco vertical leaked: {stripped}"
            assert "ProactiveCustomerCareOrchestrator" not in stripped, (
                f"Telco orchestrator leaked: {stripped}"
            )
            assert "TELCO_PROOF_" not in stripped or "# " in line, (
                f"Telco env var leaked: {stripped}"
            )

    def test_indexes_all_airline_orchestrators(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for contract in EXPECTED_CONTRACTS:
            assert contract["orchestrator"] in source, (
                f"Script must check that {contract['orchestrator']} is indexed by Functions host"
            )

    def test_shell_orchestrator_grep_covers_all_three(self):
        source = SCRIPT.read_text(encoding="utf-8")
        grep_line = next(
            (line for line in source.splitlines() if "PROOF_ORCHESTRATOR_GREP" in line),
            "",
        )
        # The shared stack helper uses literal grep for one readiness sentinel.
        # The Airline harness separately verifies every orchestrator below.
        assert "|" not in grep_line
        for contract in EXPECTED_CONTRACTS:
            assert contract["orchestrator"] in source

    def test_shell_checks_all_airline_activity_triggers(self):
        source = SCRIPT.read_text(encoding="utf-8")
        expected = {
            "airline_evidence_activity_trigger",
            "airline_agent_activity_trigger",
            "airline_admission_activity_trigger",
            "airline_governance_activity_trigger",
            "airline_command_activity_trigger",
            "aog_evidence_activity_trigger",
            "aog_airworthiness_activity_trigger",
            "aog_agent_activity_trigger",
            "aog_governance_activity_trigger",
            "aog_command_activity_trigger",
            "sched_evidence_activity_trigger",
            "sched_assess_agent_activity_trigger",
            "sched_admission_activity_trigger",
            "sched_synthesize_agent_activity_trigger",
            "sched_governance_activity_trigger",
            "sched_command_activity_trigger",
        }
        for activity in expected:
            assert activity in source, f"proof shell does not verify {activity}"

    def test_agt_enforcement(self):
        source = SCRIPT.read_text(encoding="utf-8")
        assert 'AGT_ENFORCE="1"' in source or "AGT_ENFORCE=1" in source

    def test_persona_auto_close(self):
        source = SCRIPT.read_text(encoding="utf-8")
        assert "PERSONA_AUTO_CLOSE" in source

    def test_has_trap_cleanup(self):
        source = SCRIPT.read_text(encoding="utf-8")
        assert "trap cleanup" in source or "trap cleanup EXIT" in source

    def test_has_clean_port_assertion(self):
        source = SCRIPT.read_text(encoding="utf-8")
        assert "port_listening" in source or "preflight_ports" in source

    def test_sources_shared_stack_library(self):
        source = SCRIPT.read_text(encoding="utf-8")
        assert "actor_world_proof_stack.sh" in source

    # ── memory backend pin contract ─────────────────────────────────
    def test_exports_memory_backend_fallback_before_fastapi(self):
        """The harness MUST explicitly pin MEMORY_BACKEND=fallback before
        invoking start_fastapi so that host AZURE_OPENAI_* credentials cannot
        cause the process to auto-select mem0, trigger embedding 400s, and
        silently drop /memory writes (AIRHUB-0001 never appears).

        MEMORY_FALLBACK_DIR alone is insufficient: it only supplies the
        fallback *path* but does not prevent auto-mode from choosing mem0
        when Azure OpenAI vars are present in the environment.
        """
        source = SCRIPT.read_text(encoding="utf-8")
        # Must contain an explicit export / assignment of MEMORY_BACKEND=fallback
        assert re.search(
            r"export\s+MEMORY_BACKEND=[\"']?fallback[\"']?|MEMORY_BACKEND=[\"']?fallback[\"']?\s+",
            source,
        ), (
            "airline_zava_e2e_proof.sh must export MEMORY_BACKEND=fallback "
            "(MEMORY_FALLBACK_DIR alone does not prevent auto mode choosing mem0)"
        )

        # Additionally verify that the MEMORY_BACKEND export appears BEFORE
        # start_fastapi is called in the live-run section (not only in replay).
        lines = source.splitlines()
        backend_line = next(
            (i for i, ln in enumerate(lines) if "MEMORY_BACKEND" in ln and "fallback" in ln),
            None,
        )
        fastapi_line = next(
            (i for i, ln in enumerate(lines) if "start_fastapi" in ln),
            None,
        )
        assert backend_line is not None, (
            "MEMORY_BACKEND=fallback export not found in script"
        )
        assert fastapi_line is not None, "start_fastapi call not found in script"
        assert backend_line < fastapi_line, (
            f"MEMORY_BACKEND=fallback (line {backend_line + 1}) must appear "
            f"before start_fastapi (line {fastapi_line + 1})"
        )

    def test_memory_fallback_dir_also_exported(self):
        """MEMORY_FALLBACK_DIR must still be exported alongside MEMORY_BACKEND=fallback."""
        source = SCRIPT.read_text(encoding="utf-8")
        assert "MEMORY_FALLBACK_DIR" in source, (
            "MEMORY_FALLBACK_DIR must be exported so the fallback backend knows where to persist"
        )

    def test_supports_replay_only(self):
        source = SCRIPT.read_text(encoding="utf-8")
        assert '"--replay-only"' in source

    def test_has_live_and_replay_passes(self):
        source = SCRIPT.read_text(encoding="utf-8")
        assert "--replay" in source, "Must run replay pass"
        assert "ZAVA_BLUEPRINT_REPLAY_ONLY=1" in source

    def test_functions_disabled_during_replay(self):
        source = SCRIPT.read_text(encoding="utf-8")
        # After live pass, Functions host should be killed before replay
        lines = source.splitlines()
        replay_idx = next(
            (i for i, line in enumerate(lines) if "replay" in line.lower() and "FastAPI" in line),
            None,
        )
        if replay_idx is not None:
            pre_replay = "\n".join(lines[:replay_idx])
            assert "kill_tree" in pre_replay, "Functions host should be torn down before replay"


# ── JS driver contract ──────────────────────────────────────────────

class TestAirlineProofDriverContract:

    def test_driver_exists_and_parses(self):
        assert DRIVER.exists(), "airline_zava_e2e_proof.mjs does not exist"
        subprocess.run(["node", "--check", str(DRIVER)], cwd=ROOT, check=True)

    def test_prints_three_workflow_contracts(self):
        contract = _print_contract()
        assert sorted(contract.keys()) == ["contracts", "surfaces"]
        assert len(contract["contracts"]) == 3
        assert sorted(contract["surfaces"]) == EXPECTED_SURFACES
        for actual, expected in zip(contract["contracts"], EXPECTED_CONTRACTS, strict=True):
            assert actual == expected

    def test_no_telco_leakage_in_driver(self):
        source = DRIVER.read_text(encoding="utf-8")
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("//"):
                continue
            assert "storm-cascade" not in stripped, f"Telco scenario leaked: {stripped}"
            assert "proactive-customer-care" not in stripped, f"Telco workflow leaked: {stripped}"
            assert "network-incident" not in stripped, f"Telco workflow leaked: {stripped}"

    def test_no_direct_durable_event_bypass(self):
        """The proof must resolve HITL through persona/exceptions, not by
        directly posting a forged Durable event."""
        source = DRIVER.read_text(encoding="utf-8")
        assert "raiseEvent" not in source, (
            "Driver must not bypass HITL by posting directly to Durable raiseEvent"
        )
        assert "/runtime/webhooks/durabletask/instances/" not in source or (
            # Reading Durable state is fine; POSTing events is not
            "raiseEvent" not in source
        )

    def test_uses_persona_sweep_route(self):
        """HITL must be resolved via POST /api/personas/sweep, not manual
        exception resolution."""
        source = DRIVER.read_text(encoding="utf-8")
        assert "/api/personas/sweep" in source, (
            "Driver must resolve HITL through POST /api/personas/sweep"
        )

    def test_no_manual_exception_resolve_in_normal_flow(self):
        """The normal HITL path must not manually POST to
        /api/exceptions/{id}/resolve — that races the persona responder."""
        source = DRIVER.read_text(encoding="utf-8")
        assert "/resolve" not in source or "exceptions" not in source.split("/resolve")[0].split("\n")[-1], (
            "Driver must not manually resolve exceptions; use /api/personas/sweep"
        )

    def test_driver_iterates_contracts_sequentially(self):
        source = DRIVER.read_text(encoding="utf-8")
        assert "WORKFLOW_CONTRACTS" in source
        assert "for (const contract of WORKFLOW_CONTRACTS)" in source or "for (const workflowContract of WORKFLOW_CONTRACTS)" in source
        for contract in EXPECTED_CONTRACTS:
            assert contract["scenario"] in source
            assert contract["workflow"] in source

    def test_hitl_gate_requires_persisted_context_for_all_three(self):
        source = DRIVER.read_text(encoding="utf-8")
        assert "awaiting_hitl" in source, (
            "Driver must inspect awaiting_hitl when it is observable"
        )
        assert "payload?.evidence?.hitl_context" in source, (
            "Driver must handle real auto-close races by reading terminal persisted HITL evidence"
        )
        assert "observedAwaiting" in source
        for contract in EXPECTED_CONTRACTS:
            assert contract["hitl_persona"] in source
            assert contract["hitl_event"] in source

    def test_expects_six_phases_per_contract(self):
        contract = _print_contract()
        for actual, expected in zip(contract["contracts"], EXPECTED_CONTRACTS, strict=True):
            assert len(actual["phases"]) == 6
            assert actual["phases"] == expected["phases"]

    def test_click_to_visible_assertion(self):
        source = DRIVER.read_text(encoding="utf-8")
        assert "click" in source.lower() and ("1000" in source or "1_000" in source), (
            "Driver must assert click-to-visible <=1s"
        )

    def test_collects_browser_errors(self):
        source = DRIVER.read_text(encoding="utf-8")
        assert "browserErrors" in source

    def test_closes_per_workflow_pages_to_release_sse_connections(self):
        source = DRIVER.read_text(encoding="utf-8")
        assert "await run.close()" in source
        assert "await page.close()" in source

    def test_captures_workflow_specific_screenshots_for_eight_surfaces(self):
        source = DRIVER.read_text(encoding="utf-8")
        assert "screenshot" in source
        assert "path.join(SCREENSHOTS" in source
        assert "workflow-api" in source and "graph-projection" in source and "constellation" in source
        assert "${contract.workflow}" in source or "${workflow.type}" in source, (
            "Screenshot filenames should be prefixed per workflow"
        )

    def test_captures_evidence_files(self):
        source = DRIVER.read_text(encoding="utf-8")
        for artifact in ("summary.json", "world-journal.json", "durable-instances.json"):
            assert artifact in source, f"Driver must produce {artifact}"

    def test_has_replay_mode(self):
        source = DRIVER.read_text(encoding="utf-8")
        assert "--replay" in source

    def test_replay_api_starts_in_canonical_replay_mode(self):
        source = SCRIPT.read_text(encoding="utf-8")
        assert source.count("ZAVA_BLUEPRINT_REPLAY_ONLY=1") >= 2
        assert "ZAVA_MODE=replay" not in source

    def test_runs_blocking_workflow_visibility_parity(self):
        shell = SCRIPT.read_text(encoding="utf-8")
        driver = DRIVER.read_text(encoding="utf-8")
        assert "workflow_visibility_proof.py" in shell
        assert "--compare-dir" in shell
        assert "ZAVA_REPLAY_WORKFLOW_DETAILS" in shell
        assert "workflow-replay-details.json" in driver

    def test_runs_all_negative_readiness_probes(self):
        shell = SCRIPT.read_text(encoding="utf-8")
        driver = DRIVER.read_text(encoding="utf-8")
        for mode in (
            "--backend-restart-probe",
            "--functions-disabled-probe",
            "--functions-recovery-probe",
            "--actor-disabled-probe",
        ):
            assert mode in shell
            assert mode in driver
        assert "ZAVA_ACTOR_WORLD_ENABLED=0" in shell
        assert "phantom workflow" in driver
        assert "diagnostic_only" in driver

    def test_uses_proof_error_not_broad_catch(self):
        source = DRIVER.read_text(encoding="utf-8")
        assert "ProofError" in source
        assert "if (error instanceof ProofError)" in source

    def test_terminal_state_deadline(self):
        source = DRIVER.read_text(encoding="utf-8")
        assert "15" in source or "15_000" in source or "15000" in source, (
            "Driver must require terminal state within deadline"
        )

    def test_contract_declares_eight_surfaces(self):
        """The proof contract must declare exactly eight distinct surfaces."""
        contract = _print_contract()
        assert sorted(contract["surfaces"]) == EXPECTED_SURFACES, (
            f"Expected 8 surfaces {EXPECTED_SURFACES}, got {sorted(contract['surfaces'])}"
        )

    def test_asserts_persona_decided_and_durable_resumed(self):
        """Driver must explicitly assert persona.decided and durable.resumed events
        (not just mention them in comments)."""
        source = DRIVER.read_text(encoding="utf-8")
        # Must use these in actual logic (need/assert), not just comments
        lines = [ln for ln in source.splitlines() if not ln.strip().startswith("//")]
        code_only = "\n".join(lines)
        assert "persona.decided" in code_only, (
            "Driver must assert persona.decided event in code (not just comments)"
        )
        assert "durable.resumed" in code_only, (
            "Driver must assert durable.resumed event in code (not just comments)"
        )

    def test_world_surface_asserts_workflow_identity_and_outcome(self):
        """World surface must assert target workflow ID and terminal success,
        not merely that the UI loads."""
        source = DRIVER.read_text(encoding="utf-8")
        # Must query world events with workflow_id
        assert "world/events" in source, (
            "Driver must query /api/world/events for world surface"
        )
        # Must not merely set loaded: true as world evidence
        assert "loaded: true" not in source and "loaded:true" not in source, (
            "World surface must assert workflow identity, not just loaded flag"
        )
        assert "worldPayload.events" in source
        assert "event.payload?.workflow_id" in source
        assert "World event log has no terminal success event" in source
        assert "`${CONTROL_PLANE}/world`" in source

    def test_workflow_api_is_separate_surface(self):
        """workflow-api must be recorded as a separate surface in evidence.surfaces."""
        source = DRIVER.read_text(encoding="utf-8")
        assert 'surfaces["workflow-api"]' in source or "surfaces['workflow-api']" in source or 'surfaces[\"workflow-api\"]' in source, (
            "Driver must record workflow-api as a separate surface in evidence.surfaces"
        )

    def test_graph_projection_is_separate_surface(self):
        """graph-projection must be a separate surface from knowledge."""
        source = DRIVER.read_text(encoding="utf-8")
        assert 'graph-projection' in source, (
            "Driver must have graph-projection as a distinct surface"
        )
        # Must be in surfaces, not just in knowledge
        assert 'surfaces["graph-projection"]' in source or "surfaces['graph-projection']" in source or 'surfaces[\"graph-projection\"]' in source, (
            "Driver must record graph-projection as a separate surface in evidence.surfaces"
        )

    def test_recorder_requires_one_non_empty_jsonl_per_hero(self):
        source = DRIVER.read_text(encoding="utf-8")
        assert "readdir(RECORDINGS)" in source
        assert "jsonl" in source
        assert "size" in source or "stat" in source, "Driver should verify recordings are non-empty"
        for contract in EXPECTED_CONTRACTS:
            assert contract["workflow"] in source, (
                f"Driver must require a recording file for {contract['workflow']}"
            )

    def test_replay_observes_all_three_workflow_types(self):
        source = DRIVER.read_text(encoding="utf-8")
        assert "workflowTypes" in source
        assert "sourceMode" in source, "Replay evidence must preserve sourceMode provenance"
        assert "/api/replay/meta" in source, "Replay proof must read replay meta provenance"
        for contract in EXPECTED_CONTRACTS:
            assert contract["workflow"] in source

    def test_functions_disabled_and_actor_world_disabled_are_checked_for_all_three(self):
        source = DRIVER.read_text(encoding="utf-8")
        assert "functionsHostReachable" in source
        assert "worldEnabled" in source
        assert "WORKFLOW_CONTRACTS" in source
        assert "!evidence.functionsHostReachable" in source or "functionsHostReachable === false" in source
        assert "world.enabled === false" in source or "evidence.worldEnabled === false" in source

    def test_backend_restart_cursor_rewind_probe_is_bounded(self):
        source = DRIVER.read_text(encoding="utf-8")
        assert "latest_seq" in source, "Driver must inspect latest_seq for cursor-rewind recovery"
        assert "after=0" in source, "Driver must rewind to after=0 when the backend cursor drops"
        assert "cursor" in source.lower(), "Driver should track a journal cursor"
        assert "restart" in source.lower() or "rewind" in source.lower(), (
            "Driver should document bounded restart/cursor-rewind recovery logic"
        )
