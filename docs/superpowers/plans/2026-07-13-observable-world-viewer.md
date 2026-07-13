# Observable World Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated `/world` Control Plane route that visibly renders actual ticket and worker actors, their journal-backed transitions, and the real Durable intervention; remove the temporary constellation stats panel.

**Architecture:** One polling hook fetches actor snapshots (1s) and causal event tails (300ms), maintaining a bounded event ring and cursor. One route renders actual actors in queue/service/terminal lanes and worker pools; every highlight and movement is driven by snapshot state or journal events. No new store, chart library, canvas framework, SSE connection or playback abstraction.

**Tech Stack:** React 19, TypeScript, Tailwind, existing Vite/Vitest/Playwright.

---

## Task 1: World polling hook

**Status:** ✅ Done — `useWorldSimulation.ts` + 5 passing tests.

**Files:**
- Create: `web/client/hooks/useWorldSimulation.ts`
- Create: `web/client/hooks/__tests__/useWorldSimulation.test.tsx`

Types mirror `/api/world/state`:

```typescript
export interface WorldTicket {
  id: string;
  customer_id: string;
  severity: "low" | "medium" | "high";
  required_skill: string;
  status: "queued" | "in_service" | "resolved" | "abandoned";
  assigned_worker_id: string | null;
  queued_at: number;
  sla_deadline: number;
  sla_breached: boolean;
}

export interface WorldWorker {
  id: string;
  team_id: string;
  skills: string[];
  status: string;
  current_ticket_id: string | null;
}

export interface WorldEvent {
  seq: number;
  event_id: string;
  sim_time: number;
  type: string;
  actor_id: string | null;
  target_id: string | null;
  cause_event_id: string | null;
  trace_id: string;
  payload: Record<string, unknown>;
}
```

`useWorldSimulation()`:

- fetch state immediately and every 1000ms
- fetch `/api/world/events?after=<cursor>` immediately and every 300ms
- cursor advances to response `latest_seq`
- merge by `seq`, keep newest 300 events
- return `{state, events, loading, error, injectSurge}`
- `injectSurge()` POSTs multiplier 4/duration 90, then refreshes
- cleanup both intervals and abort in-flight fetches
- no SSE, reducer framework or context

Tests with fake timers/fetch prove:

1. initial snapshot/events load
2. cursor is used on next event request
3. duplicate sequence events are not duplicated and ring stays bounded
4. injection sends exact typed payload
5. unmount aborts/cleans timers

Run:

```bash
npx vitest run web/client/hooks/__tests__/useWorldSimulation.test.tsx
```

Commit:

```bash
git add web/client/hooks/useWorldSimulation.ts web/client/hooks/__tests__/useWorldSimulation.test.tsx
git commit -m "feat(world-ui): poll actor state and causal events" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>" \
  -m "Copilot-Session: 9c29044c-2d33-401f-8e7c-a453079cf45e"
```

---

## Task 2: Actual-actor operational view

**Status:** ✅ Done — `World.tsx` + 12 passing tests.

**Files:**
- Create: `web/client/routes/World.tsx`
- Create: `web/client/routes/__tests__/World.test.tsx`

The route uses the existing full-page shell style and shows:

### Simulation header

- logical simulation time, seed and status
- actual actor counts (customers/tickets/workers) as secondary instrumentation
- one button: **Inject demand surge**
- no unrelated controls

### Ticket floor (hero)

Four lanes:

```text
WAITING          IN SERVICE         RESOLVED          ABANDONED
```

- every card is a real ticket ID from snapshot
- waiting cards show customer ID, severity, skill and wait/SLA state
- in-service cards show actual assigned worker ID
- terminal lanes show the latest 20 actual actors by transition event order
- render at most 40 waiting and 40 in-service cards for DOM performance;
  header reports true totals
- cards newly referenced by events get a brief CSS pulse keyed by event seq
- high severity/SLA breach uses existing red/amber palette

### Worker floor

- actual support workers and reserve workers, by ID
- busy workers show current ticket ID
- workers mentioned by `worker.reallocated` events pulse green and visibly
  appear in the support group because snapshot `team_id` changed
- no decorative worker movement without that journal event

### Durable intervention

When the current trace contains responder events, show one compact causal strip:

```text
Pressure detected → Responder requested → Durable decided
→ Command accepted → WRK-0035, WRK-0040 reallocated
```

