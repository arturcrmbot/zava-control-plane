# Repo Coherence Remediation Plan

**Source audits:** `files/arch-ground-truth.md`, `files/code-quality.md`, `files/doc-accuracy.md`
**Repo HEAD at audit time:** `c26bdcef`

## Problem statement

The repo is internally coherent at the substrate level, but three distinct seams of drift were found:

1. **Code↔code drift** — the `DECIDED_ON` Kuzu sharding refactor (`ac569ec2`) updated writers but not readers. Decisions written today don't appear in precedent lookups or the KnowledgePulse activity strip.
2. **Code↔code↔docs drift** — the cosmic-lens UI is mid-redesign (5 of last 10 commits) with no vitest coverage on new surfaces, dead code still on disk, and a real polling-doubling bug in `useLiveCosmic`.
3. **Code↔docs drift** — `ARCHITECTURE.md` and `CODEBASE-TOUR.md` froze at Phase 1/2 (claim 8 domains / 15 personae; reality is 19 domains / 32 personae and Phase 3–4 components are missing entirely). Several mermaid diagrams and curl examples reference the wrong port (`:8000` vs `:3001`).

Beyond the seams, the security posture is "PoC-internal-only": raw-Cypher MCP tool, `exec()`/`eval()` of YAML-loaded persona code, CORS `*`+credentials, and several unauthenticated routes that mutate state or leak the substrate graph.

## Approach

Sequenced into six tracks, ordered by harm-if-left-broken. Each todo is independently executable; dependencies are wired in `todo_deps`.

- **Track A — Stop the bleeding** (P0): the sharding-readers bug + the SSE/polling frontend bugs. Small fixes, high impact.
- **Track B — Doc honesty** (P1): rewrite the two damaging docs and fix the wrong-port references so onboarding is no longer misleading.
- **Track C — Security guardrails** (P1): introduce a "do-not-expose" guard and pick an auth story for each currently-unauth route.
- **Track F — Cosmic-lens humanization** (P1): make every interactive surface read as plain English via `web/shared/humanize.ts`. Detail in `plan/feature-humanize-cosmic-lens-1.md` (8 phases, 36 tasks); SQL tracks at phase granularity (`f1`–`f8`). Inserted before Track D because Track D's frontend tests should run against the humanized surfaces, not the current jargon.
- **Track D — Frontend stabilisation** (P2): test coverage for new cosmic-lens surfaces, kill dead code, type the `(wf: any)` cast.
- **Track E — Cleanup** (P3): config drift, rebrand debris, archived docs, missing `web/README`.

Tracks A, C, and E are independent of Track F. Track B's two doc rewrites depend on Track A's sharding fix landing first. Track D's frontend tests (`d1`, `d3`) depend on Track F finishing so we don't write smokes against soon-to-change copy. Track D's `d5` (typing the `(wf: any)` cast in WorkflowDrawer) is sequenced into Track F's Phase 4 area to avoid edit-conflicts on the same file.

## Notes / considerations

- The substrate (entity graph + reflector + 12 projections + EventBus + state.py) is **the healthiest part of the repo** — do not touch it except where Track A explicitly says to.
- `web/blueprint/` is the primary React app. `web/portal/` is the candidate portal (real, used). `web/client/` is unclear — flag for an explicit decision in Track E rather than auto-deleting.
- Skipped tests should be addressed *only* when their target feature is in scope; do not unblock skips speculatively.
- All Kuzu schema/Cypher changes must respect the `kuzu schema syntax` constraints already captured in stored memories (no `SET n += $map`, backtick reserved words, inline `LIMIT` ints).
- Use `claude-opus-4.7-1m-internal` for any sub-agents per stored user preference.
- **Track F sub-plan:** the cosmic-lens humanization per-task detail lives at [`plan/archive/feature-humanize-cosmic-lens-1.md`](archive/feature-humanize-cosmic-lens-1.md). It was archived at plan-merge time (not yet shipped) because the master plan now owns the queue — the archive copy is kept solely as the source of TASK-001..036 detail referenced by `f1`–`f8`. Do NOT duplicate that detail in this file. When all eight phases ship, leave the file in `archive/` and update its status header to `Shipped`.
- **d5 ↔ f4 coordination:** d5 (typing the `(wf: any)` cast in `WorkflowDrawer.tsx`) and f4 (function drawer wording rewrite) both edit the same file. Sequence d5 immediately after f4 in the same working session to avoid merge friction.

## Tracking

Todos are tracked in SQL (`todos` + `todo_deps`). Use:

```sql
SELECT id, title, status FROM todos ORDER BY id;
SELECT t.id, t.title FROM todos t
WHERE t.status = 'pending'
  AND NOT EXISTS (SELECT 1 FROM todo_deps d JOIN todos dep ON d.depends_on = dep.id
                  WHERE d.todo_id = t.id AND dep.status != 'done');
```

This `plan.md` is the human-readable source of truth; the SQL table is the queryable execution surface.
