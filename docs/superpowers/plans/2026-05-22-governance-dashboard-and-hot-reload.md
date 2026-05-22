# Plan A — Governance Dashboard Rewrite + Kernel Hot-Reload

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dead `/api/policy` surface with a two-panel governance dashboard sourced from the actual AGT-enforced `matrix.json`, and wire AGT's `reload_policies()` so a checked-in matrix change takes effect on the running process within ~1 s.

**Architecture:** Delete `api/shared/policies.yaml` + `AutonomyPolicy` + the old route. Add `/api/governance/matrix` + `/api/governance/policy_changes/recent`. Add a file watcher in `GovernanceKernel` that recompiles on `matrix.json` change and emits a bus event. Rewrite `web/client/routes/PolicyAndAutonomy.tsx` as a constitution table on top of a live decisions stream.

**Tech Stack:** FastAPI · AGT (`agent_os.policies`) · Kuzu (Decision nodes) · React + Vite · existing SSE relay.

**Spec:** `docs/superpowers/specs/2026-05-22-public-replay-landing-design.md` (sections: "Governance surface" + "Kernel hot-reload" + Phase 0 cleanup line)

---

## Phase 0 — Cleanup dead policy surface

### Task 0.1: Audit references

**Files (read-only):**
`api/shared/policies.yaml`, `api/server/routes/policy.py`, `api/server/services/state_store.py`, `api/shared/types.py`, `web/client/routes/PolicyAndAutonomy.tsx`, all tests.

- [ ] Grep `AutonomyPolicy`, `upsert_policy`, `list_policies`, `/api/policy/dry-run`, `/api/policy/propose-change`, `api/shared/policies.yaml`. Record consumers in session notes.
- [ ] Note that the operator UI route at `/policy` will be rewritten in Phase 2, not deleted; the API route at `/api/policy` returns 410 until rewritten.

### Task 0.2: Remove `AutonomyPolicy` model + state-store methods

**Files:** `api/shared/types.py`, `api/server/services/state_store.py`, any test importing `AutonomyPolicy`.

- [ ] Delete the `AutonomyPolicy` class.
- [ ] Delete `_policies` dict + `upsert_policy` + `list_policies` from `StateStore`.
- [ ] Run pytest, fix any test that imported the deleted symbols (delete the test if it only exercised the dead route).
- [ ] Verify FastAPI boots: `uv run uvicorn api.server.main:app --port 3199` → `curl /api/workflows` returns 200.
- [ ] Commit: `refactor(governance): drop dead AutonomyPolicy model + state-store methods`.

### Task 0.3: Delete `policies.yaml` and stub the old `/api/policy` route

**Files:** `api/shared/policies.yaml` (delete), `api/server/routes/policy.py` (stub).

- [ ] `git rm api/shared/policies.yaml`.
- [ ] Replace `api/server/routes/policy.py` with a single 410 handler explaining the surface moved.
- [ ] Smoke: boot FastAPI, `curl /api/policy` → 410.
- [ ] Commit: `refactor(governance): retire policies.yaml; /api/policy returns 410`.

---

## Phase 1 — New governance endpoints

### Task 1.1: `GET /api/governance/matrix` enriched

**Files (create):**
- `api/server/services/governance/matrix_enrichment.py`
- `api/server/routes/governance_matrix.py` (or extend `governance.py`)
- `tests/api/server/routes/test_governance_matrix.py`

- [ ] Test: endpoint returns each matrix row with `owner_persona`, `owner_function`, `last_changed_at`, `last_changed_by_sha`.
- [ ] Implement enrichment: parse `data/synthetic/authority/matrix.json`; map `(action, category)` → function via `api/shared/functions.py:FUNCTIONS`; derive `owner_persona` from the function's persona-hierarchy root; run `git log -1 --format='%aI %h %an' -- data/synthetic/authority/matrix.json` once at boot, cache result.
- [ ] Register the router in `api/server/main.py`.
- [ ] Verify locally: `curl /api/governance/matrix | jq '.rules[0]'` shows enriched fields.
- [ ] Commit: `feat(governance): /api/governance/matrix enriched rows`.

### Task 1.2: `GET /api/governance/policy_changes/recent`

**Files:** extend `api/server/routes/governance.py`, test under `tests/api/server/routes/`.

- [ ] Test: returns recent `policy_set` Decisions in reverse-chrono order with `governing_rule_id` populated.
- [ ] Implement: Kuzu query against `Decision` nodes where `kind = 'policy_set'`, limit param, mapped to a flat JSON shape (`id`, `decided_at`, `persona_role`, `scope`, `governing_rule_id`, `reason`).
- [ ] Verify: trigger a `policy_set` locally (cadence loop produces them eventually), `curl /api/governance/policy_changes/recent`.
- [ ] Commit: `feat(governance): recent policy_set changes endpoint`.

### Task 1.3: Surface `policy_set` events on `/api/blueprint/stream`

**Files:** `api/server/routes/blueprint.py`, `api/server/services/policy_application.py`.

- [ ] Confirm `_spawn_policy_set` emits a bus event with `governing_rule_id`. If not, emit one (`decision.recorded` with `kind: policy_set`).
- [ ] Add the event type to `_OBSERVATORY_TYPES` in `blueprint.py`; surface `governing_rule_id` in the normalised payload.
- [ ] Verify: `curl -N /api/blueprint/stream` shows the new event after a `policy_set` fires.
- [ ] Commit: `feat(governance): relay policy_set events with governing_rule_id`.

---

## Phase 2 — `/policy` UI rewrite

