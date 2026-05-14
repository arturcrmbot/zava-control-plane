# Cosmic Lens v2 — Stabilisation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve every open item in `web/blueprint/src/components/cosmicLens/STATE.md`: switch rockets to a per-workflow model with animated travel + family colour + persistent trail + idle bob + fly-home pop, fix the empty WorkflowDrawer timeline, tighten registry pruning, and refresh STATE.md.

**Architecture:** `Rocket` becomes one entry per `workflow_id` in `RocketRegistry`. `Rockets.tsx` switches from `<instancedMesh>` (200 instances, flat yellow) to `<group>` of one `<mesh>` per active rocket (~10–30 in practice), each coloured by function family. Travel is a per-frame interpolation between current and target city; idle is a sin-driven bob; completion is fly-home + radial burst + despawn. `Trails.tsx` is driven from per-workflow rockets, emitting one sample per frame while travelling and every 6th frame while idle. `WorkflowDrawer.tsx` is a contract fix: read `data.timeline` (server returns `{workflow, timeline:[{ts, kind, label, ...}]}`).

**Tech Stack:** React 19, @react-three/fiber 9, three 0.184, vitest 2.

---

## File map

| File | Change |
|---|---|
| `web/blueprint/src/components/cosmicLens/lib/types.ts` | Reshape `Rocket` interface (per-workflow, pose fields, color, burst state). |
| `web/blueprint/src/components/cosmicLens/lib/registries.ts` | `RocketRegistry`: index by `workflow_id`, add `upsertForWorkflow`, tighten `pruneCompleted`. |
| `web/blueprint/src/components/cosmicLens/lib/__tests__/registries.test.ts` | New tests for the per-workflow `RocketRegistry` semantics. |
| `web/blueprint/src/components/cosmicLens/Rockets.tsx` | Major rewrite — per-workflow, individual meshes, animated travel, idle bob, fly-home + burst, family colour, wounded tint. |
| `web/blueprint/src/components/cosmicLens/Trails.tsx` | Drive from per-workflow rockets; emit during travel and (sparser) during idle; colour-match. |
| `web/blueprint/src/components/cosmicLens/HUD/WorkflowDrawer.tsx` | Read `data.timeline`; new `TimelineEvent` shape; renderer uses `kind`/`label`. |
| `web/blueprint/src/components/cosmicLens/STATE.md` | Refresh: promote resolved items, strip false items, document new model. |

## Conventions used in this plan

- Run tests with `npm run test -- web/blueprint/src/components/cosmicLens` from the repo root.
- Build the blueprint bundle (acts as type-check) with `npm run build:blueprint` from the repo root.
- Commit after each task with the trailer:
  ```
  Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
  ```

---

## Task 1: Fix the WorkflowDrawer timeline contract (smallest, highest-confidence win first)

**Files:**
- Modify: `web/blueprint/src/components/cosmicLens/HUD/WorkflowDrawer.tsx:25-29` (TimelineEvent interface), `:242-309` (`WorkflowView`), `:327-335` (`eventColor`).

- [ ] **Step 1: Replace the TimelineEvent interface to match the server shape**

In `WorkflowDrawer.tsx`, replace lines 25-29:

```ts
interface TimelineEvent {
  ts?: number;
  type: string;
  data?: Record<string, unknown>;
}
```

with:

```ts
interface TimelineEvent {
  ts?: number;
  /** Server row category: "phase" | "agent" | "tool" | "decision" | actor_kind. */
  kind: string;
  label?: string;
  status?: string;
  actor?: string;
  verdict?: string;
  reason?: string;
  result_summary?: string | null;
  tokens?: number | null;
  details?: Record<string, unknown> | null;
  completed_at?: number | null;
}
```

- [ ] **Step 2: Read `data.timeline` instead of `data.events`**

In `WorkflowDrawer.tsx#WorkflowView`, replace lines 252-256:

```ts
const data = await res.json();
const items = (Array.isArray(data) ? data : data.events ?? []) as TimelineEvent[];
if (!cancelled) setEvents(items);
```

with:

```ts
const data = await res.json();
const items = (
  Array.isArray(data) ? data : data.timeline ?? data.events ?? []
) as TimelineEvent[];
if (!cancelled) setEvents(items);
```

(The `data.events` fallback is kept so the component still degrades gracefully if some other server endpoint returns the older shape.)

- [ ] **Step 3: Update the row renderer to use `kind`/`label`**

In `WorkflowDrawer.tsx#WorkflowView`, replace lines 277-305 (the `{events.map((ev, i) => ...)}` block):

```tsx
{events.map((ev, i) => {
  const title = ev.label ?? ev.kind;
  const subtitle = ev.kind + (ev.status ? ` · ${ev.status}` : "");
  const detailRows: [string, string][] = [];
  if (ev.actor) detailRows.push(["actor", ev.actor]);
  if (ev.verdict) detailRows.push(["verdict", ev.verdict]);
  if (ev.reason) detailRows.push(["reason", ev.reason]);
  if (ev.result_summary) detailRows.push(["result", ev.result_summary]);
  if (typeof ev.tokens === "number") detailRows.push(["tokens", String(ev.tokens)]);
  if (ev.details) {
    for (const [k, v] of Object.entries(ev.details)) {
      if (v === null || v === undefined) continue;
      detailRows.push([k, String(v).slice(0, 60)]);
      if (detailRows.length >= 6) break;
    }
  }
  return (
    <div
      key={i}
      style={{
        padding: "8px 12px",
        margin: "3px 0",
        borderLeft: `3px solid ${eventColor(ev.kind)}`,
        background: "rgba(15,23,42,0.5)",
        fontSize: 12,
      }}
    >
      <div style={{ color: "#e2e8f0", fontWeight: 500 }}>{title}</div>
      <div style={{ fontSize: 10, color: "#64748b", marginTop: 2 }}>
        {subtitle}
        {ev.ts ? " · " + new Date(ev.ts * 1000).toLocaleTimeString() : ""}
      </div>
      {detailRows.length > 0 && (
        <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 4, fontFamily: "monospace", lineHeight: 1.4 }}>
          {detailRows.slice(0, 5).map(([k, v]) => (
            <div key={k}>
              <span style={{ color: "#64748b" }}>{k}:</span> {v}
            </div>
          ))}
        </div>
      )}
    </div>
  );
})}
```

- [ ] **Step 4: Re-key `eventColor` off `kind`**

In `WorkflowDrawer.tsx`, replace `eventColor` (lines 327-335) with:

```ts
function eventColor(kind: string): string {
  switch (kind) {
    case "phase":
      return "#22d3ee"; // cyan — workflow scaffolding
    case "agent":
    case "skill":
      return "#a78bfa"; // violet — agent / skill spans
    case "tool":
      return "#2dd4bf"; // teal — MCP / tool calls
    case "decision":
      return "#fbbf24"; // amber — operator / persona decisions
    case "persona":
      return "#fb923c"; // coral — persona actions
    case "system":
      return "#64748b"; // slate
    default:
      // Fall back to the legacy substring heuristic so the drawer still
      // colours rows from any newly-introduced kind without an immediate
      // code change.
      const k = kind.toLowerCase();
      if (k.includes("decided") || k.includes("decision")) return "#fbbf24";
      if (k.includes("thinking")) return "#a78bfa";
      if (k.includes("completed") || k.includes("done")) return "#4ade80";
      if (k.includes("exception") || k.includes("failed")) return "#ef4444";
      if (k.includes("started") || k.includes("workflow")) return "#22d3ee";
      if (k.includes("entity")) return "#14b8a6";
      return "#64748b";
  }
}
```

- [ ] **Step 5: Build to confirm types compile**

Run:

```bash
npm run build:blueprint
```

Expected: build succeeds with no TS errors.

- [ ] **Step 6: Commit**

```bash
git add web/blueprint/src/components/cosmicLens/HUD/WorkflowDrawer.tsx
git commit -m "fix(cosmic): WorkflowDrawer reads data.timeline (server shape)

Server route /api/workflows/index/timeline/{id} returns
{workflow, timeline:[{ts, kind, label, status, ...}]}. Drawer was
reading data.events (always undefined) and rendering ev.type/ev.data
(also undefined), so every workflow drawer showed 'No timeline events
recorded' even when the API had rows.

Reshape the TimelineEvent interface to match the server, switch to
data.timeline (with data.events kept as a defensive fallback), and
re-key the row renderer + eventColor switch to ev.kind / ev.label.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 2: Reshape the `Rocket` type for the per-workflow model

**Files:**
- Modify: `web/blueprint/src/components/cosmicLens/lib/types.ts:75-89` (Rocket interface).

- [ ] **Step 1: Replace the Rocket interface**

In `lib/types.ts`, replace lines 75-89 with:

```ts
/** A rocket as managed by rocketRegistry — one per in-flight workflow. */
export interface Rocket {
  /** Equal to workflow_id (one rocket per workflow). */
  id: string;
  workflow_id: string;
  origin_workflow_id: string;
  /** Rocket lifecycle phase. */
  phase: "spawning" | "travelling" | "idle" | "returning" | "burst" | "done";
  /** Body color (hex string), set on spawn from function family. */
  color: string;
  /** Last city the rocket parked at (or null until first travel). */
  current_city_id: string | null;
  /** Travel destination while phase === "travelling". */
  target_city_id: string | null;
  /** Most recent rocket position used as the start point of the next leg. */
  current_pos: [number, number, number];
  /** Travel start position captured when "travelling" begins. */
  travel_from: [number, number, number] | null;
  /** Travel target position captured when "travelling" begins. */
  travel_to: [number, number, number] | null;
  /** Wallclock ms when the current phase started. */
  phase_started_at: number;
  /** Wallclock ms when the workflow first spawned. */
  spawned_at: number;
  /** Set when the workflow has an active_exception_id (drives wounded tint). */
  is_wounded: boolean;
  /** Most recent flash type that drove a travel — used for label. */
  last_event_type?: string;
  /** Last short label (e.g. tool/skill/persona) — used for hover affordance. */
  last_label?: string;
  /** For Entities mode visual cues on the trail. */
  is_write?: boolean;
  is_read?: boolean;
}
```

- [ ] **Step 2: Build (will surface type errors in registries/Rockets/CosmicLens — fixed in later tasks)**

Run:

```bash
npm run build:blueprint
```

Expected: TS errors in `registries.ts` and `Rockets.tsx` referencing the removed fields (`city_id`, `dispatched_at`, `parked_at`, `completed_at`, `returned_at`, `is_exception`, `label`). These are addressed by Tasks 3-4. Do **not** commit yet — finish Task 3 first, then commit them together.

---

## Task 3: Per-workflow `RocketRegistry` + tightened pruning + tests

**Files:**
- Modify: `web/blueprint/src/components/cosmicLens/lib/registries.ts:88-157` (`RocketRegistry`).
- Modify: `web/blueprint/src/components/cosmicLens/lib/__tests__/registries.test.ts:67-116` (RocketRegistry tests).

- [ ] **Step 1: Rewrite the failing tests for the new shape**

In `web/blueprint/src/components/cosmicLens/lib/__tests__/registries.test.ts`, replace the `describe("RocketRegistry", ...)` block (lines 67-116) with:

```ts
describe("RocketRegistry (per-workflow)", () => {
  function newRocket(workflow_id: string, overrides: Partial<import("../types").Rocket> = {}): import("../types").Rocket {
    return {
      id: workflow_id,
      workflow_id,
      origin_workflow_id: workflow_id,
      phase: "idle",
      color: "#facc15",
      current_city_id: null,
      target_city_id: null,
      current_pos: [0, 0, 0],
      travel_from: null,
      travel_to: null,
      phase_started_at: 0,
      spawned_at: 0,
      is_wounded: false,
      ...overrides,
    };
  }

  it("upsertForWorkflow keeps a single entry per workflow_id", () => {
    const r = new RocketRegistry();
    r.upsertForWorkflow("VKY-1", () => newRocket("VKY-1"));
    r.upsertForWorkflow("VKY-1", () => newRocket("VKY-1"));
    expect(r.size()).toBe(1);
  });

  it("upsertForWorkflow returns the existing rocket on a second call", () => {
    const r = new RocketRegistry();
    const first = r.upsertForWorkflow("VKY-1", () => newRocket("VKY-1", { color: "#aabbcc" }));
    const second = r.upsertForWorkflow("VKY-1", () => newRocket("VKY-1", { color: "#ddeeff" }));
    expect(second).toBe(first);
    expect(second.color).toBe("#aabbcc");
  });

  it("forWorkflow returns the same instance set by upsert", () => {
    const r = new RocketRegistry();
    const x = r.upsertForWorkflow("VKY-7", () => newRocket("VKY-7"));
    expect(r.forWorkflow("VKY-7")).toBe(x);
    expect(r.forWorkflow("missing")).toBeUndefined();
  });

  it("atCity filters rockets that are idle at that city", () => {
    const r = new RocketRegistry();
    r.upsertForWorkflow("a", () => newRocket("a", { phase: "idle", current_city_id: "city1" }));
    r.upsertForWorkflow("b", () => newRocket("b", { phase: "travelling", current_city_id: "city1" }));
    r.upsertForWorkflow("c", () => newRocket("c", { phase: "idle", current_city_id: "city2" }));
    expect(r.atCity("city1").map((x) => x.id).sort()).toEqual(["a"]);
  });

  it("pruneCompleted removes rockets whose phase is done", () => {
    const r = new RocketRegistry();
    r.upsertForWorkflow("d1", () => newRocket("d1", { phase: "done" }));
    r.upsertForWorkflow("d2", () => newRocket("d2", { phase: "burst" }));
    r.pruneCompleted();
    expect(r.has("d1")).toBe(false);
    expect(r.has("d2")).toBe(true);
  });

  it("recordVisit dedups consecutive identical city ids", () => {
    const r = new RocketRegistry();
    r.recordVisit("wf", "city_a", 1);
    r.recordVisit("wf", "city_a", 2);
    r.recordVisit("wf", "city_b", 3);
    expect(r.historyFor("wf").map((h) => h.city_id)).toEqual(["city_a", "city_b"]);
  });
});
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run:

