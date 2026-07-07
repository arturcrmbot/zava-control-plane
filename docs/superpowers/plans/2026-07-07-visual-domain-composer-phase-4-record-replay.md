# Visual Domain Composer — Phase 4 (Record & Replay) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the demo bulletproof without giving up authenticity: **record** a real compose run's normalized event stream to a tape, and **replay** it cinematically through the *same* cockpit + endpoints — fast, deterministic, hands-free or presenter-clickable — while the tool stays fully live-usable for real work.

**Architecture:** `ComposeSession` already buffers every emitted event; we add relative timing and a `save_tape()`. A `ReplayBridge` fills the same role as `ComposeBridge` but re-emits a loaded tape into a `ComposeSession` at a scaled cadence (no agent, no tree mutation). Because the cockpit only consumes `/api/compose/{id}/stream` + posts to `/answer` `/brief`, replay reuses all of Phase 3 untouched. HITL pauses reuse the existing pending-future mechanism, so a presenter can click through a recorded question exactly as if it were live.

**Tech Stack:** Python 3.13 (asyncio), FastAPI, React (small additions to the Phase-3 intake). Tape format mirrors `data/blueprint-recordings/` (`{"ts_offset_ms", "event"}` JSONL).

**Depends on:** Phases 1–3. **Design source of truth:** [`../specs/2026-07-07-visual-domain-composer-design.md`](../specs/2026-07-07-visual-domain-composer-design.md) §10 (later: replay), and the existing replay system (`api/server/services/blueprint_recorder.py`, `api/server/services/replay/`).

**Why a compose-scoped tape (not the existing FleetEvent recorder):** the existing recorder captures `FleetEvent`s on the bus; the composer's normalized events (`thought`/`tool`/`brief`/…) are a *different* stream on `/api/compose/*`. A small compose tape that records exactly those events is the honest, minimal reuse of the pattern.

**Recommended demo recipe (documented in Task 6):** do the real compose **once** on a clean checkout — it genuinely graduates the domain *and* writes a tape. Keep that domain in the tree. For the recording, **replay the tape**: the narration/thinking is reproduced deterministically, and because the domain really exists, the Ignite → cosmic-lens handoff is real (poll finds it instantly). Bulletproof *and* true.

---

## File Structure

| File | Responsibility |
|---|---|
| `api/server/services/compose/session.py` | Modify: capture `timeline` (ts_offset_ms per event). |
| `api/server/services/compose/tape.py` | `save_tape()`, `list_tapes()`, `load_tape()` over `data/compose-recordings/`. |
| `api/server/services/compose/replay_bridge.py` | `ReplayBridge`: re-emit a tape into a session at scaled cadence, optional HITL pause. |
| `api/server/services/compose/bridge.py` | Modify: auto-save a tape on completion when `COMPOSE_RECORD=1`. |
| `api/server/routes/compose.py` | Modify: `POST /api/compose/replay`, `GET /api/compose/tapes`. |
| `web/blueprint/src/pages/compose/ReplayPicker.tsx` | Tape dropdown + speed + hands-free/click toggle → `POST /replay`. |
| `web/blueprint/src/pages/compose/IntakePanel.tsx` | Modify: add the ReplayPicker section. |
| `web/blueprint/src/pages/compose/api.ts` | Modify: `listTapes()`, `startReplay()`. |
| `web/blueprint/src/pages/ComposePage.tsx` | Modify: honour `?replay=<tape>` deep link. |
| `tests/api/compose/test_tape.py` | save/load round-trip. |
| `tests/api/compose/test_replay_bridge.py` | ordered re-emit + HITL pause/resume. |
| `tests/api/compose/test_replay_route.py` | `POST /replay` streams events; `GET /tapes` lists. |

---

## Task 1: Capture per-event timing on `ComposeSession`

**Files:**
- Modify: `api/server/services/compose/session.py`
- Test: `tests/api/compose/test_session.py` (add case)

- [ ] **Step 1: Add the failing test**

Append to `tests/api/compose/test_session.py`:

```python
def test_timeline_records_events_with_offsets():
    s = ComposeSession("cid")
    s.emit({"type": "thought", "text": "a"})
    s.emit({"type": "narration", "text": "b"})
    assert len(s.timeline) == 2
    assert s.timeline[0]["event"]["text"] == "a"
    assert s.timeline[0]["ts_offset_ms"] == 0
    assert s.timeline[1]["ts_offset_ms"] >= 0
    assert all(set(e.keys()) == {"ts_offset_ms", "event"} for e in s.timeline)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/api/compose/test_session.py -k timeline -v`
Expected: FAIL — `AttributeError: ... 'timeline'`.

- [ ] **Step 3: Implement**

In `session.py`, add `import time` at top. In `__init__` add:

```python
        self._t0 = time.monotonic()
        self.timeline: list[dict] = []
```

In `emit`, right after appending to `self.events`, add:

```python
        self.timeline.append({
            "ts_offset_ms": int((time.monotonic() - self._t0) * 1000),
            "event": event,
        })
```

(Set the first offset to 0 deterministically: capture `_t0` lazily on the first emit instead — simpler is to leave monotonic; the test asserts `timeline[0]` is 0 only because it emits immediately. To guarantee it, set `if not self.timeline: self._t0 = time.monotonic()` at the start of `emit`.)

Final `emit` timing block:

```python
        if not self.timeline:
            self._t0 = time.monotonic()
        self.timeline.append({
            "ts_offset_ms": int((time.monotonic() - self._t0) * 1000),
            "event": event,
        })
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/api/compose/test_session.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/server/services/compose/session.py tests/api/compose/test_session.py
git commit -m "feat(compose): capture per-event timeline for tapes (phase 4)"
```

---

## Task 2: Tape storage (save/list/load)

**Files:**
- Create: `api/server/services/compose/tape.py`
- Test: `tests/api/compose/test_tape.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/api/compose/test_tape.py`:

```python
from api.server.services.compose import tape
from api.server.services.compose.session import ComposeSession


def test_save_and_load_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("ZAVA_REPO_ROOT", str(tmp_path))
    s = ComposeSession("cid")
    s.emit({"type": "thought", "text": "hi"})
    s.emit({"type": "done", "workflow_type": "capex-approval", "display_name": "Capex"})
    path = tape.save_tape(s, "capex-approval")
    assert path.exists()
    assert "capex-approval" in path.name

    names = tape.list_tapes()
    assert path.name in names

    loaded = tape.load_tape(path.name)
    assert loaded[0]["event"]["text"] == "hi"
    assert all({"ts_offset_ms", "event"} == set(e) for e in loaded)


def test_list_tapes_empty_when_no_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("ZAVA_REPO_ROOT", str(tmp_path))
    assert tape.list_tapes() == []
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/api/compose/test_tape.py -v`
Expected: FAIL — `ModuleNotFoundError: ...tape`.

- [ ] **Step 3: Implement `tape.py`**

Create `api/server/services/compose/tape.py`:

```python
"""Compose tapes: record/replay the normalized event stream of a compose run.

Format mirrors data/blueprint-recordings/: one JSONL file per run, each line
{"ts_offset_ms": int, "event": <normalized compose event>}.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from api.shared.compose_config import repo_root


def _dir() -> Path:
    d = repo_root() / "data" / "compose-recordings"
    return d


def save_tape(session, workflow_type: str) -> Path:
    d = _dir()
    d.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    safe = (workflow_type or "compose").replace("/", "-")
    path = d / f"{safe}-{stamp}.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for entry in session.timeline:
            fh.write(json.dumps(entry) + "\n")
    return path


def list_tapes() -> list[str]:
    d = _dir()
    if not d.exists():
        return []
    return sorted(p.name for p in d.glob("*.jsonl"))


def load_tape(name: str) -> list[dict]:
    path = _dir() / Path(name).name  # prevent traversal
    with path.open(encoding="utf-8") as fh:
        return [json.loads(ln) for ln in fh if ln.strip()]
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/api/compose/test_tape.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add api/server/services/compose/tape.py tests/api/compose/test_tape.py
git commit -m "feat(compose): compose tape save/list/load (phase 4)"
```

