# Presenter primer — read this on the train

You have the script ([DEMO-script.md](DEMO-script.md)) and the beat sheet
([DEMO-beats.md](DEMO-beats.md)). This file is the *grounding* — what
each piece is, why it's there, why the design choices land, and what to
say when someone asks the obvious follow-up. Read it cover-to-cover; you
do not need to memorise it. The goal is for "wait, what is that?" to
never throw you.

It's deliberately written as prose, not bullets. Bullets are for the
beat sheet.

---

## 1. The thesis, in your own voice

Three years of enterprise AI has produced a recognisable shape. Customer
funds a use case. Vendor delivers it. The thing works, more or less.
Next use case is funded as a new project. New prompts, new evaluation,
new integrations, new governance review, often a different vendor. The
deliverables stop accumulating about a week after each contract ends.

The industry treats this as an execution problem and prescribes more
discipline, better playbooks, a centre of excellence. Our argument is
that the *unit of delivery* is wrong. You cannot solve compounding by
executing harder on the wrong unit.

So: stop selling use cases. Sell the environment they get composed in.
The environment is a working, governed agentic substrate, running in
your cloud, made of four things in combination — none of which is
interesting alone:

- **Skills** — small markdown files declaring an agent's name, its
  description, and the tools it is allowed to call. Centrally governed.
- **MCP servers** — your real systems (Workday, Concur, ServiceNow,
  Greenhouse, Graph) and your third-party APIs, surfaced as Model
  Context Protocol tools with negotiated auth, schemas and contracts.
- **The harness** — agents are spun up on demand with the right skills
  and MCP tools, do their work, and are torn down. There are no
  thousands of standing agents to manage.
- **Identity, security, governance** — the runtime governance kernel
  (AGT), Ed25519-signed agent identities, hash-chained audit ledger,
  policy-driven (not code-driven) behaviour, validators between agent
  output and downstream systems.

The pull-quote: *what you've been buying is a manuscript, what you need
is a press*. Each AI project today is a hand-illuminated book — months
of skilled, painstaking work that does not transfer to the next book.
What we're proposing is the case of type: the alphabet is cast once,
and the next page is *composition*, not construction. The compositor
itself is an agent.

The proof of the thesis sits in the repo: thirteen domains in `main`,
two hand-built, eleven graduated by a meta-skill called `compose-domain`
from a YAML brief. The first hand-built domain took fifteen days. The
most recent compose-domain run took hours.

If you take one line from this primer onto stage with you, take this
one: **the deliverable isn't POC1, and it isn't POC2 — it's the
substrate that runs both, and the next six, and the ninth one you'll
add when you decide what it should be.** POC1 and POC2 are existence
proofs. The substrate is the deal.

---

## 2. The thirty-second elevator version

If a CTO catches you in a corridor before you've started:

> "We've built a single agentic substrate — skills, MCP tools,
> orchestration, governance — that runs eight live business domains on
> a laptop. Two of those domains we built by hand, finance compliance
> and hiring. The other six were graduated end-to-end by a meta-skill
> we wrote, from a YAML brief, over a single weekend. There's one
> Control Plane the operator works in, one governance kernel that
> mediates every tool call, one signed audit chain across the lot. The
> argument is that you stop sponsoring AI projects one at a time and
> you start sponsoring the environment that composes them."

That's enough to earn the next ten minutes.

---

## 3. The architecture, plain English

The substrate is **three tiers plus a governance kernel that sits
across all of them**. This is the diagram in your head:

**Tier 1 — Durable Functions orchestration.** Microsoft Azure Durable
Functions is an event-sourced workflow runtime. One orchestrator
instance per work item — one per expense claim, one per hire, one per
travel pre-approval. Two properties matter for an enterprise fleet:

- It *survives*. State is event-sourced. If the host crashes, if the
  region fails over, if you deploy a new version mid-run, the
  orchestrator picks up from its last checkpoint. Resume isn't a
  feature you build — it's how the runtime works.
- It *parks at zero compute*. When the workflow is waiting on a human,
  no process is sitting idle. Durable Functions stores the state, and
  when the external event arrives, the orchestrator wakes from exactly
  where it left off. So 5,500 end-of-quarter concurrent workflows is
  5,500 rows of state in storage, not 5,500 processes.

This is the answer to the brief's region-recovery acceptance criterion.
It's not custom code; it's a property of the runtime we picked.

**Tier 2 — Microsoft Agent Framework (MAF) graphs per phase.** Inside
the durable envelope, every phase tile on the workflow ribbon is a
typed Pregel graph. MAF is the open-source Microsoft framework that
came out of merging Semantic Kernel and AutoGen — it's the agent
runtime layer. Each graph mixes three kinds of executor:

- *Deterministic code* — schema checks, three-way matches, threshold
  comparisons, EMS lookups. No model involved. You want these to be
  right every single time, so they are just code.
- *Agent calls* — classification, arbitration recommendation,
  notification draft, CV triage. Real LLM calls, real reasoning, real
  tool use. Things where you actually want judgement.
- *Validators* — guardrails between an agent's output and the next
  deterministic step. The agent's output is a typed contract. The
  validator either passes it or sends it back. Bad model output never
  reaches the ledger or the EMS.

The framing the audience needs to hear: **we don't have to trust the
agents everywhere. We deterministic-gate them where we can; we
validate them where we can't.** That's how you go from "clever agent
demo" to "I can put it in production".

