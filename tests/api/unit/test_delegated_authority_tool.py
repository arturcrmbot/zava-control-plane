"""Tests for delegated_authority MCP tool wrapper.

Two test surfaces:
  - Unit: stub httpx with MockTransport and assert request shape + response parsing.
  - Live integration (skipped unless AUTHORITY_MCP_LIVE=1): hit the real Node mock
    on port 4108 and assert the 8 canonical resolutions from
    mocks/authority-mcp/test/resolver.test.ts.

Phase 3 TASK-022 note: the default backend for ``resolve_approver`` /
``check_authority`` is now the in-process governance kernel; the HTTP
path is reached only when ``AUTHORITY_MCP_URL`` is set in env. The unit
tests below explicitly enter the HTTP branch via the autouse fixture
``_force_http_backend`` so the existing httpx-MockTransport assertions
remain meaningful (they validate the engagement-POC swap-in seam).
In-process resolver coverage lives in
``tests/api/server/services/governance/test_authority_resolver.py``.
"""
from __future__ import annotations

import asyncio
import json
import os

import httpx
import pytest

from api.server.mcp_tools import delegated_authority as da


@pytest.fixture(autouse=True)
def _force_http_backend(monkeypatch):
    """Force the HTTP fallback path. The unit tests below stub
    ``httpx.post`` and assert HTTP request shape; that path is only
    taken when ``AUTHORITY_MCP_URL`` is present (TASK-022)."""
    monkeypatch.setenv("AUTHORITY_MCP_URL", "http://127.0.0.1:4108")
    yield


# --------------------------------------------------------------------------
# Unit tests — stubbed httpx
# --------------------------------------------------------------------------


def _stub_transport(handler):
    """Replace `httpx.post` with a callable that runs `handler(request)` and
    returns its response with the request attached (so `raise_for_status` works)."""

    def _post(url, json=None, timeout=None, **kwargs):  # noqa: A002 (mirror httpx kwargs)
        request = httpx.Request("POST", url, json=json)
        response = handler(request)
        response.request = request
        return response

    return _post


def test_resolve_approver_sends_correct_payload(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "matched": True,
                "approver_role": "ssc_reviewer",
                "threshold_gbp": 2500,
                "escalation_chain": ["finance_controller"],
                "rule_id": "EXP-003",
                "basis": "Material meals expense.",
            },
        )

    monkeypatch.setattr(da.httpx, "post", _stub_transport(handler))

    result = da.resolve_approver(
        action="expense_claim_approval",
        category="meals",
        value=1000,
        business_unit="creative",
        geography="EMEA",
    )

    assert isinstance(result, da.ApproverResolution)
    assert result.matched is True
    assert result.approver_role == "ssc_reviewer"
    assert result.threshold_gbp == 2500
    assert result.escalation_chain == ["finance_controller"]
    assert result.rule_id == "EXP-003"

    assert captured["url"].endswith("/resolve_approver")
    body = captured["body"]
    assert body["action"] == "expense_claim_approval"
    assert body["category"] == "meals"
    assert body["value"] == 1000
    assert body["business_unit"] == "creative"
    assert body["geography"] == "EMEA"


def test_resolve_approver_no_match(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"matched": False, "reason": "no rule matched"})

    monkeypatch.setattr(da.httpx, "post", _stub_transport(handler))

    result = da.resolve_approver(action="no_such_action")
    assert result.matched is False
    assert result.approver_role is None
    assert result.reason and "no rule matched" in result.reason


def test_check_authority_allows_primary(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "allowed": True,
                "reason": "role 'ssc_reviewer' is the matched approver per rule EXP-003",
                "governing_rule_id": "EXP-003",
            },
        )

    monkeypatch.setattr(da.httpx, "post", _stub_transport(handler))

    result = da.check_authority(role="ssc_reviewer", action="expense_claim_approval", value=1000)
    assert result.allowed is True
    assert result.governing_rule_id == "EXP-003"


def test_resolve_approver_url_respects_env(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"matched": False, "reason": "stub"})

    monkeypatch.setattr(da.httpx, "post", _stub_transport(handler))
    monkeypatch.setenv("AUTHORITY_MCP_URL", "http://elsewhere:9999/")

    da.resolve_approver(action="expense_claim_approval")
    assert captured["url"] == "http://elsewhere:9999/resolve_approver"


def test_resolve_approver_tool_returns_json_payload(monkeypatch):
    from copilot.tools import ToolInvocation

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "matched": True,
                "approver_role": "line_manager",
                "threshold_gbp": 500,
                "escalation_chain": ["ssc_reviewer", "finance_controller"],
                "rule_id": "EXP-002",
                "basis": "Meals expense above per-diem requires line manager review.",
            },
        )

    monkeypatch.setattr(da.httpx, "post", _stub_transport(handler))

    inv = ToolInvocation(
        session_id="t",
        tool_call_id="t",
        tool_name="delegated_authority_resolve_approver",
        arguments={"action": "expense_claim_approval", "category": "meals", "value": 180},
    )
    result = asyncio.run(da.delegated_authority_resolve_approver_tool.handler(inv))
    assert result.result_type == "success"
    payload = json.loads(result.text_result_for_llm)
    assert payload["matched"] is True
    assert payload["approver_role"] == "line_manager"
    assert payload["rule_id"] == "EXP-002"


