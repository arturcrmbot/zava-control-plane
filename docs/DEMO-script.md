# Demo — 30 minutes, live

Audience: WPP CTO + CIO + senior business. Peer conversation, not a
pitch. Companion to [DEMO.md](DEMO.md).

Structured around the five pillars from the customer steer:
1. Control Plane — how it works, read/write, customisation
2. Multi-agent orchestration & durability
3. Governance, security & compliance — runtime policy
4. System integration — Databricks data layer or direct biz systems via API/MCP
5. Advanced capabilities — POC2

| Block | Time | Surface |
|---|---|---|
| Open + 1-claim anatomy | 3 | one workflow detail page |
| Pillar 1 — Control Plane | 6 | `/fleet`, exception, bulk |
| Pillar 2 — Orchestration & durability | 4 | same workflow + Functions trace |
| Pillar 3 — Governance | 5 | Evidence chip, kill switch, audit blob |
| Pillar 4 — Integration | 4 | EMS swap + Databricks/MCP framing |
| Pillar 5 — POC2 advanced | 6 | portal apply → triage → voice → avatar |
| Constellation close | 2 | `:5175/?view=constellation` |

> **Pre-flight:** `make up`. Wait for one red claim parked at
> Arbitrate. Tabs warm: workflow detail, `/fleet`, `/apply`,
> constellation view.

---

## Open + 1-claim anatomy — 3 min

> Surface: one workflow detail page (any in-flight `EXP-NNNN`).

"Right — straight in. This is one expense claim, mid-flight, on this
laptop. Workday data, Concur OAuth, real Document Intelligence on the
receipt, real audit blob in Azure. Nothing here is a screenshot.

Phase ribbon at the top is the workflow. Reasoning panel on the right
is the agent's actual trace from this run. Cost and audit at the
bottom.

Three things to know about the shape and then we move:

- The workflow is a Durable orchestrator. It survives restarts and
  parks at human gates for hours or days at zero compute.
- Each phase tile is a small graph — some deterministic code, some
  agent calls with named identities, some validators that block bad
  agent output before it lands anywhere.
- The agent identities are real Entra-bound. Every tool call goes
  through one chokepoint — that's where governance lives.

That's the anatomy. Now the five things you actually want to
interrogate."

---

## Pillar 1 · Control Plane — 6 min

> Surface: `http://localhost:5173/fleet`. Role: Agent Administrator.

"This is the Finance Controller's view. They don't log into Workday.
They don't log into Concur. They govern the fleet that does.

*(point at the grid)* About *(count)* workflows live right now. Greens
auto-process — the agent talks to the EMS, validates the receipt,
applies the policy, posts back. The ones that need a human surface
here as exceptions. **AC #1 and AC #2 — single view across 30+,
exception-only.**

### What gets read and written

Read: every workflow's state, phase, agent reasoning, cost, audit
chain — all live off the same event bus. The Control Plane is a
subscriber, not a poller. There's a single always-on session — we
call it the Fleet Manager — that owns the cross-fleet view.

Write: human decisions, kill switches, autonomy threshold changes,
bulk actions. Every write is a signed event into the same chain the
agents are writing into. There's no separate 'admin database'. The
operator and the agents share one ledger.

### Drill in

*(click the red EXP-NNNN — STALLED at Arbitrate)*

The agent's already done Intake, Classify, Receipt, Route — all
green, no human touched any of it. It's parked at Arbitrate because
the policy said this one needs a human.

*(point at the reasoning panel)*

It's not asking 'what should we do'. It's drafted a recommendation —
here's the policy clause, here are two prior arbitrations that look
similar, here's the way I'd lean. The reviewer's job is concur or
override. **AC #5 — receipt cross-validation — happened up here at
Receipt; the OCR total didn't match the claim line, that's why it
went red.**

### Decide

*(click Reject)*

Header flips. Phase ribbon paints Arbitrate red. Two new entries in
the ledger — my decision signed as `finance-controller@wpp`, then
`workflow.rejected`. Out of the queue. Done.

