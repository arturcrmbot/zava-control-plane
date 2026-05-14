# Zava Living Simulator — Tiny digital twin of an agency

> **Status:** Locked v2 — scope refined by user 2026-05-11  
> **Goal:** Build a **small but absolutely real** Zava agency simulator: an autonomous control plane you can spin up, leave running for hours, and come back to find that things have actually happened — workflows interfering with each other through shared entities, precedents accumulating, the org observably learning and optimising itself.  
> **Owner:** TBD

## 0. What we are actually building (the philosophy)

This is **not** about scale, throughput, or impressing with volume. It's about proving **end-to-end agentic automation across all 14+ domains simultaneously**, with the substrate as the shared protagonist.

Three properties have to be **felt**, not just claimed:

### Property 1 — Concurrency across domains
At any moment, **the same Person, Vendor, Brand or Period is being touched by multiple workflows in parallel**. A vendor's KYC status, a person's availability, a brand's budget, a quarter's accruals are not isolated — they are the connective tissue. The cosmic lens has to make this visible: you should literally see two rockets land on the same city in the same second.

### Property 2 — Feedback loops & emergent learning
Decisions in one domain become precedents in another. KPI movements wake ambient agents. Persona behaviour adjusts to history. Over an hour of wall-clock time, the system should observably **get better at itself**:

- Repeat-classifier accuracy improves as the precedent cache fills.
- Escalation rate drops as personae learn each other's preferences.
- Average decision latency for high-volume domains shrinks.
- New patterns emerge: e.g. a vendor that fails KYC twice gets auto-blocked on the third invoice without human review.

### Property 3 — Long-running observability
You start it on Monday morning, walk away, come back at lunch, and the system has a story to tell:

- "12 vendors flagged, 3 escalated to GC; the GC's queue depth peaked at 8 and is back down to 1."
- "Aisha's bonus-cycle decisions show a 30% faster-than-average closure time today; her workload is 1.5× the team mean — flagged."
- "Brand X's campaign Y went over budget by £4,200 at 11:42; the budget-variance ambient agent caught it and spawned an exception-claim workflow."
- "Sub-workflow chain depth reached 4 (account-onboarding → MSA → DPIA → onboarding-it-access)."

**Tiny doesn't mean toy.** A 100-person Zava with this property set is more impressive than a 100k-person Unilever fake.

## 1. Locked decisions (2026-05-11)

| # | Question | Decision | Implication |
|---|---|---|---|
| 1 | Vertical priority | **Agency/Holdings only** (Zava is a small but real creative agency holding) | One pack, deep |
| 2 | Multi-tenant vs fork-per-pack | **One pack per fork/branch** | No multi-tenant primitive needed |
| 3 | Fixture format | **Programmatic-only + Kuzu snapshot files** | Generated, not hand-edited |
| 4 | Mock framework | **Hand-crafted** | Each new system mock is its own ~200-line TS file |
| 5 | Persona DSL | **Keep YAML + `exec()`/`eval()`** | PoC-acceptable security debt; documented |
| 6 | Branding | **Zava** (no real customer branding) | All naming stays "Zava" |
| 7 | **Demo scale** | **Tiny-but-absolutely-real** (~100 employees, ~50 vendors, ~10 brands, ~5 subsidiaries, ~25 in-flight workflows, ~3,000 entities, ~10,000 edges) | Cosmic lens stays smooth on a laptop |
| 8 | **Demo philosophy** | **Living simulator** — emphasise concurrency, feedback loops, longitudinal observability over volume | Pass criteria measured in **emergent behaviour**, not entity counts |

### Hard caps (laptop-safe, demo-rich)

| Entity | Cap | Notes |
|---|---:|---|
| Employees (Person) | **~100** | Every one named, photographed, in an org chart, with a personality knob |
| Vendors / freelancers (Org) | **~50** | Named — production houses, freelancers, software, ad-tech, research, talent |
| Subsidiaries (Org) | **~5** | "Zava Creative", "Zava Media", "Zava Production", "Zava Data", "Zava Group" |
| Holding clients (Org) | **~6** | Top 6 holding-level clients |
| Brands (new entity kind) | **~10** | 1–3 brands per holding client |
| Campaigns / Pitches / MediaPlans | **~30 / ~15 / ~10** | Mix of in-flight, recent-won, recent-lost |
| Periods | **~10** | 4 quarters + 1 fiscal year + 5 campaign windows |
| Places | **~15** | Offices (London, NY, Singapore, …) + key media markets |
| Money rows | **~500–1,000** | Last quarter, 80/20 distribution |
| Decisions (historical) | **~300–500** | Rich enough for precedent search to actually find precedent |
| Workflows in flight (concurrent) | **~25** | Hard visual cap on rockets |
| Workflows historical (24h replay) | **~100–150** | Plenty of audit trail |
| **Total entities** | **~1,500–3,000** | Comfortable for both Kuzu and the cosmic lens |
| **Total edges** | **~5,000–10,000** | Same |