def test_check_authority_tool_returns_json_payload(monkeypatch):
    from copilot.tools import ToolInvocation

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "allowed": False,
                "reason": "role 'candidate' is not authorised; matched rule EXP-003 requires 'ssc_reviewer'",
                "governing_rule_id": "EXP-003",
            },
        )

    monkeypatch.setattr(da.httpx, "post", _stub_transport(handler))

    inv = ToolInvocation(
        session_id="t",
        tool_call_id="t",
        tool_name="delegated_authority_check_authority",
        arguments={"role": "candidate", "action": "expense_claim_approval", "value": 1000},
    )
    result = asyncio.run(da.delegated_authority_check_authority_tool.handler(inv))
    assert result.result_type == "success"
    payload = json.loads(result.text_result_for_llm)
    assert payload["allowed"] is False
    assert payload["governing_rule_id"] == "EXP-003"


def test_tool_returns_failure_on_http_error(monkeypatch):
    from copilot.tools import ToolInvocation

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    monkeypatch.setattr(da.httpx, "post", _stub_transport(handler))

    inv = ToolInvocation(
        session_id="t",
        tool_call_id="t",
        tool_name="delegated_authority_resolve_approver",
        arguments={"action": "expense_claim_approval"},
    )
    result = asyncio.run(da.delegated_authority_resolve_approver_tool.handler(inv))
    assert result.result_type == "failure"
    assert "unreachable" in result.text_result_for_llm.lower()


# --------------------------------------------------------------------------
# Phase 3 TASK-022 — default backend is in-process when env var unset
# --------------------------------------------------------------------------


def test_resolve_approver_uses_kernel_when_env_unset(monkeypatch):
    """With AUTHORITY_MCP_URL absent, the call MUST go through the
    in-process kernel and httpx MUST NOT be touched."""
    # Override the autouse fixture's env setting.
    monkeypatch.delenv("AUTHORITY_MCP_URL", raising=False)
    # Sentinel — fail loudly if anything reaches httpx.
    def _boom(*a, **kw):
        raise AssertionError("httpx.post called when AUTHORITY_MCP_URL unset")
    monkeypatch.setattr(da.httpx, "post", _boom)

    result = da.resolve_approver(
        action="expense_claim_approval", category="meals", value=180
    )
    assert result.matched is True
    assert result.rule_id == "EXP-002"
    assert result.approver_role == "line_manager"


def test_check_authority_uses_kernel_when_env_unset(monkeypatch):
    """Same for check_authority: kernel by default, no httpx."""
    monkeypatch.delenv("AUTHORITY_MCP_URL", raising=False)
    def _boom(*a, **kw):
        raise AssertionError("httpx.post called when AUTHORITY_MCP_URL unset")
    monkeypatch.setattr(da.httpx, "post", _boom)

    result = da.check_authority(
        role="ssc_reviewer",
        action="expense_claim_approval",
        category="meals",
        value=1000,
    )
    assert result.allowed is True
    assert result.governing_rule_id == "EXP-003"


# --------------------------------------------------------------------------
# Live integration — only when AUTHORITY_MCP_LIVE=1 and the mock is running.
# --------------------------------------------------------------------------


_LIVE = os.environ.get("AUTHORITY_MCP_LIVE") == "1"


@pytest.mark.skipif(not _LIVE, reason="AUTHORITY_MCP_LIVE not set; skipping live integration")
@pytest.mark.parametrize(
    "action,category,value,expect_rule,expect_approver",
    [
        ("expense_claim_approval", "meals", 180, "EXP-002", "line_manager"),
        ("travel_preapproval", "international", 4200, "TRV-011", "finance_controller"),
        ("vendor_kyc_signoff", "high_risk", None, "VKY-003", "contracts_counsel"),
        ("contract_renewal_signoff", "price_jump", 35000, "CRN-010", "contract_finance_bp"),
        ("it_access_grant", "privileged_role", None, "ITAR-003", "it_access_it_admin"),
        ("employee_onboarding_access", "external_contractor", None, "ONB-003", "onboarding_it_admin"),
        ("perf_calibration_signoff", "calibration_outlier", None, "PRR-002", "perf_review_hr_bp"),
        ("hire_budget_approval", "within_band", 8000, "HIRE-BUDGET-002", "finance_bp"),
    ],
)
def test_live_canonical_resolutions(action, category, value, expect_rule, expect_approver):
    result = da.resolve_approver(action=action, category=category, value=value)
    assert result.matched is True, f"expected match for {action}/{category}/{value}"
    assert result.rule_id == expect_rule
    assert result.approver_role == expect_approver
