---
goal: Replace the existing 3D Constellation page with "The Org Building" — a 2.5D / 3D zoom-first visualisation that shows the live agentic org at four levels of scale (whole org → wing → department → workflow), making entities, decisions, ambient agents, cadences, MCP calls, and cross-department flows visible at every zoom. Preserve the existing cosmic aesthetic as a togglable lens. Replaces, not adds — one URL (`?view=constellation`), one canonical view, one story.
version: 1.0
date_created: 2026-05-09
last_updated: 2026-05-09
owner: Zava Control Plane — substrate
status: 'Draft'
tags: [feature, frontend, blueprint, observatory, agentic-org, visualisation]
---

# The Org Building — design spec

![Status: Draft](https://img.shields.io/badge/status-Draft-lightgrey)

## Problem

Phases 1-4 of the agentic-org rollout shipped 1018 passing tests + a fully working substrate (entity graph, function FMs, ambient dispatcher, cadence loop, KPI store, precedent queries, meta-workflows, three observatory pages). When the operator opens `?view=constellation` (the existing 3D scene) **or** the Fleet Manager session UI, **none of the agentic-org work is visible**. The Constellation shows workflow-centric activity but knows nothing about entities, functions, decisions, ambient agents, cadences, or cross-department flows. The new pages (`?view=entities`, `?view=functions`, `?view=org-clone`) are isolated and discoverable only by URL. The substrate is alive but invisible.

## What we're building

A new visualisation, addressed at the existing `?view=constellation` URL (replaces the current scene), that:

1. **Has a fixed structural backbone** the eye learns once and never has to re-orient against (a 10-storey building, one floor per function FM)
2. **Reveals detail through zoom**, not through "everything visible at once" (4 zoom levels — org → wing → department → workflow)
3. **Animates events on top of the fixed backbone**, with one signal per visual property (so colour means kind, pulse means activity, glow means recency — never overloaded)
4. **Tells the org-clone story end-to-end**, with cross-function entity reuse and meta-workflow filaments rendered as the literal headline visual primitive
5. **Preserves the existing 3D Constellation as one togglable lens** for pitch moments

## 1. Requirements & Constraints

- **REQ-001**: New surface replaces the existing Constellation page at `web/blueprint/src/pages/ConstellationPage.tsx`. Same URL (`?view=constellation`), same role ("the substrate, running"). Old scene preserved in git history; available as togglable "cosmic lens" within the new page (does not require a separate URL).
- **REQ-002**: Four zoom levels — `org` (default), `wing`, `department`, `workflow`. Smooth camera transitions (~400ms ease-in-out). Pinch-zoom + scroll-wheel + click-to-focus + ESC/back nav.
- **REQ-003**: Building metaphor — the structural backbone is a 10-floor skyscraper rendered in 3D cutaway. CEO-FM = penthouse on top; 9 function floors below in functional grouping; ground floor / lobby = the entity graph (Persons / Orgs / Assets / Money / Decisions / Places / Periods vaults).
- **REQ-004**: Live event reactions on the backbone — `entity.upserted`, `entity.linked`, `decision.recorded`, `ambient.decided`, `cadence.tick`, `workflow.completed`, `workflow.sub_spawned` each map to one specific animated overlay. See §4 for the per-event mapping.
- **REQ-005**: Cross-function entity reuse rendered as **persistent inter-floor light beams** (elevators) at zoom-3, **inter-department flows** at zoom-2, and **highlighted entity references** at zoom-1 / zoom-0. This is the headline visual primitive — the literal proof that the org-clone is more than a bag of workflows.
- **REQ-006**: Meta-workflows (`workflow.sub_spawned`) rendered as **bright filaments** between parent and child workflow icons at every zoom — most prominent at zoom-3 (cross-floor) and zoom-1 (intra-department).
- **REQ-007**: Live KPI strips per floor, sourced from `KpiStore` via `/api/functions/{name}/kpis-latest` (a small new endpoint to add) OR computed client-side from existing `/api/functions[].kpis` static metadata + sparkline polling. Bloomberg-style ticker on the building facade at zoom-3; full clipboards at zoom-1.
- **REQ-008**: Cadence timeline at zoom-3 — horizontal "now" needle + plotted cadence dots (morning-sweep, period-close, quarterly-okr) — visible on the building face.
- **REQ-009**: Right-rail event feed at every zoom level — chronological tail of audit-eligible events (`decision.recorded`, `ambient.decided`, `cadence.tick`, `workflow.sub_spawned`, `entity.write.failed`, `governance.find_entities.denied`). Each entry deep-links to the entity / decision / workflow / persona.
- **REQ-010**: Backend SSE filter widening — verify `/api/observatory/sse` relays the new event types; widen the filter if necessary. ~5-10 LoC change in `api/server/services/sse_hub.py` or the observatory route.
- **REQ-011**: Preserve the existing photon-arc visual language (skill/tool/validator orange/blue/red) at zoom-0 (workflow level) — workflows currently emit these via `step.started`, `tool.invoked`, etc. They render as local arcs on the firing planet/workstation.
- **REQ-012**: Default landing = zoom-3 (whole building, slowly orbiting). User can zoom in to anything at any time.
- **REQ-013**: "Cosmic lens" toggle (bottom-right button) — switches the centre area to the existing 3D Constellation scene for pitch moments. Toggle off = back to building. Cosmic lens preserves the existing `useObservatory` event stream.
- **SEC-001**: Click-to-deep-link goes through existing API surfaces only — no new bypass paths into entities / workflows / personae. The right-rail event feed entries link to existing detail pages.
- **SEC-002**: Entity card (slide-in from the right when an entity mote is clicked at zoom-1) reads via the existing `GET /api/entities/{id}` + `GET /api/entities/{id}/linked` endpoints. No new API surface.
- **CON-001**: One canonical URL (`?view=constellation`). The old standalone `?view=entities`, `?view=functions`, `?view=org-clone` pages stay alive (don't break existing operator bookmarks) but the building view becomes the primary pitch + day-to-day surface.
- **CON-002**: Replacement is non-destructive — preserve the existing 3D Constellation as a JS module reachable from the cosmic-lens toggle. Old `Constellation.tsx` becomes `CosmicConstellation.tsx`; new building lives in `OrgBuilding.tsx`.
- **CON-003**: No new substrate dependencies. Re-uses the same R3F + drei + postprocessing libs already in `package.json` for the building's 3D rendering. 2D HUD elements use plain React + CSS.
- **CON-004**: Performance budget — ≥60fps on the operator's MacBook Pro at zoom-3; ≥45fps at zoom-1 (the most detail-rich level). Use `InstancedMesh` for entity motes (≤1000 visible at once); LOD for distant floors at zoom-3.
- **CON-005**: First build does NOT need to be production-grade visual polish. The structural backbone + event animations + zoom transitions are the v1 contract. Polish (lighting, materials, ambient particles) comes in v2.
- **GUD-001**: One signal per visual property. Colour = entity kind. Pulse rate = activity intensity. Glow intensity = recency. Beam thickness = entity-reuse cardinality. Never overload a property with multiple meanings.
- **GUD-002**: Animation should be subtle by default (gentle pulses, slow drifts) and bright/sharp only on rare meaningful events (decision.recorded, ambient.decided, cadence.tick, workflow.sub_spawned). The eye should be drawn to the rare events, not exhausted by constant motion.
- **GUD-003**: All overlays toggleable from a bottom-strip control panel. User can turn off any layer (heat / entity flows / cross-function streaks / cadence pulses) to reduce visual load when investigating.
- **PAT-001**: Backbone is fixed; motion is layered on top. The 10 floors of the building never reposition; only window lights, beams, and floating elements animate.
- **PAT-002**: Hierarchical zoom matches semantic hierarchy — zoom-3 (org) → zoom-2 (wing of related functions) → zoom-1 (one function floor) → zoom-0 (one workflow). Each level inherits the right-rail event feed but the centre stage shows only the level's relevant elements.
- **PAT-003**: Camera transitions are dolly-and-tween, not jump-cuts. Apple-style ease-in-out (~400ms) so the spatial relationship is preserved.
- **PAT-004**: Click-to-drill — every visible element (floor, persona, workstation, ambient sensor, entity vault, workflow) is a click target that focuses the camera + transitions one level deeper.

## 2. Implementation Steps

### Implementation Phase 1 — Backend SSE filter widening + KPI snapshot endpoint

- GOAL-001: The frontend can subscribe to the full event stream (all agentic-org event types) over SSE, and can fetch the latest KPI snapshot per function via a single endpoint. Both prerequisites for the front-end build.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Audit `api/server/services/sse_hub.py` and `/api/observatory/sse` to confirm which event types currently relay to the front-end. The existing `useObservatory` hook already receives `workflow.*`, `step.*`, `tool.*`, `agent.*`. Verify by inspecting the topic broadcast filter and the SSE route handler. Document findings in this commit's message. | | |
| TASK-002 | If `entity.upserted`, `entity.linked`, `decision.recorded`, `ambient.decided`, `cadence.tick`, `workflow.sub_spawned`, `entity.write.failed`, `entity.write.killed`, `governance.find_entities`, `governance.find_entities.denied` do NOT flow to `/api/observatory/sse`, widen the filter to include them. ~5-10 LoC. Add `tests/api/server/services/test_sse_observatory_filter.py` asserting all the new types relay through. | | |
| TASK-003 | Add `GET /api/functions/{name}/kpis-latest` endpoint to `api/server/routes/functions.py` returning `{metric: latest_value, since: ts}` per KPI declared on `FUNCTIONS[name].kpis`. Reads from `app_state.kpi_store.query(function=name)` and reduces to latest-per-metric (DEC-OQ3 schema-version-tolerant). Returns `{}` if no KPIs published. Add `tests/api/server/routes/test_functions_kpis_latest.py`. | | |
| TASK-004 | Smoke: boot the server, emit one of each new event type via the in-process bus, confirm a curl-tail of `/api/observatory/sse` receives them. Document in this commit. | | |

### Implementation Phase 2 — Frontend scaffolding: page + zoom router + lens toggle

- GOAL-002: A new `OrgBuilding.tsx` component renders behind the existing Constellation route. Empty backbone; zoom router works; cosmic-lens toggle swaps to the legacy 3D scene. Foundation for the rest of the build.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Rename `web/blueprint/src/components/Constellation.tsx` → `web/blueprint/src/components/CosmicConstellation.tsx`. Preserves the existing 3D scene as a togglable lens. Update all imports (likely just `ConstellationPage.tsx` + the editorial Observatory section). Verify the existing Constellation still renders unchanged at `?view=constellation` after rename. | | |
| TASK-006 | Create `web/blueprint/src/components/OrgBuilding.tsx` — empty stub that renders a placeholder 3D scene (just a tall extruded box for the building) using R3F + Canvas + OrbitControls. Same scene primitives as `CosmicConstellation.tsx`. Sets up the camera, lighting, postprocessing rig. | | |
| TASK-007 | Create `web/blueprint/src/lib/orgZoom.ts` — zoom-state machine. Defines `ZoomLevel = 0 \| 1 \| 2 \| 3`, `ZoomTarget = {kind: 'org' \| 'wing' \| 'department' \| 'workflow', id?: string}`, `useOrgZoom()` hook that exposes `{level, target, zoomTo(target), zoomOut(), zoomIn()}`. Camera position + lookAt + FOV per zoom-level live here. | | |
| TASK-008 | Update `ConstellationPage.tsx` — replace the `<Constellation />` render with: `<OrgBuilding />` by default + a bottom-right toggle button "Cosmic lens" that swaps to `<CosmicConstellation />`. Toggle state = `useState(false)`; press / click toggles. ESC at zoom-0 / zoom-1 / zoom-2 zooms out one level via `useOrgZoom().zoomOut()`. ESC at zoom-3 with cosmic-lens-off is a no-op (already at top level). | | |
| TASK-009 | Add a tiny test/storybook-equivalent: `tests/web/blueprint/test_org_building_render.tsx` — smoke that the page mounts without error, the toggle switches between the two scene components, and the zoom router accepts each level. (Vite + Playwright or just a vitest jsdom render — match existing frontend test conventions.) | | |

### Implementation Phase 3 — Backbone: 10-floor building at zoom-3

- GOAL-003: The default zoom-3 view shows a recognisable 10-storey skyscraper with one floor per function FM (CEO-FM penthouse on top, 9 function floors below, ground-floor lobby for the entity graph). Window lights = activity intensity per floor. KPI ticker on the facade. Cadence clock on the building face. No animations yet beyond steady-state rendering.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-010 | Create `web/blueprint/src/components/orgBuilding/Building.tsx` — the 3D skyscraper. 11 stacked floor meshes (penthouse + 9 function floors + lobby). Each floor is a `<group>` with: a translucent floor slab, a colored backdrop accent (function colour), a label mesh ("Finance", "HR", etc.), and a placeholder for windows (next TASK). Functions ordered top-down: ceo, finance, revenue, hr, ops, legal, marketing, tech, data, customer-success, lobby. Order matches functional grouping (money near top, support near bottom). | | |
| TASK-011 | Create `web/blueprint/src/components/orgBuilding/Window.tsx` — one window panel per workflow icon on each floor (~6 windows per floor, one per owned domain). Each window has a `lit: boolean` prop. Lit windows glow the floor's colour; dim windows are nearly invisible. `InstancedMesh` for performance. Static layout per floor at zoom-3 (no animation yet). | | |
| TASK-012 | Create `web/blueprint/src/lib/useOrgData.ts` — hook that fetches and caches `/api/functions`, `/api/entities/_stats`, `/api/cadences` on mount + every 5s. Returns `{functions, entityCounts, cadences, status}`. Used by every zoom level. | | |
| TASK-013 | Wire `Building.tsx` to `useOrgData()` — render one floor per non-legacy function (in the canonical top-down order from TASK-010), labelled with display name + KPI count. Lobby (ground floor) shows entity counts as 7 stacked icons (Person/Org/Asset/Money/Decision/Place/Period) with live count tickers. CEO-FM penthouse pulses gently. | | |
| TASK-014 | Add KPI ticker on the building facade — for each floor, render a small marquee text strip showing the floor's `kpis` from `/api/functions[].kpis` (e.g. "DSO 28 ▼  DPO 41 ▲  budget-variance-pct 2.1 ▲"). Source from `/api/functions/{name}/kpis-latest` (poll every 5s). When no KPIs published, show "—" placeholder. | | |
| TASK-015 | Add cadence clock on the building face — a small circular widget bottom-right of the building backbone, showing current wall-clock + 3 cadence pip-marks (next morning-sweep, next period-close, next quarterly-okr). Source from `/api/cadences` next_run_at. Hand sweeps in real time (1Hz update). | | |
| TASK-016 | Add status pill top-left ("watching" / "connecting" / "offline") — pull from `useObservatory.status` (existing). Style to match the existing Constellation HUD. | | |
| TASK-017 | Smoke test the zoom-3 view manually — boot stack with `make up` + `ENTITY_PLANE_ENABLED=1`, navigate to `?view=constellation`, confirm the skyscraper renders with 10 floors visible, KPI tickers present (or "—"), cadence clock ticks, status pill reads "watching". Capture a screenshot for the spec. | | |

### Implementation Phase 4 — Animated event overlays at zoom-3

- GOAL-004: Live events from the SSE stream animate on top of the static backbone. The eye is drawn to rare meaningful events (decisions, ambient triggers, cadence ticks, sub-spawn filaments); steady-state shows only gentle activity heat.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-018 | Extend `useOrgData.ts` to subscribe to the `useObservatory` SSE stream + dispatch incoming events to a `useReducer`-managed animation queue. Queue holds `{kind: 'spark' \| 'beam' \| 'pulse' \| 'filament', target: ..., t: number}` entries. Animation loop in `OrgBuilding.tsx` consumes from queue per-frame + advances existing entries. | ✓ | 2026-05-09 |
| TASK-019 | `entity.upserted` event handler — drift a small mote from the firing workflow's window down to the lobby's entity vault (the kind-coded icon stack). Brief brighten of the destination icon + count tick. Use `InstancedMesh` for the mote pool. | ✓ | 2026-05-09 |
| TASK-020 | `decision.recorded` event handler — bright spark at the firing workflow's window + photon trail down to the lobby's Decision vault (violet trail). Decision count tick visible at the lobby. | ✓ | 2026-05-09 |
| TASK-021 | `ambient.decided` event handler — flash of the floor's ambient agent indicator (small sensor-icon mounted on the floor's facade, one per ambient agent). Optional small spawn-arc outward from the firing floor. | ✓ | 2026-05-09 |
| TASK-022 | `cadence.tick` event handler — pulse the cadence clock + flash the firing function's ambient sensor icon. | ✓ | 2026-05-09 |
| TASK-023 | `workflow.completed` event handler — gentle pulse of the corresponding window (no spark, just brightness ticking up briefly then fading). | ✓ | 2026-05-09 |
| TASK-024 | `workflow.sub_spawned` event handler — bright filament from the parent workflow's window to the child workflow's window. If the child is on a different floor, the filament traces between floors (this is the meta-workflow visual). | ✓ | 2026-05-09 |
| TASK-025 | Cross-function entity reuse — persistent inter-floor light beam between two floors when an entity has source_workflows spanning both. Beam thickness = number of cross-cutting entities. Computed client-side by joining `/api/entities/_stats.hot` (hot entities + their source_workflows) with `/api/functions[].owns_domains` (workflow_type → function lookup). Beams fade after 30s of no new cross-cutting upserts. | ✓ | 2026-05-09 |
| TASK-026 | Bottom-strip layer-toggle controls — checkboxes to enable/disable: activity heat, entity flows, decision sparks, ambient flashes, cadence pulses, cross-function beams, cosmic-lens. State persisted to localStorage so the user's preferences survive reloads. | ✓ | 2026-05-09 |
| TASK-027 | Smoke test live with `make up` + simulator inject of 5 fleet workflows + auto-close personae list — confirm: window lights tick on, cadence clock ticks, decision sparks appear, cross-function beams appear when a vendor is touched by ≥2 functions. Capture a video / screen recording for the spec. | deferred | 2026-05-09 |

### Implementation Phase 5 — Right-rail event feed (all zoom levels)

- GOAL-005: Persistent right-rail event feed, sticky across zoom transitions. Most-recent-first; ~50-entry rolling tail. Each entry deep-links to its source (entity / workflow / persona / decision).

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-028 | Create `web/blueprint/src/components/orgBuilding/EventFeed.tsx` — fixed-position right-rail panel (~280px wide). Subscribes to `useObservatory`. Renders the last 50 events as one-line entries (`14:01:33 ⚖ decision.recorded VKY-0001 finance_signoff (cfo)`). Auto-scrolls to top on new events; pauses auto-scroll if user has scrolled away. | ✓ | 2026-05-09 |
| TASK-029 | Each entry deep-links to its source: decision → `/api/entities/{decision_id}` opens the entity card; workflow event → existing workflow detail page; entity event → entity card slide-in. | ✓ | 2026-05-09 |
| TASK-030 | Filter chips at the top of the feed — toggle to show only decisions / only ambient / only cadence / only meta-workflow. Filter state persists to localStorage. | ✓ | 2026-05-09 |

### Implementation Phase 6 — Zoom level 2: a wing (3-4 adjacent floors)

- GOAL-006: Camera flies to a wing of related function floors when the user clicks a floor's "wing" indicator (or scroll-zooms past zoom-3). Wing-level shows 3-4 floors with their inter-floor connections + KPIs more legible. Mostly a camera repositioning + LOD swap; no new visual elements beyond zoom-3.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-031 | Define wing groupings in `web/blueprint/src/lib/orgWings.ts`: `Money` (finance + revenue), `People` (hr), `Operations` (ops + tech + data), `Front-office` (marketing + legal + customer-success), `C-suite` (ceo). Constant exported as `WINGS`. | ✓ | 2026-05-09 |
| TASK-032 | Extend `useOrgZoom()` to support `target.kind === 'wing'`. Camera position computed to frame all floors of the named wing (each wing has 1-3 floors). Smooth tween from zoom-3 position. | ✓ | 2026-05-09 |
| TASK-033 | Wing-level UI: when zoomed in, the inactive floors fade to ~30% opacity + the active wing's floors brighten + KPI tickers grow legible (font scales up). | ✓ | 2026-05-09 |
| TASK-034 | Smoke: click a floor at zoom-3, confirm camera flies to its wing. ESC zooms back to zoom-3. | ✓ | 2026-05-09 |

### Implementation Phase 7 — Zoom level 1: one department (one function's floor, interior)

- GOAL-007: Camera flies inside one function's floor. Interior-cutaway view shows the floor's CFO-FM corner office, persona-hierarchy desks, owned-domain workstations, ambient sensors, entity vault, KPI clipboards, cadence calendar. Interactive — click anything to drill to zoom-0 (workflow detail).

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-035 | Create `web/blueprint/src/components/orgBuilding/DepartmentInterior.tsx` — interior-cutaway 3D scene for one function. Reads `/api/functions/{name}` for persona hierarchy + owned-domains + ambient agents. Renders: a corner-office tile for the function FM (pulses on session activity), a desk-cluster per persona-hierarchy node (one tile per role, indented to show reporting), a workstation tile per owned-domain (small monitor glyph), an ambient-sensor tile per ambient agent (camera glyph mounted on a wall). | ✓ | 2026-05-09 |
| TASK-036 | Entity vault rendering at zoom-1: a row of 7 vault icons (one per kind) along one wall, each showing the count of entities the function "touches" (joined client-side: entities whose source_workflows include any workflow_type in `FUNCTIONS[name].owns_domains`). Click any vault icon → opens entity-list panel filtered to that kind + this function. Click any entity in the list → entity card slide-in. | ✓ | 2026-05-09 |
| TASK-037 | KPI wall at zoom-1: 4-6 clipboard tiles, one per KPI in `FUNCTIONS[name].kpis`. Each clipboard shows: metric name, latest value, sparkline of last 30 snapshots (from `/api/functions/{name}/kpis-latest` extended to return history). | ✓ | 2026-05-09 |
| TASK-038 | Cadence calendar at zoom-1: small wall-calendar tile showing this function's relevant cadences (e.g. CFO floor shows period-close + quarterly-okr; HR shows morning-sweep). Pip-marks on day cells where cadences fire next. | ✓ | 2026-05-09 |
| TASK-039 | Live event animations at zoom-1 — the same SSE-driven animations as zoom-3, but rendered on the interior tiles (decision spark on the persona desk who decided; entity mote drifts to the entity vault; ambient flash on the sensor; meta-workflow filament from workstation to workstation). | ✓ | 2026-05-09 |
| TASK-040 | Click handlers — clicking a workstation zooms to zoom-0 (workflow detail) for the most recent in-flight workflow on that domain (or opens a list if multiple in-flight). Clicking a persona opens a sidebar with their pending HITL gates + recent decisions (read from `/api/persona/{role}/recent` — small new endpoint, or computed client-side from event tail). | ✓ | 2026-05-09 |
| TASK-041 | Smoke: from zoom-3 click on Finance floor → flies to Finance interior → confirm CFO-FM tile present, persona desks render in hierarchy order, 6 workstations visible, 3 ambient sensors visible, 7 entity vault icons with counts, 4 KPI clipboards, cadence calendar. ESC zooms back to zoom-3. | ✓ | 2026-05-09 |

### Implementation Phase 8 — Zoom level 0: one workflow (full detail)

- GOAL-008: Camera flies to one workflow's "workstation" and shows its lifecycle in detail — phase timeline, current MCP calls firing, HITL gate state, entities touched, decisions recorded so far, audit ledger tail. Replaces the role of today's `WorkflowDetail` page within the building view.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-042 | Create `web/blueprint/src/components/orgBuilding/WorkflowZoom.tsx` — full-screen-ish detail panel for one workflow. Reads `/api/workflows/{id}` (existing) for workflow shape + phase + status. Reads `/api/entities/touched-by/{wf_id}` (existing) for entities. | ✓ | 2026-05-09 |
| TASK-043 | Phase timeline at zoom-0: a horizontal strip of phase tiles (intake → classify → route → audit etc.), each showing kind (deterministic / agent / hitl), current state (queued / running / done / awaiting). Photon arcs (skill/tool/validator) fire local to the running tile (preserve today's visual primitive). | ✓ | 2026-05-09 |
| TASK-044 | MCP calls panel at zoom-0: list of currently-firing tool calls (from `tool.invoked` events that haven't completed yet). Updates live from SSE. | ✓ | 2026-05-09 |
| TASK-045 | HITL gate panel at zoom-0: when the workflow is awaiting a HITL decision, show the gate's persona + the auto-close status + any pending decision payload preview. | ✓ | 2026-05-09 |
| TASK-046 | Entities-touched panel at zoom-0: list (or grid) of entities currently in this workflow's source_workflows. Each entity is clickable → opens its entity card. Cross-function entity badge appears when an entity is also touched by other-function workflows. | ✓ | 2026-05-09 |
| TASK-047 | Decisions-so-far panel at zoom-0: list of decisions emitted by the projection from this workflow's payload. Each decision shows ULID, persona, verdict, reason, decided_at. | ✓ | 2026-05-09 |
| TASK-048 | Audit-tail panel at zoom-0: chronological tail of all events for this workflow_id, scrollable. | ✓ | 2026-05-09 |
| TASK-049 | Smoke: from zoom-1 (Finance floor) click on the ap-invoice workstation → flies to one in-flight ap-invoice workflow's WorkflowZoom view → confirm phase timeline, MCP calls, HITL gate, entities touched, decisions, audit tail all populate. ESC zooms back to zoom-1. | ✓ | 2026-05-09 |

### Implementation Phase 9 — Cosmic lens preservation

- GOAL-009: The existing 3D Constellation is reachable as a togglable lens from the new building view. Doesn't replace anything; preserves the pitch-moment aesthetic.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-050 | Bottom-right toggle button "Cosmic lens" in `ConstellationPage.tsx` → swaps the centre area from `<OrgBuilding />` to `<CosmicConstellation />` (the renamed legacy scene from TASK-005). Toggle off = back to building. State held in `useState(false)`. | ✓ | 2026-05-09 |
| TASK-051 | Smoke: confirm the cosmic lens still renders the existing scene with all its photon arcs, status pill, counts ribbon. Toggle off, confirm building view returns. | pending ralph-loop | |

### Implementation Phase 10 — Performance + polish + smoke

- GOAL-010: Performance budget met (≥60fps at zoom-3, ≥45fps at zoom-1). Visual polish on the building (lighting, materials). End-to-end smoke + screen recording for stakeholder review.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-052 | Profile the building scene at zoom-3 with 1000+ motes in flight + 50 events/sec via the simulator ramp. Record fps. If <60fps: add LOD on motes (zoom-out → cloud render; zoom-in → individual). Use `InstancedMesh` for window panels + entity motes. | ✓ | 2026-05-09 |
| TASK-053 | Profile zoom-1 (department interior) with the same load. Target ≥45fps. If <45fps: reduce per-tile shader cost (replace fancy materials with flat-shaded glow). | ✓ | 2026-05-09 |
| TASK-054 | Lighting + material polish — tune the building's emissive material so floors glow gently at rest + brightly during activity. Background backdrop (cosmic stars, low contrast) so the building doesn't float in pure black. | ✓ | 2026-05-09 |
| TASK-055 | Run an end-to-end smoke: `make up` + 11 simulator injects (one per fleet domain) + full PERSONA_AUTO_CLOSE list. Record a 60s screen capture showing: (a) zoom-3 with window lights + cadence clock + KPI tickers; (b) cross-function beam appearing as a vendor is touched by 2 functions; (c) decision spark + filament from sub-spawn; (d) zoom into Finance interior (zoom-1); (e) zoom into one ap-invoice workflow (zoom-0). Save to `docs/superpowers/specs/2026-05-09-org-building-design.smoke.mp4` (or .webm). | pending ralph-loop | |
| TASK-056 | Update `web/blueprint/src/sections/Observatory.tsx` to point the existing "Live entity graph" link at the new `?view=constellation` building view (was pointing at `?view=entities`). Old `?view=entities` and `?view=org-clone` pages stay alive for now — separate retirement decision. | ✓ | 2026-05-09 |
| TASK-057 | Final commit + plan-status bump + screenshot in PR description. | pending ralph-loop | |

## 3. Done means

> A new operator opens `?view=constellation`, sees a 10-floor building breathing with activity, and within 30 seconds understands: (a) the org has 10 functions arranged hierarchically, (b) workflows are running inside each, (c) entities are flowing into the lobby, (d) decisions are being recorded, (e) cadences are scheduled, (f) some entities matter to multiple functions. They click a floor and zoom inside; click a workstation and zoom to one workflow; ESC back out. The cosmic-lens toggle preserves the original aesthetic.
>
> The `?view=constellation` URL is the canonical demo + day-to-day surface. The substrate is finally visible.

Smoke commands:
```bash
make up   # full stack
# In separate terminals or via curl:
for ep in fleet-vendor-kyc fleet-employee-onboarding fleet-treasury-fx fleet-purchase-order creative-campaign \
          fleet-ap-invoice fleet-perf-review fleet-contract-renewal fleet-contract-review \
          fleet-privacy-dpia fleet-it-access-request; do
  curl -X POST http://localhost:3001/api/simulator/$ep -H 'Content-Type: application/json' -d '{}' && sleep 2
done
open 'http://localhost:3001/?view=constellation'
# Watch zoom-3 for 30s — should see entity counts ticking, cadence clock sweeping,
# decision sparks firing as workflows complete, cross-function beams when vendors are
# referenced by ≥2 functions.
```

Acceptance, mapped to TASKs:
- Backend SSE relays the new event types → TASK-001..-004
- Building backbone renders at zoom-3 → TASK-005..-017
- Live event animations at zoom-3 (entity flows + decisions + ambient + cadence + sub-spawn + cross-function beams) → TASK-018..-027
- Persistent event feed across zoom levels → TASK-028..-030
- Wing-level zoom-2 → TASK-031..-034
- Department interior zoom-1 (CFO-FM tile + persona desks + workstations + entity vault + KPI wall + cadence calendar + interior animations + drill click) → TASK-035..-041
- Workflow detail zoom-0 (phase timeline + MCP calls + HITL gate + entities-touched + decisions + audit) → TASK-042..-049
- Cosmic lens toggle preserves legacy 3D → TASK-050..-051
- Performance budget met + screen recording captured → TASK-052..-055
- Observatory section + nav links updated → TASK-056..-057

## 4. Visual references / inspiration

Patterns this design borrows from:
- **Datadog Service Map / Lightstep**: fixed nodes, animated edges
- **Bloomberg Terminal**: dense always-on numerical strips on a fixed grid
- **Cities: Skylines population overlay**: fixed map, toggleable overlays per dimension
- **Honeycomb / Lightstep distributed tracing**: hierarchical drill from service → endpoint → trace
- **CERN particle event displays**: fixed detector geometry + animated overlay tracks
- **Apple Mac OS Mission Control**: zoom hierarchy from Spaces → app → window
- **Tony Stark's lab (MCU)** / architectural cutaway renderings: 3D building visible in cross-section with all floors lit

Visual primitives reused from the existing 3D Constellation:
- R3F + drei + postprocessing libs
- Cosmic backdrop (stars, low-contrast nebula)
- Bloom + emissive materials for the "luminous" feel
- Photon arcs (orange skill / blue tool / red validator) at zoom-0

Visual primitives NOT inherited (new):
- Building structural backbone (stacked floor meshes)
- Window-light density per floor
- KPI ticker marquee on facade
- Cadence clock widget
- Cross-function light-beam elevators
- Interior-cutaway department view
- Phase-timeline strip at zoom-0

## 5. Open questions to flag for v1 implementation

1. **Wing-level zoom-2** — is this actually a useful intermediate level, or should we skip it (zoom-3 → zoom-1 directly)? Recommend: build it; cheap to add (mostly camera reposition); demo flow benefits from "zoom out from a department to see its sister departments" beat.
2. **CFO-FM session activity** — how do we know the FM is "in session"? Check for an open SSE topic subscriber on `fleet-manager.<name>`? Or read from `/api/functions/{name}/sse` connection count? Spec deferred to TASK-013 implementation.
3. **Persona pending-HITL count** — is there an existing endpoint, or do we compute client-side from `/api/exceptions`? Spec deferred to TASK-040 implementation.
4. **KPI history sparklines** — `/api/functions/{name}/kpis-latest` returns only the latest. We need a `?since=<ts>` variant for sparkline history. Add as a TASK-037 sub-step.
5. **Mobile / small-screen** — out of scope for v1. Building view is desktop-first (operator workstation). Mobile gets the existing simpler `?view=entities` + `?view=functions` pages until further notice.
