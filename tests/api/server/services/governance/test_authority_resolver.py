"""TASK-020 — unit tests for the in-process authority resolver.

Exercises the kernel's resolve_approver / check_authority methods
directly (no HTTP). Confirms first-match-wins semantics, wildcard
handling, value-band edges, and the unmatched / unauthorised paths.

Live parity against the Node mock is in
``test_authority_parity.py`` (skipped unless ``AUTHORITY_MCP_LIVE=1``).
"""

from __future__ import annotations

import os

# Same Azurite-probe short-circuit as the other Phase-2/3 governance tests.
os.environ.setdefault("AZURE_STORAGE_CONNECTION_STRING", "")

import pytest

from api.server.services.governance import GovernanceKernel, kernel
from api.server.services.governance.authority import check, resolve
from api.server.services.governance.kernel import _reset_for_tests
from api.shared.vertical_loader import active_runtime


@pytest.fixture(autouse=True)
def _fresh_kernel():
    _reset_for_tests()
    yield
    _reset_for_tests()


# ---------------------------------------------------------------------------
# kernel.resolve_approver — happy path against the real matrix
# ---------------------------------------------------------------------------


def test_resolve_picks_first_matching_band() -> None:
    """A meals claim at £180 hits EXP-002 (band 100..500), not EXP-001."""
    k = kernel()
    r = k.resolve_approver(action="expense_claim_approval", category="meals", value=180.0)
    assert r.matched is True
    assert r.rule_id == "EXP-002"
    assert r.approver_role == "line_manager"
    assert r.threshold_gbp == 500
    assert "ssc_reviewer" in r.escalation_chain


def test_resolve_band_inclusive_on_min() -> None:
    """Band [100, 500] is inclusive on min — but EXP-001's [0, 100] is
    also inclusive on max, and it comes first. So value=100 actually
    resolves to EXP-001, not EXP-002. This is the correct first-match
    semantics from mocks/authority-mcp/resolver.ts."""
    k = kernel()
    r = k.resolve_approver(action="expense_claim_approval", category="meals", value=100.0)
    assert r.matched is True
    assert r.rule_id == "EXP-001"
    assert r.threshold_gbp == 100


def test_resolve_band_inclusive_on_min_when_first_band_excludes() -> None:
    """value=101 falls outside EXP-001's [0, 100] (inclusive max=100),
    so EXP-002's [100, 500] picks it up — proving band inclusivity on
    EXP-002's min."""
    k = kernel()
    r = k.resolve_approver(action="expense_claim_approval", category="meals", value=101.0)
    assert r.matched is True
    assert r.rule_id == "EXP-002"


def test_resolve_band_inclusive_on_max() -> None:
    """Band [100, 500] must include exactly 500."""
    k = kernel()
    r = k.resolve_approver(action="expense_claim_approval", category="meals", value=500.0)
    assert r.matched is True
    assert r.rule_id == "EXP-002"


def test_resolve_unbounded_max_falls_through_to_high_band() -> None:
    """Meals at £10k matches EXP-004 (min=2500, max=null)."""
    k = kernel()
    r = k.resolve_approver(action="expense_claim_approval", category="meals", value=10_000.0)
    assert r.matched is True
    assert r.rule_id == "EXP-004"
    assert r.approver_role == "finance_controller"
    assert r.threshold_gbp is None  # unbounded


def test_resolve_unmatched_returns_reason() -> None:
    """An unknown action returns matched=False with a populated reason."""
    k = kernel()
    r = k.resolve_approver(action="not_a_real_action", value=1.0)
    assert r.matched is False
    assert r.reason
    assert "not_a_real_action" in r.reason


def test_travel_pack_authority_preserves_global_rules_without_airline_leakage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ZAVA_VERTICAL", "travel")
    monkeypatch.delenv("ZAVA_WORLD", raising=False)
    active_runtime.cache_clear()
    try:
        governance = GovernanceKernel()
        travel = governance.resolve_approver(
            action="reaccommodate_travellers",
            value=700.0,
        )
        expense = governance.resolve_approver(
            action="expense_claim_approval",
            category="meals",
            value=180.0,
        )
        airline = governance.resolve_approver(
            action="airline.commit_recovery_plan",
            value=700.0,
        )
    finally:
        active_runtime.cache_clear()

    assert travel.matched is True
    assert travel.rule_id == ("AUTH-operations_controller-reaccommodate_travellers")
    assert expense.matched is True
    assert expense.rule_id == "EXP-002"
    assert airline.matched is False
    assert airline.rule_id is None


