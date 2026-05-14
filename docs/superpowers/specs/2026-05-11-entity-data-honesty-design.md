# Spec — entity-data honesty

## Why

The cosmic-lens entity view shipped (2026-05-10) but the data behind it is
degraded in three specific, verifiable ways. The fixes are surgical and
bring the live demo into honest agreement with the substrate.

## Bug 1 — Projections read the wrong payload shape

Every domain spawner produces a payload of the form:

```json
{
  "<business_object_key>": { "...domain fields..." },
  "scenario": "...",
  "decisions": [ ... ]
}
```

Verified shapes (sampled live):

| workflow_type        | nested key       |
|----------------------|------------------|
| ap-invoice           | `invoice`        |
| vendor-kyc           | `vendor`         |
| contract-renewal     | `contract`       |
| contract-review      | `contract_review`|
| treasury-fx          | `treasury_op`    |
| it-access-request    | `request`        |
| perf-review          | `review`         |
| creative-campaign    | `brief`          |
| employee-onboarding  | `joiner`         |
| purchase-order       | `purchase_order` |
| privacy-dpia         | `dpia`           |
| travel-preapproval   | (TBD — sample)   |

Every projection in `api/server/services/entity_projections/*.py` reads via
`p.get("vendor_name")` etc. at the top level — i.e. one layer too high.
Result: `vendor_name` is None → falls back to `"unknown"` → every entity
collides on the fallback id (`ORG-vendor-unknown`, `MONEY-INV-...` with
amount=0, etc.). This is the single biggest reason the cross-domain leader
board is dominated by `ORG-vendor-unknown` (466 workflows).

**Fix:** in each projection, pull the nested business object first
(`obj = p.get("<key>") or {}`), then read scalar fields from `obj`. Keep
top-level `decisions` / `scenario` reads unchanged.

## Bug 2 — Entity events emit with `workflow_id: null`

`entity_reflector._on_event()` knows the originating `workflow_id` but
never threads it down to `EntityGraph.upsert()`, which reads it from
`entity.attrs.get("workflow_id")` for the FleetEvent payload. Projections
don't put it in `attrs` either, so every `entity.upserted` / `entity.read`
/ `entity.linked` event on the SSE bus has `workflow_id: null`.

The cosmic-lens rocket loop in entities mode requires a workflow_id to
locate which rocket should fly — so it skips every entity event and **no
rockets ever fly to entity cities**. Verified by sniffing
`/api/blueprint/stream`.

**Fix:** in `entity_reflector._dispatch_op` (and `read_back` paths that
emit `entity.read`), stamp the resolved `workflow_id` onto `op.attrs`
before calling `graph.upsert(op)`. Since `EntityWrite` is a frozen
dataclass, mutate `attrs` (a `dict`) in place — no rebuild needed.
For `entity.read` (which may be triggered by deterministic executors
without a workflow context), pass the workflow_id as a param to the
graph methods that emit reads, threading it from the reflector path
where known.

## Bug 3 — Decisions don't link to anything

Schema (`api/server/services/entity_graph.py:281`):

```sql
CREATE REL TABLE DECIDED_ON (FROM Decision TO Person)
```

Projections call:

```python
build_decision(..., decided_on=(money_id,))   # ap-invoice
build_decision(..., decided_on=(asset_id,))   # purchase-order
build_decision(..., decided_on=(org_id,))     # vendor-kyc
```

`record_decision` invokes `self.link(decision_id, "DECIDED_ON", did)`,
which `link()` silently no-ops because the kuzu rel table doesn't accept
that target type.

Empirical check: `/api/entities/<decision_id>/linked` returns `[]` for
every decision sampled. Decisions are floating, story-less nodes.

Kuzu 0.6.1 does **not** support multi-pair rel tables
(`FROM Decision TO Person, FROM Decision TO Money` parser-rejects).

**Fix:** create one rel table per target kind, named `DECIDED_<KIND>`:

| Rel name          | Target kind   |
|-------------------|---------------|
| `DECIDED_PERSON`  | Person        |
| `DECIDED_MONEY`   | Money         |
| `DECIDED_ASSET`   | Asset         |
| `DECIDED_ORG`     | Organisation  |
| `DECIDED_PERIOD`  | Period        |
| `DECIDED_PLACE`   | Place         |

Keep the old `DECIDED_ON` table on disk for backward compatibility (no
data migration; old graph already wiped). Update `record_decision` to
inspect each `decided_on` id, look up its kind from the graph, and write
to the right `DECIDED_<KIND>` rel. Update `_REL_TABLES` so
`rel_counts()` and `_canonical_edges()` see the new tables. Update
`/api/entities/<id>/linked` so it walks the new tables (it already
iterates `_REL_TABLES`, so adding the rows there is enough).

Frontend EntityView Decision narrative already reads the linked list and
groups by kind — so once the rels land, the panel populates with no UI
changes.

## What success looks like

- Open `?view=entities` → rockets fly from function planets to Person /
  Organisation / Money / Asset / Decision cities continuously.
- Click a recent ap-invoice Decision → drawer shows `DECIDED_MONEY`
  (the invoice) and `DECIDED_ASSET` (the PO), not "nothing touched".
- The cross-domain leaders panel shows real vendor names
  (`ORG-vendor-globex-industries`, etc.) instead of one mega-row of
  `ORG-vendor-unknown`.
- `MONEY-INV-*` entities have non-zero `amount` attribute matching the
  invoice payload.
- `entity.upserted` events on `/api/blueprint/stream` carry the
  spawning workflow_id.

## Out of scope

- Hiring projector (CON-001 — separate work).
- Backfilling rocket history from past sessions.
- New entity kinds beyond the 8 already in the schema.
- Editorial polish on the EntityView panels (kind-specific narrative
  already shipped).

## Risk + rollback

- Single-commit per task; all changes touch only the substrate / reflector
  / graph schema. Frontend untouched.
- The graph file is wiped at the start of this run, so no migration
  hazards. New schema is created fresh by the existing
  `_initialise_schema` path.
- Existing tests cover projections + reflector + graph; we re-run them.