---

## 2. Problem statement

Today the substrate is **proof-of-concept scale**. The architecture is right (events → projections → entity graph + per-function FMs + 33 personae + 44 MCP tools) and demos a real autonomous-org loop, but three properties needed for the "living simulator" pitch are missing:

| Property | Today | Needed |
|---|---|---|
| **Concurrency across domains** | Domains run in parallel but rarely touch the **same** entity. Vendor KYC happens in isolation from AP invoice. | Shared-entity workflows: KYC outcome gates invoices; brand budget gates campaign spend; persona availability gates approvals across domains |
| **Feedback / learning loops** | Precedents are stored but seldom influence new decisions. Ambient agents fire on simple KPI thresholds; they don't get smarter. | Precedent-influenced persona policy; KPI-trend (not just snapshot) triggers; exception classifier with online learning; auto-routing improvements |
| **Longitudinal observability** | KPIs are point-in-time; the cosmic lens shows "now". No way to see "the last hour" or "yesterday vs today". | KPI history series; persona load over time; decision-latency trends; "leave it 4h and see" replay UI |
| Domains (live) | 14 (5 stub) | All 19 live, plus 7 cross-domain meta-workflows |
| Personae | 33 | ~80 with realistic delegation depth |
| Entity-kind types | 8 | 13 (add Brand, Campaign, Pitch, MediaPlan, Subsidiary) |
| Stack mocks | 11 | + 7 (Salesforce, Mediaocean, Prisma, Kinesso, SAP S/4, Workday, DocuSign) |

**Bottom line:** the substrate is ~80% there structurally; the **emergent-behaviour proof** is ~10% there. Closing that gap is what makes the demo land.

---

## 3. Approach: 10 tracks, sequenced

```
Track A — Substrate hardening (one-time foundation)
Track B — Data fabric & generated entity baseline (small-but-real ontology)
Track C — Domain depth (legacy projections + 5 stub domains + agency-specific domains)
Track D — Persona depth (5–6-tier org, authority matrix, personality knobs)
Track E — Agency entity kinds & content (Brand, Campaign, Pitch, MediaPlan, Subsidiary + projections)
Track F — Stack mocks (Salesforce, Mediaocean, Prisma, Kinesso, SAP S/4, Workday, DocuSign)
Track H — Cross-domain entanglement (the connective-tissue layer — where the magic actually lives)
Track I — Learning & feedback loops (the system gets observably smarter over time)
Track J — Longitudinal observability (KPI history, time-scrub UI, "leave it for hours" view)
Track G — Demo scripting & narrative (3-act 30-min runbook + KPI cinematics + voice command)
```

Tracks A and B are still the foundation. Tracks H, I, J are **the new headline** — they implement the three properties from §0. Track E supplies the entity kinds H needs. C/D/F can run in parallel after A/B.

---

## 4. Track-by-track detail

### Track A — Substrate hardening (P0, foundation)

| ID | Title | Why now |
|---|---|---|
| a1 | Project entity-kind columns in `/api/entities/{id}` (drop NULL union noise) | At 3k entities, the union-of-all-columns response shape is unreadable |
| a2 | Make `/api/entities/{id}/linked` paginate (limit/cursor) | A vendor with 500 invoices today returns one giant array |
| a3 | Add `/api/entities/{id}/timeline` (chronological view of every event referencing this id) | The killer "show me everything that touched this PO" pitch view; foundation for property #1 (concurrency) |
| a4 | Wire `expense-claim` and `hiring` entity projections | These two are the most-spawned legacy domains and emit nothing to the graph; concurrency invisible without them |
| a5 | Wire `TOUCHED` (Person→Decision) and `PRECEDENT_OF` (when query_precedents resolves a hit) | Both feed property #2 — TOUCHED makes "who decided what" queryable; PRECEDENT_OF is the literal precedent edge |
| a6 | Promote `Workflow` node to first-class city in the cosmic lens | Meta-workflow / parent-child orchestration is core to property #1 |
| a7 | Add `/api/entities/_kinds` summary endpoint | "Org X-ray" 5-second opener for the demo |
| a8 | Snapshot/restore (one Kuzu file → tarball → restore) | Cold-start demo is a no-no; also lets us "save game" after a 4h run |
| a11 | Cosmic lens scaling: aggregation + LOD + sprite cap | The hard cap that makes laptop-safe scale visibly impressive |

