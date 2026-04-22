# Apex Control Plane Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retrofit the Apex visual language (WPPET-4 slides 9–11) onto the existing Finance P2P POC1 backend. Three screens (Dashboard / Workflow Detail / Execution Timeline) rendered against real pipeline events, with light theme + narrative exception analysis + named intervention protocols + derived economics.

**Architecture:** Backend gains four small services (MCP event instrumentation, economics derivation, narrative assembler, intervention-protocol enrichment). Frontend switches to light theme, adds 12 small components under `components/apex/`, rebuilds Dashboard and Workflow Detail. Every value on screen derives from a real event. Fork / Rollback are log-only stubs.

**Tech Stack:** FastAPI + Pydantic + Azure Durable Functions + React 19 + Vite + Tailwind + Playwright.

**Spec:** `docs/superpowers/specs/2026-04-23-apex-control-plane-redesign.md`

---

## File Structure

**Python (backend) — new:**
- `api/server/services/economics.py` — derive per-workflow cost / model calls / tool calls.
- `api/server/services/exception_narrative.py` — template-driven Exception Analysis narrative.
- `api/server/routes/fleet.py` — `GET /api/fleet/economics` aggregate endpoint.

**Python (backend) — modified:**
- `api/shared/types.py` — add `McpCall` type; add `recommended` field on `ExceptionOption`.
- `api/server/services/state_store.py` — add `_mcp_calls` storage + getters/setters.
- `api/server/services/exception_factory.py` — emit enriched Finance-flavored option sets.
- `api/functions/graphs/_common.py` — instrument `call_mcp` to emit `mcp.call` events.
- `api/functions/graphs/executors/deterministic/*.py` — pass `workflow_id` / `instance_id` into `call_mcp` (~10 files, mechanical).
- `api/server/routes/internal_durable_event.py` — handle `kind == "mcp.call"`.
- `api/server/routes/workflows.py` — return `economics`, `narrative`, `mcpCalls` on detail response.
- `api/server/routes/exceptions.py` — accept extended `action` enum values.
- `api/server/main.py` — register the new `fleet` router.

**React (frontend) — new under `web/client/components/apex/`:**
- `PhaseRibbon.tsx`, `WorkflowHeaderTiles.tsx`, `ExceptionAnalysisCard.tsx`, `InterventionProtocols.tsx`, `EconomicsPanel.tsx`, `FleetAssignment.tsx`, `AuditTrail.tsx`, `ExecutionTimelineTab.tsx`, `ExceptionCardCompact.tsx`, `KpiTileRow.tsx`, `FleetEconomicsPanel.tsx`, `PolicyAutonomyPanel.tsx`.

**React (frontend) — modified:**
- `web/client/styles.css` — light theme palette swap.
- `web/client/App.tsx` — Apex shell chrome (top bar + left nav).
- `web/client/routes/WorkflowDetail.tsx` — Overview tab composes Apex components; Orchestration tab replaced with Execution Timeline.
- `web/client/routes/FleetDashboard.tsx` — Apex Dashboard layout.
- `web/shared/types.ts` — `McpCall`, `Economics`, `Narrative`, `ExceptionOption.recommended`, `WorkflowDetail` response shape.

**Tests:**
- `tests/e2e/smoke.spec.ts` — 8 new tests.
- `tests/api/unit/test_economics.py` — new.
- `tests/api/unit/test_exception_narrative.py` — new.
- `tests/api/unit/test_mcp_call_event.py` — new.

---

### Task 1: McpCall type + store plumbing

**Files:**
- Modify: `api/shared/types.py`
- Modify: `api/server/services/state_store.py`
- Test: `tests/api/unit/test_mcp_call_event.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/unit/test_mcp_call_event.py
from api.server.services.state_store import StateStore
from api.shared.types import McpCall


def test_append_and_get_mcp_calls() -> None:
    store = StateStore()
    call = McpCall(
        workflow_id="W-1", timestamp=1.0,
        tool="getVendor", url="http://x/mcp/call/getVendor",
        method="POST", request={"vendorId": "V-1"},
        response={"id": "V-1"}, status_code=200, duration_ms=42,
    )
    store.append_mcp_call(call)
    got = store.get_mcp_calls("W-1")
    assert len(got) == 1
    assert got[0].tool == "getVendor"
    assert got[0].status_code == 200
    # workflow isolation
    assert store.get_mcp_calls("W-2") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_mcp_call_event.py -v`
Expected: FAIL — `McpCall` / `append_mcp_call` missing.

- [ ] **Step 3: Add `McpCall` to `src/shared/types.py`** (insert after the existing `OtelSpan` class):

```python
class McpCall(BaseModel):
    workflow_id: str
    timestamp: float
    tool: str
    url: str
    method: str = "POST"
    request: dict
    response: dict
    status_code: int
    duration_ms: int
```

- [ ] **Step 4: Add store plumbing in `state_store.py`**

In the constructor `__init__` add:

```python
self._mcp_calls: dict[str, list[McpCall]] = {}
```

Add the import at the top near other type imports:

```python
from api.shared.types import (  # existing imports...
    McpCall,
)
```

Add two methods next to `append_span` / `get_spans`:

```python
def append_mcp_call(self, c: McpCall) -> None:
    self._mcp_calls.setdefault(c.workflow_id, []).append(c)

def get_mcp_calls(self, workflow_id: str) -> list[McpCall]:
    return self._mcp_calls.get(workflow_id, [])
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_mcp_call_event.py -v`
Expected: 1 passed.

- [ ] **Step 6: Run full test suite — no regressions**

Run: `uv run pytest -q`
Expected: all passing.

- [ ] **Step 7: Commit**

```bash
cd "c:/dev/ghcp sdk stuff"
git add api/shared/types.py api/server/services/state_store.py tests/api/unit/test_mcp_call_event.py
git commit -m "feat(types): add McpCall + state store plumbing for MCP-call events"
```

---

### Task 2: Instrument `call_mcp` to emit webhook event

**Files:**
- Modify: `api/functions/graphs/_common.py`
- Test: extend `tests/api/unit/test_mcp_call_event.py`

- [ ] **Step 1: Write the failing test (append to existing file)**

```python
# Append to tests/api/unit/test_mcp_call_event.py
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_call_mcp_emits_webhook(monkeypatch) -> None:
    from api.functions.graphs import _common

    # Fake httpx.AsyncClient: returns a dummy 200 response.
    class FakeResp:
        status_code = 200
        is_success = True
        text = ""
        def json(self): return {"id": "V-1"}

    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json, timeout): return FakeResp()

    monkeypatch.setattr(_common, "httpx", type("_", (), {"AsyncClient": FakeClient}))

    emitted: list[dict] = []
    async def fake_emit(wid, iid, kind, payload):
        emitted.append({"wid": wid, "iid": iid, "kind": kind, "payload": payload})
    monkeypatch.setattr("src.functions.webhook.emit", fake_emit)

    result = await _common.call_mcp(
        "http://mcp", "getVendor", {"vendorId": "V-1"},
        workflow_id="W-1", instance_id="I-1",
    )
    assert result == {"id": "V-1"}
    assert len(emitted) == 1
    e = emitted[0]
    assert e["kind"] == "mcp.call"
    assert e["wid"] == "W-1"
    assert e["payload"]["tool"] == "getVendor"
    assert e["payload"]["status_code"] == 200
    assert e["payload"]["method"] == "POST"
    assert e["payload"]["request"] == {"vendorId": "V-1"}
    assert "duration_ms" in e["payload"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_mcp_call_event.py::test_call_mcp_emits_webhook -v`
Expected: FAIL — `call_mcp` does not accept `workflow_id`.

- [ ] **Step 3: Rewrite `call_mcp` in `src/functions/graphs/_common.py`**

Replace the function's body with:

```python
# src/functions/graphs/_common.py
from __future__ import annotations
import time
import httpx


async def call_mcp(
    base_url: str,
    tool: str,
    args: dict,
    workflow_id: str | None = None,
    instance_id: str | None = None,
) -> dict:
    """POST to an MCP endpoint. Emits a durable `mcp.call` event with the
    request, response, status, and duration when `workflow_id` is provided
    so the UI's Execution Timeline can render per-call step cards."""
    url = f"{base_url}/mcp/call/{tool}"
    t0 = time.time()
    resp_json: dict
    status_code: int
    async with httpx.AsyncClient() as c:
        try:
            r = await c.post(url, json=args, timeout=10)
            status_code = r.status_code
            resp_json = r.json() if r.is_success else {"error": r.text}
        except Exception as ex:  # network / timeout
            resp_json = {"error": str(ex)}
            status_code = 599
    duration_ms = int((time.time() - t0) * 1000)

    if workflow_id is not None:
        # Local import avoids circular deps during module load.
        from api.functions.webhook import emit
        await emit(workflow_id, instance_id, "mcp.call", {
            "tool": tool, "url": url, "method": "POST",
            "request": args, "response": resp_json,
            "status_code": status_code, "duration_ms": duration_ms,
        })

    if status_code >= 400:
        raise RuntimeError(f"mcp {tool} failed: {status_code}")
    return resp_json
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_mcp_call_event.py -v`
Expected: both tests pass.

- [ ] **Step 5: Commit**

```bash
git add api/functions/graphs/_common.py tests/api/unit/test_mcp_call_event.py
git commit -m "feat(mcp): instrument call_mcp to emit mcp.call durable events"
```

---

### Task 3: Pass `workflow_id` from deterministic executors

**Files (modify all that call `call_mcp`):**
- `api/functions/graphs/executors/deterministic/lookup_vendor_context.py`
- `api/functions/graphs/executors/deterministic/lookup_active_gls.py`
- `api/functions/graphs/executors/deterministic/lookup_cost_centre_policy.py`
- `api/functions/graphs/executors/deterministic/doc_intelligence_extract.py`
- `api/functions/graphs/executors/deterministic/three_way_match.py`
- `api/functions/graphs/executors/deterministic/generate_payment_file.py`
- `api/functions/graphs/executors/deterministic/submit_payment.py`
- `api/functions/graphs/executors/deterministic/bank_statement_match.py`
- `api/functions/graphs/executors/deterministic/load_authority_policy.py`

- [ ] **Step 1: Identify every caller**