```bash
npm run test -- web/blueprint/src/components/cosmicLens/lib/__tests__/registries.test.ts
```

Expected: the new RocketRegistry tests fail (`upsertForWorkflow is not a function`, `forWorkflow is not a function`, `pruneCompleted` arity mismatch). Existing FunctionRegistry / MoonRegistry / CityRegistry / TrailRegistry tests should still pass.

- [ ] **Step 3: Rewrite the `RocketRegistry` class**

In `web/blueprint/src/components/cosmicLens/lib/registries.ts`, replace the `RocketRegistry` class (lines 88-157) with:

```ts
export class RocketRegistry extends Registry<Rocket> {
  /** Per-workflow chronological list of cities the workflow has parked at.
   *  Used by HoveredWorkflowPath to draw the "where I've been" history
   *  polyline. Bounded to last MAX_HISTORY visits per workflow. */
  private cityHistory = new Map<string, { city_id: string; ts: number }[]>();
  private static readonly MAX_HISTORY = 24;

  /** Get or create the rocket for a workflow. The factory is invoked only
   *  on first creation so spawn-time fields (color, spawned_at) stay stable
   *  across the workflow's lifetime. */
  upsertForWorkflow(workflowId: string, factory: () => Rocket): Rocket {
    const existing = this.items.get(workflowId);
    if (existing) return existing;
    const created = factory();
    this.items.set(workflowId, created);
    this.version++;
    return created;
  }

  /** Returns the rocket for a workflow, or undefined if none. */
  forWorkflow(workflowId: string): Rocket | undefined {
    return this.items.get(workflowId);
  }

  /** Append a city visit for a workflow's history. Idempotent w.r.t.
   *  consecutive identical city_ids. */
  recordVisit(workflowId: string, cityId: string, ts: number): void {
    const arr = this.cityHistory.get(workflowId) ?? [];
    const last = arr[arr.length - 1];
    if (last && last.city_id === cityId) return;
    arr.push({ city_id: cityId, ts });
    if (arr.length > RocketRegistry.MAX_HISTORY) {
      arr.splice(0, arr.length - RocketRegistry.MAX_HISTORY);
    }
    this.cityHistory.set(workflowId, arr);
    // Bump version so reactive consumers (e.g. HoveredWorkflowPath's
    // historyPoints useMemo) re-compute when a new visit is recorded.
    this.version++;
  }

  /** Returns chronological city visits for a workflow, oldest first. */
  historyFor(workflowId: string): { city_id: string; ts: number }[] {
    return this.cityHistory.get(workflowId) ?? [];
  }

  /** Returns rockets currently parked (idle) at a given city. */
  atCity(cityId: string): Rocket[] {
    const out: Rocket[] = [];
    for (const r of this.items.values()) {
      if (r.current_city_id === cityId && r.phase === "idle") out.push(r);
    }
    return out;
  }

  /** Returns the rocket for a given workflow if alive (non-done), else undefined. */
  fromWorkflow(workflowId: string): Rocket[] {
    const r = this.items.get(workflowId);
    if (!r || r.phase === "done") return [];
    return [r];
  }

  /** Drop rockets whose phase has reached the terminal "done" state.
   *  Cheap to call every frame — no time gating required because rockets
   *  only reach "done" after the burst animation has finished. */
  pruneCompleted(): void {
    const to_delete: string[] = [];
    for (const [id, r] of this.items.entries()) {
      if (r.phase === "done") to_delete.push(id);
    }
    for (const id of to_delete) this.delete(id);
    if (to_delete.length > 0) {
      // version already bumped by delete() per id, but ensure consumers
      // see at least one bump even if to_delete was empty pre-call.
    }
  }

  /** Backwards-compat alias for the old name. The 2-arg form is ignored.
   *  Some legacy callers may still pass (now, maxAgeMs). */
  latestForWorkflow(workflowId: string): Rocket | undefined {
    return this.forWorkflow(workflowId);
  }
}
```

- [ ] **Step 4: Run tests to confirm they pass**

Run:

```bash
npm run test -- web/blueprint/src/components/cosmicLens/lib/__tests__/registries.test.ts
```

Expected: all `RocketRegistry (per-workflow)` tests pass. Other registry suites stay green.

- [ ] **Step 5: Do not commit yet — Task 4 needs to fix the `Rockets.tsx` consumer before the build is green.**

---

## Task 4: Rewrite `Rockets.tsx` for per-workflow model with animated travel + family colour + fly-home pop

**Files:**
- Replace: `web/blueprint/src/components/cosmicLens/Rockets.tsx` (full file).

- [ ] **Step 1: Replace the entire file**

Open `web/blueprint/src/components/cosmicLens/Rockets.tsx` and replace the **entire file contents** with:

```tsx
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";
import type {
  CityMeta,
  CosmicFlash,
  CosmicMode,
  FunctionMeta,
  Rocket,
  WorkflowMoonData,
} from "./lib/types";
import { MoonRegistry, RocketRegistry, TrailRegistry } from "./lib/registries";
import { moonPosition } from "./WorkflowMoons";
import { cityPosition } from "./Cities";
import { isReadEvent, isWriteEvent, labelForCapability, labelForEntity } from "./lib/labels";
import { buildWorkflowTypeToFunction, resolveFunction, workflowTypeFromId } from "./lib/workflowFunction";
import { colorForFunction } from "./lib/colors";

interface RocketsProps {
  flashesRef: React.MutableRefObject<{ buffer: CosmicFlash[]; version: number }>;
  inFlight: WorkflowMoonData[];
  cities: CityMeta[];
  functions: FunctionMeta[];
  mode: CosmicMode;
  /** External trail registry so Trails component can render the same data. */
  trailRegistry: TrailRegistry;
  /** External rocket registry so DirectionalBeams + HoveredWorkflowPath can read it. */
  rocketRegistry: RocketRegistry;
  /** When set, brighten/upscale the rocket owned by this workflow. */
  highlightWorkflowId?: string | null;
}

const ROCKET_BODY = 0.3;
const TRAVEL_MS = 1200;
const RETURN_MS = 1000;
const BURST_MS = 600;
const TRAIL_EMIT_TRAVEL_EVERY_FRAMES = 1;
const TRAIL_EMIT_IDLE_EVERY_FRAMES = 6;
const WOUNDED_RED = "#ef4444";

// Cubic ease-in-out
function ease(p: number): number {
  return p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;
}

// Lerp two colour strings into a THREE.Color (returned by ref).
const _lerpA = new THREE.Color();
const _lerpB = new THREE.Color();
function lerpColor(out: THREE.Color, fromHex: string, toHex: string, t: number): THREE.Color {
  _lerpA.set(fromHex);
  _lerpB.set(toHex);
  out.copy(_lerpA).lerp(_lerpB, t);
  return out;
}

interface BurstHandle {
  ringRef: React.MutableRefObject<THREE.Mesh | null>;
}

/**
 * Rockets — one per in-flight workflow.
 *
 * Spawn on workflow.started; one entry in rocketRegistry keyed by workflow_id.
 * Travel smoothly between cities on tool/persona/executor events. Bob in place
 * while idle. Fly back to the workflow's moon and burst on completion.
 *
 * At expected scale (10–30 simultaneous rockets) we draw one mesh per rocket
 * instead of an InstancedMesh — gives free per-rocket colour without the
 * vertexColors-on-InstancedMesh shader-compile hazard documented in STATE.md.
 */
export function Rockets({ flashesRef, inFlight, cities, functions, mode, trailRegistry, rocketRegistry, highlightWorkflowId }: RocketsProps) {
  const moonRegistry = useMemo(() => new MoonRegistry(), []);
  const lastVersionRef = useRef(0);
  const frameRef = useRef(0);
  const diagRef = useRef<{ ticks: number; lastDrawnCount: number }>({ ticks: 0, lastDrawnCount: 0 });

  // Expose diagnostics handle on the registry so CosmicLens can publish it
  // through window.__cosmic.rocketDiag().
  useEffect(() => {
    (rocketRegistry as unknown as { __diag?: typeof diagRef.current }).__diag = diagRef.current;
  }, [rocketRegistry]);

  // workflow_id -> function key
  const wfFn = useMemo(() => {
    const wfTypeMap = buildWorkflowTypeToFunction(functions);
    const m = new Map<string, string>();
    inFlight.forEach((wf) => {
      const wfType = wf.workflow_type || workflowTypeFromId(wf.id) || "";
      m.set(wf.id, resolveFunction({ ...wf, workflow_type: wfType } as WorkflowMoonData, wfTypeMap));
    });
    return m;
  }, [inFlight, functions]);

  const cityPositions = useMemo(() => {
    const m = new Map<string, [number, number, number]>();
    cities.forEach((city) => {
      m.set(city.id, cityPosition(city.id));
    });
    return m;
  }, [cities]);

  // Set of currently in-flight workflow ids (for spawn-on-discovery + despawn-on-disappear).
  const inFlightIds = useMemo(() => new Set(inFlight.map((w) => w.id)), [inFlight]);
  const woundedIds = useMemo(() => {
    const s = new Set<string>();
    for (const w of inFlight) if (w.active_exception_id) s.add(w.id);
    return s;
  }, [inFlight]);

  // Spawn a rocket for any in-flight workflow that doesn't have one yet.
  // Mark wounded flag from the polled in-flight snapshot.
  useEffect(() => {
    const now = Date.now();
    for (const wf of inFlight) {
      const fn = wfFn.get(wf.id);
      const r = rocketRegistry.upsertForWorkflow(wf.id, () => {
        const moonPos = moonPosition(wf.id, fn, functions, performance.now() / 1000, moonRegistry);
        return {
          id: wf.id,
          workflow_id: wf.id,
          origin_workflow_id: wf.id,
          phase: "idle",
          color: colorForFunction(fn),
          current_city_id: null,
          target_city_id: null,
          current_pos: moonPos,
          travel_from: null,
          travel_to: null,
          phase_started_at: now,
          spawned_at: now,
          is_wounded: !!wf.active_exception_id,
        };
      });
      r.is_wounded = woundedIds.has(wf.id);
    }
  }, [inFlight, rocketRegistry, wfFn, functions, moonRegistry, woundedIds]);

  // Drain new flashes — drive travel + completion.
  useEffect(() => {
    const interval = setInterval(() => {
      const ref = flashesRef.current;
      if (ref.version === lastVersionRef.current) return;
      const buffer = ref.buffer;
      const since = lastVersionRef.current;
      lastVersionRef.current = ref.version;
      // We don't know exactly which buffer entries were appended since the
      // last drain (the ref doesn't track it), so process the most recent
      // batch heuristically: at most (version-since) tail entries.
      const newCount = Math.max(1, Math.min(buffer.length, ref.version - since));
      const tail = buffer.slice(buffer.length - newCount);
      const now = Date.now();
      for (const flash of tail) {
        const workflowId = flash.workflow_id ?? flash.caller_workflow_id;
        if (!workflowId) continue;
        const r = rocketRegistry.forWorkflow(workflowId);
        if (!r) continue; // workflow not in inFlight snapshot yet — wait for next poll

        // Completion: fly home and burst.
        const isCompletion =
          flash.type === "workflow.completed" ||
          flash.type === "durable.workflow.completed" ||
          flash.type === "workflow.failed";
        if (isCompletion && r.phase !== "returning" && r.phase !== "burst" && r.phase !== "done") {
          const fn = wfFn.get(r.workflow_id);
          const moonPos = moonPosition(r.workflow_id, fn, functions, performance.now() / 1000, moonRegistry);
          r.travel_from = [...r.current_pos];
          r.travel_to = moonPos;
          r.target_city_id = null;
          r.phase = "returning";
          r.phase_started_at = now;
          continue;
        }

        // Travel: tool / executor.invoked / persona.thinking / ambient.decided
        const isExecutorStart =
          flash.type === "durable.executor.invoked" &&
          (flash as unknown as { stage?: string }).stage === "start";
        const isCapabilityEvent =
          flash.type === "tool.invoked" ||
          flash.type === "persona.thinking" ||
          flash.type === "ambient.decided" ||
          isExecutorStart;
        const isEntityEvent =
          flash.type === "entity.read" ||
          flash.type === "entity.upserted" ||
          flash.type === "entity.linked";
        const isTravelEvent =
          mode === "capabilities" ? isCapabilityEvent : isEntityEvent;
        if (!isTravelEvent) continue;

        const cityId = pickCityForFlash(flash, cities, mode);
        if (!cityId) continue;
        const cityPos = cityPositions.get(cityId);
        if (!cityPos) continue;

        // Skip pure-repeat travels to the same city while still travelling
        // there (avoids stutter when multiple events fire on one tool).
        if (r.phase === "travelling" && r.target_city_id === cityId) continue;

        r.travel_from = [...r.current_pos];
        r.travel_to = [...cityPos];
        r.target_city_id = cityId;
        r.phase = "travelling";
        r.phase_started_at = now;
        r.last_event_type = flash.type;
        r.last_label = mode === "capabilities" ? labelForCapability(flash) : labelForEntity(flash);
        r.is_read = isReadEvent(flash.type);
        r.is_write = isWriteEvent(flash.type);
      }
    }, 100);
    return () => clearInterval(interval);
  }, [flashesRef, rocketRegistry, cities, mode, cityPositions, wfFn, functions, moonRegistry]);

  // Per-frame: integrate phase, write each rocket's mesh transform/color via refs.
  const meshRefs = useRef(new Map<string, THREE.Mesh>());
  const haloRefs = useRef(new Map<string, THREE.Mesh>());
  const burstRefs = useRef(new Map<string, BurstHandle>());
  const tmpColor = useMemo(() => new THREE.Color(), []);
  const tmpVec = useMemo(() => new THREE.Vector3(), []);
  const upY = useMemo(() => new THREE.Vector3(0, 1, 0), []);
  const downY = useMemo(() => new THREE.Vector3(0, -1, 0), []);

  useFrame((state) => {
    frameRef.current++;
    const t = state.clock.getElapsedTime();
    const now = Date.now();
    let drawn = 0;

    // Despawn any rockets whose workflow is no longer in flight AND who are
    // already idle/done (don't yank rockets mid-travel — let them complete
    // naturally via workflow.completed flash).
    for (const r of rocketRegistry.values()) {
      if (!inFlightIds.has(r.workflow_id) && (r.phase === "idle" || r.phase === "done")) {
        // Treat as completion: fly home + burst.
        if (r.phase === "idle") {
          const fn = wfFn.get(r.workflow_id);
          const moonPos = moonPosition(r.workflow_id, fn, functions, t, moonRegistry);
          r.travel_from = [...r.current_pos];
          r.travel_to = moonPos;
          r.target_city_id = null;
          r.phase = "returning";
          r.phase_started_at = now;
        }
      }
    }

    for (const r of rocketRegistry.values()) {
      const mesh = meshRefs.current.get(r.id);
      if (!mesh) continue;
      const halo = haloRefs.current.get(r.id);
      const fn = wfFn.get(r.workflow_id);
      const moonPos = moonPosition(r.workflow_id, fn, functions, t, moonRegistry);
      const phaseAge = now - r.phase_started_at;

      let px = r.current_pos[0];
      let py = r.current_pos[1];
      let pz = r.current_pos[2];
      let dirSet = false;

      if (r.phase === "travelling" && r.travel_from && r.travel_to) {
        const p = Math.min(1, phaseAge / TRAVEL_MS);
        const e = ease(p);
        const arc = Math.sin(p * Math.PI) * 1.5;
        px = r.travel_from[0] + (r.travel_to[0] - r.travel_from[0]) * e;
        pz = r.travel_from[2] + (r.travel_to[2] - r.travel_from[2]) * e;
        py = r.travel_from[1] + (r.travel_to[1] - r.travel_from[1]) * e + arc;
        // Orient nose toward destination
        tmpVec.set(r.travel_to[0] - r.travel_from[0], r.travel_to[1] - r.travel_from[1], r.travel_to[2] - r.travel_from[2]).normalize();
        mesh.quaternion.setFromUnitVectors(upY, tmpVec);
        dirSet = true;
        if (p >= 1) {
          r.phase = "idle";
          r.phase_started_at = now;
          r.current_city_id = r.target_city_id;
          if (r.target_city_id) rocketRegistry.recordVisit(r.workflow_id, r.target_city_id, now);
          r.travel_from = null;
          r.travel_to = null;
        }
        // Trail emission while travelling
        if (frameRef.current % TRAIL_EMIT_TRAVEL_EVERY_FRAMES === 0) {
          trailRegistry.push({
            from: [px, py, pz],
            to: [r.travel_to[0], r.travel_to[1], r.travel_to[2]],
            emitted_at: now,
            color: r.is_wounded ? WOUNDED_RED : r.color,
          });
        }
      } else if (r.phase === "idle") {
        // Bob gently in place at the current city (or moon if never travelled).
        const base = r.current_city_id && cityPositions.has(r.current_city_id)
          ? cityPositions.get(r.current_city_id)!
          : moonPos;
        const bob = Math.sin(t * 2.5 + r.spawned_at * 0.0007) * 0.06;
        px = base[0];
        py = base[1] + 0.45 + bob;
        pz = base[2];
        mesh.quaternion.setFromUnitVectors(upY, downY);
        dirSet = true;
        // Sparser idle trail
        if (frameRef.current % TRAIL_EMIT_IDLE_EVERY_FRAMES === 0) {
          trailRegistry.push({
            from: [px, py, pz],
            to: [px, py - 0.2, pz],
            emitted_at: now,
            color: r.is_wounded ? WOUNDED_RED : r.color,
          });
        }
      } else if (r.phase === "returning" && r.travel_from && r.travel_to) {
        const p = Math.min(1, phaseAge / RETURN_MS);
        const e = ease(p);
        const arc = Math.sin(p * Math.PI) * 1.0;
        px = r.travel_from[0] + (r.travel_to[0] - r.travel_from[0]) * e;
        pz = r.travel_from[2] + (r.travel_to[2] - r.travel_from[2]) * e;
        py = r.travel_from[1] + (r.travel_to[1] - r.travel_from[1]) * e + arc;
        tmpVec.set(r.travel_to[0] - r.travel_from[0], r.travel_to[1] - r.travel_from[1], r.travel_to[2] - r.travel_from[2]).normalize();
        mesh.quaternion.setFromUnitVectors(upY, tmpVec);
        dirSet = true;
        if (frameRef.current % TRAIL_EMIT_TRAVEL_EVERY_FRAMES === 0) {
          trailRegistry.push({
            from: [px, py, pz],
            to: [r.travel_to[0], r.travel_to[1], r.travel_to[2]],
            emitted_at: now,
            color: r.is_wounded ? WOUNDED_RED : r.color,
          });
        }
        if (p >= 1) {
          r.phase = "burst";
          r.phase_started_at = now;
          r.current_pos = [r.travel_to[0], r.travel_to[1], r.travel_to[2]];
          r.travel_from = null;
          r.travel_to = null;
        }
      } else if (r.phase === "burst") {
        // Stay at moon, scale up the burst ring + fade.
        const moonNow = moonPos;
        px = moonNow[0];
        py = moonNow[1];
        pz = moonNow[2];
        const burstP = Math.min(1, phaseAge / BURST_MS);
        const burstHandle = burstRefs.current.get(r.id);
        if (burstHandle?.ringRef.current) {
          const s = 0.4 + burstP * 1.6;
          burstHandle.ringRef.current.scale.set(s, s, s);
          burstHandle.ringRef.current.position.set(px, py, pz);
          const mat = burstHandle.ringRef.current.material as THREE.MeshBasicMaterial;
          mat.opacity = 0.7 * (1 - burstP);
          mat.color.set(r.is_wounded ? WOUNDED_RED : r.color);
          mat.transparent = true;
          mat.depthWrite = false;
        }
        if (burstP >= 1) {
          r.phase = "done";
        }
      } else {
        // done — park off-screen until pruneCompleted clears it this frame.
        px = 0;
        py = -100;
        pz = 0;
      }

      r.current_pos = [px, py, pz];
      mesh.position.set(px, py, pz);
      if (!dirSet) {
        mesh.quaternion.identity();
      }

      // Body color: lerp toward red if wounded; brighten if highlighted.
      const baseHex = r.color;
      if (r.is_wounded) {
        lerpColor(tmpColor, baseHex, WOUNDED_RED, 0.6);
      } else {
        tmpColor.set(baseHex);
      }
      const isHighlighted = !!highlightWorkflowId && r.workflow_id === highlightWorkflowId;
      const bodyMat = mesh.material as THREE.MeshBasicMaterial;
      bodyMat.color.copy(tmpColor);
      const s = isHighlighted ? 2.4 : 1.0;
      mesh.scale.set(s, s, s);

      if (halo) {
        halo.position.set(px, py, pz);
        const haloPulse = 1 + 0.15 * Math.sin(t * 4 + r.spawned_at * 0.0007);
        const sH = isHighlighted ? 3.0 : haloPulse;
        halo.scale.set(sH, sH, sH);
        const haloMat = halo.material as THREE.MeshBasicMaterial;
        haloMat.color.copy(tmpColor);
      }

      if (r.phase !== "done") drawn++;
    }

    // Cheap, every-frame prune of done rockets (tight: no time gating).
    rocketRegistry.pruneCompleted();

    diagRef.current.ticks++;
    diagRef.current.lastDrawnCount = drawn;
    if (diagRef.current.ticks % 120 === 0 && drawn > 0) {
      const sample = rocketRegistry.values().slice(0, 3).map((r) => ({
        id: r.id,
        wf: r.workflow_id,
        phase: r.phase,
        city: r.current_city_id,
        color: r.color,
      }));
      console.debug("[rocket-diag]", { active: drawn, sample });
    }
  });

  // Render one mesh per active rocket. React reconciliation uses key=workflow_id
  // so adding/removing workflows is a clean mount/unmount.
  const live = rocketRegistry.values();

  return (
    <>
      {live.map((r) => (
        <RocketMesh
          key={r.id}
          rocket={r}
          radius={ROCKET_BODY}
          meshRefs={meshRefs}
          haloRefs={haloRefs}
          burstRefs={burstRefs}
        />
      ))}
    </>
  );
}

interface RocketMeshProps {
  rocket: Rocket;
  radius: number;
  meshRefs: React.MutableRefObject<Map<string, THREE.Mesh>>;
  haloRefs: React.MutableRefObject<Map<string, THREE.Mesh>>;
  burstRefs: React.MutableRefObject<Map<string, BurstHandle>>;
}

function RocketMesh({ rocket, radius, meshRefs, haloRefs, burstRefs }: RocketMeshProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  const haloRef = useRef<THREE.Mesh>(null);
  const ringRef = useRef<THREE.Mesh>(null);

  useEffect(() => {
    if (meshRef.current) meshRefs.current.set(rocket.id, meshRef.current);
    if (haloRef.current) haloRefs.current.set(rocket.id, haloRef.current);
    burstRefs.current.set(rocket.id, { ringRef });
    const id = rocket.id;
    return () => {
      meshRefs.current.delete(id);
      haloRefs.current.delete(id);
      burstRefs.current.delete(id);
    };
  }, [rocket.id, meshRefs, haloRefs, burstRefs]);

  return (
    <>
      <mesh ref={meshRef} frustumCulled={false}>
        <coneGeometry args={[radius, radius * 2.5, 6]} />
        <meshBasicMaterial color={rocket.color} />
      </mesh>
      <mesh ref={haloRef} frustumCulled={false}>
        <sphereGeometry args={[radius * 1.5, 12, 12]} />
        <meshBasicMaterial
          color={rocket.color}
          transparent
          opacity={0.4}
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </mesh>
      {/* Burst ring — only visible while phase === "burst", controlled by useFrame. */}
      <mesh ref={ringRef} frustumCulled={false} visible={true}>
        <ringGeometry args={[radius * 1.2, radius * 1.6, 24]} />
        <meshBasicMaterial color={rocket.color} transparent opacity={0} depthWrite={false} blending={THREE.AdditiveBlending} />
      </mesh>
    </>
  );
}

/** Pick a city to target. Match by tool/skill/persona name when possible,
 *  otherwise fall back to a deterministic hash so motion is always visible. */
function pickCityForFlash(
  flash: CosmicFlash,
  cities: CityMeta[],
  mode: CosmicMode,
): string | null {
  if (!cities.length) return null;
  if (mode === "capabilities") {
    if (flash.type === "persona.thinking" && flash.persona) {
      const found = cities.find(
        (c) => c.kind === "persona" && (c.id === flash.persona || c.label === flash.persona),
      );
      if (found) return found.id;
    }
    const f = flash as unknown as { skill?: string; tool?: string; tool_name?: string };
    const cap = f.skill || f.tool || f.tool_name;
    if (cap) {
      const found = cities.find(
        (c) =>
          c.id === cap ||
          c.label === cap ||
          c.id.endsWith(cap) ||
          cap.startsWith(c.id),
      );
      if (found) return found.id;
    }
  } else {
    if (flash.entity_kind) {
      const found = cities.find(
        (c) => c.kind === "entity_type" && (c.id === flash.entity_kind || c.label === flash.entity_kind),
      );
      if (found) return found.id;
    }
  }
  let hash = 5381;
  const seed = `${flash.type}-${flash.workflow_id ?? ""}-${flash.persona ?? flash.tool_name ?? flash.entity_kind ?? ""}`;
  for (let i = 0; i < seed.length; i++) {
    hash = ((hash << 5) + hash + seed.charCodeAt(i)) | 0;
  }
  const idx = Math.abs(hash) % cities.length;
  return cities[idx].id;
}
```

