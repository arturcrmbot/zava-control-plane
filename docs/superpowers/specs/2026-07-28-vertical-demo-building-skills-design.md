# Contract-First Vertical Demo Building Skills

**Date:** 2026-07-28
**Status:** Approved
**Scope:** `zava-constellation` public builder skills and the
`zava-control-plane` pack authoring, proof, and deployment contracts

## 1. Decision

Keep the existing public skill names, but make them one contract-first,
resumable build system:

```text
compose-org
  -> research-company
  -> design
  -> build one golden vertical slice
  -> add-domain / compose-domain as needed
  -> scale the process portfolio
  -> prove continuously
  -> prepare an inspectable demo
  -> zava-workspace-deploy
```

`compose-org` is the single public controller for a new vertical. The lower-level
skills remain available for focused work, but they consume the same current
contracts and may not invent a separate definition of "built", "proven", or
"demo ready".

The system remains code-first. A vertical is real Python and TypeScript,
Durable workflows, actor-world models, skills, MCP tools, typed commands,
projections, and optional UI extensions. Structured files record facts,
ownership, resumability, and proof. They do not form a universal vertical DSL.

## 2. Why this change is needed

The Telco, Fashion, and Travel iterations exposed a repeated pattern: the high
level intent is sound, but the operator has had to restate implementation and
demo expectations that should already be part of the builder contract.

### 2.1 Contract drift

The same rules are repeated across `compose-org`, `add-domain`,
`compose-domain`, `compose-domain-live`, `CHECKLIST.md`, and
`VERTICAL-PROOF.md`. The copies have drifted.

Examples in the current contracts include:

- `compose-domain` identifies itself as v3 while describing a v4 pipeline.
- Its fast-path policy conflicts with an anti-pattern that still requires
  reading old canonical examples.
- `author-durable-domain` still describes global wiring that the active
  pack-scoped contract forbids.
- `compose-domain-live` refers to phases and manual hand-stitches that are not
  represented consistently by `add-domain`.
- The companion `vertical-pack-contract.md` still says packs add to global
  registries, while the substrate treats those modules as read-only active-pack
  adapters.
- The companion upstream pin still validates a May 2026 substrate shape and
  obsolete global paths.

Adding more prose to each copy would make this worse. One current contract must
be authoritative, with contract tests rejecting stale instructions elsewhere.

### 2.2 Proof arrives too late

Static pack completeness is not demo completeness. Fashion initially had eight
declared agentic workflows, registered skills, and tools, but some "agent"
phases returned deterministic Python and did not call `run_agent_session`.
Telco and Fashion also showed that APIs can be healthy while the visible page is
empty, generic, overloaded, or racing the event stream.

The builder must prove one complete visible vertical slice before multiplying
workflows. Proof then remains active throughout the build instead of becoming a
large repair phase at the end.

### 2.3 Machine correctness is not seller readiness

Travel correctly separated machine proof from human seller review. Fashion
showed the inverse failure mode: all workflows could complete while the default
UI hid them, approvals disappeared too quickly, the world used irrelevant
labels, or high-volume actors overwhelmed the map.

The skills need two explicit claims:

- **Build ready:** deterministic machine gates pass.
- **Demo ready:** build-ready evidence plus a human seller review of the
  actual reset, pacing, screens, and story.

Machine proof must never silently promote itself to seller approval.

### 2.4 Proof must be repeatable and hermetic

Travel exposed several requirements that belong in the permanent builder:

- two genuine consecutive qualifying runs from the same source SHA and runtime
  fingerprint;
- generated-file parity and an explicit ownership manifest;
- proof teardown on success and failure;
- ignored runtime state that cannot leak into commits or archived worktrees;
- exact evidence for delayed HITL, real browser detail, Knowledge, Memory, and
  cross-surface identity;
- preservation of a seller-review `PENDING` state instead of an unsupported
  readiness claim.

Telco additionally exposed rate-limit and load sensitivity, Durable resume
latency, browser restart recovery, and the need to show actual execution
activity rather than inferred phase metadata.

