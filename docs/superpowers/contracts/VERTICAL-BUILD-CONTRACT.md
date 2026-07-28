# Vertical Build Contract

**Contract version:** `1.0.0`
**Status:** Active

## Authority

This is the canonical code-first contract for building a Zava vertical.
`docs/VERTICAL-PROOF.md` is the proof authority. Lower-level and companion
skills reference these contracts rather than defining competing ownership,
readiness, or graduation procedures.

## Code-first boundary

A vertical is executable Python and TypeScript: pack composition, actor-world
models, Durable workflows, skills, MCP tools, typed commands, projections, and
optional UI extensions.

Structured artifacts preserve facts, generated-file ownership, resumability,
and proof. They are not a universal vertical DSL and do not replace bespoke
code.

## Capability classification

Classify each capability before implementation:

1. **Reuse** an existing engine or profile only when behavior and command
   semantics match.
2. **Extend** an industry-neutral substrate primitive when multiple verticals
   need the same behavior.
3. **Bespoke** pack-owned code when the world, workflow, command, projection,
   or presentation is genuinely different.

Generated and bespoke code use the same canonical identity, governance,
execution-evidence, typed-command, and projection interfaces.

## Phase truth modes

| Mode | Meaning |
|---|---|
| `agent` | Calls canonical `run_agent_session` and persists observed reasoning and tool evidence |
| `deterministic` | Runs deterministic typed logic and records input/output provenance |
| `hitl` | Uses the governance kernel, persisted recovery context, and a declared external event |
| `sub_orchestrator` | Runs a real child orchestration with parent/child lineage |

Declaring `agent` while returning canned deterministic output is a blocking
contract failure. Deterministic code remains correct when rules, safety, cost,
or repeatability require it.

## Build order

Build and prove one golden vertical slice before adding process breadth:

```text
world event
  -> sensor
  -> objective
  -> Durable workflow
  -> declared phase truth modes
  -> HITL when applicable
  -> typed command
  -> world mutation
  -> measured outcome
  -> visible cross-surface evidence
```

Supporting processes are then added by Reuse, Extend, or Bespoke
implementation. Each keeps a distinct trigger, case, typed command,
projection, and proof evidence.

## Readiness

- **build ready**: every applicable machine gate in
  `docs/VERTICAL-PROOF.md` passes.
- **demo ready**: build-ready evidence plus a human seller review of reset,
  pacing, visual quality, and story coherence.
- **deployed**: a separately approved deployment mode passes deployment
  preflight and post-deploy smoke.

Machine proof cannot set seller review to PASS. A failed or skipped gate cannot
produce a readiness-shaped result.

## Pack ownership

Business behavior belongs to one automatically discovered
`verticals/<slug>/manifest.py` pack. `api/shared/domains.py`,
`api/shared/functions.py`, and equivalent compatibility modules are read-only
active-pack adapters, not graduation targets.

Pack-specific business behavior must not leak into another selected pack.

## Compatibility

Companion skills record the build and proof contract versions they were
validated against. A missing or incompatible version is a blocking preflight
failure, not permission to fall back to an older procedure.
