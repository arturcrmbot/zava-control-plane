"""Registry validation — every Domain entry is internally consistent and
matches the runtime substrate.

Per TASK-006 of plan/feature-fleet-domain-substrate-1.md.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from api.shared import domains as registry


REPO_ROOT = Path(__file__).resolve().parents[3]
PERSONAE_DIR = REPO_ROOT / "api" / "server" / "personae"


def test_workflow_types_unique():
    types = [d.workflow_type for d in registry.DOMAINS.values()]
    assert len(types) == len(set(types)), f"duplicate workflow_type in registry: {types}"


def test_prefixes_unique():
    prefixes = [d.workflow_id_prefix for d in registry.DOMAINS.values()]
    assert len(prefixes) == len(set(prefixes)), f"duplicate prefix: {prefixes}"


def test_every_hitl_phase_declares_persona_and_event():
    for wt, d in registry.DOMAINS.items():
        for g in d.hitl_gates:
            assert g.gate_phase, f"{wt}: HitlGate has empty gate_phase"
            assert g.external_event, f"{wt}: HitlGate has empty external_event"
            assert g.persona, f"{wt}: HitlGate has empty persona"


def test_every_persona_has_skill_md():
    for wt, d in registry.DOMAINS.items():
        for g in d.hitl_gates:
            skill = PERSONAE_DIR / g.persona / "SKILL.md"
            assert skill.exists(), (
                f"{wt} HitlGate {g.gate_phase!r} references persona "
                f"{g.persona!r} but {skill} doesn't exist"
            )


def test_orchestrator_names_resolve():
    """Every Domain.orchestrator_name must be a decorated orchestrator
    in function_app.py. Parsed via simple text scan to avoid importing
    the Functions worker module (which depends on Azure runtime)."""
    fa = (REPO_ROOT / "function_app.py").read_text(encoding="utf-8")
    for wt, d in registry.DOMAINS.items():
        # Match the decorator pattern `def <orchestrator_name>(`
        token = f"def {d.orchestrator_name}("
        assert token in fa, (
            f"{wt}: orchestrator_name={d.orchestrator_name!r} not found "
            f"in function_app.py"
        )


def test_resolve_external_event_round_trip():
    """resolve_external_event returns the right event for every gate."""
    for wt, d in registry.DOMAINS.items():
        for g in d.hitl_gates:
            got = registry.resolve_external_event(wt, g.gate_phase)
            assert got == g.external_event, (
                f"{wt}: resolve_external_event({g.gate_phase!r}) "
                f"returned {got!r}, expected {g.external_event!r}"
            )


def test_resolve_external_event_handles_normalisation():
    # "Manager Approval" should resolve like "manager_approval".
    assert registry.resolve_external_event("travel-preapproval", "Manager Approval") \
        == "manager_approval_decision"


def test_by_prefix():
    assert registry.by_prefix("VKY-0001").workflow_type == "vendor-kyc"
    assert registry.by_prefix("EXP-0042").workflow_type == "expense-claim"
    assert registry.by_prefix("HIRE-0007").workflow_type == "hiring"
    assert registry.by_prefix("UNKNOWN-1") is None


def test_all_wake_hints_includes_poc1_red_route():
    hints = registry.all_wake_hints()
    assert "claim.routed.red" in hints


def test_all_wake_hints_includes_at_least_one_per_fleet_domain():
    hints = registry.all_wake_hints()
    expected = {
        "vendor.kyc.high_risk",
        "access.scope.privileged",
        "travel.policy.exception",
        "perf.calibration.outlier",
        "contract.renewal.price_jump",
        "onboarding.access.broad_scope",
    }
    missing = expected - hints
    assert not missing, f"missing wake hints: {missing}"
