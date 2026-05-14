# Cosmic Lens — Entity View Design

**Date:** 2026-05-10
**Scope:** `web/blueprint/src/components/cosmicLens/` (cities, edges, drawer, rockets), `api/server/routes/cities.py` (real-kind reconciliation), `api/server/routes/entities.py` (a few response-shape additions), `api/server/services/entity_graph.py` (rolling-counter helper + first/last-seen).
**Goal:** Make the entities mode of the cosmic lens show the substrate's actual knowledge graph — what entities exist, how they're linked, how they're growing, which workflows touch them, and what decisions have been made about them — not 15 fictional canonical kinds with no inspector.

## What we actually have (audit summary)

The substrate already produces remarkable data; the lens isn't surfacing any of it.

- **8 real graph kinds** (`Person, Organisation, Asset, Money, Decision, Place, Period, Workflow`). Live counts at audit time: `Person 31, Organisation 13, Asset 354, Money 354, Decision 991, Period 109, Place 0, Workflow 0`. Two are populated zero today (Place is gated on optional payload fields; Workflow has no projector).
- **`source_workflows` is the killer cross-domain signal.** `ORG-vendor-unknown` appears in **100+ workflows spanning 5 workflow types** (vendor-kyc, ap-invoice, purchase-order, contract-renewal, contract-review). The same vendor crosses domains — that's exactly what "company knowledge growing" looks like.
- **Decisions are stored as their own entities** with full `verdict`, `reason`, `decided_at` (real timestamp), `persona_role`, `phase`. `Decision` count is **991** with rich free-text reasons like *"within treasurer delegation per TREASURY-FX-001: GBP 250000.0"* and *"missing policy_fit_check verdict"*. The substrate has 991 stored decisions begging to be read.
- **Story-bearing attrs already populated:** `Person.attributes.breach_history` (tiered policy breaches per employee), `Organisation.attributes.creditRating + sanctioned`, `Organisation.risk_band` (KYC), `Money.attributes.{vendor_id, po_id, invoice_id, currency_pair, op_kind}`. All sitting in `EntityWrite.attrs` ready to display.
- **Rels are sparser than the schema suggests.** Schema declares 10 rels (`EMPLOYED_BY, MANAGES, OWNS, TRANSACTS, BELONGS_TO, LOCATED_IN, DECIDED_ON, PRECEDENT_OF, TOUCHED, SUB_WORKFLOW_OF`) but in live data only `MANAGES` (employee_onboarding), `OWNS` (employee_onboarding + it_access_request), `BELONGS_TO` (purchase_order + contract_renewal), `LOCATED_IN` (travel_preapproval) actually fire. Many projections passed `decided_on=(money_id,)` but the schema types `DECIDED_ON: Decision→Person`, so those `link()` calls quietly no-op — `/api/entities/{id}/linked` returns empty for most ids today. The lens needs to show what's actually linked, not promise rels that don't exist.
- **No `created_at`/`updated_at` on entity rows.** The audit ledger (hash-chained, with `timestamp`) is the canonical "first/last seen" source. We need a server-side helper that derives `first_seen_at` / `last_seen_at` from the audit chain (or, simpler, mirrors them as columns on upsert).
- **KPIs are stored historically** (sqlite, append-only `kpi_snapshot(function, metric, period, value, schema_version, captured_at)`) so we can render real sparklines over time. Currently only seeded via `/api/simulator/seed-kpis` — but the data path is real.
- **The audit ledger is the substrate's "knowledge growth" signal.** Every `entity.upserted` / `entity.linked` / `decision.recorded` event lands as a hash-chained ledger entry. Counting entries over time → entities/min, decisions/min, links/min.

## Problem

Three layered defects make the entities mode dead:

1. **Schema fiction.** `cities.py:_gather_entity_types()` returns 15 hardcoded canonical labels (`Vendor`, `Invoice`, `Candidate`, …) that don't exist in the graph. Vendors live as `Organisation`, invoices as `Money`. Cities are pretty pictures wired to nothing.
2. **No live signal on the cities.** Even where a city's kind would match (`Person`, `Money`, `Decision`, `Period`), it shows as a static dot. No count, no recent-activity badge, no proof anything is happening.
3. **No inspector. None.** `WorkflowDrawer.tsx#CityView` is a 14-line placeholder. Click any city, see "City queue inspector. Phase E: live list of currently-parked rockets." and the city id echoed back. Individual entities can't be drilled into at all.

