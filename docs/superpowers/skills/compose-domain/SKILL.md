---
name: compose-domain
description: |
  Design-time meta-skill. Given a domain brief (YAML) or a free-text idea,
  produce a complete Durable-fidelity domain sandbox: orchestrator, per-phase
  graphs, validators, agent skills, MCP tool stubs, persona(e), synthetic
  data and simulator entries — all shape-isomorphic to the existing
  `expense-claim` and `hiring` domains. Sandbox-only; never touches real
  trees. Calls `author-runtime-skill`, `author-mcp-tool`, and
  `author-durable-domain` as sub-skills.
audience: design-time-only
forbidden-runtime: true
---

# compose-domain

You are the orchestrator for a five-step procedure that turns a domain brief
into a complete sandboxed Durable-fidelity domain. You do not improvise. You
follow this skill literally. When you are uncertain, you stop and ask the
operator — you do not invent.

> **Forbidden.** This skill, and any sub-skill it invokes, **MUST NOT**
> write to any path outside `tools/scratch/compose-domain/<run-id>/` and
> `docs/superpowers/specs/`. In particular: never edit
> `api/server/`, `api/functions/`, `function_app.py`,
> `api/server/services/blueprint_inventory.py`,
> `api/server/services/simulator_orchestrator.py`, or any other live tree.
> Graduation is a separate, manual step.

## Inputs

You are invoked one of two ways:

1. **With a brief path.** "Run compose-domain against
   `docs/superpowers/specs/<domain>-brief.yaml`." Skip step 1.
2. **With a free-text idea.** "Compose a new domain for X." Run step 1 to
   produce the brief, then continue.

## The five steps

### Step 1 — Brief intake (only if no YAML brief was supplied)

Hand off to the existing `brainstorming` skill. It will elicit the brief
through one-question-at-a-time dialogue with the operator. When it returns
the design, transcribe it into the YAML schema below and write it to
`docs/superpowers/specs/<domain.name>-brief.yaml`. Read it back to the
operator. Wait for explicit approval. Then continue to step 2.

If the operator gives you a YAML brief path on entry, skip this step.

#### Brief schema (authoritative)

```yaml
domain:
  name: <kebab-case, used as folder/file prefix; must start with "fleet-">
  display_name: <human label>
  owner_role: <snake_case persona role; the dominant operator>
  description: |
    One paragraph at the level a senior engineer would write on a whiteboard.

phases:
  - name: <snake_case>
    intent: <one sentence>
    kind: deterministic | agent | hitl
    external_systems: [<id>, ...]            # ids from the external_systems list below
    hitl: false | true
    # only when kind == agent:
    agent_skill_name: <kebab-case>
    # only when kind == hitl:
    persona: <role from personae below>

personae:
  - role: <snake_case>
    decision_policy: |
      One paragraph stating the rule the persona uses to decide.

external_systems:
  - id: <snake_case>
    mcp_tool: <snake_case Python module name, no .py>
    operations: [<snake_case function name>, ...]
```

Validate the brief before you continue:
- `domain.name` starts with `fleet-`.
- Every phase referenced in `external_systems` exists in the top-level
  `external_systems` list.
- Every persona referenced in a HITL phase exists in `personae`.
- At least one phase has `kind: agent`.
- At least one phase has `kind: hitl`.

If validation fails, stop and tell the operator what's wrong. Do not
proceed to step 2.

### Step 2 — Plan

From the brief, produce the artefact list. **Print this list back to the
operator before you write a single file.** Wait for "go".

For each phase:
- `kind: deterministic` → 1 MAF graph file with a single deterministic
  executor. No agent skill. May still have a validator.
- `kind: agent` → 1 MAF graph file with `agent → validator → terminal`.
  1 runtime SKILL.md at `api/server/skills/<domain.name>-<agent_skill_name>/`.
  1 agent executor at `api/functions/graphs/executors/agents/agent_<...>.py`.
  1 validator at `api/functions/graphs/executors/validators/validate_<...>_schema.py`.
- `kind: hitl` → no graph (the orchestrator does the wait directly).
  1 persona SKILL.md at `api/server/personae/<role>/SKILL.md`.

For each `external_systems[]` entry whose `mcp_tool` does not already
exist in `api/server/mcp_tools/` (check this against the live filesystem):
- 1 MCP tool stub at `api/server/mcp_tools/<mcp_tool>.py`.

Always:
- 1 orchestrator at `api/functions/workflows/<domain.name>.py`.
- 1 activities module at `api/functions/workflows/<domain.name>_activities.py`.
- 1 synthetic generator at `api/server/services/synthetic_data_<domain.name>.py`.
- 1 simulator entry stub at `api/server/services/simulator_<domain.name>.py`.
- 1 `GRADUATION.md` at the sandbox root listing the diffs the engineer must
  apply to `function_app.py`, `simulator_orchestrator.py`, and
  `blueprint_inventory.py`.

### Step 3 — Inventory and isomorphism

Before invoking any sub-skill, read the canonical examples once and remember
them. **Do not skip this step.** Sub-skills depend on you having loaded
these so they can be referred to by path.

- Existing runtime skills: `api/server/skills/receipt-validator/SKILL.md`,
  `api/server/skills/cv-crystalliser/SKILL.md`,
  `api/server/skills/budget-checker/SKILL.md`.
