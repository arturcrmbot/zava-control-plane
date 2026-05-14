"""Tests for the three meta-workflow briefs (Phase 4 IP5 TASK-026).

Each brief at ``docs/superpowers/specs/<meta>-brief.yaml`` is processed
by the v4 schema validator + the orchestrator codegen. We assert:

* schema-valid (no semantic surprises);
* function key matches the Phase 3 canonical (`hr`/`finance`/`revenue`,
  not `chro`/`cfo`);
* codegen renders parseable Python;
* output contains the expected ``call_sub_orchestrator`` /
  ``task_all`` patterns;
* the ``workflow.sub_spawned`` audit checkpoint surfaces (SEC-002).

We do NOT write to ``api/functions/workflows/`` — graduate.sh's job.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[5]
SPECS_DIR = REPO_ROOT / "docs" / "superpowers" / "specs"

META_BRIEFS = [
    (
        "hire-to-productive-brief.yaml",
        {
            "function": "hr",
            "workflow_type": "hire-to-productive",
            "expected_class_names": [
                "FleetItAccessRequestOrchestrator",
                "FleetEmployeeOnboardingOrchestrator",
                "FleetPerfReviewOrchestrator",
            ],
            "expects_task_all": True,        # onboarding parallel_group
            "hitl_persona": "hr_bp",
        },
    ),
    (
        "vendor-risk-to-pay-brief.yaml",
        {
            "function": "finance",
            "workflow_type": "vendor-risk-to-pay",
            "expected_class_names": [
                "FleetVendorKycOrchestrator",
                "FleetContractReviewOrchestrator",
                "FleetPurchaseOrderOrchestrator",
                "FleetApInvoiceOrchestrator",
                "FleetTreasuryFxOrchestrator",
            ],
            "expects_task_all": True,        # pay parallel_group
            "hitl_persona": "cfo",
        },
    ),
    (
        "lead-to-cash-brief.yaml",
        {
            "function": "revenue",
            "workflow_type": "lead-to-cash",
            "expected_class_names": [
                "CreativeCampaignOrchestrator",
                "FleetContractReviewOrchestrator",
                "FleetApInvoiceOrchestrator",
            ],
            "expects_task_all": False,
            "hitl_persona": "account_director",
        },
    ),
]


@pytest.fixture
def codegen(sub_skill_loader):
    return sub_skill_loader("author-domain-skeleton", "codegen")


@pytest.fixture
def skeleton_validator(sub_skill_loader):
    return sub_skill_loader("author-domain-skeleton", "validator")


@pytest.mark.parametrize("filename,spec", META_BRIEFS, ids=[m[0] for m in META_BRIEFS])
def test_brief_schema_validates(filename, spec, shared_validator, skeleton_validator):
    brief = yaml.safe_load((SPECS_DIR / filename).read_text())
    shared_validator.validate_brief(brief)
    skeleton_validator.validate(brief)
    assert brief["function"] == spec["function"]
    assert brief["domain"]["workflow_type"] == spec["workflow_type"]


@pytest.mark.parametrize("filename,spec", META_BRIEFS, ids=[m[0] for m in META_BRIEFS])
def test_brief_codegen_emits_valid_python(filename, spec, codegen):
    brief = yaml.safe_load((SPECS_DIR / filename).read_text())
    body = codegen.render_orchestrator(brief)
    assert body.strip(), "codegen produced empty body"
    ast.parse(body)
    for cls in spec["expected_class_names"]:
        assert cls in body, f"{filename}: missing expected sub-orchestrator {cls}"
    if spec["expects_task_all"]:
        assert "context.task_all([" in body
    # SEC-002: every meta-workflow sub-spawn is audited.
    assert "workflow.sub_spawned" in body
    # HITL gate keeps wait_for_external_event semantics.
    assert "wait_for_external_event" in body


@pytest.mark.parametrize("filename,spec", META_BRIEFS, ids=[m[0] for m in META_BRIEFS])
def test_brief_lands_at_expected_path(filename, spec, codegen):
    brief = yaml.safe_load((SPECS_DIR / filename).read_text())
    snake = spec["workflow_type"].replace("-", "_")
    assert codegen.render_filename(brief) == f"{snake}.py"
