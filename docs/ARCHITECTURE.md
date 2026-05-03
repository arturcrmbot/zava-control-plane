# Architecture

Canonical reference for how the codebase hangs together. Three live
domains run on a single substrate (skills + MCP tools + harness +
governance); the orchestrator class and the phase graphs change per
domain, the rest is reused. For acceptance-criteria status and the
per-claim flow, see [poc1-status.md](poc1-status.md); for the hiring
flow, see [poc2-status.md](poc2-status.md).

## Three tiers

```
┌───────────────────────────────────────────────────────────────────┐
│                    Fleet Manager (FastAPI)                        │
│   always-on GHCP SDK session · MCP tools · streams to UI rail     │
└──────────▲─────────────────────────────────────────────▲──────────┘
           │ triage-filtered events                      │ SSE
           │                                             │
┌──────────┴────────────────────┐            ┌───────────┴──────────┐
│  MAF Durable Workflows (func) │            │  React UIs (Vite)    │
│  ExpenseClaimOrchestrator     │◀──────────▶│  Control Plane :5173 │
│  HiringOrchestrator           │   HTTP+SSE │  Candidate Portal    │
│  FleetTravelPreapproval…      │            │  :5174               │
│  …per-domain phase activities │            │  Blueprint :5175 *   │
└──────────▲────────────────────┘            └──────────────────────┘
           │
           │ per-phase MAF Pregel graphs
           ▼
┌───────────────────────────────────────────────────────────────────┐
│   Mock MCP servers — finance (4101-4103) + HR/comms (4201-4207)   │
└───────────────────────────────────────────────────────────────────┘

* Blueprint also ships as a single container to Azure Container Apps;
  the deployed image renders the editorial page only and does NOT carry
  the durable runtime or the live event bus. See
  blueprint-microsite-contributor-guide.md §Deploying to Azure.
```

### 1. MAF Durable Workflow orchestration

One Durable orchestrator generator class per domain:

| Domain | Orchestrator | File |
|---|---|---|
| Expense compliance (POC1) | `ExpenseClaimOrchestrator` | [api/functions/workflows/expense_claim.py](../api/functions/workflows/expense_claim.py) |
| Hiring (POC2) | `HiringOrchestrator` | [api/functions/workflows/hiring.py](../api/functions/workflows/hiring.py) |
| Fleet travel pre-approval | `FleetTravelPreapprovalOrchestrator` | [api/functions/workflows/fleet_travel_preapproval.py](../api/functions/workflows/fleet_travel_preapproval.py) |

All are registered in [function_app.py](../function_app.py). Each
orchestrator runs a sequence of phase activities; each activity wraps a
typed MAF Pregel graph (see tier 2). Per-domain flow charts:

- POC1: [poc1-status.md §2](poc1-status.md#2-architecture)
- POC2 hiring: [poc2-status.md §2](poc2-status.md#2-architecture)

Human-in-the-loop checkpoints use Azure Durable Functions'
`wait_for_external_event` — the orchestrator parks until the
[FastAPI `/internal/durable_event` route](../api/server/routes/internal_durable_event.py)
raises the matching event. Events come from the operator UI, the
candidate portal, persona webhook callbacks, or the
[persona_responder](../api/server/services/persona_responder.py)
(autonomous demo mode).

Checkpointing is automatic via the Azure Durable runtime; state
persists in Azurite locally (`./azurite-data/`), in Azure Storage in
production. `make reset` wipes local state.

### 2. Per-phase MAF Pregel graphs

Each phase activity calls into a typed `WorkflowBuilder` graph in
[api/functions/graphs/](../api/functions/graphs/). Per-domain phase
files live alongside each other (POC1 expense files, POC2 hiring files,
and now `fleet_travel_preapproval_*.py` for the first composed domain).

Graphs mix three executor kinds:
- **Deterministic** — [executors/deterministic/](../api/functions/graphs/executors/deterministic/):
  document intelligence extract, threshold routing, decision recording, etc.
- **Agent** — [executors/agents/](../api/functions/graphs/executors/agents/):
  per-domain agent identities loaded via `GitHubCopilotAgent`. Skills live in
  [api/server/skills/](../api/server/skills/) (walked at runtime — no
  hand-maintained list).
- **Validator** — [executors/validators/](../api/functions/graphs/executors/validators/):
  guardrails between agent output and the next deterministic step
  (e.g. `validate_required_fields`, `validate_recommendation_authority`,
  `validate_fleet_travel_preapproval_policy_fit_check`).

Validators are the "bounded probabilism" edge — when an agent picks a
bad value, the validator blocks and emits an exception event; Fleet
Manager wakes and composes a recoverable exception card.

### 3. Fleet Manager (FastAPI-side)

The Fleet Manager is **not** part of the durable orchestration. It
runs inside the FastAPI process, as a single always-on GHCP SDK session
in [api/server/services/fleet_manager_service.py](../api/server/services/fleet_manager_service.py).

Flow:
1. Phase activities emit OTEL-shaped events to the in-process
   [EventBus](../api/server/services/event_bus.py), under the
   `durable.*` event vocabulary defined in [api/shared/events.py](../api/shared/events.py).
2. [Triage](../api/server/services/triage.py) filters events by the
   `WAKE_TYPES` set.
3. A [FleetManagerQueue](../api/server/services/fleet_manager_queue.py)
   debounces and coalesces; when the window closes, `send_and_wait`
   invokes the SDK session over the batch.
4. The session calls MCP tools from
   [api/server/mcp_tools/](../api/server/mcp_tools/) (walked at runtime).
5. Reasoning + tool-call deltas stream through the
   [SSE hub](../api/server/services/sse_hub.py) to the UI right rail
   (`/api/stream/fleet-manager`).

The same bus also feeds two other consumers: the
[blueprint stream](../api/server/routes/blueprint.py) (`/api/blueprint/stream`)
which translates events into the visual vocabulary the microsite
mind-map understands, and the
[blueprint_recorder](../api/server/services/blueprint_recorder.py)
which captures `durable.*` events to JSONL files under
[data/blueprint-recordings/](../data/blueprint-recordings/) for replay
in the deployed microsite.

GHCP **agent identities**: one per domain (`finance-agent`,
`hiring-agent`, etc.) for per-phase work, plus `fleet-manager-agent`
for the always-on session. All authenticated via the single
`gh auth token` at boot.

## Runtime boundaries

| Process | Port | Contents |
|---|---|---|
| Vite — Control Plane UI | 5173 | Domain-neutral operator surface; proxies `/api` + `/internal` to FastAPI |
| Vite — Candidate Portal | 5174 | POC2 candidate-facing app + recruiter view |
| Vite — Blueprint microsite | 5175 | Editorial page + live observatory (local dev) |
| FastAPI | 3001 | Fleet Manager, simulator, REST, SSE hub, blueprint composition + stream |
| Azure Functions host | 7071 | All Durable orchestrators + activities |
| Azurite | 10000-10002 | Durable Functions state backing |
| Mock MCPs (POC1 finance) | 4101-4103 | workday-mcp, concur-mcp, maconomy-mcp |
| Mock MCPs (POC2 HR + comms) | 4201-4207 | greenhouse, linkedin, workday-hr, graph, servicenow, acs, heygen |

All inter-process traffic is HTTP; SSE runs FastAPI → UI.

## Personae and the autonomous responder

The substrate ships with a set of personae under
[api/server/personae/](../api/server/personae/) (`claim_submitter`,
`finance_bp`, `line_manager`, `ssc_reviewer`, `recruiter`, `hr_bp`,
`candidate`). The
[persona_responder](../api/server/services/persona_responder.py) closes
HITL gates by acting as the appropriate persona on an `AUTO_CLOSE`
allow-list — a DRY responder that drives the autonomous demo loop.
Combined with the simulator's domain-aware ramp loop
([simulator_orchestrator.py](../api/server/services/simulator_orchestrator.py),
default ON), the demo runs itself.

## Event flow end-to-end

```
POST /api/simulator/inject   (or domain-aware ramp loop)
   │
   ▼
simulator → durable_client.start_new (→ Functions host :7071)
   │
   ▼
<Domain>Orchestrator — phase activity
   │   ├── per-phase graph (deterministic + agent + validator)
   │   └── emits `durable.*` events on the bus
   ▼
…HITL waits resolve via UI, portal, persona_responder, or external webhook…
```

At each step the FastAPI-side EventBus receives events; triage +
queue decide whether to wake Fleet Manager; the blueprint stream and
recorder also subscribe. Exceptions land in
[api/server/routes/exceptions.py](../api/server/routes/exceptions.py),
surface in the UI exception queue, and flow back to the orchestrator
via `/internal/durable_event` when resolved.

## The blueprint microsite — separate cloud surface

The microsite (`web/blueprint/`) is the editorial layer that visualises
the substrate. It runs locally on `:5175` against the live FastAPI for
development; it ships as a single container to Azure Container Apps for
sharing the pitch. **The deployed container is intentionally Scope A —
the page only.** No durable runtime, no live event bus, no MCPs run in
the deployed image; the live observatory replays events from the JSONL
recordings baked in at build time. The full deploy procedure, image
contents, and resource layout live in
[blueprint-microsite-contributor-guide.md §Deploying to Azure](blueprint-microsite-contributor-guide.md#deploying-to-azure).

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
| `<domain>-agent` (finance, hiring, …) | Per-phase graph agent executors | [api/server/skills/](../api/server/skills/) — walked at runtime |
| `fleet-manager-agent` | Fleet Manager FastAPI session | [skills/fleet-manager/SKILL.md](../api/server/skills/fleet-manager/SKILL.md) |

All authenticated via the single `gh auth token` at boot.

## Composing a new domain

The [`compose-domain`](superpowers/skills/compose-domain/SKILL.md)
meta-skill (now at v3) graduates a new domain from a YAML brief into a
working orchestrator + activities + graphs + skills + personae + MCP
tools, all registered with the substrate. The canonical existence
proof is `fleet-travel-preapproval`, graduated from
[fleet-travel-preapproval-brief.yaml](superpowers/specs/fleet-travel-preapproval-brief.yaml).
Three more briefs are ready to go.

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

## Scope and out-of-scope

- Three domains live in `main` (expense + hiring + fleet travel
  pre-approval). The platform layer (Fleet Manager, Durable runtime,
  validators, OTEL, audit ledger, bulk HITL, blueprint observatory) is
  intentionally domain-agnostic so additional domains reuse it.
- No persistence across restarts (Fleet Manager + simulator state).
- No production auth — local single-operator implicit identity.
- Cuttable screens (Analytics, Evaluations) exist but lightweight.