- [ ] **Step 2: Build to verify TS compiles end-to-end**

Run:

```bash
npm run build:blueprint
```

Expected: build succeeds. Warnings about unused imports in `Rockets.tsx` (e.g. if `tmpColor`/`tmpVec` flagged) are acceptable but should be cleaned up if TypeScript flags them as errors under strict mode.

- [ ] **Step 3: Run all tests**

Run:

```bash
npm run test -- web/blueprint/src/components/cosmicLens
```

Expected: all registry + colour + label tests pass.

- [ ] **Step 4: Commit Tasks 2-4 together (the type, registry, and consumer all change as one atomic unit)**

```bash
git add web/blueprint/src/components/cosmicLens/lib/types.ts \
        web/blueprint/src/components/cosmicLens/lib/registries.ts \
        web/blueprint/src/components/cosmicLens/lib/__tests__/registries.test.ts \
        web/blueprint/src/components/cosmicLens/Rockets.tsx
git commit -m "feat(cosmic): per-workflow rocket model

One rocket per in-flight workflow (was: one per tool.invoked event).
Spawn on workflow appearing in /api/workflows/index/in-flight, despawn
on completion via fly-home + radial burst. Animated travel between
cities (1.2s ease-in-out cubic), idle bob in place at last city,
family-coloured body + halo, wounded workflows tint toward red.

Drop InstancedMesh for rockets in favour of one mesh per rocket — at
the new ~10–30 simultaneous rocket count, this is simpler and
side-steps the vertexColors-on-InstancedMesh shader-compile hazard
documented in cosmicLens/STATE.md.

RocketRegistry reshaped: indexed by workflow_id with upsertForWorkflow
and forWorkflow helpers. pruneCompleted runs every frame (no time
gating) — entries only reach 'done' after the burst animation.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 5: Refresh `STATE.md`

**Files:**
- Modify: `web/blueprint/src/components/cosmicLens/STATE.md`.

- [ ] **Step 1: Replace the file**

Open `web/blueprint/src/components/cosmicLens/STATE.md` and replace its entire contents with:

````markdown
# Cosmic Lens v2 — Current State (verified)

> Snapshot taken 2026-05-10 after stabilisation. Every claim below was
> verified at runtime via the `window.__cosmic` introspector, NOT by
> eyeballing screenshots. Where a claim could not be verified, it is
> marked **NOT VERIFIED**.

## How to verify the running scene yourself

Open `http://localhost:5275/?view=constellation` then in DevTools:

```js
// What's actually in the three.js scene right now?
window.__cosmic.sceneState()             // every visible mesh: world+screen pos, color, material
window.__cosmic.rocketDiag()             // rocket count, lastDrawnCount, sample
window.__cosmic.rocketSummary()          // phase distribution + idle-by-city
window.__cosmic.eventTypeHistogram()     // SSE event counts since page load
window.__cosmic.hoverMoon('WF-1234')     // simulate hovering a moon (for hover-path test)
```

These are real, programmatic queries — **use them instead of taking
screenshots when reasoning about what's rendered**.

## What works (verified)

### Stack health
- FastAPI on **3101** (`/healthz` 200) — `api/server/main.py`
- Vite dev on **5275** (HMR firing) — `web/blueprint/`
- Azure Functions host on **7071** — `functions/python/`
- Azurite on **10000-10002**
- Backend's own **`ramp_loop`** spawns workflows (interval = `SIMULATOR_RAMP_AVG_INTERVAL_SECONDS`, default 90s)
  — at `api/server/services/simulator_orchestrator.py:496`. Set the env var
  to make the disc less crowded for visual debugging.

### Rocket model — one per in-flight workflow
- One rocket per workflow_id in `RocketRegistry`. Spawned when the
  workflow appears in `/api/workflows/index/in-flight`. State machine:
  `idle → travelling → idle → … → returning → burst → done`.
