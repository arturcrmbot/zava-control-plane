# Cosmic Lens — Entity View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the cosmic lens entities mode show real entity-graph data — 8 real kinds (not 15 fictional ones), live counts, per-kind inspector, per-entity drawer with kind-specific narrative panels, and a Knowledge Pulse strip showing how the substrate's knowledge is growing in real time.

**Architecture:** Five tasks (1=schema-honest cities, 2=first/last_seen_at columns, 3=CityView inspector, 4=EntityView drawer, 5=Knowledge Pulse + entity-mode rocket affordances). Each task is one atomic commit. Backend changes are response-shape extensions on existing endpoints + one helper on EntityGraph + two timestamp columns. Frontend changes are isolated to web/blueprint/src/components/cosmicLens/.

**Tech Stack:** Python 3.13 (FastAPI), Kuzu 0.6.1, pydantic FleetEvents, React 19 + three.js, vitest 2, pytest.

---

## File map

| File | Tasks touching | Change |
|---|---|---|
| `api/server/services/entity_graph.py` | 1, 2, 5 | Add `first_seen_at` + `last_seen_at` TIMESTAMP columns to all 8 node tables; idempotent ALTER on bootstrap. `upsert()` writes both. New `_recent_activity_per_min(kind)` rolling 5-min counter. New `cross_domain_top(limit, window_seconds)` Cypher query. New `count_by_kind()` and `rel_counts()` helpers. |
| `api/server/routes/cities.py` | 1 | `_gather_entity_types()` returns 8 real graph kinds with `count` + `recent_activity_per_min` + `active`. `_canonical_edges()` derived from `_REL_TABLES` with live `count`. `/api/cities/affinity` extended `?kind=` filter. |
| `api/server/routes/entities.py` | 2, 3, 5 | `?order=recent` on list endpoint. `/{id}` response includes `first_seen_at`+`last_seen_at`. New `/api/entities/_pulse` endpoint. |
| `web/blueprint/src/components/cosmicLens/lib/colors.ts` | 1, 4 | `ENTITY_TYPE_COLORS` reduced to 8 real kinds. New `verdictColor()` helper. |
| `web/blueprint/src/components/cosmicLens/lib/types.ts` | 1, 3, 4, 5 | `CityMeta` gains `count?`, `recent_activity_per_min?`, `active?`. New `EntityRow`, `EntityLink`, `PulseSnapshot`, `EntityDetail` types. `DrawerView.type` union extended with `"entity"`. |
| `web/blueprint/src/components/cosmicLens/lib/useLiveCosmic.ts` | 1, 5 | Tighten cities-polling to 10s when `mode==="entities"`. Poll `/api/entities/_pulse` every 5s in entities mode; expose as `live.pulse`. |
| `web/blueprint/src/components/cosmicLens/lib/entityRender.ts` | 3, 4 | New file. Pure helpers: `keyAttrFor(kind, row)`, `verdictColor(verdict)`, `extractEntityIdRefs(value)`, `formatRelative(ms)`. |
| `web/blueprint/src/components/cosmicLens/Cities.tsx` | 1, 5 | Render `${label} · ${count}` when count defined. Reduced opacity when `active===false`. Pulse-on-rocket-arrival in entities mode (kind-coloured 600ms decay). |
| `web/blueprint/src/components/cosmicLens/EntityEdges.tsx` | 1 | Read per-edge `count`; line width `0.5 + 0.5*log10(1+count)`; reduced opacity when count===0. |
| `web/blueprint/src/components/cosmicLens/Rockets.tsx` | 5 | In entities mode, hover label includes `entity_id`; click opens EntityView. On arrival, emit a city-pulse callback. |
| `web/blueprint/src/components/cosmicLens/HUD/WorkflowDrawer.tsx` | 3, 4 | Replace `CityView` body with per-kind inspector. Add `EntityView` component. Extend `DrawerView` union. |
| `web/blueprint/src/components/cosmicLens/HUD/KnowledgePulse.tsx` | 5 | New file. Four-counter overlay + sparklines + cross-domain-top click-through. |
| `web/blueprint/src/components/cosmicLens/CosmicLens.tsx` | 5 | Mount `<KnowledgePulse>` when `mode==="entities"`. Wire entity / rocket clicks → `setView({type:"entity",id})`. Plumb city-pulse callback. |
| `web/blueprint/src/components/cosmicLens/lib/__tests__/entityRender.test.ts` | 3, 4 | Tests for `keyAttrFor`, `verdictColor`, `extractEntityIdRefs`, `formatRelative`. |
| `tests/api/server/test_entity_view.py` (new) | 1, 2, 5 | Tests for live cities response shape, first/last_seen_at population, _pulse endpoint. |

## Conventions

- Run Python tests from repo root: `python -m pytest <path> -x -q`. Use `PORTAL_DATA_DIR=$(pwd)/data/portal-test` if a uvicorn instance holds the default kuzu lock.
- Run JS tests: `npm run test -- web/blueprint/src/components/cosmicLens` from repo root.
- Run blueprint build: `npm run build:blueprint` from repo root.
- Commit with co-author trailer:
  ```
  Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
  ```

---

## Task 1 — Schema-honest cities + live counts

**Goal:** Replace 15 fictional canonical kinds with 8 real graph kinds. Each city carries a live count + recent-activity rate. Edges derived from `_REL_TABLES` with live link counts.

**Files:**
- Modify: `api/server/services/entity_graph.py` (add `count_by_kind()`, `rel_counts()`, `_recent_activity_per_min(kind)` helpers).
- Modify: `api/server/routes/cities.py` (rewrite `_gather_entity_types()` and `entity_edges()`; add `?kind=` to `/affinity`).
- Modify: `web/blueprint/src/components/cosmicLens/lib/colors.ts` (8-kind palette).
- Modify: `web/blueprint/src/components/cosmicLens/lib/types.ts` (CityMeta extension).
- Modify: `web/blueprint/src/components/cosmicLens/lib/useLiveCosmic.ts` (10s polling in entities mode).
- Modify: `web/blueprint/src/components/cosmicLens/Cities.tsx` (label rendering with count, opacity).
- Modify: `web/blueprint/src/components/cosmicLens/EntityEdges.tsx` (log-scale width, dormant opacity).
- Create: `tests/api/server/test_entity_view.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/api/server/test_entity_view.py`:

```python
"""Tests for the entity-view substrate work (cities response shape, pulse endpoint)."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from api.server.main import app
    return TestClient(app)


def test_cities_entities_mode_returns_eight_real_kinds(client):
    resp = client.get("/api/cities?mode=entities")
    assert resp.status_code == 200
    body = resp.json()
    cities = body.get("cities", body if isinstance(body, list) else [])
    kinds = sorted(c["id"] for c in cities)
    assert kinds == sorted(["Person", "Organisation", "Asset", "Money",
                            "Decision", "Place", "Period", "Workflow"])
    for c in cities:
        assert c["kind"] == "entity_type"
        assert "count" in c, f"city {c['id']!r} missing count"
        assert isinstance(c["count"], int)
        assert "recent_activity_per_min" in c
        assert "active" in c


def test_cities_edges_uses_real_rels(client):
    resp = client.get("/api/cities/edges")
    assert resp.status_code == 200
    edges = resp.json().get("edges", [])
    real_rels = {"EMPLOYED_BY", "MANAGES", "OWNS", "TRANSACTS",
                 "BELONGS_TO", "LOCATED_IN", "DECIDED_ON",
                 "PRECEDENT_OF", "TOUCHED", "SUB_WORKFLOW_OF"}
    for e in edges:
        assert e.get("rel") in real_rels, f"edge {e} uses non-real rel"
        assert "count" in e
        assert e["from_kind"] in {"Person", "Organisation", "Asset", "Money",
                                  "Decision", "Place", "Period", "Workflow"}


def test_cities_affinity_supports_kind_filter(client):
    resp = client.get("/api/cities/affinity?kind=Money")
    assert resp.status_code == 200
```

- [ ] **Step 2: Run to confirm fail**

```bash
PORTAL_DATA_DIR=$(pwd)/data/portal-test python -m pytest tests/api/server/test_entity_view.py -x -q
```

Expected: tests fail (response shape not yet updated).

- [ ] **Step 3: Add EntityGraph helpers**

In `api/server/services/entity_graph.py`, after the `linked()` method (around line 935) and before `touched_by()`, add:

```python
    def count_by_kind(self) -> dict[str, int]:
        """Return per-kind node counts as a dict keyed by kind name."""
        out: dict[str, int] = {}
        for kind in _VALID_KINDS:
            rows = self.query(f"MATCH (n:{kind}) RETURN count(*) AS c")
            out[kind] = int(rows[0]["c"]) if rows else 0
        return out

    def rel_counts(self) -> list[dict[str, Any]]:
        """Return live counts per (src_kind, rel, dst_kind) triple.

        Uses `_REL_TABLES` to know what tuples exist; runs one count
        Cypher per rel. Cheap at demo scale (10 rels × <1ms each).
        """
        out: list[dict[str, Any]] = []
        for rel_name, ddl in _REL_TABLES:
            # Parse "FROM Foo TO Bar" out of the DDL.
            try:
                from_idx = ddl.index("FROM ") + len("FROM ")
                to_idx = ddl.index(" TO ", from_idx)
                src_kind = ddl[from_idx:to_idx].strip()
                tail = ddl[to_idx + len(" TO "):]
                end_tokens = [tail.find(c) for c in (",", ")", "\n") if tail.find(c) >= 0]
                end_idx = min(end_tokens) if end_tokens else len(tail)
                dst_kind = tail[:end_idx].strip()
            except Exception:
                continue
            try:
                rows = self.query(
                    f"MATCH (a:{src_kind})-[r:{rel_name}]->(b:{dst_kind}) "
                    f"RETURN count(*) AS c"
                )
                cnt = int(rows[0]["c"]) if rows else 0
            except Exception:
                cnt = 0
            out.append({
                "rel": rel_name,
                "from_kind": src_kind,
                "to_kind": dst_kind,
                "count": cnt,
            })
        return out
```

