# Visualisation reference

The single canonical home for "how the substrate is visualised". Other
docs link here; this page owns the surface inventory, the visual
vocabulary, and the SSE-event → visual mapping. When the visualisation
layer changes, edit here.

> **Where this fits.** Per [docs/README.md](README.md) §2 (Living
> truth), this file owns: the inventory of visualisation surfaces, the
> visual vocabulary, and the SSE-event → visual mapping. The forward
> design that consolidates these surfaces lives in
> [superpowers/specs/2026-05-09-org-building-design.md](superpowers/specs/2026-05-09-org-building-design.md).
> To add a new layer (event, function, entity kind, cadence pip), see
> [visualisation-contributor-guide.md](visualisation-contributor-guide.md).

---

## 1. Surfaces today

The blueprint microsite ([`web/blueprint/`](../web/blueprint/), `:5175`
locally; Azure Container Apps in production) hosts five visualisation
surfaces today. Routing is a single `?view=` switch in
[`web/blueprint/src/App.tsx`](../web/blueprint/src/App.tsx); the
editorial blueprint page is the default.

| Surface | URL | Component | What it shows | Data source | Role |
|---|---|---|---|---|---|
| Editorial blueprint | `/` | [`App.tsx`](../web/blueprint/src/App.tsx) sections | Composition tree, personae, authority, mind-map, observatory ribbon | `GET /api/blueprint/composition` + `GET /api/blueprint/stream` | Pitch — the printed-on-the-page argument |
| 3D Constellation | `/?view=constellation` | [`Constellation.tsx`](../web/blueprint/src/components/Constellation.tsx) (1,270 LOC) | Substrate sphere at centre + sunflower-distributed domain clusters; photon arcs (orange skill / blue tool / red validator); pulses on workflow start/end | `useObservatory()` SSE on `/api/blueprint/stream` | Pitch — full-bleed projection / recording |
| Entities | `/?view=entities` | [`EntitiesPage.tsx`](../web/blueprint/src/pages/EntitiesPage.tsx) | 7 kind tiles (Person / Organisation / Asset / Money / Decision / Place / Period), kind-filtered entity table, recent-links pulse | `GET /api/entities/_stats` (5 s poll) | Day-to-day — entity inspector |
| Functions | `/?view=functions` | [`FunctionsPage.tsx`](../web/blueprint/src/pages/FunctionsPage.tsx) | 9-tile grid of function FMs; tile expands inline to show owned domains + persona-hierarchy tree | `GET /api/functions` (5 s poll) | Drill — per-function detail |
| Org-clone | `/?view=org-clone` | [`OrgClonePage.tsx`](../web/blueprint/src/pages/OrgClonePage.tsx) | Fan-out across entities, in-flight meta-workflows, ambient agents, function FMs, cadence schedule | 5 endpoints (entities/_stats, workflows, functions, functions/{n}/ambient, cadences); 8 s poll | Admin — single-page operator view |

The Control Plane (`:5173`) and Candidate Portal (`:5174`) hold their
own UIs; they are not visualisation surfaces and are out of scope here.

---

## 2. The visual vocabulary

The Constellation establishes the primitives that every other
visualisation surface should re-use to stay coherent.

### Colour

| Channel | Meaning | Source |
|---|---|---|
| Cluster tint | Per-domain, deterministic from `workflow_type` | [`DOMAIN_PALETTE`](../web/blueprint/src/components/Constellation.tsx) (11-colour warm/cool palette) |
| Substrate sphere | Always the same; the centre of gravity | [`SubstrateSphere.tsx`](../web/blueprint/src/components/constellation/SubstrateSphere.tsx) |
| Photon arc — orange | Skill executor running | `durable.executor.invoked` with `executor_type=agent` |
| Photon arc — blue | MCP tool call | `durable.executor.invoked` with `tool` set |
| Photon arc — red | Validator blocked | `durable.validator.blocked` |
| Status pill | `watching` (live) / `connecting` / `offline` | [`useObservatory.status`](../web/blueprint/src/lib/useObservatory.ts) |

### Motion

| Property | Meaning | Notes |
|---|---|---|
| Pulse on cluster | Workflow lifecycle event arriving | Subtle by default; sharp on `workflow.started` / `workflow.resolved` |
| Photon-arc lifetime | Single MCP / skill / validator hop | ~1 s; fades on its own |
| Mote drift | Pending work | Slow drift toward firing cluster |
| Bloom + emissive falloff | Recency | Brighter = more recent |

### Determinism rules

