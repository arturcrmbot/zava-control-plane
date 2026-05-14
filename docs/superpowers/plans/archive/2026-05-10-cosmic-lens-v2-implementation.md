# Cosmic Lens v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild `/?view=constellation` as the v2 cosmic lens — a real-time x-ray of the agentic substrate where workflows orbit function planets as moons, dispatch rockets to capability-cities on a central disc, and (via toggle) swap to entity-graph mode showing reads/writes as directional beams.

**Architecture:** Pure React + R3F. New component tree under `web/blueprint/src/components/cosmicLens/`. One central `useLiveCosmic` hook polls existing PR #6/#7 endpoints + subscribes to SSE. Per-entity registries in plain TS modules. Backend additions are minimal — one new `/api/cities` endpoint group plus an `entity.read` event type. Force-directed layout via `d3-force` (added as dep). InstancedMesh used for cities/moons/rockets/trails to keep frame budget tight.

**Tech Stack:** React 19, TypeScript, @react-three/fiber 9, @react-three/drei 10, three 0.184, d3-force (NEW), Python 3.12 / FastAPI / Pydantic / pytest, vitest.

**Spec:** `docs/superpowers/specs/2026-05-10-cosmic-lens-v2-design.md`

---

## File Structure

### Frontend (`web/blueprint/src/`)