## 3. Design principles

1. **One sentence should be enough to start.** A request such as "build an
   airline demo in the BA/IAG space" supplies direction. The skills own the
   recurring engineering and demo defaults.
2. **Ask only material business questions.** Research gaps, the flagship story,
   consequential authority, and customer-supplied material may require approval.
   File layout, test strategy, proof mechanics, observability, and demo cleanup
   do not.
3. **Code-first, contract-bounded.** Contracts define invariants and evidence,
   not every industry behavior.
4. **Reuse, extend, then build bespoke.** Reuse an engine only when behavior
   matches. Extend a shared primitive when the capability is industry-neutral.
   Write pack-owned bespoke code for novel worlds and processes.
5. **Golden slice before breadth.** One causal story must work through the real
   browser and evidence surfaces before supporting workflows are added.
6. **Truthful execution modes.** Agent, deterministic, and HITL phases mean
   different things and are proved differently.
7. **Proof observed behavior.** Conditional branches and live model tool choices
   are validated from what happened, not from a predicted ideal trace.
8. **Resumable failure.** A failed gate records the exact criterion, evidence,
   and next command. Recovery resumes from that stage without restarting the
   business interview.
9. **No cosmetic verticals.** A vertical must introduce the entities, causal
   dynamics, commands, authority, and presentation its industry needs.
10. **No readiness inflation.** Build-ready, demo-ready, and deployed are
    separate states.

## 4. Skill responsibilities

### 4.1 `compose-org`: the vertical controller

`compose-org` owns the end-to-end state machine:

1. Inspect the current substrate and verify the companion contracts are
   compatible with it.
2. Run or validate source-backed research.
3. Produce a rich design spec and obtain approval for material business
   decisions.
4. Classify each required capability as reuse, shared extension, or bespoke
   pack code.
5. Build and prove one golden vertical slice.
6. Add the remaining process portfolio in coherent families.
7. Run the complete repeatable live/replay proof.
8. Prepare a stable, inspectable demo state and evidence-backed talk track.
9. Stop at a build-ready or demo-ready handoff. Deployment remains explicit.

The controller records stage state under:

```text
tools/scratch/compose-org/<run-id>/STATE.json
```

The state contains the target, source SHA, approved spec path, completed stages,
current gate, evidence paths, and exact resume command. It contains no secrets
and remains ignored local state.

`compose-org` must not dispatch its critical build state to an untracked nested
session. Parallel workers may implement isolated tasks, but the controller owns
the artifact ledger and verifies every returned change before advancing.

### 4.2 `research-company`: factual grounding

Keep the thin factual boundary:

- source-backed facts with confidence and references;
- explicit assumptions and uncertainties;
- no synthetic records presented as research.

Change the primer rule from "stop if no primer exists" to an orchestrated
decision. `compose-org` may create and review a new industry model as part of
Design when the target is novel. A missing primer must not force the operator to
understand or manually run a separate skill.

Research freshness and factual review are independent of deterministic world
seeds. Public facts anchor the demo; synthetic operating data remains generated.

### 4.3 `add-domain`: focused pack-aware entry point

Reduce `add-domain` to a thin controller over the current domain authoring and
proof contracts:

- discover the selected pack and its actual conventions;
- classify the new process as a profile reuse, shared-engine extension, or
  bespoke domain;
- create or update the design and generation ownership records;
- invoke `compose-domain` only where generation is appropriate;
- graduate without manual hand-stitches;
- prove the new process in isolation and in its declared cascades;
- update the whole-pack proof inventory.

It cannot claim completion because the domain appears in
`active_runtime().pack.domains`. Registration is an early static gate, not the
finish line.

### 4.4 `compose-domain`: current deterministic authoring boundary

`compose-domain` remains useful for repeatable workflow scaffolding, but its
scope is narrower than a full vertical:

- accept a reviewed domain brief;
- generate only generator-owned files into a sandbox;
- generate pack-scoped graduation edits;
- preserve workflow and orchestration identity;
- instrument agent phases through `run_agent_session`;
- persist HITL recovery context;
- produce templates that satisfy the current observability contract;
- emit a machine-readable report and ownership entries.