**Tier 3 — Fleet Manager (FastAPI session).** This one is structurally
different and most people miss the distinction. The Fleet Manager is
*not* a Durable orchestrator. It's a single, always-on GitHub Copilot
SDK session running inside the FastAPI process. Phase activities emit
events to an in-process event bus; a triage filter decides which events
are wake-worthy; a debounce queue coalesces them; the Fleet Manager
session is invoked over the batch and reasons about cross-workflow
patterns.

It owns the exception queue. It composes recoverable cards from a
batch of related events. It uses MCP tools (`query_fleet`,
`audit_query`, `compose_exception`, `query_economics`,
`query_reviewer_decisions`) the same way phase agents use Workday
tools — the substrate is uniform.

**The fourth tier — governance kernel (AGT).** This is the bit that
crosses all three. The Microsoft Agent Governance Toolkit (AGT) is a
relatively new open-source kit that gives you a single in-process
policy kernel that mediates every MCP tool call any agent makes, with
a hash-chained signed audit ledger underneath. It went to public
preview a few weeks ago. We integrated it as the substrate's runtime
governance core. Section 5 below unpacks it; for now, hold the picture
of a policy kernel that every tool call passes through, in-process, in
both the FastAPI process and the Functions worker.

Two GHCP agent identities matter:

- `<domain>-agent` — `finance-agent`, `hiring-agent`, etc. — handles
  per-phase work inside the graphs.
- `fleet-manager-agent` — the always-on supervisor session.

All authenticated via the single `gh auth token` at boot in the lab
build; engagement-POC swaps to Foundry Hosted Agents on the same shape.
Same skill files, same tool registry, same audit chain. The substrate
doesn't change.

---

## 4. The tech stack, layer by layer with rationale

Read this once and you can fluently answer any "why did you pick X"
question.

### 4.1 Why Microsoft Agent Framework, and what it actually is

MAF is the merged successor of Semantic Kernel and AutoGen. We chose it
because:

- It's the layer Microsoft is putting its weight behind for agent
  graph orchestration, and the bid is to a customer whose cloud is
  Azure-first.
- It uses *typed Pregel graphs*. Pregel is a graph-execution model:
  nodes process inputs, send messages on edges, the graph runs to
  fixpoint or termination. This gives you deterministic graph topology
  and clear state transitions per node — much easier to reason about
  than free-form agent loops.
- It lets you mix deterministic, agent, and validator executors inside
  one phase. That's the architectural primitive that makes "bounded
  probabilism" possible.
- Its OTEL semantic conventions are shared with Semantic Kernel, OpenAI
  Agents SDK, GitHub Copilot SDK, and the broader ecosystem. So the
  same `gen_ai.generate_content` span shape shows up in Foundry
  Tracing whoever the runtime vendor is.

### 4.2 Why GitHub Copilot SDK for agent identities (today), Foundry Hosted Agents (engagement)

In the lab build, every agent identity is sessioned through the GitHub
Copilot SDK, authenticated via `gh auth token`. This is why you can
boot the whole substrate from a single laptop with a Copilot license
and no Azure tenant.

At engagement time, those identities swap to Foundry Hosted Agents —
Azure's managed agent runtime. The skill manifest doesn't change, the
tool registry doesn't change, the audit chain doesn't change. **This is
deliberate**: the SDK is the swap-in seam, by design, so the lab build
is a credible proxy for what runs in Zava's cloud.

If anyone challenges "but the lab uses GHCP, not Azure" — your answer
is that the runtime is the only thing that swaps; the substrate
(skills, tools, kernel, ledger, surfaces) is identical, and the
SCOPE-DELTA doc lists every difference explicitly so nobody is fooled.

### 4.3 Why Durable Functions for orchestration

Three reasons, in order of importance:

1. **HITL waits at zero compute.** A hiring workflow waits on a human
   for days. We are not paying for a process to sit idle. Durable
   parks the orchestrator and resumes on the external event. This
   is genuinely hard to replicate in a hand-rolled stack.
2. **Survives failover.** Event-sourced state means resume is free. The
   bid response includes a region-recovery acceptance criterion; this
   is the answer.
3. **Volume.** 5,500 concurrent workflows is 5,500 rows of state. Most
   alternatives don't scale to that without bespoke engineering.

The honest tradeoff: Durable's Python support is sync-on-async (we wrap
async activities in `asyncio.run`), which is mildly ugly. We accept
that because the production properties dominate.

### 4.4 Why Model Context Protocol (MCP) for every external system

MCP is an open protocol Anthropic put out and Microsoft, OpenAI, and
the rest of the industry have rallied behind for how agents talk to
tools. We chose it as the *one* integration shape and pushed everything
behind it: Workday, Concur, Maconomy, Greenhouse, ServiceNow,
Microsoft Graph, the lot.

What you get from forcing the convention:

- The agent doesn't know the difference between Workday and Concur.
  It sees a tool catalogue (`claim_lookup`, `policy_search`,
  `employee_history`) and the MCP server underneath maps that to
  whatever the actual EMS calls are. Swap Workday for Workday vNext —
  the agent code doesn't change.
- One place where authentication lives — APIM AI Gateway in front of
  every MCP, with credentials in Key Vault. The agents never see a
  token, which is how you avoid the obvious incident pattern.
