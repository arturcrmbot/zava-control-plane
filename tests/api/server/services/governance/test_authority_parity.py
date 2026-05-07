"""TASK-021 — in-process kernel ≡ Node mock parity test.

For each of the 8 canonical resolutions from
``plan/feature-authority-and-personae-1.md`` TASK-006, assert the
in-process ``GovernanceKernel.resolve_approver(...)`` and
``check_authority(...)`` return byte-identical fields to the Node mock
running at ``http://127.0.0.1:4108`` (or ``$AUTHORITY_MCP_URL``).

Skipped unless ``AUTHORITY_MCP_LIVE=1`` is set (mock spun up via
``make mcp-authority`` or the new ``make boot-demo-with-authority-mock``
target from TASK-025a). The CI ring (Phase 8) runs this test once per
nightly build with the mock spun up under that flag, then tears it
down — the mock is no longer part of the autonomous demo loop after
TASK-025a.
"""
from __future__ import annotations

import os

# Short-circuit Azurite probe at import time so the kernel constructor
# (which also constructs api.server.state via late imports) stays clean
# under pytest. See /memories/repo/wpp-pre-existing-test-failures.md.
os.environ.setdefault("AZURE_STORAGE_CONNECTION_STRING", "")

import httpx
import pytest

from api.server.services.governance import kernel
from api.server.services.governance.kernel import _reset_for_tests


_LIVE = os.environ.get("AUTHORITY_MCP_LIVE") == "1"
_BASE = os.environ.get("AUTHORITY_MCP_URL", "http://127.0.0.1:4108").rstrip("/")


@pytest.fixture(autouse=True)
def _fresh_kernel():
    _reset_for_tests()
    yield
    _reset_for_tests()


# Same 8 canonical cases as tests/api/unit/test_delegated_authority_tool.py
# (the live integration block). Each row is the exact request shape both
# sides receive; the assertion is "kernel output == mock output".
CANONICAL: list[dict] = [
    {"action": "expense_claim_approval", "category": "meals", "value": 180},
    {"action": "travel_preapproval", "category": "international", "value": 4200},
    {"action": "vendor_kyc_signoff", "category": "high_risk", "value": None},
    {"action": "contract_renewal_signoff", "category": "price_jump", "value": 35000},
    {"action": "it_access_grant", "category": "privileged_role", "value": None},
    {"action": "employee_onboarding_access", "category": "external_contractor", "value": None},
    {"action": "perf_calibration_signoff", "category": "calibration_outlier", "value": None},
    {"action": "hire_budget_approval", "category": "within_band", "value": 8000},
]


def _mock_resolve(req: dict) -> dict:
    resp = httpx.post(f"{_BASE}/resolve_approver", json=req, timeout=5.0)
    resp.raise_for_status()
    return resp.json()


def _mock_check(req: dict) -> dict:
    resp = httpx.post(f"{_BASE}/check_authority", json=req, timeout=5.0)
    resp.raise_for_status()
    return resp.json()


@pytest.mark.skipif(
    not _LIVE,
    reason="AUTHORITY_MCP_LIVE not set; skipping live parity test",
)
@pytest.mark.parametrize("req", CANONICAL, ids=lambda r: r["action"])
def test_resolve_approver_parity(req: dict) -> None:
    """Kernel and Node mock must produce byte-identical resolutions."""
    k = kernel()
    in_proc = k.resolve_approver(**req).model_dump(exclude_none=False)
    via_mock = _mock_resolve(req)

    # Normalise: pydantic always emits all fields (with None); the Node
    # mock omits ``reason`` on success and ``approver_role`` etc. on
    # failure. Compare on the union of keys both sides set.
    if in_proc.get("matched") and via_mock.get("matched"):
        assert in_proc["approver_role"] == via_mock["approver_role"]
        assert in_proc["threshold_gbp"] == via_mock["threshold_gbp"]
        assert in_proc["escalation_chain"] == via_mock["escalation_chain"]
        assert in_proc["rule_id"] == via_mock["rule_id"]
        assert in_proc["basis"] == via_mock["basis"]
    else:
        assert in_proc["matched"] == via_mock["matched"]
        # Both unmatched: reasons are human-readable; assert they exist.
        assert in_proc.get("reason")
        assert via_mock.get("reason")


@pytest.mark.skipif(
    not _LIVE,
    reason="AUTHORITY_MCP_LIVE not set; skipping live parity test",
)
@pytest.mark.parametrize("req", CANONICAL, ids=lambda r: r["action"])
def test_check_authority_parity(req: dict) -> None:
    """For each canonical case, ask both sides whether the matched
    approver role would itself be authorised — should match exactly."""
    k = kernel()
    # First resolve to get the role to ask about.
    resolution = k.resolve_approver(**req)
    if not resolution.matched:
        pytest.skip(f"no matched rule for {req!r}; skipping check parity")
    role = resolution.approver_role

    in_proc = k.check_authority(role=role, **req).model_dump()
    via_mock = _mock_check({**req, "role": role})

    assert in_proc["allowed"] == via_mock["allowed"]
    assert in_proc["governing_rule_id"] == via_mock["governing_rule_id"]
    # Reason text is informational; both sides should produce one.
    assert in_proc["reason"]
    assert via_mock["reason"]


@pytest.mark.skipif(
    not _LIVE,
    reason="AUTHORITY_MCP_LIVE not set; skipping live parity test",
)
def test_check_authority_unauthorised_role_parity() -> None:
    """A role that is NOT in the matched rule's approver/escalation must
    be denied identically by both sides."""
    k = kernel()
    req = {"action": "expense_claim_approval", "category": "meals", "value": 180}
    in_proc = k.check_authority(role="intern_with_no_authority", **req).model_dump()
    via_mock = _mock_check({**req, "role": "intern_with_no_authority"})

    assert in_proc["allowed"] is False
    assert via_mock["allowed"] is False
    assert in_proc["governing_rule_id"] == via_mock["governing_rule_id"]