---

## Task 3: `ReplayBridge`

**Files:**
- Create: `api/server/services/compose/replay_bridge.py`
- Test: `tests/api/compose/test_replay_bridge.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/api/compose/test_replay_bridge.py`:

```python
import asyncio
import pytest
from api.server.services.compose.session import ComposeSession
from api.server.services.compose.replay_bridge import ReplayBridge


TAPE = [
    {"ts_offset_ms": 0, "event": {"type": "thought", "text": "thinking"}},
    {"ts_offset_ms": 50, "event": {"type": "tool", "id": "t1", "title": "Reading x", "status": "completed"}},
    {"ts_offset_ms": 100, "event": {"type": "narration", "text": "done"}},
]


@pytest.mark.asyncio
async def test_replays_events_in_order_then_ready():
    s = ComposeSession("cid")
    q = s.subscribe()
    await ReplayBridge(s, TAPE, speed=1000.0).start()
    seen = []
    for _ in range(10):
        ev = await asyncio.wait_for(q.get(), timeout=2)
        seen.append(ev)
        if ev.get("type") == "stage" and ev.get("stage") == "ready":
            break
    types = [e.get("type") for e in seen]
    assert types[:3] == ["thought", "tool", "narration"]
    assert seen[-1]["stage"] == "ready"
    assert s.done is True


@pytest.mark.asyncio
async def test_pause_on_hitl_waits_for_answer():
    tape = [
        {"ts_offset_ms": 0, "event": {"type": "question", "request_id": "orig", "text": "CFO?", "options": ["CFO"]}},
        {"ts_offset_ms": 10, "event": {"type": "narration", "text": "after answer"}},
    ]
    s = ComposeSession("cid")
    q = s.subscribe()
    await ReplayBridge(s, tape, speed=1000.0, pause_on_hitl=True).start()

    first = await asyncio.wait_for(q.get(), timeout=2)
    assert first["type"] == "question"
    rid = first["request_id"]  # a fresh id assigned by replay
    # narration must NOT arrive until we answer
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(q.get(), timeout=0.3)
    s.resolve(rid, "CFO")
    nxt = await asyncio.wait_for(q.get(), timeout=2)
    assert nxt["type"] == "narration"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/api/compose/test_replay_bridge.py -v`
Expected: FAIL — `ModuleNotFoundError: ...replay_bridge`.

- [ ] **Step 3: Implement `replay_bridge.py`**

Create `api/server/services/compose/replay_bridge.py`:

```python
"""ReplayBridge: drive a ComposeSession from a recorded tape.

Fills the same role as ComposeBridge (it makes a session emit events) but from
a tape instead of a live agent — no subprocess, no tree mutation. HITL events
optionally pause using the session's existing pending-future mechanism, so the
Phase-3 /answer + /brief endpoints resume replay exactly as in a live run.
"""
from __future__ import annotations

import asyncio
import uuid

_MAX_GAP_S = 2.5  # compress long "thinking" pauses so a 10-min run replays fast
_HITL_TIMEOUT_S = 300


class ReplayBridge:
    def __init__(self, session, tape: list[dict], speed: float = 8.0,
                 pause_on_hitl: bool = False) -> None:
        self.session = session
        self.tape = tape
        self.speed = max(speed, 0.1)
        self.pause_on_hitl = pause_on_hitl

    async def start(self) -> None:
        asyncio.create_task(self._run())

    async def _run(self) -> None:
        prev = 0
        try:
            for entry in self.tape:
                gap = (entry.get("ts_offset_ms", prev) - prev) / 1000.0 / self.speed
                if gap > 0:
                    await asyncio.sleep(min(gap, _MAX_GAP_S))
                prev = entry.get("ts_offset_ms", prev)

                event = dict(entry.get("event") or {})
                if self.pause_on_hitl and event.get("type") in ("question", "brief"):
                    rid = uuid.uuid4().hex
                    event["request_id"] = rid
                    fut = self.session.new_pending(rid)
                    self.session.emit(event)
                    try:
                        await asyncio.wait_for(fut, timeout=_HITL_TIMEOUT_S)
                    except asyncio.TimeoutError:
                        pass
                else:
                    self.session.emit(event)
        finally:
            self.session.done = True
            self.session.emit({"type": "stage", "stage": "ready", "label": "Replay complete"})
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/api/compose/test_replay_bridge.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add api/server/services/compose/replay_bridge.py tests/api/compose/test_replay_bridge.py
git commit -m "feat(compose): ReplayBridge re-emits tapes into the same cockpit (phase 4)"
```