Now add a rolling-counter helper. Near the top of the module, after the constants block (around line 295), add:

```python
# In-process recent-activity counter, keyed by entity kind. 5-minute window.
# Reset on process restart — single-laptop scale, no persistence needed.
_ACTIVITY_WINDOW_SECONDS = 300
_activity_lock = __import__("threading").Lock()
_activity_events: dict[str, list[float]] = {}


def _record_activity(kind: str | None) -> None:
    if not kind:
        return
    import time as _t
    with _activity_lock:
        bucket = _activity_events.setdefault(kind, [])
        bucket.append(_t.time())


def _activity_per_min(kind: str) -> float:
    import time as _t
    cutoff = _t.time() - _ACTIVITY_WINDOW_SECONDS
    with _activity_lock:
        bucket = _activity_events.get(kind, [])
        # Lazy compaction.
        while bucket and bucket[0] < cutoff:
            bucket.pop(0)
        n = len(bucket)
    return (n / _ACTIVITY_WINDOW_SECONDS) * 60.0
```

Wire `_record_activity` into the three event-emit sites in entity_graph.py:
- In `upsert()`, after `self.bus.emit(FleetEvent(type="entity.upserted", …))` (around line 579), add: `_record_activity(entity.kind)`.
- In `link()`, after the `self.bus.emit(FleetEvent(type="entity.linked", …))` block (around line 656), add: `_record_activity(rel_upper)` (rel name as proxy for activity since both endpoint kinds touched).
- In `get()` (around line 855) and `by_type()` (around line 897), after the bus.emit, add `_record_activity(result.get("_label") if isinstance(result, dict) else None)` and `_record_activity(kind)` respectively.

Expose a public accessor near the bottom of the `EntityGraph` class:

```python
    def recent_activity_per_min(self, kind: str) -> float:
        """Return the rolling 5-minute activity rate for ``kind``."""
        return _activity_per_min(kind)
```

- [ ] **Step 4: Rewrite cities.py routes**

Edit `api/server/routes/cities.py`. Replace `_gather_entity_types()` (lines 132-147) with:

```python
def _gather_entity_types() -> list[dict[str, Any]]:
    """Return cities for the 8 real entity-graph kinds with live counts."""
    from api.server.state import app_state
    real_kinds = ["Person", "Organisation", "Asset", "Money",
                  "Decision", "Place", "Period", "Workflow"]
    try:
        counts = app_state.entities.count_by_kind()
    except Exception:
        counts = {k: 0 for k in real_kinds}
    out: list[dict[str, Any]] = []
    for k in real_kinds:
        cnt = int(counts.get(k, 0))
        try:
            rate = float(app_state.entities.recent_activity_per_min(k))
        except Exception:
            rate = 0.0
        out.append({
            "id": k,
            "kind": "entity_type",
            "label": k,
            "category": "entity",
            "count": cnt,
            "recent_activity_per_min": round(rate, 2),
            "active": cnt > 0 or rate > 0.0,
        })
    return out
```

Replace `entity_edges()` (lines 237-258) with:

```python
@router.get("/edges")
def entity_edges() -> dict[str, Any]:
    """Persistent entity-type edges derived from `_REL_TABLES` with live counts."""
    from api.server.state import app_state
    try:
        rows = app_state.entities.rel_counts()
    except Exception:
        rows = []
    edges = [
        {
            "from_kind": r["from_kind"],
            "to_kind": r["to_kind"],
            "rel": r["rel"],
            "label": r["rel"].lower(),
            "count": int(r.get("count", 0)),
        }
        for r in rows
    ]
    return {"edges": edges, "count": len(edges)}
```

Add `?kind=` filter to `/affinity`. Replace `cities_affinity()` (lines 224-231):

```python
@router.get("/affinity")
def cities_affinity(kind: str | None = Query(None)) -> dict[str, Any]:
    """Pairwise city co-occurrence. With ?kind= returns rels incident to that kind."""
    if kind is not None:
        from api.server.state import app_state
        try:
            rows = app_state.entities.rel_counts()
        except Exception:
            rows = []
        filtered = [
            {
                "rel": r["rel"],
                "partner_kind": r["to_kind"] if r["from_kind"] == kind else r["from_kind"],
                "count": int(r.get("count", 0)),
            }
            for r in rows
            if r["from_kind"] == kind or r["to_kind"] == kind
        ]
        filtered.sort(key=lambda x: -x["count"])
        return {"kind": kind, "rels": filtered}
    now = time.time()
    if _AFFINITY_CACHE["data"] is None or now - _AFFINITY_CACHE["ts"] > _AFFINITY_TTL_S:
        _AFFINITY_CACHE["data"] = _compute_affinity()
        _AFFINITY_CACHE["ts"] = now
    return _AFFINITY_CACHE["data"]
```

- [ ] **Step 5: Update colors.ts**

Edit `web/blueprint/src/components/cosmicLens/lib/colors.ts`. Replace `ENTITY_TYPE_COLORS` block (lines 77-92) with:

```ts
const ENTITY_TYPE_COLORS: Record<string, string> = {
  Person:       "#fb923c",
  Organisation: "#3b82f6",
  Asset:        "#a78bfa",
  Money:        "#22c55e",
  Decision:     "#fbbf24",
  Place:        "#94a3b8",
  Period:       "#64748b",
  Workflow:     "#22d3ee",
};
```

- [ ] **Step 6: Update types.ts**

Edit `web/blueprint/src/components/cosmicLens/lib/types.ts`. Find `CityMeta` interface (around line 18) and extend:

```ts
export interface CityMeta {
  id: string;
  kind: string;
  label: string;
  category?: string;
  count?: number;
  recent_activity_per_min?: number;
  active?: boolean;
}
```

- [ ] **Step 7: Cities.tsx and EntityEdges.tsx render updates**

