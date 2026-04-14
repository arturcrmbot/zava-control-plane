# WPP Control Plane — Python POC1 (DF + MAF + GHCP SDK) Design

**Status:** Draft for approval
**Date:** 2026-04-13
**Author:** brainstorm session
**Target milestone:** evidence (screenshots + video) embedded in the WPP RFP written response due 2026-04-23
**Build window:** 2 days, subagent-driven
**Working directory (new):** `c:\dev\ghcp sdk stuff\control-plane-py\`
**TS v1 (unchanged):** `c:\dev\ghcp sdk stuff\control-plane\`

---

## 1. Context and goal

The TS v1 build ([control-plane/](../../../control-plane/)) proved the **runtime pattern** — a real GHCP SDK Fleet Manager, hooks, MCP tools, OTEL — but the [solution-audit](../../../control-plane/docs/SOLUTION-AUDIT.md) flagged five solution.md sections as NARRATIVE-ONLY. The biggest is §7 Workflow Durability: solution.md commits to long-running orchestration with HITL waits, MAF workflow graphs per phase, and GHCP SDK sessions inside agent executors — and v1 implements none of it.

This spec replaces the in-process simulator with a **real Python implementation of POC1** built on **Microsoft's Durable Agents pattern** ([MAF v1.0 + Durable Task Framework](https://learn.microsoft.com/en-us/agent-framework/tutorials/agents/orchestrate-durable-agents)) — a single MAF `DurableWorkflow` per invoice that runs to completion across hours/days with native HITL waits and automatic checkpointing. Each workflow step invokes a MAF workflow graph (Pregel BSP) of typed executors; agent executors host GHCP SDK Python sessions loading skills. The same React Control Plane UI talks to either backend via an env-var switch.

### Goals

- Implement all six POC1 phases per solution.md §14 phase table, faithfully, as **steps inside one MAF `DurableWorkflow` per invoice**, with the deterministic-by-default + agentic-by-exception pattern realised (multi-agent MAF graphs with deterministic glue and validators between).
- Surface MAF Durable Workflow activity in the Control Plane UI so the architecture is visibly demonstrated, not hidden behind unchanged screens.
- Produce six new hero screenshots that prove the Durable Agents pattern for inclusion in the written response.
- Migrate the entire backend to Python (FastAPI + GHCP SDK Python + MAF Python + Azure Functions runtime hosting MAF's durable runtime) so the codebase is single-language and aligned with the Microsoft AI stack.

### Non-goals

- POC2 (HR Talent Lifecycle) — out of scope.
- Cosmos DB / Dataverse persistence — state stays in-memory.
- Real APIM AI Gateway, Foundry IQ, Agent 365, Entra Agent ID — narrative-only in the response, not built.
- Cloud deployment — runs locally via Functions Core Tools + Azurite.
- Production polish — single happy path per phase, one scripted failure case for the bounded-probabilism screenshot.

---

## 2. Scope summary (decisions from brainstorm)

- **Backend language:** Python end-to-end (FastAPI + MAF Python Durable Workflows hosted on Azure Functions runtime + GHCP SDK Python).
- **Orchestration pattern:** **Microsoft Durable Agents** — one MAF `DurableWorkflow` per invoice, six phases as workflow steps, native HITL via `ctx.wait_for_external_event`, checkpointing automatic. No separately authored DF orchestrator function.
- **Migration shape:** Greenfield in `control-plane-py/`. TS v1 untouched. UI selects backend via `VITE_API_BASE_URL` (or equivalent).
- **MAF graph richness:** Moderate with one Rich moment. Three hybrid phases (Intake, Routing, Reconciliation) each have 3 agent executor invocations inside their per-phase Pregel graph; Intake includes a sub-agent delegation moment.
- **Identity model:** two Hosted Agent identities — `finance-agent` (used by all 9 finance skills) and `fleet-manager-agent` (used by the fleet-manager skill). One agent identity per logical role; specialisation via skills, not via separate agents.
- **HITL:** native MAF Durable Workflow `ctx.wait_for_external_event("approval_decision")` in the Approval step; resumed via the MAF durable runtime client's `raise_event` from FastAPI when the operator resolves the corresponding exception in the UI.
- **UI changes:** new "Orchestration" tab on Workflow Detail + new "Orchestration" feed tab on the right rail. Existing screens unchanged.
- **Mock MCPs:** reused as-is from v1 (TS Express stubs, HTTP, language-agnostic).
- **Auth:** `gh auth token` via the user's personal Copilot license. Same path the v1 spike proved.

---

## 3. System architecture

```
┌─────────────────────────────────────────────────────────────┐
│   React UI (UNCHANGED — same /api/* paths, same SSE)        │
│   Adds: Workflow Detail "Orchestration" tab,                │
│         right-rail "Orchestration" feed tab                 │
└──────────────────────▲──────────────────────────────────────┘
                       │
       Backend toggle via env var: VITE_API_BASE_URL
                       │
       ┌───────────────┴──────────────────┐
       │                                  │
┌──────▼──────────┐               ┌───────▼──────────────────────┐
│ TS v1 (kept)    │               │ Python POC1 (NEW)            │
│ control-plane/  │               │ control-plane-py/            │
│                 │               │                              │
│ Express, det    │               │ FastAPI server  (port 3001)  │
│ simulator,      │               │  ├ Fleet Manager (Python)    │
│ Fleet Manager   │               │  ├ EventBus (in-mem)         │
│ (TS), in-memory │               │  ├ StateStore (in-mem)       │
│                 │               │  ├ SSE hub                   │
│ Port 3001       │               │  ├ Routes (/api/*)           │
└─────────────────┘               │  └ DF webhook receiver       │
                                  │                              │
                                  │ Azure Functions host         │
                                  │  (port 7071, local)          │
                                  │  hosts MAF durable runtime   │
                                  │                              │
                                  │  InvoiceP2PWorkflow          │
                                  │  (MAF DurableWorkflow,       │
                                  │   one instance per invoice)  │
                                  │   ├ step: intake (graph)     │
                                  │   ├ step: validation         │
                                  │   ├ step: routing (graph)    │
                                  │   ├ step: approval (HITL)    │
                                  │   ├ step: payment            │
                                  │   └ step: reconciliation     │
                                  │       (graph)                │
                                  │                              │
                                  │ Azurite (Docker, port 10000) │
                                  │  (DF Task Framework storage  │
                                  │   underneath MAF runtime)    │
                                  └──────▲───────────────────────┘
                                         │
                                         │ HTTP MCP calls
                                         ▼
                                  ┌──────────────────────┐
                                  │ Mock MCP servers     │
                                  │ (UNCHANGED — TS)     │
                                  │ workday, d365,       │
                                  │ maconomy, payment    │
                                  │ Ports 4101–4104      │
                                  └──────────────────────┘
```

### Process topology

- **FastAPI server** — `python -m uvicorn server.main:app --port 3001`. Owns all `/api/*` routes, the SSE hub, the in-memory EventBus + StateStore, the Fleet Manager Python service, and a webhook receiver `/internal/durable-event` that the MAF runtime calls back to.
- **Azure Functions host** — `func start --port 7071`. Hosts the **MAF durable runtime**, which loads `InvoiceP2PWorkflow` and runs instances. Underneath, MAF uses the Durable Task Framework with Azurite as its state store.
- **Azurite** — `docker run mcr.microsoft.com/azure-storage/azurite`. Provides the durable state store (Tables + Blobs + Queues) on port 10000. Visible via Azure Storage Explorer or `az storage` CLI.
- **TS mock MCP servers** — unchanged from v1, on ports 4101–4104.
- **React UI** — unchanged React app, served via `vite` from `control-plane/` (the existing build). Backend selected via `.env.local` setting `VITE_API_BASE_URL=http://localhost:3001`.

### How a workflow runs end-to-end

1. UI or simulator-injection endpoint POSTs `/api/simulator/inject` on FastAPI
2. FastAPI calls the MAF durable runtime client to start a new `InvoiceP2PWorkflow` instance with the invoice payload
3. Runtime returns instance ID; FastAPI persists `Workflow.orchestrationInstanceId`
4. The Durable Workflow's `run` method drives steps in sequence: `intake → validation → routing → approval → payment → reconciliation`
5. Each step builds and executes its per-phase MAF workflow graph (Pregel BSP). Inside agent executor nodes, GHCP SDK Python sessions load skills, run the loop, return typed results. Validators and deterministic nodes do their work between agent invocations.
6. Each significant runtime event (workflow started, step started, executor invoked, validator failed, suspended, resumed, completed) emits to FastAPI via webhook (`/internal/durable-event`)
7. FastAPI updates StateStore + emits to EventBus + fans out via SSE
8. UI updates in real time
9. On the Approval step, if HITL is required, the workflow calls `await ctx.wait_for_external_event("approval_decision")` and parks at zero compute (durable runtime persists the suspension)
10. Operator resolves via UI → POST `/api/exceptions/bulk-resolve` → FastAPI calls the MAF runtime client `raise_event(instance_id, "approval_decision", payload)` → Workflow resumes from the awaited line
11. Workflow completes when `run` returns; final webhook fires; state updated; UI shows "completed"

---

## 4. Phase mapping and MAF graph design

UI keeps existing v1 phase names so React renders unchanged. Each is a step inside the single `InvoiceP2PWorkflow` Durable Workflow; each step builds and executes a per-phase MAF graph (Pregel BSP):

| UI phase name | solution.md phase | Per-phase MAF graph type |
|---------------|-------------------|--------------------------|
| Intake | Intake / OCR | Hybrid (3 agent executors + 2 validators + sub-agent moment) |
| Validation | Three-way match | Deterministic |
| Routing | GL coding & cost centre | Hybrid (3 agent executors + 2 validators) |
| Approval | Routing & approval gate | Deterministic + native MAF HITL wait |
| Payment | Payment file generation | Deterministic + GHCP SDK hook on send |
| Reconciliation | Reconciliation | Hybrid (3 agent executors + 1 validator) |

### 4.1 Intake (Hybrid, includes the sub-agent Rich moment)

```
[doc_intelligence_extract] (det)            ← Doc Intelligence stub returns parsed structure
        ↓
[agent_field_extractor] (agent / skill: field_extractor.skill.md)
   │ For each field below confidence threshold:
   └→ spawns sub-agents per ambiguous field via GHCP SDK sub-agent delegation
        ↓
[agent_line_item_extractor] (agent / skill: line_item_extractor.skill.md)
        ↓
[validate_required_fields] (det)            ← assert all mandatory fields present
        ↓
[agent_anomaly_flagger] (agent / skill: anomaly_flagger.skill.md)
        ↓
[validate_amount_consistency] (det)         ← line items must sum to total within tolerance
        ↓
forward
```

3 agent executors on `finance-agent`. Sub-agent delegation in `agent_field_extractor` — **the Rich moment** — is visible in the right rail as nested tool calls.

### 4.2 Validation (Deterministic)

```
[fetch_po(invoice.poRef)] (det) → [fetch_grn(po.id)] (det) → [three_way_match(invoice, po, grn)] (det)
        ↓
forward (or emit workflow.exception.detected if mismatch)
```

No agent, no validator (the matching IS the check).

### 4.3 Routing — GL coding & cost centre (Hybrid, contains the bounded-probabilism screenshot)

```
[lookup_vendor_context] + [lookup_active_gls] + [lookup_cost_centre_policy] (det parallel fan-out)
        ↓
[agent_invoice_classifier] (agent / skill: invoice_classifier.skill.md)
        ↓
[agent_gl_coder] (agent / skill: gl_coder.skill.md)
        ↓
[agent_cost_centre_assigner] (agent / skill: cost_centre_assigner.skill.md)
        ↓
[validate_gl_active] (det)  ← DELIBERATE FAIL CASE for one scripted workflow
        ↓
[validate_threshold_authority] (det)
        ↓
[record_decision] (det)
```

3 agent executors + 2 validators + parallel deterministic fan-out at the start.

**Bounded-probabilism demo case**: one scripted workflow's `agent_gl_coder` is prompted to favour an inactive GL (via a prompt-engineering hint in the synthetic invoice description). `validate_gl_active` blocks. Orchestration emits `validator-blocked` event. Fleet Manager wakes, composes exception. Right rail captures the whole sequence.

### 4.4 Approval (Deterministic + native MAF HITL)

```
[load_authority_policy] (det)
        ↓
[apply_threshold_routing(amount, policy)] (det)
        ↓
   ┌── if auto-approvable → [record_decision] (det) → forward
   │
   └── if HITL required:
          [emit workflow.hitl.requested event] (det)
          await ctx.wait_for_external_event("approval_decision")  # MAF native, zero compute
          [on resume: record_decision with operator id] (det)
          forward
```

No agent. HITL is told entirely by MAF's native `wait_for_external_event` (which uses Durable Task Framework underneath but is exposed as a single line of MAF API). The visible "Suspended awaiting `approval_decision`" badge in the Orchestration tab is the screenshot.

### 4.5 Payment (Deterministic + hook)

```
[generate_payment_file(invoice, decision)] (det)
        ↓
[GHCP SDK hook on payment.submitPayment]
   │  Hook checks: action ledger contains an "approved" entry by a human?
   │  If YES → forward to deterministic submitPayment call
   │  If NO  → block and emit hitl.requested
        ↓
[payment.submitPayment via MCP] (det)
        ↓
forward
```

The hook implements the non-revocable-action gating from solution.md §1: deterministic check that human approval exists before allowing the send. No LLM in the path.

### 4.6 Reconciliation (Hybrid)

```
[bank_statement_match(payment, statement)] (det)
        ↓ if all matched → forward
        ↓ if unmatched items present:
[agent_exception_classifier] (agent / skill: exception_classifier.skill.md)
        ↓
[agent_root_cause_explainer] (agent / skill: root_cause_explainer.skill.md)
        ↓
[agent_resolution_recommender] (agent / skill: resolution_recommender.skill.md)
        ↓
[validate_recommendation_within_authority] (det)
        ↓
forward (or escalate to Fleet Manager if validator blocks)
```

3 agent executors chained sequentially.

---

## 5. Skill library

10 SKILL.md files total, lifted into `control-plane-py/src/server/skills/`:

**finance-agent skills** (loaded into ephemeral GHCP SDK Python sessions inside MAF agent executor nodes; all run on the single `finance-agent` Hosted Agent identity):

1. `field_extractor.skill.md` — parse invoice fields from raw extracted structure; flag low-confidence fields for sub-agent reasoning
2. `line_item_extractor.skill.md` — parse line items from multi-line invoices
3. `anomaly_flagger.skill.md` — flag suspicious patterns (vendor mismatch, unusual amounts, unexpected GL codes)
4. `invoice_classifier.skill.md` — categorise invoice as media production / talent / post / other
5. `gl_coder.skill.md` — pick GL account given category + vendor history + cost centre policy
6. `cost_centre_assigner.skill.md` — pick cost centre given agency + project + vendor
7. `exception_classifier.skill.md` — classify unmatched bank statement items
8. `root_cause_explainer.skill.md` — propose explanation for an unmatched item
9. `resolution_recommender.skill.md` — recommend an action (write off / escalate / retry)

**fleet-manager-agent skill** (separate Hosted Agent identity, ported from v1):

10. `fleet-manager.skill.md` — copied verbatim from v1's [src/server/skills/fleet-manager.skill.md](../../../control-plane/src/server/skills/fleet-manager.skill.md)

---

## 6. UI changes

### 6.1 Workflow Detail — new "Orchestration" tab

Lives next to existing tabs. Layout:

```
[Overview] [Phases] [Traces] [Ledger] [Amplification] [Orchestration]

Durable Workflow: InvoiceP2PWorkflow     instance: <instance_id>
status: <Running/Suspended/Completed/Failed>
started: <timestamp>                     updated: <timestamp>

PHASE TIMELINE
─────────────────────────────────────────────────────────────
✓ Intake             (Hybrid)            duration: 4.2s
   ├ doc_intelligence_extract (det)      0.3s
   ├ agent_field_extractor (agent)       1.8s   skill: field_extractor
   │   └ sub-agent: invoice_total (0.6s)
   ├ agent_line_item_extractor (agent)   0.7s   skill: line_item_extractor
   ├ validate_required_fields (det)      0.0s
   ├ agent_anomaly_flagger (agent)       1.0s   skill: anomaly_flagger
   └ validate_amount_consistency (det)   0.0s

✓ Validation         (Deterministic)     1.1s
✓ Routing            (Hybrid)            5.6s
   ├ lookup_vendor_context (det) │ lookup_active_gls (det) │ lookup_cost_centre_policy (det)
   ├ agent_invoice_classifier (agent)
   ├ agent_gl_coder (agent)
   ├ agent_cost_centre_assigner (agent)
   ├ ✗ validate_gl_active (det)         FAILED — routed to Fleet Manager
   └ (paused)

⏸ Approval           (Deterministic + HITL)
   Suspended awaiting `approval_decision` event since T+0:34

○ Payment            (not started)
○ Reconciliation     (not started)
```

API: new `GET /api/workflows/:id/orchestration` returns the durable workflow history (steps + their MAF graph executor invocations + skill loads).

### 6.2 Right rail — new "Orchestration" feed tab

Tab strip at top: **[Fleet Manager] [Orchestration]** — same component, different SSE feed.

Each row in Orchestration feed:

```
icon   workflow   step / executor                   status     duration
[stp]  INV-0042   step:intake started               -          -
[det]  INV-0042   doc_intelligence_extract          ok         0.3s
[agt]  INV-0042   agent_field_extractor             ok         1.8s   skill: field_extractor
[agt]  INV-0042   └ sub-agent: invoice_total        ok         0.6s
[val]  INV-0042   validate_required_fields          ok         0.0s
[agt]  INV-0042   agent_anomaly_flagger             ok         1.0s   skill: anomaly_flagger
[stp]  INV-0042   step:intake completed             ok         4.2s
[stp]  INV-0017   step:reconciliation started       -          -
[det]  INV-0017   bank_statement_match              ok         0.5s
[val]  INV-0017   validate_recommendation_authority blocked   0.0s   → routed to Fleet Manager
```

`[stp]` rows are Durable Workflow step transitions; `[det]/[agt]/[val]` rows are MAF graph executor invocations within a step.

Filter chip at top: `all` | `agent only` | `validator only` | `step transitions only`.

API: new SSE topic `/api/stream/orchestration`.

### 6.3 No other UI changes

- Fleet Dashboard, Exception Queue, Policy & Autonomy, Analytics, Evaluations: unchanged.
- All existing API contracts (`/api/workflows`, `/api/exceptions`, `/api/policy`, `/api/stream/fleet`, `/api/stream/fleet-manager`): preserved by FastAPI.

---

## 7. HITL signal flow (Approval step)

```
InvoiceP2PWorkflow.run advances to step:approval
  ↓
Approval MAF graph: [load_authority_policy] → [apply_threshold_routing]
  ↓ if requires HITL:
Workflow emits {step:"approval", state:"awaiting_hitl", workflowId} → FastAPI webhook
  ↓
FastAPI:
  - StateStore.workflow.status = "awaiting_hitl"
  - EventBus.emit({type:"workflow.hitl.requested", ...})
  - SSE → UI shows exception in Exception Queue
  ↓
Workflow: await ctx.wait_for_external_event("approval_decision")  [zero compute, persisted by MAF runtime]
  ↓
Operator clicks "Approve" in UI → POST /api/exceptions/bulk-resolve
  ↓
FastAPI:
  - Lookup workflow's orchestrationInstanceId from StateStore
  - Call MAF runtime client: durable_client.raise_event(instance_id, "approval_decision", {decision:"approved", by:operator_id})
  - Update local state, emit event
  ↓
Workflow resumes:
  - wait_for_external_event returns the payload
  - Step records the decision and proceeds to step:payment
  ↓
Webhook back to FastAPI → state update → SSE → UI shows Approval completed, Payment in progress
```

The workflow instance ID is stored on the Workflow record (new field `orchestrationInstanceId`). Captured at spawn time when the MAF runtime returns it.

---

## 8. Demo evidence plan — 12 hero shots

Six existing v1 hero shots remain valid (run against either backend). Six new shots specifically for the Python POC1 build:

| # | Shot | Proves | Captured from |
|---|------|--------|---------------|
| 1 | Fleet Dashboard with 30+ workflows, 3 exceptions visible | CP-1, CP-7, CP-8 | UI |
| 2 | Exception Queue with bulk-3 expanded showing recommendation + policy refs | CP-2, CP-4, CP-5 | UI |
| 3 | Workflow Detail Traces tab with OTEL span tree | CP-3, CP-9 | UI |
| 4 | Bulk HITL modal with 3 checked | CP-4 | UI |
| 5 | Right rail mid-reasoning showing `compose-exception` tool call | "FM is real" | UI |
| 6 | What-If analysis showing impact delta | CP-6, CP-11 | UI |
| **7** | **Workflow Detail → Orchestration tab showing DF history + MAF graph mid-phase** | **DF + MAF are real** | **New UI** |
| **8** | **Same view zoomed into Routing showing 3 agent executors + 2 validators + skill names** | **Multi-agent MAF + skills, single agent identity** | **New UI** |
| **9** | **Validator-blocked: red `validate_gl_active`, "Routed to Fleet Manager", right rail showing FM picking it up** | **Bounded probabilism — the architectural thesis** | **New UI** |
| **10** | **Right rail Orchestration tab with parallel DF events across 5+ workflows** | **Fleet-wide orchestration is real** | **New UI** |
| **11** | **DF state from Functions Core Tools or Azure Storage Explorer showing the same orchestration history** | **Underlying DF runtime is real** | **`func` CLI / Azurite Storage Explorer** |
| **12** | **Workflow Detail orchestration tab when DF is suspended on `wait_for_external_event` for HITL** | **Zero-compute HITL wait is real** | **New UI** |

All embedded in [response/response-technical-sections.md](../../../response/response-technical-sections.md).

---

## 9. File and folder layout

```
c:\dev\ghcp sdk stuff\control-plane-py\
├── README.md                          # quickstart for the Python build
├── pyproject.toml                     # uv / pip-tools managed
├── .env.example
├── .gitignore
├── docker-compose.yml                 # Azurite for local DF storage
├── host.json                          # Azure Functions host config
├── local.settings.json.example        # Functions local env (NOT committed)
├── src/
│   ├── server/                        # FastAPI app
│   │   ├── main.py                    # uvicorn entry, mounts routes, starts FM
│   │   ├── routes/
│   │   │   ├── workflows.py
│   │   │   ├── exceptions.py
│   │   │   ├── policy.py
│   │   │   ├── simulator.py           # /api/simulator/inject — calls DF starter
│   │   │   ├── stream.py              # SSE: /api/stream/{fleet,fleet-manager,orchestration}
│   │   │   ├── orchestration.py       # /api/workflows/:id/orchestration
│   │   │   └── internal_durable_event.py # /internal/durable-event (MAF runtime webhook receiver)
│   │   ├── services/
│   │   │   ├── event_bus.py
│   │   │   ├── state_store.py
│   │   │   ├── triage.py
│   │   │   ├── fleet_manager_service.py   # Python port of TS service
│   │   │   ├── fleet_manager_queue.py
│   │   │   ├── audit_logger.py
│   │   │   ├── sse_hub.py
│   │   │   ├── durable_client.py      # wraps MAF durable runtime client (start_new, raise_event, get_status)
│   │   │   └── eval_runner.py
│   │   ├── mcp_tools/                 # Fleet Manager's 5 MCP tools (Python defineTool)
│   │   │   ├── query_fleet.py
│   │   │   ├── query_traces.py
│   │   │   ├── compose_exception.py
│   │   │   ├── propose_skill_amp.py
│   │   │   └── dry_run_policy.py
│   │   ├── skills/                    # 10 SKILL.md files
│   │   │   ├── fleet-manager.skill.md
│   │   │   ├── field_extractor.skill.md
│   │   │   ├── line_item_extractor.skill.md
│   │   │   ├── anomaly_flagger.skill.md
│   │   │   ├── invoice_classifier.skill.md
│   │   │   ├── gl_coder.skill.md
│   │   │   ├── cost_centre_assigner.skill.md
│   │   │   ├── exception_classifier.skill.md
│   │   │   ├── root_cause_explainer.skill.md
│   │   │   └── resolution_recommender.skill.md
│   │   └── fixtures/                  # vendors, POs, agencies, policy refs (copied from v1)
│   ├── shared/
│   │   ├── types.py                   # Pydantic models for Workflow, Phase, Exception, etc.
│   │   ├── events.py                  # FleetEvent discriminated union, WAKE_TYPES
│   │   └── policies.yaml              # copied from v1
│   └── functions/                     # Azure Functions host hosting MAF durable runtime
│       ├── function_app.py            # MAF runtime registration + workflow exposure
│       ├── workflows/
│       │   └── invoice_p2p.py         # InvoiceP2PWorkflow (single MAF DurableWorkflow with 6 steps)
│       ├── webhook.py                 # posts events to FastAPI /internal/durable-event
│       └── graphs/                    # per-step MAF Pregel graphs invoked from workflow steps
│           ├── intake.py              # graph for Intake (hybrid)
│           ├── validation.py          # graph for Validation (deterministic)
│           ├── routing.py             # graph for Routing/GL coding (hybrid)
│           ├── approval.py            # graph for Approval (det)
│           ├── payment.py             # graph for Payment (det + hook)
│           ├── reconciliation.py      # graph for Reconciliation (hybrid)
│           ├── executors/             # individual deterministic + agent + validator nodes
│           │   ├── deterministic/
│           │   ├── agents/            # each wraps a GHCP SDK Python session + skill load
│           │   └── validators/
│           └── _common.py             # shared graph helpers
├── tests/
│   └── unit/
└── docs/
    └── demo-script.md
```

`control-plane/` (TS v1) is untouched.

---

## 10. Tech stack

| Concern | Choice | Why |
|---------|--------|-----|
| Server framework | FastAPI | Async-first, SSE supported, Pydantic models match v1 type shapes |
| Server runtime | Uvicorn | Standard FastAPI runner |
| Orchestration | MAF Durable Workflows (Python) — Microsoft's Durable Agents pattern | Single artefact per workflow (vs DF orchestrator + MAF wired by hand). Native HITL via `wait_for_external_event`. Checkpointing automatic. |
| Per-phase graphs | MAF workflow graphs (Pregel BSP) | Typed executors: deterministic / agent / validator. Invoked from workflow steps. |
| Durable runtime hosting | Azure Functions runtime (Python) | Hosts the MAF durable runtime locally via Functions Core Tools. |
| Durable state store | Durable Task Framework (under MAF) backed by Azurite locally | Standard Microsoft pattern; visible via Azure Storage Explorer. |
| Agent runtime | `@github/copilot-sdk` Python | Same SDK family as v1 TS; same `gh auth token` auth path |
| MCP for Fleet Manager tools | MAF / GHCP SDK MCP client | `defineTool`-style, Pydantic schemas |
| Mock MCP servers | Existing TS Express stubs | Language-agnostic HTTP, no rewrite needed |
| State persistence | In-memory `dict[str, T]` (Pydantic models) | Same v1 pragmatism; persistence is its own gap |
| Event bus | In-process `asyncio.Queue` + handler list | Equivalent to v1's Node EventEmitter |
| Local DF storage | Azurite via Docker Compose | Standard local Functions setup |
| Functions runtime | Azure Functions Core Tools 4 | `func start` for local DF host |
| Tests | pytest + pytest-asyncio | Standard Python |
| Package manager | uv | Fast |

**Not using:** Cosmos DB, Bicep, Container Apps, Entra Agent ID, EasyAuth, real APIM, real Foundry IQ. All "narrative-only" in the response.

---

## 11. Risks and mitigations

| # | Risk | Mitigation |
|---|------|-----------|
| 1 | MAF Durable Agents pattern (Python) preview-status surprises | Spike on day 1 morning — confirm `DurableWorkflow` API surface, `wait_for_external_event`, `raise_event` client. Worst case fall back: hand-write a DF orchestrator function that invokes MAF workflow graphs as activities (the manual-integration pattern) — slightly less elegant, same demo value. |
| 2 | `gh auth token` not consumed cleanly by GHCP SDK Python | Spike on day 1 morning (same window as #1). |
| 3 | Functions Core Tools + Azurite stability on Windows | Pre-pull Azurite Docker image. Use `func` v4 not v3. |
| 4 | UI tab data shape lock-in too late | Lock `/api/workflows/:id/orchestration` and `/api/stream/orchestration` shapes in the implementation plan before backend coding starts. |
| 5 | Validator-blocked screenshot needs scripted data | One scripted workflow's GL-coder gets a contrived prompt that favours an inactive GL. Controlled. |
| 6 | TS v1 regression mid-rewrite | Greenfield approach removes this risk entirely — v1 stays runnable. |
| 7 | 2-day timeline slips | Cut order: skip new shots #11-12 first; if deeper trouble, fall back to TS v1 demo entirely. |

---

## 12. Cut list if we slip

In order:

1. **Hero shot #11** (DF state from Functions Core Tools / Azure Storage Explorer) — supplementary, can be left to live demo phase.
2. **Hero shot #12** (HITL `wait_for_external_event` zero-compute moment) — describable in prose.
3. **Right-rail Orchestration tab** — drop in favour of just the Workflow Detail Orchestration tab. Less compelling but fewer moving parts.
4. **Reconciliation as Hybrid** — make it deterministic-only for v1, only Intake + Routing as hybrid. Loses one screenshot-worthy phase but keeps the deterministic+agent+validator pattern in two phases.
5. **Sub-agent Rich moment in Intake** — drop sub-agent delegation; keep `agent_field_extractor` as a flat agent invocation. Loses the "sub-agent visible in right rail" moment.

**Never cut:**
- The 3-layer (DF + MAF + GHCP SDK) execution path itself, even for one phase
- The validator-blocked screenshot (hero shot #9) — it's the bounded-probabilism story
- HITL via DF wait/raise — proves zero-compute waits

---

## 13. Success criteria

The build is done when:

1. `make dev` (or equivalent) brings up FastAPI + Functions + Azurite + mock MCPs in a single command.
2. UI loads at http://localhost:5173, hits Python backend, shows workflows populating.
3. At least 30 invoice workflows run end-to-end through the full DF + MAF + GHCP SDK pipeline within ~2 minutes of startup.
4. A workflow visibly transits all 6 phases with each MAF executor invocation observable in the Orchestration tab + right rail.
5. The scripted bounded-probabilism demo case fires reliably: validator blocks, Fleet Manager picks it up, exception queue populates.
6. HITL on Approval phase: at least one workflow visibly suspends on `wait_for_external_event` and resumes on operator action.
7. All 12 hero screenshots can be produced from a single demo run.
8. TS v1 backend still runs and produces v1 screenshots if someone flips `VITE_API_BASE_URL` back.

---

## 14. Open questions

- Whether to reuse v1's existing TS Fleet Manager service via HTTP bridge instead of porting to Python. Decided: port to Python — single-language backend is the goal, and the port is small (~300 LOC).
- Exact MAF Python API surface for `DurableWorkflow`, `ctx.wait_for_external_event`, and the durable runtime client. Discovered by day-1 spike (analogous to the v1 GHCP SDK spike). Spike output documented in `control-plane-py/spike/MAF-DURABLE-NOTES.md` for downstream phase implementations.

---

## 15. References

- [solution.md](../../../solution/solution.md) — architecture commitments (esp. §1 principles, §7 workflow durability, §13 component summary, §14 POC1 phase table)
- [spec.md](../../../spec.md) — WPP RFP requirements
- [v1 design](2026-04-13-wpp-control-plane-v1-design.md) — the TS v1 spec we're now augmenting
- [v1 audit](../../../control-plane/docs/SOLUTION-AUDIT.md) — gaps this spec is intended to close
- [v1 architecture as-built](../../../control-plane/docs/ARCHITECTURE.md) — TS implementation reference
- [SPIKE-NOTES.md](../../../control-plane/spike/SPIKE-NOTES.md) — GHCP SDK API patterns proven in v1
