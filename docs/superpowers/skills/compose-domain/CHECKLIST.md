# compose-domain CHECKLIST

The self-check `compose-domain/SKILL.md` step 5 runs against this list.
Each item is **PASS / FAIL / N/A**. The skill writes the verdicts to
`<run-id>/REPORT.md` and prints them inline.

If anything FAILs, the right move is almost always to fix the SKILL.md
that produced the failure (`compose-domain/SKILL.md` or one of the
sub-skills), then delete the sandbox and re-invoke. Do not silently fix
in the sandbox — that hides the procedure bug.

---

## §1 — Sandbox layout

- [ ] §1.0  The run records its target vertical; graduation destinations are under `verticals/<vertical>/` for business assets.
- [ ] §1.1  `tools/scratch/compose-domain/<run-id>/` exists.
- [ ] §1.2  `<run-id>/api/server/skills/<domain>-<phase>/SKILL.md` exists for every phase with `kind: agent`.
- [ ] §1.3  `<run-id>/api/server/personae/<role>/SKILL.md` exists for every phase with `kind: hitl`.
- [ ] §1.4  `<run-id>/api/server/mcp_tools/<tool>.py` exists for every `external_systems[].mcp_tool` not already present in the real `api/server/mcp_tools/`.
- [ ] §1.5  `<run-id>/api/functions/workflows/<domain>.py` exists.
- [ ] §1.6  `<run-id>/api/functions/workflows/<domain>_activities.py` exists.
- [ ] §1.7  `<run-id>/api/functions/graphs/<domain>_<phase>.py` exists for every **non-HITL** phase. (HITL phases have no graph — the orchestrator does the wait directly, mirroring `expense_claim.py`.)
- [ ] §1.8  `<run-id>/api/functions/graphs/executors/agents/agent_<domain>_<phase>.py` exists for every agent phase.
- [ ] §1.9  `<run-id>/api/functions/graphs/executors/validators/validate_<domain>_<phase>.py` exists for every agent phase.
- [ ] §1.10 `<run-id>/GRADUATION.md` exists (human-readable reference).
- [ ] §1.11 `<run-id>/graduate.sh` exists, is `chmod +x`, and runs without args.
- [ ] §1.12 `<run-id>/REPORT.md` exists (this file is written last).

## §2 — Brief integrity

- [ ] §2.1  The brief's `domain.workflow_type` matches `^[a-z][a-z0-9-]*$` and is **not** already in the selected pack's domains (`active_runtime().pack.domains`).
- [ ] §2.2  Every phase listed in the orchestrator appears in the brief in the same order.
- [ ] §2.3  Every persona referenced by a HITL phase appears in `personae` (or already lives under `api/server/personae/`).
- [ ] §2.4  Every `external_systems[]` id referenced by any phase is defined.
- [ ] §2.5  Every persona has both `decision_policy` (prose paragraph) AND `decision_code` (Python source) in the brief. (NEW v3.)
- [ ] §2.6  `domain.prefix` matches `^[a-z][a-z0-9_]*$` (used for orchestrator/activities file names; almost always `fleet`). (NEW v4.)

## §3 — Cross-references

- [ ] §3.1  Every runtime SKILL.md's `name` frontmatter matches its leaf folder name.
- [ ] §3.2  Every runtime SKILL.md's `allowed-tools` is a CSV (no YAML list form).
- [ ] §3.3  Every entry in every `allowed-tools` resolves to either a tool defined in the sandbox or a tool present in the real `api/server/mcp_tools/`.
- [ ] §3.4  Every agent executor imports the tools it passes to `tools=[…]` from the matching path (sandbox or real tree).
- [ ] §3.5  The orchestrator's `wait_for_external_event` event names match the persona SKILL.md's documented output event for each HITL phase.
- [ ] §3.6  Every activity name registered in GRADUATION.md (`<phase>_activity_trigger`) appears in the orchestrator's `call_activity(...)` calls.

## §4 — Shape isomorphism