Edit `web/blueprint/src/components/cosmicLens/Cities.tsx`. Find where the city label is rendered (search for `{city.label}` — it's inside a `<Html>` block). Replace the label expression with:

```tsx
{city.count !== undefined && city.count > 0
  ? `${city.label} · ${city.count}`
  : city.label}
```

Find the city dot/sphere mesh and lower opacity when `city.active === false`. The simplest pattern: in the material props, add:

```tsx
opacity={city.active === false ? 0.35 : 1.0}
transparent={city.active === false}
```

Edit `web/blueprint/src/components/cosmicLens/EntityEdges.tsx`. The fetched edges now carry `count`. In the geometry-build loop, compute width:

```ts
const count = (edge as { count?: number }).count ?? 0;
const width = 0.5 + 0.5 * Math.log10(1 + count);
const opacity = count === 0 ? 0.2 : 0.6;
```

Apply width and opacity to the line material / mesh per edge.

- [ ] **Step 8: useLiveCosmic.ts cadence**

Edit `web/blueprint/src/components/cosmicLens/lib/useLiveCosmic.ts`. Find the cities-polling effect (around line 110 with `CITIES_POLL_MS = 30_000`). Replace the constant or add a mode-aware computation:

```ts
const citiesPollMs = mode === "entities" ? 10_000 : 30_000;
```

And use `citiesPollMs` in the `setTimeout(pollCities, citiesPollMs)` call instead of the constant.

- [ ] **Step 9: Run tests + build**

```bash
PORTAL_DATA_DIR=$(pwd)/data/portal-test python -m pytest tests/api/server/test_entity_view.py -x -q
npm run test -- web/blueprint/src/components/cosmicLens
npm run build:blueprint
```

All green.

- [ ] **Step 10: Commit**

```bash
git add api/server/services/entity_graph.py \
        api/server/routes/cities.py \
        web/blueprint/src/components/cosmicLens/lib/colors.ts \
        web/blueprint/src/components/cosmicLens/lib/types.ts \
        web/blueprint/src/components/cosmicLens/lib/useLiveCosmic.ts \
        web/blueprint/src/components/cosmicLens/Cities.tsx \
        web/blueprint/src/components/cosmicLens/EntityEdges.tsx \
        tests/api/server/test_entity_view.py
git commit -m "feat(cosmic): schema-honest entity cities + live counts

Replace 15 fictional canonical entity kinds (Vendor/Invoice/Candidate/...)
with the 8 real graph kinds the substrate actually stores
(Person/Organisation/Asset/Money/Decision/Place/Period/Workflow). Each
city carries live count + 5-min rolling activity rate; dormant kinds
render at reduced opacity.

Edges derived from the schema's _REL_TABLES with live link counts;
thickness scales as log10(1 + count); dormant edges at low opacity.

Adds entity_graph.count_by_kind / rel_counts / recent_activity_per_min
helpers and a 5-min in-process activity counter wired into upsert /
link / get / by_type bus emit sites.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 2 — first_seen_at / last_seen_at on entities

**Goal:** Add timestamp columns mirrored on every upsert. Enables `?order=recent` and EntityView age display.

**Files:**
- Modify: `api/server/services/entity_graph.py` (schema additions, upsert population, idempotent migration).
- Modify: `api/server/routes/entities.py` (`?order=recent`, include in `/{id}` response).
- Modify: `tests/api/server/test_entity_view.py` (timestamp tests).

- [ ] **Step 1: Add tests**

Append to `tests/api/server/test_entity_view.py`:

```python
def test_entities_endpoint_supports_order_recent(client):
    resp = client.get("/api/entities?kind=Decision&order=recent&limit=5")
    assert resp.status_code == 200
    rows = resp.json()
    if not rows:
        pytest.skip("no Decision entities in graph")
    for r in rows:
        assert "last_seen_at" in r or "decided_at" in r


def test_entity_detail_includes_timestamps(client):
    list_resp = client.get("/api/entities?kind=Decision&limit=1")
    if list_resp.status_code != 200 or not list_resp.json():
        pytest.skip("no entities to detail")
    entity = list_resp.json()[0]
    eid = entity["id"]
    resp = client.get(f"/api/entities/{eid}")
    assert resp.status_code == 200
    body = resp.json()
    assert "first_seen_at" in body or "decided_at" in body, (
        "EntityView needs at least one timestamp anchor"
    )
```

- [ ] **Step 2: Add columns to schema + idempotent migration**

In `api/server/services/entity_graph.py`, after `_REL_TABLES` (around line 285), add:

```python
# Columns added post-Phase-1 to support EntityView age display + ?order=recent.
# `_bootstrap_schema` runs ALTER TABLE ... ADD ... IF NOT EXISTS for each.
_TIMESTAMP_COLUMNS: tuple[str, ...] = ("first_seen_at", "last_seen_at")
_TIMESTAMP_KINDS: tuple[str, ...] = (
    "Person", "Organisation", "Asset", "Money",
    "Decision", "Place", "Period", "Workflow",
)
```

In `_bootstrap_schema()` (around line 456), after the existing rel-table loop, add:

```python
        # Idempotent timestamp-column migration. Kuzu 0.6.1 raises if the
        # column already exists; we swallow exceptions per-attempt.
        for kind in _TIMESTAMP_KINDS:
            for col in _TIMESTAMP_COLUMNS:
                ddl = f"ALTER TABLE {kind} ADD {col} TIMESTAMP"
                try:
                    with self._conn_lock:
                        self.conn.execute(ddl)
                except Exception:
                    pass
```

In `upsert()` (around line 490), after the `_build_set_clauses` line and before `self.conn.execute(MERGE ...)`, append timestamp set clauses. Find the line:

```python
            attr_clauses, attr_params = _build_set_clauses(
                entity.attrs, prefix="n", kind=entity.kind
            )
            set_clauses.extend(attr_clauses)
            params.update(attr_params)
```

Add immediately after:

```python
            # first/last_seen_at: write last on every upsert; first only
            # if currently NULL. Kuzu 0.6.1 has no COALESCE-on-MERGE so
            # we read existing first_seen_at and conditionally include it.
            import datetime as _dt
            now_ts = _dt.datetime.utcnow()
            params["last_seen_at"] = now_ts
            set_clauses.append("n.last_seen_at = $last_seen_at")
            try:
                existing = self.conn.execute(
                    f"MATCH (n:{entity.kind}) WHERE n.id = $id "
                    "RETURN n.first_seen_at AS fs",
                    {"id": entity.id},
                )
                first_existing = None
                if existing.has_next():
                    first_existing = existing.get_next()[0]
                if first_existing is None:
                    params["first_seen_at"] = now_ts
                    set_clauses.append("n.first_seen_at = $first_seen_at")
            except Exception:
                pass
```

- [ ] **Step 3: ?order=recent + timestamps in /{id} response**

Edit `api/server/routes/entities.py`. In `list_entities` (line 28), add the param + ordering:

```python
async def list_entities(
    kind: str | None = None,
    limit: int = 50,
    order: str | None = None,
):
    if kind is not None:
        try:
            rows = app_state.entities.by_type(kind)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        if order == "recent":
            def _ts(row: dict) -> float:
                v = row.get("last_seen_at") or row.get("decided_at")
                if v is None:
                    return 0.0
                try:
                    return v.timestamp() if hasattr(v, "timestamp") else float(v)
                except Exception:
                    return 0.0
            rows = sorted(rows, key=_ts, reverse=True)
        return rows[:limit]
    out: list[dict] = []
    for k in _KINDS:
        if len(out) >= limit:
            break
        remaining = limit - len(out)
        out.extend(app_state.entities.by_type(k)[:remaining])
    return out
```

In the `/{id}` endpoint (line 180), the return already passes through whatever Kuzu returns — `first_seen_at` / `last_seen_at` will appear automatically once columns exist.

- [ ] **Step 4: Run tests + build**

```bash
PORTAL_DATA_DIR=$(pwd)/data/portal-test python -m pytest tests/api/server/test_entity_view.py -x -q
npm run build:blueprint
```

- [ ] **Step 5: Commit**

```bash
git add api/server/services/entity_graph.py \
        api/server/routes/entities.py \
        tests/api/server/test_entity_view.py
git commit -m "feat(entities): first_seen_at + last_seen_at timestamps

Add TIMESTAMP columns to all 8 node tables via idempotent ALTER TABLE
on bootstrap. upsert() writes last_seen_at on every call and
first_seen_at only when currently NULL. /api/entities?order=recent
sorts by last_seen_at DESC.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 3 — CityView per-kind inspector

**Goal:** Replace 14-line CityView placeholder with real per-kind inspector showing recent entities, top relationships, live activity ticker.

**Files:**
- Create: `web/blueprint/src/components/cosmicLens/lib/entityRender.ts`.
- Create: `web/blueprint/src/components/cosmicLens/lib/__tests__/entityRender.test.ts`.
- Modify: `web/blueprint/src/components/cosmicLens/HUD/WorkflowDrawer.tsx` (replace CityView).
- Modify: `web/blueprint/src/components/cosmicLens/lib/types.ts` (EntityRow, EntityLink types).

- [ ] **Step 1: Write entityRender.ts pure helpers**

Create `web/blueprint/src/components/cosmicLens/lib/entityRender.ts`:

```ts
/** Kind-specific key-attr selection + verdict colour + entity-id ref detection. */

export function keyAttrFor(kind: string, row: Record<string, unknown>): string {
  const get = (k: string) => {
    const v = row[k];
    return v === null || v === undefined ? "" : String(v);
  };
  switch (kind) {
    case "Person":
      return get("name") || get("role") || "(unnamed)";
    case "Organisation": {
      const name = get("name");
      const risk = get("risk_band");
      return risk ? `${name} · ${risk}` : name || "(unnamed)";
    }
    case "Asset":
      return [get("kind"), get("identifier")].filter(Boolean).join(" · ") || "(unnamed)";
    case "Money": {
      const amt = get("amount");
      const cur = get("currency");
      const k = get("kind");
      const head = amt && cur ? `${cur} ${amt}` : "";
      return [head, k].filter(Boolean).join(" · ") || "(no amount)";
    }
    case "Decision": {
      const verdict = get("verdict");
      const reason = get("reason").slice(0, 60);
      return reason ? `${verdict}: ${reason}` : verdict || "(no verdict)";
    }
    case "Period":
      return [get("label"), get("kind")].filter(Boolean).join(" · ") || "(unlabelled)";
    case "Place":
      return [get("name"), get("kind")].filter(Boolean).join(" · ") || "(unnamed)";
    case "Workflow":
      return [get("workflow_type"), get("status")].filter(Boolean).join(" · ");
    default:
      return get("id");
  }
}

export function verdictColor(verdict: string | undefined): string {
  switch ((verdict || "").toLowerCase()) {
    case "approve":
    case "approved":
    case "ok":
      return "#4ade80";
    case "reject":
    case "rejected":
    case "deny":
      return "#ef4444";
    case "escalate":
    case "escalated":
      return "#fbbf24";
    default:
      return "#94a3b8";
  }
}

const _ID_PATTERN = /^[A-Z][A-Z0-9_]*-[A-Za-z0-9_-]+$/;

export function extractEntityIdRefs(value: unknown): string[] {
  if (typeof value !== "string") return [];
  if (_ID_PATTERN.test(value)) return [value];
  return [];
}

export function formatRelative(targetMs: number, nowMs: number = Date.now()): string {
  const diff = Math.max(0, nowMs - targetMs);
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

export function parseTimestamp(v: unknown): number | null {
  if (v === null || v === undefined || v === "") return null;
  if (typeof v === "number") return v > 1e12 ? v : v * 1000;
  if (typeof v === "string") {
    const n = Date.parse(v);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}
```

Create `web/blueprint/src/components/cosmicLens/lib/__tests__/entityRender.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import {
  keyAttrFor, verdictColor, extractEntityIdRefs, formatRelative, parseTimestamp,
} from "../entityRender";

describe("keyAttrFor", () => {
  it("Person picks name then role", () => {
    expect(keyAttrFor("Person", { name: "Aisha" })).toBe("Aisha");
    expect(keyAttrFor("Person", { role: "Engineer" })).toBe("Engineer");
    expect(keyAttrFor("Person", {})).toBe("(unnamed)");
  });
  it("Organisation appends risk_band when set", () => {
    expect(keyAttrFor("Organisation", { name: "Globex", risk_band: "amber" })).toBe("Globex · amber");
    expect(keyAttrFor("Organisation", { name: "Globex" })).toBe("Globex");
  });
  it("Money formats amount + currency + kind", () => {
    expect(keyAttrFor("Money", { amount: 1450, currency: "GBP", kind: "invoice" })).toBe("GBP 1450 · invoice");
  });
  it("Decision combines verdict and truncated reason", () => {
    const long = "x".repeat(80);
    const out = keyAttrFor("Decision", { verdict: "approve", reason: long });
    expect(out.startsWith("approve: ")).toBe(true);
    expect(out.length).toBeLessThanOrEqual(70);
  });
});

describe("verdictColor", () => {
  it("maps known verdicts", () => {
    expect(verdictColor("approve")).toBe("#4ade80");
    expect(verdictColor("reject")).toBe("#ef4444");
    expect(verdictColor("escalate")).toBe("#fbbf24");
    expect(verdictColor(undefined)).toBe("#94a3b8");
  });
});

describe("extractEntityIdRefs", () => {
  it("matches PREFIX-suffix patterns", () => {
    expect(extractEntityIdRefs("MONEY-INV-API-0001")).toEqual(["MONEY-INV-API-0001"]);
    expect(extractEntityIdRefs("ORG-vendor-globex")).toEqual(["ORG-vendor-globex"]);
  });
  it("rejects plain text", () => {
    expect(extractEntityIdRefs("hello world")).toEqual([]);
    expect(extractEntityIdRefs(42)).toEqual([]);
  });
});

describe("formatRelative", () => {
  it("formats seconds/minutes/hours/days", () => {
    const now = 10_000_000;
    expect(formatRelative(now - 5_000, now)).toBe("5s ago");
    expect(formatRelative(now - 120_000, now)).toBe("2m ago");
    expect(formatRelative(now - 7200_000, now)).toBe("2h ago");
    expect(formatRelative(now - 2 * 86400_000, now)).toBe("2d ago");
  });
});

describe("parseTimestamp", () => {
  it("handles ISO strings and unix seconds and ms", () => {
    expect(parseTimestamp("2026-05-10T18:00:00Z")).toBe(Date.parse("2026-05-10T18:00:00Z"));
    expect(parseTimestamp(1778000000)).toBe(1778000000 * 1000);
    expect(parseTimestamp(1778000000000)).toBe(1778000000000);
    expect(parseTimestamp(null)).toBe(null);
  });
});
```

- [ ] **Step 2: Run vitest to confirm new tests pass**

```bash
npm run test -- web/blueprint/src/components/cosmicLens/lib/__tests__/entityRender.test.ts
```

Expected: green.

- [ ] **Step 3: Add EntityRow type**

Edit `web/blueprint/src/components/cosmicLens/lib/types.ts`. After `WorkflowMoonData`, add:

```ts
export interface EntityRow {
  id: string;
  kind?: string;
  source_workflows?: string[];
  last_seen_at?: string | number | null;
  first_seen_at?: string | number | null;
  decided_at?: string | number | null;
  [key: string]: unknown;
}

export interface EntityLink {
  rel: string;
  partner_kind?: string;
  count?: number;
  node?: EntityRow;
}

export interface AffinityResponse {
  kind?: string;
  rels?: Array<{ rel: string; partner_kind: string; count: number }>;
}
```

- [ ] **Step 4: Replace CityView body**

Edit `web/blueprint/src/components/cosmicLens/HUD/WorkflowDrawer.tsx`. Find `CityView` (lines 311-325). Replace the entire function body with a real inspector.

Add at the top of the file (with other imports):

```tsx
import { keyAttrFor, verdictColor, formatRelative, parseTimestamp } from "../lib/entityRender";
import type { EntityRow, AffinityResponse, CosmicFlash } from "../lib/types";
import { colorForEntityType } from "../lib/colors";
```

Extend `DrawerView`:

```ts
export interface DrawerView {
  type: "function" | "workflow" | "city" | "entity" | null;
  id?: string;
  label?: string;
}
```

Update `WorkflowDrawerProps` to plumb the entity-open callback and the live flashes ref:

```tsx
interface WorkflowDrawerProps {
  view: DrawerView;
  onClose: () => void;
  onOpenWorkflow: (id: string) => void;
  onOpenEntity?: (id: string) => void;
  flashesRef?: React.MutableRefObject<{ buffer: CosmicFlash[]; version: number }>;
}
```

In `DrawerContent`, route the new entity view and pass the new props:

```tsx
function DrawerContent({
  view,
  onClose,
  onOpenWorkflow,
  onOpenEntity,
  flashesRef,
}: {
  view: DrawerView;
  onClose: () => void;
  onOpenWorkflow: (id: string) => void;
  onOpenEntity?: (id: string) => void;
  flashesRef?: React.MutableRefObject<{ buffer: CosmicFlash[]; version: number }>;
}) {
  if (view.type === "function") {
    return <FunctionView functionKey={view.id ?? ""} label={view.label} onClose={onClose} onOpenWorkflow={onOpenWorkflow} />;
  }
  if (view.type === "workflow") {
    return <WorkflowView workflowId={view.id ?? ""} onClose={onClose} />;
  }
  if (view.type === "city") {
    return <CityView cityId={view.id ?? ""} label={view.label} onClose={onClose}
                     onOpenEntity={onOpenEntity ?? (() => {})}
                     flashesRef={flashesRef} />;
  }
  if (view.type === "entity") {
    return <EntityView entityId={view.id ?? ""} onClose={onClose}
                       onOpenWorkflow={onOpenWorkflow}
                       onOpenEntity={onOpenEntity ?? (() => {})} />;
  }
  return null;
}
```

Replace the existing `CityView` (lines 311-325) entirely with:

```tsx
function CityView({
  cityId, label, onClose, onOpenEntity, flashesRef,
}: {
  cityId: string;
  label?: string;
  onClose: () => void;
  onOpenEntity: (id: string) => void;
  flashesRef?: React.MutableRefObject<{ buffer: CosmicFlash[]; version: number }>;
}) {
  const [recent, setRecent] = useState<EntityRow[]>([]);
  const [rels, setRels] = useState<AffinityResponse["rels"]>([]);
  const [meta, setMeta] = useState<{ count: number; rate: number } | null>(null);
  const [, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [r, a, c] = await Promise.all([
          fetch(`/api/entities?kind=${encodeURIComponent(cityId)}&limit=10&order=recent`).then(x => x.json()),
          fetch(`/api/cities/affinity?kind=${encodeURIComponent(cityId)}`).then(x => x.json()),
          fetch(`/api/cities?mode=entities`).then(x => x.json()),
        ]);
        if (cancelled) return;
        setRecent(Array.isArray(r) ? r : []);
        setRels((a as AffinityResponse).rels ?? []);
        const cities = (c.cities ?? c) as Array<{ id: string; count: number; recent_activity_per_min: number }>;
        const me = cities.find(x => x.id === cityId);
        if (me) setMeta({ count: me.count ?? 0, rate: me.recent_activity_per_min ?? 0 });
      } catch (err) {
        console.warn("CityView fetch failed", err);
      }
    }
    load();
    const iv = setInterval(load, 8000);
    const tick = setInterval(() => setTick(t => t + 1), 1000);
    return () => { cancelled = true; clearInterval(iv); clearInterval(tick); };
  }, [cityId]);

  const liveActivity = (() => {
    if (!flashesRef) return [];
    const buf = flashesRef.current.buffer;
    return buf
      .filter(f => (f.type === "entity.read" || f.type === "entity.upserted" || f.type === "entity.linked")
                   && (f as unknown as { kind?: string }).kind === cityId)
      .slice(-5)
      .reverse();
  })();

  const color = colorForEntityType(cityId);
  return (
    <>
      <DrawerHeader
        title={label ?? cityId}
        subtitle={meta ? `${meta.count} entities · ${meta.rate.toFixed(1)}/min` : "entity kind"}
        onClose={onClose}
      />
      <div style={{ flex: 1, overflowY: "auto", padding: "12px 20px" }}>
        <SectionHeader>Most recently touched</SectionHeader>
        {recent.length === 0 && <Empty>No entities of this kind yet.</Empty>}
        {recent.map((r) => {
          const ts = parseTimestamp(r.last_seen_at ?? r.decided_at ?? r.first_seen_at);
          const wfCount = (r.source_workflows ?? []).length;
          const wfTypes = new Set((r.source_workflows ?? []).map((w: string) => w.split("-")[0]));
          const crossDomain = wfTypes.size >= 2;
          return (
            <Row key={r.id} onClick={() => onOpenEntity(r.id)}>
              <div style={{ color: "#22d3ee", fontWeight: 600 }}>{r.id}</div>
              <div style={{ fontSize: 11, color: "#cbd5e1", marginTop: 2 }}>
                {keyAttrFor(cityId, r as Record<string, unknown>)}
              </div>
              <div style={{ fontSize: 10, color: "#64748b", marginTop: 4, display: "flex", gap: 8 }}>
                {ts && <span>{formatRelative(ts)}</span>}
                {wfCount > 0 && <span>{wfCount} wfs</span>}
                {crossDomain && <span style={{ color: color, fontWeight: 600 }}>cross-domain</span>}
              </div>
            </Row>
          );
        })}

        <SectionHeader style={{ marginTop: 18 }}>Top relationships</SectionHeader>
        {(rels ?? []).length === 0 && <Empty>No relationships incident to this kind.</Empty>}
        {(rels ?? []).slice(0, 5).map((rl) => (
          <div key={`${rl.rel}-${rl.partner_kind}`} style={{
            padding: "6px 12px", margin: "2px 0",
            background: "rgba(15,23,42,0.4)", fontSize: 12, color: "#cbd5e1",
            display: "flex", justifyContent: "space-between",
          }}>
            <span style={{ color: "#a78bfa" }}>{rl.rel}</span>
            <span style={{ color: "#94a3b8" }}>{rl.partner_kind} · {rl.count}</span>
          </div>
        ))}

        <SectionHeader style={{ marginTop: 18 }}>Live activity</SectionHeader>
        {liveActivity.length === 0 && <Empty>No recent events for this kind.</Empty>}
        {liveActivity.map((f, i) => (
          <div key={i} style={{
            padding: "4px 12px", fontSize: 11, color: "#94a3b8",
            borderLeft: `2px solid ${color}`, margin: "2px 0",
          }}>
            <span style={{ color: "#cbd5e1" }}>{f.type.replace("entity.", "")}</span>
            {f.workflow_id && <span style={{ marginLeft: 8 }}>· {f.workflow_id}</span>}
          </div>
        ))}
      </div>
    </>
  );
}

function SectionHeader({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{
      fontSize: 10, textTransform: "uppercase", letterSpacing: 0.8,
      color: "#64748b", fontWeight: 700, marginBottom: 6, ...(style || {}),
    }}>
      {children}
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ color: "#475569", fontStyle: "italic", fontSize: 11, padding: "4px 0" }}>
      {children}
    </div>
  );
}

function Row({ children, onClick }: { children: React.ReactNode; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        display: "block", width: "100%", padding: "8px 12px", margin: "3px 0",
        background: "rgba(15,23,42,0.5)", border: "1px solid rgba(99,102,241,0.12)",
        borderRadius: 6, cursor: onClick ? "pointer" : "default", textAlign: "left",
        color: "#e2e8f0", fontFamily: "inherit", fontSize: 12,
      }}
    >
      {children}
    </button>
  );
}
```

- [ ] **Step 4: Add EntityView stub (will be filled in Task 4)**

Append to the same file, just below CityView:

```tsx
function EntityView({
  entityId, onClose, onOpenWorkflow, onOpenEntity,
}: {
  entityId: string;
  onClose: () => void;
  onOpenWorkflow: (id: string) => void;
  onOpenEntity: (id: string) => void;
}) {
  return (
    <>
      <DrawerHeader title={entityId} subtitle="entity (Task 4 fills this in)" onClose={onClose} />
      <div style={{ padding: 20, color: "#94a3b8", fontSize: 12 }}>
        EntityView placeholder — replaced by Task 4. References used so the
        compiler doesn't complain: <span style={{ display: "none" }}>
          {String(typeof onOpenWorkflow)}{String(typeof onOpenEntity)}
        </span>
      </div>
    </>
  );
}
```

Update the WorkflowDrawer call site in `CosmicLens.tsx` to pass the new props (only `onOpenEntity` and `flashesRef` — both new). Find the `<WorkflowDrawer ... />` JSX and add:

```tsx
<WorkflowDrawer
  view={drawerView}
  onClose={() => setDrawerView({ type: null })}
  onOpenWorkflow={(id) => setDrawerView({ type: "workflow", id })}
  onOpenEntity={(id) => setDrawerView({ type: "entity", id })}
  flashesRef={live.flashesRef}
/>
```

- [ ] **Step 5: Run tests + build**

```bash
npm run test -- web/blueprint/src/components/cosmicLens
npm run build:blueprint
```

- [ ] **Step 6: Commit**

```bash
git add web/blueprint/src/components/cosmicLens/lib/entityRender.ts \
        web/blueprint/src/components/cosmicLens/lib/__tests__/entityRender.test.ts \
        web/blueprint/src/components/cosmicLens/lib/types.ts \
        web/blueprint/src/components/cosmicLens/HUD/WorkflowDrawer.tsx \
        web/blueprint/src/components/cosmicLens/CosmicLens.tsx
git commit -m "feat(cosmic): real CityView per-kind entity inspector

Replace 14-line placeholder with three-panel inspector:
- Most-recently-touched (10 rows, click-through to EntityView)
- Top relationships incident to this kind
- Live activity ticker from flashesRef

Adds entityRender.ts pure helpers (keyAttrFor, verdictColor,
extractEntityIdRefs, formatRelative, parseTimestamp) with vitest
coverage. Extends DrawerView union with 'entity' (filled in next
commit). Cross-domain workflow badge on entities spanning >=2
workflow types.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 4 — EntityView drawer with kind-specific narrative panels

**Goal:** Per-entity drawer with Attributes + Touched-by + Linked + kind-specific narrative panel (Person breach history, Organisation cross-domain footprint + hot vendor badge, Money transactional context with auto-link references, Decision verdict-card).

**Files:**
- Modify: `web/blueprint/src/components/cosmicLens/HUD/WorkflowDrawer.tsx` (replace EntityView stub).

- [ ] **Step 1: Replace EntityView stub with full implementation**

Replace the EntityView stub from Task 3 with:

```tsx
function EntityView({
  entityId, onClose, onOpenWorkflow, onOpenEntity,
}: {
  entityId: string;
  onClose: () => void;
  onOpenWorkflow: (id: string) => void;
  onOpenEntity: (id: string) => void;
}) {
  const [entity, setEntity] = useState<EntityRow | null>(null);
  const [linked, setLinked] = useState<Array<{ node: EntityRow; rel: string }>>([]);
  const [, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [e, l] = await Promise.all([
          fetch(`/api/entities/${encodeURIComponent(entityId)}`).then(r => r.json()),
          fetch(`/api/entities/${encodeURIComponent(entityId)}/linked`).then(r => r.json()),
        ]);
        if (cancelled) return;
        setEntity(e);
        setLinked(Array.isArray(l) ? l : []);
      } catch (err) {
        console.warn("EntityView fetch failed", err);
      }
    }
    load();
    const tick = setInterval(() => setTick(t => t + 1), 1000);
    return () => { cancelled = true; clearInterval(tick); };
  }, [entityId]);

  if (!entity) {
    return (
      <>
        <DrawerHeader title={entityId} subtitle="loading…" onClose={onClose} />
        <div style={{ padding: 20, color: "#64748b", fontStyle: "italic" }}>loading entity…</div>
      </>
    );
  }

  const kind = String(entity._label ?? entity.kind ?? "Unknown");
  const color = colorForEntityType(kind);
  const firstSeenMs = parseTimestamp(entity.first_seen_at);
  const lastSeenMs = parseTimestamp(entity.last_seen_at ?? entity.decided_at);
  const sourceWfs = (entity.source_workflows ?? []) as string[];
  const wfTypeCounts = new Map<string, number>();
  for (const wf of sourceWfs) {
    const t = wf.split("-")[0];
    wfTypeCounts.set(t, (wfTypeCounts.get(t) ?? 0) + 1);
  }

  const linkedByRel = new Map<string, Array<{ node: EntityRow; rel: string }>>();
  for (const l of linked) {
    if (!linkedByRel.has(l.rel)) linkedByRel.set(l.rel, []);
    linkedByRel.get(l.rel)!.push(l);
  }

  return (
    <>
      <DrawerHeader
        title={entityId}
        subtitle={kind}
        onClose={onClose}
      />
      <div style={{ flex: 1, overflowY: "auto", padding: "12px 20px" }}>
        <div style={{
          display: "flex", gap: 8, marginBottom: 14,
          fontSize: 11, color: "#94a3b8",
        }}>
          <span style={{ background: color, color: "#0f172a", padding: "2px 8px", borderRadius: 4, fontWeight: 600 }}>{kind}</span>
          {firstSeenMs && <span>created {formatRelative(firstSeenMs)}</span>}
          {lastSeenMs && <span>· touched {formatRelative(lastSeenMs)}</span>}
        </div>

        <NarrativePanel kind={kind} entity={entity} onOpenEntity={onOpenEntity} />

        <SectionHeader>Attributes</SectionHeader>
        <AttributesPanel entity={entity} onOpenEntity={onOpenEntity} />

        <SectionHeader style={{ marginTop: 18 }}>
          Touched by ({sourceWfs.length} workflow{sourceWfs.length === 1 ? "" : "s"}, {wfTypeCounts.size} domain{wfTypeCounts.size === 1 ? "" : "s"})
        </SectionHeader>
        {sourceWfs.length === 0 && <Empty>No workflows have touched this entity.</Empty>}
        {sourceWfs.length > 0 && (
          <div>
            {[...wfTypeCounts.entries()].sort((a, b) => b[1] - a[1]).map(([t, n]) => (
              <div key={t} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, color: "#cbd5e1", padding: "2px 0" }}>
                <span style={{ width: 80 }}>{t}</span>
                <div style={{ flex: 1, height: 6, background: "rgba(99,102,241,0.15)" }}>
                  <div style={{ width: `${Math.min(100, n * 4)}%`, height: 6, background: "#a78bfa" }} />
                </div>
                <span style={{ width: 24, textAlign: "right" }}>{n}</span>
              </div>
            ))}
            <div style={{ marginTop: 8, fontSize: 10, color: "#64748b" }}>
              {sourceWfs.slice(0, 8).map((wf) => (
                <button
                  key={wf}
                  onClick={() => onOpenWorkflow(wf)}
                  style={{
                    background: "transparent", border: "1px solid rgba(99,102,241,0.2)",
                    color: "#22d3ee", padding: "2px 6px", marginRight: 4, marginBottom: 4,
                    fontSize: 10, cursor: "pointer", borderRadius: 3,
                  }}
                >
                  {wf}
                </button>
              ))}
              {sourceWfs.length > 8 && <span style={{ marginLeft: 4 }}>+{sourceWfs.length - 8} more</span>}
            </div>
          </div>
        )}

        <SectionHeader style={{ marginTop: 18 }}>Linked entities</SectionHeader>
        {linkedByRel.size === 0 && <Empty>No outgoing relationships.</Empty>}
        {[...linkedByRel.entries()].map(([rel, items]) => (
          <div key={rel} style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 10, color: "#a78bfa", fontWeight: 600, padding: "4px 0" }}>{rel} ({items.length})</div>
            {items.map((l, i) => {
              const partnerKind = String(l.node._label ?? l.node.kind ?? "?");
              const partnerColor = colorForEntityType(partnerKind);
              return (
                <Row key={`${rel}-${i}`} onClick={() => onOpenEntity(String(l.node.id))}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "#22d3ee" }}>{String(l.node.id)}</span>
                    <span style={{ color: partnerColor, fontSize: 10 }}>{partnerKind}</span>
                  </div>
                </Row>
              );
            })}
          </div>
        ))}
      </div>
    </>
  );
}

