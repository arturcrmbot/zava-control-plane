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

"OK so what you're looking at here is one expense claim, mid-flight. I
want to spend a couple of minutes walking around this one page before
we look at the fleet, because every workflow in the system has the
same shape — once you've seen one, the dashboard makes a lot more
sense.

Quick word on what's real and what's mocked, because you'll ask
and I'd rather you ask me than guess. The EMS connectors — Workday,
Concur, Maconomy — are local mocks running on the laptop. We made
that call deliberately so you can see the whole thing run end-to-end
without waiting on sandbox credentials. The pieces that need to be
real to be a credible claim are real: the OCR on the receipt is a
live Azure Document Intelligence call, the audit ledger is being
written to an actual Azure Storage blob with version-level
immutability turned on, the LLM calls are real, and the telemetry is
going to a real Foundry project. Mocked at the edges, real where it
matters.

Three things on the page itself.

*(point at phase ribbon)* The strip across the top is the workflow —
seven phases for an expense claim. Each tile is its own small graph
underneath, mixing deterministic code, agent calls, and validators
that catch bad agent output before it lands anywhere.

*(point at reasoning panel)* On the right is the agent's trace from
this run — which skill it loaded, which tools it called, what it
concluded. Live data from this workflow, not an edited transcript.

*(point at the bottom)* Cost tile and audit chain — we'll come back
to both.

The whole thing is being driven by a Durable orchestrator. That
matters because it survives process restarts and parks at human
gates for hours or days at zero compute — but I'll come back to that
when we get to durability.

Let me show you the fleet."

---

## Pillar 1 · Control Plane — 6 min

> Surface: `http://localhost:5173/fleet`. Role chip top-right says
> Agent Administrator.

"OK so this is the Control Plane — the Finance Controller's view.
The framing here matters: this person, in the target operating
model, never logs into the EMS. They never open Workday. They never
open Concur. Their job is to govern the fleet of agents that does.
That's the whole shift POC1 is making the case for — operators move
up a layer, from doing the work to overseeing the work.

*(point at the grid)* Right now there's something like *(count)*
workflows in flight. The greens you can see are auto-processing —
the agent's pulled the claim from the EMS mock, run the receipt
through Document Intelligence, applied the policy, posted back. No
human has touched any of those, and most of the time no human ever
will. The exceptions — the reds — are the ones the agents have
flagged because they hit something they don't have authority to
decide on their own. And that's all the controller sees by default.
You can flip the toggle to see the full fleet, but the default is
exception-only, because the whole point is that 95% of the volume
shouldn't need their attention.

The really nice property here, and I think this is genuinely one of
the more elegant pieces of the design — the controller and the
agents are looking at the same data. There isn't an 'admin
dashboard' database that's separate from the workflow database.
There's one event bus. The agents emit events as they work, the
controller subscribes to those same events, and when the controller
makes a decision, that decision goes back onto the same bus as a
signed event. The audit chain has the agent's actions and the
human's actions in one stream, in the order they actually happened.

### Drilling into one

*(click into a red EXP-NNNN — the STALLED · Exception at Arbitrate
tile)*

So this one is parked at Arbitrate. Look at the phase ribbon — the
agent has done Intake, Classify, Receipt, Route, all green, and
then it stopped. The reason it stopped is the receipt total didn't
match the claim line — that's the cross-validation step at Receipt,
where the OCR comes off the receipt PNG and gets reconciled against
the structured claim from the EMS. Mismatch, so the verdict went
red, so the workflow's now waiting on a human.

*(point at the reasoning panel)*

But the agent hasn't just stopped and gone 'over to you'. It's
drafted a recommendation. Here's the policy clause it would invoke,
here's two prior arbitrations of similar shape, here's how it would
lean. The reviewer's job is concur or override — it's not 'decide
this from cold', it's 'sanity-check the agent's draft'. That's the
productivity unlock. You're not removing humans, you're moving them
from data entry to judgement, and the data entry has been done for
them.