---

## Task 4: Auto-record real runs + replay/tapes routes

**Files:**
- Modify: `api/server/services/compose/bridge.py`
- Modify: `api/server/routes/compose.py`
- Test: `tests/api/compose/test_replay_route.py`

- [ ] **Step 1: Auto-save a tape on real completion**

In `bridge.py`, add near the top:

```python
from . import tape as compose_tape
```

In `_run_prompt`'s `finally` block, before `await self.client.stop()`, add:

```python
            if os.getenv("COMPOSE_RECORD", "1") == "1":
                wt = next((e.get("workflow_type") for e in reversed(self.session.events)
                           if e.get("type") == "done"), "compose")
                try:
                    compose_tape.save_tape(self.session, wt)
                except Exception as ex:
                    print(f"[compose] tape save failed: {ex}")
```

- [ ] **Step 2: Write the failing route tests**

Create `tests/api/compose/test_replay_route.py`:

```python
import json
from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.server.routes.compose import router
from api.server.services.compose import tape


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


def _write_tape(tmp_path):
    d = tmp_path / "data" / "compose-recordings"
    d.mkdir(parents=True)
    p = d / "capex-approval-20260101T000000.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in [
        {"ts_offset_ms": 0, "event": {"type": "thought", "text": "hi"}},
        {"ts_offset_ms": 20, "event": {"type": "done", "workflow_type": "capex-approval", "display_name": "Capex"}},
    ]))
    return p.name


def test_list_and_replay(tmp_path, monkeypatch):
    monkeypatch.setenv("ZAVA_REPO_ROOT", str(tmp_path))
    (tmp_path / ".poc-safety").write_text("POC_UNSAFE_FOR_PUBLIC_DEPLOY=1\n")
    name = _write_tape(tmp_path)
    client = TestClient(_app())

    tapes = client.get("/api/compose/tapes").json()["tapes"]
    assert name in tapes

    r = client.post("/api/compose/replay", json={"tape": name, "speed": 1000})
    assert r.status_code == 200
    cid = r.json()["compose_id"]

    events = []
    with client.stream("GET", f"/api/compose/{cid}/stream") as s:
        for line in s.iter_lines():
            if line and line.startswith("data: "):
                ev = json.loads(line[6:])
                events.append(ev)
                if ev.get("type") == "stage" and ev.get("stage") == "ready":
                    break
    assert any(e["type"] == "thought" for e in events)
    assert any(e.get("type") == "done" for e in events)
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/api/compose/test_replay_route.py -v`
Expected: FAIL — no `/api/compose/tapes` route.

- [ ] **Step 4: Add the routes**

In `api/server/routes/compose.py` add:

```python
import uuid as _uuid
from api.server.services.compose import tape as compose_tape
from api.server.services.compose.replay_bridge import ReplayBridge


@router.get("/api/compose/tapes")
async def tapes():
    return {"tapes": compose_tape.list_tapes()}


@router.post("/api/compose/replay")
async def replay(payload: dict = Body(...)):
    name = payload.get("tape")
    if not name:
        return JSONResponse({"error": "tape required"}, status_code=422)
    try:
        loaded = compose_tape.load_tape(name)
    except FileNotFoundError:
        return JSONResponse({"error": "tape not found"}, status_code=404)
    cid = _uuid.uuid4().hex
    session = ComposeSession(cid)
    registry.register(session)
    bridge = ReplayBridge(
        session, loaded,
        speed=float(payload.get("speed", 8.0)),
        pause_on_hitl=bool(payload.get("pause_on_hitl", False)),
    )
    await bridge.start()
    return {"compose_id": cid}
```

