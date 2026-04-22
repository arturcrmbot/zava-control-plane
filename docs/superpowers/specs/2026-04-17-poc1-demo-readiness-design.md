# POC1 Demo-Readiness Design

**Status:** Draft for review
**Date:** 2026-04-17
**Scope:** `control-plane-py/` (Python POC1 backend) + `control-plane/` (React UI)
**Not in scope:** booting the stack end-to-end (deferred), Foundry Hosted Agent identity / Responses API adapter (Layer 2, future), four-eyes, rollback, Cosmos/Dataverse, real MCPs.

---

## 1. Context

POC1 code landed in commit `244df3a` but has never run end-to-end. Before attempting a boot-up, five demo-blocking issues need fixing in source so the boot is a real verification, not a moving target:

1. **Real OTEL tracing** into the Azure AI Foundry project's App Insights workspace — replacing the TS v1 in-memory `OtelSpan` fabrication and the Python backend's zero-span state
2. **HITL rejection path** — orchestrator currently ignores `decision == "reject"` and falls through to Payment
3. **Deterministic exception on suspend/block** — today an exception only exists if Fleet Manager's LLM decides to call `compose-exception`, which is non-deterministic and a live-demo risk
4. **Azurite reset script** — DF state accumulates across demo takes with no easy wipe
5. **Deterministic demo scenarios** — `demo-fail` depends on the LLM taking a prompt hint; there's no `demo-hitl` at all

Target outcome: when the stack is booted, the Foundry Tracing tab shows real agent runs; demo-fail and demo-hitl fire reliably; rejection visibly stops the workflow; exceptions appear instantly.

---

## 2. Item 1 — Real OTEL to Foundry's App Insights

### Goal
Every significant runtime event in the Python stack emits a real OpenTelemetry span, exported via Azure Monitor, visible in the Foundry project's Tracing tab with `gen_ai.*` semconv so Foundry renders agent runs natively.

### Design

**Single entry point** — `src/shared/otel.py`:

```python
def init_otel(service_name: str) -> None:
    """Idempotent. Called from FastAPI lifespan and function_app.py module-load."""
    conn = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not conn: return
    from azure.monitor.opentelemetry import configure_azure_monitor
    configure_azure_monitor(connection_string=conn,
                            resource_attributes={"service.name": service_name})
    # Optional: FastAPIInstrumentor / HTTPXClientInstrumentor if not auto-wired
```

**Wired once in two places:**
- `src/server/main.py` lifespan: `init_otel("control-plane-server")` before `app_state.fm.start()`
- `function_app.py` module top: `init_otel("control-plane-functions")` before `app = df.DFApp(...)`

**Same `APPLICATIONINSIGHTS_CONNECTION_STRING` set in both** `.env` (for FastAPI) and `local.settings.json` (for Functions worker). Functions picks it up automatically → **DF orchestrator + activity spans go to Foundry for free**, no code change.

**Executor spans** — `src/functions/graphs/_tracked_executor.py`:
- Wrap `await self._fn(input)` in `tracer.start_as_current_span(f"executor.{self._name}")`
- Attributes: `wpp.workflow.id`, `wpp.workflow.instance_id`, `wpp.workflow.phase` (from input), `wpp.executor.type`, `wpp.executor.name`
- If `self._executor_type == "agent"`: also set `gen_ai.agent.name = "finance-agent"`
- If `validator` returns `ok is False`: set span status = ERROR, add event `validator.blocked` with reason
- Exception in `fn`: record on span, re-raise

**Agent generate-content spans** — `src/functions/graphs/executors/agents/_wrapper.py`:
- Wrap `await agent.run(prompt)` in `tracer.start_as_current_span("gen_ai.generate_content")`
- Attributes: `gen_ai.system = "github_copilot"`, `gen_ai.request.model = model`, `gen_ai.agent.name = "finance-agent"`, `wpp.skill = skill_name`
- Response text added as span event (truncated to 4KB)
- Extract token counts from response object if exposed by the SDK; attach as `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens`

**GHCP SDK session event → OTEL bridge** — applies in two places:
- `_wrapper.py`: subscribe `session.on(...)` for the lifetime of the call; `TOOL_EXECUTION_START` opens a child span `tool.{name}` keyed by `tool_call_id`; `TOOL_EXECUTION_COMPLETE` closes it with status from `.success`
- `fleet_manager_service.py`: same bridge on the always-on session; spans attach to the current reasoning span opened by `_process_batch`