Cluster positions are stable across reloads — the same `workflow_type`
always sits at the same spot in the sky. The placement function is a
Fibonacci-on-sphere scatter
([`sunflower.ts`](../web/blueprint/src/lib/constellation/sunflower.ts),
[`Constellation.tsx::clusterPositions`](../web/blueprint/src/components/Constellation.tsx#L58));
the workflow-type list is sorted alphabetically before placement, so
reads from `/api/blueprint/composition` produce identical scenes on
every load. **Adding a new domain shifts every cluster's position by
one slot** — this is intended (the picture stays self-consistent for
its current set of domains) and is the same trade-off the printed
blueprint makes.

The `?view=entities` and `?view=functions` pages do not yet carry the
3D vocabulary; they use plain CSS tiles. The Org Building spec (§4)
extends the vocabulary into the building backbone.

---

## 3. Event → visual mapping

The visualisation reads the live event bus over Server-Sent Events.
The endpoint is **`/api/blueprint/stream`** (not `/api/observatory/sse`
— the spec uses that name aspirationally). The SSE handler
([`api/server/routes/blueprint.py`](../api/server/routes/blueprint.py))
applies a curated allow-list before forwarding.

### Allow-list today (`_OBSERVATORY_TYPES`)

Anchored at
[`api/server/routes/blueprint.py::_OBSERVATORY_TYPES`](../api/server/routes/blueprint.py).

| Event | Visualised by | What renders |
|---|---|---|
| `workflow.started` / `durable.workflow.started` | Constellation | Pulse on the workflow's cluster |
| `durable.step.started` | Constellation | Cluster brightens for the step |
| `durable.step.completed` | Constellation | Cluster relaxes |
| `durable.executor.invoked` (`executor_type=agent`) | Constellation | Orange skill arc |
| `durable.executor.invoked` (`tool` set) | Constellation | Blue tool arc |
| `durable.validator.blocked` | Constellation | Red validator arc |
| `agent.completed` | Constellation | Skill counter ticks |
| `workflow.exception.detected` | Constellation | Cluster flares |
| `workflow.hitl.requested` / `workflow.hitl.escalated` | Constellation | Persona satellite appears next to the awaiting mote |
| `workflow.policy.violation` | Constellation | Red flare |
| `workflow.sla.breach_imminent` | Constellation | Amber flare |
| `durable.suspended` / `durable.resumed` | Constellation | Awaiting / resuming state |
| `durable.workflow.completed` / `workflow.resolved` | Constellation | Resolution pulse + counter tick |

### Emitted but not yet visualised

Anchored at
[`api/server/services/audit_logger.py`](../api/server/services/audit_logger.py)
and the producers cited below. These types fire on the in-process bus
and land in the audit ledger, but **do not** flow through
`_OBSERVATORY_TYPES` and so do not reach the front-end SSE consumer.

| Event | Producer | Why it matters |
|---|---|---|
| `entity.upserted` | [`entity_reflector.py`](../api/server/services/entity_reflector.py) | Entity flow into the lobby vault (Org Building TASK-019) |
| `entity.linked` | `entity_reflector.py` | Cross-entity relationship lit at zoom-1 |
| `entity.write.failed` | [`meta_workflow_reflector.py`](../api/server/services/meta_workflow_reflector.py), `entity_reflector.py` | Right-rail audit-eligible failure entries (REQ-009) |
| `entity.write.killed` | `entity_reflector.py` | Subscriber kill-switch fired |
| `decision.recorded` | [decision projection](../api/server/services/entity_projections/) | Decision-spark + lobby Decision-vault tick (TASK-020) |
| `ambient.decided` | [`ambient_dispatcher.py`](../api/server/services/ambient_dispatcher.py) | Sensor flash on the floor's ambient indicator (TASK-021) |
| `cadence.tick` | [`state.py`](../api/server/state.py) cadence runner | Cadence clock pulse + ambient flash (TASK-022) |
| `workflow.sub_spawned` | `meta_workflow_reflector.py` | Bright filament between parent and child workflow (TASK-024) |
| `governance.find_entities` / `governance.find_entities.denied` | [`governance/`](../api/server/services/governance/) | Right-rail policy-decision entries |

Closing this gap is the explicit motivation for the Org Building spec
(see its `## Problem` section). The fix is small (≈5–10 LoC widening
of `_OBSERVATORY_TYPES`, plus matching consumer handlers) and is
TASK-001..-002 of that spec.

---

## 4. Where the visualisation is going — the Org Building

The forward design lives in
[2026-05-09-org-building-design.md](superpowers/specs/2026-05-09-org-building-design.md).
One-screen summary:

- **Replaces** the Constellation page at `?view=constellation` (the
  legacy 3D scene is preserved as a togglable "cosmic lens" in the
  bottom-right corner — does not require its own URL).
- **Four zoom levels:** `org` (default — whole 10-floor skyscraper) →
  `wing` (3-4 adjacent floors) → `department` (one function's
  interior) → `workflow` (one workflow's lifecycle in detail).
- **Fixed structural backbone:** 10 floors, one per function FM (CEO
  penthouse + 9 function floors + lobby = entity graph). Floor order
  is canonical and should remain stable across releases — a change
  forces every operator's spatial memory to re-orient.
- **Headline visual primitive — cross-function light-beam elevators.**
  When an entity is touched by workflows from ≥ 2 floors, a beam
  appears between those floors. Beam thickness encodes the number of
  cross-cutting entities. This is the literal proof-shot that the
  org-clone is more than a bag of workflows (REQ-005).
- **Meta-workflows** render as bright filaments between parent and
  child workflow icons at every zoom (REQ-006).
- **Live KPI ticker** on the building facade at zoom-3; full clipboards
  at zoom-1 (REQ-007).
- **Cadence clock** on the building face — wall-clock + 3 cadence
  pip-marks (morning-sweep, period-close, quarterly-okr) (REQ-008).
- **Right-rail event feed** persistent across all zoom levels — most
  recent first; deep-links to entity / decision / workflow / persona
  detail pages (REQ-009).

The spec's 10 phases / 57 TASKs are unchecked at time of writing —
nothing in `web/blueprint/src/components/orgBuilding/` exists yet. The
canonical entry points already exist:

- `useObservatory()` — SSE consumer; will be widened, not replaced.
- `FUNCTIONS` registry ([`api/shared/functions.py`](../api/shared/functions.py))
  — the 10-floor canonical order.
- `DOMAINS` registry ([`api/shared/domains.py`](../api/shared/domains.py))
  — workflow-type → function lookup.
- `audit_logger.py` — emits all 9 not-yet-visualised event types
  (table above).

To prepare to demo the Org Building before the visualisation ships, see
the org-simulation expansion roadmap in
[2026-05-10-simulator-expansion-design.md](superpowers/specs/2026-05-10-simulator-expansion-design.md).

---

## 5. Performance budget

Lifted from the Org Building spec CON-004; applies to any future
high-density visualisation.

| Surface | Target | How |
|---|---|---|
| Org Building zoom-3 (whole building) | ≥ 60 fps | `InstancedMesh` for window panels and entity motes (≤ 1000 visible at once); LOD on distant floors |
| Org Building zoom-1 (department interior) | ≥ 45 fps | Flat-shaded glow on tiles (no per-tile expensive shaders); reuse one material per kind |
| Constellation today | 60 fps comfortable on a MacBook Pro | `additive points + bloom`; cluster mote pool capped per cluster |
| Polling pages (entities / functions / org-clone) | <100 ms render budget | 5–8 s poll cadence; no live SSE; tile counts kept under 100 |

If a new layer would push past these budgets, gate it behind a
toggle (see the `bottom-strip layer-toggle controls` pattern in
TASK-026 of the Org Building spec).

---

## 6. Known limitations / explicitly out of scope

- **Mobile / small-screen.** All visualisation surfaces are desktop-first
  (operator workstation / projection). Mobile users get the simpler
  `?view=entities` and `?view=functions` polling pages.
- **Embedded fleet-manager iframe interactions.** The `embed=1` flag
  on `?view=constellation` only suppresses the "← return to the page"
  link; deeper iframe-host messaging is not implemented.
- **Multi-tenant tinting.** A single tenant's events are rendered. No
  partitioning of clusters by tenant. Reaching that needs an
  SSE-topic-partitioning substrate change (see Tier 3 of the
  simulator-expansion spec).
- **Replay scrubber / time-travel.** No recorded SSE tail can be
  scrubbed in the UI. Recording happens server-side
  (`data/blueprint-recordings/*.jsonl`) and replays on a fresh
  EventSource connect, but the UI has no scrubber control.
- **Mocked production deploy.** The Azure Container Apps build is
  intentionally Scope A — only recorded events replay; no live durable
  runtime, no live MCPs. See
  [ARCHITECTURE.md §The blueprint microsite](ARCHITECTURE.md#the-blueprint-microsite--separate-cloud-surface).

---

## 7. Cross-references

- **Add a new visualisation layer** → [visualisation-contributor-guide.md](visualisation-contributor-guide.md)
- **The forward design** → [superpowers/specs/2026-05-09-org-building-design.md](superpowers/specs/2026-05-09-org-building-design.md)
- **Drive the visualisation from the simulator** → [superpowers/specs/2026-05-10-simulator-expansion-design.md](superpowers/specs/2026-05-10-simulator-expansion-design.md)
- **How the blueprint microsite ships to Azure** → [blueprint-microsite-contributor-guide.md](blueprint-microsite-contributor-guide.md)
- **Code-anchored architecture** → [ARCHITECTURE.md](ARCHITECTURE.md)
- **Codebase tour (front-end section)** → [CODEBASE-TOUR.md](CODEBASE-TOUR.md)
