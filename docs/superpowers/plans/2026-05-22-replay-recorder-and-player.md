# Plan B — Replay Recorder + Player + Read-Only Mode

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `ZAVA_MODE=record` to capture a tape of live substrate activity, `ZAVA_MODE=replay` to load + replay a tape at wall-clock pace, and a read-only middleware that blocks all writes in replay mode. Visitors get a header badge + a 3-second restart banner on loop. Locally proven; cloud deploy is Plan C.

**Architecture:** Tape is a gzip-tar containing `meta.json`, `snapshot_t0/*.json` (REST-shaped state at recording start), `events.ndjson` (bus events with `t` seconds-since-start), `mutations.ndjson` (state deltas). Recorder taps the EventBus and a new MutationBus; Player loads the snapshot into in-memory stores, ticks events at real-time pace, applies mutations on cue, on EOT emits a banner event, sleeps 3 s, re-hydrates from t=0.

**Tech Stack:** Python stdlib (`tarfile`, `asyncio`, `json`) · FastAPI middleware · React (badge + banner + 403 toast hook) · existing SSE relay.

**Spec:** `docs/superpowers/specs/2026-05-22-public-replay-landing-design.md` (sections: "Tape format", "Recorder", "Replayer", "Read-only middleware", "Front-end changes", recording cadence + DEMO_LOUD note).

---

## Phase 1 — Tape format + snapshot writer

### Task 1.1: Tape format Pydantic models

**Files (create):**
- `api/server/services/replay/__init__.py`
- `api/server/services/replay/tape_format.py`
- `tests/api/server/services/replay/test_tape_format.py`

- [ ] Test: `TapeMeta`, `EventRecord`, `MutationRecord` round-trip through `model_dump` ↔ `model_validate`. Constants: `META_NAME = "meta.json"`, `SNAPSHOT_DIR = "snapshot_t0/"`, `EVENTS_NAME = "events.ndjson"`, `MUTATIONS_NAME = "mutations.ndjson"`, `TAPE_FORMAT_VERSION = 1`.
- [ ] Implement the three Pydantic models + the layout constants. `EventRecord.t` is float seconds since recording start; `MutationRecord.op ∈ {upsert, delete}`; `kind ∈ {workflow, exception, memory, lesson, decision, insight, entity, audit}`.
- [ ] Commit: `feat(replay): tape format Pydantic schemas`.

### Task 1.2: Snapshot writer

**Files (create):**
- `api/server/services/replay/snapshot.py`
- `tests/api/server/services/replay/test_snapshot.py`

- [ ] Test: `take_snapshot(out_dir)` writes `workflows.json`, `exceptions.json`, `personae.json`, `functions.json`, `memories.json`, `lessons.json`, `kpis.json`, `audit_summary.json`. Each is valid JSON.
- [ ] Implement: walk `app_state.store.list_workflows()`, `list_exceptions()`, `PERSONA_DEFINITIONS`, `FUNCTIONS`, `app_state.domain_memories[*].list_all()` (split into `memories.json` for working entries + `lessons.json` for distilled), audit counts. Use `model_dump(by_alias=True, mode="json")` for camelCase parity with the REST routes.
- [ ] Verify: `python -c "from api.server.services.replay.snapshot import take_snapshot; from pathlib import Path; print(take_snapshot(Path('/tmp/snap')))"` dumps the expected file list.
- [ ] Commit: `feat(replay): snapshot writer for t=0 REST state`.

---

## Phase 2 — Mutation taps + Recorder

### Task 2.1: MutationBus

**Files (create):**
- `api/server/services/replay/mutation_bus.py`
- `tests/api/server/services/replay/test_mutation_bus.py`

- [ ] Test: `set_active_bus(bus)` + `get_active_bus()` works as a process-global tee; emits are noop when no bus is active; emitted entries carry `op`, `kind`, `id`, `patch`.
- [ ] Implement: minimal class + module-level singleton accessor.
- [ ] Commit: `feat(replay): MutationBus tee`.