The skill and its sub-skills must be revised as one version. Remove stale v3/v4
language, global patch steps, contradictory read rules, and graph-only
assumptions. `author-durable-domain` must no longer describe a second,
incompatible graduation procedure.

Generation does not own bespoke vertical behavior. If a novel workflow cannot
be expressed truthfully by the current generator, `compose-org` writes bespoke
pack code and records that ownership instead of forcing the workflow into an
existing template.

#### Mandatory boundary for bespoke runtime code

Generated and bespoke implementations use the same industry-neutral substrate
interfaces. Bespoke does not mean uninstrumented.

- Every phase declared `agent` calls the canonical `run_agent_session` wrapper
  directly and supplies workflow, orchestration, phase, and skill provenance.
- Every Durable path uses the canonical checkpoint and identity contract.
- Every HITL path uses the governance kernel, persists reconstructable
  `hitl_context`, and resumes through the declared external event.
- Every state change crosses a typed, idempotent command boundary.
- Every projection preserves the canonical workflow identity used by the API
  and UI evidence surfaces.

The substrate owns these interfaces. `compose-org` decides whether generated or
bespoke code is appropriate, but it may not create a pack-local substitute for
canonical evidence or governance. Where current bespoke packs repeat adapter
boilerplate, implementation may extract a narrow shared helper after proving
the same need in generated and bespoke paths; this does not create a universal
vertical framework.

The vertical-pack contract documents these mandatory interfaces, and generator
tests include one bespoke fixture so proof guarantees do not depend on code
having originated from `compose-domain`.

### 4.5 `compose-domain-live`: visible controller adapter

This skill remains a communication adapter for the Visual Domain Composer. It
must report the durable `STATE.json` stages rather than optimistic narrative:

- current stage;
- completed artifacts;
- blocking gate and evidence;
- requested business decision, if any;
- resumable next action.

It may report completion only after the expected sandbox, graduation,
whole-pack registration, and relevant proof records exist. Missing artifacts are
failures, not warning text followed by success.

### 4.6 `zava-workspace-deploy`: proven artifact consumer

Deployment consumes the same versioned proof manifest and fails closed on:

- unsupported proof schema;
- source SHA mismatch;
- vertical or runtime fingerprint mismatch;
- missing qualifying repeatability runs;
- a deployment mode not covered by proof;
- browser, event-loss, cleanup, or source-mode failures.

Post-deploy smoke checks must use the selected pack's declared capabilities.
They must not rely on fabricated generic routes such as a universal test entity
write endpoint.

## 5. Durable artifacts

These artifacts preserve intent and evidence without reducing the substrate to
configuration files.

### 5.1 `verticals/<slug>/org-brief.yaml`

Contains researched facts, source references, approved assumptions,
uncertainties, and the boundary between public fact and synthetic demo content.
It does not describe executable workflow behavior.

### 5.2 Approved Markdown design spec

The design spec remains the expressive architecture document. It defines:

- the organisational and causal model;
- actors, entities, relationships, distributions, and time;
- flagship and supporting stories;
- workflow families and novel orchestration;
- authority and governance;
- AI, deterministic, and HITL boundaries;
- typed commands and success measures;
- pack-specific UI needs;
- proof and seller-review expectations.

Markdown is intentional here: novel industries need explanation and trade-offs,
not only fields in a fixed schema.

### 5.3 `verticals/<slug>/generation-manifest.json`

Records:

- generator and schema versions;
- approved input paths and hashes;
- generator-owned paths and checksums;
- bespoke paths the generator must never overwrite;
- shared-substrate extensions and their owning tests;
- regeneration and parity commands.

Deletion and regeneration audits operate only on generator-owned paths. A
manifest mismatch fails loudly instead of silently overwriting bespoke work.

### 5.4 `tools/scratch/compose-org/<run-id>/STATE.json`

Provides local resumability. It is not a product configuration file and is not
deployed.

### 5.5 `proof/manifest.json`

