# Autonomous Domain Insights — Design Spec

**Status:** Approved · ready for implementation plan
**Date:** 2026-05-12
**Predecessor:** `docs/plans/archive/2026-05-12-entity-graph-coherence.md` (the data plane this spec sits on)
**Implementation slice (v1.0):** §1–§7 + §10–§13 only — the closed-loop SYSTEM with no hardcoded persona behaviour. §8 (Aurora demo scenario) is deferred to v1.1 alongside the rest of §9 polish; the initial plan ships a working CEO synthesis persona + a test-fixture persona that exercises the runtime, then real per-domain `summary_policy` blocks (CFO, HR-head, etc.) land as separate plans built on top.

---

## 1. Vision

Today the substrate has 14 autonomous domains (workflow types) running on a Kuzu entity graph rich enough to tell their story. Personas (`api/server/personae/<role>/SKILL.md`) already serve as autonomous gate-deciders. What's missing is **the loop where a persona observes the live state of its domain, proposes a policy, gets HITL approval, and watches that policy reach forward into in-flight work**.

This spec adds exactly that loop, with one new node kind (`Insight`) and three small wires on the existing persona runtime. Everything else composes pieces already in the substrate: persona registry, persona_responder, AGT governance kernel, entity graph, Decision-as-policy semantics, Fleet Manager queue, WorkflowDrawer.

### What a customer sees in 5 minutes

| Act | Time | What happens | What the customer thinks |
|---|---|---|---|
| **1. Calm** | 0:00–1:00 | Constellation alive. Personas show healthy KPIs. CEO planet pulses softly. | "OK it runs. So what?" |
| **2. Trigger** | 1:00–3:30 | Anomaly drops in (Aurora budget overrun). CFO notices on the next refresh tick (~15s). CFO writes a fresh Insight: *"Aurora at 87% of FY budget; I propose a 14-day freeze on POs over £1k."* User clicks **Approve**. | "A non-human just diagnosed and proposed a fix." |
| **3. Reach** | 3:30–4:30 | Within 10s the freeze ripples through in-flight workflows. Aurora ap-invoices visibly auto-escalate to CFO. | "The decision **reached forward** into work that was already running." |
| **4. CEO synthesis** | 4:30–5:00 | Click CEO planet. One paragraph: *"Finance in good shape this quarter despite Aurora overrun — mitigated by CFO's 14-day freeze (47s ago). 4 invoices auto-escalated; ~£18k deferred. HR on track. Creative delivering."* | "The org just told me how it's doing, citing a decision a non-human made 47s ago." |

Act 3 is the prestige moment: **autonomous decisions modify in-flight autonomous work**. That's the inversion the customer doesn't have today.

---

## 2. Architecture

```
                   ┌─────────────────────────────────────────────────┐
                   │       kuzu entity graph (existing)              │
                   │  Money, Account, Brand, Decision, Workflow, ... │
                   └────────────────────┬────────────────────────────┘
                                        │ reads
                  ┌─────────────────────┴───────────────────────┐
                  │                                             │
          ┌───────▼───────┐      ┌───────────────┐      ┌───────▼───────┐
          │ CFO persona   │      │ HR-head pers. │ ...  │ Creative head │
          │ summary_policy│      │ (later)       │      │ (later)       │
          └───────┬───────┘      └───────────────┘      └───────────────┘
                  │ writes Insight on change (skips no-op)
          ┌───────▼─────────────────────────────────────────────────┐
          │   Insight nodes in kuzu                                 │
          │   {role, scope, decided_at, headline, body, kpis,       │
          │    proposed_actions, fingerprint}                       │
          └───────┬─────────────────────────────────────────────────┘
                  │ reads
          ┌───────▼───────┐                          ┌───────────────┐
          │ CEO persona   │  writes meta-Insight ──> │  same table   │
          │  (new SKILL)  │                          └───────────────┘
          └───────────────┘                                  ▲
                                                             │ HTTP read
          ┌──────────────────────────────────────────────────┴────────┐
          │  UI: opens persona-related entity in WorkflowDrawer →     │
          │      fetches /api/personas/{role}/insights/latest →       │
          │      renders headline / body / kpis / Approve button      │
          │  Approve → POST → spawns one-shot policy_set workflow →   │
          │      AGT kernel gates → on completion records a Decision  │
          │      with phase="policy_set", verdict="freeze", etc.      │
          │  All future personas' decision_policy blocks check the    │
          │  graph for active policy_set Decisions in their scope     │
          │  (helper: active_policies_for(graph, scope_kind, id)).    │
          └───────────────────────────────────────────────────────────┘
```

