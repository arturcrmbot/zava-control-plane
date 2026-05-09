"""Tests for author-function-membership (TASK-021)."""
from __future__ import annotations

from dataclasses import dataclass, field

import pytest


@pytest.fixture
def brief():
    return {
        "domain": {
            "workflow_type": "purchase-card",
            "prefix": "fleet",
            "display_name": "Purchase card",
        },
        "phases": [
            {"name": "intake", "kind": "deterministic"},
            {"name": "signoff", "kind": "hitl",
             "persona": "manager", "external_event": "manager_signoff_decision"},
        ],
        "function": "finance",
    }


@pytest.fixture
def validator(sub_skill_loader):
    return sub_skill_loader("author-function-membership", "validator")


def test_known_function_validates_against_placeholder(validator, brief):
    validator.validate(brief)


def test_unknown_function_raises(validator, brief):
    brief["function"] = "not-a-function"
    with pytest.raises(validator.SchemaError) as exc:
        validator.validate(brief)
    assert exc.value.path == "function"
    # JSON schema enum check or our semantic "unknown function" — either is fine.
    assert "not-a-function" in exc.value.reason or "unknown function" in exc.value.reason


def test_missing_function_raises(validator, brief):
    brief.pop("function")
    with pytest.raises(validator.SchemaError) as exc:
        validator.validate(brief)
    assert exc.value.path == "function"


def test_placeholder_has_eleven_canonical_keys(validator):
    assert validator.FUNCTIONS_PLACEHOLDER == {
        "finance", "hr", "revenue", "ops", "legal",
        "marketing", "tech", "data", "customer-success", "ceo", "legacy",
    }


def test_dup_claim_in_other_function_raises(validator, brief):
    @dataclass
    class _Entry:
        owns_domains: list[str] = field(default_factory=list)

    registry = {
        "finance": _Entry(owns_domains=["vendor-kyc"]),
        # purchase-card is (incorrectly) already claimed by hr in this
        # synthetic registry — switching it to finance should raise.
        "hr": _Entry(owns_domains=["purchase-card"]),
        "revenue": _Entry(),
        "ops": _Entry(),
        "legal": _Entry(),
        "marketing": _Entry(),
        "tech": _Entry(),
        "data": _Entry(),
        "customer-success": _Entry(),
        "ceo": _Entry(),
        "legacy": _Entry(),
    }
    with pytest.raises(validator.SchemaError) as exc:
        validator.validate(brief, registry_override=registry)
    assert exc.value.path == "function"
    assert "already claimed" in exc.value.reason


def test_same_function_self_claim_is_fine(validator, brief):
    @dataclass
    class _Entry:
        owns_domains: list[str] = field(default_factory=list)

    registry = {k: _Entry() for k in validator.FUNCTIONS_PLACEHOLDER}
    registry["finance"].owns_domains.append("purchase-card")
    # This should NOT raise — same function re-claiming itself is fine.
    validator.validate(brief, registry_override=registry)
