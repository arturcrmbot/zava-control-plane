# Codebase Tour

How this repo hangs together at high level — POC1 (what's built) and POC2
(what's planned). Audience: a technical visitor walking through the code
for the first time. For acceptance-criteria status, defer to
[poc1-status.md](poc1-status.md). For per-tier code anchors, defer to
[ARCHITECTURE.md](ARCHITECTURE.md).

## The repo in one breath

A single-laptop demo of WPP's Apex Control Plane vision. POC1 is **expense
compliance** — pivoted from invoice-P2P on 2026-04-27 when the WPP brief
landed as expense compliance. Everything runs locally except the model API
(GitHub Copilot) and OTEL export (App Insights). No Azure deployment for
the demo.

## The three tiers — load-bearing diagram

```
Fleet Manager (FastAPI long-lived GHCP session)  ← always-on, 1 instance, OWNS exception queue
         ▲                                ▲
         │ triage-filtered events         │ SSE
         │
ExpenseClaimOrchestrator (Durable Functions)     ← 1 per claim, 7 phases, HITL waits at zero compute
         ▲
         │ activity per phase
         │
Per-phase Pregel graphs (ephemeral GHCP sessions) ← stateless, load skills + MCP tools per phase, exit
         │
Mock MCP servers (Workday/Concur/Maconomy)        ← Node + Express, 150 synthetic claims
```

Two GHCP **agent identities**: `finance-agent` (per-phase work, 12 skills)
and `fleet-manager-agent` (the always-on one). One `gh auth token` powers
both. The split matters — Fleet Manager doesn't run inside the Durable
orchestration. It runs in FastAPI and reacts to events the orchestrator
emits.

## Process map

| Process | Port | Contents |
|---|---|---|
| Vite | 5173 | React Control Plane UI — proxies `/api` + `/internal` to FastAPI |
| FastAPI (uvicorn) | 3001 | Fleet Manager session, simulator, REST routes, SSE hub |
| Azure Functions host (`func start`) | 7071 | `ExpenseClaimOrchestrator` + activities |
| Azurite | 10000-10002 | Durable state, checkpoints, timers |
| Mock MCPs | 4101-4103 | workday-mcp, concur-mcp, maconomy-mcp |

## POC1 — what does what

### Per-claim flow: 7 phases

Defined in [api/functions/workflows/expense_claim.py](../api/functions/workflows/expense_claim.py);
registered in [function_app.py](../function_app.py).

```
P1 Intake → P2 Classify → P3 Validate Receipt → P4 Route → verdict
                                                              ├ green  → P7 Audit (auto-approve)
                                                              ├ amber  → reviewer queue → P7
                                                              └ red    → P5 Notify → HITL (justification, 72h)
                                                                          → P6 Arbitrate → HITL (reviewer decision, 72h)
                                                                          → P7 Audit
```

Each phase activity wraps a typed Pregel graph in
[api/functions/graphs/](../api/functions/graphs/): `intake.py`,
`classify.py`, `receipt.py`, `route.py`, `notify.py`, `arbitrate.py`. Each
graph mixes three executor kinds:

- **Deterministic** — three-way match, threshold routing, decision recording.
- **Agent** — loads a `SKILL.md` via `GitHubCopilotAgent`. The skill's
  `allowed-tools` frontmatter decides what MCP tools the model can call;
  we don't prompt-stuff.
- **Validator** — guardrails between agent output and the next deterministic
  step. **The "bounded probabilism" edge** — when an agent picks something
  bad, the validator blocks and emits an exception event; Fleet Manager wakes.

### The 12 skills

In [api/server/skills/](../api/server/skills/), each a `SKILL.md` with
frontmatter (`model:`, `allowed-tools:`):

`field-extractor`, `line-item-extractor`, `rag-classifier`,
`receipt-validator`, `escalation-advisor`, `notification-composer`,
`anomaly-flagger`, `exception-classifier`, `resolution-recommender`,
`root-cause-explainer`, `arbitration`, `fleet-manager`.

### The 14 MCP tools

In [api/server/mcp_tools/](../api/server/mcp_tools/), each a `@define_tool`
with Pydantic params:

- **Claim/data**: `claim_lookup`, `claim_get_structured`,
  `claim_get_receipt`, `claim_summary`, `employee_history`
- **Policy**: `policy_search`, `policy_cite`, `dry_run_policy`
- **Precedents**: `precedents_search` — token-overlap retrieval over 53
  SSC precedents (AC #8)
- **Fleet Manager's toolkit**: `query_fleet`, `query_traces`,
  `compose_exception`, `propose_skill_amp`

### Fleet Manager — the bit people will ask about

Lives in [api/server/services/fleet_manager_service.py](../api/server/services/fleet_manager_service.py).
Flow:

1. Phase activities emit OTEL-shaped events to the in-process
   [EventBus](../api/server/services/event_bus.py).
2. [Triage](../api/server/services/triage.py) filters by `WAKE_TYPES`
   (6 wake-worthy kinds out of ~13).
3. [FleetManagerQueue](../api/server/services/fleet_manager_queue.py)
   debounces and coalesces; when the window closes, `send_and_wait`
   invokes the SDK session over the batch.
4. Session calls its 5 MCP tools, reasons, composes exceptions.
5. Reasoning + tool-call deltas stream through
   [SSEHub](../api/server/services/sse_hub.py) to the UI right rail at
   `/api/stream/fleet-manager`.

Coalescing matters — without it, the long-lived session would wake on
every event and burn tokens.

### UI

Vite/React. Routes in [web/client/routes/](../web/client/routes/):
`FleetDashboard`, `WorkflowDetail`, `ExceptionQueue`, `Analytics`,
`Evaluations`, `PolicyAndAutonomy`, `ReviewerQueue`. Components in
[web/client/components/](../web/client/components/) — most "wow" pieces
are `FleetManagerRail` (live SSE), `BulkHitlModal`, `WorkflowCard`
(exception-only surfacing), `OtelSpanTree`.

Shared types in [web/shared/types.ts](../web/shared/types.ts) mirror
Python [api/shared/types.py](../api/shared/types.py); smoke test enforces
the contract in [tests/e2e/smoke.spec.ts](../tests/e2e/smoke.spec.ts).

### Where POC1 stands today

13 acceptance criteria. Status table is in
[poc1-status.md §1](poc1-status.md#1-acceptance-criteria--status) — the
canonical source. **Don't duplicate it elsewhere.**

## POC2 — the plan

POC2 is **HR Talent Lifecycle**, 12-week sprint, the "Frontier POC". Hire
a Senior Data Engineer at a WPP USA agency. 5 humans, 4 timezones, 22
capability demos required from `spec.md` §4.

The plan ([poc2-status.md](poc2-status.md)) is **reuse the POC1 platform;
swap the domain.** ~75% of POC1 source artefacts are domain-agnostic
platform.

- **7 ✅** apply as-is (Control Plane shell, Durable runtime, Fleet
  Manager, OTEL, audit ledger, validators, bulk HITL)
- **9 🟡** rebind by swapping skill prompt / MCP endpoint / label
- **6 ❌** genuinely new: voice, multi-surface convergence, jurisdiction
  switching, crystallisation, Threadlight, A2A, AG-UI

Six work tracks (A–F) and a 12-week shape — see
[poc2-status.md §3 + §5](poc2-status.md#3-whats-left-to-build-and-how)
for the full breakdown.

## Talking points worth landing with the audience

A few things the code doesn't make obvious:

1. **Why three tiers and not "agents all the way down"** — Durable owns
   persistence and HITL waits (zero compute while parked). Agentic loops
   are stateless and ephemeral. Fleet Manager is a third, separate kind.
   Conflating them is the most common mistake.
2. **Validators are not bureaucracy** — they're the integration seam
   between agent reasoning and deterministic systems. Without them, an
   LLM picking a bad value silently breaks downstream state.
3. **Skills + `allowed-tools` frontmatter, not prompt-stuffing** — show
   one `SKILL.md` to make this concrete. The model decides which tool
   to call from the manifest, not from text we shoved into the prompt.
4. **POC2 is "platform stays, domain swaps"** — the laptop diagram for
   POC2 is structurally identical to POC1's. That's the differentiator
   vs hand-rolling each vertical.

## End-to-end exception path

If anyone asks live "show me an exception end-to-end":

```
simulator inject → Durable phase → validator blocks → EventBus
   → triage → FleetManager wakes → compose_exception → SSE
   → ExceptionQueue route → operator clicks → /internal/durable_event
   → orchestrator unblocks
```

## Where to dig next

| To learn | Read |
|---|---|
| Acceptance criteria + remaining work | [poc1-status.md](poc1-status.md) |
| Code-anchored architecture reference | [ARCHITECTURE.md](ARCHITECTURE.md) |
| How to run the demo | [DEMO.md](DEMO.md) |
| Local dev setup | [DEVELOPMENT.md](DEVELOPMENT.md) |
| Verbatim WPP brief | [poc1-brief.md](poc1-brief.md) |
| POC2 plan | [poc2-status.md](poc2-status.md) |
| What every doc in `docs/` is for | [README.md](README.md) (this directory) |