- [ ] §4.1  Orchestrator file imports `from collections.abc import Generator` and `from typing import Any` and `import azure.durable_functions as df`. Mirrors `expense_claim.py`.
- [ ] §4.2  Activities module uses `_run_workflow` imported from `api.functions.workflows.activities` (does not redefine it).
- [ ] §4.3  Per-phase graphs build `WorkflowBuilder(start_executor=n1).add_edge(...)…build()` exactly like `classify.py`.
- [ ] §4.4  Agent executors mirror `agent_rag_classifier.py`: `from ._wrapper import SKILLS_DIR, run_agent_session`, `_SKILL_DIR = SKILLS_DIR / "<skill-name>"`, `await run_agent_session(...)`. Segment and legacy graph-agent templates forward both canonical `workflow_id=input.get("workflow_id")` and real orchestration `instance_id=input.get("instance_id")`.
- [ ] §4.5  Validators return `{"ok": bool, ...}` — never raise on shape errors at the in-graph layer.
- [ ] §4.6  MCP tool stubs use `@traced_tool(...)` and `@define_tool(...)` decorators; Pydantic params class is `_<Op>Params(BaseModel)`.
- [ ] §4.7  MCP tool stubs are pure (no `time`, no `random`, no `os.environ`, no network). Same input → byte-identical output.

## §5 — Frontmatter and content quality

- [ ] §5.1  Every SKILL.md frontmatter parses as YAML.
- [ ] §5.2  Every SKILL.md body has the required sections for its mode (`## Inputs / ## Procedure / ## Output` for phase agents; `## Decision policy / ## Procedure` for personae).
- [ ] §5.3  No file in the sandbox contains a `TODO`, `FIXME`, `XXX`, `<placeholder>`, or `…` left over from a template slot.
- [ ] §5.4  No file contains the words "AI-powered", "leverage", "synergy", or any equivalent marketing register.
- [ ] §5.5  Every persona SKILL.md frontmatter contains `decision_policy` (executable Python), `external_event`, `workflow_label`. (NEW v3.)
- [ ] §5.6  Persona `decision_policy` source uses only safe builtins per `api/server/services/persona_responder.py:_DECISION_BUILTINS` — no `import`, `open`, `os`, `subprocess`, `eval`, `__import__`. Verified by grep. (NEW v3.)

## §6 — Determinism

- [ ] §6.1  Re-running `compose-domain` against the same brief produces a sandbox whose tree differs only in the `<run-id>` timestamp directory name and the `REPORT.md` timestamp line. Verified by:

      diff -r --brief \
        tools/scratch/compose-domain/<run-id-1>/ \
        tools/scratch/compose-domain/<run-id-2>/

  Differences allowed: the top-level `<run-id>` folder name, the
  `Generated <ts>` line in `REPORT.md` and `GRADUATION.md`. Anything else
  is a determinism failure — the divergence points are exactly the parts
  of the SKILLs that gave the author freedom. Codify those parts.

- [ ] §6.2  HITL convention: every HITL phase's `wait_for_external_event`
  name in the orchestrator equals the persona SKILL.md's `external_event`
  frontmatter field, byte-identical. Verified by
  `grep -E 'wait_for_external_event' <run-id>/api/functions/workflows/*.py`
  and `grep -E '^external_event:' <run-id>/api/server/personae/*/SKILL.md`.

- [ ] §6.3  v3 substrate-fix contract: orchestrator stamps `workflow_type`
  on EVERY checkpoint payload (workflow.started, every suspended, every
  resumed, workflow.completed). Verified by
  `grep -c '"workflow_type":' <run-id>/api/functions/workflows/<domain>.py`
  — must be at least `(2 * num_hitl_phases) + 2`.

- [ ] §6.4  v3 persona contract: every HITL `suspended` payload stamps
  `persona`, `external_event`, `context`. Verified by
  `grep -A 6 '"kind": "suspended"' <run-id>/api/functions/workflows/<domain>.py`
  showing all three fields.

## §7 — GRADUATION.md + graduate.sh completeness

