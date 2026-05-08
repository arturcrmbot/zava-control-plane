# Codebase Tour

How this repo hangs together at high level — the substrate, the domains
running on it, and the editorial layer that visualises both. Audience: a
technical visitor walking through the code for the first time. For
acceptance-criteria status, defer to [poc1-status.md](poc1-status.md) and
[poc2-status.md](poc2-status.md). For per-tier code anchors, defer to
[ARCHITECTURE.md](ARCHITECTURE.md).

## The repo in one breath

A composable agentic substrate (skills + MCP tools + harness +
governance) running on a single laptop, with **eight business domains**
composed on top of it:

- **POC1 — finance expense compliance** (7 phases, 13 ACs) — pivoted from
  invoice-P2P on 2026-04-27.
- **POC2 — HR talent lifecycle** (10 phases, 22 capabilities) — built
  out across late April / early May, demo-ready.
- **Six fleet-* domains** graduated end-to-end by the
  [`compose-domain`](superpowers/skills/compose-domain/SKILL.md)
  meta-skill — `travel-preapproval` (v1, the existence proof) plus
  `vendor-kyc`, `employee-onboarding`, `it-access-request`,
  `contract-renewal`, `perf-review` (v3, 2026-05-03). All eight reach
  Fleet-Manager substrate parity per the
  [feature-fleet-domain-substrate-1](../plan/feature-fleet-domain-substrate-1.md)
  plan: registered in the central [`api/shared/domains.py`](../api/shared/domains.py)
  registry, upserted into `StateStore`, resolvable from the operator
  exception queue, and cycling per-domain seed corpora through the
  autonomous demo loop.

