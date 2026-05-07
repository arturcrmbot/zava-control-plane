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
| Pillar 2 — Orchestration & durability | 4 | same workflow + Foundry trace |
| Pillar 3 — Governance (AGT) | 5 | Evidence chip, kill switch, audit blob |
| Pillar 4 — Integration (MCP + Databricks) | 4 | `/fleet` cross-EMS view |
| Pillar 5 — POC2 advanced | 6 | portal apply → triage → voice → avatar |
| Close — agentic loop + Constellation | 3 | `:5175/?view=constellation` |

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

> Surface: stay on `/fleet`. The fact that you can see claims from
> different EMS sources sitting next to each other in this view is
> the demo for this pillar; you don't necessarily need to open
> another window.

"OK so let's talk integration, because this is the bit that
usually kills these projects. The brief is explicit on it — claims
from multiple EMS, one Control Plane view, system-agnostic to the
operator, and a path to add a third EMS without having to rewrite
the agents. That's a tall order if you're plugging things in
ad-hoc. So we made an early architectural call here that I want
to walk you through, because it's worth the few minutes.

There are essentially two integration shapes you'll find inside
WPP. There's direct integration to business systems — REST APIs,
SOAP if you're unlucky, that kind of thing. And there's the data-
layer pattern where the source of truth has been consolidated into
a lakehouse, typically Databricks. We support both, because every
real customer has both, and you cannot pick one and tell people
'sorry, you have to migrate'.

### Direct to systems — MCP everywhere

For the direct shape, every external system in this build —
Workday, Concur, Maconomy, Greenhouse, ServiceNow, Microsoft
Graph, the lot — sits behind an MCP server. Model Context Protocol.
That's the open protocol Anthropic put out and Microsoft, OpenAI
and the rest of the industry have rallied behind for how agents
talk to tools.

What that buys you, very concretely:

The agent doesn't know the difference between Workday and Concur.
It sees a tool catalogue — `claim_lookup`, `policy_search`,
`employee_history` — and the MCP server underneath maps that to
whatever the actual EMS calls are. So if you swap Workday for
Workday vNext, or move from on-prem Concur to cloud Concur, the
agent code doesn't change. You change the MCP server.

There's one place where authentication happens. APIM AI Gateway in
front of every MCP. OAuth, SAML, on-behalf-of — all handled at the
gateway, with credentials in Key Vault. The agents never see a
token. That matters because the alternative — agents holding
credentials — is how you end up with a security incident.

And there's one place where governance happens, which is the AGT
chokepoint we just looked at. Every tool call is an MCP call, every
MCP call goes through the kernel, every kernel decision goes into
the audit chain. There isn't a back door. If you want a new
integration, you have to register the tool — and the tool registry
is what the policy bundle is compiled from.

So adding a new EMS — and Maconomy was literally our third one,
we did it during the build — is three steps. Register the MCP
server in the gateway. Declare the tool in the relevant skill
manifest. Publish. The agent skills don't change. The Control
Plane doesn't change. The audit story doesn't change. That's the
brief's extensibility criterion, and the answer to it is the
architecture, not a roadmap commitment.

One bonus property worth knowing — APIM has a REST-to-MCP
gateway feature that auto-generates the MCP tool surface from an
OpenAPI spec. So if your team has REST APIs already, which most
WPP teams do, that's a config-file step rather than a custom
build.

### Data layer — Databricks pattern

For the data-layer shape, where the source of truth is a lakehouse
— Databricks, Fabric, anything Delta-format — we don't fight it.
You don't want agents writing into your governed lake; that's not
what lakes are for. So the pattern is:

For reads, an MCP tool fronts a SQL warehouse or a Databricks SQL
endpoint. The agent issues structured queries against governed
views — Unity Catalog enforces row-level security, the agent's
identity is propagated through, the audit story carries because
every query is still an MCP call going through the same chokepoint.
So 'agent reads from the lake' has the same governance properties
as 'agent reads from the EMS'.

For writes, our pattern is — agents write to the systems of record,
not to the lake. Workday is the source of truth for the claim,
Concur is the source of truth for the receipt, the lake aggregates
*from* those. So when the workflow needs to post a decision, it
posts to Workday. The lake catches up via the customer's existing
ingestion pipeline. We don't get in the middle of that.

The point is the two shapes aren't an either/or. The same workflow
can pull a candidate's reference data from Databricks for context,
make decisions through the Foundry-hosted agents, and post the
offer back into Workday — all in one orchestration, all governed
through the same kernel.

### One registry — the substrate's claim, made concrete

*(optional — flip to `api/shared/domains.py` in your editor for
two seconds, then back)*

