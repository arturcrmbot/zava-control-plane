# Dreaming Sessions: Autonomous Lesson Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the human-approval flow shipped in D1 with a fully autonomous lesson lifecycle: lessons that meet the policy threshold are auto-promoted into agent memory; lessons that fail are auto-rejected; a periodic "dreaming session" cleans the slate. The control plane gets a read-only Lessons surface (domain-agnostic) for observability — no buttons, no human action.

**Architecture:**

1. **Auto-promote on threshold.** Today `dream_pass/policy.py` already returns `promote` / `reject` / `flagged` / `inconclusive`. Drop `flagged` as a verdict — anything that doesn't clear the bar collapses into `reject` with `reason="below_threshold"` (or `reason="flagged:<original>"` if a stricter sub-policy fired). The orchestrator stops calling `governor.write_flagged_candidate`; the candidate just doesn't get promoted.
2. **Dreaming sessions.** A `DreamingScheduler` runs N times a day (Durable timer or cron, env-toggled) and for each registered domain:
   - prunes superseded / stale lessons (default: any `active` lesson with `promoted_at < now - LESSON_TTL_DAYS` AND no read activity since)
   - runs one `DreamPassOrchestrator.run()` pass with the in-memory store warmed from Kuzu
   - emits a `FleetEvent("dream_pass.session", ...)` with counts
3. **Generic Lessons surface on the control plane.** A new `LessonsPanel.tsx` in `web/client/` lists all `Lesson` rows across all domains and statuses (active / candidate-pruned / pruned), with filters for domain + status. Read-only. No approve/reject. Backend route `GET /api/lessons` joins Kuzu + audit ledger to show provenance.
4. **Remove D1 HITL.** Delete the `/dream-pass-exceptions` portal page, `/api/dream-pass/flagged/{id}/approve|reject` routes, `LessonGovernor.approve_flagged` / `reject_flagged`, `lesson.approve_flagged` / `lesson.reject_flagged` from `tools.yaml`. Keep `LessonGovernor.write_flagged_candidate` only if useful for observability — otherwise also delete.

**Tech Stack:** Python 3.11, existing AGT kernel, existing Kuzu, FastAPI for the new read route, React + Vite + TypeScript for the control plane page. No new third-party deps.

---

## ⚠️ What this plan is replacing