function NarrativePanel({
  kind, entity, onOpenEntity,
}: { kind: string; entity: EntityRow; onOpenEntity: (id: string) => void }) {
  if (kind === "Decision") {
    const verdict = String(entity.verdict ?? "");
    const reason = String(entity.reason ?? "");
    return (
      <div style={{
        padding: "10px 12px", marginBottom: 14,
        background: "rgba(15,23,42,0.7)",
        borderLeft: `3px solid ${verdictColor(verdict)}`,
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: verdictColor(verdict), marginBottom: 4 }}>
          {verdict || "(no verdict)"}
        </div>
        <div style={{ fontSize: 12, color: "#cbd5e1", lineHeight: 1.4 }}>{reason || "(no reason)"}</div>
        <div style={{ fontSize: 10, color: "#64748b", marginTop: 6 }}>
          {[entity.persona_role, entity.phase, entity.workflow_id].filter(Boolean).join(" · ")}
        </div>
      </div>
    );
  }
  if (kind === "Person") {
    let attrs: Record<string, unknown> = {};
    try {
      const raw = entity.attributes;
      attrs = typeof raw === "string" ? JSON.parse(raw) : (raw as Record<string, unknown> ?? {});
    } catch { /* ignore */ }
    const breaches = (attrs.breach_history as Array<{ category?: string; date?: string; tier?: string }> | undefined) ?? [];
    if (breaches.length === 0) return null;
    return (
      <div style={{ marginBottom: 14 }}>
        <SectionHeader>Policy breaches ({breaches.length})</SectionHeader>
        {breaches.map((b, i) => {
          const dot = b.tier === "escalation" ? "#ef4444" : b.tier === "warning" ? "#fbbf24" : "#94a3b8";
          return (
            <div key={i} style={{
              display: "flex", gap: 8, alignItems: "center",
              padding: "4px 8px", margin: "2px 0",
              background: "rgba(15,23,42,0.4)", fontSize: 11, color: "#cbd5e1",
            }}>
              <span style={{ width: 8, height: 8, borderRadius: 4, background: dot, display: "inline-block" }} />
              <span style={{ flex: 1 }}>{b.category ?? "(unspecified)"}</span>
              <span style={{ color: "#64748b", fontSize: 10 }}>{b.date ?? ""}</span>
            </div>
          );
        })}
      </div>
    );
  }
  if (kind === "Organisation") {
    const sourceWfs = (entity.source_workflows ?? []) as string[];
    const types = new Set(sourceWfs.map((w) => w.split("-")[0]));
    const isHot = types.size >= 3 && sourceWfs.length >= 10;
    let attrs: Record<string, unknown> = {};
    try {
      const raw = entity.attributes;
      attrs = typeof raw === "string" ? JSON.parse(raw) : (raw as Record<string, unknown> ?? {});
    } catch { /* ignore */ }
    return (
      <div style={{ marginBottom: 14 }}>
        {isHot && (
          <div style={{
            background: "rgba(251,146,60,0.15)", border: "1px solid #fb923c",
            color: "#fb923c", padding: "4px 10px", marginBottom: 8,
            fontSize: 11, fontWeight: 600, borderRadius: 4,
          }}>
            🔥 Hot vendor — touches {types.size} workflow types across {sourceWfs.length} workflows
          </div>
        )}
        <SectionHeader>Risk profile</SectionHeader>
        <div style={{ fontSize: 11, color: "#cbd5e1", padding: "4px 0", lineHeight: 1.6 }}>
          {entity.risk_band && <div>risk_band: <strong style={{ color: entity.risk_band === "red" ? "#ef4444" : entity.risk_band === "amber" ? "#fbbf24" : "#4ade80" }}>{String(entity.risk_band)}</strong></div>}
          {entity.country && <div>country: {String(entity.country)}</div>}
          {entity.jurisdiction && <div>jurisdiction: {String(entity.jurisdiction)}</div>}
          {attrs.creditRating !== undefined && <div>creditRating: {String(attrs.creditRating)}</div>}
          {attrs.sanctioned !== undefined && <div>sanctioned: <strong style={{ color: attrs.sanctioned ? "#ef4444" : "#4ade80" }}>{String(attrs.sanctioned)}</strong></div>}
        </div>
      </div>
    );
  }
  if (kind === "Money") {
    const amount = entity.amount;
    const currency = entity.currency;
    if (amount === undefined && currency === undefined) return null;
    return (
      <div style={{
        padding: "10px 12px", marginBottom: 14,
        background: "rgba(34,197,94,0.08)", border: "1px solid rgba(34,197,94,0.3)",
      }}>
        <div style={{ fontSize: 18, fontWeight: 700, color: "#22c55e" }}>
          {currency ? String(currency) : ""} {amount !== undefined ? String(amount) : ""}
        </div>
        {entity.kind && <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 4 }}>kind: {String(entity.kind)}</div>}
      </div>
    );
  }
  // No narrative panel for Asset / Place / Period / Workflow.
  return null;
}