**No new abstractions.** Composition of: entity graph, persona registry, persona_responder runtime, AGT governance kernel, Decision-as-Policy semantics, existing one-shot workflow spawn path, existing WorkflowDrawer.

---

## 3. Schema additions

### 3.1 `Insight` node kind (the only new kind)

```python
# api/server/services/entity_graph.py — append to _NODE_TABLES
(
    "Insight",
    """
    CREATE NODE TABLE IF NOT EXISTS Insight (
        id STRING,
        role STRING,
        scope STRING,
        decided_at TIMESTAMP,
        headline STRING,
        body STRING,
        kpis STRING,
        proposed_actions STRING,
        fingerprint STRING,
        source_workflows STRING[],
        attributes STRING,
        PRIMARY KEY (id)
    )
    """,
),
```

| Column | Purpose |
|---|---|
| `id` | e.g. `INSIGHT-cfo-2026-05-12T17:30:00Z` |
| `role` | The persona that produced it (queryable: latest by role) |
| `scope` | The domain `function` (`finance`, `hr`, `it`, ...) — for CEO grouping |
| `decided_at` | Phase 4.2 standard sortable timestamp |
| `headline` | One-line summary for tile |
| `body` | Longer narrative paragraph |
| `kpis` | JSON dict: `{"budget_used_pct": 0.87, "escalations_this_week": 4}` |
| `proposed_actions` | JSON list: `[{"label": "...", "kind": "policy_set", "verdict": "freeze", "decided_on": [...], "attributes": {...}}]` |
| `fingerprint` | SHA-1 of the underlying graph state the persona considered. Persona compares newly-computed fingerprint with last Insight's fingerprint; matches = skip write. |
| `source_workflows`, `attributes` | Standard substrate provenance |

Plus the standard side-effects of adding a kind, established in Phases 2-3: extend `_TIMESTAMP_KINDS`, the route-side `_KINDS` tuple, `_PROJECT_FIELDS_BY_KIND`, and the schema-test fixtures (`tests/api/server/services/test_entity_graph_schema.py`).

### 3.2 No new rels for v1

The Insight has neither inbound nor outbound rels. Persona attribution is via the `role` attribute. If a future surface wants `Insight -[:CITES]-> Decision` (provenance pointer), that's a v2 addendum.

---

## 4. Closed-loop mechanism (Decisions-as-Policy)

The pattern is: **a persona-proposed action that gets HITL-approved becomes a Decision node with `phase="policy_set"`. Other personas' `decision_policy` blocks query for active policy Decisions and honour them.**

### 4.1 Why overload Decision instead of adding a `Policy` kind

- Decision already has every column we need: `verdict` (the action — `freeze`, `unfreeze`, `cap`, `defer`), `decided_on` (the targets), `decided_at` (Phase 4.2 timestamp for expiry math), typed columns (Phase 4.3 — `amount_gbp` etc), `attributes` JSON (rule body — `expiry_days`, `scope`, etc), `persona_role` (who set it).
- Phase 4.1 already widened the verdict vocabulary; adding `freeze`/`unfreeze` is a one-line `_ALIASES` extension to `decision_vocab.py`.
- Semantically a "policy" *is* a CFO's decision — separating them would conflate naming, not behaviour.
- Avoids a new kind + new schema migration that the user explicitly asked us not to add.

