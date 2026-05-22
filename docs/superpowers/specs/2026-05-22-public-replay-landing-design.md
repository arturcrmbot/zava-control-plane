# Zava Control Plane — Public Replay Landing
**Date:** 2026-05-22
**Status:** Draft — pending user approval before implementation

## What we're building
A public always-on demo of the Zava Control Plane at the existing Azure Container Apps URL (`blueprint.jollygrass-c41bb8b9.swedencentral.azurecontainerapps.io`). Visitors land on the operator UI (the control plane on port 5273 today), watch a 2-hour recorded loop of the substrate doing its thing — workflows arriving, personae deciding **on their own cadence** (visitor never needs to click), dream passes firing, lessons crystallising, **and the governance matrix mutating live as domain agents take ownership decisions** — and can drill into anything they see. No decision-making asked of the visitor, no LLM cost, no abuse vector. A persistent badge tells them it's a replay.

## Why a replay (not the real thing)
The substrate has:
- Per-process global state (one Fleet Manager, one bus, one Mem0). Two visitors trample each other.
- Unauthenticated write surfaces (`/api/simulator/inject`, `/api/dream-pass/run`, `/api/memory/v2/seed-demo`).
- Uncapped LLM cost (persona summaries every 5 min, dream consolidation, Foundry evals).
- A `.poc-safety` marker explicitly forbidding public ingress until hardening lands.

A read-only replay sidesteps every one of those for ~5 days of work instead of weeks of hardening. Visitors still get the full visual experience and can click through every detail page in their own time.

## Architecture

### Two modes, one codebase
The FastAPI control plane gains two new modes flipped by env:

- `ZAVA_MODE=record` — boot the existing local stack; subscribe a recorder service to the EventBus; periodically snapshot REST-shaped state. On graceful shutdown (`Ctrl-C` after ≥ 2 h), write a `tape.tar.gz` containing everything needed for playback.
- `ZAVA_MODE=replay` — load `tape.tar.gz` into in-memory state stores; gate all POST routes behind a read-only middleware; replay bus events at real-time pace; on EOT hard-reset to t=0 with a 3-second banner.

Local development and the existing demo stack are unaffected (default mode is `live`).

### Tape format
A gzip-tar with:
```
tape.tar.gz
├── meta.json                  # recorded_at, duration_s, version, app sha
├── snapshot_t0/               # full REST-shaped initial state
│   ├── workflows.json
│   ├── exceptions.json
│   ├── personae.json
│   ├── functions.json
│   ├── memories.json
│   ├── lessons.json
│   ├── kpis.json
│   └── audit_summary.json
├── events.ndjson              # one JSON event per line, "t": seconds-since-t0
└── mutations.ndjson           # state deltas, "t": seconds-since-t0
                               # ({op:"upsert", kind:"workflow", id:..., patch:{...}})
```

`events.ndjson` is exactly what the SSE relay emits today. `mutations.ndjson` is the new piece: every state change the recorder observed (workflow created, exception resolved, persona decided, lesson promoted) so the REST endpoints stay consistent with what the SSE stream just announced.

### Recorder
A new `api/server/services/replay/recorder.py` that:
1. Subscribes to the EventBus and tees every event into a buffer with `t = now - started_at`.
2. Subscribes to state-change hooks on `StateStore`, `DomainMemory`, `EntityGraph` and writes a mutation entry per change.
3. Takes the initial snapshot by walking each existing REST handler (`list_workflows`, `list_exceptions`, etc.) at `t=0` and freezing the response payloads.
4. Periodically (every 5 min) flushes buffers to disk so a crash doesn't lose the whole recording.
5. On `Ctrl-C` (SIGTERM), tars everything and exits.

No new bus event types — we tap the existing surface. Recording the local stack with the simulator running for 2 h produces a real tape.

