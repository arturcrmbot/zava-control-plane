# Zava Compose-Org Skill Design

**Date:** 2026-07-20
**Status:** Approved

## Goal

An account team runs one guided skill:

```text
compose-org "fashion retailer"
```

The skill researches the target, asks the operator for business decisions,
builds a complete executable Zava vertical, proves every declared process
live and in replay, and hands over a working local workspace.

Deployment remains a separate explicit step:

```text
compose-org -> zava-workspace-deploy
```

## Public skills

### `compose-org`

The only build entry point. It runs four phases in one conversation:

1. **Research** — invokes `research-company` internally.
2. **Design** — agrees the simulated organisation, process story and proof
   contract with the operator.
3. **Build** — creates a standalone customer repository containing an
   isolated vertical pack.
4. **Prove** — runs every declared process against the live synthetic world,
   then replays the resulting evidence without Functions or the actor world.

The operator answers business questions and approves factual/design
checkpoints. The skill owns technical implementation decisions.

### `zava-workspace-deploy`

Deploys a workspace only after `compose-org` has produced passing evidence.
The operator must choose:

- **private live** — authenticated, writable, Durable Functions and actor
  world enabled;
- **public replay** — read-only, baked evidence tape, Functions and actor
  world disabled.

### `research-company`

Remains an installed specialist skill because `compose-org` invokes it and
maintainers may run it independently. It is no longer presented as a required
account-team step.

It gathers only source-backed facts:

- identity, footprint and scale;
- products, services and customer segments;
- leadership and operating model;
- disclosed systems;
- regulations;
- strategic themes and public operational events.

Unknowns remain explicit. It never invents synthetic actors or records.

## Factual versus synthetic

Research anchors the vertical. The generated world is deliberately synthetic.

The skill must keep these separate:

- researched facts carry sources and confidence;
- industry assumptions are labelled as assumptions and require approval;
- generated actors and records are labelled synthetic and reproducible from
  a fixed seed.

Synthetic does not mean static or cosmetic. The world must be causal:

```text
world event
  -> sensor
  -> objective
  -> Durable workflow
  -> HITL when declared
  -> typed command
  -> real world-state mutation
  -> measured outcome
```

## Build output

`compose-org` acquires the Zava substrate, retains an `upstream` remote, and
creates customer-specific behavior under:

```text
verticals/<slug>/
```

The pack owns:

- manifest and UI identity;
- functions, domains and process profiles;
- actor world, seed and reset;
- sensors, commands and golden scenarios;
- Durable registrations;
- agents, personas and authority;
- skills and MCP capability packs;
- entity projections and memory workflow types;
- recordings and proof metadata.

Core Zava files are not mass-rebranded and global business registries are not
replaced. Branding and terminology come from pack metadata.

## Process scalability

The generated vertical uses the Telco pattern:

- a small set of interconnected hero workflows may use bespoke orchestration;
- related processes share workflow engines, reasoning skills and MCP packs;
- every process still has its own trigger, profile, typed command, world case
  and success event.

Adding a use case follows the cheapest truthful path:

1. Reuse an existing process family when behavior matches.
2. Add a new profile, golden scenario and proof assertions.
3. Add a new engine or command only when the process is genuinely different.

Another customer in the same industry reuses the vertical model and changes
facts, scale, identity and scenarios. A new industry pays the actor-world and
process-family cost once.

## Guided checkpoints

`compose-org` pauses only for decisions a human should make:

1. Approve the research summary and uncertainties.
2. Choose or approve the flagship causal story.
3. Approve process breadth and hero processes.
4. Approve organisational authority and named leadership treatment.
5. Approve use of any customer-provided material.

The skill does not ask which files, classes or frameworks to use.

## No-fake contract

`compose-org` must stop rather than claim success when any of these are true:

- a process is a stub;
- a process exists only as a UI card;
- a workflow returns a hard-coded successful result;
- Agency behavior is merely relabelled as another industry;
- a synthetic assumption is presented as researched fact;
- replay is used without first passing the live proof;
- the UI and backend disagree about workflow identity or outcome;
- browser errors or dropped workflow evidence remain;
- reset cannot reproduce the starting world.

## Proof output

The generated repository must contain one permanent proof command and an
evidence directory containing:

- live summary;
- replay summary;
- world state and journal;
- Durable instances;
- workflow API details;
- entity graph;
- recordings;
- screenshots/video;
- browser errors;
- exact source commit and vertical fingerprint.

All declared workflows must pass live and replay.

## Minimal substrate changes

Only three substrate improvements are required:

1. Discover `verticals/*/manifest.py` instead of hard-coding pack names.
2. Finish removing stale global-registry instructions from the existing
   pack-scoped `compose-domain` skill.
3. Publish the Telco live/replay evidence shape as the mandatory proof
   contract that generated verticals must implement.

Do not create a new framework of public builder skills. `compose-org`
orchestrates the existing coding agent and Zava authoring skills.

## Repository updates

### `zava-control-plane`

- implement automatic pack discovery with isolation tests;
- align `add-domain` / `compose-domain` documentation and checklists with
  pack-scoped graduation;
- document the reusable vertical proof contract;
- update the Constellation MetaSkill section and hosting brief;
- keep Agency and Telco behavior unchanged.

### `zava-constellation`

- rewrite `compose-org` around Research -> Design -> Build -> Prove;
- make `research-company` an internal factual phase;
- update `zava-workspace-deploy` for explicit live/replay deployment and
  proof-manifest preflight;
- refresh the retail primer to require an executable actor world and process
  proof rather than workflow stubs;
- update README, `ZAVA.md`, plugin metadata and public site;
- add lightweight contract checks that reject the old clone/rebrand/stub
  instructions.

## Acceptance

1. Account-team documentation starts with `compose-org <target>`.
2. No active instruction tells users to customize Zava through literal global
   rebranding, schema replacement or stub domains.
3. A newly added manifest is selectable without editing
   `api/shared/vertical_loader.py`.
4. Pack-scoped domain graduation tests pass.
5. Agency and Telco isolation tests pass.
6. The Telco 37-process live/replay proof still passes.
7. Companion-repository contract checks pass.
8. Both repositories are committed and pushed.
9. The public Constellation site reflects the new two-step story.

## Later acceptance run

The real generality test is a Fashion Retail invocation from a clean checkout.
That run must build and prove the Fashion vertical without hand-editing.

It is deliberately not hidden inside this skill-refresh change. Until that
run passes, the skills may describe the supported procedure but must not claim
that arbitrary industries have already been proven.
