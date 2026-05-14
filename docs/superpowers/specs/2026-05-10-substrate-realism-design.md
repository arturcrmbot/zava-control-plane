# Substrate Realism — Design

**Date:** 2026-05-10
**Scope:** `api/shared/domains.py`, `api/server/services/simulator_orchestrator.py`, `api/server/services/persona_responder.py`, `api/server/services/ambient_dispatcher.py`, `api/server/services/entity_graph.py`, `api/server/routes/internal_durable_event.py`, `api/server/routes/blueprint.py`, `web/blueprint/src/components/cosmicLens/lib/useLiveCosmic.ts`, `README.md`.
**Goal:** Make the Zava control-plane substrate feel like a real business — domains spawn at realistic cadences, the cosmic lens consumes the events the producers actually emit, HITL gates produce real decision moments, ambient pulses keep the scene alive between workflow spawns, and total event throughput stays bounded.

## Problem

Three independent gaps make the substrate feel synthetic and the observatory feel half-empty:

1. **Substrate dishonesty.** `domains.py` registers 19 entries (14 live + 5 stubs). The README claims 8. The cosmic lens declares it consumes 10 SSE event types; 5 of them are never emitted on the bus (or are emitted under a different name). The simulator has its own duplicate registry — a literal `spawners = {…}` dict at `simulator_orchestrator.py:554-569` — that must be edited every time a domain is added. `PERSONA_AUTO_CLOSE=*` is the env default, so every HITL gate auto-resolves and operators never see real exceptions.
2. **Cadence treadmill.** Every domain spawns on the same 90s ± 30% schedule (`SIMULATOR_RAMP_AVG_INTERVAL_SECONDS`). A real business doesn't do board-prep with the same frequency as AP-invoice processing. The uniform rate makes the disc look like a synthetic stress test.
3. **Dead air between workflows.** Between workflow spawns, the only thing happening on the bus is a `fleet.tick` every 30 seconds — and the lens doesn't render it. Cypher-trigger ambient agents fire on cadence but their decisions never reach the bus. The result is a scene that goes quiet for stretches even though the substrate is doing work.

## Approach

Make `domains.py` the single source of truth and drive everything else from it. Add a per-domain realistic spawn cadence and a single demo time-warp multiplier so the same registry serves both real-time and demo modes. Add a per-gate `wait_probability` so a fraction of HITL gates produce real exceptions instead of always auto-closing. Align the cosmic lens's event allow-list with what producers emit; emit the few events producers should be emitting but aren't. Render the always-on heartbeat events the substrate already produces. Cap total observatory throughput as a belt-and-braces protection against any future firehose.

The work is decomposed into three phases (C, A, B) ordered by dependency: hygiene first so the registry is trustworthy, then cadence so spawning matches reality, then ambient activity to fill the gaps that cadence reveals.

## Architecture

### Phase C — Substrate hygiene & contract truth