### Replayer
A new `api/server/services/replay/player.py` that runs at startup when `ZAVA_MODE=replay`:
1. Loads `tape.tar.gz` from a configurable path (env `ZAVA_TAPE_PATH=...`).
2. Hydrates `app_state.store`, `app_state.entities`, `app_state.domain_memories`, etc. from `snapshot_t0/`.
3. Spawns one asyncio task that ticks at wall-clock pace, advancing through `events.ndjson` and `mutations.ndjson` in order, applying mutations to state and emitting events onto the bus.
4. At EOT: emit a `playback.restart.pending` event, sleep 3 s, reload the snapshot, reset the playback clock to `t=0`, continue.
5. The simulator, AmbientDispatcher, cadence loops, persona responder, and any background task that *writes* state is disabled in replay mode. Only the SSE relay and read endpoints stay live.

### Read-only middleware
A FastAPI middleware that, when `ZAVA_MODE=replay`:
- Allows: all `GET`, plus the read-only SSE routes.
- Rejects: every `POST`, `PUT`, `PATCH`, `DELETE` with a 403 JSON `{ "error": "replay", "message": "This is a recorded replay — actions are observed, not made." }`.
- Whitelist exception: `POST /api/blueprint/stream/connect` if any existing route truly needs POST for connect (none today; verify).

### Front-end changes
Tiny, additive:
- A new env-fed `useReplayBadge()` hook that reads `GET /api/replay/meta` (returns `{ mode: "replay" | "live", recorded_at, tape_id, duration_s, current_t }`).
- Add the badge to `web/client/components/feed/Header.tsx`: `● live replay — recorded May 22` with a tooltip / click-to-modal explaining "you're watching a 2-hour recording on loop; all decisions were made by autonomous personae".
- On `playback.restart.pending` event over SSE, surface a 3 s overlay banner: `Replay restarting…`.
- When a POST hits 403 with `error: "replay"`, the existing toast layer shows `This is a replay — actions are observed, not made.` Already toast-capable — just hook the 403 handler.

### Recording with personae fully autonomous
The recording is captured with `DEMO_LOUD=1` so each persona's natural 2–8 s "thinking" window is preserved. From the visitor's perspective: a HITL gate appears with Approve/Reject buttons visible, the persona resolves it within a few seconds, the card flips to a resolved state, buttons gone. No new code needed — `persona_responder` already does this. The replayer simply ticks the resulting bus events at the recorded pace.

### Governance surface — replace the existing `/policy` page
The current `/policy` page lists synthetic autonomy policies (`expense.routing.amber_to_reviewer_threshold_usd`, etc.) sourced from a **dead** parallel file `api/shared/policies.yaml`. AGT never sees that file — it's pure cosmetic UI data left over from the demo era. **The cleanup deletes it.** The actual governance surface AGT enforces is `data/synthetic/authority/matrix.json`; this rewrite makes the UI tell the same truth as the kernel.

**Why this matters for the replay landing:** the visitor sees not just workflows flowing but the *rules themselves* (the matrix) AND the *operational decisions exercising those rules* in real time (`policy_set` Insights from the entity graph), with the link between them explicit via `governing_rule_id`.

Two-panel layout:

**Top panel — "Constitution" (the matrix.json rows)**
- Beautiful table, one row per matrix rule, grouped by domain.
- `Rule` — composed from `pattern`, `effect`, `governing_rule_id`.
- `Owner persona` — derived from the rule's function (CFO for `finance.*`, CTO for `tech.*`, CHRO for `hr.*`, etc.) via a small mapper over `api/shared/functions.py:FUNCTIONS`.
- `Last changed` — file-level `git log -1 --format='%ai %h %an'` against `matrix.json`. v1 is file-level; per-rule blame is a follow-up.
- `Effect` — Allow / Deny / Require-policy-set with a coloured chip.
- Click a row → modal with the raw JSON + a tooltip: *"This is the constitution — checked in at this commit. Every rule change is a PR. The running container hot-reloads the matrix within ~1 s of the file changing."*