- One place where governance lives — the AGT kernel chokepoint. Every
  tool call is an MCP call; every MCP call goes through the kernel;
  every kernel decision goes into the audit chain. There is no back
  door.

Adding a new EMS becomes three steps: register the MCP server in the
gateway, declare the tool in the relevant skill manifest, publish.
That's the architecture-as-extensibility-answer claim.

The bonus property worth knowing: APIM has a REST-to-MCP gateway
feature that auto-generates the MCP tool surface from an OpenAPI spec.
Most Zava teams have REST APIs already, so this is a config-file step,
not a custom build.

### 4.5 Why Skills (markdown + allow-lists), not prompts

This is the architectural choice that underpins everything you'll show.
There are two camps in the industry on how you build an agent:

- **Camp one — prompt-engineered.** You take a big language model, you
  write a lengthy system prompt ("you are a finance agent, you do this
  and that, here are some rules, please be careful"), and you plug a
  few tools in. It works in demos. It falls over the moment your
  auditor asks "show me where it says the agent can't write to
  Workday." The answer is — it doesn't say that anywhere. The prompt
  asks nicely. The model usually complies. There is no policy.

- **Camp two — skills + tools** (what we built). Each agent has a tiny
  markdown file we call a SKILL file. It declares three things: name,
  description (one or two sentences), and an *allow-list* of tools.
  The runtime literally cannot call a tool that isn't in the list. The
  CV-crystalliser agent has access to `ocr_extract` and that's it.
  The budget-checker has Workday position-read and an Adaptive Card
  composer and that's it. The classifier can read policy and structured
  claim data — it has *no write tools at all, anywhere*.

So when the auditor asks "how do I know this agent isn't doing
something I don't expect" — the answer is the SKILL file plus the tool
registry. Both are in version control. Both are signed. **Neither
involves trusting the model.**

This composes with the kernel layer (section 5). Tools declared in
SKILL files have to be declared in the tool registry. The registry is
what compiles into the policy bundle. The bundle is what the kernel
evaluates against. So "agent declares it can use a tool" and "kernel
allows the tool to be called" are two separate gates that both have
to pass. Defence in depth, structurally.

### 4.6 Why FastAPI alongside Functions

Why are there two Python processes? Because Fleet Manager is not a
Durable orchestrator and shouldn't be one. It needs a long-lived agent
session reasoning across many in-flight workflows; that doesn't map to
"one orchestrator instance per work item." So Fleet Manager runs in
FastAPI (uvicorn :3001) and reacts to events the Durable orchestrators
emit. The Functions host (:7071) handles all per-workflow durable
state. They share the in-process kernel and the audit ledger via
identical configuration; they don't share memory.

### 4.7 React + Vite for three frontends

Three separate Vite apps:

- Control Plane (`:5173`) — the operator surface, domain-neutral.
- Candidate Portal (`:5174`) — POC2 candidate-facing app + recruiter
  view.
- Blueprint microsite (`:5175` locally, deployed to Azure Container
  Apps) — the editorial pitch page + live observatory of the substrate.

The split matters for the demo: the Control Plane has *zero*
hiring-specific vocabulary. Open a hiring workflow in it and the wait
label says *Awaiting operator review*; the deep-link says *Open
recruiter view*. The same page, opened on an expense workflow, says
*Open reviewer queue*. The role-specific surfaces hang off the
domain-neutral Control Plane. That's the platform split working as
designed and a thing to point at on stage.

### 4.8 Azure Document Intelligence for OCR

Real Azure DI calls — `prebuilt-receipt`, `prebuilt-layout`,
`prebuilt-invoice`, `prebuilt-idDocument`, `prebuilt-document` models —
wrapped behind one MCP tool (`ocr_extract`) with a sha256+model cache.
Both `receipt-validator` (POC1) and `cv-crystalliser` (POC2) call it as
their first step. Different document classes, different prompts,
different output schemas, *same MCP tool*. That's the integration-shape
claim made concrete.

Authenticated via Entra-ID; tenant policy disables key auth on
Cognitive Services, so this is the production-shaped path even on the
laptop.

### 4.9 Azure Communication Services for email

Real ACS email send at the candidate-portal boundary. When a candidate
applies, the magic-link email goes out via real ACS. Same for offer
URLs and booking URLs. Real send, real domain, real delivery. Mocked
edges, real where it matters.

### 4.10 Azure GPT-Realtime over WebRTC for the voice screen

The voice screen in POC2 is a live WebRTC call to Azure's GPT-Realtime
endpoint. Real model, real voice, real latency. The agent on the other
end is briefed off the candidate's CV and asks role-relevant questions.
Transcript posts back; workflow resumes.

There's a fallback for when the laptop's mic is awkward in front of an
audience: `VITE_VOICE_TRANSPORT=canned` plays a recorded transcript
through the same callback path. If a click goes wrong live, fall back
gracefully — the runbook has the curl one-liner against
`/api/portal/voice/complete` if you need to bypass the UI entirely.

### 4.11 Azure AI Speech for the onboarding avatar

Real Speech avatar with voice synthesis at the candidate-facing edge.
Blob-cached by SHA of voice plus script — the second render of the
same content is free. Worth pointing at for two reasons: it's a real
multimodal capability, not a slideware claim; and it's the kind of
production a video team used to do.

### 4.12 Azure Storage for the audit ledger

Every audit ledger entry is dual-written: in-memory list (for fast
reads on the workflow detail page) and an Azure Storage append blob
keyed on `workflow_id`, in container `audit-ledger`, on storage
account `apexdemo62525`, with **version-level immutability turned on**.

The retention policy is enforced by Azure itself — not by our code,
not by anyone's goodwill. If we tried to mutate that blob, Azure would
refuse. If someone with full RBAC on the storage account tried to
delete it, Azure would refuse until the retention period expired. So
between the chain integrity and the storage immutability, both have to
fail, through completely different mechanisms, for the audit to be
wrong.

This is the answer to "how do I know what the agents actually did last
quarter when the regulator asks me." The honest answer in most agentic
stacks is "we hope the logs survived." The answer here is "here's the
blob, here's the CLI, run it yourself."

### 4.13 Foundry / Application Insights for telemetry

App Insights connection string is wired into both processes. The
Foundry portal's *Tracing* tab at https://ai.azure.com surfaces every
`gen_ai.generate_content` span with `gen_ai.agent.name`,
`gen_ai.request.model`, `zava.skill`, `gen_ai.usage.input_tokens` /
`output_tokens`, plus tool-call children. **Same OTEL conventions
Microsoft Agent Framework, Semantic Kernel, the OpenAI Agents SDK, and
GHCP all share.** This is not proprietary telemetry; anyone who builds
an agent on the same conventions plugs straight into the same Foundry
view.

If you have connectivity in the room, switching tabs from the local UI
to the Foundry portal mid-demo is a strong move. If you don't, just
say it once and move on.

### 4.14 The cost-per-task number

Real `gen_ai.usage` token telemetry off the agent runs, multiplied by
Microsoft's published per-million-token rates, sourced this week. Not
a synthetic constant. The honest caveat — the model SDK doesn't always
emit token counts on every call; when it doesn't, we estimate from
prompt length plus tool payload using a chars-over-four heuristic, and
*every span carries a provenance tag* — `sdk` or `estimated`. So your
auditor can always tell which is which on a per-call basis.

The tile on the workflow page is the same number Foundry shows you
when you open the same workflow in the Foundry tracing tab.

---

## 5. AGT — the bit your CISO will want to spend the most time on

The Microsoft Agent Governance Toolkit (AGT) is the most important
piece of new tech in the build. This is the section to read twice.

It's a Microsoft Research kit — open-source, public-preview a few weeks
ago — that provides a single in-process policy kernel mediating every
MCP tool call, with a hash-chained, JWS-signed audit ledger underneath.
It is, essentially, the missing governance layer that nobody had a
clean answer for in the agentic stack until now.

Why this is the bit you should be most proud of: it took the bid
response's claim of "OWASP Agentic Top 10 — ten of ten" from being a
marketing assertion into being a thing your auditor can re-derive
themselves from a CLI command and the audit blob. The OWASP-10 badge
in the README links to the plan doc that walks every item.

There are four moving parts to land:

### 5.1 Policy compile-and-publish

There's one place where policy lives:

- A *delegated authority matrix* — 80 rules in
  `data/synthetic/authority/matrix.json`, version-controlled, signed.
  Resolves `(action, value, category, business_unit, geography,
  requester_role) → approver` for every approval gate in every domain.
- A *tool registry* declaring for every MCP tool whether it's
  reversible, what it costs, who can call it.

When something changes — a new approval threshold, a tool gets locked
down — it's a pull request against those two files. The policy bundle
compiles deterministically: same inputs always produce the
byte-identical output, with a hash printed to the console at boot.
That determinism matters because it means the auditor can take the
YAML out of the audit blob, recompile it from the source files at the
timestamp on the entry, and prove they match. No drift, no "who
changed what when" arguments.

Once it's published, every agent session, on every tool call,
evaluates against the bundle that was live at *that* timestamp. So
"how does a new policy reach the fleet" is — merge, publish, sub-second
propagation. No agent restart. No deploy. The kernel reloads in
process.

### 5.2 The runtime kill switch

The compile-and-publish flow is governed and slow, which is the right
answer for the 99% case. But sometimes you need *stop, now*. Something
is misbehaving, an agent is looping on a tool, a vendor's API is down
and you don't want fifty agents hammering it. The kill switch is the
runtime override.

The operator fills in a form on the workflow sidebar — actor or tool,
TTL, reason — and posts it. Example: `concur.submit_decision`, 30
minutes, reason "investigating duplicate submissions." The kernel
consults the kill table on every single tool call. The next attempt
by any agent anywhere in the fleet to call that tool comes back with a
structured `GovernanceDenied` decision, with a `decision_id` the
operator can trace through Foundry. **The Functions worker doesn't
restart. There is no deploy. It is hot.**

That's the operational fire-extinguisher your security team needs in
their hand before they'll ever sign off on increasing autonomy.

### 5.3 The Evidence chip — three sub-checks

This is the part where the OWASP claim becomes auditor-reproducible.
The Evidence chip in the workflow detail sidebar has three sub-chips,
all of which are normally green:

**Chain.** Every entry in the action ledger has a SHA-256 hash of the
previous entry baked into it. So the ledger is a hash chain — if anyone
in the middle modified any entry, every subsequent entry's hash would
no longer match. The chain check verifies the whole chain end to end.
If it goes red, it tells you exactly which entry broke.

**Signatures.** Every entry is signed by the actor that produced it.
Ed25519, JWS compact serialisation. Each agent has its own keypair;
the public keys are committed in the repo, the private keys are in
Key Vault in production. The signature check verifies that every
entry was signed by the actor it claims to be from. Nobody can forge
a "finance-controller approved this" entry — *not even the agents*.

**Decisions.** Every entry references a `decision_id` from the
governance kernel, which references the policy bundle hash that was
live at that moment. The decision check verifies that every referenced
decision still resolves cleanly against a known bundle in the bundle
history. So nobody can claim "the policy at the time allowed this" if
the policy never said any such thing.

Three checks, all green, and you have an auditor-reproducible proof
that every action in this workflow was taken by the actor the ledger
says, against the policy the ledger says, in the order the ledger
says.

There's a CLI version too — `agt verify` — which the auditor can run
against the audit blob from their laptop, no access to the substrate
required. So your external auditor doesn't even need permissions in
your system; they just need read access to the blob.

### 5.4 Storage immutability

Section 4.12 above. The chain proves the *content* hasn't been tampered
with. Storage immutability proves the *blob* hasn't been tampered with.
Different mechanism, different failure mode, both have to fail.

### 5.5 OWASP Agentic Top 10 — what the badge actually means

The README carries a green badge: "OWASP Agentic Top 10 — 10/10
covered." OWASP published this list as the canonical taxonomy of
agentic-AI risk. The full mapping is in the AGT plan doc; the
short summary of what each item maps to in our build:

- *Memory poisoning* — typed contracts on every persisted artefact;
  validators between agent output and storage.
- *Tool poisoning* — the tool registry is the *only* declaration of
  what tools exist; agents cannot invent tools; CI fails on
  unregistered agents calling registered tools.
- *Privilege compromise / excessive agency* — per-agent capability
  declarations + value-ceiling gates + reversibility-aware policy
  enforcement. The classifier *literally* cannot call a Workday write
  tool.
- *Resource overrun / cascading failures* — kill switch + per-tool
  TTLs.
- *Repudiation* — Ed25519 JWS signatures; nobody can deny an action
  they signed.
- *Identity spoofing* — per-agent Ed25519 keypairs; public keys in
  repo, private in Key Vault.
- *Supply-chain compromise* — deterministic policy-bundle compilation;
  hash printed at boot; CI gate on bundle drift.
- *Unbounded consumption* — token budget enforcement at the kernel.
- *Hallucination cascade* — validators between agent output and
  downstream state.
- *Misaligned goals* — skills + tool allow-lists are policy, not
  prompt; the kernel decides whether a tool call happens.

You don't need to land all ten on stage. You need to be able to say
"every item maps to a concrete kernel mechanism, the mapping is in the
plan doc, and `agt verify` is the CLI an auditor would actually run."

---

## 6. The five demo pillars, with the conceptual point each one is making

This is the structure of the script. Internalise the *point* of each
pillar so if you go off-script you can still land it.

**Pillar 1 — Control Plane.** Operators move up a layer. From doing
the work to overseeing the work. The Finance Controller never logs into
Workday; their job is to govern the fleet of agents that does. The
elegant property: controller and agents share *one event bus*. There
is no admin database separate from the workflow database. The audit
chain has both the agent's actions and the human's actions, in the
order they actually happened.

**Pillar 2 — Multi-agent orchestration & durability.** Three layers
(Durable, MAF graphs, agent identities), and *we don't have to trust
the agents everywhere*. We deterministic-gate them where we can; we
validate them where we can't. That's how you go from clever demo to
production.

**Pillar 3 — Governance.** AGT. Three pieces: policy compile-and-
publish, runtime kill switch, three-check Evidence chip. Auditor-
reproducible. Storage immutability is enforced by Azure, not by us.

**Pillar 4 — Integration.** Two integration shapes (direct via MCP,
data layer via Databricks); one chokepoint (the kernel) for both.
Adding an EMS is three steps, not three months. The brief's
extensibility criterion is the architecture, not a roadmap commitment.

**Pillar 5 — POC2 advanced.** Same engine, different domain. Real
WebRTC voice, real avatar, real ACS email, real DI on a different
document class. POC2 is the proof that "one platform, many domains"
isn't aspirational; it dropped in clean as a separate domain through
the registry.

**Close — agentic loop + Constellation.** The architectural choice that
makes everything work is *skills + tools, not prompts*. Allow-lists are
policy. Prompts aren't. Constellation is what scale across Zava's
operating model looks like, on the same substrate, with the same
governance, on day one.

---

## 7. POC2's distinctive bits — what the hiring demo proves that finance can't

If you're asked why you bothered building POC2 when POC1 already proves
the substrate, this is your answer. POC2 demonstrates capabilities that
POC1's domain shape doesn't exercise:

- **Real WebRTC voice agent** in production-shaped configuration.
  Synchronous, multimodal, real latency. The voice screen at Phase 6 is
  not a clever pre-recording.
- **Real avatar synthesis** at the candidate-facing edge. The
  onboarding moment.
- **Real Document Intelligence on a different document class.** Same
  `ocr_extract` MCP tool, different prompt, different output schema.
  The integration-shape claim made concrete.
- **Real ACS email** at the boundary. Magic-link tokens, single-use,
  TTL-bound.
- **Multi-actor, multi-surface workflow.** Candidate, recruiter, hiring
  manager — three different humans, three different surfaces,
  coordinated through one orchestration. POC1 has one operator; POC2
  has three.
- **Jurisdiction-conditional behaviour.** Rerun the same hiring flow
  with `C-SE-DE-00` instead of `C-SE-USA-00` and the same code path
  adds a Compliance phase for the German works-council notification —
  because the graph is data-driven off the candidate's country.

Phase 7 is where the orchestrator earns its keep. Three sequential
human gates: recruiter invites to interview, candidate books a slot,
recruiter makes the post-interview decision. Each one parks the
orchestrator on a different external event. The recruiter view paints
a different decision card for each one, keyed off the workflow's
current `awaiting_reason`. **The human always sees the right thing to
do next; they never have to remember which step they're on.**

The deliberate refusal-to-fabricate property is worth highlighting
specifically: if Document Intelligence fails or returns low confidence,
you see a red chip and *no recommendation*. The agent is wired to
refuse to fabricate a verdict when it doesn't have ground truth. For
HR — especially in jurisdictions like the EU where automated decision-
making on candidates is regulated — that *don't hallucinate when you
don't know* property matters more than any individual feature on the
page.

---

## 8. Composition, not construction — what `compose-domain` actually does

This is the closer. The argument the substrate is *composable*, not
just reusable.

POC1 (finance) and POC2 (hiring) were hand-built. The other six domains
on the Constellation ring — travel pre-approval, vendor KYC, employee
onboarding, IT access requests, contract renewal, performance review —
were graduated end-to-end by a meta-skill called `compose-domain` from
YAML briefs.

What `compose-domain` actually is: a skill (markdown + tools) that
takes a YAML brief describing a new domain, and emits the registry
entry, the orchestrator class, the phase graphs, the persona set, the
seed data, and the per-domain skill stubs. It runs the existing
substrate against that brief and produces a working domain. Six times
in a row, no human in the loop on the substrate side, over a single
weekend.

The reason this is cheap is that every per-domain integration fact
lives in one Python file: `api/shared/domains.py`. Phases, EMS
adapters, persona set, skill list, HITL gates, persona map, operator
surface, wake hints — all in one place. The Control Plane reads from
it. The Fleet Manager reads from it. The simulator reads from it. The
phase ribbon reads from it. So adding the ninth domain is a registry
entry plus a YAML brief.

Every domain on the ring inherits everything you've shown: one Control
Plane, one AGT governance kernel (same OWASP coverage, same kill switch,
same Evidence chip, same audit chain), one Foundry project (same OTEL
conventions, same evaluation pipeline, same cost ledger, same tracing
tab), one agent registry, one tool registry, one policy bundle.
**There is no per-domain governance story, because there is no
per-domain substrate.**

A second meta-skill — `compose-persona` — graduated 14 of the 29
registered personae from YAML briefs in the same way. The "compositor
itself is an agent" claim isn't a future hope; it's the procedure these
personae arrived through.

---

## 9. What's real and what's mocked — know this cold

The first thing the audience will wonder. Don't make them ask:

**Mocked at the edges:**
- The EMS connectors — Workday, Concur, Maconomy — are local Node
  mocks running on the laptop on ports 4101/4102/4103.
- The HR/comms connectors — Greenhouse, LinkedIn, Workday-HR, Graph,
  ServiceNow, ACS-mock, HeyGen — are Node mocks on 4201–4207.
- The fleet-* domains use deterministic stubs in `api/server/mcp_tools/`
  rather than a separate Node server.
- Synthetic data — claims, employees, precedents, policies, candidates,
  CVs — committed under `data/synthetic/`.

**Real where it matters:**
- Azure Document Intelligence (OCR on receipts and CVs).
- Azure Storage with version-level immutability (audit ledger blob).
- Azure Communication Services (email send for candidate magic links).
- Azure GPT-Realtime over WebRTC (voice screen).
- Azure AI Speech (onboarding avatar).
- LLM calls (real GitHub Copilot endpoint; engagement-POC swaps to
  Foundry Hosted Agents).
- Telemetry (App Insights → Foundry Tracing).

The line to use: **"mocked at the edges, real where it matters."** It's
honest and it pre-empts the gotcha question.

The reason the EMS is mocked is deliberate, not a shortcut: it lets
the audience watch the end-to-end flow without waiting on sandbox
credentials. The MCP contract is the swap-in seam — the agent code,
skill prompts, validators, and registry don't change when the engagement
POC plugs into real Workday SAML-Okta, real Concur OAuth 2.0, real
Maconomy REST behind APIM AI Gateway with Key Vault credentials.

---

## 10. Vocabulary cheat sheet

Quick definitions of jargon you'll be saying. If you flub the term in
front of a CTO, you lose credibility you don't have to.

- **AGT** — Agent Governance Toolkit. Microsoft Research's open-source
  kit for in-process policy enforcement and signed audit trails.
- **MCP** — Model Context Protocol. Anthropic's open protocol for how
  agents talk to tools. Industry-standard now.
- **MAF** — Microsoft Agent Framework. The merged successor to Semantic
  Kernel and AutoGen. Typed Pregel graphs.
- **Pregel** — a graph-execution model. Nodes process inputs, send
  messages on edges, run to fixpoint or termination. Predictable
  topology, predictable state.
- **Durable Functions** — Azure's event-sourced workflow runtime.
  Survives crashes; parks at zero compute on external events.
- **GHCP SDK** — GitHub Copilot SDK. The Python SDK we use to spawn
  agent identities in the lab build. Swaps to Foundry Hosted Agents at
  engagement time.
- **Foundry** — Azure AI Foundry. The portal/runtime layer for agents
  and observability. We use it for tracing, evaluation, hosted agents.
- **OTEL** — OpenTelemetry. The vendor-neutral observability standard.
  We emit `gen_ai.*` semantic-convention spans that Foundry, Datadog,
  whatever, all understand.
- **HITL** — human-in-the-loop. A gate where the workflow parks for
  human input.
- **JWS** — JSON Web Signature. Compact-serialisation signatures on
  every audit-ledger entry, Ed25519.
- **Ed25519** — the elliptic-curve signature algorithm. Modern, fast,
  small keys.
- **Skill** — a markdown file with name, description, and
  `allowed-tools` allow-list. The unit of agent behaviour.
- **Persona** — a markdown file with a `decision_policy` block that
  says how a human role would decide on a HITL gate. Drives the
  autonomous demo loop.
- **Validator** — code that sits between agent output and the next
  deterministic step; bounces bad output. The "bounded probabilism"
  edge.
- **Compose-domain / compose-persona** — the meta-skills that graduate
  new domains and personae from YAML briefs.
- **Registry** — `api/shared/domains.py`. The single Python file where
  every per-domain integration fact lives.

---

## 11. Q&A — what to actually say, not just the one-liner

The script ends with one-liners. Here's the slightly fuller answer for
each.

**"Are the cost numbers real?"**
Real `gen_ai.usage` token telemetry where the SDK reports it,
chars-over-four estimate when it doesn't. Every span is provenance-
tagged `sdk` or `estimated`. The number on the workflow tile is the
same number Foundry will show you when you open the workflow in the
Foundry tracing tab. Microsoft's published per-million-token rates,
sourced this week.

**"How do you know the audit can't be tampered with?"**
Two mechanisms, different failure modes, both have to fail. (1) Ledger
is a SHA-256 hash chain — modifying any entry breaks every subsequent
hash. (2) Ledger is also dual-written to an Azure Storage append blob
with version-level immutability — Azure refuses mutation, refuses
deletion within the retention window, even from full RBAC. Plus the
Ed25519 JWS signature on every entry means even forging an entry
requires the actor's private key, which lives in Key Vault.

**"How do you add a new domain?"**
Registry entry in `api/shared/domains.py` plus a YAML brief through
`compose-domain`. Six in a single weekend. The Control Plane, the
Fleet Manager, the simulator, the blueprint inventory all read from
the registry at runtime, so a new domain lights up everywhere with
no per-domain branches.

**"What's Foundry's role?"**
Telemetry, evaluation, observability, hosted agents. Next to the
runtime, not in front of it. Same OTEL conventions every major agent
SDK shares, so the telemetry isn't proprietary.

**"What's different between this lab build and the engagement POC?"**
SCOPE-DELTA.md lists every difference. The headlines: agent identities
swap GHCP SDK → Foundry Hosted Agents on the same shape; backends swap
mocks → real Workday/Concur/Maconomy via APIM; storage swaps Azurite
→ Cosmos with point-in-time restore. The substrate, the kernel, the
surfaces, the skill manifests, the tool registry, the audit story —
unchanged.

**"Why allow-lists, not prompts?"**
Allow-lists are *policy*. Prompts aren't. The kernel decides whether
a tool call happens, not the prompt. The CV-crystalliser literally
cannot call a Workday write tool because the runtime refuses the call.
Your auditor can read a SKILL file and a tool manifest in a coffee
break — they cannot reasonably reason about a multi-thousand-token
prompt under adversarial input.

**"You claim ≥95% accuracy on POC1. Where's the number?"**
The pipeline and prompt are live and demonstrable. The corpus-wide
gate is reserved for Zava's 3,430-line real dataset; running it on the
synthetic 300 wouldn't be a meaningful number. The bid response is
explicit: ≥95% on the Zava dataset, 40% of the POC1 score, run after
engagement kickoff when Zava supplies the data.

**"How does this scale beyond a laptop?"**
Each tier has a clear scale-up path. Durable Functions runs on Azure
Storage with geo-redundant durable hub in production. FastAPI scales
horizontally; the only process-local state today is the
`sendEventPostUri` cache in `durable_client.py`, which moves to Redis
for multi-worker. MCP servers scale horizontally behind APIM. The
governance kernel is reentrant, in-process, no shared state. The
synthetic-state ceiling we hit on a laptop is the Functions Python
async-sync wrapper, not the architecture.

**"How does a new policy reach a running agent?"**
Merge the change to the delegated-authority matrix or the tool
registry. The bundle compiles deterministically (hash printed at
boot). Publish. Sub-second propagation. No agent restart. No deploy.
The kernel reloads in process. The boot-time hash and the entry-time
hash are both in the audit chain so the auditor can re-derive what
policy was live when.

**"What if an agent goes rogue?"**
Three layers of protection. (1) The skill's allow-list — the runtime
won't pass a tool call that isn't declared. (2) The validator — bad
typed output bounces. (3) The kernel — a runtime kill-switch the
operator can apply by actor or tool, with TTL, no deploy. Plus every
action is signed and chained, so post-incident forensics is a CLI run
against the audit blob.

**"How is this different from \[LangGraph / AutoGen-only / one-vendor
proprietary stack\]?"**
We're using MAF, which *is* the merger of Semantic Kernel and AutoGen
under Microsoft, plus the open MCP protocol and the open OTEL
conventions. So the substrate composes with the open ecosystem rather
than locking into one stack's idioms. The agent identities are swap-in
(GHCP SDK today, Foundry Hosted Agents tomorrow), the tools are
MCP-shaped (so the same tool surface works for any MCP-aware client),
and the telemetry is OTEL (so any observability vendor reads it). The
governance kernel (AGT) is itself open-source. There is no proprietary
low-code studio in the way.