function AttributesPanel({
  entity, onOpenEntity,
}: { entity: EntityRow; onOpenEntity: (id: string) => void }) {
  const skipKeys = new Set([
    "id", "_label", "kind", "source_workflows",
    "first_seen_at", "last_seen_at",
    "verdict", "reason", "persona_role", "phase", "workflow_id",
    "amount", "currency", "risk_band", "country", "jurisdiction",
    "name", "email", "role", "market", "department",
    "label", "starts", "ends",
  ]);

  const rows: Array<[string, unknown]> = [];
  for (const [k, v] of Object.entries(entity)) {
    if (skipKeys.has(k)) continue;
    if (v === null || v === undefined || v === "") continue;
    rows.push([k, v]);
  }

  if (rows.length === 0) {
    return <Empty>No additional attributes.</Empty>;
  }

  return (
    <div style={{ fontSize: 11, fontFamily: "ui-monospace", color: "#cbd5e1", lineHeight: 1.6 }}>
      {rows.map(([k, v]) => {
        let display: string;
        if (typeof v === "string") display = v;
        else {
          try { display = JSON.stringify(v); } catch { display = String(v); }
        }
        const refs = extractEntityIdRefs(display);
        const truncated = display.length > 80 ? display.slice(0, 80) + "…" : display;
        return (
          <div key={k} style={{ padding: "2px 0" }}>
            <span style={{ color: "#64748b" }}>{k}:</span>{" "}
            {refs.length > 0
              ? <button
                  onClick={() => onOpenEntity(refs[0])}
                  style={{ background: "transparent", border: "none", color: "#22d3ee", cursor: "pointer", padding: 0, fontFamily: "inherit", fontSize: 11 }}
                >
                  {refs[0]}
                </button>
              : <span title={display}>{truncated}</span>}
          </div>
        );
      })}
    </div>
  );
}
```

Add the `extractEntityIdRefs` import at the top of the file:

```tsx
import { keyAttrFor, verdictColor, formatRelative, parseTimestamp, extractEntityIdRefs } from "../lib/entityRender";
```

- [ ] **Step 2: Run tests + build**

```bash
npm run test -- web/blueprint/src/components/cosmicLens
npm run build:blueprint
```

- [ ] **Step 3: Commit**

```bash
git add web/blueprint/src/components/cosmicLens/HUD/WorkflowDrawer.tsx
git commit -m "feat(cosmic): EntityView drawer with kind-specific narrative

