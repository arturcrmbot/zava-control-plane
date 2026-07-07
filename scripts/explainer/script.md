# Agentic Blueprint — explainer script

Voice: `en-US-Grant:MAI-Voice-2`. Tone: grounded, factual, first-person where it
fits, no hype. Sentence rhythm varied. No em dashes. No "let's", "dive into",
"actually" as filler, no "showcase / underscore / vibrant" vocabulary.

The script has been written to match the voice of the essay it narrates. Numbers
(35 skills, 23 MCPs, 10 workflows) reflect what the deployed page actually says,
not what `README.md` claims.

---

## Scene 1 — Cold open  (~17s)

This is the page at aka dot M S slash agentic blueprint. It's an essay arguing
that the way most organisations are buying AI is why none of it is compounding.
And it's backed by a working substrate I built to show what compounding looks
like.

## Scene 2 — Why nothing compounds  (~37s)

The argument is simple. Sponsor an initiative, the demo works, contracts get
signed, something ships. The next one starts over with new tech, new prompts,
new vendor. Nothing carries.

Two reasons. First, humans cannot realistically build, train and govern
initiatives one at a time fast enough. By the time the first lands, the
organisation has adopted three other tools. Second, most organisations are
running several agent frameworks in parallel. None of them strengthen each
other. Nothing accumulates because none of them share a foundation that would
let them.

## Scene 3a — Harness  (~9s)

The substrate is four things together. First, the harness. It runs agentic
segments inside otherwise deterministic workflows. The model picks the next
tool inside a segment. The orchestrator picks everything else.

## Scene 3b — Skills  (~7s)

Second, skills. A skill is a markdown file with a system prompt, an
allow-list of tools, and a model choice. Replacing one is a file edit.

## Scene 3c — MCPs  (~8s)

Third, MCPs. One adapter per outside system, shared by every agent. Workday,
Concur, the authority matrix, the policy ledger.

## Scene 3d — Foundation  (~11s)

Fourth, the foundation. Per-agent signing keys, tool allow-lists checked before
every call, structural validation on every output, and a tamper-evident audit
log. Policy lives in a YAML file compliance can edit directly.

## Scene 4 — Reference organisation  (~23s)

On top of this I built a reference organisation. Around 35 skills, 23 MCP
adapters, 10 workflows wired up end to end. Each tile is a domain. The skills
and MCPs aren't owned by any single workflow. They're cast once and shared
across all of them.

## Scene 5 — The loop in aggregate  (~48s)

This is the substrate actually running. The visualisation in the middle plots
one workflow at a time. Domain at the centre, the skills the agents picked up
around it, the MCP calls travelling out to the rim. Each blink is a real
event. None of it is animation.

The counters track the substrate as a whole. Workflows started, skills run,
MCP calls, validators blocked, workflows completed. They go up as agents work.

What you're watching is real telemetry. The workflows ran on my laptop
against the same orchestrator, skills and MCPs described above. Every event
was captured. We're replaying the recording so it reads continuously instead
of waiting for live traffic.

## Scene 6 — One iteration  (~36s)

This is the operator dashboard. Pick a workflow that's mid-flight. This AP
invoice from Globex for two hundred and ninety five thousand pounds. The
drawer shows what the agent did. Invoice lookup ran, three-way match ran,
then the workflow suspended for human approval because the amount sits
outside the regional controller's delegation per the authority matrix.

The reasoning, the matched authority rule, the state snapshot, the audit
trail. All of it on one page. That's one iteration of the loop.

## Scene 7 — Why this compounds  (~15s)

The reason this compounds isn't that the model got smarter. It's structural.
Each new domain reuses the same identity, audit, operator surface and
orchestrator. The first one I built took fifteen days. The recent ones took
hours.

---

Total target: ~3:31 (211s). Re-check after synth measures actual durations.