Run: `grep -rn "call_mcp(" api/functions/graphs/executors/deterministic/`
Expected: a small set of one-line call sites per file, each receiving `input: dict` in its `execute` function.

- [ ] **Step 2: Update each call site to pass `workflow_id` + `instance_id`**

Example for `lookup_vendor_context.py` — change this:

```python
v = await call_mcp(WORKDAY_URL, "getVendor", {"vendorId": vendor_id})
```

To:

```python
v = await call_mcp(
    WORKDAY_URL, "getVendor", {"vendorId": vendor_id},
    workflow_id=input.get("workflow_id"),
    instance_id=input.get("instance_id"),
)
```

Repeat in every listed file, passing through `input.get("workflow_id")` / `input.get("instance_id")` from the `execute(input: dict)` arg.

- [ ] **Step 3: Verify unit tests still pass**

Run: `uv run pytest -q`
Expected: same pass count as before.

- [ ] **Step 4: Commit**

```bash
git add api/functions/graphs/executors/deterministic/
git commit -m "feat(mcp): thread workflow_id through deterministic executor MCP calls"
```

---

### Task 4: Route `mcp.call` kind into the store

**Files:**
- Modify: `api/server/routes/internal_durable_event.py`
- Test: add unit test under `tests/api/unit/test_internal_durable_event.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# tests/api/unit/test_internal_durable_event.py
from fastapi.testclient import TestClient
from api.server.main import app


def test_mcp_call_event_appends_to_store() -> None:
    client = TestClient(app)
    r = client.post("/internal/durable-event", json={
        "workflow_id": "W-T1",
        "instance_id": "I-T1",
        "kind": "mcp.call",
        "payload": {
            "tool": "getVendor",
            "url": "http://wd/mcp/call/getVendor",
            "method": "POST",
            "request": {"vendorId": "V-1"},
            "response": {"id": "V-1"},
            "status_code": 200,
            "duration_ms": 11,
        },
    })
    assert r.status_code == 200
    from api.server.state import app_state
    calls = app_state.store.get_mcp_calls("W-T1")
    assert len(calls) == 1
    assert calls[0].tool == "getVendor"
    assert calls[0].response == {"id": "V-1"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_internal_durable_event.py -v`
Expected: FAIL — no mcp.call handling.

- [ ] **Step 3: Add handler branch in `internal_durable_event.py`**

After the existing `elif body.kind == "executor.invoked":` branch, add:

```python
elif body.kind == "mcp.call":
    p = body.payload
    app_state.store.append_mcp_call(McpCall(
        workflow_id=wid,
        timestamp=now,
        tool=p.get("tool", "?"),
        url=p.get("url", ""),
        method=p.get("method", "POST"),
        request=p.get("request", {}),
        response=p.get("response", {}),
        status_code=int(p.get("status_code", 0)),
        duration_ms=int(p.get("duration_ms", 0)),
    ))
```

Add the import at the top (beside the existing `Phase, OtelSpan, ActionLedgerEntry`):

```python
from api.shared.types import Phase, OtelSpan, ActionLedgerEntry, McpCall
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_internal_durable_event.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add api/server/routes/internal_durable_event.py tests/api/unit/test_internal_durable_event.py
git commit -m "feat(events): handle kind=mcp.call; append to store"
```

---

### Task 5: Economics derivation service

**Files:**
- Create: `api/server/services/economics.py`
- Test: `tests/api/unit/test_economics.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/unit/test_economics.py
import time
from api.shared.types import Workflow, OtelSpan, McpCall, Vendor, InvoiceData
from api.server.services.economics import compute


def _wf(wid: str, age_s: float = 100.0) -> Workflow:
    return Workflow(
        id=wid, created_at=time.time() - age_s, sla_due_at=time.time() + 3600,
        vendor=Vendor(id="V-1", name="Vendor", country="US"),
        invoice=InvoiceData(number="N", amount=1.0, currency="USD", po_ref="P"),
        jurisdiction="US", agency="Ag-1",
    )


def test_compute_with_no_activity() -> None:
    w = _wf("W-1", age_s=0.0)
    eco = compute(w, spans=[], mcp_calls=[])
    assert eco["modelCalls"] == 0
    assert eco["toolCalls"] == 0
    assert eco["computeCostUsd"] == 0.0
    assert eco["slaToken"].startswith("SLA-")
    assert eco["daysElapsed"] >= 0.0


def test_compute_accumulates_agent_and_tool_counts() -> None:
    w = _wf("W-2")
    spans = [
        OtelSpan(trace_id="t", span_id=f"s{i}", name="executor.a", start_ms=0, end_ms=1000,
                 attributes={"workflow.id": "W-2", "executor.type": "agent"})
        for i in range(3)
    ] + [
        OtelSpan(trace_id="t", span_id=f"d{i}", name="executor.d", start_ms=0, end_ms=500,
                 attributes={"workflow.id": "W-2", "executor.type": "deterministic"})
        for i in range(2)
    ]
    calls = [
        McpCall(workflow_id="W-2", timestamp=0, tool="t", url="u",
                method="POST", request={}, response={}, status_code=200, duration_ms=5)
        for _ in range(4)
    ]
    eco = compute(w, spans=spans, mcp_calls=calls)
    assert eco["modelCalls"] == 3
    assert eco["toolCalls"] == 4
    assert eco["computeCostUsd"] > 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_economics.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Create `economics.py`**

```python
# api/server/services/economics.py
from __future__ import annotations
import hashlib
import time
from api.shared.types import Workflow, OtelSpan, McpCall


COMPUTE_RATE_PER_SECOND = 0.0001   # $ per second of executor wall-clock
MODEL_CALL_RATE = 0.02             # $ per agent executor invocation


