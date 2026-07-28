---
name: author-durable-domain
description: |
  Sub-skill of `compose-domain`. Writes the sandboxed Durable runtime artifacts
  selected by the parent artifact plan and returns pack-scoped graduation
  fragments. Generated agent paths use canonical run_agent_session; generated
  HITL paths preserve identity and recovery context. The parent compose-domain
  skill writes GRADUATION.md and graduate.sh.
audience: design-time-only
forbidden-runtime: true
---

# author-durable-domain

Generate the Durable artifacts selected by the parent `compose-domain` plan.
Do not derive a second architecture or graduation procedure.

## Authority

Follow:

1. `docs/superpowers/contracts/VERTICAL-BUILD-CONTRACT.md`;
2. the parent `compose-domain` path table and artifact plan;
3. the current templates selected by that plan;
4. canonical examples only when the parent or template names one.

The parent path table and artifact plan are authoritative.

## Inputs

1. **`output_root`** - absolute sandbox run path.
2. **`vertical`** - selected installed pack name.
3. **`brief`** - validated current brief.
4. **`artifact_plan`** - exact Step 2 artifact list, including phase kind,
   output path, and selected template.
5. **`canonical_paths`** - only current examples named by the parent invocation.

Reject an input when an output escapes `output_root`, a phase kind is unknown,
a selected template is missing, or a planned path conflicts with another
artifact.

## Outputs

Write only files named by `artifact_plan`. Return:

- the generated-file copy map;
- imports and registrations for the selected pack's `durable.py`;
- graph exports when graph artifacts are planned;
- selected-pack spawner registration;
- selected-pack domain declaration;
- selected-pack function membership.

These are pack-scoped graduation fragments. The parent `compose-domain` writes
`GRADUATION.md` and `graduate.sh`.

## Procedure

### Step 1 - Validate the plan

Validate all inputs before creating a file. Do not infer missing artifacts.

### Step 2 - Read on demand

Read each selected template. Read only the canonical example needed to resolve
a byte-shape not covered by the parent contract or template.

### Step 3 - Generate planned runtime artifacts

Use the parent-selected template for every output:

- `kind: agent` uses its planned segment by default;
- `kind: graph` uses its planned graph, executor, and in-graph validator;
- `kind: deterministic` uses only its planned deterministic artifacts;
- `kind: hitl` adds no graph or agent executor;
- `kind: sub_orchestrator` adds no per-phase execution file.

Do not convert one phase kind into another.

### Step 4 - Preserve execution truth

Every planned agent path calls canonical `run_agent_session` and forwards
workflow, orchestration, and phase provenance. Generate an in-graph executor
only for a planned `kind: graph` phase; a planned segment does not receive a
duplicate graph executor.

Generate only validators named by `artifact_plan`. Segment validation is a
Durable activity boundary; graph validation remains inside the planned graph.

### Step 5 - Preserve identity and HITL recovery

Every checkpoint carries canonical workflow and orchestration identity. Every
planned HITL suspend carries persona, external event, phase, and reconstructable
decision context. Event names match the persona contract byte-for-byte.

### Step 6 - Return graduation fragments

Return only fragments represented by `artifact_plan`. Every append fragment
uses the exact compose-domain sentinel format and is idempotent.

Global compatibility adapters, `function_app.py`, Blueprint inventory, global
simulator routes, and another vertical are never targets.

## Self-check

- Generated paths exactly equal `artifact_plan`.
- No file escapes `output_root`.
- Agent paths use canonical `run_agent_session`.
- Planned validators use the parent-selected validation boundary.
- Workflow and orchestration identity are forwarded.
- HITL suspend payloads preserve recovery context.
- Pack-scoped fragments target only the selected pack's `durable.py`,
  `spawners.py`, `domains.py`, and `functions.py`.
- No placeholder or unplanned artifact remains.

If a check fails, report the failing artifact and stop. Fix the owning parent
contract or template rather than inventing a local exception.

## Forbidden

- Re-deriving the artifact list from the brief.
- Generating one graph per phase regardless of `kind`.
- Returning a global-registration fragment.
- Calling a model outside canonical `run_agent_session`.
- Writing `GRADUATION.md`, `graduate.sh`, or a live-tree file.
- Claiming success when a planned artifact or fragment is missing.
