"""Tests for the api.shared.personas registry."""
from __future__ import annotations

from pathlib import Path

import pytest

from api.shared import personas
from api.shared.personas import PERSONAS, Persona, get, by_archetype, by_function

REPO_ROOT = Path(__file__).resolve().parents[3]
PERSONAE_DIR = REPO_ROOT / "api" / "server" / "personae"


def test_every_registered_persona_has_a_skill_md():
    for role, p in PERSONAS.items():
        skill = PERSONAE_DIR / role / "SKILL.md"
        assert skill.exists(), f"Persona '{role}' is in PERSONAS but missing {skill}"


def test_every_skill_md_has_a_registry_entry():
    on_disk = {p.name for p in PERSONAE_DIR.iterdir() if p.is_dir()}
    on_disk.discard("__pycache__")
    missing = on_disk - set(PERSONAS.keys())
    assert not missing, f"Personae with SKILL.md but no registry entry: {sorted(missing)}"


def test_registry_archetype_values_are_valid():
    valid = {"approver", "subject", "reviewer", "delegate", "notifier"}
    for role, p in PERSONAS.items():
        assert p.archetype in valid, (
            f"Persona '{role}' has invalid archetype {p.archetype!r}; expected one of {valid}"
        )


def test_registry_scope_function_values_are_valid():
    valid = {"finance", "hr", "it", "procurement", "legal", "legal_privacy", "commercial", "candidate"}
    for role, p in PERSONAS.items():
        assert p.scope_function in valid, (
            f"Persona '{role}' has invalid scope_function {p.scope_function!r}; expected one of {valid}"
        )


def test_every_domain_hitl_gate_persona_is_registered():
    """Cross-check: every persona named in api.shared.domains.DOMAINS HITL gates exists in PERSONAS."""
    from api.shared.domains import DOMAINS

    for workflow_type, domain in DOMAINS.items():
        for gate in domain.hitl_gates:
            assert gate.persona in PERSONAS, (
                f"Domain '{workflow_type}' HITL gate '{gate.gate_phase}' references "
                f"persona '{gate.persona}' which is NOT in api.shared.personas.PERSONAS"
            )


def test_get_helper_returns_registered_persona():
    p = get("ssc_reviewer")
    assert p is not None
    assert p.role == "ssc_reviewer"
    assert p.archetype == "reviewer"
    assert p.scope_function == "finance"


def test_get_helper_returns_none_for_unknown_role():
    assert get("not_a_real_role") is None


def test_by_archetype_groups_correctly():
    approvers = by_archetype("approver")
    assert len(approvers) >= 10
    assert all(p.archetype == "approver" for p in approvers)
    subjects = by_archetype("subject")
    assert {p.role for p in subjects} >= {"candidate", "claim_submitter"}


def test_by_function_groups_correctly():
    finance = by_function("finance")
    assert {p.role for p in finance} >= {"finance_bp", "ssc_reviewer", "vendor_kyc_finance_bp", "contract_finance_bp"}


def test_authority_users_lists_migrated_personae():
    users = personas.authority_users()
    roles = {p.role for p in users}
    # The 3 personae migrated in Phase 4 of feature-authority-and-personae-1:
    assert {"finance_bp", "ssc_reviewer", "contract_finance_bp"} <= roles, (
        f"Expected the 3 Phase-4 migrated personae in authority_users(); got: {sorted(roles)}"
    )


def test_registry_count_meets_minimum_baseline():
    # Phase 6 baseline: 15 originally + 14 graduated via compose-persona = 29.
    assert len(PERSONAS) >= 27