### 4.2 Lookup helper

A single new file `api/server/services/policy_lookup.py`:

```python
"""Active-policy lookup for persona decision_policy blocks.

A 'policy' here is a Decision with phase='policy_set' that has not yet
expired (decided_at + attributes.expiry_days >= now()). Personas call this
helper at gate-time to discover policies that should constrain the
current decision.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from api.server.services.entity_graph import EntityGraph


def active_policies_for(
    graph: EntityGraph,
    *,
    scope_kind: str,  # e.g. "Brand", "Money", "Organisation"
    scope_id: str,    # e.g. "BRAND-aurora"
    verdict: str | None = None,  # filter to a specific verdict if given
) -> list[dict[str, Any]]:
    """Return active policy_set Decisions whose decided_on includes scope_id."""
    decided_rel = {
        "Brand": "DECIDED_BRAND",
        "Money": "DECIDED_MONEY",
        "Organisation": "DECIDED_ORG",
        "Person": "DECIDED_PERSON",
        "Period": "DECIDED_PERIOD",
        "Place": "DECIDED_PLACE",
        "Asset": "DECIDED_ASSET",
        "Subsidiary": "DECIDED_SUBSIDIARY",
        "Campaign": "DECIDED_CAMPAIGN",
        "Pitch": "DECIDED_PITCH",
        "MediaPlan": "DECIDED_MEDIAPLAN",
    }.get(scope_kind)
    if decided_rel is None:
        return []

    cypher = f"""
    MATCH (d:Decision {{phase: 'policy_set'}})-[:{decided_rel}]->(t:{scope_kind} {{id: $id}})
    RETURN d.id AS id, d.verdict AS verdict, d.decided_at AS decided_at,
           d.persona_role AS persona_role, d.reason AS reason,
           d.attributes AS attributes
    """
    rows = graph.query(cypher, {"id": scope_id})
    now = datetime.utcnow()
    out: list[dict[str, Any]] = []
    for r in rows:
        if verdict is not None and r["verdict"] != verdict:
            continue
        attrs = {}
        try:
            attrs = json.loads(r["attributes"] or "{}")
        except Exception:
            pass
        expiry_days = attrs.get("expiry_days")
        decided_at = r["decided_at"]
        if expiry_days is not None and isinstance(decided_at, datetime):
            if decided_at + timedelta(days=int(expiry_days)) < now:
                continue  # expired
        out.append({
            "id": r["id"],
            "verdict": r["verdict"],
            "decided_at": decided_at,
            "persona_role": r["persona_role"],
            "reason": r["reason"],
            "attributes": attrs,
        })
    return out
```

### 4.3 Worked example — Aurora freeze

```
T+0    CFO summary_policy reads graph
       → headline: "Aurora at 87% of FY budget; trajectory flat-lining the line"
       → kpis: {"aurora_budget_used_pct": 0.87, ...}
       → proposed_actions: [{
              label: "Freeze Aurora POs for 14d",
              kind: "policy_set",
              verdict: "freeze",
              decided_on: ["BRAND-aurora"],
              attributes: {expiry_days: 14, scope: "po"},
              reason: "Budget overrun risk; revisit at FY26 Q3 review"
         }]
       → fingerprint = sha1("aurora=87,esc=4,...")
       → previous Insight fingerprint = sha1("aurora=84,esc=3,...")
       → different → write new Insight node

T+1    User clicks Approve in WorkflowDrawer
       → POST /api/personas/cfo/actions/{action_id}/approve
       → Spawns one-shot policy_set workflow (existing substrate primitive)
       → On completion: graph.record_decision(
             phase="policy_set", verdict="freeze",
             decided_on=("BRAND-aurora",),
             attributes={"expiry_days": 14, "scope": "po"},
             persona_role="cfo", source_event="persona.action.approved")
       → Decision node lands; AGT hash-chains the audit row

T+2    A new ap-invoice gates on `ap_clerk_signoff`. ap_clerk's
       decision_policy now contains:
           policies = active_policies_for(
               graph, scope_kind="Brand",
               scope_id=context.get("brand_id"), verdict="freeze")
           if policies:
               decision = "escalate"
               reason = f"Frozen by {policies[0]['persona_role']}: {policies[0]['reason']}"
       → Auto-escalates. The clerk's autonomy is *bounded* by the CFO's policy.

T+15s  CFO summary_policy runs again
       → Reads graph: spend stable; new escalations count = 4 (was 0)
       → kpis: {"aurora_budget_used_pct": 0.87, "escalations_this_week": 4}
       → fingerprint changed → new Insight written
       → headline: "Aurora freeze active 47s; 4 POs auto-escalated"
       → The decision the CFO took is now feeding back as observable state.
```