The machine evidence manifest gains:

- `schema_version`;
- `source_commit`;
- selected vertical and runtime fingerprint;
- qualifying run ledger with at least two consecutive runs from the same source
  and fingerprint;
- live and replay results and source modes;
- per-workflow evidence references;
- browser errors and dropped-event counts;
- observed AI/session/tool evidence summaries;
- HITL authority, resume, and recovery results;
- cleanup and dirty-tree results;
- `build_ready` as a boolean and `seller_review` as
  `PENDING | PASS | FAIL`.

Proof payload snapshots remain ignored local artifacts because they may contain
workflow data. The manifest points to them and deployment validates them in the
same trusted workspace.

## 6. Build lifecycle

### Stage 0: Preflight

- Preserve user-owned changes and use an isolated clean worktree for a new
  vertical.
- Resolve the current substrate shape dynamically.
- Reject stale companion contracts before authoring code.
- Record source SHA, tool versions, selected model availability, ports, and
  runtime roots.

### Stage 1: Research

- Gather public facts and uncertainties.
- Select or create an industry model.
- Mark every non-sourced operating assumption.
- Obtain one factual/business approval checkpoint.

### Stage 2: Design

Apply opinionated defaults and ask only questions that materially change the
business story. The default design includes:

- a causal actor world, not a dashboard fixture;
- one flagship story and a coherent supporting portfolio;
- bounded autonomy and named authority where the business warrants it;
- typed commands that mutate state;
- measurable outcomes;
- an honest execution-mode declaration;
- a seller journey through existing product surfaces;
- reset, replay, and teardown behavior.

The operator is not asked to choose files, frameworks, test commands,
observability, or deployment internals.

### Stage 3: Golden vertical slice

Build the smallest end-to-end story:

```text
world event
  -> sensor
  -> objective
  -> Durable workflow
  -> agent/deterministic work
  -> HITL when declared
  -> typed command
  -> world mutation
  -> evaluation
  -> visible cross-surface evidence
```

Open the actual browser before adding breadth. The slice is incomplete if the
API passes but the default UI hides, races, clips, overloads, or mislabels the
story.

### Stage 4: Portfolio scale

Add process families one at a time:

1. Reuse a profile when phase and command behavior match.
2. Extend a shared engine when behavior is similar but not identical.
3. Add a new engine or bespoke orchestration when the process is genuinely
   different.

Each process keeps a distinct trigger, case, typed command, projection, and
evidence. Cascades are observed from their real parent trigger; proof does not
start duplicates merely to obtain a workflow ID.

Each family addition gets one focused qualifying run. The expensive
two-consecutive-run requirement applies to the final whole-vertical proof, not
to every intermediate family addition. Any subsequent fix that changes source
or runtime fingerprint invalidates the final pair and requires a new pair.

### Stage 5: Whole-vertical proof

Run all static, runtime, browser, replay, repeatability, and cleanup gates in
section 8. Failures return to the owning stage and preserve evidence.

### Stage 6: Demo preparation

Generate a stable command:

```bash
make demo VERTICAL=<slug>
```

It:

- resets to the named demo seed and scale;
- starts a bounded demo-safe execution mode;
- pauses meaningful approval gates long enough to inspect;
- prints the relevant URLs and current state;
- emits an evidence-backed talk track from actual capabilities;
- leaves the stack running for review;
- provides a separate teardown command.

The talk track may describe only capabilities proved by the current source and
runtime fingerprint.

### Stage 7: Deployment

Deployment remains a separate explicit action after build proof. Public replay
and private live are independently validated modes.

## 7. Execution-mode policy

The builder declares an execution mode for each phase and a runtime mode for the
demo.

### Phase truth modes

| Mode | Required implementation | Required evidence |
|---|---|---|
| `agent` | Real `run_agent_session` invocation using declared skills/tools | Persisted canonical reasoning, observed tool calls, typed validated output |
| `deterministic` | Deterministic code over typed input | Input/output provenance and repeatable invariant result |
| `hitl` | Governed external event and persona decision | Authority check, persisted recovery context, decision, Durable resume |
| `sub_orchestrator` | Real child orchestration | Parent/child identity and terminal lineage |

