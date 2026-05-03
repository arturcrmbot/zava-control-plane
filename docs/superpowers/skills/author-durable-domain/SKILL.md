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

Use `templates/agent_executor.py.tmpl`. Mirror `agent_rag_classifier.py`:

```python
from api.server.mcp_tools.<tool_a> import <tool_a>_tool
# … one per tool the skill's allowed-tools needs

from ._wrapper import SKILLS_DIR, run_agent_session

_SKILL_DIR = SKILLS_DIR / "<domain>-<phase>"

async def execute(input: dict) -> dict:
    workflow_id = input.get("workflow_id")
    prompt = (
        f"<one-paragraph instruction that names the inputs the skill should "
        f"call its tools with, and tells it to return JSON conforming to "
        f"its skill spec — no prose, no markdown.>"
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

The `prompt` must explicitly name (a) the input fields the skill will
need, drawn from the brief's prior phases' outputs, and (b) the
`allowed-tools` it should use. Mirror `agent_rag_classifier.py`.

### Step 7 — Write validators

Use `templates/validator.py.tmpl`. Mirror
`validate_classification_schema_node.py`. Each validator returns
`{"ok": True, "<phase>": payload, ...}` or `{"ok": False,
"blocked_reason": "<text>", "<phase>": payload}`. The fields it
guards are determined by the agent skill's stated output JSON schema —
read the `## Output` section of the just-authored agent SKILL.md.

### Step 8 — Write GRADUATION.md

Use `templates/GRADUATION.md.tmpl`. The file lists every hand-edit the
engineer must apply at graduation, with copy-pasteable diffs. Sections:

1. **Copy these files** — table of `<sandbox-path> → <real-tree-path>`.
2. **Edit `function_app.py`** — show the literal block of new
   `@app.orchestration_trigger` and `@app.activity_trigger` decorators to
   add. Show the `from api.functions.workflows.<domain> import …` import
   to add at the top.
3. **Edit `api/functions/workflows/activities.py`** — show the new imports
   and the new `def <domain>_<phase>_activity(...)` functions.
4. **Edit `api/functions/graphs/__init__.py`** — show the new
   `build_<domain>_<phase>_workflow` exports.
5. **Edit `api/server/services/simulator_orchestrator.py`** — show the
   new `spawn_<domain>_workflow` helper, mirroring `spawn_hiring_workflow`.
6. **Edit `api/server/services/blueprint_inventory.py`** — show the new
   entry to add to the `DOMAINS` list (`name`, `status: "live"`, `skills`).
7. **Edit `api/shared/constants.py`** — show the `<PHASE>_TIMEOUT`
   constants to lift out of the orchestrator.
8. **Smoke test commands** — `make test`, `curl
   /api/simulator/<domain>` body, expected FleetEvent sequence on
   `/api/blueprint/stream`.

The GRADUATION.md does NOT execute anything. It is a checklist for a
human.

### Step 9 — Self-check

- Every phase from the brief has exactly one graph file and one activity.
- Every agent phase has exactly one agent executor and one validator.
- Every HITL phase emits a `wait_for_external_event` and a paired
  `create_timer`.
- The orchestrator's emit sequence at entry/exit matches `expense_claim.py`.
- The activity functions all use `_run_workflow` from
  `api.functions.workflows.activities`.
- GRADUATION.md mentions every file in the file set.
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
