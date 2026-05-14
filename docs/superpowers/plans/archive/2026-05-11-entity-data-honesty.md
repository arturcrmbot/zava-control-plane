# Plan — entity-data honesty

Spec: `docs/superpowers/specs/2026-05-11-entity-data-honesty-design.md`.

## Pre-flight

- Branch: `main` (small surgical fixes; user has authorised direct push).
- Co-author: `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`.
- The graph file at `data/portal/entity_graph.kuzu` was wiped at session
  start, so any schema change applies cleanly on the next FastAPI boot.
- After all tasks ship, restart uvicorn so the new code is live, then
  re-verify against `/api/entities/_pulse` and a sampled decision.

---

## Task A — Fix payload shape across all projections

**Files** (one edit each):

- `api/server/services/entity_projections/ap_invoice.py` — pull
  `inv = p.get("invoice") or {}`, then read `vendor_name`, `po_id`,
  `amount_gbp`, `category`, `currency` from `inv`.
- `api/server/services/entity_projections/vendor_kyc.py` — pull
  `v = p.get("vendor") or {}`, then read `vendor_name`,
  `country_of_incorporation`, `proposing_agency` from `v`.
- `api/server/services/entity_projections/contract_renewal.py` — pull
  `c = p.get("contract") or {}`, then read `contract_id`, `vendor_name`,
  `current_annual_value`, `proposed_annual_value` from `c`.
- `api/server/services/entity_projections/contract_review.py` — pull
  `c = p.get("contract_review") or {}`, then read `contract_id`,
  `vendor_name`, `contract_type`, `amount_gbp`, `deviates_from_template`
  from `c`.
- `api/server/services/entity_projections/treasury_fx.py` — pull
  `op = p.get("treasury_op") or {}`, then read `op_id`, `op_kind`,
  `currency_pair`, `notional_gbp` from `op`.
- `api/server/services/entity_projections/it_access_request.py` — pull
  `r = p.get("request") or {}`, then read `employee_id`, `department`,
  `requested_role_templates`, `business_justification` from `r`.
- `api/server/services/entity_projections/perf_review.py` — pull
  `r = p.get("review") or {}`, then read `employee_id`, `cycle`,
  `prior_rating` from `r`.
- `api/server/services/entity_projections/creative_campaign.py` — pull
  `b = p.get("brief") or {}`, then read `client_brand`, `agency`,
  `category`, `audience`, `channels`, `kpis`, `constraints` from `b`.
- `api/server/services/entity_projections/employee_onboarding.py` — pull
  `j = p.get("joiner") or {}`, then read `employee_id`, `department`,
  `buddy_id`, `start_date` from `j`.
- `api/server/services/entity_projections/purchase_order.py` — pull
  `po = p.get("purchase_order") or {}`, then read `po_id`, `vendor_name`,
  `amount_gbp`, `category`, `supplier_on_approved_list` from `po`.
- `api/server/services/entity_projections/privacy_dpia.py` — pull
  `d = p.get("dpia") or {}`, then read `dpia_id`, `system_name`,
  `risk_tier`, `geography` from `d`.
- `api/server/services/entity_projections/travel_preapproval.py` —
  inspect a live travel-preapproval workflow's payload to confirm the
  nested key (likely `trip` or `travel`); apply the same pattern.

**Compatibility shim:** keep the `or {}` fallback so an old/manual
top-level payload still produces a degraded but non-crashing entity.

**Tests:** existing `tests/api/server/test_entity_projections*.py`
(fixtures may already be top-level; update fixtures to nest the business
object under the right key, since live payloads are nested). The change
is essentially "tests + projections move together".

**Status:** DONE when:
- Sampling a live AP-invoice workflow shows `MONEY-INV-...` with
  non-zero `amount` and a vendor id like `ORG-vendor-globex-industries`.
- All projection-related tests pass.

---

## Task B — Reflector stamps workflow_id

**File:** `api/server/services/entity_reflector.py`

**Change:** in `_on_event`, after resolving `workflow_id` and collecting
`ops`, mutate each `EntityWrite.attrs["workflow_id"] = workflow_id` (the
dict is mutable even though the dataclass is frozen). Do this before
calling `_dispatch_op`, so `EntityGraph.upsert()` reads it back through
`entity.attrs.get("workflow_id")` and emits a fully-formed FleetEvent.