def test_airline_pack_synthesizes_only_recovery_command_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ZAVA_VERTICAL", "airline")
    monkeypatch.delenv("ZAVA_WORLD", raising=False)
    active_runtime.cache_clear()
    try:
        governance = GovernanceKernel()
        recovery = governance.check_authority(
            role="duty_operations_manager",
            action="airline.commit_recovery_plan",
            category="synthetic-operational-recovery",
            value=75_000.0,
        )
        hitl_event = governance.resolve_approver(
            action="duty_operations_manager_decision",
            value=75_000.0,
        )
        travel = governance.resolve_approver(
            action="reaccommodate_travellers",
            value=700.0,
        )
    finally:
        active_runtime.cache_clear()

    assert recovery.allowed is True
    assert recovery.governing_rule_id == ("AUTH-duty_operations_manager-airline.commit_recovery_plan")
    assert hitl_event.matched is False
    assert hitl_event.rule_id is None
    assert travel.matched is False
    assert travel.rule_id is None


def test_customer_care_credit_escalates_to_cs_manager() -> None:
    result = kernel().resolve_approver(
        action="customer_care_credit_approval",
        category="service_credit",
        value=75.0,
    )

    assert result.matched is True
    assert result.rule_id == "CARE-002"
    assert result.approver_role == "cs_manager"


def test_order_capacity_exception_routes_to_delivery_lead() -> None:
    result = kernel().resolve_approver(
        action="order_capacity_exception",
        category="site_capacity",
        value=95.0,
    )

    assert result.matched is True
    assert result.rule_id == "ORDER-001"
    assert result.approver_role == "delivery_lead"


@pytest.mark.parametrize(
    ("role", "action", "category", "value", "rule_id"),
    [
        (
            "network_ops_director",
            "network_ops_director_decision",
            "prestage_field_resources",
            13_000.0,
            "TELCO-NETOPS-001",
        ),
        (
            "delivery_lead",
            "delivery_lead_decision",
            "dispatch_field_repair",
            3_500.0,
            "TELCO-DELIVERY-001",
        ),
        (
            "cs_manager",
            "cs_manager_decision",
            "apply_retention_offer",
            75.0,
            "TELCO-CS-001",
        ),
    ],
)
def test_telco_personae_can_close_cascade_hitl_gates(
    role: str,
    action: str,
    category: str,
    value: float,
    rule_id: str,
) -> None:
    result = kernel().check_authority(
        role=role,
        action=action,
        category=category,
        value=value,
    )

    assert result.allowed is True
    assert result.governing_rule_id == rule_id


# ---------------------------------------------------------------------------
# kernel.check_authority — primary, escalation, denied
# ---------------------------------------------------------------------------


def test_check_primary_role_allowed() -> None:
    """The matched approver role is allowed."""
    k = kernel()
    c = k.check_authority(
        role="ssc_reviewer",
        action="expense_claim_approval",
        category="meals",
        value=1000.0,
    )
    assert c.allowed is True
    assert c.governing_rule_id == "EXP-003"
    assert "matched approver" in c.reason


def test_check_escalation_role_allowed() -> None:
    """A role in the escalation chain is also allowed."""
    k = kernel()
    c = k.check_authority(
        role="finance_controller",
        action="expense_claim_approval",
        category="meals",
        value=1000.0,
    )
    assert c.allowed is True
    assert c.governing_rule_id == "EXP-003"
    assert "escalation chain" in c.reason


def test_check_unauthorised_role_denied_with_rule_id() -> None:
    """A random role is denied but the governing rule_id surfaces."""
    k = kernel()
    c = k.check_authority(
        role="intern_with_no_authority",
        action="expense_claim_approval",
        category="meals",
        value=1000.0,
    )
    assert c.allowed is False
    assert c.governing_rule_id == "EXP-003"
    assert "not authorised" in c.reason


