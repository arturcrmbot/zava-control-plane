"""Behavioural-parity tests for the 3 personae migrated in Phase 4.

Each persona's authority lookup is stubbed (no live MCP needed). The
tests assert that the migrated decision_policy returns the same
decision/reason shape as before for the canonical inputs that exercised
the old inline thresholds.
"""
from __future__ import annotations

import pytest

import api.server.services.persona_responder as pr
from api.server.services.persona_responder import _load_personae


@pytest.fixture
def stub_authority_check(monkeypatch):
    """Replace the sandbox authority_check with a deterministic stub.

    The stub mimics the matrix's behaviour for the rules these personae
    care about. Tests can override per-call via the `responses` mapping.
    """
    calls: list[dict] = []

    def factory(responses=None):
        responses = responses or {}

        def _stub(role, action, value=None, category=None, **kwargs):
            calls.append({
                "role": role, "action": action, "value": value,
                "category": category, **kwargs,
            })
            key = (role, action, category)
            if key in responses:
                return responses[key]
            # Default: allow everything, with a synthetic governing_rule_id.
            return {"allowed": True, "reason": "stubbed", "governing_rule_id": "STUB-001"}

        monkeypatch.setitem(pr._DECISION_BUILTINS, "authority_check", _stub)
        return calls

    return factory


def _persona(role: str):
    defs = _load_personae()
    p = defs.get(role)
    assert p is not None, f"persona {role} not loaded"
    return p


# --------------------------------------------------------------------------
# finance_bp parity
# --------------------------------------------------------------------------


def test_finance_bp_approves_within_delegation(stub_authority_check):
    stub_authority_check()
    p = _persona("finance_bp")
    result = p.decide({
        "budget": {
            "verdict": "needs_finance_bp",
            "requires_finance_bp": True,
            "delta_vs_midpoint_gbp": 7500,  # within £10k
            "envelope_remaining_gbp": 50000,
        },
    })
    assert result["decision"] == "approve"
    assert "delegation" in result["reason"].lower()
    assert "STUB-001" in result["reason"]


def test_finance_bp_rejects_outside_delegation(stub_authority_check):
    stub_authority_check(responses={
        ("finance_bp", "hire_budget_approval", "within_band"): {
            "allowed": False,
            "reason": "not authorised",
            "governing_rule_id": "HIRE-BUDGET-003",
        },
    })
    p = _persona("finance_bp")
    result = p.decide({
        "budget": {
            "verdict": "needs_finance_bp",
            "requires_finance_bp": True,
            "delta_vs_midpoint_gbp": 15000,  # over £10k
            "envelope_remaining_gbp": 50000,
        },
    })
    assert result["decision"] == "reject"
    assert "exceeds" in result["reason"].lower()
    assert "HIRE-BUDGET-003" in result["reason"]


def test_finance_bp_rejects_out_of_envelope(stub_authority_check):
    stub_authority_check()
    p = _persona("finance_bp")
    result = p.decide({
        "budget": {
            "verdict": "out_of_envelope",
            "requires_finance_bp": True,
            "delta_vs_midpoint_gbp": 0,
            "envelope_remaining_gbp": -5000,
        },
    })
    assert result["decision"] == "reject"
    assert "envelope" in result["reason"].lower()


# --------------------------------------------------------------------------
# ssc_reviewer parity
# --------------------------------------------------------------------------


def test_ssc_reviewer_accepts_small_meals(stub_authority_check):
    stub_authority_check()
    p = _persona("ssc_reviewer")
    result = p.decide({
        "claim": {"category": "meals", "amount": 120, "currency": "GBP"},
        "arbitrate": {"recommendation": "approve"},
    })
    assert result["decision"] == "approve"
    assert "STUB-001" in result["reason"]


def test_ssc_reviewer_rejects_when_outside_delegation(stub_authority_check):
    stub_authority_check(responses={
        ("ssc_reviewer", "expense_claim_approval", "entertainment"): {
            "allowed": False,
            "reason": "outside band",
            "governing_rule_id": "EXP-022",
        },
    })
    p = _persona("ssc_reviewer")
    result = p.decide({
        "claim": {"category": "entertainment", "amount": 3500, "currency": "GBP"},
        "arbitrate": {"recommendation": "approve"},
    })
    assert result["decision"] == "reject"
    assert "EXP-022" in result["reason"]


def test_ssc_reviewer_agrees_with_arbitration_reject(stub_authority_check):
    stub_authority_check()
    p = _persona("ssc_reviewer")
    result = p.decide({
        "claim": {"category": "meals", "amount": 80, "currency": "GBP"},
        "arbitrate": {"recommendation": "reject"},
    })
    assert result["decision"] == "reject"
    assert "arbitration" in result["reason"].lower()


# --------------------------------------------------------------------------
# contract_finance_bp parity
# --------------------------------------------------------------------------


def test_contract_finance_bp_approves_under_10pct(stub_authority_check):
    stub_authority_check()
    p = _persona("contract_finance_bp")
    result = p.decide({
        "renewal_terms_drafter": {
            "cost_change_pct": 5.0,
            "proposed_annual_value_usd": 100000,
        },
    })
    assert result["decision"] == "approve"
    assert "10%" in result["reason"]
    assert "STUB-001" in result["reason"]


def test_contract_finance_bp_rejects_between_10_and_25pct(stub_authority_check):
    stub_authority_check()
    p = _persona("contract_finance_bp")
    result = p.decide({
        "renewal_terms_drafter": {
            "cost_change_pct": 18.0,
            "proposed_annual_value_usd": 100000,
        },
    })
    assert result["decision"] == "reject"
    assert "10%" in result["reason"]


def test_contract_finance_bp_escalates_above_25pct(stub_authority_check):
    stub_authority_check()
    p = _persona("contract_finance_bp")
    result = p.decide({
        "renewal_terms_drafter": {
            "cost_change_pct": 30.0,
            "proposed_annual_value_usd": 100000,
        },
    })
    assert result["decision"] == "escalate"
    assert "25%" in result["reason"]


def test_contract_finance_bp_rejects_when_pct_missing(stub_authority_check):
    stub_authority_check()
    p = _persona("contract_finance_bp")
    result = p.decide({"renewal_terms_drafter": {}})
    assert result["decision"] == "reject"
    assert "cost_change_pct" in result["reason"]