For `entity.read` (emitted from `EntityGraph.read_back` /
`find_by_pattern` etc.), inspect existing call sites — when they're
called from a path with workflow_id in scope, accept an optional kwarg
and thread it through to the FleetEvent. Out of scope: deterministic
executors that read entities without any workflow context (those keep
emitting `workflow_id: null` and we accept that).

**Tests:** add a unit test in `tests/api/server/` that runs a fake
projection through the reflector with a fake bus and asserts the
captured `FleetEvent.workflow_id == "WF-test-001"`.

**Status:** DONE when:
- New unit test passes.
- Live `/api/blueprint/stream` shows `entity.upserted` events with
  populated `workflow_id`.
- Cosmic-lens entities mode shows rockets actually flying to entity
  cities (verified visually after restart).

---

## Task C — Multi-target DECIDED rel tables

**File:** `api/server/services/entity_graph.py`

**Schema change** (`_REL_TABLES`):
- Replace the single `DECIDED_ON (FROM Decision TO Person)` row with six:
  - `DECIDED_PERSON (FROM Decision TO Person)`
  - `DECIDED_MONEY  (FROM Decision TO Money)`
  - `DECIDED_ASSET  (FROM Decision TO Asset)`
  - `DECIDED_ORG    (FROM Decision TO Organisation)`
  - `DECIDED_PERIOD (FROM Decision TO Period)`
  - `DECIDED_PLACE  (FROM Decision TO Place)`

`_VALID_RELS` is auto-derived, so nothing else to wire there.

**`record_decision` change:** for each `did` in `decided_on`, look up its
node kind via a `MATCH (n) WHERE n.id = $id RETURN label(n)` (label-less
match, supported in 0.6.1 per stored memory). Map the kind to the rel
name, and write via `self.link(decision_id, "DECIDED_<KIND>", did)`. If
the lookup returns nothing, log a debug line and skip — do **not** crash.

**`link()` validation:** `_VALID_RELS` already filters; the new rel names
are valid because `_REL_TABLES` lists them. No change needed there.

**`rel_counts()`:** already iterates `_REL_TABLES`, so the new rels show
up automatically with their counts.

**Tests:**
- `tests/api/server/test_entity_graph_decisions.py` (or similar): update
  any existing `DECIDED_ON` assertions to assert the right `DECIDED_<KIND>`
  table received the row instead.
- Add a small new test that runs a Decision with mixed-kind targets
  (Money + Person) and verifies both end up in their respective tables.

**Status:** DONE when:
- All graph tests pass.
- Live `/api/entities/<recent_decision>/linked` returns `[ {rel: "DECIDED_MONEY", entity: {...}} ]` or similar.
- Frontend EntityView Decision drawer renders linked entities (no UI
  change required — it already groups by rel).

---

## Task D — Restart + smoke verify (no commit)

After A, B, C are committed:

1. Stop uvicorn + functions; nuke `data/portal/entity_graph.kuzu` and
   `azurite-data/__azurite_db_*.json` for a fresh slate.
2. `bash scripts/boot-demo.sh` (re-detached) and wait ~90s.
3. Verify:
   - `/api/entities/_pulse` shows `cross_domain_top` with real vendor
     names instead of `ORG-vendor-unknown` dominating.
   - `/api/entities?kind=Money&limit=5` shows non-zero `amount`.
   - `/api/entities?kind=Decision&limit=1` then
     `/api/entities/<id>/linked` returns ≥1 entry.
   - `/api/blueprint/stream` `entity.upserted` events carry workflow_id.
4. Eyeball the cosmic lens at `?view=entities` — rockets visible flying
   to entity cities.
5. Tell the user it's done with the URL.

---

## Task ordering and dependencies

A, B, C are independent and can land in any order, but doing them in
this order means each fix is verifiable on its own:

- After A only: real vendor names + non-zero money, but rockets still
  invisible and decisions still empty.
- After B: rockets fly. Decisions still empty.
- After C: decisions populate with linked entities.

Do A → B → C → D, one commit per task.

---

## Notes on Kuzu 0.6.1 quirks (already proven)

- `SET n += $map` not supported — emit one `n.\`key\` = $param` per attr.
- `id STRING PRIMARY KEY` inline rejected — use trailing `PRIMARY KEY (id)`.
- Multi-pair `REL TABLE` not supported (proven this session) — one rel
  table per target kind.
- `LIMIT $n` parameter substitution not supported — inline as integer.
- Label-less `MATCH ({id: $id})` works in 0.6.1.
- Use `label(r)` not `type(r)` for rel type names.
