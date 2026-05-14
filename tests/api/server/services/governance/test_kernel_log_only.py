"""TASK-018 — log-only kernel guard at the chokepoints.

Asserts:

(a) ``call_mcp`` produces a governance decision and stamps it onto the
    ``mcp.call`` event payload via the existing ``emit`` helper.
(b) In log-only mode, ``call_mcp`` does NOT raise even when the kernel
    is forced to deny.
(c) ``@traced_tool`` decorator records the decision and runs the wrapped
    function regardless in log-only mode.
(d) In enforce mode the chokepoints raise ``GovernanceDenied`` and skip
    the wrapped body / network hop.
"""
from __future__ import annotations

import os

# IMPORTANT: silence the local Azurite blob-store probe BEFORE any import
# of ``api.server.mcp_tools`` reaches ``api.server.state``. The package's
# ``__init__`` triggers a chain that lands in ``BlobStore.__init__``,
# which calls ``create_container`` against Azurite and hangs (with
# 60-second retries) when the local emulator isn't running. The
# governance test suite does not need blob storage; clearing the conn
# string short-circuits ``_build_blob_store`` to ``None``. See
# /memories/repo/zava-pre-existing-test-failures.md.
os.environ["AZURE_STORAGE_CONNECTION_STRING"] = ""

from unittest.mock import patch

import pytest

from api.server.services.governance import Decision, kernel
from api.server.services.governance.kernel import _reset_for_tests


# Mirror of the FakeClient pattern in tests/api/unit/test_mcp_call_event.py
# (the only existing test that exercises call_mcp). Monkeypatching
# ``_common.httpx`` directly avoids the global httpx swap that trips up
# opentelemetry-instrumentation-httpx.
class _FakeResp:
    status_code = 200
    is_success = True
    text = ""

    def json(self) -> dict:
        return {"ok": True}


class _FakeClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json, timeout):
        return _FakeResp()


@pytest.fixture(autouse=True)
def _fresh_kernel():
    _reset_for_tests()
    yield
    _reset_for_tests()


# ---------------------------------------------------------------------------
# call_mcp chokepoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_mcp_records_decision_on_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``call_mcp`` invokes the kernel and stamps the decision onto the
    ``mcp.call`` event payload."""
    monkeypatch.delenv("AGT_ENFORCE", raising=False)
    from api.functions.graphs import _common

    monkeypatch.setattr(
        _common, "httpx", type("_", (), {"AsyncClient": _FakeClient})
    )
    emitted: list[dict] = []

    async def fake_emit(wid, iid, kind, payload):
        emitted.append({"wid": wid, "iid": iid, "kind": kind, "payload": payload})

    monkeypatch.setattr("api.functions.webhook.emit", fake_emit)

    result = await _common.call_mcp(
        "http://wd", "claim.lookup", {"limit": 5},
        workflow_id="WF-LOG-1", instance_id="inst-1",
    )
    assert result == {"ok": True}
    assert len(emitted) == 1
    payload = emitted[0]["payload"]
    gov = payload["governance"]
    assert gov["allowed"] is True
    assert gov["enforcement_mode"] == "log_only"
    assert gov["decision_id"]
    assert gov["policy_version"]
    assert gov["rule_id"] == "tool:claim.lookup"
    assert gov["actor"]


@pytest.mark.asyncio
async def test_call_mcp_does_not_raise_on_deny_in_log_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A kernel deny in log-only mode is recorded but not raised: the
    network hop still happens, the event still emits."""
    monkeypatch.delenv("AGT_ENFORCE", raising=False)
    from api.functions.graphs import _common

    monkeypatch.setattr(
        _common, "httpx", type("_", (), {"AsyncClient": _FakeClient})
    )
    emitted: list[dict] = []

    async def fake_emit(wid, iid, kind, payload):
        emitted.append(payload)

    monkeypatch.setattr("api.functions.webhook.emit", fake_emit)

    fake_decision = Decision(
        allowed=False,
        rule_id="tool:claim.lookup",
        action="deny",
        reason="forced deny for test",
        enforcement_mode="log_only",
        policy_version="abcdef012345",
    )
    with patch.object(kernel(), "evaluate_tool_call", return_value=fake_decision):
        result = await _common.call_mcp(
            "http://wd", "claim.lookup", {},
            workflow_id="WF-LOG-2",
        )
    assert result == {"ok": True}
    assert emitted
    gov = emitted[0]["governance"]
    assert gov["allowed"] is False
    assert gov["rule_id"] == "tool:claim.lookup"
    assert gov["enforcement_mode"] == "log_only"