### Task 2.2: Wire state-store mutation taps

**Files (modify):**
- `api/server/services/state_store.py` — `upsert_workflow`, `upsert_exception`.
- `api/server/services/memory/domain_memory.py` — `add`, `add_distilled`, `delete`.

- [ ] After each successful write, call `get_active_bus()`; if present, `bus.emit(op, kind, id, patch)`. Wrap in try/except so a bus failure never breaks the write.
- [ ] Test: with an active bus, a single `upsert_workflow` produces exactly one mutation entry; with no active bus, zero mutations.
- [ ] Commit: `feat(replay): mutation taps on StateStore + DomainMemory`.

### Task 2.3: Recorder service

**Files (create):**
- `api/server/services/replay/recorder.py`
- `tests/api/server/services/replay/test_recorder.py`

- [ ] Test: `Recorder.start()` snapshots state, subscribes to bus. Two events arrive; `Recorder.stop()` finalises a tarball containing `meta.json`, `events.ndjson` (with both events in order with `t` offsets), `mutations.ndjson`, `snapshot_t0/*.json`.
- [ ] Implement: on `start()` create temp dir, snapshot, subscribe to `app_state.bus.on_any`, set active `MutationBus`. Maintain in-memory `events` + `mutations` lists. Every 5 min, flush to disk (crash-safe). On `stop()` cancel flush task, unsubscribe, write `meta.json` with `duration_s`, `recorded_at`, `tape_id`, pack to `out_path`.
- [ ] Commit: `feat(replay): Recorder service`.

### Task 2.4: CLI `scripts/record_tape.sh`

**Files (create):**
- `scripts/_record_entrypoint.py`
- `scripts/record_tape.sh`

- [ ] Entrypoint: imports `app_state` (triggers init), constructs Recorder, registers SIGINT/SIGTERM handlers, enforces a minimum duration. CLI args: `--out`, `--min-seconds`.
- [ ] Shell script: parses `DURATION=5m|30m|2h` env var → seconds; exports `DEMO_LOUD=1 DREAM_PASS_DEMO_CADENCE_SECONDS=180 DREAM_PASS_TRIGGER_BACKLOG=5 MEMORY_DOMAINS=hiring ZAVA_APP_SHA=$(git rev-parse --short HEAD)`; runs the entrypoint via `uv run python`.
- [ ] Smoke: `DURATION=10s OUT=tapes/test.tar.gz scripts/record_tape.sh`; SIGINT after 12 s; `tar tzf tapes/test.tar.gz` shows the expected layout.
- [ ] Commit: `feat(replay): scripts/record_tape.sh`.

---

## Phase 3 — Player + replay mode

### Task 3.1: TapeLoader

**Files (create):**
- `api/server/services/replay/tape_loader.py`
- `tests/api/server/services/replay/test_tape_loader.py`

- [ ] Test: building a minimal tape on disk, `TapeLoader(path).load()` populates `.meta`, `.snapshot[name]` (eager dict of parsed JSON), and `iter_events()` / `iter_mutations()` yield records in `t` order.
- [ ] Implement: extract tar to a temp dir on `load()`, parse meta, eager-load all snapshot files into a dict keyed by filename. NDJSON streams are lazy generators.
- [ ] Commit: `feat(replay): TapeLoader`.

### Task 3.2: State hydration

**Files (create):**
- `api/server/services/replay/hydrate.py`
- `tests/api/server/services/replay/test_hydrate.py`