### Track B — Data fabric & generated entity baseline (P0, scale)

Generator that produces the small-but-real Zava org from a typed `DataPack(...)` config. Per locked decision #3, no hand-edited JSON.

| ID | Title | Output |
|---|---|---|
| b1 | Calendar engine (fiscal year, quarters, weeks, public holidays per country) | ~10 Period nodes |
| b2 | Faker-based employee generator using each function's `persona_hierarchy` as the spine | ~100 named Persons in a real org chart |
| b3 | Vendor generator (production houses, freelancers, software, ad-tech, research, talent) | ~50 Org nodes with risk bands, payment terms, ESG ratings |
| b4 | Client / Brand generator | 6 client Orgs, ~10 Brand nodes |
| b5 | Asset generator (campaigns, MSAs, SOWs, media plans, briefs, decks) | ~150 Asset nodes |
| b6 | Money generator (POs, invoices, contracts, recharges, FX) — 80/20 distribution | ~500–1,000 Money rows (one quarter) |
| b7 | 24-h workflow spawn timeline (per-domain frequency) | ~100–150 historical workflows + ~25 in flight at boot |
| b8 | Localisation tables (UK/US/DE/FR/JP/IN/BR/AU) | 8 region rows with currency/date/holiday/statute |
| b9 | `DataPack` typed config — single Python entrypoint that materialises the whole pack | One pack = one dataclass |
| b10 | Snapshot the generated graph as `.kuzu` tarball; restore on boot | 2–5 sec cold start |

### Track C — Domain depth (P1)

| ID | Title |
|---|---|
| c1 | Promote 5 stub domains to live: `board-prep`, `fy-close`, `lead-to-cash`, `hire-to-productive`, `vendor-risk-to-pay` |
| c2 | 7 cross-domain meta-workflows: `media-pitch-to-win`, `account-onboarding`, `intercompany-recharge`, `talent-redeployment`, `agency-network-roll-up`, `m-and-a-integration`, `crisis-response` |
| c3 | ~10 agency-specific domains: `creative-awards-submission`, `client-renewal`, `freelancer-onboarding`, `data-clean-room-setup`, `weekly-pitch-review`, `monthly-client-pnl`, `quarterly-creative-awards`, `annual-budget-setting`, `new-business-pipeline-scrub`, `intercompany-talent-transfer` |
| c4 | Region overlays — same domain, different policies per region |
| c5 | Slow-burn domains — contracts spanning months, perf cycles spanning quarters; time-compressed (1 min wall = 1 day business) |
| c6 | Long-tail HITL personae per domain — sick / on-holiday / escalation timeout / override edge cases |

### Track D — Persona depth (P1)

| ID | Title |
|---|---|
| d1 | 5–6 layer trees per function (cfo → controller → regional-controller → bp-pod-lead → bp → analyst → clerk) |
| d2 | Authority matrix as data: per-persona spend limit, approval power per phase, delegation chain, OOO/holiday rules |
| d3 | Agency-specific role library (account director hierarchy, planner/buyer split, creative tree ECD→CD→ACD→…, strategist tree, production producer/PM tree, client services, talent/casting, ad-ops, data-science) |
| d4 | Personality knobs (risk-appetite, thoroughness, escalation-style) — same role, different humans, different decisions |
| d5 | Pre-canned narrative arcs (named individuals + photos + 2-line bios surfaced in HUD) |

### Track E — Agency entity kinds & content (P1, the structural differentiator)