**Fleet Manager MCP tool spans** — each `@define_tool` in `src/server/mcp_tools/*.py` wrapped in `tracer.start_as_current_span(f"tool.server.{name}")`. Shared helper to avoid per-tool boilerplate.

**Fleet Manager reasoning span** — `_process_batch` opens a parent span `gen_ai.agent.run` with `gen_ai.agent.name = "fleet-manager-agent"` + attributes `wpp.fleet_manager.batch_size`, `wpp.fleet_manager.workflow_ids`.

**Cross-process propagation** — `opentelemetry-instrumentation-httpx` auto-injects `traceparent` on outbound calls; `opentelemetry-instrumentation-fastapi` extracts inbound. `webhook.py`'s `httpx.post` → FastAPI `/internal/durable-event` becomes one continuous trace.

### Files

Add / change:
- `pyproject.toml` — add `azure-monitor-opentelemetry`, `opentelemetry-instrumentation-httpx`, `opentelemetry-instrumentation-fastapi`
- `.env.example`, `local.settings.json.example` — add `APPLICATIONINSIGHTS_CONNECTION_STRING`
- **New**: `src/shared/otel.py` — `init_otel(service_name)`
- `src/server/main.py` — call `init_otel` in lifespan
- `function_app.py` — call `init_otel` at module load
- `src/functions/graphs/_tracked_executor.py` — add span wrap + attrs + error mapping
- `src/functions/graphs/executors/agents/_wrapper.py` — add `gen_ai.generate_content` span + session→OTEL bridge
- `src/server/services/fleet_manager_service.py` — add reasoning span + session→OTEL bridge
- **New**: `src/server/mcp_tools/_otel.py` — shared `@traced_tool` decorator
- `src/server/mcp_tools/*.py` — apply the decorator

### Acceptance

- Run any workflow end-to-end → Foundry Tracing tab shows a single trace rooted at `Functions.InvoiceP2POrchestrator` with:
  - Child span per activity (`intake_activity_trigger`, etc.) — emitted by DF host for free
  - Inside each, `executor.*` spans with `gen_ai.agent.name = "finance-agent"` on agent nodes
  - Inside agent nodes, `gen_ai.generate_content` + nested `tool.*` spans
  - FastAPI webhook span chained via `traceparent`
- Fleet Manager's reasoning trace visible as a separate trace rooted at `gen_ai.agent.run` with `gen_ai.agent.name = "fleet-manager-agent"`

---

## 3. Item 2 — HITL rejection path

### Goal
When an operator rejects at Approval, the orchestration stops at Approval, the workflow is marked `rejected`, and Payment + Reconciliation do not run.

### Design

**Canonical decision values** in `src/shared/constants.py`:

```python
DECISION_APPROVED = {"approve", "approved", "ok"}
DECISION_REJECTED = {"reject", "rejected", "deny", "denied"}
```

**Orchestrator branch** in `src/functions/workflows/invoice_p2p.py`, replacing lines 62–78:

```python
decision = decision_event.result
decision_type = (decision.get("decision") if isinstance(decision, dict) else "").lower()

if decision_type in DECISION_REJECTED:
    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.rejected",
        "payload": {"by": decision.get("resolved_by"), "reason": "operator rejected"}
    })
    return {"status": "rejected", "phase": "Approval", "decision": decision}

# else: approved path (existing logic — ledger entry + resumed checkpoint)
```

**Webhook receiver** in `src/server/routes/internal_durable_event.py`:
- `workflow.rejected` → emit `FleetEvent(type="workflow.resolved", workflow_id=wid, resolution="rejected")`, update store: `w.status = "failed"`, `w.current_phase = "Approval"`

**UI** — Workflow Detail and OrchestrationView already handle terminal states; "rejected" gets a red indicator on Approval and "Rejected by <operator>" on the Overview card. Minor CSS, no new component.

**Input validation** — `exceptions.py` bulk-resolve accepts `resolution` enum-validated via Pydantic Literal: `Literal["approve", "reject", "escalate"]`. Unknown values 400.

### Files
- **New**: `src/shared/constants.py`
- `src/functions/workflows/invoice_p2p.py` — add rejection branch
- `src/server/routes/internal_durable_event.py` — handle `workflow.rejected`
- `src/server/routes/exceptions.py` — validate resolution enum
- `control-plane/src/client/routes/WorkflowDetail.tsx` — red state for rejection (small)
- `control-plane/src/client/components/OrchestrationView.tsx` — red marker on Approval step when rejected