- [ ] §7.1  GRADUATION.md lists every file in §1 with target real-tree path.
- [ ] §7.2  graduate.sh exists at the sandbox root, is executable.
- [ ] §7.3  graduate.sh registers the orchestrator and activities on the selected pack's `durable.py` (BEGIN/END sentinel guards).
- [ ] §7.4  graduate.sh exports graph builders into `api/functions/graphs/__init__.py` (build_* exports; sentinel-guarded).
- [ ] §7.5  graduate.sh registers the spawn helper on the selected pack's `spawners.py` (BEGIN/END sentinel guards). Never patches a global service module.
- [ ] §7.6  graduate.sh registers the domain declaration on the selected pack's `domains.py` (BEGIN/END sentinel guards).
- [ ] §7.7  graduate.sh registers function membership on the selected pack's `functions.py` (BEGIN/END sentinel guards). Global compatibility adapters and Blueprint inventory are never patched.
- [ ] §7.8  graduate.sh validates the active pack: `active_runtime().pack.domains` must include the new `workflow_type`; step exits non-zero otherwise.
- [ ] §7.9  graduate.sh prints smoke commands at the end.
- [ ] §7.10 graduate.sh is idempotent: re-running on an already-graduated tree is a no-op (each step checks its sentinel before appending).
- [ ] §7.11 GRADUATION.md §Rollback lists every file/path graduate.sh touched.

---

## Graduation (mechanical, post-self-check)

Graduation is one command: `bash <run-id>/graduate.sh` from repo root.
The script applies all six pack-scoped steps idempotently:

1. Read `<run-id>/REPORT.md` end-to-end. Every item PASS or N/A.
2. Read `<run-id>/GRADUATION.md` (so you know what graduate.sh will do).
3. Run `bash <run-id>/graduate.sh` from repo root.
4. Restart FastAPI with `ZAVA_VERTICAL=<vertical>`.
5. Run the smoke command graduate.sh prints. Confirm `active_runtime().pack.domains`
   includes the new workflow_type.
6. Collect evidence required by `docs/VERTICAL-PROOF.md`; commit recorded walks.

## §8 — Entity projection (v4)

- [ ] §8.1  `<run-id>/api/server/services/entity_projections/<workflow_type_snake>.py` exists.
- [ ] §8.2  Module imports compile (no SyntaxError).
- [ ] §8.3  Exposes module-level `WORKFLOW_TYPE = "<workflow_type>"` and a bare `def project(workflow)` callable (Phase 1 PAT-005).
- [ ] §8.4  Imports limited to `api.server.services.entity_projections` (DecisionWrite/EntityWrite/RelWrite/build_decision/slug) + `api.shared.types` (Workflow).
- [ ] §8.5  Every entity `kind` is in `_VALID_KINDS` (Phase 1 schema source-of-truth).
- [ ] §8.6  Every relation `kind` is in `_VALID_RELS`.

## §9 — Decision mapping (v4)

- [ ] §9.1  One `<run-id>/api/server/services/precedent_queries/<workflow_type>_<phase>.cypher` per HITL phase listed under `decisions:`.
- [ ] §9.2  Each Cypher MATCHes on the dedupe triple via persona_role + workflow_type, ORDERed by `decided_at DESC`, LIMITed by `$limit`.
- [ ] §9.3  Persona names referenced under `decisions[].persona` resolve to a folder in `api/server/personae/`.
- [ ] §9.4  No two decisions name the same phase (one decision per HITL phase).

## §10 — Function membership (v4)

- [ ] §10.1 `brief.function` is one of the 10 canonical keys (`finance`, `hr`, `revenue`, `ops`, `legal`, `marketing`, `tech`, `data`, `customer-success`, `legacy`).
- [ ] §10.2 graduate.sh step 5 registers the `workflow_type` in the selected pack's `verticals/<vertical>/functions.py`, appending to `FUNCTIONS["<fn>"].owns_domains`. The registration block is wrapped in sentinel comments `# === BEGIN compose-domain <workflow_type> ===` and `# === END compose-domain <workflow_type> ===`, guarded by grep `BEGIN compose-domain $MARKER` (idempotent re-runs). The global `api/shared/functions.py` is a read-only active-pack adapter and is never modified.
- [ ] §10.3 Sentinel comments in `verticals/<vertical>/functions.py` follow the exact format `# === BEGIN compose-domain <workflow_type> ===` and matching END. These guard against duplicate registration on re-runs.
- [ ] §10.4 The workflow_type is not also claimed by a *different* function in the registry (orphan/dup check by author-function-membership validator).

## §11 — Ambient trigger (v4, optional)