### Task 2.1: Data hooks

**Files (create):**
- `web/client/hooks/useGovernanceMatrix.ts`
- `web/client/hooks/usePolicyChanges.ts`

- [ ] Test: each hook polls its endpoint, dedups identical responses, exposes a refetch.
- [ ] `usePolicyChanges` ALSO subscribes to `/api/blueprint/stream`; on `decision.recorded` with `kind: policy_set`, prepend to the in-memory list and dispatch a window event `governance:pulse-rule` with `governing_rule_id` so the table can highlight the row.
- [ ] Commit: `feat(governance): useGovernanceMatrix + usePolicyChanges hooks`.

### Task 2.2: `ConstitutionTable` component

**Files (create):** `web/client/components/policy/ConstitutionTable.tsx`, test in `__tests__`.

- [ ] Test: renders rows grouped by `owner_function`; each row shows the owner-persona chip in the persona's hue (`usePersonaHues`), `Last changed` cell, `Effect` chip.
- [ ] Implement: receives matrix from `useGovernanceMatrix`. Listens for `governance:pulse-rule`; adds a 3 s outline animation on the row with matching `rule_id`. Click row → modal with raw JSON + tooltip about the PR/hot-reload framing.
- [ ] Commit: `feat(governance): ConstitutionTable with live pulse`.

### Task 2.3: `RecentDecisions` component

**Files (create):** `web/client/components/policy/RecentDecisions.tsx`, test.

- [ ] Test: vertical timeline; each row links back to its matrix rule via anchor scroll.
- [ ] Implement: receives changes from `usePolicyChanges`. Renders persona chip + timestamp + scope + governing-rule pill (clickable, scrolls the constitution table to that row + pulses it).
- [ ] Commit: `feat(governance): RecentDecisions timeline`.

### Task 2.4: Compose into `/policy` route

**Files (rewrite):** `web/client/routes/PolicyAndAutonomy.tsx`.

- [ ] Two-panel layout: ConstitutionTable on top, RecentDecisions below. Page title "Governance".
- [ ] Drop old `AutonomyPolicy` rendering, drop `WhatIfPanel`.
- [ ] Page also reserves a 32px banner area for the Phase 3 "constitution reloaded" event.
- [ ] Verify visually with Playwright: `tests/e2e/audit-screens.spec.ts` re-screenshots `/policy`; spec passes.
- [ ] Commit: `feat(governance): two-panel /policy dashboard`.

---

## Phase 3 — Kernel hot-reload

### Task 3.1: `ReloadWatcher` service

**Files (create):**
- `api/server/services/governance/reload_watcher.py`
- `tests/api/server/services/governance/test_reload_watcher.py`

- [ ] Test: writing the file fires the callback within ~200 ms.
- [ ] Implement: asyncio task polling mtime + sha256 every 500 ms (configurable); calls a single `on_change` callback. Tolerant of file-not-found, file-mid-write (sha check guards against torn reads).
- [ ] Commit: `feat(governance): ReloadWatcher`.

### Task 3.2: `GovernanceKernel.reload()` + bus event

**Files:** `api/server/services/governance/kernel.py`, `api/shared/events.py` (add event type to docs catalogue if appropriate).

- [ ] Test: `kernel.reload()` recompiles, swaps `_bundle` atomically, returns the diff (`{added, removed, changed_rule_ids, new_policy_version}`).
- [ ] Implement: lock around the swap so an in-flight `check_authority` doesn't see a half-replaced bundle. Emit `governance.matrix.reloaded` on the global bus with the diff.
- [ ] Commit: `feat(governance): GovernanceKernel.reload()`.

### Task 3.3: Wire watcher into FastAPI lifespan

**Files:** `api/server/state.py` or `api/server/main.py` lifespan.

- [ ] Start `ReloadWatcher(matrix_path, on_change=lambda: kernel.reload())` when `GOVERNANCE_HOT_RELOAD != "0"` (default on).
- [ ] Cancel + await on lifespan teardown.
- [ ] Verify locally: boot FastAPI, edit a rule in `matrix.json`, `curl /api/governance/matrix` reflects the change within 1 s; the bus event surfaces over `/api/blueprint/stream`.
- [ ] Commit: `feat(governance): hot-reload matrix.json into running kernel`.

### Task 3.4: Surface reload event on the dashboard

**Files:** `api/server/routes/blueprint.py` (add event type), `web/client/components/policy/ConstitutionTable.tsx`.

- [ ] Add `governance.matrix.reloaded` to `_OBSERVATORY_TYPES` and the normaliser.
- [ ] Table listens for the event over SSE; shows a 3 s banner `constitution reloaded — N rules changed (sha abc1234)`; pulses each `changed_rule_ids` row.
- [ ] Commit: `feat(governance): dashboard banner on matrix reload`.

---

## Done criteria

- `/api/policy` returns 410; new dashboard lives at `/policy` UI route.
- Matrix dashboard shows enriched rows with owner persona + last-changed timestamp + rule effect.
- A `policy_set` event causes the corresponding matrix row to pulse + adds a line to the decisions panel within 1 s.
- Editing `matrix.json` while FastAPI is running causes a reload within 1 s and surfaces a banner on the dashboard.
- Existing tests still pass; new tests cover the three new endpoints + the watcher + the kernel reload.

## Estimate

| Phase | Days |
|---|---|
| 0 — cleanup | 0.5 |
| 1 — endpoints | 0.5 |
| 2 — UI rewrite | 1.0 |
| 3 — hot-reload | 0.5 |
| **Total** | **~2.5** |
