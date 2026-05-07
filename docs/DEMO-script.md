# Demo narration — 30-minute script (CTO + senior business audience)

Companion to [DEMO.md](DEMO.md). Same four acts, same surfaces — but
written as words you can actually say to a room that includes WPP's
CTO and senior business stakeholders. Lead with what it means for
their operating model; the technical depth is there as proof, not as
the headline.

**Total: ~30 minutes** if you breathe between sentences. Pause where
it says *(pause)*; click where it says *(click)*; the asides in
italics are for you, not the room.

| Act | Time | Audience takeaway |
|---|---|---|
| 1 · Frame | 4 min | What you're about to see, and why it's not another agent demo |
| 2 · POC1 — Control Plane | 13 min | A finance org running 30 expense workflows with one human in the loop, fully governed |
| 3 · POC2 — end-to-end hire | 9 min | Same engine, completely different surface — proves it's a platform |
| 4 · Constellation | 4 min | The deliverable is the substrate, not the two demos |

> **Before you start:** `make up`, wait until at least one workflow
> is on `/fleet` and at least one red claim has parked at Arbitrate
> (≈ 2–3 min after boot). Have these tabs warm:
> 1. `http://localhost:5173/workflows/<a recent EXP-NNNN>` — the canvas for Act 1
> 2. `http://localhost:5173/fleet` — Act 2 home
> 3. `http://localhost:5174/apply` — Act 3 entry
> 4. `http://localhost:5175/?view=constellation` — Act 4 closer

---

## Act 1 · Frame — 4 minutes

> **Surface:** one workflow detail page. Don't open anything else
> yet. This single page is the canvas for the framing.

"Before I click anything, two sentences on what you're about to see —
because every vendor in your evaluation will show you agents doing
work, and that's not what's interesting here.

The interesting question for an operation the size of WPP isn't
*can an agent classify an expense claim*. It's *who is accountable
when thirty thousand of them run every week, what happens when one
goes wrong, and what does the auditor see at the end of the
quarter*. That's what this build is about. We've called it a Control
Plane on purpose — the agents do the work, but a human, with the
right surface and the right evidence, governs the fleet.

*(point at the open workflow page)*

What you're looking at is one expense claim, mid-flight, on my
laptop. The phase ribbon at the top is the workflow. The panel on
the right is what the agent is actually reasoning about right now —
not a transcript I edited, the live trace. The tiles at the bottom
are cost and audit.

Three things to register about how this runs, and then I'll stop
talking and start clicking.

**One** — the workflow is a Durable orchestrator. It survives
process restarts, region failover, and 72-hour human waits at zero
compute cost. We didn't invent that; it's how Microsoft runs
long-running business processes.

**Two** — every box you see in the phase ribbon is a small graph of
typed steps. Some are deterministic code, some are agent calls with
named identities and a constrained skill, and some are validators
that block bad agent output before it ever lands in the ledger. That
mix is deliberate — we don't let the model decide things that don't
need a model.

**Three** — almost everything you'll see runs on this laptop.
Workday, Concur, Maconomy, Greenhouse — all stood up as local mocks
so you can see the system end to end without waiting on integration
tickets. The cloud pieces that *are* real are the ones the
engagement POC inherits unchanged: real Azure Document Intelligence
for receipts, real Azure Storage for the audit ledger with
version-level immutability, real Azure GPT-Realtime for the voice
call you'll see in act three, real telemetry into Foundry. Those are
the production-shaped seams.

*(pause)*

OK — let me show you the fleet."

---

## Act 2 · POC1 — Control Plane — 13 minutes

> **Surface:** `http://localhost:5173/fleet`. Role chip top-right
> should say **Agent Administrator**. You should already see ~10–20
> workflows; if not, give it a beat.

### A · Frame the operating model — 1 min

"This is the Finance Controller's view. London office. Notice what
they're *not* doing — they are not logged into Workday. They are not
logged into Concur. They never see an individual claim form.

