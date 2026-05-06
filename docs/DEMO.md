# Demo flow — Microsoft Apex / WPP

Four acts, **40 minutes total**, live against the running stack — no
slides, no recordings. Take time to **explain** as you go; this is not
a speed-run.

| Act | Time | What |
|---|---|---|
| 1 · Intro — workflow + architecture at a glance | 5 min | How a workflow actually runs · what's on the laptop · what's in Azure / Foundry |
| 2 · POC1 — Control Plane | 15 min | Finance Controller + SSC Reviewer governing 30+ agentic expense workflows |
| 3 · POC2 — standalone end-to-end | 15 min | Candidate → recruiter → hiring manager → onboarding; the Control Plane stays closed |
| 4 · Constellation — the substrate | 5 min | Pull back to the eight-domain view; the central claim of the bid |

Detailed runbooks if you want to drill in:

- POC1 acceptance criteria + status: [poc1-status.md](poc1-status.md)
- POC2 long-form runbook (22 capabilities): [poc2-DEMO.md](poc2-DEMO.md)
- POC2 short happy-path script: [poc2-quick-demo.md](poc2-quick-demo.md)
- Substrate / blueprint pitch: [blueprint.md](blueprint.md)
- Architecture canon: [ARCHITECTURE.md](ARCHITECTURE.md)
- Lab vs engagement-POC scope: [SCOPE-DELTA.md](SCOPE-DELTA.md)

---

## Act 1 · Intro — workflow + architecture (5 min)

Open a single workflow detail page (any in-flight POC1 claim works,
e.g. `http://localhost:5173/workflows/<latest CMP-NNNN>`) and use it
as the canvas. Talk through the three tiers as the audience looks at
the phase ribbon, the agent reasoning panel, and the cost / audit
tiles.

### How one workflow actually runs

1. **Trigger.** Either an EMS event (POC1: claim batch arriving from
   Workday / Concur), a public form submission (POC2: candidate
   apply), or the simulator. The FastAPI process schedules a new
   Durable orchestration on the Functions host.
2. **Durable orchestrator** (Azure Functions, [`function_app.py`](../function_app.py))
   runs a fixed sequence of phase activities. Per-domain orchestrator
   files in [`api/functions/workflows/`](../api/functions/workflows/) —
   POC1 is `ExpenseClaimOrchestrator` (7 phases),
   POC2 is `HiringOrchestrator` (10 phases).
3. **Each phase activity = a typed MAF Pregel graph**
   ([`api/functions/graphs/`](../api/functions/graphs/)) mixing three
   executor kinds: deterministic steps, agent calls (GHCP SDK
   identities, skills under [`api/server/skills/`](../api/server/skills/)),
   and validators that block bad agent output and emit exception
   events.
4. **HITL gates** park the orchestrator on `wait_for_external_event`;
   the FastAPI [`/internal/durable_event`](../api/server/routes/internal_durable_event.py)
   route raises the matching event when an operator clicks, a
   candidate replies, or a persona webhook callback fires.
5. **Fleet Manager** (FastAPI-side, single always-on GHCP SDK session,
   [`fleet_manager_service.py`](../api/server/services/fleet_manager_service.py))
   subscribes to a triage-filtered event stream from every workflow
   and streams reasoning + tool calls to the operator UI rail.

### Where it runs from

**On the laptop (everything except the rectangles below):**

| Process | Port | What |
|---|---|---|
| FastAPI / uvicorn | `:3001` | REST + SSE + Fleet Manager session + simulator |
| Azure Functions host | `:7071` | Durable orchestrators + per-phase activities |
| Azurite | `:10000-10002` | Durable state, checkpoints, timers |
| Vite — Control Plane | `:5173` | Operator UI (Agent-Administrator role) |
| Vite — Candidate Portal | `:5174` | POC2 candidate + recruiter + hiring-manager surfaces |
| Vite — Blueprint microsite | `:5175` | Editorial page + Constellation full-screen view |
| 10 Node mock MCPs | `:4101-4103, :4201-4207` | Workday / Concur / Maconomy + Greenhouse / LinkedIn / Workday-HR / Graph / ServiceNow / ACS / HeyGen |

**In Azure / Foundry (the network rectangle):**

- **Azure OpenAI · GPT-Realtime** — the real WebRTC voice screen in
  POC2 ([`RealtimeCall.ts`](../web/portal/src/lib/RealtimeCall.ts)).
- **Azure AI Speech** — real avatar synthesis for the POC2 onboarding
  welcome video; blob-cached by `sha256(voice|script)`.
