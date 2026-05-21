# compose-domain v4 + add-domain — findings from `employee-transfer` (2026-05-21)

Author session: ran the `add-domain` skill end-to-end against a "build me an employee-transfer-between-organisations domain" autonomous-mode request, with the user driving verification (boot-demo, Playwright on the Control Plane, AGT authority matrix). The domain shipped fully wired (chip in the UI, ramp spawning, orchestrator progressing through phases, AuthorityCard rendering for international transfers), but only after **13 papercuts** across the skill chain. This file captures every one so we can fix them before the next domain is added.

The findings are grouped by which skill owns the fix:

- [A. compose-domain v4 codegen / templates](#a-compose-domain-v4-codegen--templates)
- [B. graduate.sh idempotent patcher](#b-graduatesh-idempotent-patcher)
- [C. add-domain orchestrator skill](#c-add-domain-orchestrator-skill)
- [D. Surrounding substrate that compose-domain should know about](#d-surrounding-substrate-that-compose-domain-should-know-about)

---

## A. compose-domain v4 codegen / templates

### A1. Spawn helper omits `app_state.store.upsert_workflow(w)` — workflows invisible to the whole control plane

**Severity:** critical. **Stage:** Phase 3 codegen.

The generated spawn helper carried this comment:

> `Note: generated domains do not currently upsert into app_state.store (the existing Workflow / ClaimData / HiringData types are domain-specific). State lives only in Durable + the FleetEvent stream.`

That statement is **false** for every v3 graduated domain. `spawn_fleet_vendor_kyc_workflow`, `spawn_fleet_employee_onboarding_workflow`, `spawn_fleet_it_access_request_workflow`, `spawn_fleet_perf_review_workflow`, `spawn_fleet_ap_invoice_workflow`, etc. all do:

```python
w = build_fleet_<wt>_workflow(wid, record=record)
app_state.store.upsert_workflow(w)
...
result = await schedule_new_orchestration(payload, function_name=...)
w.orchestration_instance_id = result.get("id")
app_state.store.upsert_workflow(w)
```

Without this:

- `GET /api/workflows/<id>` returns 404
- `GET /api/workflows/<id>/orchestration` returns 404
- The Feed UI never sees the workflow (it consumes from `/api/workflows`)
- The AuthorityCard never renders (it needs the Workflow JSON to derive the matrix request)
- HITL routing breaks (resolve route can't look up the workflow)

**Fix:** Update `author-durable-domain` to always emit the upsert pattern. The comment in the template needs to be deleted.

**Citations:** `api/server/services/simulator_orchestrator.py:809-843` (canonical vendor-kyc shape), `api/server/services/simulator_orchestrator.py:1788-1837` (original buggy generated employee-transfer shape, since fixed in this session).

### A2. No matching `build_fleet_<wt>_workflow()` factory in `synthetic_data.py`

**Severity:** critical. **Stage:** Phase 3 codegen. **Coupled to A1.**

The v3 spawn helpers all delegate Workflow construction to a factory in `api/server/services/synthetic_data.py` (e.g. `build_fleet_employee_onboarding_workflow`, `build_fleet_it_access_request_workflow`, `build_fleet_perf_review_workflow`). compose-domain v4 generates the spawn helper but **never** generates the factory.

**Fix:** Either

1. Add a new codegen template `build_fleet_<wt>_workflow.py.tmpl` that emits the factory into `synthetic_data.py` (graduate.sh appends, idempotent via sentinel), or
2. Inline the Workflow construction in the spawn helper itself and drop the factory layer (simpler, but breaks parity with the 8 graduated domains).

Option 1 is more idiomatic. The factory shape is trivial: build a dict of synthesised defaults, return `Workflow(id=..., type=..., current_phase=<first phase Display Name>, created_at=..., sla_due_at=..., jurisdiction="London-Zava", agency="Zava", payload={"<entity_kind>": <dict>, "scenario": r.get("scenario")})`.

**Citations:** `api/server/services/synthetic_data.py:245-267` (build_fleet_employee_onboarding_workflow — the cleanest model), `api/server/services/synthetic_data.py:270-300` (build_fleet_it_access_request_workflow).

### A3. Spawn helper doesn't capture `orchestration_instance_id` on the Workflow

Even if A1 is fixed, the canonical pattern writes the Durable orchestration instance id back onto the Workflow record after scheduling. Without this, the `/api/workflows/<id>/orchestration` route can't correlate the workflow to its Durable history.

**Fix:** Bundled with A1 in the template fix:

```python
result = await schedule_new_orchestration(payload, function_name="<Class>Orchestrator")
w.orchestration_instance_id = result.get("id")
app_state.store.upsert_workflow(w)
```

### A4. HITL `external_event:` defaults collide with shared persona event names

**Severity:** high. **Stage:** Phase 2 brief authoring (autonomous mode).

When a HITL phase reuses an existing persona (`line_manager`, `hr_director`, `hr_bp`, `finance_bp`, etc.), the persona's SKILL.md frontmatter has a **fixed** `external_event:` (e.g. `line_manager` → `manager_approval_decision`; `hr_director` → `hr_director_decision`). The compose-domain convention default `<phase_name>_decision` produces a NEW event name (`releasing_manager_approval_decision`, `hr_director_signoff_decision`) — the orchestrator's `wait_for_external_event(...)` then never fires, because the persona responder emits the persona's declared event, not the orchestrator's expected one.

This was caught only after the first full sandbox completed and the CHECKLIST §3.5 / §6.2 FAILed — costing a full ~12-min regenerate.

**Fix:** In `author-domain-skeleton` (and the autonomous-mode brief writer): when a HITL phase's `persona` already exists under `api/server/personae/`, **read that persona's `external_event:` from frontmatter and stamp it onto the brief's phase as an explicit override**. Add a CHECKLIST item §3.5b that asserts byte-match between brief.phase.external_event and the persona SKILL.md frontmatter for every reused persona.

Also: store a memory (already done in this session) — "compose-domain v4 briefs MUST set explicit `external_event:` on each HITL phase when reusing an existing persona."

**Citations:** `api/server/personae/line_manager/SKILL.md` (external_event: manager_approval_decision), `api/server/personae/hr_director/SKILL.md` (external_event: hr_director_decision).

### A5. Ambient-block emission shape is stale

The author-ambient-trigger codegen template emits `ambient_registry.append(...)` guarded by `hasattr(...)`. The **live** shape in `api/server/services/ambient_agents/{hr,finance}.py` is module-level constants:

```python
EmployeeTransferWatcher = AmbientAgent(
    name="employee-transfer-watcher",
    function="hr",
    triggers=(BusTrigger(event_type="hr.transfer.proposed"),),
    reasoning_skill=None,
    spawnable_workflow_types=("employee-transfer",),
)
```

The subagent for the second run noticed this drift and produced the right shape, but the template is still wrong — next compose-domain run that doesn't have a sharp-eyed agent will emit the dead append shape.

**Fix:** Update `author-ambient-trigger/codegen.py` to emit the module-level constant shape. The `graduate.sh` append step already concatenates between sentinels, so the per-domain block is exactly the constant.

**Citations:** `api/server/services/ambient_agents/hr.py:1-32` (MorningSweep canonical shape), `api/server/services/ambient_agents/finance.py` (BudgetVarianceWatcher, VendorRiskWatcher, PeriodClose).

### A6. Default `realistic_interval_seconds` lacks a demo-friendly guardrail

The brief author (autonomous mode) defaulted `realistic_interval_seconds=259200` (3 days). At `DEMO_TIME_WARP_FACTOR=60` that's 72 minutes per spawn — invisible in any demo session. Other employee-lifecycle domains use `86400` (24 min) or `21600` (6 min).

**Fix:** Add to `author-domain-skeleton` SKILL.md a guidance table mapping plausible cadence prose to demo-effective intervals:

| Real-world cadence | `realistic_interval_seconds` | Demo interval @ warp 60 |
|---|---|---|
| "every few hours" | 7200 | 2 min |
| "daily" | 21600 | 6 min |
| "few times a week" | 43200 | 12 min |
| "weekly" | 86400 | 24 min |
| "monthly+" | 259200 | 72 min — usually too slow |

CHECKLIST §10.x: warn if `realistic_interval_seconds > 86400` without explicit justification in the brief.

### A7. Tool operations in brief don't have to match real `@define_tool` decorators

The brief listed `contract_repository.draft_contract` as an operation, but no such tool exists in the live `contract_repository.py` (the actual operations are `get_contract`, `find_similar`, `list_amendments`). The agent skill's `allowed-tools` CSV silently drops unknown operations — the agent then can't draft a contract at runtime.

**Fix:** In `author-runtime-skill` (phase_agent mode), validate every `(mcp_tool, operation)` pair against the **actual** `@define_tool` decorator names by importing the module at validation time. Unknown operations fail brief validation with a clear "no such tool — available: [...]" message.

**Citations:** `api/server/mcp_tools/contract_repository.py` (real ops), brief `external_systems[].operations` mismatch noted by the subagent's REPORT.md.

### A8. `# AGENT-CHOICE:` annotations specified by the skill but not emitted

The `add-domain` SKILL.md autonomous-mode procedure says: *"Where the request is genuinely ambiguous (...) pick the most defensible default and annotate it inline in the brief as a `# AGENT-CHOICE: …` comment so it's reviewable later."* The generated brief had narrative-style choice rationale in the file header instead. The annotations are easier to grep + audit than prose.

**Fix:** Update the brief-author sub-skill to use the literal `# AGENT-CHOICE:` prefix for every defensible default. Add a CHECKLIST item that greps for `# AGENT-CHOICE:` and lists each one in the operator report.

---

## B. graduate.sh idempotent patcher

### B1. Step 5 (ramp_loop spawners) tries to patch a registry that no longer exists

**Severity:** medium (cosmetic WARN).

Step 5 in the generated `graduate.sh` looks for `spawners = {...}` literal in `simulator_orchestrator.py` and prints `WARN: could not find spawners dict literal in ramp_loop; skipping`. The codebase migrated to dynamic `_resolve_spawner(domain)` keyed off `DOMAINS[wt].spawn_fn` long ago — there is no static dict to patch, and adding the spawn helper alone is sufficient.

**Fix:** Drop step 5 entirely from the `graduate.sh.tmpl` template. Add a comment explaining the dispatch is now `_resolve_spawner(domain)` → reads `DOMAINS[wt].spawn_fn`, set in Phase 4b.

### B2. Step 7 (blueprint_inventory.py Procurement marker) is broken; `set -e` then masks steps 8-11

**Severity:** critical (the script visibly exited 0 but did not patch constants.py, owns_domains, or ambient hr.py).

The python heredoc in step 7 looks for `'    {\n        "name": "Procurement"'` as an insertion anchor:

```python
marker = '    {\n        "name": "Procurement"'
if marker not in src:
    raise SystemExit("ERR: could not find Procurement aspirational marker in inventory")
```

The inventory's live + aspirational lists are now **derived** from `DOMAINS` (a for-loop emits Procurement / Legal / IT) — there is no static `"Procurement"` string anymore. The `SystemExit` raised non-zero, `set -e` fired, and steps 8 / 9 / 10 silently never ran. The wrapping `2>&1 | tail -60` masked the non-zero exit so the operator (me) thought it had finished.

This required three hand-runs (constants lift, owns_domains tuple append, hr.py ambient append) to recover.

**Fix:** Rewrite step 7 to only patch `_PHASE_ALIASES` (the live entry is already auto-derived from `DOMAINS`). Also: change all `python3 - <<EOF_PY...` blocks to print diagnostics and `sys.exit(0)` rather than raising SystemExit — `set -e` is too sharp for the "could not find marker" case, which should be a WARN, not a hard stop. Or wrap each step in `|| true` with explicit verification afterwards.

Belt-and-braces: at the end of `graduate.sh`, run a final verification block that greps for the new `workflow_type` in every consumer file the script claims to have patched, and exits non-zero if any are missing. That catches B2-style silent-skip bugs.

**Citations:** Generated `graduate.sh` step 7 in `tools/scratch/compose-domain/20260521-083006-fleet-employee-transfer/graduate.sh:248-285`; live `api/server/services/blueprint_inventory.py:107-145`.

### B3. `set -e` + `| tail -60` hides failures

The operator runs `bash graduate.sh 2>&1 | tail -60` to keep the output digestible. With `set -e` and a Python heredoc that `raise SystemExit`s, the script's exit code becomes the pipe's exit code = the exit code of `tail`, which is 0. The visible "ERR:" line then looks like a soft warning.

**Fix:** Two options:

1. Recommend `bash graduate.sh 2>&1 | tee /tmp/grad.log; echo "exit: ${PIPESTATUS[0]}"` in `GRADUATION.md`.
2. Or simply have `graduate.sh` print a `DONE.` sentinel as its last line and have the operator grep for it. (Quickest fix.)

### B4. Step 9 doesn't extend `FUNCTIONS[<fn>].ambient_agents` even when the brief carries an `ambient:` block

Step 9 only patches `owns_domains` (the workflow_type list). It leaves `ambient_agents=(...)` untouched. Without the ambient agent name in that tuple, the orphan validator (and FM-skill catalogue) doesn't see the new watcher.

For employee-transfer I had to hand-add `"employee-transfer-watcher"` to `FUNCTIONS["hr"].ambient_agents`.

**Fix:** Extend step 9 to also append the brief's `ambient.name`-derived agent name (kebab-cased) to `FUNCTIONS[<function>].ambient_agents` via a second sentinel-anchored patch.

**Citations:** `api/shared/functions.py:106-114` (the FUNCTIONS["hr"] entry where both tuples live), brief `ambient.name: EmployeeTransferWatcher`.

### B5. Step 8 (constants timeout lift) silently no-ops when the orchestrator already imports from `api.shared.constants`

Step 8's branching logic checks `if grep -q "from api.shared.constants import" "$ORCH_PATH" && grep -q "MANAGER_APPROVAL_DECISION_TIMEOUT" "$ORCH_PATH"` and prints "orchestrator already lifted (skip)". In the first run we never even reached step 8, so this didn't trigger — but the logic is fragile: a fresh orchestrator that already imports *some other* constant would skip the lift entirely.

**Fix:** Decouple the two checks (constants.py append vs orchestrator import rewrite) into two independent idempotent steps.

---

## C. add-domain orchestrator skill

### C1. Skill claims `graduate.sh` patches 7 live trees — but two patches are broken (B1, B2) and one is incomplete (B4)

The `.github/skills/add-domain/SKILL.md` substrate-map table at the top says all 7 files (function_app.py, graphs/__init__.py, simulator_orchestrator.py, simulator route, blueprint_inventory.py, constants.py, functions.py) are patched by `graduate.sh`. The reality from this run:

- function_app.py ✓
- graphs/__init__.py ✓
- simulator_orchestrator.py — spawn helper appended, ramp dict patch fails harmlessly (B1)
- simulator route ✓
- blueprint_inventory.py ✗ (B2 — script halts here)
- constants.py ✗ (silently skipped after B2)
- functions.py — owns_domains only, ambient_agents not patched (B4)

Of the "8 expected files" in the substrate-map table, three are broken end-to-end. The skill needs to either fix the script or move those three to the **hand-stitch** column alongside `api/shared/domains.py` and `entity_projections/__init__.py`.

**Fix:** Until graduate.sh is fixed, update the substrate-map in `.github/skills/add-domain/SKILL.md`:

| # | File | Patched by | Notes |
|---|------|-----------|-------|
| 7 | `blueprint_inventory.py` | **Hand-stitched (Phase 4b)** | Add an entry to `_PHASE_ALIASES`; live-domain manifest auto-derives from `DOMAINS`. |
| 8 | `constants.py` | **Hand-stitched (Phase 4b)** | Lift per-phase `<PHASE>_TIMEOUT` constants + rewrite orchestrator import. |
| 9 | `functions.py` | **Hand-stitched (Phase 4b)** | Append `workflow_type` to `owns_domains`; also append ambient agent name to `ambient_agents`. |

### C2. UI filter chip list (`KNOWN_DOMAINS` in `web/client/components/feed/Feed.tsx`) is hardcoded — new domains invisible in the chip bar until manually added

Not mentioned anywhere in the substrate map. We hit this directly: the chip bar showed 15 hardcoded entries, `employee-transfer` was absent. The UI bundle had to be edited + `npx vite build` rerun.

**Fixed 2026-05-21:** `KNOWN_DOMAINS` deleted from `Feed.tsx`. All UI surfaces (`Feed.tsx` filter chips, `PhaseRibbon.tsx`, `PhaseTimeline.tsx`, `WorkflowCard.tsx`) now derive from `/api/blueprint/composition` via the new `useDomainRegistry` hook at `web/client/hooks/useDomainRegistry.ts`. The composition endpoint was extended to emit a per-domain `phases: [{name, kind}]` array, auto-derived from `api.shared.domains.DOMAINS`. The 13 `*_PHASE_ORDER` constants in `web/shared/types.ts` and the matching switch statements in `PhaseRibbon.tsx` / `PhaseTimeline.tsx` / `WorkflowCard.tsx` were also deleted. New domains now require zero per-domain UI code — they appear in every surface on the next server restart.

**Fix:** Add to the substrate-map a 10th entry:

| # | File | Patched by | Notes |
|---|------|-----------|-------|
| 10 | `web/client/components/feed/Feed.tsx` | **No edit needed (as of 2026-05-21)** | Derives from `/api/blueprint/composition` via `useDomainRegistry`. New domains auto-appear after server restart. |

And require an `npx vite build` step in Phase 4d verification.

**Citations:** `web/client/components/feed/Feed.tsx:28-33`.

### C3. AGT authority matrix not addressed at all

The `add-domain` skill makes no mention of `data/synthetic/authority/matrix.json` or `AuthorityCard.tsx` `deriveMatrixRequest()`. A new domain without matrix rules + a derivation case won't show the AuthorityCard on its workflow-detail page — silently degraded governance surface. We discovered this only because the user asked.

**Fix:** Add an 11th entry to the substrate-map:

| # | File | Patched by | Notes |
|---|------|-----------|-------|
| 11 | `data/synthetic/authority/matrix.json` | **Hand-stitched (Phase 4b)** | Add ≥1 rule per HITL gate; categories should match the AuthorityCard's `deriveMatrixRequest()` switch. |
| 12 | `web/client/components/apex/AuthorityCard.tsx` | **Hand-stitched (Phase 4b)** | Add a `deriveMatrixRequest()` case mapping `payload.<entity>` → `{action, category, value}`. |

Long-term: the brief's `decisions[]` block already names per-HITL personae and entities — compose-domain v4 could emit a per-domain matrix-rules JSON fragment and a TypeScript snippet for `deriveMatrixRequest` and let `graduate.sh` patch both files between sentinels.

**Citations:** `data/synthetic/authority/matrix.json` (new EXF-001..003 rules added this session), `web/client/components/apex/AuthorityCard.tsx:81-126` (existing per-domain switch cases).

### C4. Subagent compose-domain runs are slow and bandwidth-heavy (~10-12 min per run)

Each compose-domain run reads ~25 canonical files end-to-end (the orchestrator SKILL.md alone is 783 lines; the 9 isomorphism examples are large). When the first run FAILs due to brief-level issues (e.g. A4), the operator pays the full cost again. In this session: ~25 minutes wall-clock for 2 runs.

**Fix:** Two orthogonal improvements:

1. **Pre-flight brief validation** before invoking compose-domain. Run the schema validator + the A4 check (HITL persona event-name match against frontmatter) + the A7 check (tool operation names against real decorators) standalone. None of these need the codegen subagent — they're pure file reads. Catching all of them shaves a full subagent run when the brief is wrong.
2. **Cache the canonical-file reads** between runs. The 9 isomorphism examples don't change between runs — the subagent re-reads them every time. A simple file-content hash + skill instruction "if you have already read this file in this session, do not re-read" would help.

**Partial fix shipped 2026-05-21** (commit-pending in this session): added a "Fast-path read budget" + "Shape cheat-sheet" section to `docs/superpowers/skills/compose-domain/SKILL.md`, and a corresponding subagent-prompt rule in `.github/skills/add-domain/SKILL.md` Phase 3. The cheat-sheet captures the byte-shapes for orchestrator, spawn helper, factory, ambient block, persona sandbox, and HITL event-name byte-match — these account for ~95% of generation byte-decisions. Canonical examples are now a fallback. Step 3 of compose-domain SKILL.md now says "read on demand", not "read exactly these 9 files end-to-end". Expected: ~3 min ingestion vs. ~6 min previously. Still wants the structural fixes above (pre-flight validator + read cache) for the full payoff.

### C5. `compose-domain` is not registered as a Copilot CLI skill, only as a docs-skill

When I tried `skill: compose-domain` it returned "Skill not found" — only `add-domain` is in the Copilot CLI skill registry. compose-domain lives at `docs/superpowers/skills/compose-domain/SKILL.md` and is dispatched to a subagent. The mismatch is mildly confusing — the `add-domain` skill links to compose-domain as if it were a sibling skill but it's actually a docs-file the parent agent has to manually orchestrate.

**Fix (low priority):** Either register `compose-domain` as a Copilot CLI skill (would help discovery + standardise invocation), or update the add-domain skill's links to be explicit ("read this docs-file and dispatch a subagent to execute it" rather than "invoke this skill").

---

## D. Surrounding substrate that compose-domain should know about

### D1. `entity_projections/__init__.py` registration is **two** alphabetised insertions, not one

The skill's Phase 4c hand-stitch says: add `from . import <wt_snake>` to the alphabetised import block AND add `<wt_snake>` to the `_DOMAIN_MODULES` tuple. I got the second insertion wrong on the first attempt (appended to the wrong line group, breaking alphabetical order) and had to re-edit.

**Fix:** In `.github/skills/add-domain/SKILL.md` Phase 4c, show a literal diff example for both insertions including the exact alphabetical neighbours so the operator can pattern-match. Or: have `graduate.sh` do this patch (it's idempotent and the two insertions are mechanical).

### D2. The CHECKLIST smoke-pytest has 14 pre-existing failures unrelated to any new domain

Running `uv run pytest tests/docs/superpowers/skills/compose_domain -q` returns `9 failed, 38 passed, 5 errors` — all about archived briefs that no longer exist at the expected paths (`lead-to-cash-brief.yaml`, `hire-to-productive-brief.yaml`, `vendor-risk-to-pay-brief.yaml`, and `fleet-purchase-card-brief.yaml` which moved to `archive/`). I had to do a `git stash` + baseline-run to confirm my changes added zero regressions.

**Fix:** Update the smoke tests to look in `docs/superpowers/specs/archive/` as well as `docs/superpowers/specs/`. Or move the archived briefs back. Or skip the parametrised tests for briefs that no longer exist. The current state forces every operator to run a baseline-comparison just to know whether they broke something.

### D3. Boot demo's `.env` `SIMULATOR_RAMP_DOMAINS` was hardcoded to a 12-domain subset

Unrelated to compose-domain per se, but the demo never spawned the new domain at boot until I noticed the .env override. The `add-domain` skill should mention this in Phase 5 (polish) as a "did you actually see it spawn?" check.

**Fix:** In `.github/skills/add-domain/SKILL.md` Phase 4d verification, add: `grep SIMULATOR_RAMP_DOMAINS .env` — if set to a hardcoded list, confirm the new domain is in it OR unset the variable. (I committed unsetting it as the demo default in this session; this finding may already be moot for future runs.)

---

## Priority order for fixes (suggested)

1. **A1 + A2 + A3** (single template patch): generated spawn helpers must mirror v3 — upsert before scheduling, build via a factory in `synthetic_data.py`, capture the orchestration instance id. This was the single biggest substantive bug.
2. **B2** (graduate.sh step 7 broken + `set -e` cascade): silently skipping 4 of 11 steps is a foot-gun that destroys operator trust in the script.
3. **A4** (HITL external_event auto-stamp from persona frontmatter): prevents a full ~12-min sandbox regenerate.
4. **C3** (AGT matrix in substrate-map): demoable governance surface needs explicit per-domain wiring.
5. **C2** (UI filter chip): the very first thing a demo'er notices.
6. **B4** (FUNCTIONS.ambient_agents append): catches the orphan-validator failure mode.
7. **B3 / B5 / B1** (graduate.sh hygiene): less impactful but cumulative.
8. **A5 / A6 / A7 / A8** (codegen polish + brief-validation tightening).
9. **C4 / C5 / D1 / D2 / D3** (skill-doc and tooling hygiene).
