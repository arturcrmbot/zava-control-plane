---
name: author-durable-domain
description: |
  Sub-skill of `compose-domain`. Writes the Durable Functions orchestrator,
  the activities module, one MAF Pregel graph per phase, and one validator
  per agent phase — all to sandbox paths, all shape-isomorphic to
  `expense_claim.py`, `hiring.py`, `activities.py`, `classify.py`, etc.
  Writes the GRADUATION.md describing the diff that the engineer must apply
  by hand to `function_app.py` and `simulator_orchestrator.py` at graduation.
audience: design-time-only
forbidden-runtime: true
---

# author-durable-domain

You write the **Durable runtime** for one domain per invocation. Multiple
files, all under the same sandbox `<run-id>/`. You are the heaviest
sub-skill — read the canonical examples thoroughly before generating.

## Inputs you require from the caller

1. **`output_root`** — absolute path of the sandbox `<run-id>/`.
2. **`brief`** — the entire YAML brief.
3. **`canonical_paths`** — exactly the list:
   - `api/functions/workflows/expense_claim.py` (orchestrator pattern)
   - `api/functions/workflows/hiring.py` (orchestrator with HITL gates)
   - `api/functions/workflows/activities.py` (activity functions)
   - `api/functions/graphs/classify.py` (simplest agent → validator graph)
   - `api/functions/graphs/_tracked_executor.py` (the executor base class)
   - `api/functions/graphs/executors/agents/agent_rag_classifier.py` and
     `api/functions/graphs/executors/agents/_wrapper.py` (agent executor)
   - `api/functions/graphs/executors/validators/validate_classification_schema_node.py`
     (validator)
   - `api/shared/events.py` (FleetEvent shape; you do NOT add new types in
     v1 — generated domains reuse the existing `durable.*` and
     `workflow.*` types)
   - `function_app.py` (registration shape — you do NOT edit this; you
     describe the diff in GRADUATION.md)
   - `api/server/services/simulator_orchestrator.py` (entry-point shape —
     you do NOT edit this; you describe the diff in GRADUATION.md)

If anything in this list is missing or has shifted shape, **stop**.

## Procedure

### Step 1 — Read canonical examples

Read every file in `canonical_paths` end-to-end. You are about to
reproduce their shape with one variable substituted: the domain. If you
have not read them, you will hallucinate function signatures.

### Step 2 — Plan the file set

From the brief, the file set is:

```
<output_root>/api/functions/workflows/<domain.name>.py
<output_root>/api/functions/workflows/<domain.name>_activities.py
<output_root>/api/functions/graphs/<domain.name>_<phase.name>.py        — one per phase
<output_root>/api/functions/graphs/executors/agents/agent_<domain.name>_<phase.name>.py
                                                                         — one per agent phase
<output_root>/api/functions/graphs/executors/validators/validate_<domain.name>_<phase.name>.py
                                                                         — one per agent phase
<output_root>/GRADUATION.md
```

### Step 3 — Write the orchestrator

Use `templates/orchestrator.py.tmpl`.

For each phase in order, emit:

- `kind: deterministic` →
  ```python
  <phase>_result = yield context.call_activity("<domain>_<phase>_activity_trigger", enriched)
  enriched = {**enriched, "<phase>": <phase>_result}
  ```
- `kind: agent` → same as deterministic (the activity wraps the graph
  which wraps the agent + validator).
