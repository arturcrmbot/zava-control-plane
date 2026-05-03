# Compose-Domain Meta-Skill — Design

**Date:** 2026-05-03
**Owner:** Artur Zielinski
**Audience:** internal — the engineer running the meta-skill (initially this Copilot session, eventually a runtime author).
**Sister artefacts:** [blueprint.md](../../blueprint.md) (the thesis the skill is the proof of) · [blueprint-microsite-design.md](2026-05-03-blueprint-microsite-design.md) (where the runtime version of this skill ends up shipped as `skill-author` / `mcp-author`).

---

## 1. Why this exists

The blueprint thesis claims the case of type extends itself: skills written
by skills, MCPs written by skills, new domains composed in hours rather than
weeks. The two mature domains (`expense-claim`, `hiring`) were written by
hand. To make the claim true rather than aspirational, we need a procedural
skill that, given a brief, produces a complete working domain — orchestrator,
graphs, validators, agent skills, MCP tools, persona, registration — in the
same shape as the two that already exist.

The point of this first build is **the procedure, not the output**. We pick
one journey as a test rig, run the skill on it, watch where the procedure is
sloppy, fix the skill, re-run. The goal is a skill that is reproducible:
running it twice on the same brief produces byte-identical output (modulo a
run-id), and changing one bullet in the brief changes only what that bullet
implies.

## 2. Scope of v1

**In scope.**
- A composed meta-skill that authors a complete Durable-fidelity domain.
- One sub-skill per artefact category (runtime skill, MCP tool, Durable
  domain).
- Sandbox-tree output. No mutation of the real trees.
- A manual graduation checklist (a doc) that an engineer follows to move a
  satisfactory sandbox into the real trees.
- One test-rig brief: **Holiday booking & cover** — 3 phases, 1 HITL,
  2 MCPs, 1 persona.

**Out of scope (v1).**
- Automated graduation. The script that lifts a sandbox into the real trees
  comes after the procedure is stable.
- A runtime version that runs inside the customer environment with allow-
  listed write permissions. That is the `skill-author` / `mcp-author` shape
  in the microsite section 6, scoped as a separate engagement.
- Agentic personae beyond the one the test rig needs.
- Editing `function_app.py`, `simulator_orchestrator.py`, the synthetic-data
  generator, or the inventory manifest. These happen at graduation time, by
  hand, against a checklist.

## 3. Where the skill lives, and where it doesn't

The meta-skill and its sub-skills live in the **repo**, under
`docs/superpowers/skills/`. This is consistent with the existing convention
(`docs/superpowers/specs/`, `docs/superpowers/plans/`).

A directory-level `README.md` explicitly marks the contents as
**design-time only**. The runtime GHCP SDK reads only `api/server/skills/`
(see [`api/functions/graphs/executors/agents/_wrapper.py`](../../api/functions/graphs/executors/agents/_wrapper.py)
which sets `_SKILLS_DIR = …/server/skills`). Anything under
`docs/superpowers/skills/` is invisible to runtime sessions by construction.
The README repeats this fact and forbids any process from copying these
SKILL.md files into `api/server/skills/`.

## 4. Skill structure

```
docs/superpowers/skills/
  README.md                       — design-time-only marker
  compose-domain/
    SKILL.md                      — the orchestrator skill (entry point)
    CHECKLIST.md                  — the artefact list every run must produce
    templates/                    — Jinja-ish skeletons sub-skills fill
      SKILL.md.tmpl
      mcp_tool.py.tmpl
      orchestrator.py.tmpl
      activity.py.tmpl
      phase_graph.py.tmpl
      agent_executor.py.tmpl
      validator.py.tmpl
      persona_SKILL.md.tmpl
      synthetic_brief.yaml.tmpl
  author-runtime-skill/
    SKILL.md                      — writes one SKILL.md (phase or persona)
  author-mcp-tool/
    SKILL.md                      — writes one in-process MCP tool stub
  author-durable-domain/
    SKILL.md                      — writes orchestrator + activities + per-phase
                                    MAF graphs + validators
```

The split is along **artefact category**, not phase. Each sub-skill produces
one well-bounded category of file. The orchestrator skill (`compose-domain`)
reads the brief, produces an internal plan, then calls each sub-skill the
right number of times in the right order.

## 5. The procedure (high level)

`compose-domain` runs in five steps:

1. **Brief intake.** If invoked with a free-text idea, hand off to the
   existing `brainstorming` skill to elicit a structured YAML brief; write
   it to `docs/superpowers/specs/<domain>-brief.yaml`. If invoked with a
   YAML brief path, skip to step 2.
2. **Plan.** From the brief, derive the artefact list:
   - one runtime SKILL.md per phase that has an `agent` step
   - one persona SKILL.md per HITL gate
   - one MCP tool stub per `external_systems[]` entry not already present
     in `api/server/mcp_tools/`
   - the orchestrator file, one activity per phase, one MAF graph per phase,
     validators per agent step
   - one synthetic-data generator stub
   - one simulator entry-point stub
3. **Inventory + isomorphism.** Read every comparable existing artefact
   (`receipt-validator/SKILL.md`, `claim_lookup.py`, `expense_claim.py`,
   `classify.py`, `validate_classification_schema_node.py`, etc.) and bind
   them to template slots. The new artefacts are shape-isomorphic to
   what's already in the repo; deviation is the bug.
