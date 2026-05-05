"""Phase 3 wiring assertion — confirm every audited skill SKILL.md and its
agent executor declares delegated_authority_resolve_approver.

This is a static assertion: it parses the SKILL.md frontmatter and the
executor module to confirm the tool is wired. It does NOT invoke the
skill (which would need a live LLM session). Behavioural verification of
`resolved_approver` landing in the structured output is part of the live
demo loop, not unit tests.
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
SKILLS_DIR = REPO_ROOT / "api" / "server" / "skills"

# (skill_dir_name, executor_module). budget-checker is intentionally excluded —
# its real agent executor is still the hiring_stub placeholder. The SKILL.md
# is wired forward-compatibly; when the executor lands, this list grows.
AUDIT_LIST: list[tuple[str, str | None]] = [
    ("escalation-advisor", "api.functions.graphs.executors.agents.agent_escalation"),
    (
        "fleet-travel-preapproval-policy-fit-checker",
        "api.functions.graphs.executors.agents.agent_fleet_travel_preapproval_policy_fit_check",
    ),
    (
        "fleet-vendor-kyc-kyc-diligence-checker",
        "api.functions.graphs.executors.agents.agent_fleet_vendor_kyc_kyc_diligence",
    ),
    (
        "fleet-it-access-request-access-risk-assessor",
        "api.functions.graphs.executors.agents.agent_fleet_it_access_request_risk_assessor",
    ),
    (
        "fleet-contract-renewal-renewal-terms-drafter",
        "api.functions.graphs.executors.agents.agent_fleet_contract_renewal_renewal_terms_drafter",
    ),
    (
        "fleet-employee-onboarding-access-drafter",
        "api.functions.graphs.executors.agents.agent_fleet_employee_onboarding_access_drafter",
    ),
    (
        "fleet-perf-review-calibration-drafter",
        "api.functions.graphs.executors.agents.agent_fleet_perf_review_calibration_drafter",
    ),
    # budget-checker SKILL.md is wired but executor is hiring_stub.
    ("budget-checker", None),
]


def _read_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    lines = text.splitlines()
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}
    return yaml.safe_load("\n".join(lines[1:end])) or {}


@pytest.mark.parametrize("skill_dir,executor_module", AUDIT_LIST)
def test_skill_declares_authority_tool(skill_dir: str, executor_module: str | None):
    skill_path = SKILLS_DIR / skill_dir / "SKILL.md"
    fm = _read_frontmatter(skill_path)
    allowed = fm.get("allowed-tools") or ""
    assert "delegated_authority_resolve_approver" in str(allowed), (
        f"{skill_dir}/SKILL.md frontmatter `allowed-tools` does not include "
        f"`delegated_authority_resolve_approver`. Found: {allowed!r}"
    )


@pytest.mark.parametrize("skill_dir,executor_module", AUDIT_LIST)
def test_skill_body_documents_resolved_approver(skill_dir: str, executor_module: str | None):
    """The skill's structured output schema must include `resolved_approver`."""
    skill_path = SKILLS_DIR / skill_dir / "SKILL.md"
    body = skill_path.read_text(encoding="utf-8")
    assert "resolved_approver" in body, (
        f"{skill_dir}/SKILL.md body does not mention `resolved_approver` in the output schema"
    )


@pytest.mark.parametrize("skill_dir,executor_module", AUDIT_LIST)
def test_executor_imports_and_registers_tool(skill_dir: str, executor_module: str | None):
    if executor_module is None:
        pytest.skip(f"{skill_dir}: executor not wired (placeholder); SKILL.md-only wiring")

    mod = importlib.import_module(executor_module)
    src = Path(mod.__file__).read_text(encoding="utf-8")
    assert "delegated_authority_resolve_approver_tool" in src, (
        f"{executor_module} does not import or register "
        f"delegated_authority_resolve_approver_tool"
    )
    # Specifically check it lands in a `tools=[` list, not just imported.
    assert "delegated_authority_resolve_approver_tool" in src.split("tools=[", 1)[-1], (
        f"{executor_module}: tool is imported but does not appear in any tools=[...] list"
    )
