# Apex Control Plane Redesign

**Status:** Approved, ready to plan
**Date:** 2026-04-23
**Scope:** `control-plane/` (React UI) + `control-plane-py/` (FastAPI server + Durable event handler)
**Not in scope:** real token/cost tracking, real Fork / Rollback backend, multi-operator RBAC, real business-system integrations, Foundry OTEL export, swap of POC1 domain (stays Finance P2P).

---

## 1. Context

The RFP client (WPP) sent a `Project Apex` diagram pack with three screen mocks:
`docs/WPPET-4-Apex-diagrams.pdf`. Our current UI is structurally similar but
visually unopinionated (dev-oriented dark slate surface). The redesign retrofits
the Apex visual language onto the existing Finance P2P POC1 backend without
changing domain data.

Three approaches were considered (**R** real-where-cheap / **F** full build /
**S** shallow visual-only). Picked **R**: pure UI refactor on real events with
minimal backend enrichment. Everything on screen traces back to a real event in
the pipeline; nothing is static mock data.

Target: produce a demo-grade Control Plane that looks like the Apex mocks and
survives click-through by a client.

---

## 2. Three screens

### 2.1 Dashboard Overview — `/fleet`

Matches Apex slide 9. Layout top-to-bottom:
- Header chrome: "Project Apex · Control Plane" brand, top nav tabs
  (Dashboard / Workflows / Agents / Library / Economics), role pill top-right.
- KPI tile row: Active Runs / Exceptions / Paused / Completed / Autonomy dial
  — maps to our existing counters; no new data.
- "Exceptions Requiring Attention" — top 3 open exceptions rendered as wide
  cards with narrative preview (first ~160 chars of `whatHappened`) and a
  single primary-recommended action button. Click = open Workflow Detail.
- Bulk Approval strip — existing bulk-resolve mechanism, relabelled.
- Right-side panels:
  - **Fleet Economics** — rolled-up sum of `economics.computeCostUsd`
    across active workflows (status in `in_progress | awaiting_hitl`),
    total model + tool calls, cost-per-workflow average. Server computes
    this on a new `GET /api/fleet/economics` endpoint.
  - **Policy & Autonomy** — per-phase autonomy bar rendered from the existing
    `/api/policy/` response (already returns autonomy levels).
- Secondary section: existing workflow card grid, kept as drill-down.

### 2.2 Workflow Detail — `/workflows/:id`

Matches Apex slide 10. The hero screen.

