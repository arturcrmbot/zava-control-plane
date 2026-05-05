# Blueprint — the pitch, captured

**Date:** 2026-05-02
**Sister doc:** [blueprint-script.md](blueprint-script.md) — the full one-pager prompt (copy + visual brief + designer notes). This file is the text and the underlying ideas only, for reference and reuse.

---

## The thesis, in one sentence

What you've been buying is a manuscript. What you need is a press.

---

## The one-pager copy

**Headline.**
*Why your AI hasn't compounded.*

**Subtitle.**
And the only thing we've found that does.

**Opening.**
If you've sponsored AI work in the last three years, you know the pattern. The demo goes fine. The contract gets signed. Some version of the thing ships. Then the next initiative arrives and effectively starts over: new prompts, new evaluation, new integrations, a fresh six-week timeline, often a different vendor. The deliverables stop accumulating about a week after each contract ends.

**Pullquote.**
*What you've been buying is a manuscript. What you need is a press.*

**Visual caption.**
Hand-illuminated, one volume at a time. Or set from a case of type that can be reset for the next page.

**Reframe.**
The pieces that make an agent — its skills, its connections to your real systems, its identity, its governance — are cast once and composed on demand. Standing up the next agent is composition, not construction. The compositor, here, is an agent itself.

**Proof.**
We have already built it. Dozens of agents — finance compliance, hiring, onboarding, procurement, more — composed from a shared case of type, increasingly by agents themselves. The first took fifteen days. The most recent took hours. We don't hand you a repository and a statement of work. We hand you the environment, running. A week with you, and your real ambition — one use case or fifty — is operating inside it.

**Closing.**
The question stops being *'which AI project do we fund next.'* It becomes *'what does it look like when this organisation composes its own.'* That's a longer and stranger conversation. It's the one that leads somewhere.

---

## The underlying argument, expanded

### The pattern we're naming

Three years of enterprise AI has produced a recognisable shape. A company funds a use case. A vendor delivers it. The thing works, more or less. The next use case is funded as a new project: new prompts, new integrations, new governance review, often a different vendor. None of the work from the first project carries over in any meaningful way. The cost of the second use case is roughly the cost of the first.

The industry treats this as an execution problem and prescribes more discipline, better playbooks, a centre of excellence. We think the unit being delivered is the problem. You can't solve compounding by executing harder on the wrong unit.

### What we're proposing instead

Stop buying use cases. Buy the environment they get composed in.

The environment is a working, governed agentic substrate, running in your cloud, made of four things in combination — none of which is interesting alone:

1. **Skills.** Autonomous, modular units of know-how. Centrally governed. A skill is a markdown file with a system prompt, a tool allow-list, and a model choice. Adding a skill is not a project.

2. **MCP servers.** A federated capability layer. Your real systems (Workday, Concur, ServiceNow, Greenhouse, Graph) and your third-party APIs, surfaced as MCP tools with negotiated auth, schemas, and contracts. The MCP servers are not agentic themselves — they are pure capability. The agents borrow them.

3. **The harness.** Agents are spun up on demand with the right skills and MCP tools, do their work, and are torn down when finished. There are no thousands of standing agents to manage. It is orchestration, not an org chart.

4. **Identity, security, governance.** Underneath everything: Agent 365, Entra Agent ID, audit, hooks on non-revocable sends, policy-driven (not code-driven) behaviour, validators as guardrails. The bit that legal and risk have to bless once. They never have to bless it again per project.

The four things together are the case of type. The skills are the letterforms. The MCPs are the words those letters can spell against your real systems. The harness is the compositor's bench. Identity and governance are the locked frame around the forme.

### The mechanism that compounds

The reason this compounds is not "the AI gets smarter at one task" — that's the cliché everyone claims and nobody has. The reason this compounds is structural:

- The act of building the next agent is itself agentic. Agents compose new agents from the existing skills and MCPs. Humans approve. Humans no longer assemble.
- Each new domain reuses the substrate. New domain = new skills + new MCP tools + a new orchestrator class. It does not = new identity model, new audit ledger, new HITL grammar, new control plane, new operator surface. Those exist.
- The operator's muscle memory transfers. The Control Plane, the exception queue, the bulk-approve, the reviewer queue — operators don't get retrained per agent.

That is why the cost curve collapses. Not because of telemetry-driven prompt tuning. Because the alphabet is already cast.

### What we actually do at engagement

We don't hand you a repository and a statement of work for a year. We hand you the environment, already running, in an enterprise-shaped cloud, with dozens of agentic loops working together under the governance you would expect.

Then we sit with you for a week. We map your real ambition — whatever the count is, one use case or fifty — onto the existing case of type. Where new letters need to be cast (a new skill, a new MCP server), the agents themselves do most of the casting, with us reviewing.

From day one, you are not running an experiment. You are operating.

---

## Why each piece of the copy is what it is

**Headline — "Why your AI hasn't compounded."**
A diagnosis, not a slogan. The reader recognises the problem in themselves immediately. No "stop X / start Y", no edgy provocation, no jargon.

**Subtitle — "And the only thing we've found that does."**
Promises an answer without telling you what it is. Earns the next thirty seconds.

