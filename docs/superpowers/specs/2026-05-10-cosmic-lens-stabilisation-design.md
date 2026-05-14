# Cosmic Lens v2 — Stabilisation Design

**Date:** 2026-05-10
**Scope:** `web/blueprint/src/components/cosmicLens/`
**Goal:** Resolve every open item in `cosmicLens/STATE.md` so the observatory becomes legible at a glance and free of known bugs.

## Problem

The Cosmic Lens v2 observatory has shipped a stable baseline (commit `0754b3a5`) but `cosmicLens/STATE.md` calls out five open issues. The keystone is a model mismatch: rockets are spawned per SSE event (`tool.invoked`, `persona.thinking`, etc.), so a workflow with 24 events generates 24 rockets — ~30 visible at once across 5 in-flight workflows. This makes the scene illegible at a glance and does not match the user's mental model ("4 in-flight workflows = 4 rockets, each one telling me what its workflow is doing right now"). Two unrelated bugs (empty workflow drawer, lazy registry prune) and two cosmetic items round out the list.

## Approach

Switch to **one rocket per in-flight workflow**, with smooth animated travel between cities, a persistent fading trail, family-coloured bodies, idle-bobbing at the last visited city, and a fly-home-and-pop completion animation. With workflow count ~10–30 instead of event count ~hundreds, drop `InstancedMesh` for rockets in favour of one regular `<mesh>` per rocket — simpler, gives free per-rocket colour, and side-steps the `vertexColors`-on-`InstancedMesh` shader-compile hazard documented in STATE.md. The drawer bug is a server/client contract mismatch — fix on the client. Registry hygiene improves naturally from the smaller working set; tighten `pruneCompleted` cadence as a small cleanup. The HIRE-DEMO item is a STATE.md misdiagnosis (`portal_seed.py` intentionally parks them at "Budget" until a real candidate applies via `/api/portal/apply`); strip from open issues with no code change.

## Architecture

### Rocket model (per-workflow)

- **Spawn** on `workflow.started`. One rocket per workflow_id. Initial pose: orbiting the workflow's moon.
- **Travel** on each significant event (`tool.invoked`, `durable.executor.invoked`, `persona.thinking`, `ambient.decided`): smooth interpolation from current pose → target city over ~1.2s using an ease-in-out cubic. While travelling, emit trail samples every frame.
- **Idle** between events: park at the last visited city; apply a small `sin(t)` y-offset so the rocket bobs gently. Continue emitting (sparser) trail samples so the trail decays naturally rather than freezing.
- **Wounded** (workflow has `active_exception_id`): tint the rocket toward the wounded-moon red (`#ef4444`) by lerping the body colour 60% toward red, and pulse the scale.
- **Completion** on `workflow.completed`: fly back to the workflow's moon over ~1s, emit a brief radial burst (small expanding ring + scale-up-and-fade), then despawn.
- **Termination on terminal error** identical to completion but burst tinted red.

### Rocket rendering

- One `<mesh>` per rocket (cone body) plus one halo `<mesh>` per rocket. At 10–30 rockets the per-frame draw-call overhead is negligible.
- Body colour from `lib/colors.ts` keyed on the workflow's resolved function family (use `workflowFunction.ts`). Halo colour matches body at 0.4 opacity.
- Material: `MeshBasicMaterial` (no lighting needed; works with the existing post-processing bloom).
- Wounded overlay handled by mutating the `Material.color` ref in the per-frame `useFrame`, not by swapping materials.

### Trails

- `Trails.tsx` keeps its decaying-sample model but is now driven by the per-workflow `rocketRegistry` rather than per-event rockets. Every active rocket emits a trail sample per frame while travelling and every Nth frame while idle. Sample shape stays the same (`{position, age, color}`).
- Trail colour matches the rocket's body colour so families are readable in the trail too.

### Drawer fix