- `kind: hitl` →
  ```python
  yield context.call_activity("checkpoint_activity_trigger", {
      "workflow_id": workflow_id, "instance_id": context.instance_id,
      "kind": "suspended",
      "payload": {"reason": "awaiting_<phase>", "phase": "<phase>",
                  "wait_kind": "operator_review"},
  })
  ev = context.wait_for_external_event("<phase>_decision")
  to = context.create_timer(context.current_utc_datetime + <PHASE>_TIMEOUT)
  winner = yield context.task_any([ev, to])
  if winner == to:
      yield context.call_activity("checkpoint_activity_trigger", {
          "workflow_id": workflow_id, "instance_id": context.instance_id,
          "kind": "workflow.completed",
          "payload": {"status": "timeout", "phase": "<phase>"}
      })
      return {"status": "timeout", "phase": "<phase>"}
  to.cancel()
  enriched["<phase>_decision"] = ev.result
  yield context.call_activity("checkpoint_activity_trigger", {
      "workflow_id": workflow_id, "instance_id": context.instance_id,
      "kind": "resumed", "payload": {"phase": "<phase>"}
  })
  ```
- The orchestrator emits `workflow.started` at entry and `workflow.completed`
  at exit, both via `checkpoint_activity_trigger`. Mirror `expense_claim.py`.

For the timeout constant `<PHASE>_TIMEOUT`, **do not** edit
`api/shared/constants.py`. Define it locally at the top of the
orchestrator file as `<PHASE>_TIMEOUT = timedelta(hours=24)`. The
GRADUATION.md notes that lifting it into `api/shared/constants.py` is a
hand step (so the simulator can override per-demo).

### Step 4 — Write the activities module

Use `templates/activity.py.tmpl`.

One activity function per phase:

```python
def <domain>_<phase>_activity(payload: dict) -> dict:
    """Phase <N> — <intent>."""
    return asyncio.run(_run_workflow(build_<domain>_<phase>_workflow, payload, "<Phase>"))
```

Reuse `_run_workflow` by importing it from `api.functions.workflows.activities`.
Do not redefine it.

For deterministic phases (no agent, no validator), still emit a graph file
and an activity, so the FleetEvent timeline is uniform across phases.

### Step 5 — Write per-phase MAF graphs

Use `templates/phase_graph.py.tmpl`.

For `kind: agent`:

```python
def build_<domain>_<phase>_workflow() -> Workflow:
    n1 = TrackedExecutor(id="<phase>", name="agent_<domain>_<phase>",
                         executor_type="agent",
                         fn=agent_<domain>_<phase>.execute)
    n2 = TrackedExecutor(id="val_<phase>", name="validate_<phase>_schema",
                         executor_type="validator",
                         fn=validate_<domain>_<phase>.execute)
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2)
        .add_edge(n2, term)
        .build()
    )
```

For `kind: deterministic`: a single deterministic executor (a small
function in the same file) → terminal.

### Step 6 — Write agent executors

Use `templates/agent_executor.py.tmpl`. Mirror `agent_rag_classifier.py`
and the v1 graduated example at
`api/functions/graphs/executors/agents/agent_fleet_travel_preapproval_policy_fit_check.py`.

The pattern:

```python
from api.server.mcp_tools.<tool_a> import <tool_a>_tool
# … one per tool the skill's allowed-tools needs

from ._wrapper import SKILLS_DIR, run_agent_session

_SKILL_DIR = SKILLS_DIR / "<domain>-<phase>"


async def execute(input: dict) -> dict:
    workflow_id = input.get("workflow_id")
    <input_extractions>
    prompt = (
        <prompt_lines>
    )
    result = await run_agent_session(
        prompt=prompt,
        tools=[<tool_a>_tool, <tool_b>_tool],
        skill_dir=_SKILL_DIR,
        skill_label="<domain>-<phase>",
        workflow_id=workflow_id,
    )
    return {"<phase>": result}
```

#### `<input_extractions>` — deterministic rules

For each prior-phase output the agent reads (per the brief's
`phase.intent`), emit one line in this exact form:

- If the upstream phase is `kind: deterministic` or `kind: agent`: the
  upstream produces a dict under its phase name. Extract with default:
  ```python
  <upstream_phase> = input.get("<upstream_phase>") or {}
  ```
- If the source is the original orchestrator payload (e.g. a `trip` /
  `claim` / `candidate` block passed in at orchestration start), extract
  the same way:
  ```python
  trip = input.get("trip") or {}
  ```