### 4.4 Risks + v1 limits

- **Decision_policy adds one Cypher per gate.** Sub-millisecond on Kuzu's embedded driver in tests; benchmark before Section 5 cadence drops below 30s.
- **Policy conflicts** — latest `decided_at` wins; expired policies silently ignored. No conflict-detection in v1; documented as a v2 candidate.
- **Persona could over-throttle itself** — if CFO's freezes cause queue floods, no auto-mitigation. Fleet Manager could surface this in CEO synthesis (out of scope).
- **The Phase 4 known gap still applies** — `pack._write_decisions` hardcodes `verdict="approve"`. The v1 demo scenario MUST avoid relying on the seed naturally producing `escalate`/`defer`. The Aurora scenario uses live workflow runs (which DO go through projections), not seeded decisions.

---

## 5. Persona runtime extension

**Three small wires on `api/server/services/persona_responder.py`. Zero new classes.**

### 5.1 Graph access

When compiling a SKILL.md `decision_policy` or `summary_policy` block, inject `graph` into the execution context (alongside the existing `context`, `authority_check`, etc.). Persona authors can now do:

```python
graph.query("MATCH (m:Money)-[:COSTED_TO_BRAND]->(b:Brand {id: $id}) RETURN sum(m.amount) AS total", {"id": brand_id})
```

Implementation: a one-line addition to `_load_personae()` exec-namespace setup.

### 5.2 Optional `summary_policy` block

Same shape as `decision_policy` but with a different return contract:

```yaml
summary_policy: |
    # Read graph, decide if anything changed, return Insight payload or None.
    # ... user code ...
    summary = {
        "headline": "...",
        "body": "...",
        "kpis": {...},
        "proposed_actions": [...],
        "fingerprint": "...",
    }
```

`PersonaDefinition` gets one optional field: `summarise: PersonaHandler | None`.

### 5.3 New wake reason

`domain.summary.requested` (alongside the existing `workflow.hitl.requested`). Payload: `{role: "cfo"}`. The responder:

1. Looks up persona by role; if `summarise is None`, no-op.
2. Reads the latest Insight for this role (via `graph.query`).
3. Calls `persona.summarise({"last_insight": last_insight})`.
4. If the returned `fingerprint` matches the last Insight's, skip.
5. Otherwise, write a new Insight node via `graph.upsert(EntityWrite(kind="Insight", ...))`.

---

## 6. Cadence

A boot-time async task in `api.server.state.AppState.attach()` (where the entity graph + bus already wire up):

```python
async def _insight_loop(self) -> None:
    interval = float(os.getenv("INSIGHT_REFRESH_SECONDS", "300"))
    while True:
        try:
            for persona in persona_responder.personae_with_summary_policy():
                await self.bus.publish(FleetEvent(
                    type="domain.summary.requested",
                    payload={"role": persona.role},
                ))
        except Exception:
            log.exception("insight loop tick failed")
        await asyncio.sleep(interval)
```

Spawned via `asyncio.create_task(self._insight_loop())` after the entity graph is initialised. Demo profile sets `INSIGHT_REFRESH_SECONDS=15`. No new scheduler primitive — same `asyncio.create_task` pattern other loops in the substrate use.

