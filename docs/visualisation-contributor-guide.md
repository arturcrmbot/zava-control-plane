# Visualisation contributor guide

How to make a new event, function, entity kind, or cadence pip show up
in the visualisation surfaces without a separate UI edit. Companion to
[visualisation.md](visualisation.md), which is the canonical reference
for what's wired today.

This guide assumes you've read
[blueprint-microsite-contributor-guide.md](blueprint-microsite-contributor-guide.md)
for the underlying microsite contract (composition tree, recordings,
deploy). This file is specifically about the **live event /
visualisation surface**.

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
curl -N http://localhost:3001/api/blueprint/stream
# Trigger your event (a workflow inject, simulator endpoint, etc.):
curl -X POST http://localhost:3001/api/simulator/<your-domain> \
     -H 'Content-Type: application/json' -d '{}'
# Confirm the event appears in the SSE tail with the expected shape.
# Then open http://localhost:5175/?view=constellation and watch.
```

Add a back-stop test: see
`tests/api/server/services/test_blueprint_stream_filter.py` (or
adjacent) for the existing pattern; assert your new type relays through.

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
curl -N http://localhost:3001/api/blueprint/stream | head -50

# Inject one workflow per fleet domain (drives Constellation
# clusters + the editorial observatory)
for ep in fleet-vendor-kyc fleet-employee-onboarding fleet-treasury-fx \
          fleet-purchase-order creative-campaign fleet-ap-invoice \
          fleet-perf-review fleet-contract-renewal fleet-contract-review \
          fleet-privacy-dpia fleet-it-access-request; do
  curl -X POST http://localhost:3001/api/simulator/$ep \
       -H 'Content-Type: application/json' -d '{}' && sleep 2
done

# Start / stop the autonomous ramp loop
curl -X POST http://localhost:3001/api/simulator/constellation-start

# Open the visualisation surfaces
open 'http://localhost:5175/?view=constellation'
open 'http://localhost:5175/?view=entities'
open 'http://localhost:5175/?view=functions'
open 'http://localhost:5175/?view=org-clone'
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
  `?view=org-clone`.

---

## Cross-references

- **Visualisation reference (what's wired today)** → [visualisation.md](visualisation.md)
- **Forward design (where it's going)** → [superpowers/specs/2026-05-09-org-building-design.md](superpowers/specs/2026-05-09-org-building-design.md)
- **How to drive the visualisation from the simulator** → [superpowers/specs/2026-05-10-simulator-expansion-design.md](superpowers/specs/2026-05-10-simulator-expansion-design.md)
- **Microsite + Azure deploy** → [blueprint-microsite-contributor-guide.md](blueprint-microsite-contributor-guide.md)
