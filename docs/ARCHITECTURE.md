# Architecture

## Three tiers

```
┌───────────────────────────────────────────────────────────────────┐
│                    Fleet Manager (FastAPI)                        │
│   always-on GHCP SDK session · 5 MCP tools · streams to UI rail   │
└──────────▲─────────────────────────────────────────────▲──────────┘
           │ triage-filtered events                      │ SSE
           │                                             │
┌──────────┴────────────────────┐            ┌───────────┴──────────┐
│  MAF Durable Workflow (func)  │            │   React UI (Vite)    │
│  InvoiceP2POrchestrator per   │◀──────────▶│   workflows · queue  │
│  invoice · 6 phase activities │   HTTP+SSE │   phases · traces    │
└──────────▲────────────────────┘            └──────────────────────┘
           │
           │ per-phase MAF Pregel graphs
           ▼
┌───────────────────────────────────────────────────────────────────┐
│             Mock MCP servers (Workday, D365, Maconomy, Payment)   │
└───────────────────────────────────────────────────────────────────┘
```

### 1. MAF Durable Workflow orchestration

One `InvoiceP2POrchestrator` generator per invoice, defined in
[api/functions/workflows/invoice_p2p.py](../api/functions/workflows/invoice_p2p.py)
and registered in [function_app.py](../function_app.py). Six phase
activities execute in sequence: **Intake → Validation → Routing →
Approval → Payment → Reconciliation**. Each activity wraps a per-phase
MAF Pregel graph (see tier 2).

Human-in-the-loop checkpoints use Azure Durable Functions'
`wait_for_external_event` — the orchestrator parks until the
[FastAPI `/internal/durable_event` route](../api/server/routes/internal_durable_event.py)
raises the matching event, which the exception UI triggers when an
operator approves or rejects from the queue.

Checkpointing is automatic via the Azure Durable runtime; state
persists in Azurite locally (`./azurite-data/`), in Azure Storage in
production. `make reset` wipes local state.

### 2. Per-phase MAF Pregel graphs

Each phase activity calls into a typed `WorkflowBuilder` graph in
[api/functions/graphs/](../api/functions/graphs/) (`intake.py`,
`validation.py`, `routing.py`, `approval.py`, `payment.py`,
`reconciliation.py`).

Graphs mix three executor kinds:
- **Deterministic** — [executors/deterministic/](../api/functions/graphs/executors/deterministic/):
  three-way match, GL lookup, payment-file generation, etc.
- **Agent** — [executors/agents/](../api/functions/graphs/executors/agents/):
  nine `finance-agent` skills (field extractor, GL coder, anomaly
  flagger, cost-centre assigner, exception classifier, resolution
  recommender, root-cause explainer, invoice classifier, line-item
  extractor). Each loads its `*.skill.md` via `GitHubCopilotAgent`.
- **Validator** — [executors/validators/](../api/functions/graphs/executors/validators/):
  guardrails between agent output and the next deterministic step
  (e.g. `validate_gl_active`, `validate_recommendation_authority`).

Validators are the "bounded probabilism" edge — when an agent picks a
bad value (e.g. GL-9999 inactive), the validator blocks and emits an
exception event; Fleet Manager wakes and composes a recoverable
exception card.

### 3. Fleet Manager (FastAPI-side)

The Fleet Manager is **not** part of the durable orchestration. It
runs inside the FastAPI process, as a single always-on GHCP SDK session
in [api/server/services/fleet_manager_service.py](../api/server/services/fleet_manager_service.py).

Flow:
1. Phase activities emit OTEL-shaped events to the in-process
   [EventBus](../api/server/services/event_bus.py).
2. [Triage](../api/server/services/triage.py) filters events by the
   `WAKE_TYPES` set (six wake-worthy kinds out of thirteen total).
3. A [FleetManagerQueue](../api/server/services/fleet_manager_queue.py)
   debounces and coalesces; when the window closes, `send_and_wait`
   invokes the SDK session over the batch.