---

## 7. HTTP routes

New file `api/server/routes/insights.py`:

```
GET  /api/personas/{role}/insights/latest
GET  /api/personas/insights/latest
POST /api/personas/{role}/actions/{action_id}/approve
```

Mounted via the existing tuple loop in `api/server/main.py` (the convention established in Task 2.5). Auth via the existing `read_route_auth.require_actor` dependency.

### 7.1 `GET /api/personas/{role}/insights/latest`

```cypher
MATCH (i:Insight {role: $role}) RETURN i ORDER BY i.decided_at DESC LIMIT 1
```

Returns 404 if no Insight exists yet.

### 7.2 `GET /api/personas/insights/latest`

For CEO synthesis. Returns one Insight per role (the latest of each).

```cypher
MATCH (i:Insight)
WITH i.role AS role, max(i.decided_at) AS latest
MATCH (i2:Insight {role: role}) WHERE i2.decided_at = latest
RETURN i2
```

(Two-step Kuzu pattern; the substrate has precedent for this in `entities.py`.)

### 7.3 `POST /api/personas/{role}/actions/{action_id}/approve`

`action_id` matches one of the `proposed_actions` in the role's latest Insight. The handler:

1. Re-reads the latest Insight for the role.
2. Finds the action by id.
3. Spawns a one-shot `policy_set` workflow (see §8.2) with the action's payload.
4. Returns 202 Accepted with the spawned workflow id.

The workflow's projection (see §8.2) records the policy Decision on completion. The AGT kernel mediates as it does for any workflow start.

---

## 8. Demo scenario for v1 — Aurora overrun

### 8.1 Trigger route

`POST /api/demo/trigger/aurora-overrun` — visible-but-unannounced demo entrypoint (no UI button in v1; operator hits it via curl during the demo). Implementation:

1. Pick `BRAND-aurora` (or whichever brand has the highest current spend; favours determinism).
2. Read its `annual_budget_gbp` from the Brand node.
3. Read its current spent total via `MATCH (m:Money)-[:COSTED_TO_BRAND]->(b:Brand {id: 'BRAND-aurora'}) RETURN sum(m.amount)`.
4. Compute the gap to push it above 85% of budget.
5. Insert ~5 fresh `Money` rows (kind=`po`) summing that gap. Each row gets `BOOKED_AGAINST` ACC-6010, `COSTED_TO_BRAND` aurora, `BELONGS_TO` the current Period.
6. Return `{brand_id, before_pct, after_pct, money_ids}`.

### 8.2 The `policy_set` workflow

A new generic one-shot workflow type registered in `api/shared/domains.py`, with a projection that records the policy Decision:

```python
# api/server/services/entity_projections/policy_set.py — new
def project(workflow: Workflow) -> list[EntityWrite | RelWrite | DecisionWrite]:
    p = workflow.payload or {}
    return [build_decision(
        workflow,
        gate_phase="policy_set",
        persona_role=p.get("persona_role", ""),
        source_event="persona.action.approved",
        decided_on=tuple(p.get("decided_on", [])),
        attributes=p.get("attributes", {}),
        verdict_override=p.get("verdict"),  # the Phase 4.1 hook
    )]
```

The Task 3.3 wiring will pick this projection up automatically (DataPack runs projections through the bus for one-shot types).

### 8.3 CFO `summary_policy` (the new SKILL.md block)

Adds a `summary_policy` block to `api/server/personae/cfo/SKILL.md`. The block:

1. For each Brand, computes `(spend_total / annual_budget_gbp)`.
2. Identifies any brand above 85% threshold.
3. If any over-threshold brand exists AND the freeze isn't already active (`active_policies_for(...)` returns empty), proposes a `freeze` policy.
4. Otherwise emits a calm Insight ("All brands within budget").
5. Returns the structured payload with fingerprint = sha1 of the kpis dict (excluding rendered prose, which can vary).

### 8.4 ap_clerk `decision_policy` extension