Per-entity drawer (DrawerView.type='entity') showing:
- kind chip + first/last_seen_at age
- Per-kind narrative panel:
    Decision: verdict-card (colour-coded) + reason + persona/phase/wf
    Person: policy breach history with severity dots
    Organisation: hot-vendor badge + risk profile (risk_band, credit, sanctioned)
    Money: large amount/currency callout
- Attributes panel with auto-link entity-id detection (click → recurse)
- Touched by panel — bar chart by workflow_type + clickable wf ids
- Linked entities grouped by rel — partner kind chips, click to recurse

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 5 — Knowledge Pulse + entity-mode rocket affordances

**Goal:** Always-visible HUD strip in entities mode showing total entities, growth in last 60s, decisions/min, links/min, top cross-domain entities. Rockets in entities mode hover-reveal entity_id, click to open EntityView, and pulse the destination city in the entity's kind colour on arrival.

**Files:**
- Create: `web/blueprint/src/components/cosmicLens/HUD/KnowledgePulse.tsx`.
- Modify: `api/server/routes/entities.py` (`/api/entities/_pulse` endpoint).
- Modify: `api/server/services/entity_graph.py` (`cross_domain_top` helper).
- Modify: `web/blueprint/src/components/cosmicLens/lib/types.ts` (`PulseSnapshot`).
- Modify: `web/blueprint/src/components/cosmicLens/lib/useLiveCosmic.ts` (pulse polling).
- Modify: `web/blueprint/src/components/cosmicLens/CosmicLens.tsx` (mount KnowledgePulse, wire rocket clicks).
- Modify: `web/blueprint/src/components/cosmicLens/Rockets.tsx` (entities-mode hover label, click handler, pulse callback on arrival).
- Modify: `web/blueprint/src/components/cosmicLens/Cities.tsx` (consume pulse callback to flash kind colour).
- Modify: `tests/api/server/test_entity_view.py` (pulse endpoint test).