| ID | Title |
|---|---|
| e1 | New entity kinds: **Brand, Campaign, Pitch, MediaPlan, Subsidiary** + rels (BRAND_OF, CAMPAIGN_FOR, EXECUTED_BY, SUPPLIED_BY, PITCH_FOR, RESULTED_IN, PART_OF) |
| e2 | Entity projections for the new agency-specific domains in c3 |
| e3 | 5 named subsidiaries under Zava Group ("Zava Creative", "Zava Media", "Zava Production", "Zava Data", "Zava Group") |
| e4 | Realistic agency KPIs surfaced on the HUD (win-rate %, billable utilisation, gross profit per brand, client churn, time-to-launch, freelancer mix %, intercompany recharge volume) |
| e5 | Cross-functional cadenced rituals (weekly pitch review, monthly client P&L, quarterly creative awards, annual budget setting, new-business pipeline scrub) |
| e6 | "Network effect" panel showing holding-level views across the 5 subsidiaries (which subsidiary owns which brand, which talent moves between agencies, which clients overlap) |

### Track F — Stack mocks (P1)

Hand-crafted (decision #4). Each ~200 lines of TypeScript under `mocks/<name>/server.ts`, in-memory state, port range 4200–4299.

| ID | Mock | Used by |
|---|---|---|
| f1 | salesforce-crm-mcp | media-pitch-to-win, lead-to-cash, account-onboarding |
| f2 | mediaocean-mcp | media plan, reconciliation, billing |
| f3 | prisma-mcp | media-buying workflow, supplier reconciliation |
| f4 | kinesso-mcp | data, audience, addressability |
| f5 | sap-s4-finance-mcp | invoice CRUD, GL post, vendor master, FX, accruals, intercompany |
| f6 | workday-hcm-mcp | employee master, comp letter, transfer, OOO calendar, learning record |
| f7 | docusign-mcp | envelope, route, signature, audit |

### Track H — Cross-domain entanglement (P0 for the headline, the connective tissue)

This is **where the "feels real" comes from**. Today, domains run in parallel but largely independently. We add deliberate **shared-state interactions** so workflows interfere via the entity graph.

| ID | Title | Concurrency story |
|---|---|---|
| h1 | **Vendor KYC outcome gates invoice processing** — when vendor-kyc verdict = "red", any in-flight ap-invoice referencing that vendor pauses with reason "vendor blocked"; resumes if cleared | One vendor city pulses: KYC rocket lands → invoice rockets in flight all glow red |
| h2 | **Brand budget gates campaign + media spend** — every Money row tagged to a Brand decrements its budget; campaigns and POs hitting an over-budget brand auto-spawn a budget-variance exception | One brand city: simultaneous PO + invoice + campaign rockets, budget gauge falling in real-time |
| h3 | **Person availability gates approvals across all domains** — the authority matrix knows who's OOO; approvals re-route to delegate within the same workflow's existing wait window | One person city goes dim ("Marcus on holiday") → in-flight approvals across 4 different domains visibly re-route to his delegate |
| h4 | **Subsidiary capacity gates new pitches** — pitch-to-win checks billable utilisation across the subsidiary's people; if utilisation > 90% the pitch decision auto-flags "no capacity" | A subsidiary city saturates: new pitch rockets get warning halos |
| h5 | **Talent transfer cascades** — moving a Person from Subsidiary A to Subsidiary B triggers OWNS-Asset reassignments + access-revoke + access-grant + comp-cycle reopen | One transfer = 4 cross-domain workflows visibly spawning |
| h6 | **Client renewal triggers MSA + DPIA + portfolio review** as sub-workflows | One renewal rocket spawns three sub-rockets (uses existing SUB_WORKFLOW_OF) |
| h7 | **Crisis injection: "key client wants out"** — coordinated event that drops 4 simultaneous workflows: contract-review (offboarding), talent-redeployment, intercompany-recharge unwind, board-prep "loss" entry | One injection = visible 4-way storm across the org |

### Track I — Learning & feedback loops (P0 for the headline, the time-evolution)

The system has to demonstrably **get smarter** as it runs.

| ID | Title | Learning effect |
|---|---|---|
| i1 | **Precedent-influenced persona policy** — every persona's `decision_policy` first calls `query_precedents`; if ≥3 matching precedents agree on a verdict, persona auto-applies it (else falls through to current logic) | Decisions accelerate as precedents accumulate; visible as decreasing latency on the per-persona KPI strip |
| i2 | **Auto-block rule emergence** — when a vendor accumulates ≥3 KYC-red verdicts, ambient agent installs an auto-block rule (a new "policy precedent") so future invoices don't even spawn | Self-tightening compliance — visible on the audit log |
| i3 | **Exception classifier online learning** — `exception-classifier` skill keeps a running count of (signature → resolution) pairs; on cache hit it short-circuits | Exception cycle time drops over the run |
| i4 | **Routing optimiser** — track per-(domain, gate) escalation outcomes; if a delegate consistently approves what their boss approves, future approvals route to delegate first | Persona load auto-rebalances |
| i5 | **KPI-trend-driven cadence triggers** — ambient agents watch trends (slope), not snapshots: a 7-day downward trend in win-rate spawns a `new-business-pipeline-scrub` workflow without anyone clicking | Real ambient autonomy |
| i6 | **Persona "experience" attribute** — every persona accumulates a count of decisions per domain; high-experience personae get higher trust weighting in the routing optimiser | Org learns who knows what |
| i7 | **Decision-replay endpoint** — `POST /api/decisions/replay/{id}` re-runs the persona's policy against current state and reports whether it would still decide the same way | Demonstrable "the org has changed its mind" |

### Track J — Longitudinal observability (P1, the "leave it 4h" view)

| ID | Title | Output |
|---|---|---|
| j1 | KPI history series (rolling 24h, every minute) per function — backed by a small SQLite ring buffer | Sparkline on every HUD KPI |
| j2 | Persona load over time series | "Aisha's queue depth over the last hour" chart |
| j3 | Per-domain decision-latency trend | "AP invoice cycle time has dropped 40% in 4 hours — precedents accumulating" |
| j4 | **Time-scrub UI on the cosmic lens** — drag a slider to see the org as it was N minutes ago; rockets and city activity replay | The killer "leave it and come back" view |
| j5 | **Daily summary pack** — auto-generated at hourly intervals: top events, biggest entity-graph deltas, learning-loop wins | The "story of the morning" view |
| j6 | **What's-new dashboard** — surfaces auto-block rules installed (i2), routing rebalances (i4), classifier hits (i3) | Makes property #2 (learning) tangible |
| j7 | **Persistent activity ledger across restarts** — snapshot includes the in-memory ambient-agent state so a 4h run plus a restart doesn't lose what was learned | "Save game" |

### Track G — Demo scripting & narrative (P1)

| ID | Output |
|---|---|
| g1 | 30-min demo script: 3 acts, 5 personae spotlighted, 3 cross-functional decisions, 1 crisis injection (h7) |
| g2 | Pre-recorded "fast-forward" scenarios — see 4 hours of activity in 60 sec via j4 time-scrub |
| g3 | Agency-specific KPI cinematics on the HUD with j1 sparklines (win-rate, billable utilisation, intercompany recharge flow visualisation) |
| g4 | One-page architecture diagram with agency stack overlaid (Salesforce / Mediaocean / Prisma / Kinesso / SAP / Workday / DocuSign edges) |
| g5 | FAQ ("but our compliance / security / data residency / data-clean-room rules / IPA code…") |
| g6 | Price-points + ROI calculator |
| g7 | Live "CFO command" demo: voice-in → cosmic-lens reaction → action recommendations → audit trail |

---

## 5. Sequencing & milestones

```
Track A — Substrate hardening
Track B — Data fabric & generated baseline       ──► Foundation milestone
                                                      │
                       ┌──────────────────────────────┼─────────────┐
                       ▼                              ▼             ▼
          Track D — Persona depth      Track F — Stack mocks   Track E — Agency entity kinds
                       │                              │             │
                       └────────────┬─────────────────┴─────────────┘
                                    ▼
                       Track C — Domain depth (uses D + F + E)
                                    │
                                    ▼
                       Track H — Cross-domain entanglement (the headline)
                                    │
                                    ▼
                       Track I — Learning & feedback loops (the headline)
                                    │
                                    ▼
                       Track J — Longitudinal observability ("leave it 4h")
                                    │
                                    ▼
                       Track G — Demo scripts & cinematics (gates the pitch)
```

H, I, J are the three properties from §0. They are the headline of the rebuilt simulator and unlock the "you can leave it for hours and come back to a story" experience.

---

## 6. Effort & gap calibration

| Track | Scope | Effort bucket |
|---|---|---|
| A | 9 surgical PRs | **small–medium** |
| B | New `data_fabric/` package; ~5 generators; calendar engine; snapshot tooling | **medium** |
| C | 5 stub domains promoted + ~10 agency domains + 7 cross-domain meta-workflows | **medium–large** |
| D | Authority matrix + ~80 personae extension | **medium** |
| E | 5 new entity kinds + projections + ~5 subsidiaries + KPIs + cadences + holding views | **medium–large** |
| F | 7 hand-crafted enterprise mocks | **medium** |
| **H** | **7 cross-domain entanglement scenarios — touches almost every domain** | **large (the headline)** |
| **I** | **7 feedback-loop / learning mechanisms** | **large (the headline)** |
| **J** | **7 longitudinal observability features (KPI history, time-scrub, save-game)** | **medium–large** |
| G | 30-min demo script + KPI cinematics + voice/avatar polish | **medium** |

**The Foundation (A + B) is still the gate.** But the project's centre of gravity has moved from "more data" to **H + I + J**.

---

## 7. What we should NOT build (yet)

- Real connectors to Salesforce / SAP / Workday / etc. (the mocks tell the story; real ones are paid integration work after a deal closes).
- Other vertical packs (FMCG / Pharma / Airline / Telco / Auto). Locked out per decision #1.
- Multi-tenant primitive. Locked out per decision #2.
- Sandboxed persona DSL. Locked out per decision #5.
- Typed mock framework. Locked out per decision #4.
- Localisation beyond ~5 regions until needed.
- Persistent learning across multi-day runs (j7's "save game" covers single restart only — multi-day longitudinal training is out of scope).

---

## 8. Demo-day pass criteria — measured in EMERGENT BEHAVIOUR

The simulator is "pitch-ready" when, after **booting cold and running for 1 hour unattended**, the following all hold:

### Static (post-boot)
1. Cold-load takes ≤ 5 seconds (snapshot restore).
2. Graph has ~1,500–3,000 entities and ~5,000–10,000 edges at boot.
3. Cosmic lens stays at >30 fps with the demo dataset loaded.
4. Every persona that appears in the demo has a name, role, photo, and 2-line bio.
5. ~25 workflows in flight at boot, hard visual cap with overflow indicator.
6. Naming stays "Zava" throughout.

### Concurrency (Property 1)
7. **At least 5 entities** (1+ vendor, 1+ brand, 1+ person, 1+ period, 1+ subsidiary) are touched by **3 or more workflows** during a 1-hour run.
8. The "concurrency clock" — at any random moment in the run — shows ≥3 different domain workflows in flight.
9. The cosmic lens demonstrably shows two rockets landing on the same city in the same second at least 3× per hour.

### Learning loops (Property 2)
10. After 1 hour, **average decision latency for ≥1 high-volume domain is measurably lower** than at minute 5 (precedents kicking in).
11. **At least 1 auto-block rule** has been installed by the substrate during the run (i2).
12. **At least 1 routing rebalance** has occurred (i4).
13. **At least 1 cadence-triggered workflow** has spawned because of a KPI trend (not snapshot — i5).
14. The "what's-new" dashboard (j6) shows ≥5 distinct learning-loop entries by t=60min.

### Longitudinal observability (Property 3)
15. KPI history sparklines on every HUD KPI (last 60 min) (j1).
16. The time-scrub slider (j4) lets you replay any 5-minute slice of the past hour.
17. The auto-generated "story of the morning" pack (j5) lists ≥5 narrative-quality events from the run.
18. Snapshot + restart preserves the in-memory ambient-agent state (j7).

### Crisis (the wow)
19. The "key client wants out" injection (h7) reliably triggers the 4-way cross-domain storm and resolves cleanly without crashing.
20. Three of an agency-holding's actual existing systems (Salesforce / Mediaocean / Prisma / Kinesso / SAP / Workday) appear as MCP edges during the demo.

---

## 9. Tracking

Tasks reflected into the session SQL `todos` table once the user kicks off implementation. IDs use the `pitch-<track><n>` convention (e.g. `pitch-a1`, `pitch-h3`, `pitch-i5`).

```sql
SELECT id, title, status FROM todos WHERE id LIKE 'pitch-%' ORDER BY id;
```

This document is the human-readable source of truth; the SQL table is the queryable execution surface.

---

