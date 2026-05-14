"""pitch-d2: data-driven delegated-authority matrix tests."""
from __future__ import annotations

import pytest

from api.shared.authority import (
    AUTHORITY,
    AuthorityRow,
    authority_check,
    delegate_for,
    is_ooo,
)


def test_authority_table_is_non_empty_and_typed():
    assert AUTHORITY, "AUTHORITY table must not be empty"
    for role, row in AUTHORITY.items():
        assert isinstance(row, AuthorityRow)
        assert row.role == role, f"role key {role} differs from row.role {row.role}"
        assert row.spend_limit_gbp >= 0
        assert isinstance(row.approval_actions, tuple)


def test_check_unknown_role_denied():
    out = authority_check(role="not_a_real_role", action="ap_invoice_approval")
    assert out == {
        "allowed": False,
        "reason": "role 'not_a_real_role' not in authority matrix",
        "governing_rule_id": None,
    }


def test_check_unauthorised_action_denied():
    # ap_clerk only does ap_invoice_approval per the matrix.
    out = authority_check(role="ap_clerk", action="contract_approval", value=10.0)
    assert out["allowed"] is False
    assert "not authorised" in out["reason"]
    assert out["governing_rule_id"] == "AUTH-ap_clerk-deny-action"


def test_check_within_band_allowed():
    out = authority_check(role="controller", action="ap_invoice_approval",
                          value=200_000.0, category="standard")
    assert out["allowed"] is True
    assert out["governing_rule_id"] == "AUTH-controller-ap_invoice_approval"


def test_check_above_band_escalates():
    out = authority_check(role="controller", action="ap_invoice_approval",
                          value=1_000_000.0)
    assert out["allowed"] is False
    assert "exceeds controller spend limit" in out["reason"]
    assert out["governing_rule_id"] == "AUTH-controller-spend-limit"


def test_cfo_authorised_for_top_band():
    out = authority_check(role="cfo", action="ap_invoice_approval",
                          value=5_000_000.0)
    assert out["allowed"] is True


def test_return_shape_matches_sandbox_helper():
    """The return dict MUST carry the three keys the existing
    `_sandbox_authority_check` returns so existing decision_policy
    blocks keep destructuring the dict unchanged."""
    out = authority_check(role="cfo", action="budget_approval", value=100.0)
    assert set(out.keys()) == {"allowed", "reason", "governing_rule_id"}


def test_three_personae_are_flagged_ooo_for_demo():
    ooo = [r for r, row in AUTHORITY.items() if row.ooo_today]
    assert len(ooo) >= 3, f"expected >=3 OOO personae for demo, got {ooo}"


def test_delegate_for_helper():
    assert delegate_for("ap_clerk") == "controller"
    assert delegate_for("cfo") is None
    assert delegate_for("not_a_real_role") is None


def test_is_ooo_helper():
    # cd is hand-flagged in the matrix.
    assert is_ooo("cd") is True
    assert is_ooo("cfo") is False
    assert is_ooo("not_a_real_role") is False


def test_d1_personae_have_authority_rows():
    """Every D1 role we added must carry an AuthorityRow."""
    expected = {
        "regional_controller_emea", "regional_controller_us", "bp_pod_lead",
        "hr_director", "regional_hr_lead", "talent_coordinator",
        "regional_account_lead", "account_manager", "account_coordinator",
        "program_manager", "delivery_lead",
        "contracts_counsel_senior",
        "ecd", "cd", "acd", "senior_copywriter", "senior_artworker",
        "mid_creative", "junior_creative",
        "it_admin_director", "support_engineer",
        "chief_data_officer", "data_lead", "data_engineer",
        "analytics_engineer", "analyst",
        "cs_director", "cs_account_director", "cs_manager", "cs_specialist",
    }
    missing = expected - set(AUTHORITY.keys())
    assert not missing, f"D1 roles missing from AUTHORITY: {sorted(missing)}"
