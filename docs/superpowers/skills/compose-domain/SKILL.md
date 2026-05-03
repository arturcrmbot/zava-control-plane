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
- 1 `GRADUATION.md` at the sandbox root listing the diffs the engineer must
  apply to `function_app.py`, `simulator_orchestrator.py`,
  `routes/simulator.py`, `blueprint_inventory.py`, `constants.py`, and
  `graphs/__init__.py`. The simulator spawn helper, the inject route, and
  any synthetic test payload all live in GRADUATION.md — NOT in standalone
  files. v1 generated domains are small enough that they don't need
  domain-specific synthetic-data or simulator modules.

### Conventions (codified for determinism)

These were free choices in earlier drafts; codifying them removes
improvisation from the procedure.

- **HITL external event name.** For every phase whose `kind: hitl`, the
  orchestrator's `wait_for_external_event(...)` name is exactly
  `<phase_name>_decision`, and the matching persona SKILL.md's `## Procedure`
  step 3 says "the orchestrator is waiting on the `<phase_name>_decision`
  event". Both places write the same string. Do not invent.
- **Activity-trigger names.** `<domain.name with - replaced by _>_<phase_name>_activity_trigger`.
  E.g. `fleet_travel_preapproval_employee_lookup_activity_trigger`.
- **Graph builder names.** `build_<domain.name with - replaced by _>_<phase_name>_workflow`.
- **Agent skill folder name.** `<domain.name>-<agent_skill_name>`. E.g.
  `fleet-travel-preapproval-policy-fit-checker`.
- **Tool registration name.** From the brief's `external_systems[].mcp_tool` and
  each `operations[].name`: `<mcp_tool>_<operation>`. E.g.
  `concur_travel_policy_get_policy`. The agent skill's `allowed-tools`
  CSV uses these names verbatim.
- **Run id.** `<YYYYMMDD-HHMMSS>-<domain.name>` from current UTC time.
  Compute once at the top of step 4; use the literal value everywhere
  downstream.

### Step 3 — Inventory and isomorphism