4. The session calls MCP tools from
   [api/server/mcp_tools/](../api/server/mcp_tools/):
   `query_fleet`, `query_traces`, `compose_exception`,
   `propose_skill_amp`, `dry_run_policy`.
5. Reasoning + tool-call deltas stream through the
   [SSE hub](../api/server/services/sse_hub.py) to the UI right rail
   (`/api/stream/fleet-manager`).

One Hosted Agent identity (`fleet-manager-agent`) powers this; a
separate `finance-agent` identity (nine skills) powers tier 2.

## Runtime boundaries

| Process | Port | Contents |
|---|---|---|
| Vite dev/preview | 5173 | React UI; proxies `/api` and `/internal` to FastAPI |
| FastAPI | 3001 | Fleet Manager, simulator, REST, SSE hub |
| Azure Functions host | 7071 | Durable orchestrator + activities |
| Azurite | 10000-10002 | Durable Functions state backing |
| Mock MCPs | 4101-4104 | Workday, D365, Maconomy, Payment |

All inter-process traffic is HTTP; SSE runs FastAPI → UI.

## Event flow end-to-end

```
POST /api/simulator/inject
   │
   ▼
simulator → durable_client.start_new (→ Functions host :7071)
   │
   ▼
InvoiceP2POrchestrator — activity 1 (intake)
   │   ├── graphs/intake.py — doc_intelligence_extract → field_extractor → classifier
   │   └── emits `invoice.intake.*` events
   ▼
activity 2 (validation)
   │   ├── graphs/validation.py — three_way_match → validators
   │   └── emits `validation.*` events
   ▼
…routing → approval (HITL) → payment → reconciliation…
```

At each step the FastAPI-side EventBus receives events; triage +
queue decide whether to wake Fleet Manager. Exceptions land in
[api/server/routes/exceptions.py](../api/server/routes/exceptions.py),
surface in the UI exception queue, and flow back to the orchestrator
via `/internal/durable_event` when resolved.

## Shared types & events

- Python: [api/shared/types.py](../api/shared/types.py),
  [api/shared/events.py](../api/shared/events.py),
  [api/shared/policies.yaml](../api/shared/policies.yaml).
- TypeScript: [web/shared/types.ts](../web/shared/types.ts),
  [web/shared/events.ts](../web/shared/events.ts) — mirror the Python
  shapes so the UI speaks the same shape (camelCase) the API returns.

The contract is enforced by an e2e test in
[tests/e2e/smoke.spec.ts](../tests/e2e/smoke.spec.ts).

## Identities

| Identity | Where | Skills |
|---|---|---|
| `finance-agent` | Per-phase graph agent executors | `api/server/skills/*.skill.md` — 9 skills |
| `fleet-manager-agent` | Fleet Manager FastAPI session | `fleet-manager.skill.md` |

Both are GHCP Hosted Agents authenticated via the single `gh auth token`
at boot.

## Known limitations

- `sendEventPostUri` cache in [durable_client.py](../api/server/services/durable_client.py)
  is process-local memory — fine for single-worker uvicorn; needs
  Redis or DB backing for multi-worker.
- Activity functions in [api/functions/workflows/activities.py](../api/functions/workflows/activities.py)
  are sync wrappers around `asyncio.run(...)` — Azure Durable Functions
  Python doesn't natively support async activities.
- HTTP-triggered orchestration requires `func start` running; if the
  Functions host is down, the simulator logs "failed to schedule" and
  the workflow shows without an orchestration instance.
- OTEL export to Foundry Tracing (App Insights) only fires when
  `APPLICATIONINSIGHTS_CONNECTION_STRING` is set in `.env`.

## POC1 scope

- Finance P2P only. POC2 HR views are out of scope for this branch —
  architecture supports them via role switcher.
- No persistence across restarts (Fleet Manager + simulator state).
- No production auth — local single-operator implicit identity.
- Cuttable screens (Analytics, Evaluations) exist but lightweight.