## Approach

Fix the schema fiction first, then add live signals layer by layer. The plan splits into five tasks (detailed in §Architecture):

- **Task 1.** Switch cities roster from 15 fictional kinds to the **8 real graph kinds**, with **live per-kind counts and activity rates** on each city. This is the foundation; everything else relies on it.
- **Task 2.** Add **first_seen_at / last_seen_at** columns to entities (mirrored on upsert) so we can sort "recent" and render age. Cheap addition; backfilled by a one-time migration over the audit ledger or just left to populate forward.
- **Task 3.** Replace `CityView` placeholder with a **per-kind inspector**: live count + activity rate + recent entities of this kind + top relationships incident to this kind + recent activity ticker.
- **Task 4.** New **`EntityView` drawer mode** (extends the `DrawerView` union with `"entity"`). Per-kind-specialised panels — Organisations show vendor-cross-domain narrative; Persons show breach history + management chain; Money shows transactional context; Decision shows verdict + reason + DECIDED_ON targets + precedents; Period shows what belongs to it.
- **Task 5.** **Knowledge Pulse** persistent strip + entity-mode rocket affordances. The Pulse is a small always-visible HUD overlay (entities mode only) showing total entity count + 60s growth + decisions/min + top cross-domain entity. Entity-mode rockets are clickable → open the `EntityView` for the entity that triggered the rocket; on completion the destination city briefly glows in the entity's color.

The work is purely additive on the backend (response-shape extensions on existing endpoints, one helper on `EntityGraph`, no schema migration). Frontend changes are isolated to `cosmicLens/` and don't affect capabilities mode.

## Architecture

### Task 1 — Real graph kinds + live counts

**`api/server/routes/cities.py:_gather_entity_types()`** returns the 8 real graph kinds with live data:

```python
[
  {"id": "Organisation", "kind": "entity_type", "label": "Organisation",
   "count": 13, "recent_activity_per_min": 4.2, "active": True},
  {"id": "Person", ..., "count": 31, ..., "active": True},
  ...
  {"id": "Place", "count": 0, "recent_activity_per_min": 0.0, "active": False},
  {"id": "Workflow", "count": 0, ..., "active": False},
]
```

`active: false` cities (count == 0 AND no recent activity) render at half opacity in the lens — visible as scaffolding but clearly dormant. The cosmic lens reads `city.count` and renders the city label as `${label} · ${count}`.

`_canonical_edges()` returns one edge per `(src_kind, rel, dst_kind)` triple from `entity_graph._REL_TABLES`, each carrying live `count` (computed from a Cypher `MATCH (a)-[r]-(b) RETURN type(r), count(*)` projected by source/target kind). Edge thickness in `EntityEdges.tsx` becomes `0.5 + 0.5 * log10(1 + count)`.

**`web/blueprint/src/components/cosmicLens/lib/colors.ts`** — `ENTITY_TYPE_COLORS` reduced to the 8 kinds with palette-consistent hex values:

```ts
const ENTITY_TYPE_COLORS = {
  Person:       "#fb923c",  // coral (warm — humans)
  Organisation: "#3b82f6",  // blue (cool — institutions)
  Asset:        "#a78bfa",  // violet
  Money:        "#22c55e",  // emerald (existing)
  Decision:     "#fbbf24",  // amber
  Place:        "#94a3b8",  // slate (often dormant)
  Period:       "#64748b",  // slate-dark (often dormant)
  Workflow:     "#22d3ee",  // cyan (structural)
};
```

**Polling cadence:** `useLiveCosmic.ts` already polls `/api/cities` every 30s. Tighten to 10s when `mode === "entities"` so live counts feel fresh.

### Task 2 — `first_seen_at` / `last_seen_at` on entities