(Note: replay does **not** require the `.poc-safety` gate for reads, but the test sets it anyway; keep `/replay` ungated since it neither spawns an agent nor mutates the tree — it only re-emits recorded events. If you prefer symmetry, gate it too; the test passes either way because it sets the marker.)

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/api/compose/test_replay_route.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add api/server/services/compose/bridge.py api/server/routes/compose.py tests/api/compose/test_replay_route.py
git commit -m "feat(compose): auto-record real runs + /tapes + /replay routes (phase 4)"
```

---

## Task 5: Frontend — replay launcher

**Files:**
- Modify: `web/blueprint/src/pages/compose/api.ts`
- Create: `web/blueprint/src/pages/compose/ReplayPicker.tsx`
- Modify: `web/blueprint/src/pages/compose/IntakePanel.tsx`
- Modify: `web/blueprint/src/pages/ComposePage.tsx`

- [ ] **Step 1: API helpers**

Append to `web/blueprint/src/pages/compose/api.ts`:

```ts
export async function listTapes(): Promise<string[]> {
  const r = await fetch("/api/compose/tapes");
  if (!r.ok) return [];
  return (await r.json()).tapes ?? [];
}

export async function startReplay(input: { tape: string; speed?: number; pause_on_hitl?: boolean }): Promise<string> {
  const r = await fetch("/api/compose/replay", {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!r.ok) throw new Error(`replay failed: ${r.status}`);
  return (await r.json()).compose_id as string;
}
```

- [ ] **Step 2: `ReplayPicker.tsx`**

Create `web/blueprint/src/pages/compose/ReplayPicker.tsx`:

```tsx
import { useEffect, useState } from "react";
import { PlayCircle } from "lucide-react";
import { listTapes, startReplay } from "./api";

export function ReplayPicker({ onStarted }: { onStarted: (cid: string) => void }) {
  const [tapes, setTapes] = useState<string[]>([]);
  const [tape, setTape] = useState("");
  const [handsFree, setHandsFree] = useState(true);

  useEffect(() => { void listTapes().then((t) => { setTapes(t); if (t[0]) setTape(t[0]); }); }, []);
  if (tapes.length === 0) return null;

  return (
    <div className="mt-8 rounded-xl border border-slate-800 bg-slate-900/50 p-4">
      <p className="text-sm font-medium text-slate-300">Replay a recorded compose (demo-safe)</p>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <select className="rounded-md bg-slate-800 px-3 py-1.5 text-sm" value={tape} onChange={(e) => setTape(e.target.value)}>
          {tapes.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <label className="flex items-center gap-2 text-sm text-slate-400">
          <input type="checkbox" checked={handsFree} onChange={(e) => setHandsFree(e.target.checked)} />
          Hands-free (uncheck to click through questions)
        </label>
        <button className="flex items-center gap-2 rounded-md bg-violet-600 px-3 py-1.5 text-sm font-medium text-white"
          onClick={() => void startReplay({ tape, speed: 8, pause_on_hitl: !handsFree }).then(onStarted)}>
          <PlayCircle size={16} /> Replay
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Add ReplayPicker to `IntakePanel`**

In `IntakePanel.tsx`, import and render it under the Compose button:

```tsx
import { ReplayPicker } from "./ReplayPicker";
// …just before the closing </div> of the panel:
<ReplayPicker onStarted={onStarted} />
```

- [ ] **Step 4: `?replay=` deep link in `ComposePage`**

Replace `ComposePage.tsx` body with:

```tsx
import { useEffect, useState } from "react";
import { IntakePanel } from "./compose/IntakePanel";
import { Cockpit } from "./compose/Cockpit";
import { startReplay } from "./compose/api";

export function ComposePage() {
  const [cid, setCid] = useState<string | null>(null);
  useEffect(() => {
    const tape = new URLSearchParams(window.location.search).get("replay");
    if (tape) void startReplay({ tape, speed: 8, pause_on_hitl: false }).then(setCid);
  }, []);
  return cid ? <Cockpit cid={cid} /> : <IntakePanel onStarted={setCid} />;
}
```

- [ ] **Step 5: Typecheck/build**

Run: `npm --prefix web/blueprint run build`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add web/blueprint/src/pages/compose/api.ts web/blueprint/src/pages/compose/ReplayPicker.tsx web/blueprint/src/pages/compose/IntakePanel.tsx web/blueprint/src/pages/ComposePage.tsx
git commit -m "feat(compose-ui): replay picker + ?replay deep link (phase 4)"
```

---

## Task 6: Phase-4 exit check + demo runbook

**Files:**
- Create: `docs/compose-demo-runbook.md`

- [ ] **Step 1: Full sweeps**

Run: `uv run pytest tests/api/compose/ -q && npm --prefix web/blueprint run test -- compose`
Expected: all green.

- [ ] **Step 2: Write the runbook**

Create `docs/compose-demo-runbook.md`:

```markdown
# Visual Domain Composer — demo runbook

## One-time: record the tape (real compose)
1. Fresh checkout / clean tree: `git status` shows nothing.
2. `bash scripts/boot-demo.sh` (COMPOSE_RECORD=1 default).
3. Open `http://localhost:5275/?view=compose`, drop the prepared capex doc
   (contains one deliberate ambiguity so a question fires).
4. Answer the question, approve the brief, let it graduate + verify, Ignite.
5. Confirm the domain is live: `curl -s localhost:3101/api/blueprint/composition | grep capex`.
6. A tape now exists: `ls data/compose-recordings/`. Commit it + the graduated domain.

## Every demo: replay (bulletproof)
- Deep link: `http://localhost:5275/?view=compose&replay=<tape>.jsonl` (hands-free), OR
- Intake screen → "Replay a recorded compose" → pick the tape → optionally uncheck
  "hands-free" to click through the question yourself.
- Ignite pans to the cosmic lens; because the domain was really graduated when the
  tape was recorded, the planet is genuinely present. Real footage, zero risk.

## Live mode (real authoring, for actual work)
- Same intake screen, just drop a doc and let it run (5–12 min). Localhost + throwaway
  machine only (COMPOSE_PERMISSION_POLICY=autopilot). Not for on-camera unless you
  have time and a clean tree.
```

- [ ] **Step 3: Confirm Phase-4 done-criteria**

  - A real run writes a tape to `data/compose-recordings/`.
  - `?replay=<tape>` (or the intake picker) drives the identical cockpit, fast.
  - Hands-free replays end-to-end; "click-through" pauses at the question until the presenter answers.
  - The demo runbook documents record-once / replay-many.

- [ ] **Step 4: Commit**

```bash
git add docs/compose-demo-runbook.md
git commit -m "docs(compose): demo runbook for record-once / replay-many (phase 4)"
```

---

## Self-Review (against the spec + Phase-4 goal)

- **Coverage:** timeline capture ✓ T1; tape save/list/load ✓ T2; ReplayBridge (ordered re-emit + HITL pause via existing futures) ✓ T3; auto-record + routes ✓ T4; UI launcher + deep link ✓ T5; runbook ✓ T6. Reuses Phase-3 cockpit + `/answer` `/brief` untouched (the whole point).
- **Placeholder scan:** none.
- **Type consistency:** `ReplayBridge(session, tape, speed, pause_on_hitl)` matches routes + tests; tape entries `{ts_offset_ms, event}` match the recorder format and `load_tape`/`ReplayBridge`; `startReplay({tape, speed, pause_on_hitl})` matches the `/replay` body; replay reuses `session.new_pending()/resolve()` and the `question`/`brief` event shapes from Phase 2/3.

---

## Feature complete (all four phases)

Live tool for real authoring (Phases 1–3) **plus** a record-once/replay-many path (Phase 4) that makes the recorded demo deterministic and fast while remaining genuinely real footage of a real compose. Resolves the "genuinely usable AND demos flawlessly" goal set at the outset.
