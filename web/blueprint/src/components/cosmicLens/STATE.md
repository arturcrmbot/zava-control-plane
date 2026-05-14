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
  toward `#ef4444`.
- Travel: 1.2s ease-in-out cubic between cities, with a sin-arc lift.
  Idle: bobs gently in place at the last city. Completion: 1s fly-home
  to the workflow's anchor point near its parent planet (see
  `lib/moonPosition.ts`), then 0.6s radial burst, then despawn.

### Activity rail (`HUD/ActivityRail.tsx`)
- Slices buffer by `delta = ref.version - lastVersion` instead of
  re-flushing the whole ring buffer. Same-workflow_id dedup walks
  newest-first and preserves the title of the newer entry.

### Wounded rockets
- Workflows with `active_exception_id` are tinted red on the rocket
  body itself (see Rocket model above). There is no separate moon
  overlay — the rocket IS the workflow.

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
  - Magenta line from workflow anchor → current rocket position
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
  real candidate to hit `/api/portal/apply`. Their rockets park at
  "Budget" until a portal application arrives.
- This is **not** a bug. The "[orchestrator] failed to schedule"
  errors that previous STATE.md snapshots attributed to these seeds
  actually came from the ramp-loop's first cycles spawning unrelated
  domains during the ~30s window after boot when the Functions host
  hasn't bound yet. Those recover on the next ramp cycle.

### `instanceColors` helper limitation
- Reads `instanceColor` buffer if present. The current rockets are
  individual meshes (not InstancedMesh), so this helper isn't
  applicable to them — use `sceneState()` for material-level colour
  inspection instead. The helper is kept around for any future
  InstancedMesh consumers.

## Quick reference: file responsibilities

| File | What it owns |
|------|-------------|
| `CosmicLens.tsx` | Scene root, Canvas, OrbitControls, postprocessing (Bloom), `__cosmic` introspector helpers, hovered-moon state |
| `HubDisc.tsx` | Central disc + emissive cyan edge ring + glow puff |
| `FunctionPlanets.tsx` | Function-family planets orbiting the hub |
| `Cities.tsx` | Capabilities/personas/entity-type cities scattered on disc surface |
| `Rockets.tsx` | One mesh-per-rocket per in-flight workflow; animated travel + idle bob + fly-home burst; family colour; wounded tint (rocket IS the workflow) |
| `HoveredWorkflowPath.tsx` | Violet polyline + step markers + magenta line when hovering a workflow |
| `Trails.tsx` | Decaying trail samples emitted by per-workflow rockets while travelling and (sparser) while idle |
| `EntityEdges.tsx` | Read/write entity edges for "entities" mode |
| `DirectionalBeams.tsx` | Conduits between functions when one calls another |
| `PlanetCompletions.tsx` | Pulse rings around planets on workflow completion |
| `CameraFocus.tsx` | Smooth camera lerp toward a focus target |
| `HUD/VitalSignsBar.tsx` | Top-left mode toggle + steps/min + burst button |
| `HUD/ActivityRail.tsx` | Right-edge live event feed (delta-sliced, dedup'd) |
| `HUD/WorkflowDrawer.tsx` | Workflow / function / city detail panel (renders timeline rows by kind) |
| `lib/registries.ts` | Plain-TS registries for rockets + trails (rockets indexed by workflow_id with `upsertForWorkflow` + city-history) |
| `lib/useLiveCosmic.ts` | SSE subscription + REST polling, exposes `flashesRef` ring buffer |
| `lib/types.ts` | Type definitions for SSE flashes + endpoint config |
| `lib/colors.ts` | Capability palette + function-family palette + entity-type palette |
| `lib/labels.ts` | Pretty-print SSE flashes for labels |
| `lib/workflowFunction.ts` | workflow_type → function-key resolution |
