"""Pack-scoped graduation artifact validation (TDD – RED before artifacts exist).

Verifies:
  1. Sandbox exists and is pack-scoped (airline vertical only).
  2. graduate.sh contains all six step labels (step 1/6 … step 6/6).
  3. graduate.sh forbids global registry paths (no edits to api/shared/domains.py
     or api/shared/functions.py or api/shared/ authority/persona adapters).
  4. graduate.sh is idempotent-safe (no non-idempotent copy/mv patterns).
  5. GRADUATION.md exists in the sandbox.
  6. Brief YAML exists and declares the correct workflow_type/function.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SANDBOX = REPO_ROOT / "tools" / "scratch" / "compose-domain" / "20260811-airline-aog"
BRIEF = REPO_ROOT / "docs" / "superpowers" / "specs" / "2026-08-11-airline-aog-engineering-recovery-brief.yaml"

GLOBAL_REGISTRY_PATHS = [
    "api/shared/domains.py",
    "api/shared/functions.py",
    "api/shared/authority",
    "api/shared/persona",
    "verticals/telco",
    "verticals/agency",
]


# ---------------------------------------------------------------------------
# Sandbox existence
# ---------------------------------------------------------------------------

def test_sandbox_dir_exists() -> None:
    assert SANDBOX.is_dir(), f"Sandbox missing: {SANDBOX}"


def test_graduation_md_exists() -> None:
    assert (SANDBOX / "GRADUATION.md").is_file(), "GRADUATION.md missing in sandbox"


def test_graduate_sh_exists() -> None:
    assert (SANDBOX / "graduate.sh").is_file(), "graduate.sh missing in sandbox"


# ---------------------------------------------------------------------------
# Step labels (step 1/6 … step 6/6)
# ---------------------------------------------------------------------------

def test_graduate_sh_has_all_six_step_labels() -> None:
    sh = (SANDBOX / "graduate.sh").read_text(encoding="utf-8")
    for i in range(1, 7):
        label = f"step {i}/6"
        assert label in sh, f"graduate.sh missing label: {label!r}"


# ---------------------------------------------------------------------------
# Global registry isolation
# ---------------------------------------------------------------------------

def test_graduate_sh_does_not_touch_global_registry_paths() -> None:
    sh = (SANDBOX / "graduate.sh").read_text(encoding="utf-8")
    violations = [p for p in GLOBAL_REGISTRY_PATHS if p in sh and "# " not in sh.split(p)[0].rsplit("\n", 1)[-1]]
    # Allow comment lines only; any non-comment reference to a global path fails.
    actual_violations: list[str] = []
    for path in GLOBAL_REGISTRY_PATHS:
        for line in sh.splitlines():
            stripped = line.lstrip()
            if path in line and not stripped.startswith("#"):
                actual_violations.append(f"{path!r} in: {line!r}")
    assert actual_violations == [], f"graduate.sh references global registry paths:\n" + "\n".join(actual_violations)


# ---------------------------------------------------------------------------
# Idempotent-safe patterns
# ---------------------------------------------------------------------------

def test_graduate_sh_uses_idempotent_copy_operations() -> None:
    sh = (SANDBOX / "graduate.sh").read_text(encoding="utf-8")
    bad_patterns = [r"\bmv\b(?!.*#.*idempotent)"]  # bare mv not annotated idempotent
    for pattern in bad_patterns:
        matches = [
            line for line in sh.splitlines()
            if re.search(pattern, line) and not line.lstrip().startswith("#")
        ]
        assert matches == [], f"Non-idempotent pattern found:\n" + "\n".join(matches)


# ---------------------------------------------------------------------------
# Pack scope — vertical=airline
# ---------------------------------------------------------------------------

def test_sandbox_is_airline_scoped() -> None:
    grad_md = (SANDBOX / "GRADUATION.md").read_text(encoding="utf-8")
    assert "airline" in grad_md.lower(), "GRADUATION.md does not reference the airline vertical"


def test_graduate_sh_declares_airline_vertical() -> None:
    sh = (SANDBOX / "graduate.sh").read_text(encoding="utf-8")
    assert "airline" in sh, "graduate.sh does not reference airline vertical"
    assert "aog-engineering-recovery" in sh, "graduate.sh does not reference aog-engineering-recovery"


# ---------------------------------------------------------------------------
# Brief YAML
# ---------------------------------------------------------------------------

def test_brief_yaml_exists() -> None:
    assert BRIEF.is_file(), f"AOG brief YAML missing: {BRIEF}"


def test_brief_yaml_declares_correct_workflow_type() -> None:
    text = BRIEF.read_text(encoding="utf-8")
    assert "workflow_type: aog-engineering-recovery" in text, \
        "Brief does not declare workflow_type: aog-engineering-recovery"


def test_brief_yaml_declares_engineering_maintenance_function() -> None:
    text = BRIEF.read_text(encoding="utf-8")
    assert "engineering-maintenance" in text, \
        "Brief does not reference engineering-maintenance function"


def test_brief_yaml_no_placeholders() -> None:
    text = BRIEF.read_text(encoding="utf-8")
    placeholders = ["TBD", "TODO", "FIXME", "<placeholder>", "???"]
    found = [p for p in placeholders if p in text]
    assert found == [], f"Brief contains placeholders: {found}"


def test_brief_yaml_references_gbp200k_gate() -> None:
    text = BRIEF.read_text(encoding="utf-8")
    assert "200" in text and ("000" in text or "200k" in text.lower() or "200,000" in text), \
        "Brief does not reference the GBP 200k spend gate"


def test_brief_yaml_references_no_release_invariant() -> None:
    text = BRIEF.read_text(encoding="utf-8")
    assert "release" in text.lower() and ("not" in text.lower() or "no" in text.lower()), \
        "Brief does not reference the no-aircraft-release invariant"


# ---------------------------------------------------------------------------
# Sandbox asset completeness
# ---------------------------------------------------------------------------

def test_sandbox_contains_skill_copy() -> None:
    skill_dirs = list((SANDBOX / "skills").glob("*/SKILL.md")) if (SANDBOX / "skills").exists() else []
    assert skill_dirs, "Sandbox missing skills/aog-recovery-ranker/SKILL.md copy"


def test_sandbox_contains_persona_copy() -> None:
    persona_dirs = list((SANDBOX / "personae").glob("*/SKILL.md")) if (SANDBOX / "personae").exists() else []
    assert persona_dirs, "Sandbox missing personae/engineering_duty_manager/SKILL.md copy"


def test_sandbox_contains_mcp_tool_copy() -> None:
    mcp = SANDBOX / "mcp_tools"
    assert mcp.is_dir() and any(mcp.iterdir()), "Sandbox missing mcp_tools/ copy"


def test_sandbox_contains_entity_projection_copy() -> None:
    ep = SANDBOX / "entity_projections"
    assert ep.is_dir() and any(ep.iterdir()), "Sandbox missing entity_projections/ copy"


def test_sandbox_contains_provenance_metadata() -> None:
    brief_dir = SANDBOX / "brief"
    assert brief_dir.is_dir(), "Sandbox missing brief/ dir"
    assert any(brief_dir.iterdir()), "Sandbox brief/ dir is empty"


# ---------------------------------------------------------------------------
# Step 4: Pack validation error handling
# ---------------------------------------------------------------------------

def test_graduate_sh_step4_pack_validation_has_failure_handler() -> None:
    """Step 4 pack-validation command substitution must have explicit failure handler.
    
    The heredoc Python script execution must be followed by || { ... }
    to catch and propagate failures explicitly.
    """
    sh = (SANDBOX / "graduate.sh").read_text(encoding="utf-8")
    
    # Find step 4 section
    step4_start = sh.find("echo \"step 4/6")
    assert step4_start != -1, "step 4/6 label not found"
    
    step5_start = sh.find("echo \"step 5/6")
    assert step5_start != -1, "step 5/6 label not found"
    
    step4_section = sh[step4_start:step5_start]
    
    # Look for the heredoc command substitution pattern
    has_heredoc = "<<'EOF'" in step4_section
    assert has_heredoc, "Step 4 missing heredoc command substitution"
    
    # Check for explicit failure handler after heredoc
    # Pattern: ) followed by || { ... }
    has_failure_handler = (
        "EOF" in step4_section and
        "||" in step4_section and
        "exit 1" in step4_section
    )
    assert has_failure_handler, \
        "Step 4 heredoc lacks explicit failure handler (|| { ... exit 1; })"
