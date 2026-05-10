"""Tests for compose-domain v4 brief schema validator (TASK-002)."""
from __future__ import annotations

import pytest


@pytest.fixture
def minimal_brief():
    return {
        "domain": {
            "workflow_type": "vendor-kyc",
            "prefix": "fleet",
            "display_name": "Vendor KYC",
        },
        "phases": [
            {"name": "intake", "kind": "deterministic"},
            {"name": "signoff", "kind": "hitl", "persona": "vendor_kyc_finance_bp"},
        ],
    }


def test_minimal_brief_validates(minimal_brief, shared_validator):
    shared_validator.validate_brief(minimal_brief)


def test_full_v4_brief_validates(shared_validator):
    full = {
        "domain": {
            "workflow_type": "purchase-card",
            "prefix": "fleet",
            "display_name": "Purchase card reconciliation",
        },
        "phases": [
            {"name": "intake", "kind": "deterministic"},
            {"name": "policy_match", "kind": "agent", "agent_skill_name": "policy-match"},
            {"name": "manager_signoff", "kind": "hitl", "persona": "manager",
             "external_event": "manager_signoff_decision"},
        ],
        "entities": [
            {"kind": "Money", "ref_field": "payload.txn_id", "source": "purchase-card"},
        ],
        "decisions": [
            {"phase": "manager_signoff", "persona": "manager",
             "source_event": "workflow.hitl.requested"},
        ],
        "function": "finance",
        "ambient": {
            "name": "PCardWatcher",
            "function": "finance",
            "spawnable_workflow_types": ["purchase-card"],
            "triggers": [{"kind": "cadence", "cron": "0 0 * * *"}],
        },
    }
    shared_validator.validate_brief(full)


def test_missing_domain_raises(shared_validator):
    with pytest.raises(shared_validator.SchemaError) as exc:
        shared_validator.validate_brief({"phases": []})
    assert "domain" in exc.value.reason or exc.value.path == "<root>"


def test_bad_phase_kind_raises(shared_validator, minimal_brief):
    minimal_brief["phases"][0]["kind"] = "wat"
    with pytest.raises(shared_validator.SchemaError) as exc:
        shared_validator.validate_brief(minimal_brief)
    assert exc.value.path.startswith("phases[0].kind")


def test_bad_function_raises(shared_validator, minimal_brief):
    minimal_brief["function"] = "synergy"
    with pytest.raises(shared_validator.SchemaError) as exc:
        shared_validator.validate_brief(minimal_brief)
    assert exc.value.path == "function"


def test_v3_brief_with_personae_back_compat(shared_validator):
    v3 = {
        "domain": {
            "workflow_type": "vendor-kyc",
            "prefix": "fleet",
            "display_name": "Vendor KYC",
        },
        "phases": [{"name": "intake", "kind": "deterministic"}],
        "personae": [{"role": "x", "decision_policy": "y", "decision_code": "pass"}],
        "external_systems": [{"id": "s", "mcp_tool": "m"}],
    }
    shared_validator.validate_brief(v3)