**Opening paragraph.**
Recognition. The reader has lived this pattern. Every clause should ring true. The last line — *"the deliverables stop accumulating about a week after each contract ends"* — is the line that makes them sit up.

**Pullquote — manuscript / press.**
The whole thesis, compressed. Carries the analogy that the reframe paragraph and the visual will then unfold.

**Reframe paragraph.**
The mechanism, plainly. *Composition, not construction* is the one near-slogan in the piece. It is left in deliberately because the printing-press analogy earns it — composition is what a compositor literally does. The line *"the compositor, here, is an agent itself"* is the agents-build-agents point landed without saying it.

**Proof callout.**
The bit that separates this from every other vendor note. Concrete count (dozens), named domains, real time-curve (fifteen days → hours), and the operationally distinctive line: *we hand you the environment, running*. No hedges. No "we don't yet know what the third will take" — we have dozens.

**Closing.**
The question reframe. The one line in the piece that a CDO might quote internally. *"What does it look like when this organisation composes its own."* Kept close to the original because it was already strong.

---

## The pitch in five moves (conversational version)

For when this is being explained out loud, not handed over on a page:

1. The unit of delivery is wrong. AI is being sold as projects. Projects don't compound.
2. What ought to exist is an environment — skills + MCPs + harness + governance — running in your cloud.
3. Inside that environment, the agents that build the next agent are themselves agents. Humans approve. Humans no longer assemble.
4. Because of that, the cost of the next domain collapses. We've watched it go from fifteen days to hours.
5. We don't pitch you a build. We hand you the environment, running. A week with you, and your real ambition operates inside it.

---

## What we are explicitly not pitching

So nobody mistakes us for the thing we are arguing against:

- Not another POC.
- Not a platform-and-services proposal.
- Not a six-week sprint to deliver one use case.
- Not a managed service where you pay us to run agents for you.
- Not a tool you install and figure out yourselves from a GitHub repository.

We have already built the thing. We are giving it to you, running, and helping you compose your real work into it. That is the sale.

---

## Reference material

- [blueprint-script.md](blueprint-script.md) — the full one-pager prompt (this copy + visual brief + designer notes)
- [poc1-status.md](poc1-status.md) — the finance-compliance build (domain one)
- [poc2-status.md](poc2-status.md) — the hiring build (domain two)
- [SCOPE-DELTA.md](SCOPE-DELTA.md) — what runs in the lab vs. what an engagement deploys
- [ARCHITECTURE.md](ARCHITECTURE.md) — the three-tier substrate the pitch describes

---

## Persona library

> Updated 2026-05-05 — see [`plan/feature-authority-and-personae-1.md`](../plan/feature-authority-and-personae-1.md) for the work that landed this.

The substrate ships with **29 registered personae** across 8 corporate functions. 15 of them are wired into HITL gates on the 8 live domains; the remaining 14 are *available cast* — graduated via the [`compose-persona`](superpowers/skills/compose-persona/SKILL.md) meta-skill ahead of the domains that will use them. Adding the next dozen domains in any of these functions is a `compose-domain` brief, not a persona-authoring exercise.

Every persona's structural metadata lives in [`api/shared/personas.py`](../api/shared/personas.py). Behaviour (the `decision_policy` block) lives in `api/server/personae/<role>/SKILL.md`. 15 of the 29 read thresholds from the [delegated-authority MCP](../mocks/authority-mcp/) instead of inlining them — flipping a numeric limit is a JSON edit on `data/synthetic/authority/matrix.json`, not a code change.

### By function

| Function | Personae |
|---|---|
| **Finance** (9) | `controller`, `fpa_analyst`, `ap_clerk`, `treasurer`, `finance_bp`, `ssc_reviewer`, `claim_submitter`, `contract_finance_bp`, `vendor_kyc_finance_bp` |
| **HR** (6) | `hr_bp`, `recruiter`, `line_manager`, `perf_review_hr_bp`, `perf_review_line_manager`, `comp_ben_analyst` |
| **IT** (4) | `change_manager`, `it_access_it_admin`, `it_access_line_manager`, `onboarding_it_admin` |
| **Procurement** (3) | `category_manager`, `sourcing_lead`, `cpo` |
| **Legal** (2) + **Privacy** (1) | `contracts_counsel`, `gc`, `dpo` |
| **Commercial** (3) | `account_director`, `project_manager`, `contract_line_manager` |
| **Candidate** (1) | `candidate` |

### By archetype

- **Approvers (21)** — sign off the gate. Default position for most personae.
- **Reviewers (4)** — `comp_ben_analyst`, `contracts_counsel`, `fpa_analyst`, `ssc_reviewer`. Examine and may flag without final sign-off.
- **Subjects (3)** — `ap_clerk`, `candidate`, `claim_submitter`. The person the workflow is *about*.
- **Delegates (1)** — `project_manager`. Stands in for an approver and escalates upward.

### What this proves

The Phase-6 graduations took on the order of an hour per persona because the meta-skill writes the SKILL.md, the registry entry, and the graduation script from a YAML brief. The next dozen personae cost the same. The next hundred cost the same. The "compositor itself is an agent" claim isn't a future hope — it's the procedure these personae arrived through.