- [ ] Test: starting from an empty `app_state`, `hydrate_from_snapshot(loader)` populates workflows + domain memories such that `app_state.store.list_workflows()` and `domain_memories[d].list_all()` match the snapshot.
- [ ] Implement: wipe stores, push each record back via the normal upsert path BUT with `MutationBus` disabled (set bus to None during hydrate so the hydrate doesn't get re-logged). Restore prior bus on exit.
- [ ] Commit: `feat(replay): hydrate_from_snapshot`.

### Task 3.3: Player — tick events + apply mutations + loop

**Files (create):**
- `api/server/services/replay/player.py`
- `tests/api/server/services/replay/test_player.py`

- [ ] Test: with a tape of two events at t=1.0 and t=3.0, the player emits them on `app_state.bus` in order with the correct timing (use monkeypatched `time.monotonic`).
- [ ] Test (loop): at EOT (`current_t >= duration_s`), the player emits `playback.restart.pending`, sleeps 3 s, re-hydrates, resets clock, continues. Total events emitted over two iterations = 2 × tape events + 2 × `playback.restart.pending`.
- [ ] Implement: asyncio task loop. Maintain `events_remaining` deque and `mutations_remaining` deque. Sleep until next `t`, apply mutation (if mutation's `t` is the smallest), or emit event (if event's `t` is smallest). Expose `current_t()`, `meta`, `stop()`.
- [ ] Commit: `feat(replay): Player with loop`.

### Task 3.4: `ZAVA_MODE=replay` wiring

**Files (create/modify):**
- `api/server/services/replay/mode.py` — `is_replay()` helper.
- `api/server/state.py` — gate cadence loops + simulator + persona insight/sweep loops on `not is_replay()`.
- `api/server/main.py` — in lifespan, if `is_replay()`, build TapeLoader from `ZAVA_TAPE_PATH`, hydrate, start Player task; teardown cancels the task.

- [ ] Test: with `ZAVA_MODE=replay`, the simulator's autonomous loop does not start; the Player task does start.
- [ ] Smoke: `ZAVA_MODE=replay ZAVA_TAPE_PATH=tapes/test.tar.gz uv run uvicorn api.server.main:app --port 3199`; `curl /api/workflows` returns the snapshot's workflows; `curl -N /api/blueprint/stream` shows replayed events.
- [ ] Commit: `feat(replay): ZAVA_MODE=replay boots Player + disables write loops`.

---

## Phase 4 — Read-only middleware + 403 toast

### Task 4.1: FastAPI middleware

**Files (create):**
- `api/server/middleware/__init__.py`
- `api/server/middleware/replay_readonly.py`
- `tests/api/server/middleware/test_replay_readonly.py`

- [ ] Test: in replay mode, every POST/PUT/PATCH/DELETE returns 403 with `{"error": "replay", "message": "This is a replay — actions are observed, not made."}`. GET/HEAD/OPTIONS pass through.
- [ ] Implement: `BaseHTTPMiddleware`; reads `is_replay()` per request (so toggle-at-runtime works for tests).
- [ ] Wire in `api/server/main.py` after CORS, only when `is_replay()`.
- [ ] Commit: `feat(replay): read-only middleware in replay mode`.

### Task 4.2: Front-end 403 toast hook

**Files (modify):**
- `web/client/lib/api.ts` (or wherever the fetch wrapper lives — discover via grep).
- `web/client/components/ToastProvider.tsx` (confirm shape, add helper if needed).

- [ ] When a non-GET response has `status === 403` and body `error === "replay"`, fire a toast with `body.message` and resolve the call as a no-op.
- [ ] Test: with a mocked fetch returning the 403 shape, the toast queue contains the message.
- [ ] Commit: `feat(replay): friendly toast on 403 replay response`.

---

## Phase 5 — Replay UI (badge, banner, essay CTAs)

### Task 5.1: `/api/replay/meta` endpoint

**Files (create):** `api/server/routes/replay.py`, test.

- [ ] Test: in live mode returns `{mode: "live"}`; in replay mode returns `{mode: "replay", tape_id, recorded_at, duration_s, current_t}`.
- [ ] Implement: live branch is trivial; replay branch reads `current_player()` (a module-level accessor set by Player on start).
- [ ] Commit: `feat(replay): /api/replay/meta`.

### Task 5.2: `useReplayMeta` hook + `ReplayBadge` + `RestartBanner`

**Files (create):**
- `web/client/hooks/useReplayMeta.ts`
- `web/client/components/feed/ReplayBadge.tsx`
- `web/client/components/feed/RestartBanner.tsx`

- [ ] `useReplayMeta`: fetches on mount, polls every 30 s.
- [ ] `ReplayBadge`: renders nothing in live mode; in replay mode renders a small pill `● live replay — recorded <date>`. Click → modal explaining "this is a recorded 2-hour loop; all decisions were made by autonomous personae; the buttons you see are real but disabled — clicking them does nothing".
- [ ] `RestartBanner`: subscribes to `/api/blueprint/stream`; when `playback.restart.pending` arrives, shows a centered overlay `Replay restarting…` for 3 s then auto-dismisses.
- [ ] Test: each component renders correctly in both modes given mocked meta + mocked SSE.
- [ ] Commit: `feat(replay): ReplayBadge + RestartBanner + useReplayMeta`.

### Task 5.3: Wire badge + banner into shell

**Files (modify):**
- `web/client/components/feed/Header.tsx` — render `ReplayBadge` before the role switcher.
- `web/client/components/feed/FleetControlShell.tsx` — render `RestartBanner` once at the root.

- [ ] Verify with Playwright: in replay mode the badge is visible at `/`; in live mode it is not.
- [ ] Commit: `feat(replay): badge in header + banner at shell root`.

### Task 5.4: Bidirectional essay ↔ demo CTAs

**Files (modify):**
- `web/blueprint/src/sections/Closing.tsx` — add "Watch it run →" CTA linking to the ACA URL with `?from=essay`.
- `web/client/components/feed/Header.tsx` — add a "Read the essay →" link next to the replay badge, links to the GitHub Pages essay URL with `?from=demo`.

- [ ] Discover env config: confirm `VITE_DEMO_URL` and `VITE_ESSAY_URL` (or equivalent) — add if missing.
- [ ] Commit: `feat(replay): bidirectional essay↔demo CTAs`.

---

## Phase 6 — Record real tapes locally (manual)

This phase is operator-driven (Artur on the MacBook Pro). Output is a single committed tape file used by Plan C.

- [ ] **5-minute smoke** — `DURATION=5m OUT=tapes/smoke.tar.gz scripts/record_tape.sh`. Verify locally: `ZAVA_MODE=replay ZAVA_TAPE_PATH=tapes/smoke.tar.gz uv run uvicorn api.server.main:app --port 3199`, open `:3199`, confirm restart banner at ~5 min.
- [ ] **30-minute recording** — same.
- [ ] **2-hour landing tape** — `DURATION=2h OUT=tapes/landing.tar.gz scripts/record_tape.sh`.
- [ ] If `landing.tar.gz` > 25 MB, push to Azure Blob and set `ZAVA_TAPE_URL` in the container (Plan C will pull on boot). Otherwise commit directly.
- [ ] Commit: `tape: 2h landing recording $(date -u +%Y%m%d)`.

---

## Done criteria

- `scripts/record_tape.sh` produces valid tapes at 5 min / 30 min / 2 h durations.
- `ZAVA_MODE=replay ZAVA_TAPE_PATH=... uvicorn ...` boots and serves a fully-clickable read-only operator UI.
- In replay mode, every write returns 403 with the friendly message; the front-end shows a toast.
- The badge is visible in replay mode; on EOT the restart banner shows for 3 s and the loop continues.
- All pre-existing tests still pass; new tests cover all six replay services + the middleware + the endpoint.

## Estimate

| Phase | Days |
|---|---|
| 1 — format + snapshot | 1.0 |
| 2 — mutation taps + recorder + CLI | 1.0 |
| 3 — TapeLoader + hydrate + Player + mode wiring | 1.5 |
| 4 — middleware + toast | 0.5 |
| 5 — replay UI | 0.5 |
| 6 — record real tapes (manual) | 0.5 |
| **Total** | **~5.0** |