Everything runtime runs locally except the model API (GitHub Copilot)
and the optional OTEL export (App Insights). One thing is in the cloud:
the [blueprint microsite](../web/blueprint/) ships as a single container
to Azure Container Apps for sharing the pitch — see the
[contributor guide](blueprint-microsite-contributor-guide.md#deploying-to-azure).

## The three tiers — load-bearing diagram

The shape is the same regardless of domain. The orchestrator class and
the phase graphs change; the rest is reused.

```
Fleet Manager (FastAPI long-lived GHCP session)  ← always-on, 1 instance, OWNS exception queue
         ▲                                ▲
         │ triage-filtered events         │ SSE
         │
<Domain>Orchestrator (Durable Functions)         ← 1 per work item, N phases, HITL waits at zero compute
         ▲                                          (8 orchestrators — see api/shared/domains.py)
         │ activity per phase
         │
Per-phase Pregel graphs (ephemeral GHCP sessions) ← stateless, load skills + MCP tools per phase, exit
         │
Mock MCP servers                                  ← Node + Express; 3 finance + 7 HR/comms (POC2)
                                                    — fleet-* domains use deterministic stubs in api/server/mcp_tools/
```

Two GHCP **agent identities**: `finance-agent` / `hiring-agent` /
`<domain>-agent` (per-phase work) and `fleet-manager-agent` (the always-on
one). One `gh auth token` powers all of them. The split matters — Fleet
Manager doesn't run inside the Durable orchestration. It runs in FastAPI
and reacts to events the orchestrators emit.

## Process map

| Process | Port | Contents |
|---|---|---|
| Vite — Control Plane UI | 5173 | Domain-neutral operator surface; proxies `/api` + `/internal` to FastAPI |
| Vite — Candidate Portal | 5174 | POC2 candidate-facing app (`/apply`, `/portal`, `/screen`, `/book`) + recruiter view (`/recruiter`) |
| Vite — Blueprint microsite | 5175 | Editorial page + live observatory (`web/blueprint/`); local dev only — production deploys to Azure Container Apps |
| FastAPI (uvicorn) | 3001 | Fleet Manager session, simulator, REST routes, SSE hub, blueprint composition + stream |
| Azure Functions host (`func start`) | 7071 | All Durable orchestrators + activities |
| Azurite | 10000-10002 | Durable state, checkpoints, timers |
| Mock MCPs (POC1 finance) | 4101-4103 | workday-mcp, concur-mcp, maconomy-mcp |
| Mock MCPs (POC2 HR + comms) | 4201-4207 | greenhouse, linkedin, workday-hr, graph, servicenow, acs, heygen |

## The domains — what does what

### POC1 — Expense compliance: 7 phases

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

Phase graphs live in [api/functions/graphs/](../api/functions/graphs/)
(`intake_expense.py`, `classify.py`, `receipt.py`, `route.py`,
`notify.py`, `arbitrate.py`).

### POC2 — Hiring: 10 phases

Defined in [api/functions/workflows/hiring.py](../api/functions/workflows/hiring.py).
Three HITL gates: Phase 1 (Budget · Finance BP), Phase 7 (Interview ·
three sequential waits — recruiter invite → candidate booking → recruiter
post-interview decision), Phase 9 (Offer · candidate accept/decline).
Full walkthrough in [poc2-quick-demo.md](poc2-quick-demo.md); status table
in [poc2-status.md](poc2-status.md).

### Six fleet-* domains — the compose-domain output

Graduated end-to-end by the [`compose-domain`](superpowers/skills/compose-domain/SKILL.md)
meta-skill from YAML briefs (one per domain, under
[`superpowers/specs/fleet-*-brief.yaml`](superpowers/specs/)). The
existence proof for the substrate's central claim — that *the act of
building the next agent is itself agentic*.

| Domain | Orchestrator file | Phases | Personae at HITL gates |
|---|---|---|---|
| Travel pre-approval | [`fleet_travel_preapproval.py`](../api/functions/workflows/fleet_travel_preapproval.py) | 3 | `line_manager` |
| Vendor onboarding & KYC | [`fleet_vendor_kyc.py`](../api/functions/workflows/fleet_vendor_kyc.py) | 4 | `vendor_kyc_finance_bp` |
| Employee onboarding | [`fleet_employee_onboarding.py`](../api/functions/workflows/fleet_employee_onboarding.py) | 4 | `onboarding_it_admin` |
| IT access request | [`fleet_it_access_request.py`](../api/functions/workflows/fleet_it_access_request.py) | 5 | `it_access_line_manager`, `it_access_it_admin` |
| Contract renewal | [`fleet_contract_renewal.py`](../api/functions/workflows/fleet_contract_renewal.py) | 5 | `contract_finance_bp`, `contract_line_manager` |
| Performance review | [`fleet_perf_review.py`](../api/functions/workflows/fleet_perf_review.py) | 5 | `perf_review_hr_bp`, `perf_review_line_manager` |

The substrate-parity work is captured in
[`plan/feature-fleet-domain-substrate-1.md`](../plan/feature-fleet-domain-substrate-1.md):
six shipped phases that brought every fleet-* domain to first-class
standing alongside POC1/POC2 — registry, generalised `Workflow.payload`,
generalised resolve route, FM domain awareness, per-domain seed
corpora (≥40 records each, scenario-tagged), and the persona
`escalate` verdict.

### How a phase graph is built (universal pattern)

Each phase activity wraps a typed Pregel graph in
[api/functions/graphs/](../api/functions/graphs/). Each graph mixes three
executor kinds:

- **Deterministic** — three-way match, threshold routing, decision recording.
- **Agent** — loads a `SKILL.md` via `GitHubCopilotAgent`. The skill's
  `allowed-tools` frontmatter decides what MCP tools the model can call;
  we don't prompt-stuff.
- **Validator** — guardrails between agent output and the next deterministic
  step. **The "bounded probabilism" edge** — when an agent picks something
  bad, the validator blocks and emits an exception event; Fleet Manager wakes.

### Skills, MCP tools, personae — walked at runtime

The substrate doesn't pin counts; everything is walked from disk:

- **Skills** — every `SKILL.md` under [api/server/skills/](../api/server/skills/).
  Authored via the [author-runtime-skill](superpowers/skills/author-runtime-skill/SKILL.md) meta-skill.
- **MCP tools** — every `@define_tool` in [api/server/mcp_tools/](../api/server/mcp_tools/),
  including the Fleet Manager's toolkit (`query_fleet`, `query_traces`,
  `compose_exception`, `propose_skill_amp`, `audit_query`,
  `query_economics`, `query_reviewer_decisions`). Authored via
  [author-mcp-tool](superpowers/skills/author-mcp-tool/SKILL.md).
- **Personae** — every `SKILL.md` under [api/server/personae/](../api/server/personae/)
  (15 today across POC1 + POC2 + the six fleet-* domains: e.g.
  `claim_submitter`, `ssc_reviewer`, `recruiter`, `hr_bp`,
  `vendor_kyc_finance_bp`, `it_access_it_admin`,
  `contract_finance_bp`, `perf_review_hr_bp`). Drive the autonomous
  responder so HITL gates close themselves during the demo — each
  persona's `decision_policy` block returns one of three verdicts:
  `approve`, `reject`, or `escalate` (the latter leaves the Durable
  gate open and emits a `workflow.hitl.escalated` event for the FM).
  Authored via [author-persona](superpowers/skills/author-persona/SKILL.md).