Add two columns (`TIMESTAMP`) to all 8 node tables in `entity_graph.py:_NODE_TABLES`. `EntityGraph.upsert` writes `last_seen_at = now()` on every call and `first_seen_at = now()` only when the row is new (post-MERGE check). Existing rows backfill `first_seen_at = last_seen_at` lazily (no migration script — first upsert after deploy populates both). Existing tests stay green because they don't assert on these columns.

`/api/entities` list endpoint gains `?order=recent` (sort by `last_seen_at DESC`). `/api/entities/{id}` response includes the two new fields.

### Task 3 — `CityView` per-kind inspector

Replace `CityView` body in `WorkflowDrawer.tsx`. Layout (top to bottom):

- **Header:** kind name + count + "N/min" recent-activity rate. Color matches the kind's palette entry.
- **"Most recently touched"** panel (top): top 10 entities of this kind sorted by `last_seen_at DESC`. Fetched via `GET /api/entities?kind={kind}&limit=10&order=recent`. Each row shows:
  - `id` (e.g. `MONEY-INV-API-0017`)
  - One key attr (kind-specific — see table below)
  - `last_seen_at` rendered as relative ("12s ago", "4m ago")
  - `source_workflows` count (e.g. "5 wfs") with a tiny multi-domain badge if the workflow types span ≥ 2 domains
  - Click anywhere on the row → opens `EntityView` for that id.

  Per-kind key-attr column:

  | kind | shown attr |
  |---|---|
  | Person | `name` (`role` if name missing) |
  | Organisation | `name` + `risk_band` if set |
  | Asset | `kind` (laptop / po / contract / processing-activity) + `identifier` |
  | Money | `amount` + `currency` + nested `kind` |
  | Decision | `verdict` (color-coded) + first 60 chars of `reason` |
  | Period | `label` + `kind` |
  | Place | `name` + `kind` |
  | Workflow | `workflow_type` + `status` |

- **"Top relationships"** panel (middle): the most common rel types incident to this kind, from `GET /api/cities/affinity?kind={kind}` extended to return `[{rel, partner_kind, count, sample_partner_id}]` sorted by `count DESC`, top 5. Click a row → opens `EntityView` for the sample_partner_id.

- **"Live activity" panel** (bottom): last 5 `entity.read` / `entity.upserted` / `entity.linked` events for this kind, pulled from the lens's `flashesRef` ring buffer client-side (no server fetch). Each row: timestamp · workflow_id · "read"/"upserted"/"linked". Updates in real time as events arrive.

### Task 4 — `EntityView` drawer mode

Extend `DrawerView.type` union with `"entity"` (carries `id: string`). Add `EntityView` component. Behaviour adapts to the kind:

- **Header (always):** id + kind chip (colored) + age (`2h ago`, from `first_seen_at`) + last-seen (`12s ago`, from `last_seen_at`).

- **"Attributes" panel (always):** every key/value in `attrs` from `GET /api/entities/{id}`, plus the row-level columns (`name`, `email`, `risk_band`, `currency`, etc.). Long string values truncate at 80 chars with hover-reveal.

- **"Touched by" panel (always):** the entity's `source_workflows` array, grouped by workflow_type, rendered as a small bar chart per type (e.g. `vendor-kyc · 12 ▆▆▆▆▆▆▆▆▆▆▆▆`, `ap-invoice · 8 ▆▆▆▆▆▆▆▆`, …). The "this entity crosses N domains" headline (e.g. "Cross-domain across 5 workflow types") sits at the top — the cross-domain signal is the substrate's "company knowledge" story made visible. Each workflow id is clickable → opens `WorkflowView`.