**Header region:**
- Title: `INV-0001 · Wayne Enterprises` (id + vendor.name)
- Subtitle: `USD 12,529.88 · PO PO-10004 · Ogilvy-US`
- Workflow identity pill top-right with id + `createdAt` date
- Three-up tile strip:
  - **Status** — colored badge with current_phase context ("Stalled at
    Approval 48h" / "In Flight" / "Completed" / "Rejected")
  - **SLA Health** — computed `slaDueAt - now`, render hours/days remaining
  - **Risk Factor** — derived label: `high` if exception + SLA <24h, `medium`
    if exception OR SLA <48h, else `low`

**Phase Ribbon** (below header):
Six pills for the six phases (Intake / Validation / Routing / Approval /
Payment / Reconciliation). Each shows status icon: ✓ completed, ⏱ in-progress,
🚫 blocked, ⏸ pending. Driven by the existing `phases` array from the detail
response plus the workflow's `currentPhase` + active exception state.

**Exception Analysis Card** (main, only when `activeException != null`):
Three sections consumed from the new `narrative` field:
- **What Happened** — single prose paragraph. Entities (vendor name, amount,
  GL code) highlighted via regex-based span wrapping. Template-generated
  server-side.
- **What the Agent Tried** — 3–5 bullet list derived from the workflow's
  `actionLedger` entries (most recent 5 ledger actions).
- **Agent Recommendation** — prose derived from `exception.recommendation`
  plus the exception's `relatedPolicyRefs`.

**Intervention Protocols** (below Exception Analysis):
Named action buttons in a horizontal strip. Category-specific options
(see §3.4). The recommended action is visually primary. Each button POSTs
to `/api/exceptions/bulk-resolve` with `exceptionIds: [currentId]` and
the button's `action` string.

**Right rail** (sidebar throughout detail):
- **Economics panel** — read-only tile grid showing computeCostUsd /
  modelCalls / toolCalls / daysElapsed / slaToken, plus a small trend bar
  showing cost over the last 5 minutes (derived from spans).
- **Fleet Assignment** — list of agents involved: the orchestrator + the
  agent-type executors that have fired at least once for this workflow
  (dedup'd by name), with a status dot (running / completed / idle).
- **Audit Trail** — compact chronological list of the last 8 action ledger
  entries + "Full Log" link that opens the existing Ledger tab.

**Tabs**: Overview (new, contains the above layout) / Phases / Traces / Ledger
/ Amplification / Execution Timeline (new, replaces current Orchestration tab
— see §2.3).

### 2.3 Execution Timeline — tab on Workflow Detail

Matches Apex slide 11. Tab label: `Execution Timeline`.

**Header:** Run ID pill + "Rollback" / "Fork Workflow" buttons top-right
(log-only — clicking appends an audit entry, no real state change).

**Left column:** vertical list of step cards. Each step = one `mcp.call`
event (from the new instrumentation, §3.1). Card shows:
- Sequence number + timestamp
- Method + path (e.g. `GET /workday/getVendor`)
- Status badge (SUCCESS green / ERROR red / PENDING blue)
- Duration ms

Failed steps get a red border and expose two buttons inline: **Fork Step &
Re-run**, **Rollback to here** — both log-only.

**Right column (when a step is selected):**
- **API Configuration** — pretty-printed JSON of the step's request payload +
  response body. Toggleable edit-mode header, read-only (the "edit" is
  visual only — not wired).
- **Agent Thought Stream** — bottom panel. For each GHCP SDK session event
  that fired during the step's time window (from the fleet-manager-stream
  already bridged), show one bubble: thought type, text, timestamp, estimated
  cost chip.

If there are no MCP calls yet (workflow still in Intake), render an empty
state: "Timeline populates as the orchestration fires MCP calls."

---

## 3. Backend enrichment

Four items, sized together to ~3 hours.

### 3.1 MCP call instrumentation

**Change:** `control-plane-py/src/functions/graphs/_common.py` — the
`call_mcp()` helper. Currently it just runs `httpx.post`. Add:

```python
async def call_mcp(base_url: str, tool: str, args: dict,
                   workflow_id: str | None = None,
                   instance_id: str | None = None) -> dict:
    t0 = time.time()
    async with httpx.AsyncClient() as c:
        try:
            r = await c.post(f"{base_url}/mcp/call/{tool}", json=args, timeout=10)
            resp = r.json() if r.is_success else {"error": r.text}
            status = r.status_code
        except Exception as ex:
            resp = {"error": str(ex)}
            status = 599
        duration_ms = int((time.time() - t0) * 1000)
    if workflow_id:
        from src.functions.webhook import emit
        await emit(workflow_id, instance_id, "mcp.call", {
            "tool": tool,
            "url": f"{base_url}/mcp/call/{tool}",
            "method": "POST",
            "request": args,
            "response": resp,
            "status_code": status,
            "duration_ms": duration_ms,
        })
    if status >= 400:
        raise RuntimeError(f"mcp {tool} failed: {status}")
    return resp
```

**Callers:** deterministic executors that use `call_mcp` (~10 files under
`executors/deterministic/`) need to pass `workflow_id` / `instance_id`. The
MAF executor's `process(input, ctx)` already receives `input["workflow_id"]`
so each caller becomes a one-line change.

**Handler:** `control-plane-py/src/server/routes/internal_durable_event.py`
gains a branch for `kind == "mcp.call"`:

```python
elif body.kind == "mcp.call":
    app_state.store.append_mcp_call(wid, McpCall(
        workflow_id=wid,
        timestamp=now,
        tool=body.payload["tool"],
        url=body.payload["url"],
        method=body.payload["method"],
        request=body.payload["request"],
        response=body.payload["response"],
        status_code=body.payload["status_code"],
        duration_ms=body.payload["duration_ms"],
    ))
```

**Store:** add `McpCall` type to `src/shared/types.py` (inherits the
camelCase base):

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

Add `_mcp_calls: dict[str, list[McpCall]]` + `append_mcp_call(wid, c)` +
`get_mcp_calls(wid)` to `StateStore`. Same shape as `_phases` / `_spans`.

**Response:** workflow detail route returns `mcpCalls:
[...store.get_mcp_calls(id)]` via `model_dump(by_alias=True)`.

### 3.2 Economics derivation

**New file:** `control-plane-py/src/server/services/economics.py`:

```python
COMPUTE_RATE_PER_SECOND = 0.0001   # "$/sec of executor wall-clock"
MODEL_CALL_RATE        = 0.02      # "$/agent invocation"

def compute(workflow, spans, mcp_calls):
    model_calls = sum(1 for s in spans
                      if s.attributes.get("executor.type") == "agent")
    tool_calls  = len(mcp_calls)
    compute_usd = (
        sum(s.end_ms - s.start_ms for s in spans) / 1000 * COMPUTE_RATE_PER_SECOND
        + model_calls * MODEL_CALL_RATE
    )
    days_elapsed = (time.time() - workflow.created_at) / 86400
    sla_token    = "SLA-" + hashlib.sha256(workflow.id.encode()).hexdigest()[:4].upper()
    return {
        "computeCostUsd": round(compute_usd, 2),
        "modelCalls": model_calls,
        "toolCalls": tool_calls,
        "daysElapsed": round(days_elapsed, 2),
        "slaToken": sla_token,
    }
```

Called from `workflows.py::get_workflow`, injected into detail response as
`economics: {...}`.

### 3.3 Narrative assembler

**New file:** `control-plane-py/src/server/services/exception_narrative.py`.

Pure-template functions, one per exception category. Each receives the
workflow, its open exception, ledger, and (for validator-blocked) the
validator name/reason. Emits:

```python
{
    "whatHappened": "Invoice INV-980444 for Wayne Enterprises (USD 12,529.88)
        blocked at Routing: the GL coder selected GL-9999 which is not in the
        active GL set for Ogilvy-US.",
    "whatAgentTried": [
        "lookup_vendor_context returned Wayne Enterprises (V-001)",
        "doc_intelligence_extract recovered all required fields",
        "agent_gl_coder assigned GL-9999 with rationale 'demo-fail injection'",
        "validate_gl_active rejected: GL-9999 not in ACTIVE_GLS",
    ],
    "agentRecommendation": "Re-route to a GL specialist to reassign an active
        GL code, or approve override if GL-9999 is intended as an exception.
        Related policy: GL-ACTIVE-POLICY (updated 2026-03-12).",
}
```

Called from `workflows.py::get_workflow` only when `active_exception_id` is
set. Injected as `narrative: {...}`.

### 3.4 Intervention Protocols

**Where:** `src/server/services/exception_factory.py` — extend the default
`options` each factory produces.

```python
# validator-blocked:
options = [
    ExceptionOption(label="Approve override",    action="approve",          recommended=False, non_revocable=True),
    ExceptionOption(label="Re-route to GL specialist", action="reroute-gl", recommended=True,  non_revocable=False),
    ExceptionOption(label="Request vendor info", action="request-info",     recommended=False, non_revocable=False),
    ExceptionOption(label="Escalate to CFO",     action="escalate",         recommended=False, non_revocable=False),
    ExceptionOption(label="Reject",              action="reject",           recommended=False, non_revocable=True),
]
# threshold-exceeded:
options = [
    ExceptionOption(label="Approve",                action="approve",      recommended=True,  non_revocable=True),
    ExceptionOption(label="Request additional docs", action="request-info", recommended=False, non_revocable=False),
    ExceptionOption(label="Escalate to approver L2", action="escalate",    recommended=False, non_revocable=False),
    ExceptionOption(label="Reject",                 action="reject",       recommended=False, non_revocable=True),
]
```

`ExceptionOption` gains a `recommended: bool = False` field (backwards
compatible default, UI reads it).

The `/api/exceptions/bulk-resolve` endpoint accepts the extended action
strings (`reroute-gl`, `request-info`, `escalate`) but treats them as
soft-resolve for now: exception marked resolved, workflow annotated in
ledger with the specific action name (`bulk-resolve:reroute-gl`), no
additional orchestration state change. Demo-only semantics.

---

## 4. Frontend

### 4.1 Light theme

`control-plane/src/client/styles.css` rewritten:
- Root `body`: `bg-slate-50 text-slate-900`
- Cards: `bg-white border border-slate-200 shadow-sm rounded-lg`
- Primary: `bg-blue-600 text-white hover:bg-blue-700`
- Success / warning / error: `emerald-600` / `amber-500` / `red-500`

Component-level classes are updated via search-and-replace across
`src/client/components/` and `src/client/routes/` (a shell script in
`scripts/light-theme-migrate.sh` runs the sed swaps, with a preview diff
step). Result checked in; no runtime feature flag, no dark/light toggle.

### 4.2 Shell chrome

`App.tsx` top bar + left nav match Apex:
- Top bar: brand · Dashboard / Workflows / Agents / Library / Economics ·
  bell · avatar. Our routes map to Dashboard=`/fleet`, Workflows=`/fleet`
  drill-down, Agents=stub page with a "Coming soon" notice, Library=stub,
  Economics=stub rendering aggregated Fleet Economics.
- Left nav inside the app: Dashboard / Active Runs / Fleet Status /
  Tool Registry / Logs. First two link to real pages; rest are stubs for
  slide-11 fidelity.

### 4.3 New components

All under `control-plane/src/client/components/apex/`:

| Component | Data source | Est. |
|---|---|---|
| `PhaseRibbon.tsx` | `phases[]` + `currentPhase` + `activeExceptionId` | 45m |
| `WorkflowHeaderTiles.tsx` | `status`, `slaDueAt`, derived risk | 30m |
| `ExceptionAnalysisCard.tsx` | `narrative.{whatHappened, whatAgentTried, agentRecommendation}` | 45m |
| `InterventionProtocols.tsx` | `activeException.options` (with `recommended` flag) | 30m |
| `EconomicsPanel.tsx` | `economics` | 20m |
| `FleetAssignment.tsx` | `spans[]` filtered by type=agent + orchestration state | 30m |
| `AuditTrail.tsx` | `actionLedger[]` (compact last 8) | 20m |
| `ExecutionTimelineTab.tsx` | `mcpCalls[]` + Fleet Manager stream | 90m |
| `ExceptionCardCompact.tsx` (dashboard) | exception + narrative preview | 30m |
| `KpiTileRow.tsx` | existing counters from `/api/workflows/` | 20m |
| `FleetEconomicsPanel.tsx` | aggregate of per-workflow economics | 30m |
| `PolicyAutonomyPanel.tsx` | `/api/policy/` | 30m |

### 4.4 Dashboard rebuild

`FleetDashboard.tsx` reworked to the Apex layout: KPI row, Exceptions
Requiring Attention (`ExceptionCardCompact` for top 3 open exceptions),
bulk approval strip, right-rail with `FleetEconomicsPanel` +
`PolicyAutonomyPanel`. Existing workflow-card grid kept as a section below.

### 4.5 Workflow detail rebuild

`WorkflowDetail.tsx` Overview tab rewritten to compose (top-down):
`WorkflowHeaderTiles` → `PhaseRibbon` → `ExceptionAnalysisCard` →
`InterventionProtocols`. Right rail (rendered by the shell around the tab
content) carries `EconomicsPanel` + `FleetAssignment` + `AuditTrail`.
The existing Phases / Traces / Ledger / Amplification tabs stay for depth.
The existing Orchestration tab is replaced by `ExecutionTimelineTab`.

---

## 5. Tests

Extensions to `control-plane/tests/e2e/smoke.spec.ts`:

**API contract**:
- Workflow detail response includes `mcpCalls` (array), `economics` (object
  with the 5 numeric fields), `narrative` when active exception exists.
- Every `mcpCall` has `tool`, `method`, `request`, `response`, `statusCode`,
  `durationMs`, `timestamp`.
- `exception.options` has at least one entry with `recommended: true` for
  non-empty exception lists.

**UI smoke**:
- `/fleet` renders KPI tile row + at least one Exception card when a
  workflow has exceptions.
- `/workflows/{id}` Overview tab renders `PhaseRibbon` (6 pills),
  `ExceptionAnalysisCard` (when exception present, contains three sections),
  `InterventionProtocols` (at least 3 buttons), `EconomicsPanel`
  (5 tile labels), `FleetAssignment`, `AuditTrail`.
- Execution Timeline tab renders at least one MCP call step after a workflow
  progresses past Intake; clicking it populates the side panel with request
  JSON.

**Interaction**:
- Click recommended Intervention Protocol button → exception resolved,
  button set becomes disabled, ledger shows `bulk-resolve:<action>`.
- Click Fork / Rollback on a failed timeline step → log entry appears in
  audit trail; no other state change.

Total test additions: ~8 new tests on top of the existing harness. Full
runtime target: under 5 minutes.

---

## 6. Out of scope (explicitly flagged)

- Real token / cost tracking from GHCP SDK telemetry — stays synthesized.
- Real Fork / Rollback via Durable sub-orchestration or replay API —
  buttons are log-only stubs.
- Multi-operator RBAC / per-role exception queues (slide 6 pattern) —
  single Finance Controller role throughout.
- Agents / Library / Economics functional pages — stub placeholders only.
- Real Workday / D365 / Maconomy / Payment integrations — MCPs stay mocked.
- OTEL exporting to Foundry's Tracing tab — requires
  `APPLICATIONINSIGHTS_CONNECTION_STRING`, optional.
- Dark/light theme toggle — one theme (light), hard switch.
- Domain change to HR hiring — POC1 stays Finance P2P.

---

## 7. Total budget

| Area | Est. |
|---|---|
| Backend (MCP events, economics, narrative, intervention options) | 3h |
| Light theme CSS migration | 1h |
| Shell chrome (App.tsx + nav) | 1h |
| Apex components (12 new components) | 4h |
| Dashboard rebuild | 2h |
| Tests | 1h |
| **Total** | **~12h** |

Work splits into non-overlapping packages after the theme lands: the
backend enrichments can run in parallel with the frontend component batch;
the dashboard rebuild and workflow detail rebuild touch different files.

---

## 8. Success criteria

1. The three screens (Dashboard / Workflow Detail / Execution Timeline)
   visually match the Apex mocks at structural level (layout, panels,
   action buttons, narrative card, phase ribbon).
2. Every value on every screen is derived from a real event in the
   pipeline; no static mock strings.
3. Full E2E harness (existing 12 + new 8) passes under 5 minutes.
4. A finance controller opening a demo-fail or demo-hitl scenario sees:
   phase ribbon lighting up phase-by-phase, narrative Exception Analysis
   populating as the exception fires, Intervention Protocols firing on
   click, Execution Timeline showing MCP calls as they happen.
5. Running `make up` from a cold repo boots this redesigned UI with no
   manual data seeding.