In the WPP target operating model, the controller governs the agent
fleet that operates those systems. The agents do the keystrokes; the
controller does the policy. That's the entire premise of POC1.

*(point at the grid)*

Right now there are *(count)* workflows in flight. The greens are
auto-processing — agents pulling receipts, calling Document
Intelligence, checking the policy clause, posting back to Workday.
Most of them no human will ever see. The ones that need a human
surface here as exceptions. **[AC #1 — single view across 30+
workflows. AC #2 — exception-only surfacing.]**"

### B · Drill into a flagged claim — 3 min

"And here's one. *(click into a red EXP-NNNN — the "STALLED ·
Exception at Arbitrate" tile)*

This is what surfaces when an agent decides it can't safely decide on
its own.

*(point at the phase ribbon)*

Intake, Classify, Receipt, Route — all green. The agent did all of
that autonomously. Notice the **Receipt** phase — under the hood
that's a real Azure Document Intelligence call against the receipt
PNG, the extracted total cross-checked against the structured claim,
and a mismatch flag if they don't agree. **[AC #5 — receipt
cross-validation.]**

*(point at Arbitrate, red)*

It's parked here. Why? *(point at the reasoning panel)* The agent
has actually composed a draft recommendation — it's cited the exact
policy clause it would invoke, surfaced two prior arbitrations that
look similar, and laid out which way it would lean. So the human
isn't being asked *what should we do* from a cold start. They're
being asked *do you concur with the agent's recommendation*. That's
the productivity unlock — the agent isn't replacing the reviewer,
it's getting them to a decision in seconds instead of fifteen
minutes.

*(scroll to the bottom — the action ledger)*

And every step the agent took is in the action ledger here. Who ran,
what they did, what they cited. That's the substrate we'll come back
to when we get to the audit story."

### C · Take a decision — watch the round-trip — 1 min

"Let me reject this one. *(click Reject)*

*(wait one second)*

Watch the header — it just flipped to red, **STATUS · REJECTED**.
The phase ribbon — Arbitrate is now red. And the action ledger has
gained two new entries: my decision, signed as
`finance-controller@wpp`, and the workflow-rejected event right
under it.

*(go back to /fleet)*

And it's gone from the exception queue. End to end, signed and
chained, and I'll show you what 'chained' actually means in a
moment."

### D · Bulk and the long tail — 1 min

"Now in the real world the controller doesn't get one exception at a
time — they get clusters. Six claims from the same vendor, all
flagged for the same reason, all in the same week.

*(open the bulk modal — don't action it)*

This lets them take one decision across the cluster. One signature,
n entries in the ledger, all linked back to the cluster id. Same
governance properties; one click. **[AC #3 — bulk action across 10+
items.]**"

### E · Cost — and the honesty about how it's measured — 1.5 min

"This tile — *(point at the economics card)* — is cost. And I want
to spend thirty seconds on it because it's the question every CFO
asks first.

This number is real `gen_ai.usage` token telemetry off the agent
runs, multiplied by Microsoft's published per-million-token rates,
sourced this week. It's not a synthetic constant. **[AC #13 —
cost-per-task report.]**

Here's the honest bit, because you'll ask. The model SDK doesn't
always emit token counts on every call. When it doesn't, we
estimate from prompt length plus tool-call payload, with about 1.1k
tokens added per inline image for vision. *And* — every span in the
trace is tagged with provenance: it either says `sdk` or
`estimated_from_chars`. So your auditor can always tell which is
which. The number on this tile is the same number Foundry shows."

### F · Audit and the OWASP claim — 2 min

"Now this is the part that matters most for the CTO and the CISO in
the room. *(point at `auditBlobUrl`)*