- [ ] §11.1 If `ambient:` block is present, `<run-id>/api/server/services/ambient_agents/<function>.py` is appended (or created) with the rendered `AmbientAgent(...)` constructor.
- [ ] §11.2 The constructor block is wrapped in sentinel comments `# compose-domain:ambient:<workflow_type> BEGIN/END` so re-runs are idempotent.
- [ ] §11.3 The constructor is guarded by `if hasattr(_module, "AmbientAgent"):` so the file imports cleanly before Phase 3 lands the primitive.
- [ ] §11.4 `ambient.function` matches `brief.function`.
- [ ] §11.5 Each trigger entry sets exactly one of `bus | cypher | cadence` and supplies the kind-specific keys.
- [ ] §11.6 Every `spawnable_workflow_types` entry is in the selected pack's domains (`active_runtime().pack.domains`) OR equals the brief's own `workflow_type` (self-spawn forward-declaration).

## §12 — Live demo runtime gates

- [ ] §12.1 Every HITL action/category/value emitted by the workflow matches a
  real governance authority matrix rule. Run
  `kernel().check_authority(role=..., action=..., category=..., value=...)`
  with representative live context and require `allowed=True`.
- [ ] §12.2 With `PERSONA_AUTO_CLOSE=*`, trigger each HITL path and require
  `persona.decided`, `durable.resumed`, and a terminal workflow status within
  15 seconds. No workflow may remain in `awaiting_hitl`.
- [ ] §12.3 While suspended, `GET /api/workflows/<id>` exposes
  `payload.hitl_context` containing `persona`, `external_event`, `phase`, and
  decision context. Invoke `POST /api/personas/sweep` and prove the same gate
  can be reconstructed if its original bus event is missed.
- [ ] §12.4 Keep the world page mounted while the backend journal is reset or
  restarted. When `/api/world/events` reports `latest_seq` below the client's
  cursor, the client must clear stale events, retry with `after=0`, and display
  new events without a page reload.
- [ ] §12.5 For every named demo scenario, measure click-to-first-visible event
  at the browser. It must be at most one second; API success without visible UI
  evidence is a failure.

## §13 — Blocking execution-visibility gate

Actual execution evidence must be visible and self-consistent. For every active
non-stub workflow type, inspect at least one instance:

- [ ] §13.1 Its timeline is non-empty, with exactly one `workflow.started` row
  and one terminal lifecycle row matching the final status.
- [ ] §13.2 Observed phase rows are non-empty and name only declared domain
  phases. Conditional branches may omit phases. Terminal workflows leave any
  observed phase rows terminal or explicitly skipped.
- [ ] §13.3 Canonical `agent.completed` reasoning rows, when present, carry
  stable run identity, completion time, and declared phase provenance. A domain
  declaring agent/graph work needs at least one such row total.
- [ ] §13.4 Validate only tool calls that occurred. Reasoning tool IDs,
  canonical `mcpCalls`, and Tool timeline rows match exactly, including
  persistent ID, `request`, `response`, `statusCode`, and `durationMs`.
- [ ] §13.5 Observed HITL decisions carry a persona, verdict, and reason; the
  persona resolves in the active pack. Observed lineage, deterministic output,
  errors, and retries are shape-valid.
- [ ] §13.6 Live and replay source modes expose the same user-visible detail.

Generated agent/LLM code uses `run_agent_session`; direct uninstrumented model
calls remain a hard failure. Do not fabricate evidence to satisfy this gate.

After all live workflows are terminal, capture and check every instance:

```bash
ZAVA_VERTICAL=<vertical> .venv/bin/python tools/workflow_visibility_proof.py \
  --vertical <vertical> --base-url http://localhost:3101 \
  --save-dir proof/workflow-details/live
```

Switch to replay, then capture the same full workflow-ID set and compare:

```bash
ZAVA_VERTICAL=<vertical> .venv/bin/python tools/workflow_visibility_proof.py \
  --vertical <vertical> --base-url http://localhost:3101 \
  --compare-dir proof/workflow-details/live \
  --save-dir proof/workflow-details/replay
```

For offline proof, use `--details-dir proof/workflow-details/replay` instead of
`--base-url`. Keep ignored `proof/` snapshots local; they may contain workflow
payloads.