### Taking a decision

*(click Reject)*

Watch what happens. *(wait one beat)* Header tile flips to red.
Phase ribbon paints Arbitrate red. Two new entries appear in the
ledger at the bottom — my decision, signed as
`finance-controller@wpp`, and right after it the workflow-rejected
event. Go back to the fleet — *(click /fleet)* — and it's gone from
the exception queue.

Whole round-trip is signed and chained, which I'll come back to
when we get to governance. The point right now is the operator's
loop is fast — see, decide, gone — and the audit trail is being
written underneath without them having to think about it.

### Bulk

*(open BulkHitlModal — don't fire)*

Real-world this controller doesn't get exceptions one at a time.
They get clusters. Six claims, same vendor, same week, all flagged
the same way. This bulk modal lets them take one decision and
apply it across the cluster — one signature, six ledger entries,
all linked back to the cluster id. Same governance properties, one
click.

### What you'd actually customise

Customer question that always comes up — 'how would my team
extend this'. The Control Plane is a React app sitting on top of a
documented event bus and a documented REST surface. There's no
proprietary low-code studio in the way. Two patterns we've used
ourselves:

If you want a new view — a different operator role with a different
sort or filter — you drop in a new component, subscribe to the same
event stream, call the same REST endpoints. The SSC Reviewer queue
at `/reviewer-queue` is exactly that. Different role, different
sort, same data underneath. Took an afternoon.

If you want a new action — a new button that does a new thing — you
register a typed event handler on the FastAPI side and surface it as
a button in the UI. The signing, the ledger entry, the OTEL span
— all of that is inherited from the event handler base class. You
don't write audit code; the substrate writes audit code for you
once you declare the action.

### Cost — and the honesty bit

*(point at the cost tile)*

Quick word on this number, because every CFO in the room is going
to ask. This is real `gen_ai.usage` token telemetry off the agent
runs, multiplied by Microsoft's published per-million-token rates,
sourced this week. Not a synthetic constant. The honest caveat —
the model SDK doesn't always emit token counts on every call. When
it doesn't, we estimate from prompt length plus tool payload, and
crucially every span carries a provenance tag — it either says
`sdk` or `estimated`. So your auditor can always tell which is
which on a per-call basis. The number on this tile is the same
number Foundry will show you when you open the same workflow in
the Foundry tracing tab."

---

## Pillar 2 · Multi-agent orchestration & durability — 4 min

> Surface: stay on the same workflow detail page. Optional second
> tab: Foundry Tracing on `https://ai.azure.com` filtered to this
> workflow, if connectivity allows.

"OK so under that nice clean fleet view there's actually quite a
lot going on. I want to take you down one layer because the
architecture choice we made here is the bit I think is genuinely
interesting — and it's the bit that makes the difference between
'cute agent demo' and 'thing you can actually run in production at
scale'.

There are three layers to how a workflow runs, and the same three
layers run every domain on this laptop.

### Layer one — durable workflow envelope

The outer envelope is Azure Durable Functions. Microsoft's
event-sourced orchestration runtime. One orchestrator instance per
expense claim, per hire, per whatever the domain is. And it has
two properties that matter enormously for an enterprise-scale
fleet.

It survives. If the Functions host process crashes, if the region
fails over, if someone deploys a new version mid-run — the
orchestrator picks up from its last checkpoint and carries on. The
state is event-sourced, so 'resume' isn't a feature you have to
build, it's how it works. That's the answer to the brief's
acceptance criterion about region recovery — it's not custom code,
it's a property of the runtime we picked.

And it parks at zero compute. When a workflow is waiting on a
human — and these workflows wait on humans for hours or days —
there's no process sitting idle burning money. The orchestrator
suspends, durable storage holds the state, and when the external
event arrives the orchestrator resumes from exactly where it left
off. That matters at the volumes the brief talks about. 5,500
end-of-quarter concurrent workflows isn't 5,500 processes. It's
5,500 rows of state in storage.

### Layer two — the agent graph per phase

Inside the envelope, each phase tile you saw on the ribbon is a
typed graph. We're using Microsoft Agent Framework for this — it's
the open-source agent runtime that came out of the Semantic Kernel
and AutoGen lines getting merged. The graph layer lets us mix
three kinds of executor inside a single phase, and this is the bit
I want you to take away because it's the answer to 'how do you
trust the agents'.

Some steps are deterministic code. Schema checks, three-way matches,
amount comparisons, lookups against the EMS. Things where there's
nothing to reason about — you just need the answer to be right
every time. So those don't go anywhere near a model. We just write
them as code.

Some steps are agent calls. The classification verdict, the
arbitration recommendation, the notification draft, the CV triage
— things where you actually want judgement applied. Those are
real LLM calls, real reasoning, real tool use.

And the third kind — and this is the one most demos skip — every
agent call has a validator behind it. The agent's output is a
typed contract. The validator either passes it or it sends it
back. So bad model output never reaches the ledger, never reaches
the EMS, never gets posted into Workday. The agents are inside a
guard rail, not in front of the steering wheel.

The framing I'd give you is: we don't have to trust the agents
everywhere. We deterministic-gate them where we can — and we
validate them where we can't. That's how you get from 'this is
clever' to 'I can put it in production'.

### Layer three — the agent identity and the agentic loop

We'll come back to this one in detail at the end when we look at
how skills work — but the headline now: each agent is a real
sessioned identity with its own skill manifest and its own tool
allow-list. It's not 'one big chatbot prompt with everything
plugged in'. The classifier agent literally cannot call a Workday
write tool, because it's not in its allow-list. The arbitration
agent can read precedents but can't post a decision. Each agent
has the smallest possible surface area.

Today these run on the GitHub Copilot agent SDK. At engagement-POC
time they swap to Foundry Hosted Agents on the same shape — same
skill files, same tool registry, same audit. The substrate doesn't
change.

> *(if Foundry tracing is open in another tab: filter
> `cloud_RoleName == control-plane-functions` and show the live
> span stream — every `gen_ai.generate_content` call with usage,
> skill name, tool calls. Same OTEL semantic conventions Microsoft
> Agent Framework, Semantic Kernel, the OpenAI Agents SDK and
> Copilot all share. So this telemetry isn't proprietary — anyone
> who builds an agent on the same conventions plugs straight into
> the same Foundry view.)*"

---

## Pillar 3 · Governance, security & compliance — 5 min

> Surface: scroll the workflow detail to the Evidence chip in the
> sidebar. Then the Kill Switch panel. Then the auditBlobUrl link.

"Right — this is the bit your CISO will want to spend the most time
on, so I'm going to slow down here.

The thing I want to put a name on first, because it underpins
everything in this section, is a piece of Microsoft tech called the
Agent Governance Toolkit. AGT for short. It's a relatively new
open-source kit from Microsoft Research — it shipped to public
preview a few weeks ago — and what it does is it gives you a single
in-process policy kernel that mediates every tool call any agent
makes, with a hash-chained signed audit ledger underneath. It's
essentially the missing 'governance layer' that nobody had a clean
answer for in the agentic stack until now.

We've integrated AGT into the substrate as the runtime governance
core. And honestly this is the bit I'm most proud of in this build,
because it took the bid response's 'OWASP Agentic Top 10 — ten of
ten' from being a marketing claim into being a thing your auditor
can re-derive themselves from a CLI command and the audit blob.
Let me show you what that means in three concrete pieces.

### Piece one — how policy gets to a running agent

There's one place where policy lives — a delegated authority
matrix that's already in this repo, plus a tool registry that
declares for every MCP tool whether it's reversible, what it costs,
who can call it. Both of those are version-controlled, both are
signed.

When something changes — say a new approval threshold, or a tool
gets locked down — it's a pull request against those two files.
The policy bundle compiles deterministically; same inputs always
produce the byte-identical output, with a hash printed on the
console at boot. That determinism matters because it means the
auditor can take the YAML out of the audit blob, recompile it from
the source files at the timestamp on the entry, and prove they
match. No drift, no 'who changed what when' arguments.

Once it's published, every agent session, on every tool call,
evaluates against the bundle that was live at *that* timestamp. So
'how does a new policy reach the fleet' is — merge, publish,
sub-second propagation. No agent restart. No deploy. The kernel
reloads in process.

### Piece two — runtime kill switch

*(point at the Kill Switch panel in the sidebar)*

Now the policy compile-and-publish flow is governed and slow,
which is the right answer for the 99% case. But sometimes you need
'stop, now'. Something's misbehaving, an agent's looping on a
tool, a vendor's API is down and you don't want fifty agents
hammering it. The kill switch is the runtime override.

The operator fills in the form here — actor or tool, TTL, reason —
and posts it. *(walk the form — for instance:
`concur.submit_decision`, 30 minutes, reason 'investigating
duplicate submissions')*. The kernel consults the kill table on
every single tool call. So the next attempt by any agent
anywhere in the fleet to call that tool comes back with a
structured `GovernanceDenied` decision, with a `decision_id` the
operator can trace through Foundry. The Functions worker doesn't
restart. There's no deploy. It's hot.

That's the operational fire-extinguisher your security team needs
in their hand before they'll ever sign off on increasing autonomy.

### Piece three — the Evidence chip

*(point at the Evidence chip in the sidebar — three sub-chips:
chain, signatures, decisions)*

This is the part where the OWASP claim gets made auditor-
reproducible. Three sub-chips. Let me unpack each one because they
each prove something different.

**Chain.** Every entry in the action ledger has a hash of the
previous entry baked into it. So the ledger is a hash chain — if
anyone in the middle modified any entry, every subsequent entry's
hash would no longer match. The chain check verifies the whole
chain end to end. If it goes red, it tells you exactly which entry
broke.

**Signatures.** Every entry is signed by the actor that produced
it — Ed25519, JWS compact serialisation. Each agent has its own
keypair; the public keys are committed in the repo, the private
keys are in Key Vault in production. The signature check verifies
that every entry was signed by the actor it claims to be from. So
nobody can forge a 'finance-controller approved this' entry — even
the agents can't.

**Decisions.** Every entry references a `decision_id` from the
governance kernel, which references the policy bundle hash that was
live at that moment. The decision check verifies that every
referenced decision still resolves cleanly against a known bundle
in the bundle history. So nobody can claim 'the policy at the time
allowed this' if the policy never said any such thing.

Three checks, all green, and you have an auditor-reproducible
proof that every action in this workflow was taken by the actor
the ledger says, against the policy the ledger says, in the order
the ledger says.

There's a CLI version too — `agt verify` — which you can run
against the audit blob from your laptop, no access to the
substrate required. So your external auditor doesn't even need
permissions in our system; they just need read access to the blob.

### Piece four — immutability is enforced by Azure, not by us

*(point at the auditBlobUrl)*

One last thing. The chain proves the content hasn't been tampered
with. But you also need 'can the storage be tampered with', which
is a different question. Every ledger entry is dual-written into
an Azure Storage append blob with version-level immutability
turned on. The retention policy is enforced by Azure itself — not
by our code, not by anyone's goodwill. If we tried to mutate that
blob, Azure would refuse. If someone with full RBAC on the storage
account tried to delete it, Azure would refuse until the retention
period expired. So between the chain integrity and the storage
immutability, both have to fail for the audit to be wrong, and
they fail through completely different mechanisms.

That's the answer to 'how do I know what the agents actually did
last quarter when the regulator asks me'. The honest answer
today, in most agentic stacks, is 'we hope the logs survived'.
The answer here is 'here's the blob, here's the CLI, run it
yourself'."

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