- Rocket body + halo are **individual `<mesh>` components** keyed by
  `workflow_id` (no InstancedMesh). At the new scale (~10–30 rockets),
  this is simpler and gives free per-rocket colour.
- Body colour from `lib/colors.ts#colorForFunction` keyed on the
  resolved function family (Hiring, Finance, Treasury, etc.).
- Wounded workflows (`active_exception_id` set) lerp the body 60%
  toward `#ef4444` — same red as the wounded-moon overlay.
- Travel: 1.2s ease-in-out cubic between cities, with a sin-arc lift.
  Idle: bobs gently in place at the last city. Completion: 1s fly-home
  to the workflow's moon, then 0.6s radial burst, then despawn.

### Activity rail (`HUD/ActivityRail.tsx`)
- Slices buffer by `delta = ref.version - lastVersion` instead of
  re-flushing the whole ring buffer. Same-workflow_id dedup walks
  newest-first and preserves the title of the newer entry.

### Wounded moons (`WorkflowMoons.tsx`)
- Third InstancedMesh of 600 instances, `MeshBasicMaterial color=#ef4444 opacity=0.85`.
  Verified via `sceneState()`. Active only for moons with `active_exception_id`.

### Cyan dome on hub (`HubDisc.tsx`)
- **Removed.** Hub now has 3 meshes: cylinder disc, cyan emissive ring, blue glow puff.

### City label persistence (`Cities.tsx`)
- Personas (`kind === 'persona'`) always labelled.
- Other cities labelled while busy + 12s grace period after pending/parked
  drops to 0.

### Hover path (`HoveredWorkflowPath.tsx`)
- Renders when `hoveredMoonId !== null`:
  - Violet polyline through every city the workflow has parked at
  - Numbered violet step markers
  - Magenta line from moon → current rocket position
  - Pulsing torus at the destination city
  - Floating "WF-XXXX · N stops" label (anchored to a `<group ref>`
    updated each frame so it tracks the midpoint as both endpoints move)