**"How does this handle multi-tenancy at Zava scale?"**
Two answers. At the data layer, Unity Catalog enforces row-level
security on the Databricks read path; identity is propagated through
the MCP call. At the agent layer, identities are per-domain (and could
be per-business-unit at engagement scale); the kernel evaluates
authority per-call against the matrix, and the matrix has business-unit
and geography as resolution axes. The 80-rule matrix in the lab build
is a small example; the production matrix is whatever Zava's delegated
authority schedule actually is.

---

## 12. Things to drop into conversation that signal you've actually built it

Slide-deck people don't say these. Pick one or two if the conversation
gets technical:

- "The Functions worker doesn't restart when the kill switch fires.
  It's a hot kernel reload."
- "The OTEL spans use the same `gen_ai.*` semantic conventions MAF, SK,
  the OpenAI Agents SDK and Copilot all share — the telemetry isn't
  proprietary."
- "Resume isn't a feature you build. It's how the runtime works."
- "The `compose-domain` meta-skill graduated six domains over a single
  weekend from YAML briefs. The reason it's cheap is that every
  per-domain fact lives in one Python file, `api/shared/domains.py`."
- "The agent's output is a typed contract. The validator either passes
  it or sends it back. Bad model output never reaches the ledger or
  the EMS."
- "Storage immutability is enforced by Azure, not by us. If we tried
  to mutate that blob, Azure would refuse. Even with full RBAC, the
  retention period has to expire first."