### Acceptance
- `POST /api/exceptions/bulk-resolve` with `resolution: "reject"` → orchestration exits at Approval within 2s
- Workflow record shows `status: "failed"`, `current_phase: "Approval"`
- Payment and Reconciliation activities never fire (verify in Foundry trace: only 4 activity spans, not 6)

---

## 4. Item 3 — Deterministic exception on suspend / block

### Goal
The moment Approval suspends or a validator blocks, a canonical Exception record exists in the store — composed by the server, not the LLM. Fleet Manager's reasoning can still augment it later, but the queue never depends on an LLM call firing.

### Design

**New service** `src/server/services/exception_factory.py`:

```python
def compose_hitl_exception(store, workflow_id: str, reason: str) -> Exception:
    # severity=medium, category=threshold-exceeded, composed_by="deterministic",
    # options=[approve, reject], empty related_policy_refs, confidence=1.0

def compose_validator_exception(store, workflow_id: str, validator: str, reason: str) -> Exception:
    # severity=high, category=validator-blocked, composed_by="deterministic"
```

Both return the persisted Exception.

**Webhook receiver** — in `internal_durable_event.py`, extend the `kind` dispatch:
- `suspended` → call `compose_hitl_exception(...)` before emitting `workflow.hitl.requested`
- `validator.blocked` → call `compose_validator_exception(...)` before emitting `workflow.exception.detected`

**Fleet Manager de-dup / augmentation** — rework `src/server/mcp_tools/compose_exception.py`:
- Before creating a new record, look up open exception for `workflow_id`
- If found: merge — update `recommendation`, append to `related_policy_refs`, set `composed_by = "fleet-manager-augmented"`, keep original id
- If not found: create (existing behaviour) with `composed_by = "fleet-manager"`

**Skill update** — `src/server/skills/fleet-manager.skill.md`: add a line noting "An exception is already created for every suspended or validator-blocked workflow. Your job is to *enrich* it — better recommendation, relevant policy refs — not recreate it. Calling `compose-exception` on a workflow that already has one will merge."

### Files
- **New**: `src/server/services/exception_factory.py`
- `src/server/routes/internal_durable_event.py` — call factory
- `src/server/mcp_tools/compose_exception.py` — merge-if-exists
- `src/server/skills/fleet-manager.skill.md` — augmentation note
- `tests/unit/test_exception_factory.py` — new

### Acceptance
- Inject `demo-hitl` → within 30s an Exception exists in `/api/exceptions/` with `composed_by: "deterministic"`, `category: "threshold-exceeded"`, regardless of Fleet Manager state
- When Fleet Manager reasons later and calls `compose-exception`, same exception id is retained, `composed_by` becomes `"fleet-manager-augmented"`, recommendation updated
- Inject `demo-fail` → exception exists within 5s of validator block, category `"validator-blocked"`

---

## 5. Item 4 — Azurite reset

### Goal
One command wipes DF state between demo takes.

### Design

`Makefile` target:

```make
reset:
	docker compose stop azurite
	rm -rf azurite-data/*
	docker compose up -d azurite
	@echo "azurite reset — restart func + uvicorn"
```

Full-stack reset documented in README: `make reset` wipes DF, then Ctrl-C + restart `func start` and `uvicorn` to clear in-memory state.

### Files
- `Makefile`
- `README.md` — reset section

### Acceptance
- `make reset` completes in <10s, `azurite-data/` is empty, Azurite container running on 10000–10002

---

## 6. Item 5 — Deterministic demo scenarios

### Goal
Two scenarios injectable via API (and via UI Dev Panel) that fire reliably on every invocation:
- `demo-fail` — validator blocks at Routing, exception in queue, Fleet Manager augments, visible in right rail
- `demo-hitl` — Approval suspends, exception in queue, operator resolves via UI, workflow resumes or stops (depending on approve/reject)

### Design

**Force flags on the workflow** — extend the orchestration payload (not the persisted Workflow type; just passed through `context.get_input()`):

```python
payload = {
    "workflow_id": ..., "vendor": ..., "invoice": ..., "agency": ..., "jurisdiction": ...,
    "force_gl_fail": bool,   # NEW
    "force_hitl": bool,      # NEW
}
```

**Simulator** — `src/server/services/simulator_orchestrator.py`:

```python
async def spawn_workflow(scenario: str | None = None) -> str:
    ...
    payload = {...}
    if scenario == "demo-fail":
        payload["force_gl_fail"] = True
    elif scenario == "demo-hitl":
        payload["force_hitl"] = True
        # Also bump invoice amount well above any reasonable threshold
        payload["invoice"]["amount"] = 12500.00
```

