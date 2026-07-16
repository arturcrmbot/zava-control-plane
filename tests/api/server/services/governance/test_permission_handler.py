"""AGT permission handler — plan/refactor-substrate-agentic-segments-1.md TASK-004.

Exercises ``AGTPermissionHandler`` against the live governance kernel.

Cases:

(a) allowed tool, AGT_ENFORCE off -> approved
(b) allowed tool, AGT_ENFORCE on  -> approved
(c) disallowed tool, AGT_ENFORCE on -> denied-by-rules with reason
(d) kill-switch active for (actor, tool), AGT_ENFORCE on -> denied
(e) non-MCP request kind -> approved (loop-safety fallthrough)
"""
from __future__ import annotations

import os

# Silence the local Azurite blob probe before importing the kernel chain
# (same pattern as test_kernel_log_only.py).
os.environ["AZURE_STORAGE_CONNECTION_STRING"] = ""

import pytest
from copilot.session import PermissionRequest

from api.server.services.governance.permission_handler import AGTPermissionHandler
from api.server.services.governance.kernel import _reset_for_tests
from api.server.services.governance.kill_switch import kill_switch_store


@pytest.fixture(autouse=True)
def _fresh_kernel():
    _reset_for_tests()
    kill_switch_store._kills.clear()  # type: ignore[attr-defined]
    yield
    _reset_for_tests()
    kill_switch_store._kills.clear()  # type: ignore[attr-defined]


def _mcp_request(*, server: str, tool: str, args: dict | None = None) -> PermissionRequest:
    """Construct a minimal MCP-kind PermissionRequest. Pass kind as the
    string 'mcp' rather than the enum so the test doesn't depend on the
    enum import path."""
    return PermissionRequest(
        kind="mcp",  # type: ignore[arg-type]
        server_name=server,
        tool_name=tool,
        args=args or {},
    )