**Bottom panel — "Decisions under the constitution" (live stream)**
- Pulls recent `policy_set` Decisions from the entity graph (the same `record_decision` path already wired by `policy_application.py`).
- Each row carries `governing_rule_id` linking back to the corresponding matrix row above.
- When a new `policy_set` arrives over SSE during the replay, the **matrix row referenced by `governing_rule_id` pulses for 3 s** and a new line slides in: *"CFO · 14:23 · approved `policy_set` for `verdaire_brand_budget` (rule EXP-031)"*.

**Backend changes** (small):
- New `GET /api/governance/matrix` — returns parsed matrix.json rows enriched with `owner_persona`, `owner_function`, `last_changed_at`, `last_changed_by_sha`. Computed once at boot, refreshed on file change.
- New `GET /api/governance/policy_changes/recent?limit=20` — recent `policy_set` Insights from the entity graph, enriched with the matrix rule they touched.
- Wire `policy_set` events into the existing `/api/blueprint/stream` relay if not already there.
- **Delete** `api/shared/policies.yaml`, the `AutonomyPolicy` model, `upsert_policy` / `list_policies` on `StateStore`, the old `/api/policy/dry-run` + `/api/policy/propose-change` routes. The old `/api/policy` route is rewritten to return the matrix shape.

**Recorder note:** the 2-hour recording should include several `policy_set` insights to make the live diff visible. The simulator + persona summary cadence already produces them on a long enough run; verify during the recording smoke test.

### Kernel hot-reload — matrix.json edits take effect within ~1 s
AGT exposes `reload_policies()` on `AsyncPolicyEvaluator`; our `GovernanceKernel.__init__` calls `compile_bundle(...)` exactly once at boot and never again. This contradicts AGT's design intent and means the marketing claim *"PR on matrix.json → all agents immediately enforce the new rule"* is false today (matrix changes need a process restart).

Fix: wire a tiny file-watcher into `GovernanceKernel`.

- New `api/server/services/governance/reload_watcher.py` — `asyncio` task that polls `matrix.json` mtime + sha256 every 500 ms (or uses `watchdog` if already a dep — verify). On change: call `compile_bundle(...)` fresh → swap the in-memory `PolicyDocument` atomically → emit a `governance.matrix.reloaded` bus event with the new `policy_version` hash + the changed `rule_ids` diff.
- Wired into the FastAPI lifespan alongside the existing kernel boot.
- Behind `GOVERNANCE_HOT_RELOAD=1` (default on; off only for tests that assert deterministic policy_version).
- Bus event surfaces in the dashboard top panel as a 3 s "constitution reloaded — 3 rules changed" banner.

This is ~half a day's work, and it makes the dashboard story strictly true: visitors can read in the tooltip that the constitution is hot, and the architecture honours that claim.

### Bidirectional essay ↔ live demo CTAs
The public essay (deployed to GitHub Pages from `web/blueprint/`) and the live replay (deployed to the ACA URL) should know about each other:
- Essay → adds a prominent **"Watch it run →"** CTA in the closing section, links to the ACA URL with a `?from=essay` query param.
- Live replay → adds a **"Read the essay →"** link in the header (next to the replay badge), links to the GitHub Pages URL with a `?from=demo` query param.
- Optional: the query param tweaks the welcome animation on the destination side (e.g. essay opens scrolled to the closing CTA if `from=demo`).
Extend the existing `scripts/build-blueprint-image.sh` / `web/blueprint/Dockerfile` into a single multi-purpose image:
- Layer 1: nginx serving `web/client/dist/` at `/`, `web/blueprint/dist/` at `/blueprint/`, `web/portal/dist/` at `/portal/`.
- Layer 2: Python 3.11 + uv + the API package; uvicorn binds to `127.0.0.1:3101`.
- nginx config proxies `/api/*` and `/internal/durable-event` to `127.0.0.1:3101`.
- `tape.tar.gz` is copied into the image at `/app/tape/tape.tar.gz` (or pulled from blob if larger than a few MB).
- Container Apps entrypoint runs both processes via `supervisord` or a tiny `entrypoint.sh`.
- Same Azure Container App, just a new image. Existing FQDN is preserved.