def compute(workflow: Workflow, *, spans: list[OtelSpan],
            mcp_calls: list[McpCall]) -> dict:
    model_calls = sum(
        1 for s in spans if s.attributes.get("executor.type") == "agent"
    )
    tool_calls = len(mcp_calls)
    executor_seconds = sum(max(0.0, s.end_ms - s.start_ms) for s in spans) / 1000.0
    compute_usd = (
        executor_seconds * COMPUTE_RATE_PER_SECOND
        + model_calls * MODEL_CALL_RATE
    )
    days_elapsed = max(0.0, (time.time() - workflow.created_at) / 86400.0)
    sla_token = "SLA-" + hashlib.sha256(workflow.id.encode()).hexdigest()[:4].upper()
    return {
        "computeCostUsd": round(compute_usd, 2),
        "modelCalls": model_calls,
        "toolCalls": tool_calls,
        "daysElapsed": round(days_elapsed, 2),
        "slaToken": sla_token,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_economics.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add api/server/services/economics.py tests/api/unit/test_economics.py
git commit -m "feat(economics): derive per-workflow cost/calls/days from events"
```

---

### Task 6: Exception Narrative service

**Files:**
- Create: `api/server/services/exception_narrative.py`
- Test: `tests/api/unit/test_exception_narrative.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/unit/test_exception_narrative.py
import time
from api.shared.types import (
    Workflow, Vendor, InvoiceData, ActionLedgerEntry, Exception_ as Exception
)
from api.server.services.exception_narrative import compose


def _wf() -> Workflow:
    return Workflow(
        id="INV-0001", created_at=time.time(), sla_due_at=time.time() + 3600,
        vendor=Vendor(id="V-1", name="Wayne Enterprises", country="US"),
        invoice=InvoiceData(number="INV-980444", amount=12529.88,
                            currency="USD", po_ref="PO-10004"),
        jurisdiction="US", agency="Ogilvy-US", current_phase="Routing",
    )


def _exc(category: str) -> Exception:
    return Exception(
        id="EXC-1", workflow_id="INV-0001", composed_by="deterministic",
        severity="high", category=category,  # type: ignore[arg-type]
        summary="Validator 'validate_gl_active' blocked workflow",
        recommendation="Re-route to a GL specialist",
        confidence=1.0, created_at=time.time(),
    )


def test_compose_validator_blocked() -> None:
    w = _wf()
    exc = _exc("validator-blocked")
    ledger = [
        ActionLedgerEntry(workflow_id=w.id, timestamp=time.time(),
                          actor_kind="agent", actor_id="phase:Intake",
                          action="phase.completed:Intake", revocable=False, details={}),
        ActionLedgerEntry(workflow_id=w.id, timestamp=time.time(),
                          actor_kind="agent", actor_id="validator:validate_gl_active",
                          action="validator.blocked", revocable=False,
                          details={"reason": "GL-9999 not in active set"}),
    ]
    n = compose(w, exc, ledger)
    assert "Wayne Enterprises" in n["whatHappened"]
    assert "12,529.88" in n["whatHappened"] or "12529.88" in n["whatHappened"]
    assert len(n["whatAgentTried"]) >= 1
    assert "GL specialist" in n["agentRecommendation"] or \
           "Re-route" in n["agentRecommendation"]


def test_compose_threshold_exceeded() -> None:
    w = _wf()
    exc = _exc("threshold-exceeded")
    exc.summary = "Amount exceeds threshold for Ogilvy-US"
    exc.recommendation = "Escalate to L2 approver"
    n = compose(w, exc, ledger=[])
    assert n["whatHappened"]
    assert isinstance(n["whatAgentTried"], list)
    assert "L2" in n["agentRecommendation"] or "Escalate" in n["agentRecommendation"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_exception_narrative.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Create `exception_narrative.py`**

```python
# api/server/services/exception_narrative.py
from __future__ import annotations
from api.shared.types import Workflow, Exception_ as Exception, ActionLedgerEntry


def _fmt_amount(amount: float, currency: str) -> str:
    return f"{currency} {amount:,.2f}"


def _agent_tried(ledger: list[ActionLedgerEntry], limit: int = 5) -> list[str]:
    """Prefer the most recent N agent-kind ledger actions, rendered as prose."""
    recent = [e for e in ledger if e.actor_kind == "agent"][-limit:]
    if not recent:
        return ["Orchestration started; no executor actions recorded yet."]
    bullets: list[str] = []
    for e in recent:
        if e.action.startswith("phase.completed:"):
            phase = e.action.split(":", 1)[1]
            bullets.append(f"{phase} phase completed")
        elif e.action == "validator.blocked":
            reason = e.details.get("reason", "validation failed")
            who = e.actor_id.replace("validator:", "")
            bullets.append(f"{who} rejected: {reason}")
        elif e.action == "suspended":
            bullets.append(
                f"Workflow suspended for HITL: "
                f"{e.details.get('reason', 'approval')}"
            )
        else:
            bullets.append(e.action)
    return bullets


def compose(workflow: Workflow, exception: Exception,
            ledger: list[ActionLedgerEntry]) -> dict:
    inv = workflow.invoice
    phase = workflow.current_phase
    amount_str = _fmt_amount(inv.amount, inv.currency)
    vendor = workflow.vendor.name

    if exception.category == "validator-blocked":
        what_happened = (
            f"Invoice {inv.number} for {vendor} ({amount_str}) blocked at "
            f"{phase}: {exception.summary}."
        )
    elif exception.category == "threshold-exceeded":
        what_happened = (
            f"Invoice {inv.number} for {vendor} ({amount_str}) requires "
            f"human approval at {phase}: {exception.summary}."
        )
    else:
        what_happened = (
            f"Invoice {inv.number} for {vendor} ({amount_str}) exception "
            f"raised at {phase}: {exception.summary}."
        )

    return {
        "whatHappened": what_happened,
        "whatAgentTried": _agent_tried(ledger),
        "agentRecommendation": exception.recommendation or
            "Review exception and select an Intervention Protocol.",
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_exception_narrative.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add api/server/services/exception_narrative.py tests/api/unit/test_exception_narrative.py
git commit -m "feat(narrative): Exception Analysis assembler (template-driven)"
```

---

### Task 7: Extend `ExceptionOption` + enrich factory options

**Files:**
- Modify: `api/shared/types.py`
- Modify: `api/server/services/exception_factory.py`
- Test: extend `tests/api/unit/test_exception_factory.py` (existing)

- [ ] **Step 1: Write the failing test (append to existing file)**

```python
# Append to tests/api/unit/test_exception_factory.py
from api.server.services.state_store import StateStore
from api.server.services.exception_factory import (
    compose_validator_exception, compose_hitl_exception
)


def test_validator_exception_has_recommended_reroute_option() -> None:
    store = StateStore()
    e = compose_validator_exception(store, "W-X",
                                    validator="validate_gl_active",
                                    reason="GL-9999 not active")
    actions = {(o.action, o.recommended) for o in e.options}
    # at least these named protocols must exist
    assert any(a == "reroute-gl" for a, _ in actions)
    assert any(a == "escalate" for a, _ in actions)
    # the re-route should be flagged as recommended
    assert ("reroute-gl", True) in actions


def test_hitl_exception_has_approve_recommended() -> None:
    store = StateStore()
    e = compose_hitl_exception(store, "W-Y", reason="amount > threshold")
    actions = {(o.action, o.recommended) for o in e.options}
    assert ("approve", True) in actions
    assert any(a == "escalate" for a, _ in actions)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_exception_factory.py -v`
Expected: the two new tests FAIL (`recommended` attribute missing and / or actions missing).

- [ ] **Step 3: Add `recommended` to `ExceptionOption` in `src/shared/types.py`**

Locate the `ExceptionOption` class and add the field:

```python
class ExceptionOption(BaseModel):
    label: str
    action: str
    non_revocable: bool = False
    recommended: bool = False   # NEW
```

- [ ] **Step 4: Rewrite option sets in `exception_factory.py`**

Replace the `options=[...]` section in `compose_validator_exception` with:

```python
options=[
    ExceptionOption(label="Re-route to GL specialist", action="reroute-gl",
                    recommended=True),
    ExceptionOption(label="Approve override", action="approve",
                    non_revocable=True),
    ExceptionOption(label="Request vendor info", action="request-info"),
    ExceptionOption(label="Escalate to CFO", action="escalate"),
    ExceptionOption(label="Reject", action="reject", non_revocable=True),
],
```

Replace the options in `compose_hitl_exception` with:

```python
options=[
    ExceptionOption(label="Approve", action="approve",
                    recommended=True, non_revocable=True),
    ExceptionOption(label="Request additional docs", action="request-info"),
    ExceptionOption(label="Escalate to approver L2", action="escalate"),
    ExceptionOption(label="Reject", action="reject", non_revocable=True),
],
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_exception_factory.py -v`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add api/shared/types.py api/server/services/exception_factory.py tests/api/unit/test_exception_factory.py
git commit -m "feat(exceptions): add recommended flag + finance-flavored Intervention Protocol options"
```

---

### Task 8: Extend bulk-resolve to accept new action strings

**Files:**
- Modify: `api/server/routes/exceptions.py`
- Test: extend `tests/api/unit/test_internal_durable_event.py` (or new `test_bulk_resolve.py`)

- [ ] **Step 1: Write the failing test**

```python
# tests/api/unit/test_bulk_resolve.py
import time
from fastapi.testclient import TestClient
from api.server.main import app
from api.server.state import app_state
from api.shared.types import Exception_ as Exception, ExceptionOption


def test_bulk_resolve_accepts_reroute_gl_action() -> None:
    client = TestClient(app)
    # seed an exception
    e = Exception(
        id="EXC-R1", workflow_id="W-R1", composed_by="deterministic",
        severity="high", category="validator-blocked",
        summary="s", recommendation="r", confidence=1.0, created_at=time.time(),
        options=[ExceptionOption(label="Re-route", action="reroute-gl",
                                 recommended=True)],
    )
    app_state.store.upsert_exception(e)
    r = client.post("/api/exceptions/bulk-resolve", json={
        "exceptionIds": ["EXC-R1"],
        "resolution": "reroute-gl",
        "resolvedBy": "controller@wpp",
    })
    assert r.status_code == 200, r.text
    assert r.json()["resolved"] == 1
    # open list should be empty for this workflow
    assert app_state.store.get_exception("EXC-R1").resolved_at is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_bulk_resolve.py -v`
Expected: FAIL — `resolution` `Literal` rejects `reroute-gl`.

- [ ] **Step 3: Loosen the Literal in `BulkResolveBody`**

In `api/server/routes/exceptions.py`, change:

```python
resolution: Literal["approve", "reject", "escalate"]
```

To:

```python
resolution: Literal[
    "approve", "reject", "escalate",
    "reroute-gl", "request-info",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_bulk_resolve.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add api/server/routes/exceptions.py tests/api/unit/test_bulk_resolve.py
git commit -m "feat(exceptions): accept reroute-gl/request-info resolutions on bulk-resolve"
```

---

### Task 9: Workflow detail response injects economics, narrative, mcpCalls

**Files:**
- Modify: `api/server/routes/workflows.py`
- Test: extend `tests/api/unit/test_internal_durable_event.py` or new

- [ ] **Step 1: Write the failing test**

```python
# tests/api/unit/test_workflow_detail_response.py
import time
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_workflow_detail_response.py -v`
Expected: FAIL — `economics` / `mcpCalls` / `narrative` not in response.

- [ ] **Step 3: Update `workflows.py`**

Replace the body of `get_workflow` with:

```python
# api/server/routes/workflows.py
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from api.server.state import app_state
from api.server.services import economics, exception_narrative

router = APIRouter(prefix="/api/workflows")


@router.get("/")
async def list_workflows(status: str | None = None, phase: str | None = None,
                         agency: str | None = None,
                         has_exception: bool | None = None):
    items = app_state.store.list_workflows(
        status=status, phase=phase, agency=agency, has_exception=has_exception,
    )
    return [w.model_dump(by_alias=True) for w in items]


@router.get("/{id}")
async def get_workflow(id: str):
    w = app_state.store.get_workflow(id)
    if not w:
        raise HTTPException(404)
    active = (
        app_state.store.get_exception(w.active_exception_id)
        if w.active_exception_id else None
    )
    spans = app_state.store.get_spans(id)
    mcp_calls = app_state.store.get_mcp_calls(id)
    eco = economics.compute(w, spans=spans, mcp_calls=mcp_calls)
    narrative = (
        exception_narrative.compose(w, active, w.action_ledger)
        if active else None
    )
    return {
        "workflow": w.model_dump(by_alias=True),
        "phases": [p.model_dump(by_alias=True)
                   for p in app_state.store.get_phases(id)],
        "spans": [s.model_dump(by_alias=True) for s in spans],
        "amplifications": [a.model_dump(by_alias=True)
                           for a in app_state.store.get_amplifications(id)],
        "activeException": active.model_dump(by_alias=True) if active else None,
        "mcpCalls": [c.model_dump(by_alias=True) for c in mcp_calls],
        "economics": eco,
        "narrative": narrative,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_workflow_detail_response.py -v`
Expected: both tests pass.

- [ ] **Step 5: Commit**

```bash
git add api/server/routes/workflows.py tests/api/unit/test_workflow_detail_response.py
git commit -m "feat(workflows): inject economics/narrative/mcpCalls into detail response"
```

---

### Task 10: Fleet economics aggregate endpoint

**Files:**
- Create: `api/server/routes/fleet.py`
- Modify: `api/server/main.py`
- Test: `tests/api/unit/test_fleet_economics.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/unit/test_fleet_economics.py
import time
from fastapi.testclient import TestClient
from api.server.main import app
from api.server.state import app_state
from api.shared.types import Workflow, Vendor, InvoiceData, OtelSpan


def _wf(wid: str, status: str = "in_progress") -> Workflow:
    return Workflow(
        id=wid, status=status,  # type: ignore[arg-type]
        created_at=time.time(), sla_due_at=time.time() + 3600,
        vendor=Vendor(id="V", name="V", country="US"),
        invoice=InvoiceData(number="N", amount=1.0, currency="USD", po_ref="P"),
        jurisdiction="US", agency="Ag",
    )


def test_fleet_economics_endpoint_rolls_up_active_only() -> None:
    # two active, one completed
    app_state.store.upsert_workflow(_wf("F-1"))
    app_state.store.upsert_workflow(_wf("F-2", status="awaiting_hitl"))
    app_state.store.upsert_workflow(_wf("F-3", status="completed"))
    for wid in ("F-1", "F-2", "F-3"):
        app_state.store.append_span(OtelSpan(
            trace_id=wid, span_id="s", name="executor.a",
            start_ms=0, end_ms=1000,
            attributes={"workflow.id": wid, "executor.type": "agent"},
        ))
    r = TestClient(app).get("/api/fleet/economics")
    assert r.status_code == 200
    body = r.json()
    # active workflows contribute (F-1 + F-2); completed (F-3) excluded
    assert body["activeWorkflowCount"] == 2
    assert body["totalModelCalls"] == 2
    assert body["totalComputeCostUsd"] > 0.0
    assert body["averageCostPerWorkflow"] == \
        round(body["totalComputeCostUsd"] / 2, 2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_fleet_economics.py -v`
Expected: FAIL — endpoint not mounted.

- [ ] **Step 3: Create `fleet.py`**

```python
# api/server/routes/fleet.py
from __future__ import annotations
from fastapi import APIRouter
from api.server.state import app_state
from api.server.services import economics

router = APIRouter(prefix="/api/fleet")


@router.get("/economics")
async def fleet_economics():
    active_states = {"in_progress", "awaiting_hitl"}
    active = [w for w in app_state.store.list_workflows()
              if w.status in active_states]
    totals = {"cost": 0.0, "model": 0, "tool": 0}
    for w in active:
        eco = economics.compute(
            w,
            spans=app_state.store.get_spans(w.id),
            mcp_calls=app_state.store.get_mcp_calls(w.id),
        )
        totals["cost"] += eco["computeCostUsd"]
        totals["model"] += eco["modelCalls"]
        totals["tool"] += eco["toolCalls"]
    n = max(1, len(active))
    return {
        "activeWorkflowCount": len(active),
        "totalComputeCostUsd": round(totals["cost"], 2),
        "totalModelCalls": totals["model"],
        "totalToolCalls": totals["tool"],
        "averageCostPerWorkflow": round(totals["cost"] / n, 2),
    }
```

- [ ] **Step 4: Register router in `main.py`**

In `api/server/main.py`, add alongside existing router registrations:

```python
from api.server.routes import fleet as fleet_routes
# ... app.include_router(...) lines:
app.include_router(fleet_routes.router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_fleet_economics.py -v`
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add api/server/routes/fleet.py api/server/main.py tests/api/unit/test_fleet_economics.py
git commit -m "feat(fleet): GET /api/fleet/economics rollup of active workflows"
```

---

### Task 11: TS shared types for new response fields

**Files:**
- Modify: `web/shared/types.ts`

- [ ] **Step 1: Add new type declarations**

At the end of `web/shared/types.ts` append:

```ts
export interface McpCall {
  workflowId: string;
  timestamp: number;
  tool: string;
  url: string;
  method: string;
  request: Record<string, unknown>;
  response: Record<string, unknown>;
  statusCode: number;
  durationMs: number;
}

export interface Economics {
  computeCostUsd: number;
  modelCalls: number;
  toolCalls: number;
  daysElapsed: number;
  slaToken: string;
}

export interface Narrative {
  whatHappened: string;
  whatAgentTried: string[];
  agentRecommendation: string;
}

export interface FleetEconomics {
  activeWorkflowCount: number;
  totalComputeCostUsd: number;
  totalModelCalls: number;
  totalToolCalls: number;
  averageCostPerWorkflow: number;
}
```

Locate `ExceptionOption` and add `recommended?: boolean;`:

```ts
export interface ExceptionOption {
  label: string;
  action: string;
  nonRevocable?: boolean;
  recommended?: boolean;   // NEW
}
```

Locate the workflow-detail response interface (the one with `workflow`, `phases`, `spans`, ...) and extend with `mcpCalls`, `economics`, `narrative`:

```ts
export interface WorkflowDetail {
  workflow: Workflow;
  phases: Phase[];
  spans: OtelSpan[];
  amplifications: SkillAmplification[];
  activeException: Exception | null;
  mcpCalls: McpCall[];
  economics: Economics;
  narrative: Narrative | null;
}
```

(If the existing file uses an inline type at the fetch site, add this interface and then update callers in later tasks to use it.)

- [ ] **Step 2: Verify TS still compiles**

Run: `npm run build 2>&1 | tail -5`
Expected: a clean build (may show existing unused-local warnings, but no errors). If errors about `Workflow` / `Phase` / `OtelSpan` / `SkillAmplification` / `Exception` come up, add missing `import` / keep references to whatever names already exist in the file.

- [ ] **Step 3: Commit**

```bash
git add web/shared/types.ts
git commit -m "feat(types): TS shapes for McpCall, Economics, Narrative, FleetEconomics"
```

---

### Task 12: Light theme CSS + top-level background swap

**Files:**
- Modify: `web/client/styles.css`
- Modify: `index.html` (body class)

- [ ] **Step 1: Replace `styles.css` with the Apex light palette**

Full contents of `web/client/styles.css`:

```css
@import "tailwindcss";

:root {
  color-scheme: light;
}

html, body, #root {
  height: 100%;
}

body {
  @apply bg-slate-50 text-slate-900 font-sans antialiased;
}

/* Reusable surface utility for card-like panels */
.panel {
  @apply bg-white border border-slate-200 rounded-lg shadow-sm;
}

.panel-header {
  @apply px-4 py-3 border-b border-slate-200 text-sm font-semibold text-slate-800;
}

.panel-body {
  @apply p-4;
}

/* Buttons */
.btn-primary {
  @apply inline-flex items-center gap-2 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:opacity-40;
}
.btn-secondary {
  @apply inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40;
}
.btn-danger {
  @apply inline-flex items-center gap-2 rounded-md border border-red-300 bg-white px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-50;
}

/* Status chips */
.chip-success { @apply inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700 border border-emerald-200; }
.chip-warning { @apply inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700 border border-amber-200; }
.chip-danger  { @apply inline-flex items-center gap-1 rounded-full bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700 border border-red-200; }
.chip-info    { @apply inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700 border border-blue-200; }
```

- [ ] **Step 2: Update `index.html` body class (if needed)**

Ensure `index.html`'s `<body>` tag does **not** carry a hard-coded dark class. If it does (e.g. `class="bg-slate-950 text-slate-100"`), remove those classes so CSS wins.

- [ ] **Step 3: Build UI + verify visually**

Run: `npm run build 2>&1 | tail -5`
Expected: build succeeds.

Start preview if not running:
Run: `npm run demo:ui &`

Open http://localhost:5173 — page background is off-white; existing text is legible dark-on-light. Many component-level `bg-slate-900` / `text-slate-*` classes will still render darkly in places; later tasks replace them per-component.

- [ ] **Step 4: Commit**

```bash
git add web/client/styles.css index.html
git commit -m "feat(theme): Apex light palette base + panel/chip/button utilities"
```

---

### Task 13: `PhaseRibbon` component

**Files:**
- Create: `web/client/components/apex/PhaseRibbon.tsx`

- [ ] **Step 1: Create the component**

```tsx
// web/client/components/apex/PhaseRibbon.tsx
import { PHASE_ORDER, type Phase, type Workflow } from "@shared/types";
import { Check, Loader2, Ban, CircleDashed } from "lucide-react";

type Status = "completed" | "in_progress" | "blocked" | "pending";

function classify(
  name: string, phases: Phase[], currentPhase: string,
  hasException: boolean,
): Status {
  const p = phases.find(x => x.name === name);
  if (p?.status === "completed") return "completed";
  if (name === currentPhase && hasException) return "blocked";
  if (name === currentPhase) return "in_progress";
  return "pending";
}

const Icon = ({ s }: { s: Status }) => {
  if (s === "completed") return <Check size={14} className="text-emerald-600" />;
  if (s === "in_progress") return <Loader2 size={14} className="text-blue-600 animate-spin" />;
  if (s === "blocked") return <Ban size={14} className="text-red-600" />;
  return <CircleDashed size={14} className="text-slate-400" />;
};

const PILL: Record<Status, string> = {
  completed: "bg-emerald-50 border-emerald-200 text-emerald-800",
  in_progress: "bg-blue-50 border-blue-200 text-blue-800",
  blocked: "bg-red-50 border-red-200 text-red-800",
  pending: "bg-slate-50 border-slate-200 text-slate-500",
};

export default function PhaseRibbon({ workflow, phases }: {
  workflow: Workflow; phases: Phase[];
}) {
  const hasException = !!workflow.activeExceptionId;
  return (
    <div className="flex items-center gap-2" data-testid="phase-ribbon">
      {PHASE_ORDER.map((name, i) => {
        const s = classify(name, phases, workflow.currentPhase, hasException);
        return (
          <div key={name} className="flex items-center gap-2">
            <div className={`flex items-center gap-1.5 rounded-full px-3 py-1 border ${PILL[s]}`}>
              <Icon s={s} />
              <span className="text-xs font-medium">{name}</span>
            </div>
            {i < PHASE_ORDER.length - 1 &&
              <div className="h-px w-4 bg-slate-300" />}
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `npm run build 2>&1 | tail -5`
Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
git add web/client/components/apex/PhaseRibbon.tsx
git commit -m "feat(apex): PhaseRibbon component"
```

---

### Task 14: `WorkflowHeaderTiles` + `EconomicsPanel` + `AuditTrail`

Three small, presentational, right-rail siblings. Grouped to one task for velocity.

**Files:**
- Create: `web/client/components/apex/WorkflowHeaderTiles.tsx`
- Create: `web/client/components/apex/EconomicsPanel.tsx`
- Create: `web/client/components/apex/AuditTrail.tsx`

- [ ] **Step 1: Create `WorkflowHeaderTiles.tsx`**

```tsx
// web/client/components/apex/WorkflowHeaderTiles.tsx
import type { Workflow } from "@shared/types";

function riskFactor(w: Workflow): "low" | "medium" | "high" {
  const hrsToSLA = (w.slaDueAt - Date.now() / 1000) / 3600;
  const hasExc = !!w.activeExceptionId;
  if (hasExc && hrsToSLA < 24) return "high";
  if (hasExc || hrsToSLA < 48) return "medium";
  return "low";
}

function slaHealth(w: Workflow): string {
  const hrs = Math.max(0, (w.slaDueAt - Date.now() / 1000) / 3600);
  if (hrs >= 24) return `${Math.round(hrs / 24)}d remaining`;
  return `${Math.round(hrs)}h remaining`;
}

const RISK_COLOR = {
  low:    "text-emerald-700 bg-emerald-50 border-emerald-200",
  medium: "text-amber-700 bg-amber-50 border-amber-200",
  high:   "text-red-700 bg-red-50 border-red-200",
};

export default function WorkflowHeaderTiles({ workflow }: { workflow: Workflow }) {
  const risk = riskFactor(workflow);
  const stalled = !!workflow.activeExceptionId;
  const statusTile = stalled
    ? { label: "STATUS · STALLED", value: `Exception at ${workflow.currentPhase}`, cls: "text-red-700 bg-red-50 border-red-200" }
    : { label: "STATUS", value: workflow.status, cls: "text-blue-700 bg-blue-50 border-blue-200" };
  return (
    <div className="grid grid-cols-3 gap-3" data-testid="workflow-header-tiles">
      {[
        statusTile,
        { label: "SLA HEALTH", value: slaHealth(workflow), cls: "text-slate-700 bg-slate-50 border-slate-200" },
        { label: "RISK FACTOR", value: risk.toUpperCase(), cls: RISK_COLOR[risk] },
      ].map(t => (
        <div key={t.label} className={`rounded-lg border p-3 ${t.cls}`}>
          <div className="text-[10px] uppercase font-semibold tracking-wide opacity-70">{t.label}</div>
          <div className="text-base font-semibold mt-1">{t.value}</div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Create `EconomicsPanel.tsx`**

```tsx
// web/client/components/apex/EconomicsPanel.tsx
import type { Economics } from "@shared/types";

export default function EconomicsPanel({ e }: { e: Economics }) {
  const tiles = [
    { k: "Compute cost", v: `$${e.computeCostUsd.toFixed(2)}` },
    { k: "Model calls",  v: String(e.modelCalls) },
    { k: "Tool calls",   v: String(e.toolCalls) },
    { k: "Days elapsed", v: String(e.daysElapsed.toFixed(1)) },
    { k: "SLA token",    v: e.slaToken },
  ];
  return (
    <div className="panel" data-testid="economics-panel">
      <div className="panel-header">Economics</div>
      <div className="panel-body grid grid-cols-2 gap-2">
        {tiles.map(t => (
          <div key={t.k} className="border border-slate-200 rounded p-2">
            <div className="text-[10px] uppercase tracking-wide text-slate-500">{t.k}</div>
            <div className="text-sm font-semibold text-slate-900">{t.v}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create `AuditTrail.tsx`**

```tsx
// web/client/components/apex/AuditTrail.tsx
import type { ActionLedgerEntry } from "@shared/types";

export default function AuditTrail({ ledger }: { ledger: ActionLedgerEntry[] }) {
  const last = ledger.slice(-8).reverse();
  return (
    <div className="panel" data-testid="audit-trail">
      <div className="panel-header flex items-center justify-between">
        <span>Audit Trail</span>
        <span className="text-[11px] font-normal text-slate-500">last {last.length}</span>
      </div>
      <div className="panel-body space-y-1.5">
        {last.length === 0 && <div className="text-xs text-slate-500">no entries yet</div>}
        {last.map((e, i) => (
          <div key={i} className="text-xs">
            <div className="text-slate-800 font-medium">{e.action}</div>
            <div className="text-slate-500">
              {new Date(e.timestamp * 1000).toLocaleString()} · {e.actorKind}:{e.actorId}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Verify build**

Run: `npm run build 2>&1 | tail -5`
Expected: build succeeds.

- [ ] **Step 5: Commit**

```bash
git add web/client/components/apex/WorkflowHeaderTiles.tsx web/client/components/apex/EconomicsPanel.tsx web/client/components/apex/AuditTrail.tsx
git commit -m "feat(apex): WorkflowHeaderTiles + EconomicsPanel + AuditTrail"
```

---

### Task 15: `ExceptionAnalysisCard` + `InterventionProtocols` + `FleetAssignment`

**Files:**
- Create: `web/client/components/apex/ExceptionAnalysisCard.tsx`
- Create: `web/client/components/apex/InterventionProtocols.tsx`
- Create: `web/client/components/apex/FleetAssignment.tsx`

- [ ] **Step 1: Create `ExceptionAnalysisCard.tsx`**

```tsx
// web/client/components/apex/ExceptionAnalysisCard.tsx
import type { Narrative } from "@shared/types";

function highlight(text: string): React.ReactNode {
  // Highlight money amounts, GL codes, PO numbers, all-caps IDs.
  const parts = text.split(/(\b[A-Z]{2,}-[A-Z0-9-]+|\$?\d[\d,]*\.?\d*|\bGL-\d+)/);
  return parts.map((p, i) => (
    /^([A-Z]{2,}-[A-Z0-9-]+|\$?\d[\d,]*\.?\d*|GL-\d+)$/.test(p)
      ? <span key={i} className="bg-amber-100 text-amber-900 rounded px-1">{p}</span>
      : <span key={i}>{p}</span>
  ));
}

export default function ExceptionAnalysisCard({ narrative }: { narrative: Narrative }) {
  return (
    <div className="panel" data-testid="exception-analysis">
      <div className="panel-header flex items-center gap-2">
        <span className="text-red-600">⚠</span>
        <span>Exception Analysis</span>
      </div>
      <div className="panel-body space-y-4 text-sm">
        <div>
          <div className="text-[10px] uppercase tracking-wide text-slate-500 mb-1">What Happened</div>
          <p className="text-slate-800">{highlight(narrative.whatHappened)}</p>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-wide text-slate-500 mb-1">What the Agent Tried</div>
          <ul className="list-disc pl-5 space-y-1 text-slate-700">
            {narrative.whatAgentTried.map((b, i) => <li key={i}>{b}</li>)}
          </ul>
        </div>
        <div className="bg-emerald-50 border border-emerald-200 rounded p-3">
          <div className="text-[10px] uppercase tracking-wide text-emerald-700 mb-1">Agent Recommendation</div>
          <p className="text-emerald-900">{narrative.agentRecommendation}</p>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create `InterventionProtocols.tsx`**

```tsx
// web/client/components/apex/InterventionProtocols.tsx
import { useState } from "react";
import type { Exception } from "@shared/types";

export default function InterventionProtocols({ exception, onResolved }: {
  exception: Exception; onResolved?: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const act = async (action: string) => {
    setBusy(true);
    try {
      await fetch("/api/exceptions/bulk-resolve", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          exceptionIds: [exception.id],
          resolution: action,
          resolvedBy: "finance-controller@wpp",
        }),
      });
      onResolved?.();
    } finally { setBusy(false); }
  };
  return (
    <div className="panel" data-testid="intervention-protocols">
      <div className="panel-header">Intervention Protocols</div>
      <div className="panel-body grid grid-cols-2 gap-2">
        {exception.options.map(o => (
          <button key={o.action}
                  disabled={busy}
                  onClick={() => act(o.action)}
                  data-testid={`protocol-${o.action}`}
                  className={o.recommended ? "btn-primary" :
                             o.action === "reject" ? "btn-danger" : "btn-secondary"}>
            {o.recommended && <span className="text-[10px] uppercase tracking-wider bg-white/20 rounded px-1">recommended</span>}
            {o.label}{o.nonRevocable ? " ⚠" : ""}
          </button>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create `FleetAssignment.tsx`**

```tsx
// web/client/components/apex/FleetAssignment.tsx
import type { OtelSpan } from "@shared/types";

export default function FleetAssignment({ spans }: { spans: OtelSpan[] }) {
  const byExecutor = new Map<string, { type: string; status: "ok" | "error"; count: number }>();
  for (const s of spans) {
    const name = String(s.attributes["executor.name"] ?? s.name);
    const type = String(s.attributes["executor.type"] ?? "unknown");
    const cur = byExecutor.get(name) ?? { type, status: "ok" as const, count: 0 };
    cur.count += 1;
    if (s.status === "error") cur.status = "error";
    byExecutor.set(name, cur);
  }
  const rows = [...byExecutor.entries()];
  return (
    <div className="panel" data-testid="fleet-assignment">
      <div className="panel-header">Fleet Assignment</div>
      <div className="panel-body space-y-1.5">
        {rows.length === 0 && <div className="text-xs text-slate-500">no executors fired yet</div>}
        {rows.map(([name, info]) => (
          <div key={name} className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${info.status === "error" ? "bg-red-500" : "bg-emerald-500"}`} />
              <span className="text-slate-800">{name}</span>
              <span className="text-[10px] text-slate-500 uppercase">{info.type}</span>
            </span>
            <span className="text-[11px] text-slate-500">{info.count} call{info.count === 1 ? "" : "s"}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Build**

Run: `npm run build 2>&1 | tail -5`
Expected: build succeeds.

- [ ] **Step 5: Commit**

```bash
git add web/client/components/apex/ExceptionAnalysisCard.tsx web/client/components/apex/InterventionProtocols.tsx web/client/components/apex/FleetAssignment.tsx
git commit -m "feat(apex): ExceptionAnalysisCard + InterventionProtocols + FleetAssignment"
```

---

### Task 16: `ExecutionTimelineTab` component

**Files:**
- Create: `web/client/components/apex/ExecutionTimelineTab.tsx`

- [ ] **Step 1: Create the component**

```tsx
// web/client/components/apex/ExecutionTimelineTab.tsx
import { useState } from "react";
import type { McpCall } from "@shared/types";
import { useFleetManagerStream } from "../../hooks/useFleetManagerStream";

function statusChip(code: number) {
  if (code === 0) return <span className="chip-info">PENDING</span>;
  if (code >= 200 && code < 300) return <span className="chip-success">{code}</span>;
  if (code >= 400) return <span className="chip-danger">{code}</span>;
  return <span className="chip-info">{code}</span>;
}

export default function ExecutionTimelineTab({ mcpCalls, workflowId, onLogAction }: {
  mcpCalls: McpCall[];
  workflowId: string;
  onLogAction: (action: string) => void;
}) {
  const [selected, setSelected] = useState<number | null>(
    mcpCalls.length > 0 ? 0 : null,
  );
  const fmEvents = useFleetManagerStream();
  const sel = selected != null ? mcpCalls[selected] : null;

  return (
    <div className="grid grid-cols-3 gap-4" data-testid="execution-timeline">
      <div className="col-span-2 space-y-2">
        <div className="flex items-center justify-between">
          <div className="text-sm text-slate-600">Run ID: <span className="font-mono">{workflowId}</span></div>
          <div className="flex gap-2">
            <button className="btn-secondary" data-testid="rollback-workflow"
                    onClick={() => onLogAction("workflow.rollback-requested")}>
              Rollback
            </button>
            <button className="btn-secondary" data-testid="fork-workflow"
                    onClick={() => onLogAction("workflow.fork-requested")}>
              Fork Workflow
            </button>
          </div>
        </div>
        {mcpCalls.length === 0 && (
          <div className="panel panel-body text-xs text-slate-500">
            Timeline populates as the orchestration fires MCP calls.
          </div>
        )}
        {mcpCalls.map((c, i) => {
          const failed = c.statusCode >= 400;
          return (
            <button key={i}
                    onClick={() => setSelected(i)}
                    data-testid={`timeline-step-${i}`}
                    className={`panel w-full text-left panel-body
                      ${i === selected ? "ring-2 ring-blue-400" : ""}
                      ${failed ? "border-red-300" : ""}`}>
              <div className="flex items-center gap-3">
                <span className="text-[10px] font-mono text-slate-500">STEP {String(i + 1).padStart(2, "0")}</span>
                <span className="text-sm font-semibold text-slate-800">{c.method} {new URL(c.url).pathname}</span>
                <span className="ml-auto">{statusChip(c.statusCode)}</span>
              </div>
              <div className="text-[11px] text-slate-500 mt-1">
                tool: {c.tool} · {c.durationMs} ms · {new Date(c.timestamp * 1000).toLocaleTimeString()}
              </div>
              {failed && (
                <div className="flex gap-2 mt-2">
                  <button onClick={e => { e.stopPropagation(); onLogAction(`step.${i}.fork`); }}
                          className="btn-secondary text-xs">Fork Step &amp; Re-run</button>
                  <button onClick={e => { e.stopPropagation(); onLogAction(`step.${i}.rollback`); }}
                          className="btn-secondary text-xs">Rollback to here</button>
                </div>
              )}
            </button>
          );
        })}
      </div>

      <div className="col-span-1 space-y-3">
        <div className="panel" data-testid="api-configuration">
          <div className="panel-header">API Configuration</div>
          <div className="panel-body">
            {!sel && <div className="text-xs text-slate-500">select a step</div>}
            {sel && (
              <>
                <div className="text-[11px] uppercase text-slate-500 mb-1">Request</div>
                <pre className="text-[11px] bg-slate-50 border border-slate-200 rounded p-2 whitespace-pre-wrap break-all max-h-48 overflow-auto">
{JSON.stringify(sel.request, null, 2)}
                </pre>
                <div className="text-[11px] uppercase text-slate-500 mb-1 mt-2">Response</div>
                <pre className="text-[11px] bg-slate-50 border border-slate-200 rounded p-2 whitespace-pre-wrap break-all max-h-48 overflow-auto">
{JSON.stringify(sel.response, null, 2)}
                </pre>
              </>
            )}
          </div>
        </div>

        <div className="panel" data-testid="agent-thought-stream">
          <div className="panel-header">Agent Thought Stream</div>
          <div className="panel-body space-y-1.5">
            {fmEvents.length === 0 && <div className="text-xs text-slate-500">no agent activity</div>}
            {fmEvents.slice(-6).map((e, i) => (
              <div key={i} className="text-xs">
                <div className="text-slate-800 font-medium">{e.kind}</div>
                <div className="text-slate-500 break-all">
                  {e.data ? JSON.stringify(e.data).slice(0, 140) : ""}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Build**

Run: `npm run build 2>&1 | tail -5`
Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
git add web/client/components/apex/ExecutionTimelineTab.tsx
git commit -m "feat(apex): ExecutionTimelineTab with step cards + API config + thought stream"
```

---

### Task 17: Rebuild `WorkflowDetail.tsx` with Apex Overview + Execution Timeline tabs

**Files:**
- Modify: `web/client/routes/WorkflowDetail.tsx`

- [ ] **Step 1: Rewrite the component**

Full contents of `web/client/routes/WorkflowDetail.tsx`:

```tsx
// web/client/routes/WorkflowDetail.tsx
import { useEffect, useState, useCallback } from "react";
import { useParams } from "react-router-dom";
import type {
  Workflow, Phase, OtelSpan, Exception, SkillAmplification,
  ActionLedgerEntry, McpCall, Economics, Narrative,
} from "@shared/types";
import OtelSpanTree from "../components/OtelSpanTree";
import PhaseTimeline from "../components/PhaseTimeline";
import SkillAmplificationPanel from "../components/SkillAmplificationPanel";
import PhaseRibbon from "../components/apex/PhaseRibbon";
import WorkflowHeaderTiles from "../components/apex/WorkflowHeaderTiles";
import ExceptionAnalysisCard from "../components/apex/ExceptionAnalysisCard";
import InterventionProtocols from "../components/apex/InterventionProtocols";
import EconomicsPanel from "../components/apex/EconomicsPanel";
import FleetAssignment from "../components/apex/FleetAssignment";
import AuditTrail from "../components/apex/AuditTrail";
import ExecutionTimelineTab from "../components/apex/ExecutionTimelineTab";

type DetailResp = {
  workflow: Workflow; phases: Phase[]; spans: OtelSpan[];
  amplifications: SkillAmplification[];
  activeException: Exception | null;
  mcpCalls: McpCall[];
  economics: Economics;
  narrative: Narrative | null;
};

const TABS = ["Overview", "Phases", "Traces", "Ledger", "Amplification", "Execution Timeline"] as const;

export default function WorkflowDetail() {
  const { id } = useParams();
  const [d, setD] = useState<DetailResp | null>(null);
  const [tab, setTab] = useState<typeof TABS[number]>("Overview");

  const refresh = useCallback(async () => {
    if (!id) return;
    const r = await fetch(`/api/workflows/${id}`);
    setD(await r.json());
  }, [id]);

  useEffect(() => { void refresh(); }, [refresh]);

  const logAction = useCallback(async (action: string) => {
    if (!id) return;
    // Fire-and-forget audit entry via bulk-resolve on no-op is out of scope;
    // simplest: refresh + console log. Real log-only happens when the
    // exception already has an action ledger appended by the server on
    // resolve. For Fork/Rollback we append a synthetic ledger entry via
    // the internal webhook.
    await fetch("/internal/durable-event", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        workflow_id: id, kind: "workflow.rejected", // reuses existing handler to append ledger entry
        payload: { by: "operator", reason: `illustrative ${action}` },
      }),
    }).catch(() => {});
    await refresh();
  }, [id, refresh]);

  if (!d) return <div className="text-sm text-slate-500">loading…</div>;
  const w = d.workflow;

  return (
    <div className="grid grid-cols-4 gap-4">
      {/* Main column */}
      <div className="col-span-3 space-y-4">
        <div>
          <div className="text-xs text-slate-500">{w.id}</div>
          <div className="text-xl font-semibold">{w.id} · {w.vendor.name}</div>
          <div className="text-xs text-slate-500">
            {w.invoice.currency} {w.invoice.amount.toLocaleString()} · PO {w.invoice.poRef} · {w.agency}
          </div>
        </div>

        <WorkflowHeaderTiles workflow={w} />
        <PhaseRibbon workflow={w} phases={d.phases} />

        <div className="flex gap-1 border-b border-slate-200">
          {TABS.map(t => (
            <button key={t} onClick={() => setTab(t)}
                    className={`text-sm px-4 py-2 ${tab === t ?
                      "text-blue-700 border-b-2 border-blue-600 font-medium" :
                      "text-slate-500 hover:text-slate-800"}`}>{t}</button>
          ))}
        </div>

        {tab === "Overview" && (
          <div className="space-y-4">
            {d.narrative && d.activeException && (
              <>
                <ExceptionAnalysisCard narrative={d.narrative} />
                <InterventionProtocols exception={d.activeException} onResolved={refresh} />
              </>
            )}
            {!d.activeException && (
              <div className="panel panel-body text-sm text-slate-500">
                No active exception. Workflow is progressing autonomously.
              </div>
            )}
          </div>
        )}
        {tab === "Phases" && <PhaseTimeline phases={d.phases} />}
        {tab === "Traces" && <OtelSpanTree spans={d.spans} />}
        {tab === "Ledger" && (
          <div className="space-y-1 text-xs">
            {(w.actionLedger as ActionLedgerEntry[]).map((a, i) => (
              <div key={i} className="panel panel-body">
                <div className="font-medium text-slate-800">{a.action}</div>
                <div className="text-slate-500">
                  {new Date(a.timestamp * 1000).toLocaleString()} · {a.actorKind}:{a.actorId}
                  · {a.revocable ? "revocable" : "non-revocable"}
                </div>
              </div>
            ))}
          </div>
        )}
        {tab === "Amplification" && <SkillAmplificationPanel items={d.amplifications} />}
        {tab === "Execution Timeline" &&
          <ExecutionTimelineTab mcpCalls={d.mcpCalls} workflowId={w.id} onLogAction={logAction} />}
      </div>

      {/* Right rail */}
      <div className="col-span-1 space-y-3">
        <EconomicsPanel e={d.economics} />
        <FleetAssignment spans={d.spans} />
        <AuditTrail ledger={w.actionLedger as ActionLedgerEntry[]} />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Build**

Run: `npm run build 2>&1 | tail -6`
Expected: build succeeds.

- [ ] **Step 3: Visual smoke**

Ensure `make up` is running in another terminal. Inject a demo-fail:

```bash
curl -s -X POST http://localhost:3001/api/simulator/inject -H "Content-Type: application/json" -d '{"scenario":"demo-fail"}'
```

Wait ~60s, then open `http://localhost:5173/workflows/INV-0001`. Verify:
- Header tile strip, Phase Ribbon, Exception Analysis card, Intervention Protocols show.
- Right rail shows Economics, Fleet Assignment, Audit Trail.
- Execution Timeline tab shows MCP call cards.

- [ ] **Step 4: Commit**

```bash
git add web/client/routes/WorkflowDetail.tsx
git commit -m "feat(ui): rebuild WorkflowDetail with Apex Overview + Execution Timeline"
```

---

### Task 18: Dashboard widgets

**Files:**
- Create: `web/client/components/apex/KpiTileRow.tsx`
- Create: `web/client/components/apex/ExceptionCardCompact.tsx`
- Create: `web/client/components/apex/FleetEconomicsPanel.tsx`
- Create: `web/client/components/apex/PolicyAutonomyPanel.tsx`

- [ ] **Step 1: `KpiTileRow.tsx`**

```tsx
// web/client/components/apex/KpiTileRow.tsx
import type { Workflow } from "@shared/types";

export default function KpiTileRow({ workflows, exceptionsCount }: {
  workflows: Workflow[]; exceptionsCount: number;
}) {
  const tiles = [
    { label: "Active Runs", v: workflows.filter(w => w.status === "in_progress").length },
    { label: "Awaiting HITL", v: workflows.filter(w => w.status === "awaiting_hitl").length },
    { label: "Completed",   v: workflows.filter(w => w.status === "completed").length },
    { label: "Failed",      v: workflows.filter(w => w.status === "failed").length },
    { label: "Exceptions",  v: exceptionsCount },
  ];
  return (
    <div className="grid grid-cols-5 gap-3" data-testid="kpi-tile-row">
      {tiles.map(t => (
        <div key={t.label} className="panel panel-body">
          <div className="text-[10px] uppercase tracking-wide text-slate-500">{t.label}</div>
          <div className="text-2xl font-semibold text-slate-900 mt-1">{t.v}</div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: `ExceptionCardCompact.tsx`**

```tsx
// web/client/components/apex/ExceptionCardCompact.tsx
import { Link } from "react-router-dom";
import type { Exception } from "@shared/types";

export default function ExceptionCardCompact({ e }: { e: Exception }) {
  return (
    <Link to={`/workflows/${e.workflowId}`}
          className="panel block p-4 hover:border-blue-400 transition">
      <div className="flex items-center gap-2 mb-2">
        <span className="chip-danger">{e.severity}</span>
        <span className="font-semibold text-slate-800">{e.workflowId}</span>
        <span className="text-xs text-slate-500">· {e.category}</span>
      </div>
      <div className="text-sm text-slate-700 line-clamp-2">{e.summary}</div>
      <div className="text-xs text-emerald-700 mt-2">→ {e.recommendation}</div>
    </Link>
  );
}
```

- [ ] **Step 3: `FleetEconomicsPanel.tsx`**

```tsx
// web/client/components/apex/FleetEconomicsPanel.tsx
import { useEffect, useState } from "react";
import type { FleetEconomics } from "@shared/types";

export default function FleetEconomicsPanel() {
  const [d, setD] = useState<FleetEconomics | null>(null);
  useEffect(() => {
    const load = () => fetch("/api/fleet/economics").then(r => r.json()).then(setD);
    void load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);
  if (!d) return <div className="panel panel-body text-xs text-slate-500">loading economics…</div>;
  return (
    <div className="panel" data-testid="fleet-economics">
      <div className="panel-header">Fleet Economics</div>
      <div className="panel-body grid grid-cols-2 gap-2 text-sm">
        <div><div className="text-[10px] uppercase text-slate-500">Compute (active)</div>
             <div className="font-semibold">${d.totalComputeCostUsd.toFixed(2)}</div></div>
        <div><div className="text-[10px] uppercase text-slate-500">Avg per wf</div>
             <div className="font-semibold">${d.averageCostPerWorkflow.toFixed(2)}</div></div>
        <div><div className="text-[10px] uppercase text-slate-500">Model calls</div>
             <div className="font-semibold">{d.totalModelCalls}</div></div>
        <div><div className="text-[10px] uppercase text-slate-500">Tool calls</div>
             <div className="font-semibold">{d.totalToolCalls}</div></div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: `PolicyAutonomyPanel.tsx`**

```tsx
// web/client/components/apex/PolicyAutonomyPanel.tsx
import { useEffect, useState } from "react";

type Policy = { id: string; description: string; currentValue: number | string | boolean };

export default function PolicyAutonomyPanel() {
  const [items, setItems] = useState<Policy[]>([]);
  useEffect(() => { void fetch("/api/policy/").then(r => r.json()).then(setItems); }, []);
  return (
    <div className="panel" data-testid="policy-autonomy">
      <div className="panel-header">Policy &amp; Autonomy</div>
      <div className="panel-body space-y-2">
        {items.length === 0 && <div className="text-xs text-slate-500">no policies loaded</div>}
        {items.map(p => {
          const v = typeof p.currentValue === "number" ? p.currentValue :
                    typeof p.currentValue === "boolean" ? (p.currentValue ? 1 : 0) : 0.5;
          const pct = Math.max(0, Math.min(1, v <= 1 ? v : v / 100));
          return (
            <div key={p.id}>
              <div className="flex justify-between text-xs">
                <span className="text-slate-700">{p.description}</span>
                <span className="text-slate-500">{String(p.currentValue)}</span>
              </div>
              <div className="h-1.5 bg-slate-200 rounded mt-1">
                <div className="h-1.5 bg-blue-500 rounded" style={{ width: `${pct * 100}%` }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Build**

Run: `npm run build 2>&1 | tail -5`
Expected: build succeeds.

- [ ] **Step 6: Commit**

```bash
git add web/client/components/apex/KpiTileRow.tsx web/client/components/apex/ExceptionCardCompact.tsx web/client/components/apex/FleetEconomicsPanel.tsx web/client/components/apex/PolicyAutonomyPanel.tsx
git commit -m "feat(apex): dashboard widgets (KPI row, compact exception, fleet economics, policy autonomy)"
```

---

### Task 19: Rebuild `FleetDashboard.tsx`

**Files:**
- Modify: `web/client/routes/FleetDashboard.tsx`

- [ ] **Step 1: Rewrite**

```tsx
// web/client/routes/FleetDashboard.tsx
import { useWorkflows } from "../hooks/useWorkflows";
import { useExceptions } from "../hooks/useExceptions";
import WorkflowCard from "../components/WorkflowCard";
import DevPanel from "../components/DevPanel";
import KpiTileRow from "../components/apex/KpiTileRow";
import ExceptionCardCompact from "../components/apex/ExceptionCardCompact";
import FleetEconomicsPanel from "../components/apex/FleetEconomicsPanel";
import PolicyAutonomyPanel from "../components/apex/PolicyAutonomyPanel";

export default function FleetDashboard() {
  const { workflows } = useWorkflows();
  const { items: exceptions } = useExceptions();
  const topExceptions = exceptions.slice(0, 3);

  return (
    <div className="grid grid-cols-4 gap-4">
      <div className="col-span-3 space-y-4">
        <div className="flex items-center gap-3">
          <div>
            <div className="text-xl font-semibold">Control Plane Overview</div>
            <div className="text-xs text-slate-500">
              Operational status for Finance Controller's fleet
            </div>
          </div>
          <div className="ml-auto"><DevPanel /></div>
        </div>
        <KpiTileRow workflows={workflows} exceptionsCount={exceptions.length} />
        <div className="panel">
          <div className="panel-header">Exceptions Requiring Attention</div>
          <div className="panel-body grid grid-cols-3 gap-3">
            {topExceptions.length === 0 &&
              <div className="text-xs text-slate-500 col-span-3">No open exceptions.</div>}
            {topExceptions.map(e => <ExceptionCardCompact key={e.id} e={e} />)}
          </div>
        </div>
        <div className="panel">
          <div className="panel-header flex items-center justify-between">
            <span>Active Workflows</span>
            <span className="text-[11px] text-slate-500">{workflows.length} shown</span>
          </div>
          <div className="panel-body grid grid-cols-3 gap-2">
            {workflows.map(w => <WorkflowCard key={w.id} w={w} />)}
          </div>
        </div>
      </div>

      <div className="col-span-1 space-y-3">
        <FleetEconomicsPanel />
        <PolicyAutonomyPanel />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Build**

Run: `npm run build 2>&1 | tail -5`
Expected: build succeeds.

- [ ] **Step 3: Visual smoke**

Open `http://localhost:5173/fleet`. Verify KPI row, Exceptions Requiring Attention block with up to 3 cards, Active Workflows grid, Fleet Economics + Policy & Autonomy right rail.

- [ ] **Step 4: Commit**

```bash
git add web/client/routes/FleetDashboard.tsx
git commit -m "feat(ui): rebuild FleetDashboard with Apex layout"
```

---

### Task 20: Shell chrome (top bar + left nav)

**Files:**
- Modify: `web/client/App.tsx`

- [ ] **Step 1: Rewrite**

Full contents of `web/client/App.tsx`:

```tsx
// web/client/App.tsx
import { NavLink, Route, Routes, BrowserRouter, Navigate } from "react-router-dom";
import FleetDashboard from "./routes/FleetDashboard";
import ExceptionQueue from "./routes/ExceptionQueue";
import PolicyAndAutonomy from "./routes/PolicyAndAutonomy";
import Analytics from "./routes/Analytics";
import Evaluations from "./routes/Evaluations";
import WorkflowDetail from "./routes/WorkflowDetail";
import FleetManagerRail from "./components/FleetManagerRail";

const leftNav = [
  { to: "/fleet",       label: "Dashboard" },
  { to: "/exceptions",  label: "Exceptions" },
  { to: "/policy",      label: "Policy" },
  { to: "/analytics",   label: "Analytics" },
  { to: "/evals",       label: "Evaluations" },
];

const topNav = [
  { to: "/fleet",   label: "Dashboard" },
  { to: "/fleet",   label: "Workflows" },    // same target for now
  { to: "/agents",  label: "Agents" },
  { to: "/library", label: "Library" },
  { to: "/economics", label: "Economics" },
];

function Stub({ title }: { title: string }) {
  return <div className="panel panel-body text-sm text-slate-600">{title} — coming soon.</div>;
}

export default function App() {
  return (
    <BrowserRouter>
      {/* Top bar */}
      <header className="flex items-center gap-6 px-6 h-12 border-b border-slate-200 bg-white">
        <div className="font-semibold">Project Apex</div>
        <span className="text-slate-300">|</span>
        <div className="text-sm text-slate-600">Control Plane</div>
        <nav className="flex gap-4 ml-8">
          {topNav.map(n => (
            <NavLink key={n.label} to={n.to}
                     className={({ isActive }) => `text-sm ${isActive ?
                       "text-blue-700 font-medium" : "text-slate-500 hover:text-slate-800"}`}>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="ml-auto text-xs text-slate-500">role: Finance Controller</div>
      </header>

      <div className="grid grid-cols-[220px_1fr_360px] h-[calc(100vh-3rem)]">
        {/* Left nav */}
        <aside className="bg-white border-r border-slate-200 p-3 space-y-1">
          <div className="text-[10px] uppercase tracking-wide text-slate-500 px-2 mb-2">
            Control Plane
          </div>
          {leftNav.map(n => (
            <NavLink key={n.to} to={n.to}
                     className={({ isActive }) => `block text-sm px-3 py-1.5 rounded ${isActive ?
                       "bg-blue-50 text-blue-700 font-medium" : "text-slate-700 hover:bg-slate-100"}`}>
              {n.label}
            </NavLink>
          ))}
        </aside>

        {/* Main */}
        <main className="p-6 overflow-auto">
          <Routes>
            <Route path="/" element={<Navigate to="/fleet" replace />} />
            <Route path="/fleet" element={<FleetDashboard />} />
            <Route path="/workflows/:id" element={<WorkflowDetail />} />
            <Route path="/exceptions" element={<ExceptionQueue />} />
            <Route path="/policy" element={<PolicyAndAutonomy />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/evals" element={<Evaluations />} />
            <Route path="/agents" element={<Stub title="Agents" />} />
            <Route path="/library" element={<Stub title="Library" />} />
            <Route path="/economics" element={<Stub title="Economics" />} />
          </Routes>
        </main>

        {/* Right rail */}
        <aside className="border-l border-slate-200 bg-white overflow-auto">
          <FleetManagerRail />
        </aside>
      </div>
    </BrowserRouter>
  );
}
```

- [ ] **Step 2: Build + visual smoke**

Run: `npm run build 2>&1 | tail -5`
Expected: build succeeds.

Open `http://localhost:5173/` — redirects to `/fleet`, top bar + left nav + right rail render, all routes navigate.

- [ ] **Step 3: Commit**

```bash
git add web/client/App.tsx
git commit -m "feat(ui): Apex shell chrome (top bar + left nav + right rail)"
```

---

### Task 21: Extend Playwright harness

**Files:**
- Modify: `tests/e2e/smoke.spec.ts`

- [ ] **Step 1: Append the new tests**

Append to `tests/e2e/smoke.spec.ts` (before the final closing of the file, after the existing `test.describe("Pipeline E2E", ...)`):

```ts
// --- Apex redesign tests ----------------------------------------------------

test.describe("Apex API contract", () => {
  test("workflow detail carries mcpCalls, economics, narrative when exception present", async ({ request }) => {
    test.setTimeout(180_000);
    const inj = await request.post(`${API}/api/simulator/inject`, {
      data: { scenario: "demo-fail" },
    });
    const { workflow_id: wid } = await inj.json();
    // poll for economics + narrative
    const deadline = Date.now() + 150_000;
    let body: any = null;
    while (Date.now() < deadline) {
      await new Promise(r => setTimeout(r, 3000));
      const r = await request.get(`${API}/api/workflows/${wid}`);
      if (!r.ok()) continue;
      body = await r.json();
      if (body.economics && (body.narrative || body.activeException === null)) break;
    }
    expect(body).not.toBeNull();
    expect(body.economics).toBeTruthy();
    for (const k of ["computeCostUsd", "modelCalls", "toolCalls", "daysElapsed", "slaToken"]) {
      expect(body.economics).toHaveProperty(k);
    }
    expect(Array.isArray(body.mcpCalls)).toBeTruthy();
    if (body.activeException) {
      expect(body.narrative).toBeTruthy();
      for (const k of ["whatHappened", "whatAgentTried", "agentRecommendation"]) {
        expect(body.narrative).toHaveProperty(k);
      }
    }
  });

  test("fleet economics endpoint returns rollup", async ({ request }) => {
    const r = await request.get(`${API}/api/fleet/economics`);
    expect(r.ok()).toBeTruthy();
    const body = await r.json();
    for (const k of ["activeWorkflowCount", "totalComputeCostUsd",
                     "totalModelCalls", "totalToolCalls", "averageCostPerWorkflow"]) {
      expect(body).toHaveProperty(k);
    }
  });

  test("exception options carry a recommended action", async ({ request }) => {
    const r = await request.get(`${API}/api/exceptions/`);
    const list = await r.json();
    if (list.length > 0) {
      expect(list[0].options.some((o: any) => o.recommended === true)).toBeTruthy();
    }
  });
});

test.describe("Apex UI smoke", () => {
  test("/fleet renders KPI tiles + exceptions block", async ({ page }) => {
    await page.goto("/fleet", { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    await expect(page.getByTestId("kpi-tile-row")).toBeVisible();
    await expect(page.getByText(/Exceptions Requiring Attention/i)).toBeVisible();
  });

  test("workflow detail shows Apex widgets", async ({ page, request }) => {
    test.setTimeout(180_000);
    let list = await (await request.get(`${API}/api/workflows/`)).json();
    if (list.length === 0) {
      await request.post(`${API}/api/simulator/inject`, { data: { scenario: "demo-fail" } });
      // wait until at least one workflow exists
      const deadline = Date.now() + 30_000;
      while (Date.now() < deadline && list.length === 0) {
        await new Promise(r => setTimeout(r, 2000));
        list = await (await request.get(`${API}/api/workflows/`)).json();
      }
    }
    expect(list.length).toBeGreaterThan(0);
    const id = list[0].id;
    await page.goto(`/workflows/${id}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2500);
    for (const tid of ["workflow-header-tiles", "phase-ribbon", "economics-panel",
                       "fleet-assignment", "audit-trail"]) {
      await expect(page.getByTestId(tid)).toBeVisible();
    }
  });

  test("execution timeline shows MCP steps after the workflow progresses", async ({ page, request }) => {
    test.setTimeout(180_000);
    // prompt a fresh workflow + wait for at least 1 mcp call
    const inj = await request.post(`${API}/api/simulator/inject`, { data: { scenario: "demo-fail" } });
    const { workflow_id: wid } = await inj.json();
    const deadline = Date.now() + 150_000;
    let body: any = null;
    while (Date.now() < deadline) {
      await new Promise(r => setTimeout(r, 3000));
      const r = await request.get(`${API}/api/workflows/${wid}`);
      if (!r.ok()) continue;
      body = await r.json();
      if (body.mcpCalls && body.mcpCalls.length > 0) break;
    }
    expect(body?.mcpCalls?.length ?? 0).toBeGreaterThan(0);
    await page.goto(`/workflows/${wid}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);
    await page.getByRole("main").getByRole("button", { name: /^Execution Timeline$/ }).click();
    await page.waitForTimeout(500);
    await expect(page.getByTestId("execution-timeline")).toBeVisible();
    await expect(page.getByTestId("timeline-step-0")).toBeVisible();
    await page.getByTestId("timeline-step-0").click();
    await expect(page.getByTestId("api-configuration")).toContainText(/Request/i);
  });

  test("intervention protocols: clicking recommended action resolves exception", async ({ page, request }) => {
    test.setTimeout(180_000);
    // ensure at least one exception exists
    let exs = await (await request.get(`${API}/api/exceptions/`)).json();
    if (exs.length === 0) {
      await request.post(`${API}/api/simulator/inject`, { data: { scenario: "demo-fail" } });
      const deadline = Date.now() + 150_000;
      while (Date.now() < deadline) {
        await new Promise(r => setTimeout(r, 3000));
        exs = await (await request.get(`${API}/api/exceptions/`)).json();
        if (exs.length > 0) break;
      }
    }
    expect(exs.length).toBeGreaterThan(0);
    const wid = exs[0].workflowId;
    const startId = exs[0].id;
    await page.goto(`/workflows/${wid}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);
    // recommended action is primary-styled; we use the server-flagged action
    const recommended = exs[0].options.find((o: any) => o.recommended)?.action ?? "approve";
    await page.getByTestId(`protocol-${recommended}`).click();
    await page.waitForTimeout(1500);
    const after = await (await request.get(`${API}/api/exceptions/`)).json();
    expect(after.map((e: any) => e.id)).not.toContain(startId);
  });
});
```

- [ ] **Step 2: Run full harness**

Ensure `make up` is running. Then:

Run: `npx playwright test --reporter=list 2>&1 | tail -20`
Expected: all new tests pass alongside existing ones. Target total runtime under 5 min.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/smoke.spec.ts
git commit -m "test(e2e): Apex harness additions (contract, UI smoke, timeline, protocols)"
```

---

## Self-review

1. **Spec coverage** — every spec section has a task:
   - §2.1 Dashboard → Task 18 + 19
   - §2.2 Workflow Detail → Tasks 13–17
   - §2.3 Execution Timeline → Task 16 + 17 (tab integration)
   - §3.1 MCP call instrumentation → Tasks 2, 3, 4
   - §3.2 Economics → Task 5
   - §3.3 Narrative → Task 6
   - §3.4 Intervention Protocols → Task 7 (factory), Task 8 (bulk-resolve), Task 15 (component)
   - §4.1 Light theme → Task 12
   - §4.2 Shell chrome → Task 20
   - §4.3 Components → Tasks 13, 14, 15, 16, 18
   - §4.4 Dashboard rebuild → Task 19
   - §4.5 Workflow detail rebuild → Task 17
   - §5 Tests → Task 21 (plus TDD tests in every earlier task)
2. **Placeholder scan** — no TODOs / TBDs / "see above". Every code block is complete.
3. **Type consistency** — `McpCall` / `Economics` / `Narrative` / `FleetEconomics` names consistent across Python + TS. `ExceptionOption.recommended` consistent. Workflow detail response shape consistent between Task 9 (Python) and Task 11 (TS) and Task 17 (consumer).
4. **Ambiguity** — the only judgment call is the fake "workflow.rejected" webhook in Task 17's `logAction` helper for Fork/Rollback. Flagged inline; the intent is a log-only audit entry without adding a new route. If the engineer prefers a dedicated `workflow.audit` kind, they can add it in ~5 min and wire a ledger append; both work for the demo.
