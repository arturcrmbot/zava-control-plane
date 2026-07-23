import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from api.server.main import app
from api.server.state import app_state
from api.shared.types import (
    Workflow, Vendor, InvoiceData, McpCall, Exception_ as Exception,
)


def _seed(wid: str) -> None:
    app_state.store.upsert_workflow(Workflow(
        id=wid, created_at=time.time(), sla_due_at=time.time() + 3600,
        vendor=Vendor(id="V-1", name="Wayne Enterprises", country="US"),
        invoice=InvoiceData(number="INV-1", amount=12.0, currency="USD", po_ref="P"),
        jurisdiction="US", agency="Ogilvy-US",
    ))
    app_state.store.append_mcp_call(McpCall(
        workflow_id=wid, timestamp=time.time(),
        tool="getVendor", url="http://wd/mcp/call/getVendor",
        method="POST", request={"id": "V-1"}, response={},
        status_code=200, duration_ms=5,
    ))


def test_detail_response_includes_economics_and_mcpcalls() -> None:
    client = TestClient(app)
    _seed("W-DET-1")
    r = client.get("/api/workflows/W-DET-1")
    assert r.status_code == 200
    body = r.json()
    assert "economics" in body
    assert body["economics"]["toolCalls"] >= 1
    assert "mcpCalls" in body
    assert len(body["mcpCalls"]) >= 1
    assert body["mcpCalls"][0]["tool"] == "getVendor"


def test_detail_response_includes_narrative_when_exception_present() -> None:
    client = TestClient(app)
    wid = "W-DET-2"
    _seed(wid)
    exc = Exception(
        id="EXC-N", workflow_id=wid, composed_by="deterministic",
        severity="high", category="validator-blocked",
        summary="blocked test", recommendation="retry",
        confidence=1.0, created_at=time.time(),
    )
    app_state.store.upsert_exception(exc)
    r = client.get(f"/api/workflows/{wid}")
    assert r.status_code == 200
    body = r.json()
    assert "narrative" in body and body["narrative"] is not None
    assert "whatHappened" in body["narrative"]
    assert "whatAgentTried" in body["narrative"]


# ---------------------------------------------------------------------------
# Task 7 quality issue #2: `get_workflow`'s pack `workflow_detail_hook` call
# must not be wrapped in a broad `except Exception` that turns a genuine hook
# bug into a silent HTTP 200 with `packDetail: null`. A hook returning `None`
# is the ONE legitimate, truthful way to signal "no applicable detail" -- a
# hook that instead *raises* has a real bug that must propagate/surface
# explicitly, never be swallowed into the same success-shaped response.
# ---------------------------------------------------------------------------


class _SentinelHookBug(RuntimeError):
    """Distinguishes a genuine hook bug from any other exception the route
    or its dependencies might legitimately raise, so the assertion below is
    unambiguous about what it's proving."""


def test_pack_detail_is_none_when_hook_returns_none() -> None:
    """A hook that legitimately has no detail to add for this workflow type
    returns `None`; the route must expose this as a truthful `packDetail:
    null` (200 OK) -- this is the correct, non-buggy "absence" path and must
    keep working after issue #2's fix."""
    client = TestClient(app)
    wid = "W-DET-PACKHOOK-NONE"
    _seed(wid)
    previous_runtime = app_state.runtime
    try:
        app_state.runtime = SimpleNamespace(
            pack=SimpleNamespace(workflow_detail_hook=lambda workflow, state: None),
        )
        r = client.get(f"/api/workflows/{wid}")
    finally:
        app_state.runtime = previous_runtime
    assert r.status_code == 200
    assert r.json()["packDetail"] is None


def test_pack_detail_hook_bug_surfaces_instead_of_a_silent_200_null() -> None:
    """A hook that raises has a genuine bug -- the route must let that
    propagate (surfacing as a real error) rather than swallowing it into the
    same success-shaped `packDetail: null` response a legitimate absence
    would produce. Silently returning 200/null here would be
    indistinguishable from the correct "no detail" case and would hide a
    real regression from both callers and operators."""
    client = TestClient(app)
    wid = "W-DET-PACKHOOK-BUG"
    _seed(wid)
    previous_runtime = app_state.runtime

    def _buggy_hook(workflow, state):
        raise _SentinelHookBug("pack hook exploded")

    try:
        app_state.runtime = SimpleNamespace(
            pack=SimpleNamespace(workflow_detail_hook=_buggy_hook),
        )
        with pytest.raises(_SentinelHookBug, match="pack hook exploded"):
            client.get(f"/api/workflows/{wid}")
    finally:
        app_state.runtime = previous_runtime