An `agent` declaration backed by canned Python is a blocking honesty failure.
Conversely, deterministic logic is not inferior when rules, safety, cost, or
repeatability make it the right design.

### Demo runtime modes

- **live-ai:** all declared agent phases use the configured live model within a
  concurrency and token budget.
- **hybrid (default):** selected flagship judgment uses live AI; deterministic
  supporting paths keep the demo responsive and rate-limit-safe.
- **deterministic-fallback:** no live model dependency; visibly labelled and
  separately proved.
- **replay:** a captured qualifying execution with write paths disabled.

Fallback is explicit. A live-AI failure must not be silently converted into a
success-shaped deterministic result.

Proof checks invariant outcomes and observed evidence. It does not require
byte-identical AI prose or a fixed optional tool-call sequence.

## 8. Blocking quality gates

### 8.1 Static and ownership

- Pack discovery, inventory, and cross-pack isolation pass.
- No forbidden global business registry edits.
- All declarations resolve to real implementations.
- No stubs, placeholders, or success-shaped empty handlers.
- Generation manifest is complete.
- Delete/regenerate yields parity for generator-owned assets.
- Bespoke assets are untouched by regeneration.

### 8.2 Runtime causal proof

- Every declared non-stub workflow has a qualifying instance.
- The flagship story proves the complete causal chain.
- Supporting workflows prove their declared applicable chain.
- Typed commands are idempotent and mutate the correct world entities.
- Evaluations compare a measured result with the relevant baseline.
- Cascades create no duplicate executions.

### 8.3 Execution visibility and honesty

- Declared agent work produces canonical `run_agent_session` evidence.
- Only observed phases and tool calls are validated.
- Tool request, response, status, duration, and persistent identity agree across
  reasoning and timeline surfaces.
- Deterministic and AI work are labelled accurately in the UI and evidence.
- Errors and retries are visible rather than rewritten as success.

### 8.4 Governance and recovery

- Every emitted HITL action/category/value matches the real authority kernel.
- Every suspended record persists persona, event, phase, and decision context.
- Auto-close proof reaches `persona.decided`, `durable.resumed`, and terminal
  state within the declared budget.
- Missed-event and process-restart sweeps reconstruct the same gate.
- Self-approval and namespace mismatches fail closed.

### 8.5 Cross-surface identity

The same workflow identity and outcome agree across:

- World;
- Workflow API;
- workflow drawer and timeline;
- Memory;
- Knowledge and graph projection;
- AG-UI;
- Constellation (the UI view);
- replay.

Completed workflow cards remain visible, retain IDs, and remain clickable.

### 8.6 Demo experience

- The default route shows the vertical's real concepts and useful state.
- Industry-neutral shared UI uses pack metadata rather than Telco/Agency labels.
- Vertical-specific UI is allowed when the shared renderer cannot tell the
  story truthfully.
- High-volume actors use bounded projections and structurally cannot overlap or
  flood the screen.
- Named scenarios show a visible event within one second of the click.
- Approval gates remain inspectable in demo mode.
- Constellation (the UI view) creates activity from the first relevant stream
  event; it does not lose executor activity while waiting for a polling-created
  object.
- Backend journal rewind is recovered without a page refresh.
- Zero browser console errors and zero dropped workflow events.

### 8.7 Reliability and repeatability

- Live-AI concurrency and token budgets are explicit.
- Hybrid and deterministic-fallback modes are separately proved.
- At least two consecutive complete runs pass from the same source SHA and
  runtime fingerprint.
- Live and replay expose equivalent user-visible evidence for the same
  qualifying workflow set.
- Proof uses isolated runtime roots and deterministic seeds.

### 8.8 Cleanup and repository safety

- Teardown runs on success, assertion failure, process failure, and interruption.
- Runtime databases, browser state, generated proof payloads, and temporary
  logs remain ignored and are removed when the proof contract says they are
  ephemeral.