### Bulk

*(open BulkHitlModal — don't fire)*

Same controller will get clustered exceptions — six claims, same
vendor, same week, same reason. One decision across the cluster, one
signature, six ledger entries. **AC #3.**

### Customisation — what you'd actually change

This UI is a React app over a documented event bus and REST surface.
Two ways customers extend it:

- **New panels** — drop a component, subscribe to the event stream,
  call the same REST. We did this for the SSC Reviewer queue at
  `/reviewer-queue` — different role, different sort, same data.
- **New actions** — register a typed event handler on the FastAPI
  side and surface it as a button. The audit and signing are
  inherited.

Cost tile here is real `gen_ai.usage` token telemetry × Microsoft's
published rates. Where the SDK doesn't return token counts we estimate
from prompt + tool payload, and every span carries a provenance tag —
`sdk` or `estimated`. Same number Foundry shows. **AC #13.**"

---

## Pillar 2 · Multi-agent orchestration & durability — 4 min

> Surface: same workflow page; optionally Foundry Tracing tab in
> another window.

"Three-layer pattern, and the same three layers run every domain we
have.

**Layer one — the durable envelope.** Azure Durable Functions, one
orchestrator per claim. Survives a process restart. Survives a region
failover. Parks at a human gate via `wait_for_external_event` at zero
compute — the 72-hour reviewer SLA costs nothing while it's waiting.
**AC #11 — region failure recovery — is a property of this layer; we
can yank the Functions host and the in-flight claims pick up from
checkpoint.**

**Layer two — the agent graph per phase.** Microsoft Agent Framework,
typed Pregel graphs. Each phase is a graph. Inside the graph we mix
three executor types deliberately:

- Deterministic code where there's nothing to reason about — three-
  way matches, schema checks, lookups.
- Agent calls where judgement is needed — classification, arbitration
  recommendation, notification drafting.
- Validators after every agent call. The agent's output is a typed
  contract; the validator either passes it or sends it back. Bad
  agent output never reaches the ledger.

This matters because it's the answer to 'how do I trust the agents'.
The answer is: I don't have to trust them everywhere — I deterministic-
gate them where I can, and I validate them where I can't.

**Layer three — the agent identity.** Each agent is a real Entra-bound
session with its own skill manifest and tool allow-list. Today they
run on the GitHub Copilot SDK; the engagement POC swaps them to
Foundry Hosted Agents on the same shape. Same skills, same tools,
same audit. The substrate doesn't change.

*(if Foundry Tracing tab is open: filter `cloud_RoleName ==
control-plane-functions` and show the live span stream — every
`gen_ai.generate_content` with usage, skill, tool calls. OTEL
semantic conventions, the same ones SK and the OpenAI Agents SDK
emit.)*"

---

## Pillar 3 · Governance, security & compliance — 5 min

> Surface: Evidence chip in workflow sidebar, then Kill Switch panel,
> then the auditBlobUrl.

"This is the part the CISO will care about most. Three pieces.

### How a policy gets to a running agent

There's one governance kernel, in-process. The policy bundle compiles
from two sources of truth: the delegated authority matrix, and the
tool registry. Both are version-controlled, both are signed.

When a policy changes:
- It's a PR against the matrix or the tool registry.
- The bundle compiles deterministically — same inputs, byte-identical
  output, hash printed on boot.
- Approved bundle is published. Every agent session, on every tool
  call, evaluates against the bundle that was live at *that*
  timestamp.

So 'how does a new rule reach the fleet' is — merge, publish,
sub-second propagation. No redeploy. No agent restart. And every
decision the kernel makes carries a `decision_id` you can trace.

### Runtime kill switch

*(point at Kill Switch panel)*

Operational override for when a policy change isn't fast enough. I
can kill an agent or a tool fleet-wide for a TTL. *(walk the form —
e.g. `concur.submit_decision`, 30 minutes)* The next attempt by any
agent gets a structured `GovernanceDenied` with a `decision_id`. No
restart, no deploy. This is the fire-extinguisher.

### Evidence — the claim is reproducible

*(point at Evidence chip — chain / signatures / decisions)*

Every action in the ledger is an Ed25519-signed JWS, hash-chained to
the previous entry, rooted in the policy bundle that was live at the
time. The chip shows three sub-checks; all green means the chain is
intact, signatures verify, and every decision references a real
bundle.

*(click through if it expands)*

The bid says OWASP Agentic AI Top 10, ten of ten. That claim is
auditor-reproducible from this endpoint plus the `agt verify` CLI
against the audit blob. Not a slide.

### Immutability — enforced by Azure, not by us

*(point at auditBlobUrl)*

Every ledger entry is dual-written to an Azure Storage append blob
with version-level immutability on. The retention policy is enforced
by Azure itself. If our code tried to mutate it, Azure would refuse.
**AC #12.**

So the chain answers 'has the content been tampered with', and the
blob policy answers 'can the storage be tampered with'. Both have to
fail for the audit to be wrong."

---

## Pillar 4 · System integration — 4 min

> Surface: `/fleet` showing claims from multiple EMS, plus the
> `api/shared/domains.py` registry if you want to flip to it.

"Two integration shapes. Direct to business systems via API/MCP, and
the data-layer pattern via Databricks. We support both because real
agencies have both.

### Direct to systems — MCP everywhere

Every external system — Workday, Concur, Maconomy, Greenhouse,
ServiceNow, Graph — is behind an MCP server. The agent doesn't know
the difference between them; it sees a tool catalogue.

What that buys you:
- One auth abstraction. APIM AI Gateway in front of every MCP, OAuth
  / SAML / OBO handled at the gateway. Agents never see tokens.
- One audit point. Every tool call is a span; the gateway is where
  rate limits, kill switches and OBO gates live.
- One extensibility shape. Adding a new EMS — Maconomy was our third
  — is register the MCP, declare the tool in the relevant skill,
  publish. **AC #9 — claims from two EMS appear identically right
  now in this fleet view. AC #10 — extensibility, that three-step
  shape.**

If the customer doesn't have an MCP server yet, APIM has a
REST-to-MCP gateway that auto-generates the tool surface from an
OpenAPI spec. So 'I have a REST API today' is a one-config-file step,
not a custom build.

### Data layer — Databricks pattern

Where the customer's source of truth is a lakehouse — Databricks,
Fabric, anything Delta-shaped — we don't fight it. Two patterns:

- **Read path**: an MCP tool fronts a SQL warehouse or Databricks SQL
  endpoint. Agent issues structured queries against governed views.
  Unity Catalog enforces row-level security; the agent identity
  carries through. Same audit story.
- **Write path** is rare for our agents — we write into the systems
  of record (Workday, Concur), not the lake — but where it's needed
  it's an ingestion job, not an agent action.

The point: data layer and direct system integration aren't an
either/or. The same agent can pull a candidate's reference data from
Databricks and post the offer back into Workday in the same workflow.

### One registry — the substrate's claim

*(optional: open `api/shared/domains.py`)*

Every per-domain integration fact — phases, EMS adapters, persona
set, skill list — lives in one Python registry. The Control Plane,
the Fleet Manager, the simulator, the phase ribbon all read from it
at runtime. Adding the ninth domain is a registry entry plus a YAML
brief. Not a refactor. We graduated six domains over a weekend that
way."

---

## Pillar 5 · Advanced capabilities — POC2 — 6 min

> Surface: candidate portal at `:5174/apply`. Close the Control Plane.

"Pivot. Different domain — hiring — running on the same substrate.
Same Durable engine, same governance kernel, same audit blob. What's
different is the surfaces and the multimodality.

### Apply

*(open `/apply`, pick Senior Data Engineer USA, drop in
`data/synthetic/hiring/cv-pdfs/C-SE-USA-00.pdf`, submit, copy id)*

Public form, no login. Orchestrator spawned. Magic-link status URL
emailed via real Azure Communication Services. Workflow already
running into Triage.

### AI triage with real OCR

*(open `/recruiter`, click into the candidate)*

The *What we learned* panel is the live trace from the CV agent.
The `ocr_extract` row is a real Document Intelligence call. If
extraction failed you'd see a red chip and no recommendation —
deliberate; the system refuses to fabricate a verdict. For HR in the
EU, that property matters more than any feature.

### Real voice screen — WebRTC

*(in recruiter view → Active magic links → copy `screen` token, open
`/screen?token=…`, allow mic, ~20 sec conversation, end call)*

Real Azure GPT-Realtime over WebRTC. Transcript posts back, workflow
resumes, recommendation lands in the recruiter's queue.

> *(if mic flakes: `VITE_VOICE_TRANSPORT=canned` plays a canned
> transcript through the same callback. Same code path.)*

### Three interview gates — skip to offer

There are three HITL gates between here and offer — invite, slot
booking, post-interview decision. Skipping for time. Pick up at
offer.

### Offer + onboarding avatar

*(open `/portal?token=…` for an offered candidate)*

Candidate accepts. Phase 10 — Onboarding — renders a real Azure AI
Speech avatar. Personalised welcome, voice synthesis, blob-cached
by SHA so the second render is free.

### What this proves

Two things, and we move to the close:

- The engine that just ran this hire is the same engine that ran the
  expense claims. Same orchestration pattern, same governance, same
  audit story.
- We didn't retrofit POC1 to make POC2 work. POC2 dropped in clean
  through the same registry. That's the substrate claim, made
  literal.

> *(if asked: jurisdiction switching — re-run with `C-SE-DE-00` and
> the same code path grows a German works-council compliance step.
> Hiring Manager surface at `/hiring-manager/HIRE-NNNN`. Episodic
> memory via `recall_similar_hires`.)*"

---

## Close — Constellation — 2 min

> Surface: `http://localhost:5175/?view=constellation`, full screen.

"Pull back.

*(open the constellation view)*

Eight domains live in `main`. POC1 — finance — and POC2 — hiring —
are the two we built by hand. The other six — travel pre-approval,
vendor KYC, employee onboarding, IT access, contract renewal,
performance review — were graduated end-to-end by a meta-skill we
wrote called `compose-domain`. Over a weekend. The ring you're
looking at is the actual list.

One registry. One governance kernel. One audit story. One Foundry
project. Eight domains.

The deliverable is the substrate. POC1 and POC2 are existence proofs.
The kernel is what makes the OWASP-10 claim auditor-reproducible.
What you're looking at on the ring is what scale across WPP's
operating model actually looks like.

Questions."

---

## Q&A — one-liners

- **Cost numbers** — real `gen_ai.usage` where the SDK reports it,
  chars-over-four estimate when it doesn't, provenance tagged.
- **Immutability** — version-level immutability is enforced by Azure
  Storage. Chain integrity by Ed25519 + `agt verify`.
- **New domain** — registry entry + YAML brief through
  `compose-domain`. Six in a weekend.
- **Foundry's role** — telemetry, evaluation, observability. Next to
  the runtime, not in front of it.
- **Lab vs engagement POC** — see [SCOPE-DELTA.md](SCOPE-DELTA.md).
  Agent identities swap GHCP SDK → Foundry Hosted Agents on the same
  shape. Substrate, kernel, surfaces don't change.
- **Why allow-lists not prompts** — allow-lists are policy. Prompts
  aren't. The kernel decides whether a tool call happens, not the
  prompt.
- **AC #4 (≥95% accuracy)** — pipeline and prompt are live. The
  corpus-wide gate is reserved for WPP's 3,430-line real dataset;
  running it on synthetic 300 wouldn't be a meaningful number.

`make down` between recordings.