Do not extract scalars individually — leave that for the prompt template.

#### `<prompt_lines>` — deterministic rules

The prompt is constructed in **exactly four sections**, in this order:

1. **One sentence stating the action** — mirrors the phase's
   `agent_skill_name`. Example:
   `"Determine policy fit and cost band for the proposed trip below."`

2. **Input lines** — one f-string per upstream variable extracted in
   `<input_extractions>`, naming every field the agent will reason over.
   Use `!r` formatter to show types and quote strings. Example:
   ```python
   f"Trip: origin={trip.get('origin')!r}, destination={trip.get('destination')!r}, "
   f"depart={trip.get('depart_date')!r}, return={trip.get('return_date')!r}.\n"
   f"Employee context: grade={employee_lookup.get('grade')!r}, "
   f"home_market={employee_lookup.get('home_market')!r}.\n\n"
   ```

3. **Tool guidance** — one sentence per `allowed-tools` entry telling the
   agent which tool to call with which inputs. Example:
   ```python
   f"Use `concur_travel_policy_get_policy(grade, market)` to load the "
   f"applicable policy slice. Use `concur_travel_search_search_options"
   f"(origin, destination, depart_date, return_date)` to load booking "
   f"options.\n"
   ```

4. **Closing instruction** — verbatim, every time:
   ```python
   f"Reason about <phase intent in 5–10 words> per your skill spec. "
   f"Return exactly the JSON object specified in your skill instructions "
   f"— no prose, no markdown."
   ```

   The closing instruction is what makes the SDK extraction work
   consistently in the existing two domains. Do not paraphrase. Do not
   add a sixth section.

The v1 graduated
`agent_fleet_travel_preapproval_policy_fit_check.py` is a complete
worked example.

### Step 7 — Write validators

Use `templates/validator.py.tmpl`. Mirror
`validate_classification_schema_node.py`. Each validator returns
`{"ok": True, "<phase>": payload, ...}` or `{"ok": False,
"blocked_reason": "<text>", "<phase>": payload}`. The fields it
guards are determined by the agent skill's stated output JSON schema —
read the `## Output` section of the just-authored agent SKILL.md.

### Step 8 — Write GRADUATION.md and graduate.sh (v3)

In v3, GRADUATION.md is human-readable reference; `graduate.sh` is the
**executable** that mechanically applies all the live-tree edits. The
operator runs `bash graduate.sh` from repo root and gets a working
graduated domain in seconds.

Use the templates at
`docs/superpowers/skills/compose-domain/templates/GRADUATION.md.tmpl`
and `docs/superpowers/skills/compose-domain/templates/graduate.sh.tmpl`.

The `graduate.sh` script must perform these idempotent steps in order
(each step a no-op if the change is already present):

1. **Validate prereqs.** Run from repo root; check `git status` shows
   no uncommitted edits to the files that will be patched (so any
   failure is a clean rollback target). Confirm Azurite, Functions
   host, FastAPI are running OR explicitly skip the smoke step.
2. **Copy sandbox files.** All paths under `api/server/skills/<domain>-*`,
   `api/server/personae/<role>/`, `api/server/mcp_tools/<new>.py`,
   `api/functions/workflows/<domain>{,_activities}.py`,
   `api/functions/graphs/<domain>_*.py`,
   `api/functions/graphs/executors/agents/agent_<domain>_*.py`,
   `api/functions/graphs/executors/validators/validate_<domain>_*.py`.
   Idempotent: `cp -n` if file already there with same content,
   else fail loudly.
3. **Patch `function_app.py`.** Append the orchestrator-import block
   between `# === BEGIN compose-domain imports ===` and
   `# === END compose-domain imports ===` markers (idempotent: if the
   block for this domain is already present, skip). Append the
   `@app.orchestration_trigger`-decorated def. Append the activity
   triggers.