- All proof-owned ports are clear after teardown.
- The proof records pre-existing dirty paths and never stages or removes them.
- No proof artifact can be mistaken for source in a commit or archived
  worktree.

### 8.9 Seller review

Machine proof sets `build_ready: true`. A human seller review then checks:

- reset and startup simplicity;
- visual quality at the intended scale;
- pacing and approval visibility;
- story coherence;
- truthful AI/deterministic explanation;
- useful drawer, Memory, Knowledge, AG-UI, and Constellation transitions;
- absence of awkward empty, stale, or overloaded screens.

Only that review may set `seller_review: PASS` and support a "demo ready"
claim.

## 9. Failure and resume behavior

Every stage has explicit failure ownership:

| Failure | Owning layer | Recovery |
|---|---|---|
| Bad public fact or assumption | Research/Design | Correct source or approved assumption; preserve build state |
| Generated shape or registration defect | Generator skill/template | Fix generator, delete generated sandbox, regenerate |
| Bespoke business behavior defect | Pack implementation | Fix pack code with a failing test first |
| Missing execution evidence | Instrumentation/template or pack path | Fix the actual execution path; never fabricate rows |
| Browser/demo defect | Shared renderer or pack UI | Fix the narrowest truthful owner and rerun browser gate |
| Proof harness defect | Proof generator/shared tooling | Fix harness and prove the failing old behavior |
| Deployment preflight defect | Deploy contract | Stop before cloud mutation |

The operator receives:

- the failed criterion;
- the shortest decisive evidence;
- the affected stage;
- the exact resume command.

The skill does not restart the business interview or claim partial readiness.

## 10. Proposed changes by repository

### 10.1 `zava-control-plane`

#### `.github/skills/add-domain/SKILL.md`

- Make it a thin pack-aware controller.
- Add reuse/extend/bespoke classification.
- Replace registration-as-completion with staged proof.
- Require generation ownership updates and cascade proof.
- Remove duplicated proof prose in favor of authoritative references and
  executable commands.

#### `.github/skills/compose-domain-live/SKILL.md`

- Align stage names with the actual `add-domain` procedure.
- Remove manual hand-stitch assumptions.
- Report resumable artifact state and exact gate failures.
- Keep the critical controller path inline while allowing verified isolated
  implementation workers.

#### `docs/superpowers/skills/compose-domain/SKILL.md`

- Publish one current version and lifecycle.
- Reconcile segment, graph, deterministic, HITL, and sub-orchestrator paths.
- Remove conflicting read budgets and canonical-example rules.
- Make pack ownership, identity, observability, and recovery intrinsic.
- Add generator ownership output.
- Define the boundary where bespoke code is required.

#### `docs/superpowers/skills/author-durable-domain/SKILL.md`

- Remove the obsolete global graduation procedure.
- Consume the same pack-scoped templates and path vocabulary as
  `compose-domain`.
- Generate real `run_agent_session` instrumentation and current HITL recovery
  contracts.

#### Templates and validators

- Add schema/version headers.
- Generate pack-scoped registrations only.
- Generate canonical identity and observed execution evidence.
- Make all graduation edits complete and idempotent so no hand-stitch list
  remains.
- Add contract tests that fail on stale global paths, old phase names, direct
  uninstrumented model calls, or conflicting version language.
- Add a bespoke-runtime fixture that proves canonical agent, identity, HITL,
  command, and projection interfaces without generator ownership.

#### Shared authoring interfaces

- Document the mandatory substrate interfaces for generated and bespoke
  runtime code.
- Consolidate only repeated industry-neutral adapters needed to preserve agent
  evidence, workflow identity, HITL recovery, typed commands, and projections.
- Reject pack-local replacements that produce success-shaped but
  non-canonical evidence.

#### `docs/superpowers/skills/compose-domain/CHECKLIST.md`

- Split static generation checks from post-graduation runtime checks.
- Back each blocking runtime requirement with one executable command or test.
- Point to the authoritative proof contract rather than restating large blocks.

#### `docs/VERTICAL-PROOF.md`