| File | Status | Responsibility |
|---|---|---|
| `components/cosmicLens/CosmicLens.tsx` | Create | Scene root: Canvas, OrbitControls (full-scene drag-rotate), lighting, mounts everything. |
| `components/cosmicLens/HubDisc.tsx` | Create | The gently-domed central disc. |
| `components/cosmicLens/Cities.tsx` | Create | All cities as `InstancedMesh`. Mode-switchable. |
| `components/cosmicLens/EntityEdges.tsx` | Create | Persistent Kuzu edges in Entities mode (Lines). |
| `components/cosmicLens/FunctionPlanets.tsx` | Create | All function planets in fixed orbital slots. |
| `components/cosmicLens/WorkflowMoons.tsx` | Create | One moon per in-flight workflow, orbit parent planet. |
| `components/cosmicLens/Rockets.tsx` | Create | Rockets in flight + parked. `InstancedMesh`. Includes directional beams. |
| `components/cosmicLens/Trails.tsx` | Create | Fading trails (instanced segments). |
| `components/cosmicLens/ModeToggle.tsx` | Create | `[ Capabilities | Entities ]` segmented control. Lives in HUD. |
| `components/cosmicLens/HUD/VitalSignsBar.tsx` | Create | Top HUD (port from glassTower style). |
| `components/cosmicLens/HUD/ActivityRail.tsx` | Create | Right rail event feed with filter chips (port). |
| `components/cosmicLens/HUD/WorkflowDrawer.tsx` | Create | Slide-in drawer (port). |
| `components/cosmicLens/lib/useLiveCosmic.ts` | Create | Single hook: poll endpoints + SSE + ref-based flash pub/sub. |
| `components/cosmicLens/lib/registries.ts` | Create | `moonRegistry`, `cityRegistry`, `rocketRegistry`, `trailRegistry`. |
| `components/cosmicLens/lib/forceLayout.ts` | Create | 2D force-directed layout (d3-force) for cities on disc. |
| `components/cosmicLens/lib/colors.ts` | Create | 5-band Capabilities palette + Entities palette. |
| `components/cosmicLens/lib/labels.ts` | Create | Mode-specific action label generator. |
| `pages/ConstellationPage.tsx` | Modify | Mount `<CosmicLens />` instead of `<Constellation />`. |
| `vite.config.ts` | Modify | Add `resolve.dedupe` for `three`/`@react-three/*` (PR #6 fix). |
| `package.json` | Modify | Add `d3-force` + `@types/d3-force`. |

### Backend (`api/server/`)

| File | Status | Responsibility |
|---|---|---|
| `api/server/routes/cities.py` | Create | `GET /api/cities` (roster) + `GET /api/cities/affinity` (call-graph weights). |
| `api/server/main.py` | Modify | Mount `cities` router. |
| `api/server/services/event_emitter.py` (or wherever entity reads happen) | Modify | Emit `entity.read` events when entities are read by workflows. |
| `api/server/routes/blueprint.py` | Modify | Add `entity.read` to `_OBSERVATORY_TYPES`. |

### Tests

| File | Status | Responsibility |
|---|---|---|
| `web/blueprint/src/components/cosmicLens/lib/__tests__/registries.test.ts` | Create | Unit tests for registries. |
| `web/blueprint/src/components/cosmicLens/lib/__tests__/forceLayout.test.ts` | Create | Unit tests for layout convergence. |
| `web/blueprint/src/components/cosmicLens/lib/__tests__/labels.test.ts` | Create | Unit tests for label generation. |
| `web/blueprint/src/components/cosmicLens/lib/__tests__/colors.test.ts` | Create | Unit tests for palette mapping. |
| `tests/api/server/routes/test_cities.py` | Create | Integration tests for cities endpoints. |

---

## Phase A — Skeleton (Tasks 1–8)

**Goal:** A visually working cosmic scene with planets, moons, and rockets dispatched from real workflow events. No labels, no force layout, no toggle. Just motion that proves the pipes work end-to-end.

### Task 1: Scaffolding + dedup + d3-force dep

**Files:**
- Modify: `web/blueprint/vite.config.ts`
- Modify: `web/blueprint/package.json`
- Create: `web/blueprint/src/components/cosmicLens/.gitkeep`
- Create: `web/blueprint/src/components/cosmicLens/lib/.gitkeep`
- Create: `web/blueprint/src/components/cosmicLens/HUD/.gitkeep`

- [ ] **Step 1:** Update `vite.config.ts` to add three.js dedup (prevents `stats-gl` shipping nested `three`):
```ts
resolve: {
  dedupe: ["three", "@react-three/fiber", "@react-three/drei"],
},
optimizeDeps: {
  include: ["three", "@react-three/fiber", "@react-three/drei", "d3-force"],
},
```
- [ ] **Step 2:** Add `d3-force` and `@types/d3-force` to `web/blueprint/package.json`.
- [ ] **Step 3:** `cd web/blueprint && npm install`
- [ ] **Step 4:** `mkdir -p src/components/cosmicLens/{lib,HUD}` and add `.gitkeep` files.
- [ ] **Step 5:** Verify build: `cd web/blueprint && npm run build`. Expect: success.
- [ ] **Step 6:** Commit: `chore(cosmic): scaffolding + three.js dedup + d3-force`

### Task 2: Pure-logic modules (registries, colors, labels)

**Files:**
- Create: `web/blueprint/src/components/cosmicLens/lib/colors.ts`
- Create: `web/blueprint/src/components/cosmicLens/lib/labels.ts`
- Create: `web/blueprint/src/components/cosmicLens/lib/registries.ts`
- Create: `web/blueprint/src/components/cosmicLens/lib/__tests__/colors.test.ts`
- Create: `web/blueprint/src/components/cosmicLens/lib/__tests__/labels.test.ts`
- Create: `web/blueprint/src/components/cosmicLens/lib/__tests__/registries.test.ts`

- [ ] **Step 1:** Write tests first (TDD). See test files in repo for canonical examples.
- [ ] **Step 2:** Implement `colors.ts` with 5-band Capabilities palette + Entity palette helpers.
- [ ] **Step 3:** Implement `labels.ts` with mode-specific label generator: `labelForCapability(event)`, `labelForEntity(event)`.
- [ ] **Step 4:** Implement `registries.ts` with: `moonRegistry`, `cityRegistry`, `rocketRegistry`, `trailRegistry`. Plain TS classes, no React.
- [ ] **Step 5:** Run vitest: `cd web/blueprint && npx vitest run src/components/cosmicLens/lib`. All pass.
- [ ] **Step 6:** Commit: `feat(cosmic): pure logic primitives — colors, labels, registries`

### Task 3: useLiveCosmic hook

**Files:**
- Create: `web/blueprint/src/components/cosmicLens/lib/useLiveCosmic.ts`

Single hook that polls 3 endpoints every 3s, subscribes to SSE, and exposes:
- `inFlight: WorkflowMoon[]` (in-flight workflows)
- `personas: PersonaState[]`
- `functions: FunctionMeta[]`
- `cities: CityMeta[]` (Phase B; can return empty in A)
- `flashesRef: React.MutableRefObject<FlashEvent[]>` for animation pub/sub
- `mode: "capabilities" | "entities"` + `setMode(...)`
- Status (connected/disconnected)

- [ ] **Step 1:** Implement hook with polling + SSE wiring (mirror PR #6 hook patterns).
- [ ] **Step 2:** Add quick types in `web/blueprint/src/components/cosmicLens/lib/types.ts`.
- [ ] **Step 3:** Smoke test: render `<UseLiveCosmicProbe />` test component, assert it doesn't throw.
- [ ] **Step 4:** Commit: `feat(cosmic): useLiveCosmic hook — single source of truth`

### Task 4: HubDisc + scene root

**Files:**
- Create: `web/blueprint/src/components/cosmicLens/HubDisc.tsx`
- Create: `web/blueprint/src/components/cosmicLens/CosmicLens.tsx`

- [ ] **Step 1:** `HubDisc.tsx`: a `<mesh>` with `<cylinderGeometry args={[8, 8, 0.5, 64]} />` for the disc + a slight dome via shader displacement OR just a second `<sphereGeometry>` cap on top.
- [ ] **Step 2:** `CosmicLens.tsx`: scene root with `<Canvas camera={{ position: [0, 12, 22], fov: 45 }}>`, `<ambientLight>`, `<directionalLight>`, `<OrbitControls enableDamping />`, `<Stars />`, `<HubDisc />`.
- [ ] **Step 3:** Update `ConstellationPage.tsx` to render `<CosmicLens />` (replace `<Constellation />`).
- [ ] **Step 4:** Run dev server. Expect: glowing disc visible at center, scene rotates with mouse.
- [ ] **Step 5:** Commit: `feat(cosmic): hub disc + scene root`

### Task 5: FunctionPlanets

**Files:**
- Create: `web/blueprint/src/components/cosmicLens/FunctionPlanets.tsx`

- [ ] **Step 1:** Read `functions` from `useLiveCosmic`. Each function = a `<mesh>` with `<sphereGeometry args={[0.7, 16, 16]} />` positioned at angle = `i * 2π / N`, radius = 13.
- [ ] **Step 2:** Color by function family (extract from `colors.ts`).
- [ ] **Step 3:** Slow rotation around Y-axis using `useFrame` (orbit motion).
- [ ] **Step 4:** Mount in `<CosmicLens />`.
- [ ] **Step 5:** Visual check: 8–12 planets visible orbiting the disc.
- [ ] **Step 6:** Commit: `feat(cosmic): function planets in orbit`

### Task 6: WorkflowMoons

**Files:**
- Create: `web/blueprint/src/components/cosmicLens/WorkflowMoons.tsx`

- [ ] **Step 1:** Read `inFlight` from `useLiveCosmic`. Group by function via `workflow_id` prefix → `workflow_type` → `function`. Use existing `PREFIX_TO_WORKFLOW_TYPE` map (port from glassTower).
- [ ] **Step 2:** For each workflow, compute orbit: parent planet position + small radius (1.4) + per-moon angle offset (hash of `wf.id`).
- [ ] **Step 3:** Render as `<InstancedMesh>` with `<sphereGeometry args={[0.15, 8, 8]} />`.
- [ ] **Step 4:** `useFrame` updates instanceMatrix each frame for slow orbital motion.
- [ ] **Step 5:** Mount in `<CosmicLens />`.
- [ ] **Step 6:** Visual check with `inject-burst`: see 30+ moons orbiting their parent planets.
- [ ] **Step 7:** Commit: `feat(cosmic): workflow moons orbiting parent planets`

### Task 7: Cities (placeholder)

**Files:**
- Create: `web/blueprint/src/components/cosmicLens/Cities.tsx`

- [ ] **Step 1:** Hardcode 30 cities at random positions on disc top surface (radius < 7.5, y = 0.3). Phase C will switch to force layout.
- [ ] **Step 2:** Render as `<InstancedMesh>` with `<sphereGeometry args={[0.18, 8, 8]} />`.
- [ ] **Step 3:** Each city has random color from cyan band (Phase B will switch to category palette).
- [ ] **Step 4:** Mount in `<CosmicLens />`.
- [ ] **Step 5:** Visual check: cities visible scattered on disc.
- [ ] **Step 6:** Commit: `feat(cosmic): cities placeholder on disc`

### Task 8: Rockets (basic dispatch)

**Files:**
- Create: `web/blueprint/src/components/cosmicLens/Rockets.tsx`

- [ ] **Step 1:** `Rockets.tsx`: subscribe to `flashesRef.current` for `tool.invoked` / `persona.thinking` events. For each event, push to `rocketRegistry` with `{from: moon_position, to: city_position, dispatched_at, completes_at}`.
- [ ] **Step 2:** On `tool.completed` / `persona.decided`, mark rocket as returning.
- [ ] **Step 3:** Render as `<InstancedMesh>` of `<coneGeometry args={[0.07, 0.2, 6]} />` (small rocket shapes).
- [ ] **Step 4:** `useFrame` interpolates rocket position along its path. When parked at city, hover with slight bob animation.
- [ ] **Step 5:** Park at random city for now (Phase B picks the right city).
- [ ] **Step 6:** Mount in `<CosmicLens />`.
- [ ] **Step 7:** Visual check: rockets visibly fly from moons to cities and back.
- [ ] **Step 8:** Commit: `feat(cosmic): rockets — flight + parking primitive`

### Phase A QA Gate

- [ ] **A.QA.1:** `cd web/blueprint && npm run build` — passes.
- [ ] **A.QA.2:** `cd web/blueprint && npx vitest run` — all pass.
- [ ] **A.QA.3:** Boot stack via `bash scripts/boot-demo.sh`. Open `http://localhost:5275/?view=constellation`. Inject burst. Visually confirm: disc + planets + moons + rockets all visible and moving.
- [ ] **A.QA.4:** Take screenshot, save to session files.
- [ ] **A.QA.5:** Commit: `chore(cosmic): Phase A complete — moving skeleton`

---

## Phase B — Semantics (Tasks 9–16)

**Goal:** Real action labels on rockets, real-time park durations, color-by-type, HITL personas as cities, working HUD chrome ported from glassTower.

### Task 9: Backend cities roster endpoint

**Files:**
- Create: `api/server/routes/cities.py`
- Modify: `api/server/main.py`
- Create: `tests/api/server/routes/test_cities.py`

- [ ] **Step 1:** Implement `GET /api/cities` returning `{cities: [{id, kind, label, category}, ...]}` where `kind` ∈ `mcp|skill|python|validator|persona|entity_type`.
- [ ] **Step 2:** Source: scan `api/server/skills/`, `api/server/agents/`, `DOMAINS` registry for personas, MCP catalog. Hardcode validator list initially.
- [ ] **Step 3:** Pytest with deterministic fixture.
- [ ] **Step 4:** Mount router in `main.py`.
- [ ] **Step 5:** Smoke: `curl localhost:3101/api/cities | jq`.
- [ ] **Step 6:** Commit: `back(cosmic): GET /api/cities roster`

### Task 10: useLiveCosmic — real cities + Capability palette

**Files:**
- Modify: `web/blueprint/src/components/cosmicLens/lib/useLiveCosmic.ts`
- Modify: `web/blueprint/src/components/cosmicLens/Cities.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/lib/colors.ts`

- [ ] **Step 1:** Hook: poll `/api/cities` every 30s, expose as `cities`.
- [ ] **Step 2:** Cities component: render real cities (still placeholder layout — Phase C does force).
- [ ] **Step 3:** Color each city by category via `colors.colorForKind(kind)`.
- [ ] **Step 4:** Visual check: cities now have proper colors (cyan/violet/teal/amber/warm-gold).
- [ ] **Step 5:** Commit: `feat(cosmic): real cities from /api/cities + 5-band palette`

### Task 11: Real action labels on rockets

**Files:**
- Modify: `web/blueprint/src/components/cosmicLens/Rockets.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/lib/labels.ts`

- [ ] **Step 1:** Use `labels.labelForCapability(event)` for rocket label.
- [ ] **Step 2:** Render label via `<Html>` from drei when rocket is parked OR hovered. Position above the rocket.
- [ ] **Step 3:** Label format examples: `awaiting HITL decision (ap_clerk)`, `running stripe.charge`, `validating signature`, `thinking…`.
- [ ] **Step 4:** Visual check: parked rockets show readable labels.
- [ ] **Step 5:** Commit: `feat(cosmic): rocket labels — what's the action`

### Task 12: Real-time park duration

**Files:**
- Modify: `web/blueprint/src/components/cosmicLens/lib/registries.ts`
- Modify: `web/blueprint/src/components/cosmicLens/Rockets.tsx`

- [ ] **Step 1:** When `tool.invoked` event arrives, dispatch rocket. Park at city until `tool.completed` arrives. No predetermined duration.
- [ ] **Step 2:** Minimum 500ms park (use `Math.max(500, completed_at - invoked_at)` for the visible duration even if API completed faster).
- [ ] **Step 3:** Same for `persona.thinking` → `persona.decided`.
- [ ] **Step 4:** Visual check: slow LLM tools = parked for seconds, fast tools = brief park.
- [ ] **Step 5:** Commit: `feat(cosmic): rocket park duration mirrors real action time`

### Task 13: HITL personas as cities

**Files:**
- Modify: `api/server/routes/cities.py`
- Modify: `web/blueprint/src/components/cosmicLens/Rockets.tsx`

- [ ] **Step 1:** Backend: ensure all personas (from `DOMAINS` + `personas/state` rosters) are returned as cities with `kind=persona`.
- [ ] **Step 2:** Frontend: when `persona.thinking` event arrives, dispatch rocket to that persona's city, label `awaiting HITL decision ({persona})`.
- [ ] **Step 3:** Persona cities use warm-gold/coral color from palette.
- [ ] **Step 4:** Visual check: HITL personas appear as warm-colored cities, rockets visibly park at them.
- [ ] **Step 5:** Commit: `feat(cosmic): HITL personas as first-class cities`

### Task 14: VitalSignsBar (port from glassTower)

**Files:**
- Create: `web/blueprint/src/components/cosmicLens/HUD/VitalSignsBar.tsx`

- [ ] **Step 1:** Port the VitalSignsBar visual from former glassTower work (was on PR #6 deleted code — reconstruct from spec §4).
- [ ] **Step 2:** Stats: in-flight count, pending decisions, throughput/min, exception count, status pill, ⚡BURST button (calls `POST /api/simulator/inject-burst?n=8`).
- [ ] **Step 3:** Add a placeholder ModeToggle slot at top-right (filled in Task 22).
- [ ] **Step 4:** Mount as overlay in `CosmicLens.tsx` (absolute positioning over Canvas).
- [ ] **Step 5:** Visual check: top bar visible with live stats updating.
- [ ] **Step 6:** Commit: `feat(cosmic): VitalSignsBar HUD`

### Task 15: ActivityRail (port)

**Files:**
- Create: `web/blueprint/src/components/cosmicLens/HUD/ActivityRail.tsx`

- [ ] **Step 1:** Port ActivityRail visual: right-edge column, event feed with filter chips.
- [ ] **Step 2:** Chip categories: decisions / thinking / done / exceptions / started / spawned / tools (tools off by default).
- [ ] **Step 3:** Auto-pin to top unless user has scrolled.
- [ ] **Step 4:** `formatRow(event)` translates raw event into one-line English.
- [ ] **Step 5:** Mount in `CosmicLens.tsx`.
- [ ] **Step 6:** Visual check: events flow into rail in real-time.
- [ ] **Step 7:** Commit: `feat(cosmic): ActivityRail with filter chips`

### Task 16: Moon ref number labels

**Files:**
- Modify: `web/blueprint/src/components/cosmicLens/WorkflowMoons.tsx`

- [ ] **Step 1:** Render workflow ref number above each moon using drei's `<Text>` or `<Html>`.
- [ ] **Step 2:** Fade label by distance/zoom — only show when zoomed in or moon is highlighted.
- [ ] **Step 3:** Visual check: zooming in reveals ref numbers like `VKY-0042`.
- [ ] **Step 4:** Commit: `feat(cosmic): moon ref number labels`

### Phase B QA Gate

- [ ] **B.QA.1:** Build + tests pass.
- [ ] **B.QA.2:** Visual smoke with burst: rockets park at named cities for real durations, labels readable, HUD live.
- [ ] **B.QA.3:** Screenshot.
- [ ] **B.QA.4:** Commit: `chore(cosmic): Phase B complete — semantics`

---

## Phase C — Emergence (Tasks 17–22)

**Goal:** Force-directed city layout, fading rocket trails, click-to-drill drawer. Capabilities mode complete.

### Task 17: Backend cities/affinity endpoint

**Files:**
- Modify: `api/server/routes/cities.py`
- Modify: `tests/api/server/routes/test_cities.py`

- [ ] **Step 1:** `GET /api/cities/affinity` returning `{pairs: [{a, b, weight}, ...]}` based on co-occurrence in recent workflows.
- [ ] **Step 2:** Source: scan recent events from observatory (last 1000 events grouped by `workflow_id`); count tool/skill/persona pairs that appear in same workflow.
- [ ] **Step 3:** Cache for 60s.
- [ ] **Step 4:** Test: deterministic fixture.
- [ ] **Step 5:** Commit: `back(cosmic): cities affinity endpoint`

### Task 18: 2D force-directed layout

**Files:**
- Create: `web/blueprint/src/components/cosmicLens/lib/forceLayout.ts`
- Create: `web/blueprint/src/components/cosmicLens/lib/__tests__/forceLayout.test.ts`
- Modify: `web/blueprint/src/components/cosmicLens/Cities.tsx`

- [ ] **Step 1:** `forceLayout.ts`: wraps `d3-force` with `forceManyBody`, `forceLink` (spring strength = affinity weight), `forceCollide`, and a custom `forceRadial` to keep cities within disc radius < 7.5.
- [ ] **Step 2:** Run for 200 ticks on data load (synchronous), then expose final `{id, x, y}` positions.
- [ ] **Step 3:** Re-run when affinity data refreshes.
- [ ] **Step 4:** Cities component reads positions, places city instances at `(x, 0.3, y)`.
- [ ] **Step 5:** Test: layout converges (no NaN, all within radius).
- [ ] **Step 6:** Visual check: related cities cluster naturally.
- [ ] **Step 7:** Commit: `feat(cosmic): force-directed city layout — corridors emerge`

### Task 19: Trails

**Files:**
- Create: `web/blueprint/src/components/cosmicLens/Trails.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/lib/registries.ts`

- [ ] **Step 1:** `trailRegistry`: ring buffer of trail samples `{from, to, age_s, color}` capped at 500.
- [ ] **Step 2:** Each rocket flight pushes a sample on completion; samples decay over 60s.
- [ ] **Step 3:** Render as `<lineSegments>` with vertex colors, alpha = `1 - age_s/60`.
- [ ] **Step 4:** Mount in `CosmicLens.tsx`.
- [ ] **Step 5:** Visual check: corridors emerge as glowing arcs after running for a minute.
- [ ] **Step 6:** Commit: `feat(cosmic): rocket trails — corridors emerge from motion`

### Task 20: WorkflowDrawer (port)

**Files:**
- Create: `web/blueprint/src/components/cosmicLens/HUD/WorkflowDrawer.tsx`

- [ ] **Step 1:** Slide-in drawer from right edge (over the activity rail when open).
- [ ] **Step 2:** Two views: FunctionView (workflow list) + WorkflowView (timeline via `/api/workflows/index/timeline/{id}`).
- [ ] **Step 3:** Backdrop + ESC to close + back button on workflow view.
- [ ] **Step 4:** Mount in `CosmicLens.tsx`.
- [ ] **Step 5:** Commit: `feat(cosmic): workflow drawer port`

### Task 21: Click-to-drill wiring

**Files:**
- Modify: `web/blueprint/src/components/cosmicLens/FunctionPlanets.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/WorkflowMoons.tsx`

- [ ] **Step 1:** Click planet → opens drawer in FunctionView (function key → workflow list).
- [ ] **Step 2:** Click moon → opens drawer in WorkflowView (workflow id → timeline).
- [ ] **Step 3:** Click city → drawer in CityView (queued rockets list — placeholder ok for now).
- [ ] **Step 4:** Visual check: all three click affordances work.
- [ ] **Step 5:** Commit: `feat(cosmic): click-to-drill — planets + moons + cities`

### Task 22: ModeToggle (Capabilities only — Phase D wires Entities)

**Files:**
- Create: `web/blueprint/src/components/cosmicLens/ModeToggle.tsx`

- [ ] **Step 1:** Segmented control `[ Capabilities | Entities ]`. Capabilities default selected; Entities disabled with "coming in next phase" tooltip.
- [ ] **Step 2:** Mount in VitalSignsBar top-right slot.
- [ ] **Step 3:** State managed by `useLiveCosmic`.
- [ ] **Step 4:** Commit: `feat(cosmic): ModeToggle scaffolding`

### Phase C QA Gate

- [ ] **C.QA.1:** Build + tests pass.
- [ ] **C.QA.2:** Visual smoke: corridors visible, drawer drills, force layout looks reasonable.
- [ ] **C.QA.3:** Screenshot.
- [ ] **C.QA.4:** Commit: `chore(cosmic): Phase C complete — Capabilities mode done`

---

## Phase D — Entities mode (Tasks 23–28)

**Goal:** Toggle works, entity cities appear with persistent edges, rockets show directional beams for read/write.

### Task 23: Backend — entity types roster + entity.read events

**Files:**
- Modify: `api/server/routes/cities.py`
- Modify: `api/server/routes/blueprint.py`
- Find/modify: wherever entity reads happen in `api/server/services/` — emit `entity.read` events.

- [ ] **Step 1:** Add `?mode=entities` to `/api/cities` returning entity types instead.
- [ ] **Step 2:** Add `/api/entities/edges` returning `{edges: [{from_kind, to_kind, label}, ...]}` from Kuzu schema.
- [ ] **Step 3:** Find entity read locations in entity_reflector / entity routes; emit `entity.read` event with `{entity_kind, entity_id, caller_workflow_id}`.
- [ ] **Step 4:** Add `entity.read` to `_OBSERVATORY_TYPES` in `blueprint.py`.
- [ ] **Step 5:** Test: pytest covers all three.
- [ ] **Step 6:** Commit: `back(cosmic): entity-mode roster + edges + entity.read events`

### Task 24: Mode-specific cities + edges

**Files:**
- Modify: `web/blueprint/src/components/cosmicLens/Cities.tsx`
- Create: `web/blueprint/src/components/cosmicLens/EntityEdges.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/lib/useLiveCosmic.ts`

- [ ] **Step 1:** Hook fetches `/api/cities?mode=X` based on current mode.
- [ ] **Step 2:** Cities component renders entity-mode cities with entity palette (by ownership domain).
- [ ] **Step 3:** EntityEdges component renders persistent Kuzu edges as `<lineSegments>` between entity-cities.
- [ ] **Step 4:** Force layout runs separately for each mode (cached).
- [ ] **Step 5:** Visual check: switching mode shows different cities + edges.
- [ ] **Step 6:** Commit: `feat(cosmic): entity-mode cities + persistent edges`

### Task 25: ModeToggle wiring + morph animation

**Files:**
- Modify: `web/blueprint/src/components/cosmicLens/ModeToggle.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/Cities.tsx`

- [ ] **Step 1:** Toggle now actually switches modes.
- [ ] **Step 2:** Cities fade out (~300ms), then new mode's cities fade in (~300ms). Total morph ~600ms.
- [ ] **Step 3:** Persistent edges fade in/out same way.
- [ ] **Step 4:** Visual check: smooth morph between modes.
- [ ] **Step 5:** Commit: `feat(cosmic): mode toggle morph animation`

### Task 26: Rocket directional beam (Entities mode)

**Files:**
- Modify: `web/blueprint/src/components/cosmicLens/Rockets.tsx`

- [ ] **Step 1:** When mode = entities and rocket is parked: render a beam between rocket and city.
- [ ] **Step 2:** Beam direction encodes read/write: read = beam goes UP from city to rocket; write = beam goes DOWN from rocket to city.
- [ ] **Step 3:** Beam = `<mesh>` with `<cylinderGeometry>` between rocket position (slightly above city) and city position. Animated emissive intensity.
- [ ] **Step 4:** Add small particles travelling along the beam in the data-flow direction (read = upward, write = downward) for unmissable encoding.
- [ ] **Step 5:** Determine read/write from event type: `entity.read` → read; `entity.upserted` / `entity.linked` → write.
- [ ] **Step 6:** Visual check: clearly see direction of data flow per parked rocket.
- [ ] **Step 7:** Commit: `feat(cosmic): directional beam — read/write made visible`

### Task 27: Mode-specific rocket labels

**Files:**
- Modify: `web/blueprint/src/components/cosmicLens/lib/labels.ts`
- Modify: `web/blueprint/src/components/cosmicLens/Rockets.tsx`

- [ ] **Step 1:** `labelForEntity(event)` returns operation-style label: `reading person details (CAND-0042)`, `updating invoice INV-0871`, `creating vendor record`, `linking decision → workflow`.
- [ ] **Step 2:** Rocket label uses mode-appropriate generator.
- [ ] **Step 3:** Tests in labels.test.ts cover both branches.
- [ ] **Step 4:** Visual check: mode toggle changes label style.
- [ ] **Step 5:** Commit: `feat(cosmic): mode-specific rocket labels`

### Task 28: Rocket dispatch in entity mode

**Files:**
- Modify: `web/blueprint/src/components/cosmicLens/Rockets.tsx`

- [ ] **Step 1:** In entity mode, dispatch rockets on `entity.read` / `entity.upserted` / `entity.linked` events.
- [ ] **Step 2:** Target city = the entity-type city.
- [ ] **Step 3:** In capability mode, dispatch on `tool.invoked` / `persona.thinking` (existing behaviour).
- [ ] **Step 4:** Modes filter out the other mode's events while active.
- [ ] **Step 5:** Visual check: switching modes changes what triggers rockets.
- [ ] **Step 6:** Commit: `feat(cosmic): rocket dispatch wired per mode`

### Phase D QA Gate

- [ ] **D.QA.1:** Build + tests pass.
- [ ] **D.QA.2:** Visual smoke both modes: capability rockets in capability mode, entity rockets with beams in entity mode.
- [ ] **D.QA.3:** Toggle morph smooth.
- [ ] **D.QA.4:** Screenshot per mode.
- [ ] **D.QA.5:** Commit: `chore(cosmic): Phase D complete — Entities mode done`

---

## Phase E — Polish (Tasks 29–34)

**Goal:** Closure animations, exception visuals, density LOD, performance pass, final QA.

### Task 29: Workflow closure animation

**Files:**
- Modify: `web/blueprint/src/components/cosmicLens/WorkflowMoons.tsx`

- [ ] **Step 1:** On `workflow.completed` event, start closure: moon flares (1.5x scale brief), then spirals inward toward parent planet over ~1.5s, fading alpha.
- [ ] **Step 2:** After completion, remove from registry.
- [ ] **Step 3:** Increment a small "completed today" counter on the planet (visible glow).
- [ ] **Step 4:** Commit: `feat(cosmic): closure animation — moon spirals into planet`

### Task 30: Exception visuals

**Files:**
- Modify: `web/blueprint/src/components/cosmicLens/WorkflowMoons.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/Rockets.tsx`

- [ ] **Step 1:** On exception event, rocket returns as red bead, brief red trail.
- [ ] **Step 2:** Wounded moon: red halo until resolved.
- [ ] **Step 3:** Exception count flashes in VitalSignsBar.
- [ ] **Step 4:** Visual check: trigger exception via `inject-burst` if exception path supported.
- [ ] **Step 5:** Commit: `feat(cosmic): exception visuals`

### Task 31: Density LOD + performance

**Files:**
- Modify: `web/blueprint/src/components/cosmicLens/WorkflowMoons.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/Rockets.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/CosmicLens.tsx`

- [ ] **Step 1:** When zoomed out (camera distance > 30): hide labels, dim non-active moons, render rockets as thin lines.
- [ ] **Step 2:** Cap rockets per moon at 3 (most recent).
- [ ] **Step 3:** Cap total visible rockets at 200.
- [ ] **Step 4:** Profile: check FPS at 200 in-flight + heavy burst. Target: ≥ 30 FPS.
- [ ] **Step 5:** Commit: `perf(cosmic): density LOD + caps for performance`

### Task 32: Mode toggle preview (small tooltip)

**Files:**
- Modify: `web/blueprint/src/components/cosmicLens/ModeToggle.tsx`

- [ ] **Step 1:** On hover of inactive mode label, show small preview tooltip: "switch to see {what}". e.g., "switch to see entity reads/writes" or "switch to see tool/skill activity".
- [ ] **Step 2:** Commit: `feat(cosmic): mode toggle preview tooltip`

### Task 33: Visual polish pass

**Files:**
- Modify: any cosmic component

- [ ] **Step 1:** Bloom postprocessing on the Canvas (subtle).
- [ ] **Step 2:** Verify color contrasts read well at default zoom.
- [ ] **Step 3:** Camera defaults: position `[0, 12, 22]`, look at `[0, 0, 0]`. Min/max zoom limits.
- [ ] **Step 4:** Disable autoRotate in OrbitControls (drag only).
- [ ] **Step 5:** Add starry background depth.
- [ ] **Step 6:** Commit: `polish(cosmic): visual pass — bloom, camera, contrast`

### Task 34: Final QA + push

- [ ] **Step 1:** `cd web/blueprint && npm run build` — passes.
- [ ] **Step 2:** `cd web/blueprint && npx vitest run` — all pass.
- [ ] **Step 3:** Boot stack. Run sustained burst (`while true; do curl -X POST localhost:3101/api/simulator/inject-burst?n=8; sleep 10; done`) for 5 minutes.
- [ ] **Step 4:** Visual confirm 5-second test passes (busy/quiet readable, anything stuck visible).
- [ ] **Step 5:** Visual confirm both modes work, toggle smooth.
- [ ] **Step 6:** Push branch + open PR.
- [ ] **Step 7:** Update PR #7 to mark spec as in-progress; new PR for the implementation.

### Phase E QA Gate (Final)

- [ ] **E.QA.1:** All tests pass.
- [ ] **E.QA.2:** Sustained 5-minute live demo: stable, FPS ≥ 30, no console errors.
- [ ] **E.QA.3:** Both modes visibly distinct and useful.
- [ ] **E.QA.4:** PR opened with screenshots.

---

## Pragmatic Notes

- **TDD strictness:** Pure logic gets full TDD. R3F visual components get render-smoke tests + manual visual verification (R3F Canvas in jsdom is unreliable).
- **InstancedMesh discipline:** Cities, moons, rockets, trails all instanced. One mesh per category.
- **`useFrame` cost:** Keep per-frame work tight. Compute matrices into reusable `THREE.Matrix4` instances; don't allocate.
- **Backend pre-existing failures:** 6 known-failing tests (accuracy, evals, audit_chain, voice) — environmental, ignore.
- **Stack ports:** FastAPI 3101, blueprint preview 5275, Functions host 7071, Azurite 10000–10002.
- **Boot:** `bash scripts/boot-demo.sh` from worktree root. ~60s warmup.
- **Test-the-test rule:** Every test must fail without the implementation. After writing test, run it, confirm failure, THEN write implementation.

*End of plan.*