def test_check_unmatched_action_denied_with_no_rule_id() -> None:
    """No matching rule -> denied AND governing_rule_id is None."""
    k = kernel()
    c = k.check_authority(role="ssc_reviewer", action="not_a_real_action", value=1.0)
    assert c.allowed is False
    assert c.governing_rule_id is None


# ---------------------------------------------------------------------------
# Resolver primitives — direct (no kernel boot needed)
# ---------------------------------------------------------------------------


def test_resolve_wildcard_business_unit_matches_anything() -> None:
    matrix = [
        {
            "rule_id": "T-1",
            "action": "x",
            "category": "*",
            "business_unit": "*",
            "geography": "*",
            "requester_role": "*",
            "approver_role": "owner",
            "value_band_gbp": {"min": None, "max": None},
            "escalation_chain": [],
            "basis": "",
        },
    ]
    r = resolve(matrix, action="x", business_unit="anywhere")
    assert r.matched and r.rule_id == "T-1"


def test_resolve_specific_business_unit_overrides_wildcard_when_listed_first() -> None:
    """First-match-wins: a specific BU rule listed first beats a wildcard."""
    matrix = [
        {
            "rule_id": "T-SPEC",
            "action": "x",
            "category": "*",
            "business_unit": "media",
            "geography": "*",
            "requester_role": "*",
            "approver_role": "media_lead",
            "value_band_gbp": {"min": None, "max": None},
            "escalation_chain": [],
            "basis": "",
        },
        {
            "rule_id": "T-DEFAULT",
            "action": "x",
            "category": "*",
            "business_unit": "*",
            "geography": "*",
            "requester_role": "*",
            "approver_role": "default_owner",
            "value_band_gbp": {"min": None, "max": None},
            "escalation_chain": [],
            "basis": "",
        },
    ]
    r1 = resolve(matrix, action="x", business_unit="media")
    assert r1.rule_id == "T-SPEC" and r1.approver_role == "media_lead"

    r2 = resolve(matrix, action="x", business_unit="other")
    assert r2.rule_id == "T-DEFAULT" and r2.approver_role == "default_owner"


def test_resolve_value_outside_band_falls_through() -> None:
    matrix = [
        {
            "rule_id": "T-LOW",
            "action": "x",
            "category": "*",
            "business_unit": "*",
            "geography": "*",
            "requester_role": "*",
            "approver_role": "junior",
            "value_band_gbp": {"min": 0, "max": 100},
            "escalation_chain": [],
            "basis": "",
        },
        {
            "rule_id": "T-HIGH",
            "action": "x",
            "category": "*",
            "business_unit": "*",
            "geography": "*",
            "requester_role": "*",
            "approver_role": "senior",
            "value_band_gbp": {"min": 100, "max": 1000},
            "escalation_chain": [],
            "basis": "",
        },
    ]
    assert resolve(matrix, action="x", value=50).rule_id == "T-LOW"
    # Value 100 hits the lower band first (inclusive on max).
    assert resolve(matrix, action="x", value=100).rule_id == "T-LOW"
    assert resolve(matrix, action="x", value=500).rule_id == "T-HIGH"


def test_resolve_skips_malformed_rules() -> None:
    """A rule missing rule_id is skipped; the next matching rule wins."""
    matrix = [
        {"action": "x"},  # malformed: no rule_id, no approver_role
        {
            "rule_id": "T-OK",
            "action": "x",
            "category": "*",
            "business_unit": "*",
            "geography": "*",
            "requester_role": "*",
            "approver_role": "owner",
            "value_band_gbp": {"min": None, "max": None},
            "escalation_chain": [],
            "basis": "",
        },
    ]
    assert resolve(matrix, action="x").rule_id == "T-OK"


def test_check_returns_unmatched_reason_when_no_rule_matches() -> None:
    out = check([], role="anyone", action="missing")
    assert out.allowed is False
    assert out.governing_rule_id is None
    assert "no rule matched" in out.reason or "missing" in out.reason