- "Adding the ninth domain is a registry entry plus a YAML brief. Not
  a refactor."
- "Defence in depth, but the depth is structural, not bolted on."
- "We don't have to trust the agents everywhere. We deterministic-gate
  them where we can, and we validate them where we can't."

---

## 13. What NOT to claim — staying credible

These are the gotchas that destroy credibility if you overreach:

- **Don't claim the synthetic accuracy run is a meaningful number.**
  AC #4 is explicitly punted to engagement-POC scope on Zava's
  3,430-line dataset.
- **Don't claim the lab build has Entra Agent ID.** That's the
  engagement-POC posture. Lab runs on a single `gh auth token`.
- **Don't claim the lab build talks to real EMSes.** It talks to
  mocks; the contract is the swap-in seam. Be explicit about that.
- **Don't claim cost numbers are exact.** They're real where the SDK
  reports tokens, estimated where it doesn't, provenance-tagged.
- **Don't claim the eight domains run on the cloud.** The cloud
  artefact is the *blueprint microsite container*, intentionally
  scope-A — page only, no durable runtime, no live event bus. The
  microsite replays JSONL recordings baked in at build time.
- **Don't claim the Constellation ring is animated by live cloud
  workflows.** It's the local laptop's actual workflow stream, in
  the local microsite. In the deployed microsite, it's recordings.