D1 (Dream-Pass Exception Portal, PR #21, merged as `b377fd20`) shipped a human approval queue. That contradicts the autonomous design of the dream-pass loop and was the wrong call. This plan reverts the human surface and replaces it with a read-only generic Lessons panel on the control plane. The dream-pass loop itself stays — only the post-flagged human path goes.

---

## File Structure

**New files:**
- `api/server/services/lessons/dreaming_scheduler.py` — `DreamingScheduler` orchestrating per-domain dream passes + lesson GC
- `api/server/services/lessons/lesson_repo.py` — read-only `LessonRepo` (broader query than `FlaggedLessonRepo`)
- `api/server/routes/lessons.py` — `GET /api/lessons` (filter by domain / status)
- `web/client/src/components/lessons/LessonsPanel.tsx` — read-only table
- `web/client/src/api/lessons.ts` — typed client
- `scripts/dream_session.py` — CLI: `dream_session.py --domain hiring` (one-shot of the scheduler's per-domain body)
- `tests/api/services/lessons/test_dreaming_scheduler.py`
- `tests/api/services/lessons/test_lesson_repo.py`
- `tests/api/routes/test_lessons.py`

**Modified files:**
- `api/server/services/dream_pass/policy.py` — collapse `flagged` into `reject`; add `reason` annotation
- `api/server/services/dream_pass/types.py` — remove `flagged` from `ExperimentVerdict` literals
- `api/server/services/dream_pass/orchestrator.py` — drop the `elif decision.verdict == 'flagged'` branch and the `governor.write_flagged_candidate` call
- `api/server/services/lessons/governor.py` — delete `approve_flagged` / `reject_flagged`; optionally delete `write_flagged_candidate`
- `api/server/services/lessons/kuzu_provenance.py` — delete `record_candidate` / `fetch_candidate` if unused; keep `list_flagged` only if `LessonRepo` doesn't subsume it (it should)
- `data/policies/tools.yaml` — remove `lesson.approve_flagged` and `lesson.reject_flagged`
- `api/server/main.py` — unregister `dream_pass_exceptions_router`, register `lessons_router`

**Deleted files:**
- `api/server/routes/dream_pass_exceptions.py`
- `api/server/services/lessons/flagged_repo.py`
- `tests/api/routes/test_dream_pass_exceptions.py`
- `tests/api/services/lessons/test_flagged_repo.py`
- `tests/api/services/lessons/test_governor_flagged.py`
- `web/portal/src/pages/DreamPassExceptions.tsx`
- `web/portal/src/api/dreamPassExceptions.ts`
- Remove the `/dream-pass-exceptions` route in `web/portal/src/App.tsx`

---

## Conventions

- Read-only on the operator side. No approve/reject. The dream-pass policy is the only decision-maker.
- Generic across domains. The Lessons panel and route MUST NOT hard-code `hiring`; domain is a filter not a primary axis.
- Scheduler is opt-in via `DREAMING_ENABLED=1` and `DREAMING_DOMAINS=hiring,vendor_kyc,...`. Off by default in dev; on in the demo container.
- Same plan-vs-reality lessons from B1/B2/C1/D1 apply: `EntityGraph.query()` not `.execute_cypher()`; `AuditLogger.log(action, details)` positional; reuse `app_state.entities` in FastAPI routes (D1 had a bug here that this plan must NOT reintroduce).

---

## Task 1: Collapse the `flagged` verdict into `reject`

**Files:**
- Modify: `api/server/services/dream_pass/policy.py`
- Modify: `api/server/services/dream_pass/types.py`
- Modify: `api/server/services/dream_pass/orchestrator.py`
- Test: extend `tests/api/services/dream_pass/test_policy.py` + `test_orchestrator.py`

Make every code path that returned `verdict='flagged'` now return `verdict='reject', reason='flagged:<original>'`. The orchestrator's `elif decision.verdict == 'flagged'` branch disappears entirely; the `reject` branch handles it (count → `rejected`).

Acceptance: existing `test_policy.py` and `test_orchestrator.py` updated to expect `reject`; no test asserts `flagged` anywhere.

## Task 2: Delete the D1 HITL surface

**Files:**
- Delete: route, repo, governor methods, tools.yaml entries, portal page, portal client, portal route — per the "Deleted files" list above.
- Delete tests for the deleted code.
- Unregister `dream_pass_exceptions_router` from `api/server/main.py`.

Acceptance: `git grep approve_flagged` returns 0 hits. `git grep dream-pass-exceptions` returns 0 hits. Existing test suite still passes.

## Task 3: `LessonRepo` (generic read)

**Files:**
- Create: `api/server/services/lessons/lesson_repo.py`
- Test: `tests/api/services/lessons/test_lesson_repo.py`

`LessonRepo.list(*, domain: str | None = None, status: str | None = None, limit: int = 200)` returns Lesson rows joined with their `EXPERIMENT_FOR_LESSON` evidence (when present). Status filter accepts `active` / `candidate` / `pruned` / `superseded`. Reuses `app_state.entities` via `graph.query(...)`.

Acceptance: 4 tests — by-domain, by-status, both, neither (returns all). All with `EntityGraph` `tmp_path` fixtures that `g.close()` on teardown.

## Task 4: `/api/lessons` route

**Files:**
- Create: `api/server/routes/lessons.py`
- Test: `tests/api/routes/test_lessons.py`
- Modify: `api/server/main.py` (mount the router)

`GET /api/lessons?domain=&status=&limit=` returns `{"items": [...]}`. Pydantic models. Reuses `app_state.entities` (D1's bug fix pattern).

Acceptance: 4 tests covering happy path, filters, empty result, 422 on bad status.

## Task 5: `DreamingScheduler`

**Files:**
- Create: `api/server/services/lessons/dreaming_scheduler.py`
- Test: `tests/api/services/lessons/test_dreaming_scheduler.py`
- Create: `scripts/dream_session.py` (CLI for one-shot per-domain run)

`DreamingScheduler.run_once(domain)` does:
1. **GC** — prune `active` lessons older than `LESSON_TTL_DAYS` with no recent read activity. Use `LessonGovernor.prune(...)` so the audit ledger captures it.
2. **Pass** — instantiate `DreamPassOrchestrator` for the domain and call `.run()`.
3. **Emit** `FleetEvent("dream_pass.session", domain=..., promoted=N, rejected=M, pruned=K, duration_ms=...)`.

No timer in the first cut — just the CLI. Wiring to Durable / cron lands in a follow-up plan once the scheduler body is proven.

Acceptance: `scripts/dream_session.py --domain hiring` runs end-to-end and prints session counts. Unit tests mock the governor + orchestrator and assert the call shape and event payload.

## Task 6: Lessons panel on the control plane

**Files:**
- Create: `web/client/src/api/lessons.ts` — typed `fetch` wrapper
- Create: `web/client/src/components/lessons/LessonsPanel.tsx` — read-only table with domain + status filters
- Modify: wherever the control plane registers panels (`web/client/src/routes/...` or equivalent — locate first with `grep -rn '<Route ' web/client/src/`)

No approve/reject buttons. Columns: body (truncated), domain, status, Δ, n, proposed_by, promoted_at, prune_reason (when present). Click-to-expand for full body + experiment evidence.

Acceptance: panel renders against `/api/lessons` with any combination of filters, shows all four statuses with colour coding (active = green, candidate = grey, pruned = red, superseded = amber). Plays cleanly when the list is empty.

## Task 7: Final regression + Definition of Done

- Full lesson + dream_pass + route suite green.
- Targeted regression: `tests/api/services/lessons tests/api/services/dream_pass tests/api/services/scoring tests/api/routes/test_lessons.py tests/api/server/test_entity_graph_smoke.py tests/api/unit/test_classify_graph.py` — all pass.
- `scripts/dream_session.py --domain hiring` runs to completion.
- Control plane `/lessons` (or whatever route Task 6 lands) renders all lessons across all merged domains.
- `git grep -iE 'approve_flagged|reject_flagged|dream-pass-exceptions'` returns 0 hits.

---

## Definition of Done

- **Autonomous:** the dream-pass loop promotes winners and rejects everything else without any human action.
- **Dreaming:** `DreamingScheduler` (manually triggered for now) does GC + a fresh dream pass per domain in one call, emits a fleet event.
- **Observable:** the control plane has a generic, read-only Lessons panel showing every Lesson across every domain.
- **Cleanup:** D1's HITL surface is gone from code, tests, tools.yaml, and the candidate portal.
- All existing tests still pass; the audit ledger continues to capture every governance decision.