- `WorkflowDrawer.tsx#WorkflowView`:
  - Read `data.timeline` (server returns `{workflow, timeline}`), not `data.events`.
  - Update the `TimelineEvent` interface to `{ts, kind, label, status?, actor?, ...}` matching `api/server/routes/workflows.py:211 workflow_timeline`.
  - Update the row renderer to display `ev.label` as the title and `ev.kind` as the subtitle (with `eventColor` keyed off `kind`).

### Registry hygiene

- `lib/registries.ts#rocketRegistry`: indexed by `workflow_id` instead of by event id. Each entry tracks `{phase, currentPos, targetPos, lastEventCity, idleSince, color}`.
- `pruneCompleted`: remove entries on the same frame their `phase === 'done'` and the completion burst has finished. No `Math.floor(t) % 10` gating.

### HIRE-DEMO and `instanceColors` cleanup

- No code change. `STATE.md` updates only — strip both items from "What does NOT work" and add a note that HIRE-DEMO seeds wait for a portal application by design (`portal_seed.py:79-84`).

## Files touched

| File | Change |
|---|---|
| `web/blueprint/src/components/cosmicLens/Rockets.tsx` | Major rewrite — per-workflow model, individual meshes, animated travel, idle bob, fly-home-and-pop completion, family colour, wounded tint. |
| `web/blueprint/src/components/cosmicLens/Trails.tsx` | Drive from per-workflow rockets; emit during travel and (sparser) during idle; colour-match the rocket. |
| `web/blueprint/src/components/cosmicLens/lib/registries.ts` | `rocketRegistry` reshaped to one entry per workflow_id with the new pose/phase fields; tighter pruning. |
| `web/blueprint/src/components/cosmicLens/lib/useLiveCosmic.ts` | Translate the SSE flash stream into per-workflow registry mutations (spawn / travel-to-city / wounded / complete). |
| `web/blueprint/src/components/cosmicLens/HUD/WorkflowDrawer.tsx` | Read `data.timeline`; new `TimelineEvent` shape; renderer uses `kind`/`label`. |
| `web/blueprint/src/components/cosmicLens/STATE.md` | Refresh: promote resolved items to "What works", strip false items, document new model. |

## Out of scope

- Auto-applier for HIRE-DEMO seeds (deferred; the demo uses real portal applications).
- Anything outside `web/blueprint/src/components/cosmicLens/` and the `WorkflowDrawer` server contract.
- The `instanceColors` helper itself — once rockets stop using `InstancedMesh`, the helper's flat-material caveat becomes a non-issue and the helper can stay as-is for future InstancedMesh consumers.
- Any change to `Cities.tsx`, `HubDisc.tsx`, `FunctionPlanets.tsx`, `WorkflowMoons.tsx`, `HoveredWorkflowPath.tsx`. The hover-path code already keys off the per-workflow rocket registry's `recordVisit` history, so it benefits from the new model with no further change.

## Verification

After implementation, verify at runtime via `window.__cosmic` in the live observatory at `http://localhost:5275/?view=constellation`:

1. `window.__cosmic.rocketDiag()` — count equals in-flight workflow count (within ±1 for spawn/despawn races).
2. `window.__cosmic.rocketSummary()` — every entry has a non-null `cityId` once the workflow has visited at least one city.
3. `window.__cosmic.sceneState()` — rocket meshes report distinct colours matching their function family.
4. Open any workflow drawer — timeline rows render (not "No timeline events recorded").
5. `curl http://localhost:3101/api/workflows/index/timeline/<id>` and confirm row count matches the drawer.
6. Existing vitest suite for `web/blueprint` stays green.

## Risks

- **Trail volume.** Per-workflow rockets emit continuously across longer lifetimes than per-event rockets. If trail samples accumulate beyond budget, decay rate or emission interval will need tuning. Mitigation: cap each workflow's trail sample buffer at N (e.g., 200) with FIFO eviction.
- **Per-mesh draw-call overhead.** Negligible at expected scale (10–30 rockets) but watch for regressions if peak workflow count exceeds 100. Mitigation: documented threshold; revert to InstancedMesh with a per-instance colour texture if needed.
- **SSE event-to-city mapping.** The current per-event rocket model already does this resolution. Reuse the same logic; no new mapping work expected.