Each step uses the real event ID/trace. No generated prose beyond event labels.

### Recent event journal

Newest 30 actual events with sim time, type, actor and cause ID. Clicking an
actor filters/highlights all current events for that actor/trace (local state
only; no drawer framework).

Tests mock `useWorldSimulation` and prove:

- real ticket/worker IDs render in correct lanes
- worker reallocation trace renders actual IDs
- clicking surge calls `injectSurge`
- disabled/loading/error states are explicit
- actor click filters journal
- no aggregate-only “WorldSignalsPanel” component is used

Run:

```bash
npx vitest run web/client/routes/__tests__/World.test.tsx
```

Commit:

```bash
git add web/client/routes/World.tsx web/client/routes/__tests__/World.test.tsx
git commit -m "feat(world-ui): render live tickets, workers and interventions" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>" \
  -m "Copilot-Session: 9c29044c-2d33-401f-8e7c-a453079cf45e"
```

---

## Task 3: Route/nav + remove constellation table

**Status:** ✅ Done — `/world` route + LeftRail nav wired; `WorldSignalsPanel` removed.

**Files:**
- Modify: `web/client/components/feed/FleetControlShell.tsx`
- Modify: `web/client/components/feed/LeftRail.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/CosmicLens.tsx`
- Delete: `web/blueprint/src/components/cosmicLens/HUD/WorldSignalsPanel.tsx`
- Delete: `web/blueprint/src/components/cosmicLens/HUD/__tests__/WorldSignalsPanel.test.tsx`

Changes:

- import/add `<Route path="/world" element={<World />} />`
- add primary LeftRail `Globe2` nav item labelled **World**
- collapsed rail gets matching icon link/title
- remove `WorldSignalsPanel` import/mount from cosmic lens
- delete component/test
- do not replace it with another constellation overlay

Run:

```bash
npm run build
npx vitest run \
  web/client/hooks/__tests__/useWorldSimulation.test.tsx \
  web/client/routes/__tests__/World.test.tsx
```

Commit:

```bash
git add web/client/components/feed/FleetControlShell.tsx \
  web/client/components/feed/LeftRail.tsx \
  web/blueprint/src/components/cosmicLens/CosmicLens.tsx \
  web/blueprint/src/components/cosmicLens/HUD/WorldSignalsPanel.tsx \
  web/blueprint/src/components/cosmicLens/HUD/__tests__/WorldSignalsPanel.test.tsx
git commit -m "refactor(world-ui): move simulation out of constellation HUD" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>" \
  -m "Copilot-Session: 9c29044c-2d33-401f-8e7c-a453079cf45e"
```

---

## Task 4: Real Playwright proof + docs

**Files:**
- Create: `tools/actor_world_viewer_proof.mjs`
- Create: `tools/actor_world_viewer_proof.sh`
- Modify: `docs/visualisation.md`
- Modify: `docs/ARCHITECTURE.md`

Boot the same real stack as Plan 2 plus Control Plane Vite on `:5273`.

Playwright proof:

1. Open `http://localhost:5273/world`.
2. Assert baseline real worker IDs and reserve group visible.
3. Click **Inject demand surge**.
4. Capture screenshots/video at:
   - baseline
   - queue pressure with actual ticket cards
   - Durable intervention with trace/worker IDs
   - reallocated workers in support group
   - later resolved ticket
5. Assert visible worker IDs equal Durable output command IDs.
6. Assert the intervention strip uses the same journal trace.
7. Assert no `WorldSignalsPanel` exists on `/?view=constellation`.
8. Save evidence under `tmp/actor-world-viewer-proof/`.

Use Playwright locators/test IDs on real actors/events, not screenshot-only
judgement. Fail non-zero on any mismatch.

Docs:

- `visualisation.md`: add dedicated World surface, event-backed visual rules,
  actor lanes, intervention trace and controls actually shipped (surge only).
- `ARCHITECTURE.md §15`: replace “viewer deferred” with shipped `/world`
  surface and proof command.

Final checks:

```bash
npm run build
npm test -- --run
uv run --frozen --no-sync pytest tests/api/world tests/api/routes/test_world_actor_routes.py -q
bash tools/actor_world_viewer_proof.sh
```

Commit docs and proof scripts separately after the proof passes.