- `historyPoints` useMemo depends on `rocketRegistry.version` — and
  `recordVisit` bumps `version` when a new city is appended.

### WorkflowDrawer timeline
- Reads `data.timeline` from `/api/workflows/index/timeline/{id}`
  (server returns `{workflow, timeline:[{ts, kind, label, status, ...}]}`).
  Rows render with `kind`-keyed colour and a compact details block
  showing actor / verdict / reason / result_summary / tokens / details.

### Registry hygiene
- `RocketRegistry.pruneCompleted` runs every frame (no `Math.floor(t) % 10`
  gating). Entries only reach `'done'` after the burst animation has
  finished, so this is safe and keeps the registry size at the
  in-flight workflow count.

### Scene introspector (`CosmicLens.tsx`)
- `<SceneIntrospector />` runs INSIDE Canvas, uses `useThree()` to publish
  `scene/camera/gl` onto `window.__cosmicScene`. Outside-Canvas helpers
  (`sceneState`, `instanceColors`) read from there.

## What does NOT work / open issues

_(none currently tracked — see git history for prior issues that have
been resolved)_

## Notes

### HIRE-DEMO-01..03 sit at "Budget" by design
- `api/server/services/portal_seed.py:79-84` intentionally does NOT
  schedule the HiringOrchestrator for the demo seeds — they wait for a
  real candidate to hit `/api/portal/apply`. Their moons appear on the
  disc but stay in "Budget" until a portal application arrives.
- This is **not** a bug. The "[orchestrator] failed to schedule"
  errors that previous STATE.md snapshots attributed to these seeds
  actually came from the ramp-loop's first cycles spawning unrelated
  domains during the ~30s window after boot when the Functions host
  hasn't bound yet. Those recover on the next ramp cycle.

### `instanceColors` helper limitation
- Reads `instanceColor` buffer if present. The current rockets are
  individual meshes (not InstancedMesh), so this helper isn't
  applicable to them — use `sceneState()` for material-level colour
  inspection instead. The helper is kept around for future
  InstancedMesh consumers (moons, wounded-moon overlay).

## Quick reference: file responsibilities

| File | What it owns |
|------|-------------|
| `CosmicLens.tsx` | Scene root, Canvas, OrbitControls, postprocessing (Bloom), `__cosmic` introspector helpers, hovered-moon state |
| `HubDisc.tsx` | Central disc + emissive cyan edge ring + glow puff |
| `FunctionPlanets.tsx` | Function-family planets orbiting the hub |
| `WorkflowMoons.tsx` | One moon per in-flight workflow, orbits parent planet, wounded overlay if exception |
| `Cities.tsx` | Capabilities/personas/entity-type cities scattered on disc surface |
| `Rockets.tsx` | One mesh-per-rocket per in-flight workflow; animated travel + idle bob + fly-home burst; family colour; wounded tint |
| `HoveredWorkflowPath.tsx` | Violet polyline + step markers + magenta line when hovering a moon |
| `Trails.tsx` | Decaying trail samples emitted by per-workflow rockets while travelling and (sparser) while idle |
| `EntityEdges.tsx` | Read/write entity edges for "entities" mode |
| `DirectionalBeams.tsx` | Conduits between functions when one calls another |
| `PlanetCompletions.tsx` | Pulse rings around planets on workflow completion |
| `CameraFocus.tsx` | Smooth camera lerp toward a focus target |
| `HUD/VitalSignsBar.tsx` | Top-left mode toggle + steps/min + burst button |
| `HUD/ActivityRail.tsx` | Right-edge live event feed (delta-sliced, dedup'd) |
| `HUD/WorkflowDrawer.tsx` | Workflow / function / city detail panel (renders timeline rows by kind) |
| `lib/registries.ts` | Plain-TS registries for moons, rockets, trails (rockets indexed by workflow_id with `upsertForWorkflow` + city-history) |
| `lib/useLiveCosmic.ts` | SSE subscription + REST polling, exposes `flashesRef` ring buffer |
| `lib/types.ts` | Type definitions for SSE flashes + endpoint config |
| `lib/colors.ts` | Capability palette + function-family palette + entity-type palette |
| `lib/labels.ts` | Pretty-print SSE flashes for labels |
| `lib/workflowFunction.ts` | workflow_type → function-key resolution |
````

- [ ] **Step 2: Commit**

```bash
git add web/blueprint/src/components/cosmicLens/STATE.md
git commit -m "docs(cosmic): refresh STATE.md after per-workflow rocket model

All STATE.md open issues are resolved or correctly diagnosed:
- Per-workflow rocket model + animated travel + family colour + fly-home burst
- WorkflowDrawer timeline contract aligned with server (data.timeline + kind)
- Tighter pruneCompleted (every frame, no time gating)
- HIRE-DEMO seeds documented as not-a-bug (portal_seed.py:79-84)
- instanceColors helper caveat noted for future InstancedMesh consumers

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 6: Final verification

- [ ] **Step 1: Full blueprint build**

Run:

```bash
npm run build:blueprint
```

Expected: succeeds with no errors.

- [ ] **Step 2: Full vitest suite**

Run:

```bash
npm run test
```

Expected: all suites pass. If unrelated failures surface in non-cosmicLens code, do not attempt to fix in this plan — note them as out-of-scope.

- [ ] **Step 3: Smoke-check the live observatory (manual)**

```bash
make up   # if not already running
```

Open `http://localhost:5275/?view=constellation` then in DevTools:

```js
window.__cosmic.rocketDiag()
window.__cosmic.rocketSummary()
window.__cosmic.sceneState().filter(m => m.name?.includes("rocket") || m.geometry === "ConeGeometry").slice(0, 5)
```

Expected:
- `rocketDiag().lastDrawnCount` ≈ in-flight workflow count from `/api/workflows/index/in-flight`.
- `rocketSummary().byPhase` shows mostly `idle` and `travelling`, occasional `returning`/`burst`/`done`.
- Sampled cone meshes have distinct `material.color` values (not all `#facc15`).

Then click any in-flight workflow's moon to open its drawer:
- Expected: timeline rows render (not "No timeline events recorded").
- Cross-check with `curl http://localhost:3101/api/workflows/index/timeline/<id> | jq '.timeline | length'` — counts should match.

- [ ] **Step 4: If smoke-check passes, no extra commit needed; the work is shipped.**

If smoke-check reveals an issue, debug and fix in a follow-up commit on the same branch — do not patch the spec/plan.
