# Visualisation reference

> **Constellation is Zava's visual command surface.** Its narrative job is to orient the
> viewer, show concurrent work across the organisation, let a viewer follow one decision
> from trigger to outcome, expose shared capabilities (skills, tools, policies), name
> governance outcomes, and identify where customer systems connect. See the canonical
> story spec for the full product narrative and claim boundaries:
> [superpowers/specs/2026-08-10-zava-constellation-story-design.md](superpowers/specs/2026-08-10-zava-constellation-story-design.md).

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
> the **Visualisation Contributor Guide** appended to this same file
> below.

> **2026-05-12 status — partially stale.** The `?view=` routing in §1
> was removed and then re-added (commit `278cffad`) so the new
> `AccountsPage` (and the existing `EntitiesPage` / `FunctionsPage` /
> `OrgClonePage` / `ConstellationPage`) are reachable again. The
> deployed blueprint bundle is now a static nginx container with
> bundled fixtures — the `?view=` pages call live `/api/...`
> endpoints and so only work against a local FastAPI backend; the
> editorial Observatory section in the deployed bundle is driven by
> [`useReplayObservatory`](../web/blueprint/src/lib/useReplayObservatory.ts).
> The `Constellation` surface inventoried below also pre-dates the
> cosmic-lens v2 refactor; see
> [ARCHITECTURE.md §7](ARCHITECTURE.md#7-cosmic-lens-ui-architecture)
> for the current scene tree under
> `web/blueprint/src/components/cosmicLens/`.

---

## 1. Surfaces today

The blueprint microsite ([`web/blueprint/`](../web/blueprint/), `:5275`
locally; Azure Container Apps in production) hosts six visualisation
surfaces today. Routing is a single `?view=` switch in
[`web/blueprint/src/App.tsx`](../web/blueprint/src/App.tsx); the
editorial blueprint page is the default.

| Surface | URL | Component | What it shows | Data source | Role |
|---|---|---|---|---|---|
| Editorial blueprint | `/` | [`App.tsx`](../web/blueprint/src/App.tsx) sections | Composition tree, personae, authority, mind-map, observatory ribbon | `GET /api/blueprint/composition` + `GET /api/blueprint/stream` | Pitch — the printed-on-the-page argument |
| 3D Constellation | `/?view=constellation` | [`Constellation.tsx`](../web/blueprint/src/components/Constellation.tsx) (1,270 LOC) | Substrate sphere at centre + sunflower-distributed domain clusters; photon arcs (orange skill / blue tool / red validator); pulses on workflow start/end | `useObservatory()` SSE on `/api/blueprint/stream` | Organisation-wide orientation, guided decision evidence, and technical drill-down; also used for full-bleed pitch and recording |
| Entities | `/?view=entities` | [`EntitiesPage.tsx`](../web/blueprint/src/pages/EntitiesPage.tsx) | 7 kind tiles (Person / Organisation / Asset / Money / Decision / Place / Period), kind-filtered entity table, recent-links pulse | `GET /api/entities/_stats` (5 s poll) | Day-to-day — entity inspector |
| Functions | `/?view=functions` | [`FunctionsPage.tsx`](../web/blueprint/src/pages/FunctionsPage.tsx) | 9-tile grid of function FMs; tile expands inline to show owned domains + persona-hierarchy tree | `GET /api/functions` (5 s poll) | Drill — per-function detail |
| Org-clone | `/?view=org-clone` | [`OrgClonePage.tsx`](../web/blueprint/src/pages/OrgClonePage.tsx) | Fan-out across entities, in-flight meta-workflows, ambient agents, function FMs, cadence schedule | 5 endpoints (entities/_stats, workflows, functions, functions/{n}/ambient, cadences); 8 s poll | Admin — single-page operator view |
| Workflow run (drill-in) | `/?view=run&run_id=<id>` | [`WorkflowRunPage.tsx`](../web/blueprint/src/pages/WorkflowRunPage.tsx) | Per-run reasoning, tool calls, state, HITL interrupts — domain-agnostic | `GET /api/workflows/{run_id}/agui` (AG-UI SSE) | Day-to-day — single-run inspector |

The Candidate Portal (`:5274`) holds its own UI and is out of scope
here. The Control Plane (`:5273`) is primarily an operator/admin UI, but
it now also hosts one dedicated visualisation surface — the actor-world
viewer at `/world`, inventoried in §1.1.

### 1.1 Control Plane world viewer (`/world`)

The observable actor world (ARCHITECTURE.md §15) ships a first-class
viewer in the Control Plane, not the blueprint microsite. The `/world`
route is **scenario-aware**: it renders this support view when
`ZAVA_WORLD=support` and the telco view (§1.2) when `ZAVA_WORLD=telco`,
switching on `state.scenario`. Support is unchanged by the telco work.

| Surface | URL | Component | What it shows | Data source | Role |
|---|---|---|---|---|---|
| World | `:5273/world` | [`World.tsx`](../web/client/routes/World.tsx) + [`useWorldSimulation`](../web/client/hooks/useWorldSimulation.ts) | Real ticket actors in Waiting / In service / Resolved / Abandoned lanes; Support + Reserve worker pools by ID; the Durable intervention causal strip; a recent-events journal | Polls `GET /api/world/state` (1 s) + `GET /api/world/events?after=` (300 ms) | Day-to-day — live actor-world operations view |

**Every visual is a real actor or a journal event — never decoration:**

- Each card is a real ticket ID and each chip a real worker ID from the
  `/api/world/state` snapshot; the lanes are the actors' actual
  `status`, worker groups their actual `team_id`.
- A card/chip replays a one-shot pulse only when a newer journal event
  references its actor id (the React key is `id:latest-seq`), so motion
  maps 1:1 to a genuine transition.
- Workers named by `worker.reallocated` events pulse green and appear in
  the Support group because their snapshot `team_id` changed to
  `TEAM-SUPPORT` — no worker moves without that event.
- The **Durable intervention** strip renders one causal chain straight
  from a single journal `trace_id`: `Pressure detected → Responder
  requested → Durable decided → Command accepted → WRK-… reallocated`.
  Each step carries the real event id; the reallocated IDs are the
  actual `worker.reallocated` actors.
- The only write control shipped is **Inject demand surge** (fixed
  multiplier 4 / duration 90 → `POST /api/world/inject/demand_surge`).
  No pause/step/restart, no aggregate KPI panel, no chart library.

Proven in a real browser against the unmocked stack by
[`tools/actor_world_viewer_proof.sh`](../tools/actor_world_viewer_proof.sh)
(see ARCHITECTURE.md §15.3).

### 1.2 Control Plane world viewer (telco)

When `ZAVA_WORLD=telco`, the same `/world` route renders
[`TelcoWorld.tsx`](../web/client/routes/TelcoWorld.tsx) instead — the
network-incident actor world (ARCHITECTURE.md §15.4). Same hook, same
polling, same "real actor or journal event, never decoration" rule.

| Surface | URL | Component | What it shows | Data source | Role |
|---|---|---|---|---|---|
| World (telco) | `/world` | [`TelcoWorld.tsx`](../web/client/routes/TelcoWorld.tsx) + [`useWorldSimulation`](../web/client/hooks/useWorldSimulation.ts) | Real cell-site cards laid out by region/status/utilisation; real active/degraded/rerouted/dropped session tokens; the incident site + its neighbours; the Durable causal intervention strip; a recent-events journal | Polls `GET /api/world/state` (1 s) + `GET /api/world/events?after=` (300 ms) | Live network-incident operations view |

**Every visual is a real actor or a journal event:**

- Each site card is a real `CellSite` ID; its status ring, utilisation
  bar and packet-loss come straight from the snapshot. The failed site
  is marked from the journal `site.failed` (persisted, so the incident
  highlight survives the fast auto-recovery) and its neighbours are
  highlighted from that site's `neighbor_ids`.
- Session tokens are real `NetworkSession` IDs bucketed by their actual
  `status` (active / degraded / rerouted / dropped). Token lists are
  DOM-capped but each lane header states the **true total**.
- The **Durable intervention** strip renders one causal chain from a
  single `network-anomaly` journal `trace_id`: `Anomaly detected →
  Responder requested → Durable decided → Command accepted → N sessions
  rerouted → Site recovered`, each step carrying the real event id.
- The only write control shipped is **Fail site**
  (`POST /api/world/inject/site_failure`, deterministic default site).
  No pause/step/restart, no map/chart library, no aggregate KPI panel.

Proven in a real browser against the unmocked stack by
[`tools/telco_world_e2e_proof.sh`](../tools/telco_world_e2e_proof.sh)
(see ARCHITECTURE.md §15.4).

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

## 8. AG-UI per-run drill-in

The workflow-run drill-in (`?view=run`) is the first surface that does
**not** consume `/api/blueprint/stream` directly. Instead it consumes
[`/api/workflows/{run_id}/agui`](../api/server/routes/workflow_agui.py),
which translates substrate `FleetEvent`s through
[`SubstrateToAGUI`](../api/server/services/substrate_to_agui.py) into
the [AG-UI protocol](https://docs.ag-ui.com) event vocabulary. The
benefit is that the same `RunPanel` renders every workflow type —
hiring, expense-claim, vendor-kyc, future domains — without a
per-domain frontend. To extend the drill-in (e.g. domain-specific
widgets), prefer AG-UI generative-UI events over bespoke React
components.

---

## 9. Cross-references

- **Add a new visualisation layer** → §"Visualisation Contributor Guide" appended below
- **The forward design** → [superpowers/specs/2026-05-09-org-building-design.md](superpowers/specs/2026-05-09-org-building-design.md)
- **Drive the visualisation from the simulator** → [superpowers/specs/2026-05-10-simulator-expansion-design.md](superpowers/specs/2026-05-10-simulator-expansion-design.md)
- **How the blueprint microsite ships to Azure** → [blueprint-microsite-contributor-guide.md](blueprint-microsite-contributor-guide.md)
- **Code-anchored architecture** → [ARCHITECTURE.md](ARCHITECTURE.md)


---

# Visualisation Contributor Guide

_(Merged from the former `visualisation-contributor-guide.md`. How to make a new event, function, entity kind, or cadence pip show up in the visualisation surfaces without a separate UI edit.)_

---

## The "one signal per visual property" rule

Before adding anything, the rule. Lifted from the Org Building spec
([§GUD-001](superpowers/specs/2026-05-09-org-building-design.md)):

| Visual property | Owns this signal | Never overload with |
|---|---|---|
| Colour | Entity kind / domain identity | Activity intensity, recency |
| Pulse rate | Activity intensity | Identity, kind |
| Glow intensity | Recency | Kind, identity |
| Beam thickness | Cardinality (e.g. how many cross-cutting entities) | Activity, recency |
| Cluster position | Identity (deterministic from `workflow_type`) | Anything else — **must stay deterministic across reloads** |

If your new layer wants to express two things at once, pick the
property that already encodes that meaning, or add a **separate**
visual primitive — never overload an existing one.

The default state should be subtle (gentle pulses, slow drifts).
Bright/sharp transitions are reserved for rare meaningful events
(`decision.recorded`, `ambient.decided`, `cadence.tick`,
`workflow.sub_spawned`). The eye should be drawn to the rare events,
not exhausted by constant motion.

---

## To make a new event surface

### 1. Emit the event

Use the standard FleetEvent path. The type is just a string (the
`FleetEventType` `Literal` in
[`api/shared/events.py`](../api/shared/events.py) is the catalogue,
but `FleetEvent.type` itself is `str` and accepts new values without
editing that file). Emit via `app_state.bus.publish(...)` or — if the
event is audit-eligible — via `app_state.audit.log("your.event.type",
{...})`. Audit-logged events are mirrored to the bus automatically.

For audit-eligible events, register a small allow-list of payload keys
in [`api/server/services/audit_logger.py`](../api/server/services/audit_logger.py)
so the ledger writes the right slim shape. Pattern: name the event
`<noun>.<verb>` (e.g. `entity.upserted`, `decision.recorded`,
`cadence.tick`). The audit ledger provides hash-chain + Ed25519
receipts for free.

### 2. Add it to the SSE allow-list

The blueprint stream filters events through
[`_OBSERVATORY_TYPES`](../api/server/routes/blueprint.py) before
forwarding to the front-end. **Add your new type to that set.** If
your event carries non-default fields, also extend `_normalise_event`
to surface them in the SSE payload (e.g. `persona`, `reason`,
`executor_type`, `stage`).

### 3. Render it on the front-end

In [`web/blueprint/src/lib/useObservatory.ts`](../web/blueprint/src/lib/useObservatory.ts),
extend the `switch (data.type)` block in the counter reducer if your
event needs to bump a counter. For visual reactions, add a handler in
the consumer ([`Constellation.tsx`](../web/blueprint/src/components/Constellation.tsx)
today; `OrgBuilding.tsx` once the Org Building lands) that subscribes
via the `onEvent` callback.

Pick the visual primitive per the table above. If you need a brand-new
primitive, document it in [visualisation.md §2](visualisation.md#2-the-visual-vocabulary)
in the same PR.

### 4. Verify locally

```bash
make up                                 # full stack
# In another terminal, tail the SSE feed:
curl -N http://localhost:3101/api/blueprint/stream
# Trigger your event (a workflow inject, simulator endpoint, etc.):
curl -X POST http://localhost:3101/api/simulator/<your-domain> \
     -H 'Content-Type: application/json' -d '{}'
# Confirm the event appears in the SSE tail with the expected shape.
# Then open http://localhost:5275/?view=constellation and watch.
```

Add a back-stop test: see
`tests/api/server/services/test_blueprint_stream_filter.py` (or
adjacent) for the existing pattern; assert your new type relays through.

---

## To add wording for a new agent or executor

The runtime emits technical labels like `executor.agent_kyc_diligence_checker`,
`gen_ai.generate_content`, or `validate_budget_schema`. **Every UI surface
that shows these names to a non-technical reader must go through the shared
humanizer** at [`web/shared/humanize.ts`](../web/shared/humanize.ts) — there is
**one source of truth**.

Current consumers:

- Cosmic-lens workflow drawer → [`humanizeTimeline.ts`](../web/blueprint/src/components/cosmicLens/HUD/humanizeTimeline.ts)
- Operator console fleet rail → [`FleetManagerRail.tsx`](../web/client/components/FleetManagerRail.tsx)

When you ship a new agent / deterministic executor / validator:

1. **Try the fallback first.** The humanizer maps trailing snake_case suffixes
   to verbs: `_drafter → Drafted X`, `_checker → Checked X`, `_lookup → Looked
   up X`, `_resolver → Resolved X`, etc. (full list in `SUFFIX_VERBS`). Add a
   new suffix-verb only if multiple future agents will share it.
2. **If the auto-phrase reads awkwardly**, add one line to `EXECUTOR_OVERRIDES`
   in [`web/shared/humanize.ts`](../web/shared/humanize.ts), keyed by the
   label without the `executor.` prefix:

   ```ts
   "agent_my_new_thing":  "Did the new thing",
   ```

3. **Test by eye** — open the blueprint drawer for a workflow that exercises
   your new step and confirm the row reads correctly to a non-technical
   person. The drawer is the canonical surface; if it looks right there it
   will look right everywhere.

**Do not**:

- inline a one-off label in a component file (it will drift from every other surface),
- hand-format snake_case in JSX (use `humanizeLabel(rawLabel)` from `@shared/humanize`),
- add an LLM call in the rendering path (humanizer must be deterministic and synchronous).

The same module also exports `prettyActor`, `formatOffset`, and `verdictVerb`
for personas, relative timing, and decision verbs — reuse them rather than
re-rolling your own.

### Other dictionaries in `web/shared/humanize.ts`

The humanizer is also the single source of truth for three other id-→-label
maps. Whenever you mint a new id in any of these categories, add it to the
matching map; do **not** hard-code the user-facing label in render code.

- **`PERSONA_LABELS`** — persona / role ids (`cpo`, `gc`, `fpa_analyst`, …)
  → job titles. Read via `prettyActor(roleId)`.
- **`WORKFLOW_TYPE_LABELS`** — workflow-type slugs (`vendor-kyc`,
  `hire-to-productive`, …) → display names. Read via
  `humanWorkflowType(workflowType)`.
- **`RELATIONSHIP_LABELS`** — Kuzu relationship names (`EMPLOYED_BY`,
  `OWNS`, …) → plain-English verbs. Read via `humanRelationship(rel)`.

Companion helpers exported from the same file (use these instead of
re-implementing them in components):

- `humanizeLabel(rawLabel)` — entry point for any executor / lifecycle /
  phase event type.
- `prettyActor(actor)` — persona / role id → job title (consults
  `PERSONA_LABELS` first, falls back to title-cased snake_case).
- `humanWorkflowType(workflowType)` — workflow-type slug → display name.
- `humanRelationship(rel)` — Kuzu relationship → plain-English verb.
- `kindToVerb(kind)` — entity-kind id → noun phrase
  (`Person → "Person record"`, `Money → "Amount"`).
- `pluralize(count, noun, pluralOverride?)` — count + noun pair with
  irregular plurals from `ENTITY_KIND_NOUNS`.
- `formatAge(seconds)` — duration in seconds → relative phrase.
- `formatRelative(targetMs, nowMs?)` — past timestamp → "5m ago".
- `formatOffset(sec)` — workflow-relative offset (used by the timeline).

**Convention.** A new persona role, workflow type, or relationship name is
added in exactly one place — the corresponding `*_LABELS` map above. Any
JSX that needs to render it goes through the matching helper. If you find
yourself writing `String(entity.persona_role)` or `relationshipName` in a
component, you are doing it wrong.

---

## To add a new function (so it gets a floor in the Org Building)

The 10-floor backbone in the forward Org Building design reads
straight from the `FUNCTIONS` registry.

1. **Add the entry** in [`api/shared/functions.py`](../api/shared/functions.py).
   Required fields: `name`, `display`, `operator_surface`,
   `owns_domains`, `ambient_agents`, `kpis`, `persona_hierarchy`,
   `kpi_schema_version`. The boot-time validators (`_wire_function_back_refs`
   and `_validate_persona_hierarchy`) will trip if you reference an
   unknown domain or persona — fix at the source rather than papering
   over.
2. **Floor ordering.** The Org Building spec
   ([TASK-010](superpowers/specs/2026-05-09-org-building-design.md))
   freezes top-down order as: `ceo` (penthouse) → `finance` →
   `revenue` → `hr` → `ops` → `legal` → `marketing` → `tech` →
   `data` → `customer-success` → lobby (entity graph). Add new
   functions in the appropriate functional grouping (money near top,
   support near bottom).
3. **Register persona SKILL.md.** Every role in `persona_hierarchy`
   must resolve to `api/server/personae/<role>/SKILL.md`. See
   [`docs/superpowers/skills/author-persona/SKILL.md`](superpowers/skills/author-persona/SKILL.md).
4. **KPIs.** List the metrics your FM owns. They surface on the
   facade ticker at zoom-3 (Org Building TASK-014) and on the
   clipboard wall at zoom-1 (TASK-037). Publish snapshots via
   `app_state.kpi_store.publish(...)`.

The visualisation will pick the new floor up automatically once the
Org Building component reads from the registry.

---

## To add a new entity kind (so it gets a vault icon)

1. **Declare the node table.** Add the kind to the Kuzu schema in
   [`api/server/services/entity_graph.py`](../api/server/services/entity_graph.py).
   Per the kuzu syntax conventions saved in repo memory, primary keys
   use the trailing `PRIMARY KEY (id)` form and reserved words like
   `starts` / `ends` must be backtick-quoted.
2. **Wire the projection.** Add a projection under
   [`api/server/services/entity_projections/`](../api/server/services/entity_projections/)
   that reads from the workflow payload and emits `entity.upserted`
   for the new kind.
3. **Add the kind to `EntitiesPage.tsx`** —
   [`web/blueprint/src/pages/EntitiesPage.tsx`](../web/blueprint/src/pages/EntitiesPage.tsx)
   carries a `KINDS` const used to render the tile row and the filter
   dropdown. Append in canonical order: Person, Organisation, Asset,
   Money, Decision, Place, Period, then your new kind. **Workflow is
   intentionally omitted** from this UI even though Kuzu has the table.
4. **Lobby ordering** for the Org Building. The 7-icon stack at the
   ground floor (Org Building TASK-013) inherits the same canonical
   order. Update both lists in the same commit.
5. **Colour.** Pick a tint from the palette in
   [visualisation.md §2](visualisation.md#2-the-visual-vocabulary) — do
   not introduce a new palette entry without updating that table.

---

## To add a new cadence (so it gets a pip on the cadence clock)

1. **Declare the cadence** wherever cadences are loaded
   ([`api/server/services/cadence_loader.py`](../api/server/services/cadence_loader.py)).
   Required: `name`, cron-like `schedule`, the `fires_ambient_agent` it
   triggers.
2. **Confirm `/api/cadences` returns it** (the route in
   [`api/server/routes/cadences.py`](../api/server/routes/cadences.py)
   is generic; new cadences flow through automatically).
3. **Pip placement.** The Org Building zoom-3 cadence clock (TASK-015)
   maps three canonical cadences to three pip-marks (morning-sweep /
   period-close / quarterly-okr). If your new cadence is one of those
   three, the pip is automatic. Otherwise add a new pip and document
   it in [visualisation.md §2](visualisation.md#2-the-visual-vocabulary).
4. **Test the firing path.** Cadences fire `cadence.tick` events. Once
   that type is in the SSE allow-list, the visualisation will react
   (clock pulse + ambient sensor flash). Until then, see
   "[To make a new event surface](#to-make-a-new-event-surface)".

---

## Local-dev recipes

```bash
# Boot the full stack
make up

# Tail the live SSE feed (the source the visualisation reads)
curl -N http://localhost:3101/api/blueprint/stream | head -50

# Inject one workflow per fleet domain (drives Constellation
# clusters + the editorial observatory)
for ep in fleet-vendor-kyc fleet-employee-onboarding fleet-treasury-fx \
          fleet-purchase-order creative-campaign fleet-ap-invoice \
          fleet-perf-review fleet-contract-renewal fleet-contract-review \
          fleet-privacy-dpia fleet-it-access-request; do
  curl -X POST http://localhost:3101/api/simulator/$ep \
       -H 'Content-Type: application/json' -d '{}' && sleep 2
done

# Start / stop the autonomous ramp loop
curl -X POST http://localhost:3101/api/simulator/constellation-start

# Open the visualisation surfaces
open 'http://localhost:5275/?view=constellation'
open 'http://localhost:5275/?view=entities'
open 'http://localhost:5275/?view=functions'
open 'http://localhost:5275/?view=org-clone'
```

If your new event does not appear in the SSE tail, check
`_OBSERVATORY_TYPES` in
[`api/server/routes/blueprint.py`](../api/server/routes/blueprint.py)
first — that filter is the most common reason a known-emitted event
does not reach the front-end.

---

## What you should not do

- **Do not introduce a third visualisation page that duplicates an
  existing surface's role.** The four `?view=` surfaces are the
  canonical set; the Org Building consolidates them. Add to the right
  one.
- **Do not hand-maintain a list of skills, MCP tools, or domains in a
  visualisation component.** All three are walked at runtime by
  [`api/server/services/blueprint_inventory.py`](../api/server/services/blueprint_inventory.py).
  Read from `/api/blueprint/composition` instead.
- **Do not bypass governance for visualisation reads.** Click-to-deep-link
  patterns (e.g. clicking a decision spark to open the entity card)
  must go through existing API surfaces (`GET /api/entities/{id}`,
  `GET /api/entities/{id}/linked`). Org Building SEC-001 / SEC-002
  formalise this; treat it as load-bearing.
- **Do not break the `?view=constellation` URL contract.** The Org
  Building replaces the page at the same URL; bookmarks must keep
  working. Same for `?view=entities`, `?view=functions`,
  `?view=org-clone`, `?view=run`.

---

## Cross-references

- **Visualisation reference (what's wired today)** → [visualisation.md](visualisation.md)
- **Forward design (where it's going)** → [superpowers/specs/2026-05-09-org-building-design.md](superpowers/specs/2026-05-09-org-building-design.md)
- **How to drive the visualisation from the simulator** → [superpowers/specs/2026-05-10-simulator-expansion-design.md](superpowers/specs/2026-05-10-simulator-expansion-design.md)
- **Microsite + Azure deploy** → [blueprint-microsite-contributor-guide.md](blueprint-microsite-contributor-guide.md)