- **Azure Document Intelligence** — real OCR for POC1 receipts and
  POC2 CV PDFs ([`ocr_extract`](../api/server/mcp_tools/ocr_extract.py)
  MCP tool, Entra-ID auth).
- **Azure Storage `apexdemo62525`** — audit ledger append blob with
  version-level immutability enabled. Surfaced as `auditBlobUrl` on
  every workflow detail.
- **Azure Communication Services** — real ACS Email send for candidate
  magic links; falls back to local outbox if offline.
- **Azure Monitor / App Insights → Foundry Tracing tab**
  (`https://ai.azure.com`) — every `gen_ai.generate_content` span with
  `gen_ai.usage.*`, `gen_ai.agent.name`, `wpp.skill`, plus tool-call
  children. Same OTEL semantic conventions Microsoft Agent Framework /
  Semantic Kernel / OpenAI Agents SDK / GHCP SDK all share.
- **Foundry `evaluate()` SDK** — the AC #4 batch + online evaluation
  pipeline. `/api/accuracy/run` returns 503 when Foundry isn't
  configured (no fake numbers).
- **GitHub Copilot endpoint** — every agent identity is a GHCP SDK
  session. At engagement-POC time this swaps to Foundry Hosted Agents
  on the same agent shape (see [SCOPE-DELTA.md](SCOPE-DELTA.md)).

> The framing line: *the laptop runs the substrate; the cloud
> rectangles are the production-shaped seams the engagement POC
> inherits as-is.*

---

## Act 2 · POC1 — Control Plane (15 min)