- **"Linked entities" panel (always):** results of `GET /api/entities/{id}/linked` grouped by `rel`. Each row shows `rel name`, partner `id` + `kind`. Each partner is clickable → opens `EntityView` for that id (recursive). Empty rels are not shown (so the panel isn't full of "no MANAGES, no OWNS" noise).

- **Per-kind "narrative" panel (kind-specific):**

  - **Person:** "Policy breaches" panel listing `attrs.breach_history` items (each with `category`, `date`, `tier`); a colored severity dot per tier. "Reports to" / "Manages" rendered if MANAGES rel is populated. "Located in" panel showing LOCATED_IN places.

  - **Organisation:** "Risk profile" — `risk_band`, `country`, `jurisdiction`, plus `attrs.creditRating` and `attrs.sanctioned` (boolean badge). "Cross-domain footprint" — bar chart of how many workflows of each type touched this org. "Hot vendor" badge if the org appears in ≥ 3 workflow types AND ≥ 10 workflows total — visible cue that this is a real company-relationship-graph hub.

  - **Money:** "Transactional context" — `amount` + `currency` headline. The attrs table (already shown above) carries `vendor_id`, `po_id`, `invoice_id` etc. — each is auto-detected as an entity-id reference and rendered as a clickable link → `EntityView` for that referenced entity. "Decided by" — Cypher query `MATCH (d:Decision)-[]-(this) WHERE this.id = $id RETURN d` returns gates that signed off on the money record (when DECIDED_ON edges actually land per Task 4 hardening below).

  - **Decision:** "Verdict + reason" prominent card (verdict colour from a small mapping: `approve`→green, `reject`→red, `escalate`→amber). Below: `phase`, `persona_role`, `decided_at` absolute time. "Decided on" — DECIDED_ON edges. "Cited precedents" — PRECEDENT_OF edges. "Source event" — the bus event type that triggered the gate.

  - **Period:** "Belongs to me" — Cypher `MATCH (m:Money)-[r:BELONGS_TO]->(this) WHERE this.id = $id RETURN m` rendered as a list. "Period span" — `starts` / `ends` if populated.

  - **Asset, Place, Workflow:** generic Attributes + Touched-by + Linked panels suffice; no kind-specialised panel for v1.

### Task 5 — Knowledge Pulse + entity-mode rockets

**Knowledge Pulse strip** (entities mode only): a small always-visible HUD overlay across the top of the canvas, ~80px tall, showing four counters with sparklines:

- **Total entities:** big number (sum across kinds) + "+N in last 60s" delta.
- **Decisions/min:** count of `decision.recorded` flashes in the last 60s, sparkline.
- **Links/min:** count of `entity.linked` flashes, sparkline.
- **Cross-domain leaders:** top 3 entity ids appearing in the most workflow types in the last 5 minutes (from `source_workflows` length × distinct types — a small server query). Each is clickable → opens `EntityView`.

The pulse strip toggles on `mode === "entities"` and hides in capabilities mode. Sparklines are pure SVG, 60-sample buffer, refreshed each second from the `flashesRef` ring buffer (no extra REST calls for the sparklines themselves).

**Entity-mode rocket affordances:**

- Rockets in entities mode already dispatch on `entity.read`/`entity.upserted`/`entity.linked` per the Phase 2 stabilisation. **Nothing structural changes** — the per-workflow rocket model still applies. What's new:
  - On the rocket's destination arrival, the city briefly **pulses in the entity's kind colour** (e.g. arriving at `Money` city pulses emerald). 600ms decay. Lets the operator see "the substrate just touched a Money record" as a recurring beat.
  - Hovering a rocket in entities mode shows its `entity_id` in the existing hover label (currently shows the workflow_id only). Pulled from `flash.entity_id` already on the FleetEvent.
  - Clicking a rocket in entities mode opens the `EntityView` for that entity_id (fallback to workflow drawer if entity_id is missing).

## Files touched

| File | Change |
|---|---|
| `api/server/routes/cities.py` | `_gather_entity_types()` returns 8 real graph kinds with `count` + `recent_activity_per_min` + `active`. `_canonical_edges()` derived from `entity_graph._REL_TABLES`, each edge with live `count`. `/api/cities/affinity` extended with `?kind=` filter and `partner_kind`/`sample_partner_id` in the response. |
| `api/server/routes/entities.py` | `?order=recent` on the list endpoint (sort by `last_seen_at DESC`). Response of `/api/entities/{id}` includes `first_seen_at` + `last_seen_at`. New `GET /api/entities/_pulse` endpoint returning {total, growth_60s, decisions_per_min, links_per_min, cross_domain_top: [{id, kind, workflow_types_count, workflow_count}]}. |
| `api/server/services/entity_graph.py` | Add `first_seen_at` + `last_seen_at` columns to all 8 node tables. `upsert()` writes `last_seen_at = now()`; sets `first_seen_at = now()` only when the row is new. `_recent_activity_per_min(kind)` rolling-counter helper (5-minute window, in-memory). `cross_domain_top(limit, window_seconds)` Cypher query for the pulse endpoint. Backfill on first upsert (no migration script needed). |
| `web/blueprint/src/components/cosmicLens/lib/colors.ts` | `ENTITY_TYPE_COLORS` reduced to the 8 real kinds with palette-consistent hex values; per-verdict colour map (`approve`/`reject`/`escalate`). |
| `web/blueprint/src/components/cosmicLens/lib/types.ts` | `CityMeta` gains `count?`, `recent_activity_per_min?`, `active?`. New `EntityRow`, `EntityLink`, `PulseSnapshot` types. |
| `web/blueprint/src/components/cosmicLens/lib/useLiveCosmic.ts` | Tighten cities-polling cadence to 10s when `mode === "entities"`. Subscribe `/api/entities/_pulse` polled every 5s in entities mode; expose as `live.pulse`. |
| `web/blueprint/src/components/cosmicLens/Cities.tsx` | Render `${label} · ${count}` when count !== undefined; reduced opacity when `active === false`; small pulse dot adjacent to label when `recent_activity_per_min > 0`. On rocket arrival in entities mode, pulse the city in the entity's kind colour (600ms decay) — wire via existing rocket-arrival callback. |
| `web/blueprint/src/components/cosmicLens/EntityEdges.tsx` | Read per-edge `count`; map to line width via log scale; reduced opacity for `count === 0`; hover tooltip via `<Html>` showing `${rel}: ${count}`. |
| `web/blueprint/src/components/cosmicLens/Rockets.tsx` | In entities mode, hover label includes `entity_id`. Click handler opens `EntityView` for `flash.entity_id` (fallback to `WorkflowView` for `workflow_id`). |
| `web/blueprint/src/components/cosmicLens/HUD/WorkflowDrawer.tsx` | Replace `CityView` body with the per-kind inspector (header + 3 panels). Add `EntityView` component (header + Attributes + Touched-by + Linked + per-kind narrative panel). Extend `DrawerView` union with `"entity"`. Verdict colour map. Per-kind narrative renderers. |
| `web/blueprint/src/components/cosmicLens/HUD/KnowledgePulse.tsx` | New file. The four-counter overlay strip + sparklines + cross-domain-top click-through. |
| `web/blueprint/src/components/cosmicLens/CosmicLens.tsx` | Mount `<KnowledgePulse>` when `mode === "entities"`. Wire entity-mesh / rocket clicks → `setView({type:"entity", id})`. |
| `web/blueprint/src/components/cosmicLens/lib/__tests__/entityViewMappers.test.ts` | New tests for kind→key-attr selection, verdict→colour, entity-id detection in arbitrary attr values, sparkline buffer eviction. |

## Out of scope

- Changing the Kuzu graph schema or introducing entity subtypes. Vendors stay as `Organisation`, invoices as `Money` — the lens shows the truth.
- Fixing the projection bugs (CON-001 hiring has no projector; AP-invoice projection reads `payload.invoice_id` at top level instead of nested). These are pre-existing data-quality issues separate from the lens display.
- Per-entity SSE streams. Polling REST is fine — already low rate; the drawer is open one entity at a time.
- New entity-creation flows from the UI.
- Re-laying-out the city positions on the disc. Existing `cityPosition()` deterministic placement keeps stability. With only 8 cities (down from 15), positions naturally re-distribute via the existing layout — accepted as a one-time visual change.
- Capabilities mode — completely untouched. All changes gate on `mode === "entities"` or on the new `entity` drawer view.
- Decision-graph backfill (writing the `DECIDED_ON` rels that currently no-op because projections pass non-Person ids). Fixing those is a substrate change separate from the lens.
- Authorisation / row-level security on entity endpoints. Single-tenant on a laptop.
- KPI sparklines per function family inside the lens. Already-stored data; could be added in a future pass.

## Verification

After implementation, in the live observatory at `http://localhost:5275/?view=constellation` after toggling to entities mode:

1. Cities show **8 entity-type labels** (`Organisation`, `Money`, `Person`, `Asset`, `Decision`, `Place`, `Period`, `Workflow`). `Place` and `Workflow` render at half opacity (active=false).
2. Cities with non-zero counts render `${label} · ${count}` (e.g. `Decision · 991`, `Money · 354`).
3. **Knowledge Pulse strip** is visible at top. Total entity count matches `/api/entities/_stats` sum. Decisions/min and links/min sparklines update each second.
4. Click a city → drawer opens with header + Most Recently Touched + Top Relationships + Live Activity panels. All three populate (with non-empty live data on a running stack; the audit shows 991 decisions and 354 invoices, so e.g. `Decision` city's drawer should show 10 recent decisions with verdict colour-coding and reason previews).
5. Click a recent entity row → drawer switches to `EntityView` showing Attributes + Touched-by + Linked + the kind-specific narrative panel.
6. **Click `ORG-vendor-unknown`** in the Organisation city's drawer → `EntityView` shows the cross-domain bar chart (`vendor-kyc · 24`, `ap-invoice · 35`, `purchase-order · 18`, `contract-renewal · 12`, `contract-review · 11`) and a "Hot vendor" badge.
7. **Click a Person `PERSON-EMP-0001`** → `EntityView` shows the breach_history list with severity dots; MANAGES / OWNS panels populated for employees who have those.
8. **Click a Decision row** → `EntityView` shows the full reason ("within treasurer delegation per TREASURY-FX-001: GBP 250000.0") with verdict colour.
9. **Switch to entities mode while workflows are running** — rockets dispatch on entity events, hover shows `entity_id`, clicking a rocket opens its entity's drawer.
10. **Cities pulse in their kind colour** when a rocket arrives — `Money` pulses emerald, `Organisation` pulses blue.
11. `npm run test -- web/blueprint` green; `npm run build:blueprint` green; `python -m pytest tests/api/server/test_entities.py tests/api/server/test_cities.py -x -q` green.
12. `curl /api/entities/_pulse | jq '.cross_domain_top[0].id'` returns a real entity id (likely `ORG-vendor-unknown` given the 100+ source_workflows on it).

## Risks

- **`recent_activity_per_min` rolling counter is in-process state.** Restarting the FastAPI process zeros all counters until 5 minutes of activity accumulate. Acceptable for a single-laptop demo; documented in the helper's docstring.
- **`first_seen_at` / `last_seen_at` columns require a Kuzu schema migration.** Kuzu 0.6.1 supports `ALTER TABLE` ADD column; the bootstrap path detects column presence and adds the new columns idempotently if missing (existing pattern in `_bootstrap_schema`). No downtime; old rows backfill to NULL until first re-upsert. The audit ledger remains the source of truth for "true historical first-seen" — the column is a fast-path cache.
- **`_pulse` endpoint runs three Cypher queries on each call (5s polling).** With current data sizes (< 2000 entities, < 1000 decisions) this is sub-millisecond. If counts grow >100k, the cross-domain query needs an index — out of scope today; documented threshold in the docstring.
- **Drawer state machine grows: function | workflow | city | entity, with entity → entity recursion.** Existing `setView` chain handles it; no nav stack. `Escape` closes; clicking another scene element replaces the view. Browser-back not supported (drawer was never history-integrated).
- **Switching cities from 15 fictional kinds to 8 real kinds is a visible change.** Any documentation screenshot showing "Vendor" / "Invoice" as cities becomes stale. `git grep -i "Vendor\|Invoice" docs/blueprint*.md docs/visualisation.md` to flag references; update them as part of this work.
- **The verdict colour map and per-kind key-attr selectors are kind-specific code.** They live in pure mapper functions in `lib/entityRender.ts` so they're testable in isolation and easy to extend when new kinds or new attrs land.
