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

- [ ] §1.1  `tools/scratch/compose-domain/<run-id>/` exists.
- [ ] §1.2  `<run-id>/api/server/skills/<domain>-<phase>/SKILL.md` exists for every phase with `kind: agent`.
- [ ] §1.3  `<run-id>/api/server/personae/<role>/SKILL.md` exists for every phase with `kind: hitl`.
- [ ] §1.4  `<run-id>/api/server/mcp_tools/<tool>.py` exists for every `external_systems[].mcp_tool` not already present in the real `api/server/mcp_tools/`.
- [ ] §1.5  `<run-id>/api/functions/workflows/<domain>.py` exists.
- [ ] §1.6  `<run-id>/api/functions/workflows/<domain>_activities.py` exists.
- [ ] §1.7  `<run-id>/api/functions/graphs/<domain>_<phase>.py` exists for every phase.
- [ ] §1.8  `<run-id>/api/functions/graphs/executors/agents/agent_<domain>_<phase>.py` exists for every agent phase.
- [ ] §1.9  `<run-id>/api/functions/graphs/executors/validators/validate_<domain>_<phase>.py` exists for every agent phase.
- [ ] §1.10 `<run-id>/GRADUATION.md` exists.
- [ ] §1.11 `<run-id>/REPORT.md` exists (this file is written last).

## §2 — Brief integrity

- [ ] §2.1  The brief's `domain.name` starts with `fleet-`.
- [ ] §2.2  Every phase listed in the orchestrator appears in the brief in the same order.
- [ ] §2.3  Every persona referenced by a HITL phase appears in `personae`.
- [ ] §2.4  Every `external_systems[]` id referenced by any phase is defined.

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
- [ ] §4.4  Agent executors mirror `agent_rag_classifier.py`: `from ._wrapper import SKILLS_DIR, run_agent_session`, `_SKILL_DIR = SKILLS_DIR / "<skill-name>"`, `await run_agent_session(...)`.
- [ ] §4.5  Validators return `{"ok": bool, ...}` — never raise on shape errors at the in-graph layer.
- [ ] §4.6  MCP tool stubs use `@traced_tool(...)` and `@define_tool(...)` decorators; Pydantic params class is `_<Op>Params(BaseModel)`.
- [ ] §4.7  MCP tool stubs are pure (no `time`, no `random`, no `os.environ`, no network). Same input → byte-identical output.

## §5 — Frontmatter and content quality

- [ ] §5.1  Every SKILL.md frontmatter parses as YAML.
- [ ] §5.2  Every SKILL.md body has the required sections for its mode (`## Inputs / ## Procedure / ## Output` for phase agents; `## Decision policy / ## Procedure` for personae).
- [ ] §5.3  No file in the sandbox contains a `TODO`, `FIXME`, `XXX`, `<placeholder>`, or `…` left over from a template slot.
- [ ] §5.4  No file contains the words "AI-powered", "leverage", "synergy", or any equivalent marketing register.

## §6 — Determinism

- [ ] §6.1  Re-running `compose-domain` against the same brief produces a sandbox whose tree differs only in the `<run-id>` timestamp. (This check is performed across two consecutive runs — the operator confirms by `diff -r` of the two `<run-id>/` directories minus the timestamp directory name.)

## §7 — GRADUATION.md completeness

- [ ] §7.1  Lists every file in §1 with target real-tree path.
- [ ] §7.2  Provides the literal `function_app.py` diff (orchestration trigger + activity triggers + imports).
- [ ] §7.3  Provides the literal `api/functions/workflows/activities.py` diff (imports + activity functions).
- [ ] §7.4  Provides the literal `api/functions/graphs/__init__.py` diff (`build_<...>` exports).
- [ ] §7.5  Provides the literal `api/server/services/simulator_orchestrator.py` diff (`spawn_<domain>_workflow`).
- [ ] §7.6  Provides the literal `api/server/services/blueprint_inventory.py` diff (`DOMAINS` entry).
- [ ] §7.7  Provides the literal `api/shared/constants.py` diff (`<PHASE>_TIMEOUT` constants).
- [ ] §7.8  Lists smoke commands and expected FleetEvent sequence.

---

## Graduation (separate, manual, after the run ends)

The skill never graduates. The engineer does. Steps:

1. Read `<run-id>/REPORT.md` end-to-end. Every item PASS or N/A.
2. Read `<run-id>/GRADUATION.md`.
3. Copy files from `<run-id>/api/...` into the real `api/...` tree per the
   §1 table.
4. Apply each `function_app.py` / `activities.py` / `__init__.py` /
   `simulator_orchestrator.py` / `blueprint_inventory.py` /
   `constants.py` diff by hand. Each diff is shown literally — no
   interpretation needed.
5. Run `make test`. The existing tests must still pass.
6. Run the smoke command from §7.8. Watch the FleetEvent sequence on
   `/api/blueprint/stream` (or the existing observatory). The expected
   sequence appears in the GRADUATION.md.
7. If the smoke fails, the bug is in the SKILL.md, not in the graduated
   files. Revert the graduation, fix the SKILL.md, delete the sandbox,
   re-invoke. Re-graduate.