Every step you saw in that ledger is being dual-written into a real
Azure Storage append blob with version-level immutability turned
on. That means the retention policy is enforced by Azure itself —
not by my code, not by my goodwill. If I tried to mutate that blob,
Azure would refuse. **[AC #12 — immutable audit trail.]**

But immutable storage on its own isn't enough — you also need to
prove the *content* hasn't been tampered with between the workflow
and the blob. So *(point at the Evidence chip in the sidebar)*
that's what this is. Three sub-chips: chain, signatures, decisions.
All three green means the action ledger is a verifiable Ed25519-
signed hash chain rooted in the governance policy bundle that was
live at the moment each entry was written. Click it and you get the
JWS receipts, the chain head, and the policy bundle hash.

*(click through if time allows)*

The bid claims OWASP Agentic AI Top 10 — ten out of ten covered.
That claim is auditor-reproducible from this endpoint plus an `agt
verify` CLI run. It is not a slide. The artifacts are in the repo
and anyone can re-derive it."

### G · The kill switch — 1 min

"And right next to that — *(point at Kill Switch)* — the operational
control your CISO actually wants. Sub-second, no redeploy.

If something is misbehaving — say there's a regression in how an
agent is calling `concur.submit_decision` — I post a kill on that
tool with a 30-minute TTL. The next time *any* agent in the fleet
tries that tool, the governance kernel returns a structured denial
with a decision id the operator can trace through Foundry. The
Functions worker doesn't restart. There's no deploy. The kill table
is consulted on every tool call.

That's the fire-extinguisher you need before you'll ever sign off on
turning autonomy up."

### H · Fleet Manager + autonomous learning — 1.5 min

"*(point at right rail)* Right rail — the Fleet Manager. Single
always-on session that subscribes to a triage-filtered event stream
from every workflow. Natural language probe of the fleet.

*(type or read)* 'show me stalled arbitrations' or 'cost this week'
or 'who are the repeat offenders' — watch the tool calls and the
reasoning stream into the panel. **[AC #6 — progressive enforcement
on repeat offenders.]**

And once the controller has been making consistent decisions for a
while, the Fleet Manager surfaces a behaviour-change proposal —
'here's a class of claims you've rejected sixty times in a row,
here's a tightened policy clause that would have caught fifty-eight
of them at Classify, do you want to promote this'. That's autonomous
learning with a human signing off the policy change, not autonomous
learning that just changes its mind. **[AC #7 — agent recommends
based on prior human decisions.]**"

### I · The other operator — 30 sec

"*(open `/reviewer-queue` in another tab, briefly)*

Quick beat — the SSC Reviewer in Manila has a completely different
surface. Same underlying queue, but pre-composed arbitration
recommendation, cited precedent, system-agnostic. They don't see the
controller's fleet. Different role, different surface, same
governance chain. **[AC #8 — SSC Reviewer interface.]**"

### J · System-agnostic across EMS — 30 sec

"And the claims you've been seeing came from two different EMS
systems — Workday and Concur — appearing identically in this
controller view. **[AC #9 — system-agnostic Control Plane.]** A new
EMS — Maconomy is the third we wired in — is a two-file shape: one
adapter, one registry entry. The agent skills don't change. **[AC
#10 — extensibility, walked in act 4.]**

*(if time and the room is technical: mention `POST
/api/simulator/region-failure` lets us yank the Functions host and
watch in-flight workflows resume from checkpoint. **AC #11.**)*"

### Reserve beats — only if asked

- The accuracy pipeline (AC #4) — `/api/accuracy/run` and the
  Evaluations page; the prompt + pipeline are live, the corpus-wide
  ≥95% gate is reserved for WPP's 3,430-claim real dataset because
  running it on synthetic claims wouldn't be a meaningful number.
- Foundry Tracing tab live on the workflow currently on screen.
- `make agt-verify` in a terminal — runs `agt verify` across every
  audit blob in the repo and prints the chain summary.

---

## Act 3 · POC2 — end-to-end hire — 9 minutes

> **Surface:** the candidate portal at `:5174`. Close the Control
> Plane tab. POC2 is *not* a Control Plane demo — same engine
> underneath, but the audience here is the hire, the recruiter, and
> the hiring manager.

### Frame the pivot — 30 sec

"Pivot. POC1 is one domain — finance. POC2 is a completely different
domain — hiring — running on the *same* substrate underneath. I'm
showing it to you because the headline of this whole bid is that
this is a platform, not two purpose-built demos. Same Durable engine,
same governance kernel, same audit story you just saw — but the
surfaces and the actors are completely different.

Three actors, four moments. Apply, AI triage, voice screen, offer."

### A · Candidate applies — 1 min

"*(open `:5174/apply`)*

Public form. No login, no SSO. This is what a candidate sees on the
careers site.

*(pick Senior Data Engineer · USA, drop in
`data/synthetic/hiring/cv-pdfs/C-SE-USA-00.pdf`, submit, copy the
candidate id)*

What just happened — a hiring orchestrator spawned, a magic-link
status URL went out by real Azure Communication Services email, and
the workflow is already running through Triage."

### B · AI triage — recruiter view — 2 min

"*(open `:5174/recruiter`, click into the candidate)*

This panel — *What we learned* — is the live trace from the agent
that's reading the CV. The `ocr_extract` row you see is a real
Document Intelligence call — same one you saw on the receipt in act
two. Below it, structured profile, token usage, latency.

If extraction had failed you would see a red chip and *no
recommendation*. That's deliberate. The system refuses to fabricate
a verdict. For HR, in the EU especially, that 'don't hallucinate
when you don't know' property matters more than any one feature."

### C · Real voice screen — 2 min

"Next gate is screening. *(in recruiter view → Active magic links →
copy the screen token)*

*(open `/screen?token=…`, allow mic)*

Real Azure GPT-Realtime call over WebRTC. *(have a 20–30 second
conversation — generic intro questions are fine)*

*(end call)*

The transcript posts back, the workflow resumes, and the recruiter
sees the recommendation in their queue.

> *(if mic is unhappy: 'I can also play a canned transcript through
> the same callback by setting `VITE_VOICE_TRANSPORT=canned` — same
> code path, no live mic.')*"

### D · Offer + onboarding avatar — 2 min

"Three interview gates exist between here and offer — invite, slot
booking, post-interview decision — I'll skip them in the interest of
time and pick up at offer.

*(open `/portal?token=…` for an offered candidate)*

Candidate accepts. Phase 10 is Onboarding — and *(wait for the
avatar)* — that's a real Azure AI Speech avatar, personalised
welcome, voice synthesis, blob-cached so we don't pay for the same
render twice. From a candidate-experience point of view, that's the
moment your new hire stops being a row in a spreadsheet."

### E · The point — 1.5 min

"Two things to take away from this act, and we move on.

One — the engine that just ran this hire is the same engine that ran
the expense claims. Same Durable orchestrator pattern, same Pregel
graphs per phase, same governance kernel evaluating every tool call,
same audit blob with version-level immutability, same Foundry
telemetry. The only thing that's different between POC1 and POC2 is
the *content* of the workflows — the seven phases vs the ten phases
— and the surfaces.

Two — and this is the harder one — we did not retrofit POC1's
substrate to make POC2 work. POC2 is a separate domain that dropped
in clean. Which is the bridge to the last act."

> **If asked, in this act, you can drop in any of:**
> - **Jurisdiction switching** — re-run with `C-SE-DE-00` and the
>   same code path automatically grows a German works-council
>   compliance step.
> - **Hiring Manager surface** at `/hiring-manager/HIRE-NNNN` —
>   different actor, different screen, same workflow.
> - **Episodic memory** — `recall_similar_hires` surfaces past hires
>   in the same role family + jurisdiction so the recommender isn't
>   deciding in a vacuum.

---

## Act 4 · Constellation — 4 minutes

> **Surface:** `http://localhost:5175/?view=constellation`. Project
> this full-screen for the closing.

"OK — pull back. POC1 and POC2 are two domains. The substrate runs
eight.

*(open the constellation view)*

This is the eight-domain ring. It's lit up live as workflows fire on
the laptop — same event bus you've been watching, just a different
surface.

Four points, briskly, and then I stop talking.

**One — eight domains, all in main.** POC1 — finance — and POC2 —
hiring — were hand-built. The other six — travel pre-approval,
vendor KYC, employee onboarding, IT access, contract renewal,
performance review — were graduated end-to-end by a meta-skill we
built called `compose-domain`, over a single weekend. The ring you're
looking at is the actual list. **[AC #10 — extensibility, made
literal: this is what 'add a new domain' looks like.]**

**Two — one registry, no per-domain branches.** Every fact about a
domain — its phases, its skills, its EMS adapters, its persona set
— lives in a single Python registry. The substrate layers — Fleet
Manager, simulator, exception queue, blueprint inventory, phase
ribbon — read from it at runtime. Adding the ninth domain is a
registry entry plus a YAML brief. It's not a refactor.

**Three — one governance kernel for all eight.** The OWASP-10
coverage you saw on POC1 covers POC2 and the other six identically.
Every MCP tool call in any of the eight domains routes through the
same chokepoint, the same kill switch, the same hash-chained
ledger, the same `agt verify` story. It is not eight different
governance stories.

**Four — one Foundry project across all eight.** Same telemetry
schema, same evaluation pipeline, same cost ledger. When you filter
the Foundry Tracing tab by `cloud_RoleName == "control-plane-functions"`
you get the live cross-domain trace stream — Hiring spans next to
Expense spans next to Vendor-KYC spans, all with the same OTEL
semantic conventions Microsoft Agent Framework, Semantic Kernel,
the OpenAI Agents SDK and GitHub Copilot all share.

*(close on the lit ring)*

So — closing line. **The substrate is the deliverable.** POC1 and
POC2 are two existence proofs of it. The governance kernel is what
makes the OWASP-10 claim auditor-reproducible. And what you're
looking at here — Constellation — is what scale across WPP's
operating model actually looks like.

Happy to take questions."

---

## Q&A — anticipated themes (one-liners)

- **"Where do the cost numbers come from?"** — Real `gen_ai.usage`
  spans where the SDK reports them; chars-over-four estimate when it
  doesn't, with provenance tagged on every span. Same number Foundry
  shows.
- **"How do we know the audit ledger is immutable?"** — Version-level
  immutability is enforced by Azure Storage itself, not my code.
  Plus the Evidence chip and `agt verify` for the chain integrity.
- **"How do we add the ninth domain?"** — Registry entry plus a YAML
  brief through `compose-domain`. We graduated six in a weekend that
  way.
- **"Where does Foundry sit?"** — Tracing, evaluation, observability
  — *next to* the agent runtime, not in front of it. Foundry is the
  dashboard, not the gate.
- **"OWASP Agentic Top 10 coverage?"** — Ten out of ten. Reproducible
  from `agt verify` plus the audit blobs. Walk-through is in the
  AGT panel.
- **"Lab vs engagement-POC scope?"** — See [SCOPE-DELTA.md](SCOPE-DELTA.md).
  Short version: agent identities swap from GHCP SDK to Foundry
  Hosted Agents on the same shape; the substrate, the kernel, the
  surfaces stay identical.
- **"Why not prompt-only? Why all this skill + allow-list machinery?"**
  — Allow-lists are policy. Prompts are not policy. The prompt can
  ask for whatever it wants — the kernel decides whether it happens.
- **"What about the ≥95% accuracy criterion (AC #4)?"** — Pipeline
  and prompt are live, evaluator UI in the app. The corpus-wide gate
  is reserved for WPP's 3,430-line real dataset; running it on our
  synthetic 300 wouldn't be a meaningful number.

`make down` between recordings. Always.
