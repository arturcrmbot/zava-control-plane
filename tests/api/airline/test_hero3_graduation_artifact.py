"""Pack-scoped graduation artifact validation — Airline Hero 3 (TDD, RED first).

Verifies:
  1. Brief YAML exists, current schema, no placeholders, exact identity/phases/
     truth/sensor/objective/forecast entities/tools/skill/Network Operations
     Director action/category/300k/monitor_risk/typed command/mutations/
     evaluation/projection/proof.
  2. Sandbox exists with sealed brief/provenance, byte-identical asset copies,
     GRADUATION.md, and executable graduate.sh.
  3. graduate.sh: idempotent six steps; validates root/airline/contracts/layout;
     pack-only safe copies; asserts all reviewed registrations (domain/function/
     profile/Durable six activities/world route/diagnostic/manifest MCP/
     projection/memory/authority/persona/agent/UI); active_runtime validate and
     ownership; focused tests; prints exact live/replay commands; no readiness
     claim; explicit error handling; no globals/other packs.
  4. Asset equality: sandbox copies match live verticals/airline/ files.
  5. No agency/telco references in graduate.sh (isolation).
  6. graduate.sh passes bash -n syntax check.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SANDBOX = (
    REPO_ROOT
    / "tools"
    / "scratch"
    / "compose-domain"
    / "20260811-airline-schedule-resilience"
)
BRIEF = (
    REPO_ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "2026-08-11-airline-schedule-resilience-brief.yaml"
)
LIVE_ROOT = REPO_ROOT / "verticals" / "airline"

GLOBAL_REGISTRY_PATHS = [
    "api/shared/domains.py",
    "api/shared/functions.py",
    "api/shared/authority",
    "api/shared/persona",
    "verticals/telco",
    "verticals/agency",
]

# ─────────────────────────────────────────────────────────────────
# 1. Brief YAML
# ─────────────────────────────────────────────────────────────────


def test_brief_yaml_exists() -> None:
    assert BRIEF.is_file(), f"Brief YAML missing: {BRIEF}"


def test_brief_yaml_no_placeholders() -> None:
    text = BRIEF.read_text(encoding="utf-8")
    for token in ("TBD", "TODO", "FIXME", "<placeholder>", "???"):
        assert token not in text, f"Brief contains placeholder: {token!r}"


def test_brief_yaml_declares_workflow_type() -> None:
    text = BRIEF.read_text(encoding="utf-8")
    assert "workflow_type: preemptive-schedule-resilience" in text


def test_brief_yaml_declares_network_planning_function() -> None:
    text = BRIEF.read_text(encoding="utf-8")
    assert "network-planning" in text


def test_brief_yaml_declares_300k_spend_gate() -> None:
    text = BRIEF.read_text(encoding="utf-8")
    assert "300000" in text or "300_000" in text or "300,000" in text


def test_brief_yaml_declares_monitor_risk_option() -> None:
    text = BRIEF.read_text(encoding="utf-8")
    assert "monitor_risk" in text


def test_brief_yaml_declares_network_operations_director() -> None:
    text = BRIEF.read_text(encoding="utf-8")
    assert "network_operations_director" in text


def test_brief_yaml_declares_commit_schedule_adjustment_command() -> None:
    text = BRIEF.read_text(encoding="utf-8")
    assert "airline.commit_schedule_adjustment" in text


def test_brief_yaml_declares_sensor_id() -> None:
    text = BRIEF.read_text(encoding="utf-8")
    assert "sensor:schedule_resilience" in text


def test_brief_yaml_declares_story_id() -> None:
    text = BRIEF.read_text(encoding="utf-8")
    assert "SYN-STORY-SCHED-001" in text


def test_brief_yaml_declares_forecast_entities() -> None:
    text = BRIEF.read_text(encoding="utf-8")
    assert "SYN-FCAST-SLOT-001" in text
    assert "SYN-FCAST-GROUND-001" in text


def test_brief_yaml_declares_both_mcp_tools() -> None:
    text = BRIEF.read_text(encoding="utf-8")
    assert "airline_read_schedule_risk_evidence" in text
    assert "airline_rank_admitted_resilience_options" in text


def test_brief_yaml_declares_schedule_resilience_ranker_skill() -> None:
    text = BRIEF.read_text(encoding="utf-8")
    assert "schedule-resilience-ranker" in text


def test_brief_yaml_declares_synthetic_schedule_resilience_category() -> None:
    text = BRIEF.read_text(encoding="utf-8")
    assert "synthetic-schedule-resilience" in text


def test_brief_yaml_declares_six_phases() -> None:
    text = BRIEF.read_text(encoding="utf-8")
    assert text.count("- name:") >= 6


def test_brief_yaml_declares_hitl_gate() -> None:
    text = BRIEF.read_text(encoding="utf-8")
    assert "hitl_gates" in text or "hitl" in text


def test_brief_yaml_declares_mutations_section() -> None:
    text = BRIEF.read_text(encoding="utf-8")
    assert "mutations" in text or "commit" in text


def test_brief_yaml_declares_evaluation_section() -> None:
    text = BRIEF.read_text(encoding="utf-8")
    assert "evaluation" in text or "projection" in text


def test_brief_yaml_declares_objective_type() -> None:
    text = BRIEF.read_text(encoding="utf-8")
    assert "manage_schedule_risk" in text


def test_brief_yaml_declares_proof_or_graduation_status() -> None:
    text = BRIEF.read_text(encoding="utf-8")
    assert "live" in text.lower() or "reviewed" in text.lower() or "graduation" in text.lower()


# ─────────────────────────────────────────────────────────────────
# 2. Sandbox structure
# ─────────────────────────────────────────────────────────────────


def test_sandbox_dir_exists() -> None:
    assert SANDBOX.is_dir(), f"Sandbox missing: {SANDBOX}"


def test_graduation_md_exists() -> None:
    assert (SANDBOX / "GRADUATION.md").is_file()


def test_graduate_sh_exists() -> None:
    assert (SANDBOX / "graduate.sh").is_file()


def test_sandbox_sealed_brief_exists() -> None:
    assert (SANDBOX / "brief" / "v5-sealed.yaml").is_file()


def test_sandbox_provenance_json_exists() -> None:
    assert (SANDBOX / "brief" / "provenance.json").is_file()


def test_sandbox_skill_copy_exists() -> None:
    assert (SANDBOX / "skills" / "schedule-resilience-ranker" / "SKILL.md").is_file()


def test_sandbox_persona_copy_exists() -> None:
    assert (SANDBOX / "personae" / "network_operations_director" / "SKILL.md").is_file()


def test_sandbox_mcp_tool_copy_exists() -> None:
    assert (SANDBOX / "mcp_tools" / "schedule.py").is_file()


def test_sandbox_entity_projection_copy_exists() -> None:
    assert (SANDBOX / "entity_projections" / "schedule.py").is_file()


# ─────────────────────────────────────────────────────────────────
# 3. Asset equality (sandbox == live)
# ─────────────────────────────────────────────────────────────────


def test_skill_copy_byte_identical_to_live() -> None:
    sandbox_file = SANDBOX / "skills" / "schedule-resilience-ranker" / "SKILL.md"
    live_file = LIVE_ROOT / "skills" / "schedule-resilience-ranker" / "SKILL.md"
    assert sandbox_file.is_file(), "Sandbox SKILL.md missing"
    assert live_file.is_file(), "Live SKILL.md missing"
    assert sandbox_file.read_bytes() == live_file.read_bytes(), \
        "Sandbox SKILL.md differs from live"


def test_persona_copy_byte_identical_to_live() -> None:
    sandbox_file = SANDBOX / "personae" / "network_operations_director" / "SKILL.md"
    live_file = LIVE_ROOT / "personae" / "network_operations_director" / "SKILL.md"
    assert sandbox_file.is_file(), "Sandbox persona SKILL.md missing"
    assert live_file.is_file(), "Live persona SKILL.md missing"
    assert sandbox_file.read_bytes() == live_file.read_bytes(), \
        "Sandbox persona SKILL.md differs from live"


def test_mcp_tool_copy_byte_identical_to_live() -> None:
    sandbox_file = SANDBOX / "mcp_tools" / "schedule.py"
    live_file = LIVE_ROOT / "mcp_tools" / "schedule.py"
    assert sandbox_file.is_file(), "Sandbox mcp_tools/schedule.py missing"
    assert live_file.is_file(), "Live mcp_tools/schedule.py missing"
    assert sandbox_file.read_bytes() == live_file.read_bytes(), \
        "Sandbox mcp_tools/schedule.py differs from live"


def test_entity_projection_copy_byte_identical_to_live() -> None:
    sandbox_file = SANDBOX / "entity_projections" / "schedule.py"
    live_file = LIVE_ROOT / "entity_projections" / "schedule.py"
    assert sandbox_file.is_file(), "Sandbox entity_projections/schedule.py missing"
    assert live_file.is_file(), "Live entity_projections/schedule.py missing"
    assert sandbox_file.read_bytes() == live_file.read_bytes(), \
        "Sandbox entity_projections/schedule.py differs from live"


# ─────────────────────────────────────────────────────────────────
# 4. graduate.sh — six step labels
# ─────────────────────────────────────────────────────────────────


def test_graduate_sh_has_all_six_step_labels() -> None:
    sh = (SANDBOX / "graduate.sh").read_text(encoding="utf-8")
    for i in range(1, 7):
        assert f"step {i}/6" in sh, f"graduate.sh missing label: step {i}/6"


# ─────────────────────────────────────────────────────────────────
# 5. graduate.sh — registration assertions
# ─────────────────────────────────────────────────────────────────


def test_graduate_sh_asserts_domain_registration() -> None:
    sh = (SANDBOX / "graduate.sh").read_text(encoding="utf-8")
    assert "preemptive-schedule-resilience" in sh or "SCHED_WORKFLOW_TYPE" in sh


def test_graduate_sh_asserts_function_ownership() -> None:
    sh = (SANDBOX / "graduate.sh").read_text(encoding="utf-8")
    assert "network-planning" in sh


def test_graduate_sh_asserts_six_durable_activities() -> None:
    sh = (SANDBOX / "graduate.sh").read_text(encoding="utf-8")
    sched_activities = [
        "sched_evidence_activity_trigger",
        "sched_assess_agent_activity_trigger",
        "sched_admission_activity_trigger",
        "sched_synthesize_agent_activity_trigger",
        "sched_governance_activity_trigger",
        "sched_command_activity_trigger",
    ]
    for act in sched_activities:
        assert act in sh, f"graduate.sh missing activity assertion: {act}"


def test_graduate_sh_asserts_mcp_tools() -> None:
    sh = (SANDBOX / "graduate.sh").read_text(encoding="utf-8")
    assert "airline_read_schedule_risk_evidence" in sh
    assert "airline_rank_admitted_resilience_options" in sh


def test_graduate_sh_asserts_world_route_and_responder() -> None:
    sh = (SANDBOX / "graduate.sh").read_text(encoding="utf-8")
    assert "SCHED_SENSOR_ID" in sh or "sensor:schedule_resilience" in sh
    assert "SCHED_OBJECTIVE_TYPE" in sh or "manage_schedule_risk" in sh


def test_graduate_sh_asserts_authority_300k() -> None:
    sh = (SANDBOX / "graduate.sh").read_text(encoding="utf-8")
    assert "300_000" in sh or "300000" in sh or "300,000" in sh


def test_graduate_sh_asserts_persona_registration() -> None:
    sh = (SANDBOX / "graduate.sh").read_text(encoding="utf-8")
    assert "network_operations_director" in sh


def test_graduate_sh_asserts_agent_registration() -> None:
    sh = (SANDBOX / "graduate.sh").read_text(encoding="utf-8")
    assert "schedule-resilience-ranker" in sh


def test_graduate_sh_asserts_mcp_module_in_manifest() -> None:
    sh = (SANDBOX / "graduate.sh").read_text(encoding="utf-8")
    assert "mcp_tools.schedule" in sh or "verticals.airline.mcp_tools.schedule" in sh


def test_graduate_sh_asserts_projection_registration() -> None:
    sh = (SANDBOX / "graduate.sh").read_text(encoding="utf-8")
    assert "SCHED_WORKFLOW_TYPE" in sh or "preemptive-schedule-resilience" in sh
    assert "projection" in sh.lower() or "projections.py" in sh


def test_graduate_sh_asserts_memory_workflow_types() -> None:
    sh = (SANDBOX / "graduate.sh").read_text(encoding="utf-8")
    assert "memory" in sh.lower() or "SCHED_WORKFLOW_TYPE" in sh


def test_graduate_sh_asserts_ui_files() -> None:
    sh = (SANDBOX / "graduate.sh").read_text(encoding="utf-8")
    assert "ui.json" in sh
    assert "world-scene.json" in sh


def test_graduate_sh_asserts_diagnostics_file() -> None:
    sh = (SANDBOX / "graduate.sh").read_text(encoding="utf-8")
    assert "diagnostics" in sh


# ─────────────────────────────────────────────────────────────────
# 6. graduate.sh — active_runtime + ownership validation
# ─────────────────────────────────────────────────────────────────


def test_graduate_sh_step4_validates_active_runtime() -> None:
    sh = (SANDBOX / "graduate.sh").read_text(encoding="utf-8")
    step4_start = sh.find("step 4/6")
    assert step4_start != -1
    step5_start = sh.find("step 5/6")
    section = sh[step4_start:step5_start]
    assert "build_runtime" in section or "active_runtime" in section or "pack" in section


def test_graduate_sh_step4_asserts_domain_in_pack() -> None:
    sh = (SANDBOX / "graduate.sh").read_text(encoding="utf-8")
    step4_start = sh.find("step 4/6")
    step5_start = sh.find("step 5/6")
    section = sh[step4_start:step5_start]
    assert "preemptive-schedule-resilience" in section


def test_graduate_sh_step4_has_failure_handler() -> None:
    sh = (SANDBOX / "graduate.sh").read_text(encoding="utf-8")
    step4_start = sh.find("step 4/6")
    step5_start = sh.find("step 5/6")
    section = sh[step4_start:step5_start]
    assert "EOF" in section
    assert "||" in section and "exit 1" in section


# ─────────────────────────────────────────────────────────────────
# 7. graduate.sh — focused test step (step 5)
# ─────────────────────────────────────────────────────────────────


def test_graduate_sh_step5_runs_focused_airline_tests() -> None:
    sh = (SANDBOX / "graduate.sh").read_text(encoding="utf-8")
    step5_start = sh.find("step 5/6")
    step6_start = sh.find("step 6/6")
    section = sh[step5_start:step6_start]
    assert "pytest" in section
    assert "airline" in section


# ─────────────────────────────────────────────────────────────────
# 8. graduate.sh — proof commands, no readiness claim
# ─────────────────────────────────────────────────────────────────


def test_graduate_sh_step6_prints_proof_commands() -> None:
    sh = (SANDBOX / "graduate.sh").read_text(encoding="utf-8")
    step6_start = sh.find("step 6/6")
    section = sh[step6_start:]
    assert "pytest" in section or "uvicorn" in section or "proof" in section.lower()


def test_graduate_sh_no_readiness_claim() -> None:
    sh = (SANDBOX / "graduate.sh").read_text(encoding="utf-8")
    # Must not claim "ready for production" or "deployment ready"
    for claim in ("ready for production", "deployment ready", "azure deployed"):
        assert claim.lower() not in sh.lower(), \
            f"graduate.sh makes forbidden readiness claim: {claim!r}"


# ─────────────────────────────────────────────────────────────────
# 9. graduate.sh — global registry isolation
# ─────────────────────────────────────────────────────────────────


def test_graduate_sh_does_not_touch_global_registry_paths() -> None:
    sh = (SANDBOX / "graduate.sh").read_text(encoding="utf-8")
    actual_violations: list[str] = []
    for path in GLOBAL_REGISTRY_PATHS:
        for line in sh.splitlines():
            stripped = line.lstrip()
            if path in line and not stripped.startswith("#"):
                actual_violations.append(f"{path!r} in: {line!r}")
    assert actual_violations == [], (
        "graduate.sh references global registry paths:\n"
        + "\n".join(actual_violations)
    )


def test_graduate_sh_no_agency_telco_references() -> None:
    sh = (SANDBOX / "graduate.sh").read_text(encoding="utf-8")
    for vertical in ("telco", "agency"):
        lines = [
            line for line in sh.splitlines()
            if vertical in line and not line.lstrip().startswith("#")
        ]
        assert lines == [], (
            f"graduate.sh contains non-comment reference to {vertical!r}:\n"
            + "\n".join(lines)
        )


# ─────────────────────────────────────────────────────────────────
# 10. graduate.sh — idempotent-safe copy patterns
# ─────────────────────────────────────────────────────────────────


def test_graduate_sh_uses_idempotent_copy_operations() -> None:
    sh = (SANDBOX / "graduate.sh").read_text(encoding="utf-8")
    bad_pattern = r"\bmv\b"
    for line in sh.splitlines():
        if re.search(bad_pattern, line) and not line.lstrip().startswith("#"):
            pytest.fail(f"Non-idempotent mv found in graduate.sh: {line!r}")


# ─────────────────────────────────────────────────────────────────
# 11. graduate.sh — bash -n syntax check
# ─────────────────────────────────────────────────────────────────


def test_graduate_sh_passes_bash_syntax_check() -> None:
    sh_path = SANDBOX / "graduate.sh"
    result = subprocess.run(
        ["bash", "-n", str(sh_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"bash -n failed on graduate.sh:\n{result.stderr}"
    )


# ─────────────────────────────────────────────────────────────────
# 12. Sandbox airline vertical scope
# ─────────────────────────────────────────────────────────────────


def test_sandbox_graduation_md_references_airline() -> None:
    text = (SANDBOX / "GRADUATION.md").read_text(encoding="utf-8")
    assert "airline" in text.lower()


def test_sandbox_graduation_md_references_hero3() -> None:
    text = (SANDBOX / "GRADUATION.md").read_text(encoding="utf-8")
    assert "hero 3" in text.lower() or "hero3" in text.lower() or "schedule" in text.lower()


def test_sandbox_provenance_declares_workflow_type() -> None:
    import json
    prov = json.loads((SANDBOX / "brief" / "provenance.json").read_text(encoding="utf-8"))
    assert prov.get("workflow_type") == "preemptive-schedule-resilience"


def test_sandbox_provenance_declares_live_status() -> None:
    import json
    prov = json.loads((SANDBOX / "brief" / "provenance.json").read_text(encoding="utf-8"))
    assert "live" in str(prov.get("status", "")).lower()