- Add proof schema versioning and a two-run ledger.
- Add generator parity, AI honesty, demo experience, and cleanup gates.
- Distinguish invariant repeatability from byte-identical AI output.
- Distinguish build-ready from seller-review status.
- Define `make demo VERTICAL=<slug>` alongside `make prove`.

#### Tests and proof tooling

- Add cross-document contract tests for current vocabulary and ownership.
- Add generated-fixture tests for all phase truth modes.
- Make proof roots, ports, teardown, and dirty-tree handling hermetic.
- Make proof record two qualifying runs and explicit source modes.
- Add vertical-neutral browser assertions and pack-specific extension hooks.

### 10.2 `zava-constellation`

#### `skills/compose-org/SKILL.md`

- Turn the four headings into an explicit resumable state machine.
- Encode the golden-slice-first build order.
- Apply default demo and execution-mode policy.
- Ask only material business questions.
- Consume current substrate contracts dynamically.
- Produce generation ownership, permanent proof, and demo handoff artifacts.
- Separate build-ready and demo-ready claims.

#### `skills/compose-org/references/vertical-pack-contract.md`

- Remove instructions that add to read-only global business registries.
- Match the actual automatic manifest discovery and pack ownership model.
- Describe shared-substrate extension criteria separately from pack behavior.

#### `skills/compose-org/references/proof-contract.md`

- Mirror the versioned substrate proof schema.
- Add repeatability, execution honesty, demo experience, cleanup, and seller
  review.
- Correct the replay definition to require live/replay user-visible parity, not
  merely graceful degradation.

#### `skills/compose-org/references/upstream-pin.md`

- Replace the obsolete May 2026 shape probe with current manifest discovery,
  pack isolation, proof schema, and representative import checks.
- Make freshness validation detect contract drift rather than only a fixed old
  SHA.

#### `skills/research-company/SKILL.md`

- Keep the factual boundary.
- Allow `compose-org` to orchestrate a new industry model when no primer exists
  instead of exposing a separate prerequisite to the operator.

#### `skills/zava-workspace-deploy/SKILL.md`

- Validate the new proof schema and two-run ledger.
- Recompute or verify the selected runtime fingerprint.
- Require proof for the chosen live/replay mode.
- Use manifest-declared post-deploy smoke capabilities.
- Preserve the explicit cloud mutation and tenant-isolation gates.

#### Companion contract tests

- Reject stale global registry paths and obsolete substrate pins.
- Require current build, proof, demo, and deploy state vocabulary.
- Verify that the companion and substrate proof schema versions agree.

## 11. Airline acceptance vertical

The first acceptance request is intentionally short:

> Build an airline demo in the BA/IAG space.

The builder must turn that into a source-grounded, synthetic airline vertical
without requiring the operator to repeat the rules in this document.

The companion repository already contains an incomplete airline industry
primer. Research expands and reviews that primer; it is an input candidate, not
pre-approved truth or a reason to skip fresh public-source validation.

### 11.1 Boundaries

- Use public facts and disclosed operating realities only.
- Do not copy proprietary BA or IAG data, processes, policies, or branding.
- Label the resulting actors, schedules, passengers, and incidents synthetic.
- Make the pack distinct from the existing Travel tour-operator vertical.
- Reuse industry-neutral substrate primitives, not Travel business behavior.

### 11.2 Generality test

The airline should force the builder to reason about concepts not already
captured by Fashion, Telco, or tour operations, such as:

- aircraft rotations and tail assignment;
- crew legality and duty limits;
- airport slots and curfews;
- passenger connections and reaccommodation;
- baggage and ground-handling dependencies;
- disruption control and network recovery.

The final flagship story is selected after research. A likely candidate is a
network disruption that requires constrained recovery planning, governed
operational choices, typed schedule or reaccommodation commands, downstream
customer-care effects, and measured recovery. This is an example, not a
hard-coded template.

### 11.3 Acceptance criteria

Starting from the one-line request, the revised skills must:

1. Complete research and clearly separate facts from synthetic assumptions.
2. Ask only material business questions.
3. Produce and approve a rich design.
4. Build one browser-proved golden slice before process breadth.
5. Introduce truthful airline-specific entities, dynamics, authority, commands,
   projections, and presentation.
6. Exercise at least one typed flagship command over an entity kind and
   operational constraint absent from every existing vertical. Passenger
   reaccommodation alone is insufficient; examples include aircraft tail
   reassignment constrained by rotation, crew legality, slots, or curfew.
7. Use live AI only where declared and prove the observed sessions and tools.
8. Complete every declared workflow in two consecutive live runs.
9. Pass replay parity, browser, cleanup, and cross-surface identity gates.
10. Generate an inspectable `make demo VERTICAL=<slug>` state and talk track.
11. Finish with build-ready evidence and an explicit seller-review status.

If the result is a relabelled Travel pack, requires repeated engineering
instructions from the operator, or passes APIs while presenting a weak demo,
the skill redesign has failed.

## 12. Test strategy

### 12.1 Contract tests

Both repositories get dependency-light tests that parse active skill and
reference files and reject:

- conflicting contract versions;
- stale paths or global registry instructions;
- proof schema disagreement;
- missing build/demo/deploy state distinctions;
- uninstrumented agent templates;
- manual post-generation hand-stitches;
- unsupported success claims.

### 12.2 Generator tests

Use compact fixtures to cover:

- deterministic phase;
- real agent phase;
- HITL with authority and recovery;
- sub-orchestrator lineage;
- profile reuse;
- bespoke-file ownership exclusion;
- deletion/regeneration parity.

Tests verify generated behavior, not only string presence.

### 12.3 Proof harness tests

Inject failures for:

- live-AI rate limit;
- Durable timeout;
- missed HITL event;
- backend journal reset;
- SSE event-before-poll race;
- browser error;
- failed teardown;
- dirty pre-existing worktree;
- mismatched replay source mode;
- stale source SHA or runtime fingerprint.

Each failure must produce a failing verdict, evidence path, cleanup, and resume
state.

### 12.4 Airline acceptance

Run the complete pipeline in a fresh isolated checkout. Existing airline
implementation code is not used as a template. The acceptance result is the
strongest evidence that the skills generalize beyond the lessons that produced
them.

## 13. Non-goals

- Define every possible vertical in YAML.
- Force every workflow into one orchestration shape.
- Require AI where deterministic logic is more truthful.
- Require byte-identical live-model prose or optional tool selection.
- Clone Telco, Fashion, Travel, or any named company.
- Create a new family of public builder skills.
- Deploy automatically, push automatically, or hide failed proof.
- Make human seller judgment a fake machine metric.

## 14. Rollout

This design is intentionally broader than one safe implementation plan. Each
phase below gets a separate plan and review checkpoint. Cross-repository phases
may use paired PRs, but a later phase starts only after the preceding contract
is active in both repositories.

1. **Align contracts:** remove cross-repository contradictions and version the
   shared build/proof vocabulary.
2. **Repair generators and bespoke boundaries:** make pack ownership,
   instrumentation, HITL recovery, ownership manifests, complete graduation,
   and the mandatory bespoke runtime interfaces intrinsic.
3. **Harden proof and demo commands:** add repeatability, hermetic cleanup,
   observed AI evidence, vertical-neutral UI gates, and seller status.
4. **Upgrade controller and deploy handoff:** make `compose-org` resumable and
   deploy consume the versioned proof.
5. **Run the airline acceptance:** use the one-line request and fix the skills,
   not the acceptance output, when general procedure defects appear.

## 15. Success

The redesign succeeds when the operator can request a new demo vertical in one
sentence, answer only a small number of real business questions, and receive:

- a truthful, novel, code-first vertical;
- a causal and governed flagship story;
- an honest mix of live AI and deterministic execution;
- a visible, stable, resettable demo;
- repeatable live/replay evidence;
- a clear build-ready versus demo-ready status;
- a deployable artifact without repeating the engineering lessons from prior
  verticals.