And the reason adding a new domain is cheap — and we'll see this
fully at the end — is that every per-domain integration fact lives
in one Python registry file. Phases, EMS adapters, persona set,
skill list, all in one place. The Control Plane reads from it. The
Fleet Manager reads from it. The simulator reads from it. The
phase ribbon reads from it. So adding the ninth domain is a
registry entry plus a YAML brief. We graduated six domains over a
single weekend that way."

---

## Pillar 5 · Advanced capabilities — POC2 — 6 min

> Surface: candidate portal at `:5174/apply`. Close the Control
> Plane tab so the audience isn't half-watching the fleet while
> you're trying to walk a candidate journey.

"OK pivot. Completely different domain — hiring. Completely
different audience for the surfaces — candidate, recruiter, hiring
manager. The reason I want to show you POC2 right after POC1 is
that the engine running underneath is *the same engine* — same
durable orchestrator, same agent graphs, same governance kernel,
same audit blob with the same Evidence chip you just saw. What's
different is the surfaces and the multimodality.

It's worth saying — we did not build POC2 by retrofitting POC1.
POC2 dropped in clean as a separate domain, through the registry
we just talked about. So this is the substrate's claim made
literal: 'one platform, many domains' isn't an aspiration, it's
something we did and you're about to see it.

Four moments. Apply, AI triage, voice screen, offer.

### Moment one — apply

*(open `:5174/apply`, pick Senior Data Engineer · USA, drop in
`data/synthetic/hiring/cv-pdfs/C-SE-USA-00.pdf`, submit, copy the
candidate id)*

Public form. No login, no SSO. This is what a candidate sees on a
careers page. Behind that — orchestrator spawned, magic-link
status URL has gone out via real Azure Communication Services
email, the workflow is already running through Triage. So even
before the recruiter has looked at this person, the system is
working.

### Moment two — AI triage with real OCR

*(open `:5174/recruiter`, click into the candidate)*

This panel — *What we learned* — is the live trace from the agent
that's reading the CV. The row that says `tool · ocr_extract` is a
real Azure Document Intelligence call against the PDF. Below that
you see the structured profile the agent extracted, the token
usage, the latency.

One thing I want to call out specifically because it's a
deliberate design choice — if Document Intelligence had failed,
or returned low confidence, you would see a red chip here and *no
recommendation*. The agent is wired to refuse to fabricate a
verdict when it doesn't have ground truth. It's allowed to say 'I
couldn't read this'. For HR, especially in jurisdictions like the
EU where automated decision-making is regulated, that 'don't
hallucinate when you don't know' property is more important than
any individual feature on the page.

### Moment three — real voice screen, real WebRTC

*(in the recruiter view → Active magic links → copy the `screen`
token)*

*(open `/screen?token=…` in a new tab, allow mic when prompted)*

This is a live call to Azure GPT-Realtime over WebRTC. Real voice,
real model, real latency. *(have a 20–30 second conversation —
generic intro questions are fine. End the call.)*

The transcript posts back to the workflow, the orchestrator
resumes, the recommendation lands in the recruiter's queue.

> *(if the mic is being awkward: there's an env switch
> `VITE_VOICE_TRANSPORT=canned` that plays a recorded transcript
> through the same callback. Same code path, no live mic.)*

### Moment four — offer + onboarding avatar

*(open `/portal?token=…` for an offered candidate)*

There are three more HITL gates between screen and offer — invite
to interview, candidate picks slot, post-interview decision —
which I'll skip in the interest of time but they're all here if
you want to come back to them. Skipping to offer.

Candidate accepts. Phase 10 is Onboarding. *(wait for the avatar to
render)*. That's a real Azure AI Speech avatar. Personalised
welcome video, voice synthesis, blob-cached by the SHA of voice
plus script so the second render of the same content is free. From
a candidate-experience point of view, that's the moment your new
hire stops being a row in a spreadsheet.

### What this proves — and why it matters for the architecture

Two things to take away from POC2 before we close.

First — the engine that ran this hire is the same engine that ran
the expense claims. Same Durable orchestration. Same Agent
Framework graphs per phase. Same MCP tool layer. Same AGT
governance kernel. Same audit chain. The surfaces are
purpose-built for the actors — candidate sees a portal, recruiter
sees a queue, hiring manager sees a different queue. But the
substrate underneath is identical, and that's the point.

Second — POC2 demonstrates a few capabilities POC1 doesn't need.
Real WebRTC voice with model-driven conversation. Real avatar
synthesis. Real Document Intelligence on a different document
class. Real ACS email-out. And jurisdiction-conditional behaviour
— if I rerun this with a German candidate, the same code path
adds a Compliance phase for the German works-council notification,
because the workflow graph is data-driven off the candidate's
country. So 'multi-region, multi-jurisdiction' isn't a roadmap
item, it's the same workflow taking a different branch through the
graph based on data.