The live counts and graph of how they all connect surface at
`GET /api/blueprint/composition` and render on the [blueprint
microsite](../web/blueprint/) — see
[blueprint-microsite-contributor-guide.md](blueprint-microsite-contributor-guide.md).

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

### Autonomous demo loop

The substrate runs itself for the demo. The simulator's domain-aware
ramp loop ([simulator_orchestrator.py](../api/server/services/simulator_orchestrator.py))
trickles real workflows into the dashboard, and the
[persona_responder](../api/server/services/persona_responder.py) closes
HITL gates by acting as the `claim_submitter`, `finance_bp`, `recruiter`
etc. on the configured `AUTO_CLOSE` allow-list. Default ON. Recordings
of the resulting walks live under
[data/blueprint-recordings/](../data/blueprint-recordings/) and feed the
blueprint microsite's live observatory when no real bus events are
available. See [blueprint-microsite-contributor-guide.md](blueprint-microsite-contributor-guide.md).

### UI surfaces

Three Vite apps:

- **Control Plane** ([web/client/](../web/client/), `:5173`) — the
  domain-neutral operator surface. Routes: `FleetDashboard`,
  `WorkflowDetail`, `ExceptionQueue`, `Analytics`, `Evaluations`,
  `PolicyAndAutonomy`, `ReviewerQueue`, `HiringManager`.
- **Candidate Portal** ([web/portal/](../web/portal/), `:5174`) — the
  POC2 candidate-facing app (`/apply`, `/portal`, `/screen`, `/book`)
  plus the `/recruiter` view. Real WebRTC voice, real ACS email send.
- **Blueprint microsite** ([web/blueprint/](../web/blueprint/), `:5175`
  locally; Azure Container Apps in production) — the editorial page +
  live observatory of the substrate. Walks `GET /api/blueprint/composition`
  on load; subscribes to `GET /api/blueprint/stream` for the live mind-map.

Shared types in [web/shared/types.ts](../web/shared/types.ts) mirror
Python [api/shared/types.py](../api/shared/types.py); smoke test enforces
the contract in [tests/e2e/smoke.spec.ts](../tests/e2e/smoke.spec.ts).

### Where each domain stands today

- **POC1** — 13 ACs, status table in
  [poc1-status.md §1](poc1-status.md#1-acceptance-criteria--status).
- **POC2** — 22 capabilities, status table in
  [poc2-status.md §1](poc2-status.md#1-capability-matrix--starting-state).
- **Six fleet-* domains** — graduated by `compose-domain` (v1 then v3);
  briefs under [superpowers/specs/fleet-*-brief.yaml](superpowers/specs/).
  All six brought to substrate parity per
  [plan/feature-fleet-domain-substrate-1.md](../plan/feature-fleet-domain-substrate-1.md):
  registered in `api/shared/domains.py`, run end-to-end via the
  autonomous demo loop, fully visible to `query_fleet`, resolvable
  from the operator UI, and produce FM-escalated traffic when persona
  `decision_policy` returns `escalate`.

**Don't duplicate the status tables elsewhere.**

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
4. **"Platform stays, domain swaps"** — the laptop diagram for POC2 is
   structurally identical to POC1's; the same is true of
   `fleet-travel-preapproval`. That's the differentiator vs hand-rolling
   each vertical.
5. **Composition, not construction** — the next domain is added by the
   [`compose-domain`](superpowers/skills/compose-domain/SKILL.md)
   meta-skill, not by hand. `fleet-travel-preapproval` is the existence
   proof. The blueprint page reflects new domains the moment they land
   on disk.

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
| The pitch this whole substrate carries | [blueprint.md](blueprint.md) |
| POC1 acceptance criteria + remaining work | [poc1-status.md](poc1-status.md) |
| POC2 capability matrix + status | [poc2-status.md](poc2-status.md) |
| Code-anchored architecture reference | [ARCHITECTURE.md](ARCHITECTURE.md) |
| How to run POC1 | [DEMO.md](DEMO.md) |
| How to run POC2 | [poc2-DEMO.md](poc2-DEMO.md) (full) · [poc2-quick-demo.md](poc2-quick-demo.md) (5–8 min) |
| Make a new domain show up on the blueprint page | [blueprint-microsite-contributor-guide.md](blueprint-microsite-contributor-guide.md) |
| Compose a new domain end-to-end | [superpowers/skills/compose-domain/SKILL.md](superpowers/skills/compose-domain/SKILL.md) |
| Local dev setup | [DEVELOPMENT.md](DEVELOPMENT.md) |
| Verbatim Zava brief | [poc1-brief.md](poc1-brief.md) |
| What every doc in `docs/` is for | [README.md](README.md) (this directory) |