- Existing MCP tools (in-process): `api/server/mcp_tools/claim_lookup.py`,
  `api/server/mcp_tools/policy_search.py`.
- Existing orchestrators: `api/functions/workflows/expense_claim.py`,
  `api/functions/workflows/hiring.py`.
- Existing activities module: `api/functions/workflows/activities.py`.
- Existing per-phase graph: `api/functions/graphs/classify.py` (the simplest
  agent → validator → terminal example).
- Existing agent executor: `api/functions/graphs/executors/agents/agent_rag_classifier.py`
  and the wrapper `api/functions/graphs/executors/agents/_wrapper.py`.
- Existing validator: `api/functions/graphs/executors/validators/validate_classification_schema_node.py`.
- Existing tracked-executor base: `api/functions/graphs/_tracked_executor.py`.
- Existing FleetEvent shapes: `api/shared/events.py`.
- Existing inventory loader: `api/server/services/blueprint_inventory.py`.
- Existing simulator: `api/server/services/simulator_orchestrator.py`.

If any of these files have moved or changed since this skill was written,
**stop**. Tell the operator the canonical example has drifted; fix this
SKILL.md before continuing. Drift here means downstream sub-skills will
generate stale-shaped code.

### Step 4 — Generate into sandbox

Compute `RUN_ID = <YYYYMMDD-HHMMSS>-<domain.name>` from the current UTC
time. Create `tools/scratch/compose-domain/<RUN_ID>/` with the layout from
the spec doc §6.

For each artefact in the plan, invoke the matching sub-skill exactly once:

| Artefact | Sub-skill | Inputs |
|---|---|---|
| Runtime SKILL.md (phase agent) | `author-runtime-skill` | brief, phase, the canonical agent SKILL.md (`receipt-validator`), the relevant `external_systems[]` entries |
| Persona SKILL.md | `author-runtime-skill` | brief, persona, the canonical `fleet-manager/SKILL.md` (closest existing analogue) |
| MCP tool stub | `author-mcp-tool` | `external_systems[]` entry, `claim_lookup.py` and `policy_search.py` as canonical examples |
| Orchestrator + activities + graphs + validators | `author-durable-domain` | the full brief, `expense_claim.py` + `hiring.py` + `activities.py` + `classify.py` |

Each sub-skill writes its files directly to the sandbox path under the
mirrored real-tree layout. **No sub-skill writes to a real path.** When a
sub-skill returns, you continue with the next.

After all sub-skills have run, write:
- `<run-id>/synthetic_data_<domain.name>.py` — a tiny stub. The shape is
  documented in the `author-durable-domain` skill.
- `<run-id>/simulator_<domain.name>.py` — a tiny `spawn_<domain.name>_workflow`
  helper, mirroring `spawn_expense_workflow`'s shape.
- `<run-id>/GRADUATION.md` — the hand-edit diff list. Format documented in
  `compose-domain/CHECKLIST.md` §"Graduation".

### Step 5 — Self-check

Run the checklist at `compose-domain/CHECKLIST.md` against the sandbox.
Produce a one-page report at `<run-id>/REPORT.md` with one row per
checklist item (PASS / FAIL / N/A). Print the same report inline to the
operator.

If any item FAILs, **do not** silently fix it. Tell the operator and stop.
The right move when something fails is almost always to fix the SKILL.md
that produced it, then delete the sandbox and re-run.

If everything passes, end with:

> Sandbox at `tools/scratch/compose-domain/<RUN_ID>/`. CHECKLIST passed.
> Graduation is manual — see `<RUN_ID>/GRADUATION.md`.

Do not graduate. Do not start the demo stack. Do not run any tests against
the real trees. The skill ends here.

## Anti-patterns (things you must not do)

- Inventing fields not present in the brief.
- Copying a runtime SKILL.md verbatim from `api/server/skills/` and just
  renaming things — the result must be an *authored* skill, not a
  rebadged one.
- Skipping the validator on agent phases ("it's a stub, the validator is
  trivial"). Validators are the bounded-probabilism edge; the harness
  expects them.
- Writing the orchestrator before reading `expense_claim.py` once in this
  session.
- Editing `function_app.py` "just to make the smoke test work". That's
  graduation. It happens by hand. By an engineer. After this skill ends.
- Graduating "while you're at it" because the sandbox looks fine. Stop.
- Running on a brief whose `domain.name` does not start with `fleet-`. The
  prefix is the visual signal that distinguishes generated domains from
  the two hand-written ones.
- Pretending you finished when you didn't. If you got blocked, say so. If
  you skipped a step, say so. If a sub-skill returned something the
  CHECKLIST won't pass, say so.

## Operator-facing prompts

When you ask the operator a question, you are explicit about what you
need:

- "Brief at `docs/superpowers/specs/<x>-brief.yaml` validates. Plan
  follows. Confirm before I generate."
- "Step 3 noted that `api/functions/graphs/classify.py` has changed shape
  since this skill was last revised. Stopping. Please update
  `compose-domain/SKILL.md` step 3 with the new canonical paths and
  re-invoke."
- "CHECKLIST item §3.4 FAIL: agent skill `<x>` references MCP tool `<y>`
  in `allowed-tools` but no such tool exists in the sandbox or
  `api/server/mcp_tools/`. The bug is probably in
  `author-runtime-skill/SKILL.md` step 4 (allow-list resolution).
  Stopping."