4. **Generate into sandbox.** Call each sub-skill once per planned artefact.
   Output goes to `tools/scratch/compose-domain/<run-id>/`. Each sub-skill
   reads only the brief, the relevant template, and the relevant existing
   examples — no implicit context.
5. **Self-check.** Run the CHECKLIST against the sandbox: every required
   file present, every cross-reference resolves (e.g. each agent skill's
   `allowed-tools` lists tools that exist in the sandbox or the real
   `api/server/mcp_tools/`), every template slot filled, no `TODO`
   placeholders left. Emit a one-page report. Stop. Do not graduate.

Graduation is a separate, manual step against
`compose-domain/CHECKLIST.md` §"Graduation". The engineer reviews the
sandbox, copies files into the real trees, patches `function_app.py`,
`simulator_orchestrator.py`, `blueprint_inventory.py`, and reruns the
existing smoke tests.

## 6. Sandbox tree

`tools/scratch/compose-domain/<YYYYMMDD-HHMMSS>-<domain>/` is gitignored.
Each invocation gets its own snapshot. We can keep multiple side-by-side
runs and diff them — the procedure-quality bar is that two runs against
the same brief diff to nothing meaningful.

The sandbox layout mirrors the real-tree layout exactly so graduation is
copy-paste rather than path-translate:

```
tools/scratch/compose-domain/20260503-141500-fleet-holiday/
  api/server/skills/<skill-name>/SKILL.md           — runtime skills
  api/server/personae/<role>/SKILL.md               — personae (new tree)
  api/server/mcp_tools/<tool>.py                    — MCP tool stubs
  api/functions/workflows/<domain>.py               — orchestrator
  api/functions/workflows/<domain>_activities.py    — activities
  api/functions/graphs/<phase>.py                   — per-phase MAF graphs
  api/functions/graphs/executors/agents/agent_<name>.py
  api/functions/graphs/executors/validators/validate_<name>.py
  api/server/services/synthetic_data_<domain>.py    — synthetic generator
  api/server/services/simulator_<domain>.py         — simulator entry point
  GRADUATION.md                                     — diffs for function_app.py
                                                      and any other files the
                                                      engineer must hand-edit
```

## 7. Brief schema

```yaml
# docs/superpowers/specs/<domain>-brief.yaml
domain:
  name: fleet-holiday                     # used as folder/file prefix
  display_name: Holiday booking & cover
  owner_role: line_manager                # the dominant persona
  description: |
    A short paragraph explaining the journey at a level a senior
    engineer would write on a whiteboard.

phases:
  - name: entitlement_check
    intent: read leave balance and forecast remaining at year-end
    kind: deterministic                   # deterministic | agent
    external_systems: [workday_hr]
    hitl: false
  - name: cover_plan_draft
    intent: propose a cover plan (named delegate per impacted day)
    kind: agent
    external_systems: [graph_calendar]
    hitl: false
    agent_skill_name: cover-planner
  - name: manager_approval
    intent: line manager approves or rejects the request
    kind: hitl
    external_systems: []
    hitl: true
    persona: line_manager

personae:
  - role: line_manager
    decision_policy: |
      Approve if remaining entitlement >= 0 after this booking AND a
      cover plan exists. Otherwise reject with a one-sentence reason.

external_systems:
  - id: workday_hr
    mcp_tool: workday_hr_leave_balance
    operations: [get_leave_balance, get_team_calendar]
  - id: graph_calendar
    mcp_tool: graph_team_availability
    operations: [list_team_busy]
```

The schema is small on purpose. Every field maps to a template slot. The
brief should not require domain knowledge to fill in — only the journey.

## 8. Iteration loop

```
1. write/edit docs/superpowers/specs/<domain>-brief.yaml
2. invoke compose-domain (this Copilot session)
3. inspect tools/scratch/compose-domain/<run-id>/ + the report
4. find one thing the skill should have done better
5. edit docs/superpowers/skills/compose-domain/ (or a sub-skill)
6. delete the sandbox run, GOTO 2
```

The loop is over **the SKILL.md**, not the holiday domain. The holiday
domain is the test rig.

## 9. Graduation discipline (v1)

Manual. The engineer:

1. Copies sandbox files into the real trees.
2. Hand-edits `function_app.py` per the GRADUATION.md emitted by the run.
3. Hand-edits `api/server/services/simulator_orchestrator.py` per the
   GRADUATION.md.
4. Hand-edits `api/server/services/blueprint_inventory.py` to add the new
   domain to the manifest.
5. Runs `make test` and the existing e2e smoke.
6. Fires the new simulator entry point and watches FleetEvents on
   `/api/blueprint/stream`.

If anything fails at graduation that the SKILL.md should have prevented, the
fix goes into the SKILL.md, not into the graduated files. Then re-graduate.

A small Python script that automates steps 1–4 is a natural follow-on; it is
deliberately out of v1 scope so the SKILL.md gets exercised against the full
manual surface first.

## 10. Done criteria for v1

- The four SKILL.md files exist under `docs/superpowers/skills/`.
- The templates exist and all expected slots are documented in the
  CHECKLIST.
- The sandbox path exists and is gitignored.
- The brief for the holiday test rig is committed.
- Running `compose-domain` against the brief produces a complete sandbox
  with the CHECKLIST passing.
- Running it twice produces byte-identical sandbox content.
- The procedure-quality bar above is met.

This spec stops here. The graduated holiday domain, the constellation
visual, and the multi-domain simulator are all separate plans, scoped after
this one closes.