A new GitHub Action `.github/workflows/deploy-replay.yml` rebuilds + redeploys on push to `main` touching the replayer code, the SPAs, or the tape file. Tape updates are a manual workflow_dispatch with the tape file uploaded as an input (or pulled from a blob URL).

### What we deliberately leave out
- No Azure Functions, no Azurite, no MCP mocks in the cloud image. The replay reproduces all the externally-visible effects without them.
- No Mem0/Chroma in the cloud either — the lessons + memories come from the tape's snapshot, not a live store.
- No auth on the public surface. Read-only middleware is the only barrier.
- The `.poc-safety` marker stays in place — it specifically warns about writes; this deploy is reads-only and the marker text gets a bullet "exception: read-only replay mode is safe for public ingress".

## Open questions for the reviewer
- **Tape size budget?** 2 h of activity with 35 active domains generates ~50k events × ~500 B/event = ~25 MB raw, ~3–5 MB gzipped. Fine to bake into the image.
- **Recording cadence for state snapshots inside the 2 h?** Default plan: take the snapshot only at `t=0`, derive all later state via mutation log. If the mutation log proves unstable, fallback to snapshotting every 5 min.
- **Domain detail pages that hit `/internal/durable-event` write endpoints** (resolution timeline, action ledger persistence) — these are operator-driven and already return 403 in replay. Verify the drawer degrades gracefully.

## Effort estimate
| Phase | Days |
|---|---|
| 0. **Delete dead policy surface** — `api/shared/policies.yaml`, `AutonomyPolicy` model, old `/api/policy` routes | 0.5 |
| 1. Recorder + tape format + minimal CLI (incremental: 5 min smoke → 30 min → 2 h) | 1.0 |
| 2. Replayer + bus event timing + state hydration + hard-reset loop | 1.5 |
| 3. Read-only middleware + 403 toast handling | 0.5 |
| 4. Replay badge in header + restart banner + essay↔demo CTAs | 0.5 |
| 5. **Governance dashboard** — `/api/governance/matrix` + `/api/governance/policy_changes/recent` + new `/policy` table with live diff pulse | 1.5 |
| 6. **Kernel hot-reload** — file-watcher + `reload_policies()` + `governance.matrix.reloaded` bus event + dashboard banner | 0.5 |
| 7. Multi-process Container image + nginx config + deploy workflow | 1.0 |
| 8. Record a real 2-h tape locally with DEMO_LOUD=1 + smoke test | 0.5 |
| 9. Cloud deploy + verification + DNS / TLS sanity | 0.5 |
| **Total** | **~7.5 days** |

## Verification
- Replayer pytest sweep: snapshot → replay → assert REST + SSE match recorded shape at each tick.
- Read-only middleware test: every POST returns 403 with the friendly message.
- Playwright E2E against `localhost` with `ZAVA_MODE=replay` and a test tape: visit `/`, see the badge, drill into a workflow drawer, see phases populated from the snapshot, watch the SSE events arrive, see the restart banner at EOT.
- Cloud smoke test once deployed: hit the FQDN, capture a screenshot, verify the badge text matches the tape `meta.json`.

## Success criteria
- A visitor opens the FQDN cold, lands on the control plane, sees workflows scrolling in real time, can click any of them and see their full detail, watches a dream pass fire and lesson satellites appear on the constellation, can browse every route, every action they try produces a polite toast.
- No LLM calls made by the running cloud container.
- Operating cost ≤ $20/day at low traffic.
- Visitor cannot crash, drown, or mutate the substrate.