@pytest.mark.asyncio
async def test_call_mcp_raises_in_enforce_on_deny(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the env flips to enforce AND the kernel says deny, the
    chokepoint raises before the network hop. No emit, no body."""
    monkeypatch.setenv("AGT_ENFORCE", "1")
    _reset_for_tests()  # rebuild kernel under enforce
    from api.functions.graphs import _common
    from api.server.services.governance import GovernanceDenied

    posts: list[tuple] = []

    class _BoomClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *e):
            return False

        async def post(self, url, json, timeout):
            posts.append((url, json))
            return _FakeResp()

    monkeypatch.setattr(
        _common, "httpx", type("_", (), {"AsyncClient": _BoomClient})
    )

    fake_decision = Decision(
        allowed=False,
        rule_id="tool:claim.lookup",
        action="deny",
        reason="capability gate",
        enforcement_mode="enforce",
        policy_version="abcdef012345",
    )
    with patch.object(kernel(), "evaluate_tool_call", return_value=fake_decision):
        with pytest.raises(GovernanceDenied):
            await _common.call_mcp(
                "http://wd", "claim.lookup", {},
                workflow_id="WF-ENFORCE-1",
            )
    assert posts == [], "network hop must not happen on enforce-deny"


# ---------------------------------------------------------------------------
# @traced_tool decorator chokepoint
# ---------------------------------------------------------------------------


def test_traced_tool_decorator_records_decision_and_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The decorator evaluates the kernel and runs the body. In log-only
    mode an injected deny decision still lets the body execute."""
    monkeypatch.delenv("AGT_ENFORCE", raising=False)
    from api.server.mcp_tools._otel import traced_tool

    calls: list[dict] = []

    @traced_tool("claim.lookup")
    def _impl(payload: dict) -> dict:
        calls.append(payload)
        return {"result_type": "success", "echo": payload}

    out = _impl({"q": "x"})
    assert out["echo"] == {"q": "x"}
    assert calls == [{"q": "x"}]

    fake_decision = Decision(
        allowed=False,
        rule_id="tool:claim.lookup",
        action="deny",
        reason="forced deny for test",
        enforcement_mode="log_only",
        policy_version="abcdef012345",
    )
    with patch.object(kernel(), "evaluate_tool_call", return_value=fake_decision):
        out2 = _impl({"q": "y"})
        assert out2["echo"] == {"q": "y"}
    assert {"q": "y"} in calls


def test_traced_tool_decorator_raises_in_enforce(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the kernel is in enforce mode AND returns a deny, the
    decorator raises ``GovernanceDenied`` before invoking the body."""
    monkeypatch.setenv("AGT_ENFORCE", "1")
    _reset_for_tests()

    from api.server.mcp_tools._otel import traced_tool
    from api.server.services.governance import GovernanceDenied

    calls: list[dict] = []

    @traced_tool("claim.lookup")
    def _impl(payload: dict) -> dict:
        calls.append(payload)
        return {"result_type": "success"}

    fake_decision = Decision(
        allowed=False,
        rule_id="tool:claim.lookup",
        action="deny",
        reason="capability gate",
        enforcement_mode="enforce",
        policy_version="abcdef012345",
    )
    with patch.object(kernel(), "evaluate_tool_call", return_value=fake_decision):
        with pytest.raises(GovernanceDenied) as excinfo:
            _impl({"q": "x"})
        assert excinfo.value.decision.rule_id == "tool:claim.lookup"
    assert calls == [], "body must not run when enforce-deny fires"