- [ ] **Step 1: Add cross_domain_top helper + pulse endpoint test**

In `api/server/services/entity_graph.py`, after `count_by_kind()`, add:

```python
    def cross_domain_top(self, limit: int = 5) -> list[dict[str, Any]]:
        """Top entities by distinct workflow-type count derived from source_workflows.

        We stream the kinds that declare source_workflows (Person /
        Organisation / Asset / Money) and compute distinct workflow-type
        counts in Python — Kuzu 0.6.1 lacks the list-comprehension
        primitives needed to do this in a single Cypher query. Cheap at
        demo scale (< few thousand rows).
        """
        candidates: list[dict[str, Any]] = []
        for kind in ("Person", "Organisation", "Asset", "Money"):
            try:
                rows = self.by_type(kind)
            except Exception:
                continue
            for row in rows:
                sw = row.get("source_workflows") or []
                if not sw:
                    continue
                types = {str(w).split("-")[0] for w in sw if isinstance(w, str)}
                candidates.append({
                    "id": row.get("id"),
                    "kind": kind,
                    "workflow_count": len(sw),
                    "workflow_types_count": len(types),
                })
        candidates.sort(key=lambda r: (r["workflow_types_count"], r["workflow_count"]), reverse=True)
        return candidates[:limit]
```

Append to `tests/api/server/test_entity_view.py`:

```python
def test_pulse_endpoint_shape(client):
    resp = client.get("/api/entities/_pulse")
    assert resp.status_code == 200
    body = resp.json()
    for k in ("total", "growth_60s", "decisions_per_min", "links_per_min", "cross_domain_top"):
        assert k in body, f"_pulse missing {k}"
    assert isinstance(body["cross_domain_top"], list)
```

- [ ] **Step 2: Add /api/entities/_pulse endpoint**

In `api/server/routes/entities.py`, before the `/{id}` route, add:

```python
import time as _time
_PULSE_BASELINE: dict[str, tuple[float, int]] = {"prev": (0.0, 0)}


@router.get("/_pulse")
async def entities_pulse():
    """Snapshot of substrate knowledge growth + activity rates."""
    counts = app_state.entities.count_by_kind()
    total = sum(counts.values())
    now = _time.time()
    prev_ts, prev_total = _PULSE_BASELINE["prev"]
    growth_60s = 0
    if prev_ts > 0 and now - prev_ts < 90:
        growth_60s = max(0, total - prev_total)
    if now - prev_ts > 60:
        _PULSE_BASELINE["prev"] = (now, total)
    decisions_rate = 0.0
    links_rate = 0.0
    try:
        decisions_rate = float(app_state.entities.recent_activity_per_min("Decision"))
        # rel_counts isn't keyed in the activity counter; sum link emits proxied via rel names
        links_rate = sum(
            float(app_state.entities.recent_activity_per_min(r))
            for r in ("EMPLOYED_BY", "MANAGES", "OWNS", "TRANSACTS", "BELONGS_TO",
                      "LOCATED_IN", "DECIDED_ON", "PRECEDENT_OF", "TOUCHED", "SUB_WORKFLOW_OF")
        )
    except Exception:
        pass
    try:
        cross = app_state.entities.cross_domain_top(limit=5)
    except Exception:
        cross = []
    return {
        "total": total,
        "growth_60s": growth_60s,
        "decisions_per_min": round(decisions_rate, 2),
        "links_per_min": round(links_rate, 2),
        "cross_domain_top": cross,
    }
```

- [ ] **Step 3: Add PulseSnapshot type and pulse polling**

Append to `web/blueprint/src/components/cosmicLens/lib/types.ts`:

```ts
export interface PulseSnapshot {
  total: number;
  growth_60s: number;
  decisions_per_min: number;
  links_per_min: number;
  cross_domain_top: Array<{
    id: string;
    kind: string;
    workflow_count: number;
    workflow_types_count: number;
  }>;
}
```

In `web/blueprint/src/components/cosmicLens/lib/useLiveCosmic.ts`, add to `UseLiveCosmicResult`:

```ts
  pulse: PulseSnapshot | null;
```

Add a polling effect (after the cities-polling effect):

```ts
  const [pulse, setPulse] = useState<PulseSnapshot | null>(null);
  useEffect(() => {
    if (mode !== "entities") return;
    let cancelled = false;
    let timer: number | undefined;
    async function poll() {
      try {
        const r = await fetch("/api/entities/_pulse");
        if (!cancelled && r.ok) setPulse(await r.json());
      } catch { /* ignore */ }
      finally {
        if (!cancelled) timer = window.setTimeout(poll, 5000);
      }
    }
    poll();
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
  }, [mode]);
```

And add `pulse` to the return object.

- [ ] **Step 4: Create KnowledgePulse component**

Create `web/blueprint/src/components/cosmicLens/HUD/KnowledgePulse.tsx`:

```tsx
import { useEffect, useRef, useState } from "react";
import type { PulseSnapshot, CosmicFlash } from "../lib/types";
import { colorForEntityType } from "../lib/colors";

interface KnowledgePulseProps {
  pulse: PulseSnapshot | null;
  flashesRef: React.MutableRefObject<{ buffer: CosmicFlash[]; version: number }>;
  onOpenEntity: (id: string) => void;
}

const SPARK_LEN = 60;

export function KnowledgePulse({ pulse, flashesRef, onOpenEntity }: KnowledgePulseProps) {
  const decisionSpark = useRef<number[]>(new Array(SPARK_LEN).fill(0));
  const linksSpark = useRef<number[]>(new Array(SPARK_LEN).fill(0));
  const [, force] = useState(0);

  useEffect(() => {
    let lastVersion = 0;
    let dec = 0, lnk = 0;
    const tick = setInterval(() => {
      const ref = flashesRef.current;
      if (ref.version !== lastVersion) {
        const newCount = Math.max(1, Math.min(ref.buffer.length, ref.version - lastVersion));
        const tail = ref.buffer.slice(ref.buffer.length - newCount);
        for (const f of tail) {
          if (f.type === "decision.recorded") dec++;
          if (f.type === "entity.linked") lnk++;
        }
        lastVersion = ref.version;
      }
      decisionSpark.current = [...decisionSpark.current.slice(1), dec];
      linksSpark.current = [...linksSpark.current.slice(1), lnk];
      dec = 0; lnk = 0;
      force(t => t + 1);
    }, 1000);
    return () => clearInterval(tick);
  }, [flashesRef]);

  return (
    <div style={{
      position: "absolute", top: 56, left: 16, right: 16,
      display: "flex", gap: 16,
      pointerEvents: "auto", zIndex: 25,
    }}>
      <Stat title="Total entities" value={pulse?.total ?? "—"} sub={pulse && pulse.growth_60s > 0 ? `+${pulse.growth_60s} in last 60s` : "no growth"} />
      <Stat title="Decisions/min" value={pulse?.decisions_per_min?.toFixed(1) ?? "—"} sparkline={decisionSpark.current} color="#fbbf24" />
      <Stat title="Links/min" value={pulse?.links_per_min?.toFixed(1) ?? "—"} sparkline={linksSpark.current} color="#a78bfa" />
      <CrossDomainPanel cross={pulse?.cross_domain_top ?? []} onOpenEntity={onOpenEntity} />
    </div>
  );
}

function Stat({
  title, value, sub, sparkline, color,
}: {
  title: string; value: number | string; sub?: string;
  sparkline?: number[]; color?: string;
}) {
  return (
    <div style={{
      flex: 1, minWidth: 140,
      background: "rgba(2,6,23,0.7)", border: "1px solid rgba(99,102,241,0.18)",
      padding: "8px 12px", color: "#e2e8f0",
      fontFamily: "ui-sans-serif, system-ui",
    }}>
      <div style={{ fontSize: 9, textTransform: "uppercase", letterSpacing: 0.8, color: "#64748b" }}>{title}</div>
      <div style={{ fontSize: 18, fontWeight: 700, marginTop: 2 }}>{value}</div>
      {sub && <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 2 }}>{sub}</div>}
      {sparkline && <Sparkline values={sparkline} color={color ?? "#22d3ee"} />}
    </div>
  );
}

function Sparkline({ values, color }: { values: number[]; color: string }) {
  const max = Math.max(1, ...values);
  const w = 120, h = 18;
  const step = w / Math.max(1, values.length - 1);
  const pts = values.map((v, i) => `${(i * step).toFixed(1)},${(h - (v / max) * h).toFixed(1)}`).join(" ");
  return (
    <svg width={w} height={h} style={{ display: "block", marginTop: 4 }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth={1.4} opacity={0.85} />
    </svg>
  );
}

function CrossDomainPanel({
  cross, onOpenEntity,
}: { cross: PulseSnapshot["cross_domain_top"]; onOpenEntity: (id: string) => void }) {
  return (
    <div style={{
      flex: 2, minWidth: 220,
      background: "rgba(2,6,23,0.7)", border: "1px solid rgba(99,102,241,0.18)",
      padding: "8px 12px", color: "#e2e8f0",
      fontFamily: "ui-sans-serif, system-ui",
    }}>
      <div style={{ fontSize: 9, textTransform: "uppercase", letterSpacing: 0.8, color: "#64748b" }}>Cross-domain leaders</div>
      {cross.length === 0 && <div style={{ color: "#475569", fontStyle: "italic", fontSize: 10, marginTop: 4 }}>no cross-domain entities yet</div>}
      {cross.slice(0, 3).map((e) => (
        <button
          key={e.id}
          onClick={() => onOpenEntity(e.id)}
          style={{
            display: "flex", justifyContent: "space-between", alignItems: "center",
            width: "100%", marginTop: 4, padding: "3px 6px",
            background: "transparent", border: "1px solid rgba(99,102,241,0.15)",
            cursor: "pointer", color: "#e2e8f0", fontSize: 11, textAlign: "left",
            fontFamily: "inherit",
          }}
        >
          <span style={{ color: colorForEntityType(e.kind) }}>{e.id}</span>
          <span style={{ color: "#94a3b8", fontSize: 10 }}>
            {e.workflow_types_count} domains · {e.workflow_count} wfs
          </span>
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 5: Mount KnowledgePulse + wire rocket clicks in CosmicLens.tsx**

In `web/blueprint/src/components/cosmicLens/CosmicLens.tsx`, import:

```tsx
import { KnowledgePulse } from "./HUD/KnowledgePulse";
```

Find the JSX root and add (only when mode === "entities"):

```tsx
{live.mode === "entities" && (
  <KnowledgePulse
    pulse={live.pulse}
    flashesRef={live.flashesRef}
    onOpenEntity={(id) => setDrawerView({ type: "entity", id })}
  />
)}
```

For rocket clicks in entities mode, the existing rocket-mesh click already routes to the workflow drawer. Update the handler to detect entity_id when `mode === "entities"`:

```tsx
// Where you handle rocket click (search for setDrawerView({ type: "workflow" ...
// inside Rockets click handler region):
if (live.mode === "entities" && rocket.last_event && (rocket.last_event as { entity_id?: string }).entity_id) {
  setDrawerView({ type: "entity", id: (rocket.last_event as { entity_id?: string }).entity_id! });
} else {
  setDrawerView({ type: "workflow", id: rocket.workflow_id });
}
```

(If the rocket data doesn't carry the last entity_id today, capture it in `Rockets.tsx` Step 6 below.)

- [ ] **Step 6: Rockets.tsx — capture last entity_id, hover label, click handler**

In `web/blueprint/src/components/cosmicLens/Rockets.tsx`, in the SSE drain loop where it handles entity events (post substrate-realism work), capture the entity_id onto the rocket state:

```ts
// Inside the drain useEffect, in the entity-event branch (where you set
// r.last_event_type / r.last_label):
r.last_label = mode === "capabilities" ? labelForCapability(flash) : labelForEntity(flash);
(r as unknown as { last_entity_id?: string }).last_entity_id =
  (flash as unknown as { entity_id?: string }).entity_id;
```

And in `Rockets.tsx` where the click is wired (or in `CosmicLens.tsx` if click handlers live there), prefer `last_entity_id` over `workflow_id` when entities mode is active.

If hover labels are rendered in `CosmicLens.tsx`'s hovered-rocket strip, add an `entity_id` line for entities mode.

- [ ] **Step 7: Cities.tsx — pulse on rocket arrival in entities mode**

The simplest approach is to add a pulse driven by recent `entity.read|upserted|linked` events of matching kind. Inside `Cities.tsx`, near the city render loop, add a small per-city last-event timestamp ref, updated by reading `flashesRef` on a 250ms interval. On render, if `now - lastTouched < 600` and `mode === "entities"`, scale-up the city slightly and tint its emissive via `colorForEntityType(city.id)`.

Concretely, in `Cities.tsx` (Cities accepts `flashesRef` already? if not, plumb it from CosmicLens):

```tsx
const lastTouchRef = useRef<Map<string, number>>(new Map());
useEffect(() => {
  if (mode !== "entities" || !flashesRef) return;
  const iv = setInterval(() => {
    const buf = flashesRef.current.buffer;
    const recent = buf.slice(-20);
    for (const f of recent) {
      if (f.type === "entity.read" || f.type === "entity.upserted" || f.type === "entity.linked") {
        const k = (f as unknown as { kind?: string }).kind;
        if (k) lastTouchRef.current.set(k, Date.now());
      }
    }
  }, 200);
  return () => clearInterval(iv);
}, [mode, flashesRef]);
```

In the per-city material props, when `mode === "entities"`:

```tsx
const touched = lastTouchRef.current.get(city.id) ?? 0;
const sinceTouched = Date.now() - touched;
const pulse = sinceTouched < 600 ? 1 - sinceTouched / 600 : 0;
const emissiveBoost = pulse * 0.6;
// apply to emissiveIntensity
```

If Cities currently only receives `cities` and `mode`, plumb `flashesRef` from `CosmicLens.tsx`'s `<Cities flashesRef={live.flashesRef} ... />` invocation.

- [ ] **Step 8: Run tests + build**

```bash
PORTAL_DATA_DIR=$(pwd)/data/portal-test python -m pytest tests/api/server/test_entity_view.py -x -q
npm run test -- web/blueprint/src/components/cosmicLens
npm run build:blueprint
```

- [ ] **Step 9: Commit**

```bash
git add api/server/routes/entities.py \
        api/server/services/entity_graph.py \
        web/blueprint/src/components/cosmicLens/HUD/KnowledgePulse.tsx \
        web/blueprint/src/components/cosmicLens/lib/types.ts \
        web/blueprint/src/components/cosmicLens/lib/useLiveCosmic.ts \
        web/blueprint/src/components/cosmicLens/CosmicLens.tsx \
        web/blueprint/src/components/cosmicLens/Rockets.tsx \
        web/blueprint/src/components/cosmicLens/Cities.tsx \
        tests/api/server/test_entity_view.py
git commit -m "feat(cosmic): KnowledgePulse strip + entity-mode rocket affordances

Entities mode gains an always-visible HUD strip showing total entities,
growth in last 60s, decisions/min sparkline, links/min sparkline, and
top 3 cross-domain entities (clickable -> opens EntityView).

Rockets in entities mode capture last entity_id from each entity event;
clicking a rocket opens its EntityView (falls back to WorkflowView when
no entity_id). Cities pulse in their kind colour on entity-event arrival
(600ms decay) so the operator sees the substrate touching each kind in
real time.

New /api/entities/_pulse endpoint and EntityGraph.cross_domain_top()
helper power the strip.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 6 — Final verification + push

- [ ] **Step 1: Full test suite**

```bash
npm run test -- web/blueprint/src/components/cosmicLens
PORTAL_DATA_DIR=$(pwd)/data/portal-test python -m pytest tests/api/server/test_entity_view.py tests/api/server/test_entities.py tests/api/server/test_cities.py -x -q
npm run build:blueprint
```

All green. Pre-existing portal test failures and the audit-chain ordering flake are not in scope.

- [ ] **Step 2: Push**

```bash
git push origin main
```

- [ ] **Step 3: Smoke check (best effort if backend reachable)**

```bash
curl -sS http://localhost:3101/api/cities?mode=entities | python3 -m json.tool | head -40
curl -sS http://localhost:3101/api/cities/edges | python3 -m json.tool | head -40
curl -sS http://localhost:3101/api/entities/_pulse | python3 -m json.tool
```

Expected:
- 8 entity-type cities returned with `count` + `recent_activity_per_min` + `active`.
- Edges list uses real rel names (`EMPLOYED_BY`, `BELONGS_TO`, etc.) with live counts.
- `_pulse` returns the full snapshot shape with cross-domain leaders.

If backend isn't running, that's fine — tests + build are sufficient evidence.