- **Don't claim AGT is generally available.** It's public-preview, a
  few weeks old. We integrated it. That timing is a feature, not a
  bug — but be honest about its maturity.

---

## 14. If something goes wrong on stage

Three recovery moves to memorise:

1. **A click doesn't do what you expect.** "OK that's the laptop being
   a laptop — but what you'd see is —" then describe it and move on.
   *Do not* try to fix it live.
2. **You blank.** Any of these is a valid landing: "The thing I want
   you to take away here is —" / "And the reason that matters is —" /
   "Let me put a name on what you're looking at —"
3. **The mic on the voice screen acts up.** Use the canned-transport
   env switch (`VITE_VOICE_TRANSPORT=canned`) or curl
   `/api/portal/voice/complete` with a stub transcript. Same code path
   resumes the workflow. Move on.

If the audience asks something off-script: *park it*. "Great question
— let me get to the end of this beat and come back to it." Then
actually come back to it. Don't get derailed; don't pretend to
remember.

---

## 15. The closing line

Memorise this verbatim. It's the line that does the work:

> "The deliverable isn't POC1, and it isn't POC2. The deliverable is
> the substrate that lets you run both, and the next six, and the
> ninth one you'll add when you decide what it should be. POC1 and
> POC2 are existence proofs. AGT is what makes the OWASP-10 claim
> something your auditor can re-derive themselves rather than
> something you have to ask them to take on faith. And Constellation
> is what scale across Zava's actual operating model looks like, on
> the same substrate, with the same governance, on day one.
>
> Happy to take questions."

Good luck on the train. You've got this.