Before invoking any sub-skill, read **exactly these 8 files** end-to-end
in this session. They are the canonical examples sub-skills mirror. Do
not read more (you don't need them) and do not read fewer (you'll
improvise the parts you didn't load). Drift in any of these files means
downstream sub-skills will generate stale-shaped code — stop and update
this SKILL.

| # | Canonical example | Used by sub-skill |
|---|---|---|
| 1 | `api/server/skills/receipt-validator/SKILL.md` | `author-runtime-skill` (phase_agent mode) |
| 2 | `api/server/personae/line_manager/SKILL.md` | `author-runtime-skill` (persona mode) |
| 3 | `api/server/mcp_tools/claim_lookup.py` | `author-mcp-tool` |
| 4 | `api/functions/workflows/expense_claim.py` | `author-durable-domain` (orchestrator + HITL pattern) |
| 5 | `api/functions/workflows/activities.py` | `author-durable-domain` (activities module — reuses `_run_workflow` from here) |
| 6 | `api/functions/graphs/classify.py` | `author-durable-domain` (per-phase agent graph) |
| 7 | `api/functions/graphs/executors/agents/agent_rag_classifier.py` | `author-durable-domain` (agent executor) |
| 8 | `api/functions/graphs/executors/validators/validate_classification_schema_node.py` | `author-durable-domain` (validator) |

**For deterministic phases**, also note: `api/functions/graphs/_tracked_executor.py`
for the `TrackedExecutor` constructor signature (used directly with
`executor_type="deterministic"` and an inline `_<phase>_execute` async
fn — there is no canonical deterministic-graph example to mirror, so
follow the v1 graduated example at `api/functions/graphs/fleet_travel_preapproval_employee_lookup.py`).

### Step 4 — Generate into sandbox

Compute `RUN_ID = <YYYYMMDD-HHMMSS>-<domain.name>` from the current UTC
time (one shell call: `date -u +"%Y%m%d-%H%M%S"`). Create
`tools/scratch/compose-domain/<RUN_ID>/` with the layout from the spec
doc §6.

For each artefact in the plan, invoke the matching sub-skill exactly
once, passing the **structured arguments** below. Do not pass the brief
as a whole — pass only the relevant slice. This is the boundary that
keeps sub-skills deterministic.

#### When invoking `author-runtime-skill` (mode: phase_agent)

```
mode: phase_agent
output_path: <RUN_ROOT>/api/server/skills/<domain.name>-<phase.agent_skill_name>/SKILL.md
brief: <the phase entry from brief.phases[]>
canonical_example_path: api/server/skills/receipt-validator/SKILL.md
available_mcp_tools:
  - { name: "<mcp_tool>_<operation>", description: "<from the tool's @define_tool description>" }
  - ... (one per (mcp_tool, operation) pair the phase's external_systems[] resolves to)
```

#### When invoking `author-runtime-skill` (mode: persona)

```
mode: persona
output_path: <RUN_ROOT>/api/server/personae/<role>/SKILL.md
brief: <the persona entry from brief.personae[]>
canonical_example_path: api/server/personae/line_manager/SKILL.md
available_mcp_tools: []   # personae have empty allowed-tools by convention
external_event_name: <hitl_phase_name>_decision   # convention; same string the orchestrator waits on
```

#### When invoking `author-mcp-tool`

```
output_path: <RUN_ROOT>/api/server/mcp_tools/<external_systems[].mcp_tool>.py
tool_brief: <the external_systems[] entry>
canonical_example_path: api/server/mcp_tools/claim_lookup.py
```

#### When invoking `author-durable-domain`

```
output_root: <RUN_ROOT>
brief: <the entire brief>
canonical_paths:
  orchestrator: api/functions/workflows/expense_claim.py
  activities: api/functions/workflows/activities.py
  agent_graph: api/functions/graphs/classify.py
  deterministic_graph: api/functions/graphs/fleet_travel_preapproval_employee_lookup.py  # v1 graduated
  agent_executor: api/functions/graphs/executors/agents/agent_rag_classifier.py
  validator: api/functions/graphs/executors/validators/validate_classification_schema_node.py
  tracked_executor: api/functions/graphs/_tracked_executor.py
```

Each sub-skill writes its files to the sandbox path under the mirrored
real-tree layout. **No sub-skill writes to a real path.** When a
sub-skill returns, you continue with the next.

After all sub-skills have run, only one more file remains for
`compose-domain` itself to write:

- `<RUN_ROOT>/GRADUATION.md` — hand-edit diff list. Use the template at
  `docs/superpowers/skills/compose-domain/templates/GRADUATION.md.tmpl`.
  `author-durable-domain` returns the structured fragments
  (orchestrator-import block, activity-trigger block, etc.) for you to
  splice into the template. **Note:** v1 generated domains do NOT add a
  `Workflow` record to `app_state.store` (the existing
  `Workflow` / `ClaimData` / `HiringData` types are domain-specific). The
  spawn helper in GRADUATION.md §5 must omit the
  `app_state.store.upsert_workflow(w)` call that `spawn_hiring_workflow`
  uses.

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

### Step 6 — Determinism check (operator-invoked, optional)

The operator may, after a clean self-check, re-invoke this skill against
the same brief and run the determinism check at
`compose-domain/CHECKLIST.md` §6.1. The two sandboxes must `diff -r` to
nothing meaningful. Divergence points are exactly the parts of these
SKILLs that gave the author freedom — the fix is to codify that part
here or in the matching sub-skill, then re-run.

The HITL event-name convention, the activity-trigger naming convention,
and the structured sub-skill input contracts in step 4 above are the
specific fixes that emerged from the v1 → v2 iteration of this SKILL.
Future iterations follow the same loop: improvise once, codify, re-run,
diff.

## Anti-patterns (things you must not do)

- Inventing fields not present in the brief.
- Inventing the HITL external event name. Convention is
  `<phase_name>_decision`. The orchestrator's
  `wait_for_external_event(...)` and the persona SKILL.md both write
  this exact string.
- Inventing tool names in an agent skill's `allowed-tools`. The
  `author-runtime-skill` step 4 list is authoritative — if a tool you
  want isn't there, it's the caller's bug, not yours. Stop.
- Copying a runtime SKILL.md verbatim from `api/server/skills/` and just
  renaming things — the result must be an *authored* skill, not a
  rebadged one.
- Skipping the validator on agent phases ("it's a stub, the validator is
  trivial"). Validators are the bounded-probabilism edge; the harness
  expects them.
- Writing the orchestrator before reading the 8 canonical examples in
  step 3 once in this session.
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