def test_allowed_tool_off_approves(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGT_ENFORCE", raising=False)
    _reset_for_tests()  # rebuild kernel under log_only
    handler = AGTPermissionHandler(skill_label="rag-classifier", workflow_id="WF-1")
    result = handler(_mcp_request(server="policy", tool="search"), {})
    assert result.kind == "approved"


def test_allowed_tool_enforce_approves(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGT_ENFORCE", "1")
    _reset_for_tests()
    handler = AGTPermissionHandler(skill_label="rag-classifier", workflow_id="WF-2")
    # rag-classifier is allowed policy.search per AGENTS registry
    result = handler(_mcp_request(server="policy", tool="search"), {})
    assert result.kind == "approved"


def test_disallowed_tool_enforce_denies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGT_ENFORCE", "1")
    _reset_for_tests()
    handler = AGTPermissionHandler(skill_label="rag-classifier", workflow_id="WF-3")
    # rag-classifier is NOT in the AGENTS registry as a caller of
    # contract_repository.get_contract; should deny under enforce.
    result = handler(
        _mcp_request(server="contract_repository", tool="get_contract"), {},
    )
    assert result.kind == "denied-by-rules"
    assert result.feedback
    assert result.message


def test_kill_switch_active_denies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGT_ENFORCE", "1")
    _reset_for_tests()
    kill_switch_store.add(
        actor="rag-classifier", tool="policy.search",
        reason="ops paused for investigation", ttl_seconds=60,
    )
    handler = AGTPermissionHandler(skill_label="rag-classifier", workflow_id="WF-4")
    result = handler(_mcp_request(server="policy", tool="search"), {})
    assert result.kind == "denied-by-rules"
    assert "kill" in (result.feedback or "").lower() or "paused" in (result.feedback or "").lower()


# ---------------------------------------------------------------------------
# Hiring segment ACL rows (plan/refactor-substrate-agentic-segments-1 TASK-005).
# Each segment label is registered in api.shared.agents.AGENTS with a
# deduped union of its constituent skills' allowed_tools. These tests pin
# both the positive path (a tool in the union approves under enforce) and
# the negative path (a tool NOT in the union denies with the standard
# deny:capability:<actor>:<tool> rule_id).
# ---------------------------------------------------------------------------


def test_segment_b_allowed_tool_enforce_approves(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGT_ENFORCE", "1")
    _reset_for_tests()
    handler = AGTPermissionHandler(skill_label="hiring-segment-b", workflow_id="WF-SEG-B-1")
    # policy.search is in the union (jd-drafter contributes it).
    result = handler(_mcp_request(server="policy", tool="search"), {})
    assert result.kind == "approved"


def test_segment_b_disallowed_tool_enforce_denies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGT_ENFORCE", "1")
    _reset_for_tests()
    handler = AGTPermissionHandler(skill_label="hiring-segment-b", workflow_id="WF-SEG-B-2")
    # contract_repository.get_contract is in tools.yaml but not in
    # segment-b's union; should deny under enforce.
    result = handler(
        _mcp_request(server="contract_repository", tool="get_contract"), {},
    )
    assert result.kind == "denied-by-rules"
    assert "hiring-segment-b" in (result.feedback or "")
    assert "contract_repository.get_contract" in (result.feedback or "")


def test_segment_d_allowed_tool_enforce_approves() -> None:
    """Segment D's union is empty (interview-recommender declares no tools).
    There is no in-union tool to pick; the segment cannot legitimately
    call any manifest tool. Documenting that explicitly here so the
    matrix of (4 segments × 2 cases) tests stays visible — the negative
    path below carries the regression weight for D."""
    import pytest as _pytest
    _pytest.skip("hiring-segment-d allow-list is intentionally empty")


def test_segment_d_disallowed_tool_enforce_denies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGT_ENFORCE", "1")
    _reset_for_tests()
    handler = AGTPermissionHandler(skill_label="hiring-segment-d", workflow_id="WF-SEG-D-2")
    result = handler(
        _mcp_request(server="contract_repository", tool="get_contract"), {},
    )
    assert result.kind == "denied-by-rules"
    assert "hiring-segment-d" in (result.feedback or "")


def test_segment_e_allowed_tool_enforce_approves(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGT_ENFORCE", "1")
    _reset_for_tests()
    handler = AGTPermissionHandler(skill_label="hiring-segment-e", workflow_id="WF-SEG-E-1")
    # policy.search is in the union (jurisdiction-router + betrvg-checker).
    result = handler(_mcp_request(server="policy", tool="search"), {})
    assert result.kind == "approved"


def test_segment_e_disallowed_tool_enforce_denies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGT_ENFORCE", "1")
    _reset_for_tests()
    handler = AGTPermissionHandler(skill_label="hiring-segment-e", workflow_id="WF-SEG-E-2")
    result = handler(
        _mcp_request(server="contract_repository", tool="get_contract"), {},
    )
    assert result.kind == "denied-by-rules"
    assert "hiring-segment-e" in (result.feedback or "")


def test_segment_f_allowed_tool_enforce_approves(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGT_ENFORCE", "1")
    _reset_for_tests()
    handler = AGTPermissionHandler(skill_label="hiring-segment-f", workflow_id="WF-SEG-F-1")
    # avatar.render is the only manifest tool in segment-f's union;
    # reversible_only=False on the segment so this approves even though
    # avatar.render is non-reversible.
    result = handler(_mcp_request(server="avatar", tool="render"), {})
    assert result.kind == "approved"


def test_segment_f_disallowed_tool_enforce_denies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGT_ENFORCE", "1")
    _reset_for_tests()
    handler = AGTPermissionHandler(skill_label="hiring-segment-f", workflow_id="WF-SEG-F-2")
    result = handler(
        _mcp_request(server="contract_repository", tool="get_contract"), {},
    )
    assert result.kind == "denied-by-rules"
    assert "hiring-segment-f" in (result.feedback or "")


def test_non_mcp_kind_approves(monkeypatch: pytest.MonkeyPatch) -> None:
    """Other permission kinds (shell, write, etc) are not used by our
    session config; the handler must approve so the loop doesn't
    deadlock if the SDK ever surfaces one."""
    monkeypatch.setenv("AGT_ENFORCE", "1")
    _reset_for_tests()
    handler = AGTPermissionHandler(skill_label="rag-classifier", workflow_id="WF-5")
    req = PermissionRequest(kind="shell")  # type: ignore[arg-type]
    result = handler(req, {})
    assert result.kind == "approved"