POC1 *is* a Control Plane demo. Per [poc1-brief.md §3](poc1-brief.md#sec-3),
the Finance Controller never logs into Workday or Concur; they govern
the agent fleet that operates those systems. Lead here.

**Surface:** `http://localhost:5173` · role: Agent Administrator (top
right of the chrome).

### Finance Controller (London) — `/fleet`

Open on the Fleet dashboard. Take a moment to explain the framing
before clicking: ~30 in-flight expense workflows; the green ones
auto-process invisibly; only the exceptions surface.

- **Fleet view** with exception-only surfacing (AC #1, AC #2).
- **Drill into a flagged workflow** — phases, agent reasoning, cited
  policy clauses, executor mix (deterministic / agent / validator)
  (AC #4, [`expense_claim.py`](../api/functions/workflows/expense_claim.py)).
- **Bulk action** — one decision applied across a clustered exception
  set (AC #3, [`BulkHitlModal.tsx`](../web/client/components/BulkHitlModal.tsx)).
- **Cost tile** — reads real `gen_ai.usage.*` token spans × published
  Azure rates (AC #13,
  [`model_pricing.py`](../api/server/services/model_pricing.py)). No
  synthetic constants. Same number Foundry shows.
- **Audit ledger** — `auditBlobUrl` on the workflow detail. Open the
  versioned, retention-policy-protected append blob in the browser
  (AC #12).
- **Fleet Manager chat** (right rail) — natural-language probe of the
  fleet ("cost this week", "stalled arbitrations", "repeat
  offenders"). Watch tool calls and reasoning stream.
- **Behaviour-change proposal** — after 50+ consistent reviewer
  decisions, the Fleet Manager surfaces an autonomy-promotion
  proposal in the policy panel (AC #7).

### SSC Expense Reviewer (Manila) — `/reviewer-queue`

Switch surface to show that the operational reviewer queue is
*separate* from the controller's surface
([`ReviewerQueue.tsx`](../web/client/routes/ReviewerQueue.tsx)).
System-agnostic queue; pre-composed arbitration recommendation with
cited precedent (AC #8).

### Justification round-trip — narrated

End-to-end Red workflow → employee notification → justification →
arbitration → resolution. Walk live if time permits, narrate over a
completed workflow if not (AC #7).

### Reserve beats (only if asked)

- EMS extensibility — [demo-ems-extensibility.md](demo-ems-extensibility.md) (AC #10).
- Region failure recovery — `POST /api/simulator/region-failure` (AC #11).
- Repeat-offender progressive enforcement (AC #6).
- Live Foundry Tracing tab on the workflow currently on screen.

---

## Act 3 · POC2 — standalone end-to-end (15 min)

POC2 is **not** a Control Plane demo. The hiring lifecycle has its own
purpose-built surfaces; the Control Plane stays closed for this act.
Same Durable orchestrator runs underneath, but the audience sees
candidate, recruiter, and hiring manager — not a fleet view.

Use [poc2-quick-demo.md](poc2-quick-demo.md) as the click-by-click
script. The shape:

### Candidate applies — Portal `:5174/apply`

Public form, no login. Pick **Senior Data Engineer · USA**, drop in a
synthetic CV PDF (`data/synthetic/hiring/cv-pdfs/C-SE-USA-00.pdf`),
submit. Copy the returned `candidate_id`.

> Explain what just happened: orchestrator spawned, magic-link status
> URL emailed via real ACS, `candidate.applied` event fired. Phase 1
> (Budget) auto-approves and the workflow runs through to Triage.

### AI triage — Recruiter view `:5174/recruiter`

Click into the candidate. Phase = Review (Triage) for ~10–60s while
`cv-crystalliser` runs.

- **What we learned · cv_crystalliser** panel paints with the real
  LLM trace — `tool · ocr_extract` row (real Document Intelligence),
  structured profile, token usage, latency chip.
- If extraction fails you see a red chip and *no fabricated verdict*
  — explain the deliberate choice not to hallucinate.

### Voice screening call — Portal `:5174/screen?token=…`

Real Azure GPT-Realtime voice call over WebRTC.

- Recruiter view → Active magic links → copy the `screen` token.
- Open `/screen?token=…`, allow mic, ~30s of conversation, end call.
- Transcript posts back, workflow resumes.
- Fast path if no mic: `VITE_VOICE_TRANSPORT=canned` plays a canned
  transcript through the same `voice_complete` callback.

### Three interview HITL gates — Recruiter view

Each gate paints a different decision panel keyed off `awaiting_reason`.

- **Gate ① · invite to interview?** — `interview-recommender` AI rec
  card with talking points; recruiter clicks Invite or Reject.
- **Gate ② · candidate picks slot** — candidate gets a `book_interview`
  magic link, picks one of 15 slots at `/book?token=…`.
- **Gate ③ · post-interview decision** — recruiter fills rating +
  decision + level + notes; `offer_decision` event raises.

### Offer + onboarding

Candidate accepts the offer at `/portal?token=…`. Phase 10 (Onboarding)
renders a personalised welcome avatar via real Azure AI Speech
(blob-cached); plays back on the candidate portal.

### Differentiators worth dropping in (any time during Act 3)

- **Jurisdiction switching** — re-run with `C-SE-DE-00`; same code path
  grows a BetrVG works-council Compliance step (capability §4.10).
- **Hiring Manager surface** — `/hiring-manager/HIRE-NNNN` for panel
  scheduling and offer sign-off (different actor, different surface,
  same workflow).
- **A2A boundary** — `POST /api/a2a/inbound` from a stand-in candidate
  PA (§4.19).
- **Episodic memory** — `recall_similar_hires` MCP tool surfaces past
  hires of the same `(role_family, jurisdiction)` (§4.7).

---

## Act 4 · Constellation — the substrate (5 min)

Pull back. POC1 and POC2 are two domains; the substrate runs eight.

**Surface:** Control Plane sidebar → **Constellation ↗** (opens the
blueprint microsite at `:5175/?view=constellation` full-screen).

Three points, briskly:

1. **Eight domains live in `main`** — POC1 (finance) and POC2 (hiring)
   were hand-built; six fleet-* domains (travel pre-approval, vendor
   KYC, employee onboarding, IT access, contract renewal, perf review)
   were graduated end-to-end by the
   [`compose-domain`](superpowers/skills/compose-domain/SKILL.md)
   meta-skill over a single weekend.
2. **One registry, no per-domain branches.** Every per-domain
   integration fact lives in
   [`api/shared/domains.py`](../api/shared/domains.py); the generic
   substrate layers (Fleet Manager skill text, simulator spawners,
   exception resolve route, blueprint inventory, per-domain phase
   ribbon) read from it at runtime. Adding the ninth domain = a
   registry entry plus a YAML brief through `compose-domain`. Not a
   refactor.
3. **Same Foundry project across all eight.** Same OTEL semantic
   conventions, same evaluation pipeline, same cost ledger. The
   Foundry Tracing tab filtered by `cloud_RoleName ==
   "control-plane-functions"` shows the live cross-domain trace
   stream.

Closing line: *the substrate is the deliverable; POC1 and POC2 are two
existence proofs of it.*

---

## End — Q&A themes

Live stack stays running. Anticipated probe themes:

- Provenance of cost numbers (real token spans, not constants).
- Immutability of the audit ledger (live verification on the append blob).
- How a ninth domain gets added (the substrate's central claim).
- Where Foundry (tracing, evaluation, observability) sits next to the
  agent runtime.
- Lab-build vs engagement-POC scope — what is real today, what
  Microsoft commits to deliver during the engagement
  ([SCOPE-DELTA.md](SCOPE-DELTA.md)).
- Skills + MCP tool allow-lists vs prompt-only engineering.