Adds a one-block extension to `api/server/personae/ap_clerk/SKILL.md`:

```python
# Phase 5: honour active policy_set Decisions in scope.
brand_id = (context or {}).get("brand_id")
if brand_id:
    freeze_policies = active_policies_for(
        graph, scope_kind="Brand", scope_id=brand_id, verdict="freeze")
    if freeze_policies:
        decision = "escalate"
        reason = f"Frozen by {freeze_policies[0]['persona_role']}: {freeze_policies[0]['reason']}"
        # ... emit decision and exit early ...
```

`controller_signoff` SKILL.md gets the same block (so the escalation chain doesn't auto-approve at the next level).

### 8.5 Demo runbook (operator card)

```
1. Open http://localhost:5275/?view=constellation in browser.
2. Click the Finance planet → WorkflowDrawer opens with CFO Insight.
   Verify headline: "All brands within budget" (or similar calm copy).
3. In another terminal:
       curl -X POST http://localhost:3101/api/demo/trigger/aurora-overrun
4. Wait ~15s (one INSIGHT_REFRESH_SECONDS tick in demo mode).
5. Click Finance planet again → CFO Insight has changed:
       headline: "Aurora at 87% of FY budget; recommend freeze"
       proposed_actions: [{label: "Freeze Aurora POs for 14d", ...}]
6. Click Approve. Backend spawns policy_set workflow; Decision lands.
7. Watch in-flight ap-invoice workflows touching Aurora auto-escalate
   (visible via the existing /api/entities?kind=Workflow + status filter,
   or via the constellation if it surfaces gate state).
8. Wait another ~15s tick. Click Finance planet:
       headline: "Aurora freeze active 1m; 4 POs auto-escalated"
9. Click CEO planet (after CEO persona's summary_policy lands):
       paragraph synthesising state across all domains, citing the
       Aurora event.
```

---

## 9. Future polish (v2+ — addendum, not v1 scope)

These were considered and explicitly deferred. Each can ship as an independent follow-up plan once v1 proves the pattern works.

| ID | Addition | Buyer impact | Cost | Notes |
|---|---|---|---|---|
| **a** | **Persona voice templates** — each SKILL.md gets a `voice` field; `summary_policy` returns structured data, a small renderer (or per-persona Jinja template) interpolates kpis into first-person prose with personality. CFO sounds like a CFO ("I've been watching Aurora since Q2..."), not a robot. | Massive — humanises autonomy | S | Optional GHCP SDK call for free-form variant. |
| **b** | **Demo trigger panel** — hidden `/demo` page with pre-baked scenarios. Each: Aurora overrun, ransomware, vendor-KYC failure, FX exposure. Each creates a believable burst of workflows that personas react to. | Massive — gives every demo its arc | M | Each scenario is one route + one trigger function. |
| **c** | **Live decision ticker** — bottom strip of the constellation, chronological feed: "ap_clerk approved INV-7841 for £1,240 (3s)" / "CFO proposed Aurora freeze (8s — pending)". Reads like Twitter. | Massive — proves the org is *alive* not staged | S | New SSE route; new HUD component. |
| **d** | **Policy-ripple animation** — when a policy_set Decision lands, the constellation animates a coloured wave that touches every affected node. The viewer SEES the policy reach. | Big — visceral "wow" | M | New animation in cosmicLens; needs the entity-bus event surfacing in the websocket already used by the constellation. |
| **e** | **Per-persona hue** — each persona gets a distinct colour. When a workflow gate is decided, the workflow particle briefly tints that colour. Buyer accumulates "agents are doing the work" without being told. | Medium | S | Colour palette in the persona registry. |
| **f** | **Time warp for personas** — the substrate already has `DEMO_TIME_WARP_FACTOR` for workflow spawn cadence. Apply the same factor to `INSIGHT_REFRESH_SECONDS` so persona refresh accelerates in demo mode. | Required for spectacular demos | XS | One env var read. |
| **g** | **Plain-language UI strings** — never show "Decision phase=policy_set verdict=freeze". Show "CFO Policy: Freeze Aurora POs (14 days)". A tiny i18n-ish layer. | Required for buyer-comprehensible UI | S | Audit pass on every new string in v1. |
| **h** | **Multi-persona quorums** — a proposed action can require N persona approvals before landing. e.g. crisis-response policy needs CMO + CFO. AGT kernel already has authority-band semantics; quorum is a thin layer. | Big in regulated industries | M | New `required_approvers` field on proposed_actions. |
| **i** | **Policy-conflict detector** — if two personas propose conflicting policies (CFO freezes, CMO unfreezes), Fleet Manager wakes a "policy conflict" exception that escalates to a human. | Big — closes the trust gap on multi-persona orgs | M | Detection logic in the cadence loop. |
| **j** | **Insight-citation graph** — `Insight -[:CITES]-> Decision` rels so a buyer can click a CFO insight and see the exact Decisions that drove the headline. Graph-native explainability. | Medium — sophisticated buyers love it | S | New rel + a small drawer panel. |
| **k** | **More frictional workflow types** — beyond the existing 14, add: vendor-risk-demotion, hiring approval (multi-CFO+HR-head), brand-pull-request, FX-hedge-quorum. Each gives the demo more interesting cause-and-effect surface. | Big — proves the pattern generalises | M-L | One per addition; reuses compose-domain. |

The polish items are independently valuable. A reasonable v2 plan picks (a) + (b) + (c) for the most demo-impact-per-day; v3 picks (d) + (e) + (f) for visceral polish; v4 picks (h) + (i) for trust/regulated sales.

---

## 10. Files

### Created
- `api/server/services/policy_lookup.py`
- `api/server/routes/insights.py`
- `api/server/routes/demo_triggers.py` (just the Aurora trigger for v1)
- `api/server/services/entity_projections/policy_set.py`
- `api/server/personae/ceo/SKILL.md` (new persona; CEO synthesis)
- `tests/api/server/services/test_policy_lookup.py`
- `tests/api/server/services/test_persona_summary_runtime.py`
- `tests/api/server/routes/test_insights.py`
- `tests/api/server/routes/test_demo_triggers.py`
- `tests/api/server/services/entity_projections/test_policy_set_projection.py`

### Modified
- `api/server/services/entity_graph.py` — add `Insight` to `_NODE_TABLES`, `_TIMESTAMP_KINDS`; extend `decision_vocab.VERDICTS` with `freeze`/`unfreeze`/`cap` (plus aliases).
- `api/server/services/persona_responder.py` — inject `graph` into exec namespace; load `summary_policy` block; handle `domain.summary.requested` events.
- `api/server/state.py` — `_insight_loop()` task spawned in `attach()`.
- `api/server/main.py` — mount `insights_router`, `demo_triggers_router`.
- `api/server/routes/entities.py` — extend `_KINDS` and `_PROJECT_FIELDS_BY_KIND` for `Insight`.
- `api/server/personae/cfo/SKILL.md` — add `summary_policy` block (Aurora-aware).
- `api/server/personae/ap_clerk/SKILL.md` — extend `decision_policy` to honour active policies.
- `api/server/personae/controller/SKILL.md` — same extension.
- `api/shared/domains.py` — register `policy_set` workflow type.
- `tests/api/server/services/test_entity_graph_schema.py` — add `Insight` to expected tables.
- `tests/api/server/routes/test_entities_kinds.py` / `test_entities_stats.py` — add `Insight` to expected kinds.
- `web/blueprint/src/components/cosmicLens/HUD/WorkflowDrawer.tsx` — fetch + render persona insight when a persona-related entity is open.

### Deleted
None.

---

## 11. Testing strategy

- **Unit:** `policy_lookup.active_policies_for` against a tmp_path graph (active policy / expired policy / no policy / wrong scope).
- **Schema:** `test_entity_graph_schema.test_show_tables_lists_exact_expected_tables` covers the new `Insight` table.
- **Persona runtime:** `test_persona_summary_runtime` writes a fake persona with a `summary_policy` block, fires a `domain.summary.requested` event, asserts an Insight node lands; second fire with same fingerprint asserts NO new Insight is written.
- **Closed loop integration:** seed a Money + Brand setup, run CFO `summary_policy`, assert it proposes a freeze; record the policy Decision; run ap_clerk's `decision_policy` against a mock workflow; assert it auto-escalates.
- **HTTP:** `test_insights` covers the three new routes with a `client_with_seed`-style fixture (modelled on Task 2.5's `_accounts_fixtures.py`).
- **Demo trigger:** `test_demo_triggers` asserts `POST /api/demo/trigger/aurora-overrun` raises Aurora's spend above 85% and returns the right shape.
- **End-to-end (manual, demo runbook §8.5):** the operator runbook IS the acceptance test.

---

## 12. Risks + assumptions

### Risks

- **R1 — Latency.** Every gate now runs an extra Cypher (`active_policies_for`). Sub-millisecond expected on Kuzu's embedded driver, but a busy gate (multiple simultaneous workflows hitting `ap_clerk_signoff`) could compound. **Mitigation:** if the Section 6 cadence loop ever drops below 30s in production, add a 2s in-memory policy cache in `app_state`, invalidated on `Decision` write events from the entity-bus.
- **R2 — Insight-loop infinite refresh.** A persona with a non-deterministic `summary_policy` (e.g. one that uses `now()` in its fingerprint computation) writes a new Insight every tick even when nothing changed. **Mitigation:** documented contract + linting rule that `fingerprint` MUST be deterministic over the persona's scope inputs. Reviewed at SKILL.md merge time.
- **R3 — Policy conflicts.** Two personas could propose conflicting policies. v1 resolves by latest-decided_at-wins; this could surprise buyers who expect explicit conflict surfacing. **Mitigation:** documented as a known v1 limit; addressed in v2 polish item (i).
- **R4 — The Phase 4 known seed gap** (verdict hardcoded to `approve` in `pack._write_decisions`) means the demo CANNOT rely on seeded `escalate`/`defer` shapes. **Mitigation:** the v1 demo scenario uses the Aurora trigger route (live workflow runs go through projections, not the bulk seed path).
- **R5 — `freeze`/`unfreeze` verdicts not yet in Phase 4.1's vocabulary.** **Mitigation:** Section 3 explicitly extends `decision_vocab.VERDICTS` and `_ALIASES`. Backward-compatible (additive).

### Assumptions

- **A1** — A persona with no `summary_policy` block is a no-op for the cadence loop. The existing personae stay unchanged.
- **A2** — The existing one-shot workflow spawn path (`/api/workflows`-equivalent OR direct durable functions invocation) accepts arbitrary payloads. The `policy_set` workflow type is registered alongside the existing 14 in `api/shared/domains.py`.
- **A3** — `graph.upsert` for the `Insight` kind needs no special handling beyond the standard pattern (Task 2.1 added `Account`/`CostCentre` the same way).
- **A4** — The CEO persona's `summary_policy` reads OTHER personas' Insights, not the raw graph. This means CEO insights are downstream of all persona insights — the cadence order matters (CEO must run after the others). v1 implementation: CEO refresh runs in the SAME tick but via a tiny ordering hack — fire `domain.summary.requested` for non-CEO personas first, await, then fire for CEO.

---

## 13. Out of scope (v1)

- The polish items in §9 (a-k).
- More than one demo scenario (Aurora only).
- Constellation-level policy-ripple visuals.
- Multi-persona quorum on action approval.
- Any persona other than CFO writing meaningful policies (others get a `summary_policy` stub returning calm copy).
- Mutating the AGT kernel's policy set directly (we go via Decision nodes; AGT gates the workflow that records them).
- Authentication beyond the existing `read_route_auth`.
- Rate-limiting on the demo trigger route (it's hidden, single-operator use).