**`demo-fail` determinism** — `src/functions/graphs/executors/agents/agent_gl_coder.py`:

```python
async def execute(input: dict) -> dict:
    if input.get("force_gl_fail"):
        return {"gl_decision": {"gl_account_id": "GL-9999", "rationale": "demo-fail injection"}}
    # existing LLM path
```

Removes "DEMO_FAIL" vendor-name hack from `synthetic_data.py`. The validator `validate_gl_active` then deterministically blocks because GL-9999 isn't in `ACTIVE_GLS`.

**`demo-hitl` determinism** — `src/functions/graphs/executors/deterministic/apply_threshold_routing.py`:

```python
async def execute(input: dict) -> dict:
    if input.get("force_hitl"):
        return {"requires_hitl": True, "reason": "demo-hitl injection"}
    # existing threshold logic
```

**Simulator route** — `src/server/routes/simulator.py` already accepts `scenario`; verify pass-through to `spawn_workflow`.

**UI Dev Panel** — new `control-plane/src/client/components/DevPanel.tsx`:
- Collapsible panel top-right of Fleet Dashboard, behind `Dev` toggle
- Buttons: `Inject normal`, `Inject demo-fail`, `Inject demo-hitl`, `Reset Azurite` (calls a new server route `/api/dev/reset` that shells out — or leave as Makefile-only and just show instructions)
- Hidden in production builds via `import.meta.env.DEV`

### Files
- `src/server/services/simulator_orchestrator.py` — scenario param → force flags
- `src/server/services/synthetic_data.py` — drop DEMO_FAIL vendor-name hack
- `src/functions/graphs/executors/agents/agent_gl_coder.py` — short-circuit on `force_gl_fail`
- `src/functions/graphs/executors/deterministic/apply_threshold_routing.py` — short-circuit on `force_hitl`
- `src/server/routes/simulator.py` — verify scenario pass-through
- **New**: `control-plane/src/client/components/DevPanel.tsx`
- `control-plane/src/client/routes/FleetDashboard.tsx` — mount DevPanel

### Acceptance
- `POST /api/simulator/inject -d '{"scenario":"demo-fail"}'` → within 30s: workflow exists with a validator-blocked exception in `/api/exceptions/`. No LLM variance.
- `POST /api/simulator/inject -d '{"scenario":"demo-hitl"}'` → within 30s: workflow in `awaiting_hitl` status, exception in queue with `category: "threshold-exceeded"`.
- Both reproducible 10/10 times.

---

## 7. Implementation order

1. **Item 1 (tracing)** — biggest, touches most files; do first so everything below is observable from day one
2. **Item 2 (rejection)** — small, standalone
3. **Item 3 (deterministic exception)** — needs rejection types finalised first
4. **Item 4 (reset)** — trivial, do anytime
5. **Item 5 (demo scenarios)** — depends on 3 (exception-on-suspend guarantees the demo doesn't depend on LLM for the exception)

Each item is independently committable.

---

## 8. Out of scope (flagged, not done)

- Booting the stack end-to-end — next task
- Foundry Hosted Agent identity / Responses API adapter — Layer 2, future
- Four-eyes / dual-control approval — future
- Compensating actions on rollback — future
- Cosmos DB / Dataverse persistence — future
- Real Workday / D365 / Maconomy / payment integrations — future
- Parallel fan-out in Routing graph — future
- Sub-agent delegation in field extractor — future
- GHCP SDK `onPreToolUse` hook wrapping `submit_payment` as a real tool call — future
- Multi-worker uvicorn fix for `sendEventPostUri` cache — future
- Functions Core Tools version check / `make doctor` — future

---

## 9. Success criteria

When all five items land:

1. Python stack emits real OTEL with `gen_ai.*` semconv; a single workflow trace spans orchestrator → activities → MAF executors → agent generate-content → tool calls, continuous across processes.
2. Foundry project's Tracing tab shows `finance-agent` and `fleet-manager-agent` runs natively.
3. Operator rejection stops the workflow at Approval; Payment and Reconciliation never fire.
4. Exceptions appear in the queue the moment a workflow suspends or a validator blocks — zero LLM dependency.
5. Azurite resets in one command between takes.
6. `demo-fail` and `demo-hitl` fire deterministically on every injection.

The stack is now boot-ready and demo-grade. Boot-up shakedown is the next spec.