> *(reserve beats if asked: jurisdiction switching with
> `C-SE-DE-00`; Hiring Manager surface at
> `/hiring-manager/HIRE-NNNN`; episodic memory via the
> `recall_similar_hires` MCP tool that pulls past hires in the same
> role family + jurisdiction; A2A boundary at `/api/a2a/inbound`
> for agent-to-agent updates from a candidate's PA.)*"

---

## Close — the agentic loop, skills + tools, and Constellation — 3-4 min

> Surface: open `http://localhost:5175/?view=constellation` and
> project it full-screen. The eight-domain ring lights up live as
> workflows fire on the laptop.

"OK, last bit. I want to do two things in the close. First, name
the architectural choice that makes everything you've just seen
work, because nobody's pointed at it explicitly yet. And second,
show you what scale of this looks like.

### The agentic loop — and why we don't write prompts

So the choice that underpins this whole substrate is how we
construct an agent. There's basically two camps in the industry on
this right now, and they look superficially similar but they are
not at all the same thing in production.

Camp one is the *prompt-engineered* agent. You take a big language
model, you write a lengthy system prompt — 'you are a finance
agent, you do this and that, here are some rules, please be
careful' — and you plug a few tools in. It works in demos. It
falls over the moment your auditor asks 'show me where it says
the agent can't write to Workday'. The answer is — it doesn't say
that anywhere. The prompt asks nicely. The model usually
complies. There is no policy.

Camp two is the *skills + tools* agent, which is what we've
built on. Each agent has a tiny markdown file — we call it a SKILL
file — that declares three things. Its name. Its description, in
one or two sentences. And, critically, its allow-list of tools. It
literally cannot call a tool that isn't in its allow-list, because
the runtime won't let it. The CV-crystalliser agent has access to
`ocr_extract` and that's it. The budget-checker has Workday
position-read and an Adaptive Card composer and that's it. The
classifier can read policy and structured claim data; it has no
write tools at all, anywhere.

So when the auditor asks 'how do I know this agent isn't doing
something I don't expect' — the answer is the SKILL file plus the
tool registry. Both are in version control. Both are signed.
Neither involves trusting the model.

This matters for a few reasons. It means new agents are cheap to
add — you write a SKILL file, you declare an allow-list, you're
done. It means the blast radius of any one agent is small by
construction — even if the model goes off the rails, it can only
do the things it's been allowed to do. It means review is
tractable — your security team can read a SKILL file and a tool
manifest in a coffee break, instead of reasoning about what a
multi-thousand-token prompt might or might not do under
adversarial input.

And it composes with the AGT layer we just looked at. Tools
declared in SKILL files have to be declared in the tool registry.
The tool registry is what compiles into the policy bundle. The
policy bundle is what the kernel evaluates against. So 'agent
declares it can use a tool' and 'kernel allows the tool to be
called' are two separate gates that both have to pass. Defence in
depth, but the depth is structural, not bolted on.

The agentic loop itself — the model reasons, picks a tool, the
runtime validates, the kernel evaluates, the tool runs, the result
goes back into the model — happens in a tight cycle inside each
phase. And every step of that cycle emits an OTEL span you can
trace in Foundry. So 'what did the agent do, in what order, against
what policy' is not a forensics exercise. It's a tab in your
observability dashboard.

### Constellation — what scale looks like

*(point at the projected ring)*

So pulling back. POC1 — finance — and POC2 — hiring — are the two
domains we built by hand for this engagement. The other six
glowing on this ring — travel pre-approval, vendor KYC, employee
onboarding, IT access requests, contract renewal, performance
review — those were graduated end-to-end by a meta-skill we wrote
called `compose-domain`. Over a single weekend.

What that means is: we wrote a tool that takes a YAML brief
describing a new domain and emits the registry entries, the phase
graphs, the persona set, the seed data. It runs the existing
substrate against that brief and produces a working domain. Six
times in a row, no human in the loop on the substrate side. The
ring you're looking at right now is the actual list of domains
running on this laptop.

And every domain on that ring inherits everything you've seen
today. One Control Plane. One AGT governance kernel — same OWASP
coverage, same kill switch, same Evidence chip, same audit chain.
One Foundry project — same OTEL conventions, same evaluation
pipeline, same cost ledger, same tracing tab. One agent registry,
one tool registry, one policy bundle. Eight domains, and there is
no per-domain governance story, because there is no per-domain
substrate.

The closing line I want to leave you with is — the deliverable
isn't POC1, and it isn't POC2. The deliverable is the substrate
that lets you run both, and the next six, and the ninth one
you'll add when you decide what it should be. POC1 and POC2 are
existence proofs. AGT is what makes the OWASP-10 claim something
your auditor can re-derive themselves rather than something you
have to ask them to take on faith. And Constellation is what scale
across WPP's actual operating model looks like, on the same
substrate, with the same governance, on day one.

Happy to take questions."

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