**C1. Truth-up the registry (don't drop the stubs).** The 5 `stub=True` domains (`hire-to-productive`, `vendor-risk-to-pay`, `lead-to-cash`, `fy-close`, `board-prep`) are referenced by `api/shared/functions.py` (each owns a meta-function via `owns_domains`), the `web/blueprint/src/pages/OrgClonePage.tsx` view, and `web/blueprint/src/components/cosmicLens/lib/workflowFunction.ts` (id-prefix mapping). They are runtime-inert because no spawner is wired, but they exist as graduation placeholders for the agentic-org Phase 4 meta-workflows. Keep them in the registry; instead:

- Update the `Domain.stub` field docstring to say "registered in the org-clone surface as a meta-workflow placeholder; not spawned at runtime".
- Update the README's domain count from 8 to "14 live + 5 strategic placeholders" with a one-line footnote pointing at `api/shared/domains.py`.
- Add a `live_domains()` helper to `domains.py` returning `[d for d in DOMAINS.values() if not d.stub]` so consumers (simulator, FM skill text, blueprint inventory) read live-only without filtering inline. This becomes the canonical "what runs" accessor.

**C2. Make spawner resolution data-driven.** Add a `spawn_fn: str | None` field to the `Domain` dataclass in `domains.py`. Each entry names the dotted path of its spawner function (e.g., `"api.server.services.simulator_orchestrator.spawn_fleet_ap_invoice_workflow"`). Replace the literal `spawners = {…}` dict at `simulator_orchestrator.py:554-569` with a `_resolve_spawner(domain)` helper that imports by name and caches the callable. Domains without `spawn_fn` raise a clear "no spawner registered" error at startup so missing wiring fails loudly. Adding a new domain becomes: domain entry + workflow file + spawn fn — three places, all logically related. No more duplicate registry.

**C3. Align event vocabulary.** The cosmic lens consumes 10 SSE event types (declared in `web/blueprint/src/components/cosmicLens/Rockets.tsx` and friends). Five are missing from the bus. Per-type fix:

| Event type | Action | Rationale |
|---|---|---|
| `tool.invoked` | Drop from cosmic-lens consumer code (Rockets.tsx). Leave in `_OBSERVATORY_TYPES` for any future producer. | The substrate emits `durable.executor.invoked` for every tool/skill/validator/agent invocation; the lens already checks both. Removing the dead alias from the lens halves the per-event branching. |
| `ambient.decided` | Emit on the bus from `ambient_dispatcher.py:342` next to the existing `self._audit.log("ambient.decided", details)` call. Type is already in `_OBSERVATORY_TYPES`. | One-line addition; useful operator signal for ambient-agent activity. |
| `entity.read` | Emit on the bus from `entity_graph.py` `get()` (line 826), `by_type()` (line 846), and `find_by_pattern()` (line 936). Add to `_OBSERVATORY_TYPES`. | Naturally rate-bounded by workflow execution; gives the entities-mode lens something to render. |
| `workflow.completed` | Update lens to listen for `durable.workflow.completed` (already emitted at `internal_durable_event.py:640`); drop the alias-listener for `workflow.completed`. | Don't introduce a duplicate server-side type. |
| `workflow.failed` | Emit on the bus from the `body.kind == "workflow.rejected"` branch in `internal_durable_event.py:656` next to the existing `workflow.resolved` emission. Add to `_OBSERVATORY_TYPES`. | Currently we only emit `workflow.phase.failed` and `workflow.resolved(resolution=rejected)`; a top-level `workflow.failed` makes the FM exception widget complete and matches the lens's existing listener. |
| `fleet.tick` | Add to `_OBSERVATORY_TYPES`. Emitted every 30s from `fleet_manager_service.py:340`. | Supplies the always-on substrate heartbeat for B1. |
| `kpi.published` | Add to `_OBSERVATORY_TYPES`. Emitted from `fleet_manager_service.py:433`. | Already low rate; useful for B1 planet-glow. |

**C4. Per-gate `wait_probability`.** Add a `wait_probability: float` field to the `Gate` dataclass in `domains.py`. The persona responder rolls the dice on each HITL hit; if it lands "wait", the gate stays open and produces a real `workflow.exception.detected` + `workflow.hitl.requested` pair, exactly as if the persona allow-list excluded that role. Sensible per-gate calibration ships in the spec (5–40% by gate risk profile). Result: ~10% of all gate hits across the substrate become real human-decision moments. The env-var contract for `PERSONA_AUTO_CLOSE` is unchanged — explicit allow/deny lists still take precedence over the per-gate roll.

### Phase A — Cadence realism + demo time-warp

**A1. Per-domain `realistic_interval_seconds`.** Add to the `Domain` dataclass. Calibrated values (real-world cadence as a rough business reality, not exact):

| Domain | Realistic cadence | seconds |
|---|---|---|
| ap-invoice | every 30 min | 1800 |
| expense-claim | every 45 min | 2700 |
| travel-preapproval | every 2 h | 7200 |
| purchase-order | every 6 h | 21600 |
| it-access-request | every 4 h | 14400 |
| vendor-kyc | every 12 h | 43200 |
| hiring | every 1 day | 86400 |
| employee-onboarding | every 1 day | 86400 |
| treasury-fx | every 1 day | 86400 |
| contract-review | every 2 days | 172800 |
| contract-renewal | every 3 days | 259200 |
| privacy-dpia | every 5 days | 432000 |
| creative-campaign | every 7 days | 604800 |
| perf-review | every 60 days | 5184000 |

**A2. `DEMO_TIME_WARP_FACTOR` env var (default 60).** Effective cadence = `realistic_interval_seconds / DEMO_TIME_WARP_FACTOR`. A single knob to slow down or speed up the entire substrate without touching per-domain config. Set to `1` for real-world cadence; default `60` keeps the demo lively (1 real-world day = 24 minutes); jack to `300` for stress testing.

**A3. Per-domain ramp loop driven by effective cadence.** `_per_domain_ramp()` at `simulator_orchestrator.py:665-698` reads its interval from `domain.realistic_interval_seconds / time_warp` instead of the global `SIMULATOR_RAMP_AVG_INTERVAL_SECONDS`. Existing ±30% jitter is preserved (Poisson-like). `SIMULATOR_RAMP_AVG_INTERVAL_SECONDS` becomes a fallback for any domain missing the new field, so partial migration stays safe.

**Event budget at warp 60.** Sum of `(time_warp / realistic_interval_seconds)` across the 14 domains gives ~12–15 spawns/min. Each workflow emits ~15–20 SSE events over its lifetime → peak ≈ 250 events/min ≈ 4/sec. Comfortably below "thousands". perf-review is effectively dormant in a demo session (one spawn every 24 hours of demo time at warp 60); creative-campaign spawns a few times per hour of demo. The high-cadence domains (AP, expense, travel) supply the steady stream the observatory needs.

### Phase B — Always-on activity & event-rate cap

**B1. Render existing always-on pulses.** Add to the cosmic lens SSE allow-list and render as low-key visual cues:

- `fleet.tick` (every 30s) — soft pulse on the central hub. Reads as the substrate's heartbeat.
- `kpi.published` — brief glow on the relevant function planet. Already low rate.
- `ambient.decided` (once C3 emits it on the bus) — quick sparkle on the city corresponding to the cypher trigger.

These render through existing primitives (`PlanetCompletions.tsx` for planet glows, a new tiny burst component for hub ticks) and don't require new event types.

**B2. Hard cap on observatory throughput.** `MAX_OBSERVATORY_EVENTS_PER_SEC` env var (default 20 = 1200/min ceiling). Implemented as a token-bucket drop in the `/api/blueprint/stream` SSE relay (`blueprint.py`). When the bucket is empty, drop subsequent events for that second and emit a single `[blueprint] dropped N events (cap=20)` log line. Belt-and-braces against any future event firehose. Default of 20 is well above expected steady-state (~4/sec) but small enough to prevent a stuck client or runaway producer from melting the browser.

## Files touched

| File | Change |
|---|---|
| `api/shared/domains.py` | Add `realistic_interval_seconds`, `spawn_fn` fields to `Domain`; add `wait_probability` field to `Gate`; populate per-domain values; remove 5 stub entries. |
| `api/server/services/simulator_orchestrator.py` | Replace literal `spawners` dict with `_resolve_spawner(domain)`; rewrite `_per_domain_ramp()` interval from domain cadence × time-warp; keep `SIMULATOR_RAMP_AVG_INTERVAL_SECONDS` as fallback. |
| `api/server/services/persona_responder.py` | Roll `wait_probability` per gate hit before `_handle_hitl()` auto-resolves. |
| `api/server/services/ambient_dispatcher.py` | Emit `ambient.decided` on the bus next to the audit log line. |
| `api/server/services/entity_graph.py` | Emit `entity.read` on the read path. |
| `api/server/routes/internal_durable_event.py` | Emit `workflow.failed` on terminal-rejection paths. |
| `api/server/routes/blueprint.py` | Add `MAX_OBSERVATORY_EVENTS_PER_SEC` token-bucket; widen `_OBSERVATORY_TYPES` to include `fleet.tick`, `kpi.published`, `ambient.decided`. |
| `web/blueprint/src/components/cosmicLens/Rockets.tsx` | Drop `tool.invoked`, accept `durable.workflow.completed` where it currently checks `workflow.completed`, accept `workflow.failed` where appropriate. |
| `web/blueprint/src/components/cosmicLens/lib/useLiveCosmic.ts` | Forward the new event types to `flashesRef`. |
| `web/blueprint/src/components/cosmicLens/CosmicLens.tsx` | (If needed) wire fleet.tick / kpi.published / ambient.decided into hub pulse + planet-glow primitives. |
| `README.md` | Update domain count from 8 to 14; mention `DEMO_TIME_WARP_FACTOR`. |
| `.env.example` | Add `DEMO_TIME_WARP_FACTOR=60` and `MAX_OBSERVATORY_EVENTS_PER_SEC=20` with brief comments. |

## Out of scope

- Implementing the 5 stub domains as real orchestrators (cut from registry; graduate via `compose-domain` if needed later).
- Reworking the cosmic lens entity view (next brainstorm round; data signals from this work will inform that design).
- New personae, new MCP servers, new orchestrators, new graph executors.
- Any change to POC1 (expense-claim) or POC2 (hiring) demo scripts. Both keep `PERSONA_AUTO_CLOSE=*` in their `.env` to preserve full auto-close for demo takes.
- Persisting per-domain cadence to disk between runs. Cadence is config in `domains.py`, not state.

## Verification

After each phase commit:

1. `pytest api/server` and `pytest api/functions` (or whatever the project uses) — green.
2. `npm run test -- web/blueprint` — green.
3. `npm run build:blueprint` — green.

After Phase A specifically: `make up`, then watch the FastAPI log for ~5 minutes. Expect:
- AP-invoice and expense-claim workflows spawning on the order of every 30–45s.
- Quieter cadences (contract-renewal, perf-review) not spawning at all in a 5-minute window. That's the point.
- `curl http://localhost:3101/api/workflows/index/in-flight | jq 'length'` — non-trivial active set after a few minutes.

After Phase B specifically: open `http://localhost:5275/?view=constellation`, then in DevTools:
- `window.__cosmic.eventTypeHistogram()` — `fleet.tick` non-zero; `ambient.decided` non-zero (proof C3+B1 worked end-to-end).
- Watch for the central hub pulse on every `fleet.tick`.
- Trigger `curl -X POST http://localhost:3101/api/simulator/inject-burst?n=50` and confirm the event-rate cap log line appears at most a few times per second.

After C4 specifically: with `PERSONA_AUTO_CLOSE=*` (default) and the new `wait_probability`, watch the FM exception widget for a few minutes. Expect ~10% of gate hits to surface as exception cards. With `PERSONA_AUTO_CLOSE=none`, every gate waits regardless of `wait_probability` — back-compat preserved.

## Risks

- **Event-rate cap may swallow useful events under burst inject.** Mitigation: the default cap (20/sec = 1200/min) is well above steady-state (~4/sec) and the burst route is for demo emphasis, not stress testing. If a demo wants every burst event surfaced, raise `MAX_OBSERVATORY_EVENTS_PER_SEC` in the demo `.env`.
- **`wait_probability` rolls produce non-determinism.** Mitigation: roll uses Python `random` seeded only by walltime — fine for demo variety. Determinism isn't a substrate property today and adding it for this case would over-engineer. If a specific demo needs reproducibility, set `PERSONA_AUTO_CLOSE=*` in that demo's `.env` to short-circuit the roll.
- **Dropping the 5 stub domains may regress some test or doc that referenced them by name.** Mitigation: a `git grep` for each stub workflow_type before removal flags any reference; either update or delete those.
- **Time-warp changes the meaning of `SIMULATOR_RAMP_AVG_INTERVAL_SECONDS`.** Mitigation: it remains a fallback only for domains missing `realistic_interval_seconds` — once all 14 live domains carry the new field, the fallback is dead code (kept for safety). Documented in `.env.example`.
- **Existing tests may have hard-coded assumptions about the spawners dict shape or the persona auto-resolve behaviour.** Mitigation: run the full test suite (Python + JS) at the end of each phase and fix any breakage as part of that phase's commit.