4. **Patch `api/functions/graphs/__init__.py`.** Append the
   `from .<domain>_<phase> import build_<domain>_<phase>_workflow`
   exports (idempotent: skip if already imported).
5. **Patch `api/server/services/simulator_orchestrator.py`.** Append
   the `spawn_<domain>_workflow` helper. Add `<domain>` to the
   `spawners` dict in `ramp_loop` so the autonomous ramp picks it up.
   v3 omits `app_state.store.upsert_workflow(w)` per substrate-fix.
6. **Patch `api/server/routes/simulator.py`.** Add the
   `class <Domain>Body(BaseModel)` and the
   `@router.post("/<domain>")` handler.
7. **Patch `api/server/services/blueprint_inventory.py`.** Append a new
   `DOMAINS` dict entry **before** the first `aspirational` one. v3
   contract: include `workflow_type`, `skills`, `phase_aliases`.
8. **Patch `api/shared/constants.py`.** Append the `<PHASE>_TIMEOUT`
   constants. Update the orchestrator file (already in real tree by
   step 2) to import from constants and remove its local timedelta
   declarations.
9. **Print smoke commands** + expected event sequence at end. Do NOT
   run the smoke automatically — the operator runs it after sanity-
   checking the graduated tree.

Every patch step uses `git diff` markers or unique anchor strings so
repeated runs are no-ops. If any step fails the script aborts loudly
and prints the rollback command (`git checkout -- <files>`).

The GRADUATION.md describes (in human-readable form) what each step
does and lists the rollback procedure. The operator reads it before
running `graduate.sh` to know what's about to happen.

### Step 9 — Self-check (v3)

- Every **non-HITL** phase from the brief has exactly one graph file
  and one activity. HITL phases have neither (the orchestrator does
  the wait directly).
- Every agent phase has exactly one agent executor and one validator.
- The orchestrator reads `workflow_type` from `input_dict.get("type")`
  ONCE at the top, then stamps it on EVERY `checkpoint_activity_trigger`
  payload (including suspended, resumed, workflow.completed,
  workflow.started). Without this, recordings break.
- Every HITL phase emits a `wait_for_external_event` paired with a
  `create_timer`. The suspended payload stamps the v3 contract:
  `persona`, `external_event`, `context`. Without these, the persona
  responder ignores the gate and the workflow stalls.
- Convention: external event name is `<phase_name>_decision` (or the
  brief's explicit override), byte-identical between the orchestrator
  and the persona SKILL.md frontmatter.
- The activity functions all use `_run_workflow` from
  `api.functions.workflows.activities`.
- Both `GRADUATION.md` AND `graduate.sh` exist at the sandbox root.
- `graduate.sh` is `chmod +x` and idempotent (re-running is a no-op).
- `graduate.sh` adds the new domain to `ramp_loop`'s `spawners` dict,
  so the autonomous ramp picks it up after graduation.
- No `TODO` placeholder remains.

If any check fails, fix in place; if you can't, stop.

## Anti-patterns

- Adding new `FleetEventType` values for the new domain. v1 reuses the
  existing `durable.*`, `workflow.*` types. Domain-specific event types
  come later, after the procedure stabilises.
- Editing `function_app.py` directly. Never. The diff goes in
  GRADUATION.md.
- Skipping the validator on agent phases. The harness expects them; the
  validator is the bounded-probabilism edge.
- Using `async def <phase>_activity(...)` — Azure Durable Functions
  Python doesn't natively support async activities. The activity wraps
  `asyncio.run(_run_workflow(...))`. Read `activities.py` again if
  unsure.
- Inventing executor kinds beyond `deterministic | agent | validator`.
  The Observatory only knows those three.
- Wiring the orchestrator to a tool import directly. Tools are referenced
  only by the agent executor (`tools=[<tool>_tool]`), and only by name
  (string) in the SKILL.md `allowed-tools` frontmatter. The orchestrator
  knows nothing about tools.
