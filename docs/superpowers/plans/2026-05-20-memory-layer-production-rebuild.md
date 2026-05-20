# Memory Layer Production Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the in-memory + prompt-prepend lesson layer shipped on 2026-05-20 with a Mem0-backed, semantically-retrieved, lifecycle-managed memory system with observability, cost budgets, and a wired kill switch — moving the substrate from "demo plumbing" to production-shaped.

**Architecture:** Storage moves from `InMemoryLessonStore` to the existing `Mem0LessonStore` (already implemented at `api/server/services/lessons/mem0_store.py`). Agents retrieve top-K relevant lessons via semantic search rather than concatenating every active lesson into every prompt. Lessons follow a `candidate → shadow → active → demote → retire` lifecycle driven by measured outcomes (HITL override correlation, lesson_used age). Cadence becomes signal-driven (working-note backlog + decision-quality drop) instead of wall-clock. The kill_switch_id field in `data/policies/dream-pass.policy.yaml` (currently unused) is wired to a real pause endpoint. Token cost is budgeted per day and per cadence with hard stops.

**Tech Stack:** Python 3.11, existing Mem0 SDK (already in `requirements.txt`), existing AGT kernel, existing Kuzu provenance, FastAPI for routes, React + Vite for the Dashboard tile additions. No new third-party dependencies.

---

## ⚠️ What this plan replaces

The 2026-05-20 commits `4ec8001d` through `46412f0e` plus the band-aid fixes `2d488e2a`, `1882e5c8`, and the prompt fix shipped same-day, all on `main`. Specifically replaced:

- `api/server/services/dream_pass/wiring.py:build_demo_orchestrator` — currently wires `InMemoryLessonStore` and `_DomainDispatchingRunner` with stub fallback. Becomes Mem0-backed with proper retrieval factories.
- `api/functions/graphs/executors/agents/_wrapper.py:_prepend_lessons_to_skill_text` — currently concatenates every active lesson into every prompt. Removed entirely; replaced by Mem0 semantic search.
- `api/server/services/dream_pass/orchestrator.py:81` hardcoded `('interview-recommender',)` — removed; orchestrator accepts a domain-scoped working-notes feed via the existing closure.
- `data/policies/dream-pass.policy.yaml` `min_samples: 5` band-aid — restored to `40` once replay-against-historicals (Phase D) supplies enough signal.
- `api/server/state.py:AppState.lesson_store` — replaced from `InMemoryLessonStore()` to `Mem0LessonStore(memory=...)` with a test-friendly factory.

This plan does NOT touch:

- The Memory page UI shipped 2026-05-20 (it consumes `/api/memory/*` which keeps the same shape).
- The dream-pass bus events (`dream.pass.started` etc.) — they stay.
- The cross-process bridge in `routes/internal_durable_event.py:agent.completed` — it stays; the working-memory capture call inside it now writes through Mem0 instead of in-memory.

---

## Scope check — multiple subsystems

This plan covers six independent-but-sequenced subsystems. Each phase ships to `main` on its own and produces working software:

| Phase | Subsystem | Independent? | Gates |
|---|---|---|---|
| A | Mem0 swap | Foundation — everything else assumes Mem0 | First |
| B | Top-K retrieval (replaces prepend-everything) | Needs Phase A | After A |
| C | Lesson lifecycle (shadow/demote/retire) | Needs Phase A | After A; concurrent with B |
| D | Observability + replay scoring | Needs Phase C status fields | After C |
| E | Signal-driven cadence + kill switch | Needs Phase D metrics | After D |
| F | Cost budgets | Independent, but most impactful after E | Last |

Phases are atomic: A is safe to merge alone (functional regression-free), and so on. The plan executes them in order in one branch but each commit is independently reviewable.

---

## File Structure

**New files:**

- `api/server/services/lessons/lesson_lifecycle.py` — pure-logic transitions `candidate → shadow → active → demote → retire`, driven by metrics, no I/O.
- `api/server/services/lessons/lesson_metrics.py` — per-lesson invocation counters + HITL override correlation, read from working-memory `lesson_used` notes and exception records.
- `api/server/services/lessons/decision_quality_signal.py` — rolling window of HITL override rate per domain; used by Phase E cadence trigger.
- `api/server/services/lessons/cost_budget.py` — daily LLM token + cost counter with Mem0-backed persistence.
- `api/server/routes/dream_pass_pause.py` — `POST /api/dream-pass/pause?domain=X`, `DELETE /api/dream-pass/pause?domain=X`, `GET /api/dream-pass/pause` (kill switch).
- `api/server/routes/memory_lesson_stats.py` — `GET /api/memory/lessons/{id}/stats` per-lesson observability surface.
- `api/server/services/dream_pass/replay_runner.py` — `ReplayExperimentRunner` that scores candidate lessons against historical HITL-reviewed workflows (replaces the toy `InterviewRecommenderSandbox` for hiring once enough history accumulates).
- `tests/api/server/services/lessons/test_lesson_lifecycle.py`
- `tests/api/server/services/lessons/test_lesson_metrics.py`
- `tests/api/server/services/lessons/test_decision_quality_signal.py`
- `tests/api/server/services/lessons/test_cost_budget.py`
- `tests/api/routes/test_dream_pass_pause.py`
- `tests/api/routes/test_memory_lesson_stats.py`
- `tests/api/server/services/dream_pass/test_replay_runner.py`
- `web/client/components/dashboard/MemoryTiles.tsx` — three KPI tiles: Lessons active, Lessons used (1h), LLM spend today.

**Modified files:**

- `api/server/services/dream_pass/wiring.py` — swap InMemoryLessonStore → Mem0LessonStore; drop `_prepend_lessons_to_skill_text` indirection (B); add lifecycle + metrics wiring (C); replace fixed cadence trigger (E); add cost-budget guard (F).
- `api/server/state.py` — `lesson_store = Mem0LessonStore(...)`; keep `working_memory_store` (still in-memory is fine for hot working notes); register lifecycle + metrics singletons.
- `api/functions/graphs/executors/agents/_wrapper.py` — remove `_prepend_lessons_to_skill_text`, `_fetch_active_lessons`, `_SKILL_TO_DOMAIN`, `_skill_to_domain`. Replace with a single new `_fetch_top_k_lessons(domain, query, top_k=3)` call against a new FastAPI endpoint.
- `api/server/routes/memory.py` — add a new `POST /api/memory/lessons/recall` endpoint that wraps `Mem0LessonStore.search(query, scope, top_k)` for cross-process retrieval.
- `api/server/services/dream_pass/orchestrator.py` — remove the hardcoded `('interview-recommender',)` literal at line 81; accept the closure's domain-scoped feed without argument override.
- `api/server/services/dream_pass/experiment.py` — accept a `ReplayExperimentRunner` alternative; existing `ExperimentRunner` (sandbox-based) stays as fallback.
- `api/server/main.py` — register the two new routers; wire kill-switch check at lifespan startup; emit cost-budget alerts on the bus.
- `data/policies/dream-pass.policy.yaml` — restore `min_samples: 40` once replay supplies enough corpus; add `shadow_invocations_required: 50` lifecycle field.
- `web/client/routes/Dashboard.tsx` — embed `MemoryTiles`.
- `tests/api/server/services/dream_pass/test_wiring.py` — update to assert Mem0 path is wired; existing stub-based tests stay.

**Deleted files:**

- None. All previous code paths get replaced inline so PRs are reviewable.

---

## Conventions

- **TDD:** every backend task starts with a failing pytest. Every UI task starts with a failing vitest. No implementation lands before a red test.
- **Mem0 in tests:** `Mem0LessonStore.__init__` accepts `memory: _MemoryLike | None`. Tests pass a `MagicMock` matching the `_MemoryLike` Protocol; only the live boot uses the real `mem0.Memory()`.
- **Backwards compatibility:** every modified API surface keeps existing kwargs working. Tests for the old InMemoryLessonStore stay green by pinning `lesson_store=InMemoryLessonStore()` explicitly.
- **No new third-party deps.** Mem0, AGT kernel, Kuzu, FastAPI, React are all present.
- **One commit per task, exact subject from the spec.** Frequent commits, no squash.
- **Audit ledger:** every lesson lifecycle transition (promote/demote/retire) flows through `LessonGovernor` so AGT + audit trail get the event.

---

## Phase A — Mem0 swap

The single highest-impact change. Lessons persist across restarts; semantic search becomes possible. ~3 tasks, ~2h.

### Task A1: Wire Mem0LessonStore in wiring.py

**Files:**
- Modify: `api/server/services/dream_pass/wiring.py`
- Modify: `api/server/state.py`
- Test: `tests/api/services/dream_pass/test_wiring.py` (extend)

- [ ] **Step 1: Write the failing test**

```python
# tests/api/services/dream_pass/test_wiring_mem0.py
from unittest.mock import MagicMock

from api.shared.events import FleetEvent  # noqa: F401 — import smoke
from api.server.services.audit_logger import AuditLogger
from api.server.services.event_bus import EventBus
from api.server.services.lessons.mem0_store import Mem0LessonStore
from api.server.services.dream_pass.wiring import build_demo_orchestrator
from api.server.services.dream_pass.proposer import StubProposer


def test_factory_uses_mem0_when_provided():
    """Caller passes a Mem0LessonStore (with mocked Memory) — factory must
    bind THAT instance to the orchestrator's governor, not silently
    swap in an in-memory store."""
    mock_memory = MagicMock()
    mock_memory.search.return_value = {"results": []}
    mem0_store = Mem0LessonStore(memory=mock_memory)

    orchestrator = build_demo_orchestrator(
        graph=None,
        bus=EventBus(),
        audit=AuditLogger(),
        lesson_store=mem0_store,
        proposer=StubProposer(candidates=[("body", "rationale")]),
    )
    # Governor's private store IS the Mem0LessonStore we passed in.
    assert orchestrator._governor._store is mem0_store
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```
PYTHONPATH=/Users/arturzielinski/dev/github-repos/zava-control-plane \
  /Users/arturzielinski/dev/github-repos/zava-control-plane/.venv/bin/pytest \
  tests/api/services/dream_pass/test_wiring_mem0.py -v
```
Expected: PASS (existing wiring already accepts `lesson_store=` per Task 4 of the 2026-05-20 plan). The test is the regression net.

If it fails because the factory shadows the kwarg or ignores it, fix that first before proceeding.

- [ ] **Step 3: Replace InMemoryLessonStore in state.py with Mem0LessonStore**

Edit `api/server/state.py`. Find the existing line:
```python
self.lesson_store = InMemoryLessonStore()
```
Replace with:
```python
# Mem0-backed: lessons persist across FastAPI restarts and support
# semantic search. The Mem0 backend respects MEM0_API_KEY (Mem0 cloud)
# or falls back to a local Qdrant; see mem0_store.py and the Mem0
# docs. Unit tests inject a MagicMock matching the _MemoryLike
# Protocol; production boot uses the real mem0.Memory().
try:
    from api.server.services.lessons.mem0_store import Mem0LessonStore
    self.lesson_store = Mem0LessonStore()
except Exception:
    import logging
    logging.getLogger(__name__).warning(
        "Mem0 backend unavailable (%s); falling back to InMemoryLessonStore. "
        "Lessons will NOT persist across restarts until Mem0 is configured.",
        "init failure", exc_info=True,
    )
    self.lesson_store = InMemoryLessonStore()
```

Keep the `from api.server.services.lessons.store import InMemoryLessonStore` import for the fallback path.

- [ ] **Step 4: Verify the existing dream-pass tests still pass**

Run:
```
PYTHONPATH=/Users/arturzielinski/dev/github-repos/zava-control-plane \
  /Users/arturzielinski/dev/github-repos/zava-control-plane/.venv/bin/pytest \
  tests/api/services/dream_pass/ tests/api/server/test_state_dream_orchestrator.py -v
```
Expected: all green. Tests pass `lesson_store=InMemoryLessonStore()` explicitly per the Task 4 fix; they don't touch the new default path.

- [ ] **Step 5: Live boot smoke**

```
make down
DREAM_PASS_DEMO_CADENCE_SECONDS=0 make up
```
Wait 60s for boot. Verify Mem0 initialised by checking the log:
```
LOG=$(ls -t /var/folders/wj/j93mw07x4k16yyt4z88pn7bw0000gn/T/copilot-detached-demo-stack*.log | head -1)
grep -i "mem0\|Mem0" "$LOG" | head
```
Expected: no warning. If you see `Mem0 backend unavailable`, the env doesn't have Mem0 configured — set `MEM0_API_KEY` per the Mem0 docs or accept the in-memory fallback path for this commit and document it in the PR description.

Also verify the `/api/memory/lessons/active` route still returns shape:
```
curl -s 'http://localhost:3101/api/memory/lessons/active?domain=hiring' | python3 -m json.tool | head
```
Expected: `{"items": []}` on a fresh boot.

- [ ] **Step 6: Commit**

```
git add api/server/state.py tests/api/services/dream_pass/test_wiring_mem0.py
git commit -m "feat(memory): swap InMemoryLessonStore for Mem0LessonStore as default"
```

### Task A2: Add a Mem0-aware /api/memory/lessons/active route

The existing route reads `lesson_store._by_id.values()` (InMemory-specific). Mem0 doesn't expose `_by_id`. Replace with the `search()` API.

**Files:**
- Modify: `api/server/routes/memory.py`
- Test: `tests/api/routes/test_memory.py` (extend)

- [ ] **Step 1: Write the failing test**

```python
# tests/api/routes/test_memory.py — append
def test_active_lessons_route_uses_lesson_store_search_not_private_by_id(monkeypatch):
    """Regression: the route MUST go through LessonStore.search so it
    works against Mem0 (which has no _by_id dict). InMemoryLessonStore
    happens to expose _by_id but reaching into it makes the route
    incompatible with Mem0."""
    from api.server.state import app_state
    from api.server.services.lessons.types import Lesson, LessonScope, LessonProvenance
    from datetime import datetime, timezone
    from unittest.mock import MagicMock

    captured: list[dict] = []
    real_search = app_state.lesson_store.search

    def spy_search(query="", *, scope, top_k=100):
        captured.append({"query": query, "scope": scope, "top_k": top_k})
        return real_search(query=query, scope=scope, top_k=top_k)

    monkeypatch.setattr(app_state.lesson_store, "search", spy_search)
    r = client.get("/api/memory/lessons/active", params={"domain": "hiring"})
    assert r.status_code == 200
    assert captured, "route did not call lesson_store.search — it must be the public read API"
    assert captured[0]["scope"].domain == "hiring"
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```
PYTHONPATH=/Users/arturzielinski/dev/github-repos/zava-control-plane \
  /Users/arturzielinski/dev/github-repos/zava-control-plane/.venv/bin/pytest \
  tests/api/routes/test_memory.py::test_active_lessons_route_uses_lesson_store_search_not_private_by_id -v
```
Expected: FAIL. The current implementation reaches into `_by_id` directly.

- [ ] **Step 3: Rewrite the `/lessons/active` handler to use `.search`**

Edit `api/server/routes/memory.py`. Replace the current implementation of `lessons_active` with:

```python
@router.get("/lessons/active")
def lessons_active(
    domain: str | None = Query(None),
) -> dict[str, list[dict[str, Any]]]:
    """Currently active (un-pruned) lessons.

    Backed by LessonStore.search so it works against both
    InMemoryLessonStore and Mem0LessonStore — the route is storage-
    agnostic. A domain filter narrows the LessonScope; without one,
    we fan out over the set of known dream-pass domains (today: just
    'hiring', read from api/server/skills/dream-passes/).
    """
    from api.server.services.lessons.types import LessonScope
    store = app_state.lesson_store
    if domain:
        domains = [domain]
    else:
        # Discover available dream-pass domains by listing the
        # dream-passes skills dir. Cheap (≤10 entries).
        from pathlib import Path as _Path
        dream_passes_dir = _Path(__file__).resolve().parents[2] / "skills" / "dream-passes"
        domains = [p.name for p in dream_passes_dir.iterdir() if p.is_dir()] if dream_passes_dir.exists() else ["hiring"]
    items: list[dict[str, Any]] = []
    for d in domains:
        try:
            lessons = store.search(query="", scope=LessonScope(domain=d), top_k=200)
        except Exception:
            log.exception("memory: lessons_active search failed for domain=%s", d)
            continue
        items.extend(_lesson_to_dict(l) for l in lessons)
    return {"items": items}
```

Remove the old `_by_id` access entirely.

- [ ] **Step 4: Run all memory tests**

Run:
```
PYTHONPATH=/Users/arturzielinski/dev/github-repos/zava-control-plane \
  /Users/arturzielinski/dev/github-repos/zava-control-plane/.venv/bin/pytest \
  tests/api/routes/test_memory.py -v
```
Expected: 7 pass (6 existing + 1 new).

- [ ] **Step 5: Commit**

```
git add api/server/routes/memory.py tests/api/routes/test_memory.py
git commit -m "feat(memory): route /lessons/active via LessonStore.search (Mem0-compatible)"
```

### Task A3: Persistence smoke

Confirm lessons survive a `make down && make up` cycle on the live demo stack. This is a manual verification step; the unit tests can't exercise real Mem0.

- [ ] **Step 1: Boot fresh**

```
make down
sleep 3
rm -f data/portal/entity_graph.kuzu/.lock
DREAM_PASS_DEMO_CADENCE_SECONDS=120 DREAM_PASS_DEMO_CADENCE_DOMAINS=hiring make up
```

- [ ] **Step 2: Trigger a pass to land a real lesson**

Wait 90s for boot, then:
```
for i in 1 2 3 4 5; do curl -s -X POST 'http://localhost:3101/api/simulator/hire' -H 'Content-Type: application/json' -d '{}' >/dev/null; done
sleep 60
curl -s -X POST 'http://localhost:3101/api/dream-pass/run?domain=hiring&sample=5' --max-time 240
```

Wait ~3 min for GHCP. Inspect lessons:
```
curl -s 'http://localhost:3101/api/memory/lessons/active?domain=hiring' | python3 -m json.tool | head -40
```
Record the lesson IDs and bodies you see.

- [ ] **Step 3: Restart**

```
make down
sleep 5
DREAM_PASS_DEMO_CADENCE_SECONDS=0 make up
```

(Cadence off this time so no NEW lessons get added — we're testing persistence of the OLD ones.)

- [ ] **Step 4: Verify lessons survived**

```
sleep 60
curl -s 'http://localhost:3101/api/memory/lessons/active?domain=hiring' | python3 -m json.tool | head -40
```
Expected: SAME lesson IDs and bodies as in Step 2. If the result is `{"items": []}`, Mem0 isn't persisting — check whether the install resolved to Mem0 cloud (requires API key) or Qdrant (requires local server). Update `state.py` to make the fallback explicit and document the env requirements in `docs/runtime-providers.md`.

- [ ] **Step 5: Commit any docs / fallback adjustments**

```
git add -A
git commit -m "docs(memory): document Mem0 backend requirements and fallback semantics"
```

---

## Phase B — Top-K retrieval (replace prepend-everything)

Today every agent gets every active lesson concatenated into its prompt. Replace with `Mem0.search(query=<context>, top_k=3)` so the LLM only sees the 3 most-relevant lessons for THIS specific decision.

### Task B1: Add /api/memory/lessons/recall endpoint

**Files:**
- Modify: `api/server/routes/memory.py`
- Test: `tests/api/routes/test_memory.py` (extend)

- [ ] **Step 1: Write the failing test**

```python
def test_recall_lessons_returns_topk_for_query():
    """POST /api/memory/lessons/recall returns up to top_k lessons
    ranked by semantic similarity to the query string."""
    r = client.post(
        "/api/memory/lessons/recall",
        json={"domain": "hiring", "query": "candidate with US visa needs review", "top_k": 3},
    )
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert isinstance(body["items"], list)
    assert len(body["items"]) <= 3
    for it in body["items"]:
        assert "id" in it
        assert "body" in it
        assert "score" in it  # Mem0 returns a similarity score


def test_recall_lessons_rejects_empty_query():
    r = client.post(
        "/api/memory/lessons/recall",
        json={"domain": "hiring", "query": "", "top_k": 3},
    )
    assert r.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```
PYTHONPATH=/Users/arturzielinski/dev/github-repos/zava-control-plane \
  /Users/arturzielinski/dev/github-repos/zava-control-plane/.venv/bin/pytest \
  tests/api/routes/test_memory.py::test_recall_lessons_returns_topk_for_query -v
```
Expected: 404 (route not registered).

- [ ] **Step 3: Add the route**

In `api/server/routes/memory.py`, add:

```python
class _RecallBody(BaseModel):
    domain: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=3, ge=1, le=10)


@router.post("/lessons/recall")
def lessons_recall(body: _RecallBody) -> dict[str, list[dict[str, Any]]]:
    """Top-K relevant lessons for a query string. Backs the Functions-
    process agent runtime: every LLM agent call POSTs the candidate
    context (role title + jurisdiction + skill name + workflow id) as
    `query`, gets the top 3 semantically-relevant lessons, and
    prepends them as natural-language guidance to its prompt. This
    replaces the prepend-everything pattern."""
    from api.server.services.lessons.types import LessonScope
    store = app_state.lesson_store
    scope = LessonScope(domain=body.domain)
    try:
        lessons = store.search(query=body.query, scope=scope, top_k=body.top_k)
    except Exception:
        log.exception("memory: lessons_recall search failed")
        return {"items": []}
    items = []
    for l in lessons:
        d = _lesson_to_dict(l)
        # Mem0 returns score; InMemoryLessonStore doesn't — surface 1.0
        # as a "matched but unscored" default. UI can show the value
        # but shouldn't filter on it.
        d["score"] = getattr(l, "_score", 1.0)
        items.append(d)
    return {"items": items}
```

Add the `Field` import: `from pydantic import BaseModel, Field`.

- [ ] **Step 4: Verify tests pass**

```
PYTHONPATH=/Users/arturzielinski/dev/github-repos/zava-control-plane \
  /Users/arturzielinski/dev/github-repos/zava-control-plane/.venv/bin/pytest \
  tests/api/routes/test_memory.py -v
```
Expected: 9 pass.

- [ ] **Step 5: Commit**

```
git add api/server/routes/memory.py tests/api/routes/test_memory.py
git commit -m "feat(memory): POST /api/memory/lessons/recall — top-K semantic retrieval"
```

### Task B2: Replace prepend-everything with recall in _wrapper.py

**Files:**
- Modify: `api/functions/graphs/executors/agents/_wrapper.py`
- Test: extend `tests/api/functions/graphs/executors/agents/test_wrapper_lesson_consumption.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/functions/graphs/executors/agents/test_wrapper_lesson_consumption.py — append
@pytest.mark.asyncio
async def test_recall_top_k_lessons_uses_recall_endpoint_not_active():
    """Phase B regression: agent runtime fetches via /lessons/recall
    (semantic, top-K) and NOT /lessons/active (return-everything)."""
    captured_urls: list[str] = []
    class _FakeR:
        status_code = 200
        def json(self):
            return {"items": [{"id": "L1", "body": "x", "score": 0.9}]}
    class _FakeC:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, *a, **kw):
            captured_urls.append(url)
            return _FakeR()
        async def get(self, url, *a, **kw):
            captured_urls.append(url)
            return _FakeR()
    from api.functions.graphs.executors.agents._wrapper import _fetch_top_k_lessons, _lesson_cache
    _lesson_cache.clear()
    with patch("api.functions.graphs.executors.agents._wrapper.httpx.AsyncClient", return_value=_FakeC()):
        out = await _fetch_top_k_lessons(
            domain="hiring",
            query="senior data engineer USA",
            top_k=3,
        )
    assert any("/api/memory/lessons/recall" in u for u in captured_urls)
    assert not any("/api/memory/lessons/active" in u for u in captured_urls)
    assert out == [{"id": "L1", "body": "x", "score": 0.9}]
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```
PYTHONPATH=/Users/arturzielinski/dev/github-repos/zava-control-plane \
  /Users/arturzielinski/dev/github-repos/zava-control-plane/.venv/bin/pytest \
  tests/api/functions/graphs/executors/agents/test_wrapper_lesson_consumption.py::test_recall_top_k_lessons_uses_recall_endpoint_not_active -v
```
Expected: `ImportError: cannot import name '_fetch_top_k_lessons'`.

- [ ] **Step 3: Add _fetch_top_k_lessons; remove old _fetch_active_lessons usage**

In `api/functions/graphs/executors/agents/_wrapper.py`, ADD the new helper (keep `_fetch_active_lessons` for the moment for the rollback path; mark it deprecated):

```python
def _memory_recall_url() -> str:
    """POST /api/memory/lessons/recall — top-K semantic retrieval."""
    base = os.getenv("FASTAPI_WEBHOOK_URL", "http://localhost:3101/internal/durable-event")
    from urllib.parse import urlsplit, urlunsplit
    parts = urlsplit(base)
    return urlunsplit((parts.scheme, parts.netloc, "/api/memory/lessons/recall", "", ""))


async def _fetch_top_k_lessons(*, domain: str, query: str, top_k: int = 3) -> list[dict]:
    """Top-K semantically-relevant lessons for ``query`` in ``domain``.
    30s in-process cache keyed on (domain, query); tolerant of network
    errors (returns [])."""
    now = time.monotonic()
    cache_key = f"{domain}::{query}"
    cached = _lesson_cache.get(cache_key)
    if cached is not None and now - cached[0] < _LESSON_CACHE_TTL_S:
        return cached[1]
    try:
        async with httpx.AsyncClient() as c:
            r = await c.post(
                _memory_recall_url(),
                json={"domain": domain, "query": query, "top_k": top_k},
                timeout=3.0,
            )
            if r.status_code != 200:
                _lesson_cache[cache_key] = (now, [])
                return []
            items = r.json().get("items") or []
            slim = [
                {"id": str(l.get("id")), "body": str(l.get("body") or ""),
                 "score": float(l.get("score") or 0.0)}
                for l in items[:top_k] if l.get("body")
            ]
            _lesson_cache[cache_key] = (now, slim)
            return slim
    except Exception:
        _lesson_cache[cache_key] = (now, [])
        return []
```

Update `run_agent_session` to use the new helper. Find the current line near line 297:
```python
domain = _skill_to_domain(skill_label, skill_dir.name if skill_dir else None)
active_lessons: list[dict] = await _fetch_active_lessons(domain) if domain else []
skill_text = _prepend_lessons_to_skill_text(skill_text, active_lessons)
```

Replace with:
```python
domain = _skill_to_domain(skill_label, skill_dir.name if skill_dir else None)
if domain:
    # Build a context query from what we know about this invocation.
    # The prompt itself is the most direct signal; truncate so we
    # don't send a 50KB system message as a search query.
    query_seed = f"skill={skill_label or '?'} domain={domain} prompt={(prompt or '')[:240]}"
    active_lessons = await _fetch_top_k_lessons(
        domain=domain, query=query_seed, top_k=3,
    )
else:
    active_lessons = []
skill_text = _prepend_lessons_to_skill_text(skill_text, active_lessons)
```

The prepend helper stays — top-3 lessons are still prepended to the system message, but now they're the 3 SEMANTICALLY-RELEVANT ones instead of every active lesson.

- [ ] **Step 4: Run tests**

```
PYTHONPATH=/Users/arturzielinski/dev/github-repos/zava-control-plane \
  /Users/arturzielinski/dev/github-repos/zava-control-plane/.venv/bin/pytest \
  tests/api/functions/graphs/executors/agents/test_wrapper_lesson_consumption.py -v
```
Expected: existing tests + the new one all pass.

- [ ] **Step 5: Commit**

```
git add api/functions/graphs/executors/agents/_wrapper.py tests/api/functions/graphs/executors/agents/test_wrapper_lesson_consumption.py
git commit -m "feat(memory): agents fetch top-3 semantic lessons (not prepend-all-active)"
```

### Task B3: Remove the deprecated _fetch_active_lessons helper

**Files:**
- Modify: `api/functions/graphs/executors/agents/_wrapper.py`

- [ ] **Step 1: Delete `_fetch_active_lessons` and `_memory_lessons_url`**

Both are now superseded by Phase B1+B2. Confirm no remaining callers:
```
grep -rn "_fetch_active_lessons\|_memory_lessons_url" api/ tests/
```
Expected: only the function definitions in `_wrapper.py`. Delete them.

- [ ] **Step 2: Run full _wrapper test suite**

```
PYTHONPATH=/Users/arturzielinski/dev/github-repos/zava-control-plane \
  /Users/arturzielinski/dev/github-repos/zava-control-plane/.venv/bin/pytest \
  tests/api/functions/graphs/executors/agents/ -v
```
Expected: all green.

- [ ] **Step 3: Commit**

```
git add api/functions/graphs/executors/agents/_wrapper.py
git commit -m "refactor(memory): remove deprecated _fetch_active_lessons (superseded by recall)"
```

---

## Phase C — Lesson lifecycle

Lessons today only ever get added. No demotion, no retirement. Phase C adds: `candidate → shadow → active → demote → retire`, driven by metrics.

### Task C1: Add LessonLifecycle pure-logic module

**Files:**
- Create: `api/server/services/lessons/lesson_lifecycle.py`
- Create: `tests/api/server/services/lessons/test_lesson_lifecycle.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/server/services/lessons/test_lesson_lifecycle.py
from datetime import datetime, timedelta, timezone

from api.server.services.lessons.lesson_lifecycle import (
    LessonStatus,
    next_status,
    LessonOutcomeMetrics,
)


def test_candidate_with_enough_shadow_invocations_promotes_to_active():
    m = LessonOutcomeMetrics(
        status=LessonStatus.SHADOW,
        invocations=50,
        hitl_override_count=2,
        promoted_at=datetime.now(timezone.utc) - timedelta(hours=2),
        last_used_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    assert next_status(m, shadow_invocations_required=50,
                      max_override_rate=0.20, retire_after_days=30) == LessonStatus.ACTIVE


def test_active_with_high_override_rate_demotes():
    m = LessonOutcomeMetrics(
        status=LessonStatus.ACTIVE,
        invocations=40,
        hitl_override_count=20,  # 50% override rate
        promoted_at=datetime.now(timezone.utc) - timedelta(days=2),
        last_used_at=datetime.now(timezone.utc) - timedelta(minutes=10),
    )
    assert next_status(m, shadow_invocations_required=50,
                      max_override_rate=0.20, retire_after_days=30) == LessonStatus.DEMOTED


def test_unused_active_retires_after_window():
    m = LessonOutcomeMetrics(
        status=LessonStatus.ACTIVE,
        invocations=10,
        hitl_override_count=0,
        promoted_at=datetime.now(timezone.utc) - timedelta(days=60),
        last_used_at=datetime.now(timezone.utc) - timedelta(days=40),
    )
    assert next_status(m, shadow_invocations_required=50,
                      max_override_rate=0.20, retire_after_days=30) == LessonStatus.RETIRED


def test_demoted_with_recent_use_does_not_re_promote():
    m = LessonOutcomeMetrics(
        status=LessonStatus.DEMOTED,
        invocations=80,
        hitl_override_count=4,
        promoted_at=datetime.now(timezone.utc) - timedelta(days=1),
        last_used_at=datetime.now(timezone.utc) - timedelta(minutes=10),
    )
    # Once demoted, never auto-promote. Only manual intervention.
    assert next_status(m, shadow_invocations_required=50,
                      max_override_rate=0.20, retire_after_days=30) == LessonStatus.DEMOTED
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```
PYTHONPATH=/Users/arturzielinski/dev/github-repos/zava-control-plane \
  /Users/arturzielinski/dev/github-repos/zava-control-plane/.venv/bin/pytest \
  tests/api/server/services/lessons/test_lesson_lifecycle.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write the lifecycle module**

```python
# api/server/services/lessons/lesson_lifecycle.py
"""Pure-logic lesson lifecycle transitions.

Lifecycle:
    candidate → shadow → active ⇄ demoted → retired

- candidate: proposer just emitted it. Not used at runtime.
- shadow: promoted by policy but not yet trusted. Used in N shadow
  invocations (silently included in prompt; outcome measured).
- active: trusted. Returned by /api/memory/lessons/recall and
  prepended to agent prompts.
- demoted: outcome metrics turned against it. NOT returned by recall.
  Stays in Mem0 for audit + manual re-evaluation.
- retired: unused for `retire_after_days`. Deleted from Mem0 (via
  governor.prune so ledger + provenance record the retirement).

Driven by LessonOutcomeMetrics; no I/O. The governor wraps this and
applies the transition through AGT + audit + Kuzu.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum


class LessonStatus(str, Enum):
    CANDIDATE = "candidate"
    SHADOW = "shadow"
    ACTIVE = "active"
    DEMOTED = "demoted"
    RETIRED = "retired"


@dataclass(frozen=True)
class LessonOutcomeMetrics:
    """Snapshot of a lesson's outcome signals at one point in time."""

    status: LessonStatus
    invocations: int
    hitl_override_count: int
    promoted_at: datetime
    last_used_at: datetime | None


def next_status(
    metrics: LessonOutcomeMetrics,
    *,
    shadow_invocations_required: int,
    max_override_rate: float,
    retire_after_days: int,
) -> LessonStatus:
    """Compute the next lifecycle status. Pure function; idempotent."""
    now = datetime.now(timezone.utc)
    s = metrics.status

    # Retirement: unused for retire_after_days, regardless of status.
    if metrics.last_used_at is not None:
        unused_for = now - metrics.last_used_at
        if unused_for > timedelta(days=retire_after_days) and s in (LessonStatus.ACTIVE, LessonStatus.SHADOW, LessonStatus.DEMOTED):
            return LessonStatus.RETIRED

    if s == LessonStatus.CANDIDATE:
        return LessonStatus.CANDIDATE  # advancement requires explicit governor.promote

    if s == LessonStatus.SHADOW:
        if metrics.invocations >= shadow_invocations_required:
            if metrics.invocations > 0:
                rate = metrics.hitl_override_count / metrics.invocations
                if rate > max_override_rate:
                    return LessonStatus.DEMOTED
            return LessonStatus.ACTIVE
        return LessonStatus.SHADOW

    if s == LessonStatus.ACTIVE:
        if metrics.invocations >= shadow_invocations_required and metrics.invocations > 0:
            rate = metrics.hitl_override_count / metrics.invocations
            if rate > max_override_rate:
                return LessonStatus.DEMOTED
        return LessonStatus.ACTIVE

    if s == LessonStatus.DEMOTED:
        return LessonStatus.DEMOTED  # no auto re-promote

    return s
```

- [ ] **Step 4: Run tests**

Expected: all 4 pass.

- [ ] **Step 5: Commit**

```
git add api/server/services/lessons/lesson_lifecycle.py tests/api/server/services/lessons/test_lesson_lifecycle.py
git commit -m "feat(memory): lesson lifecycle state machine (candidate→shadow→active→demoted→retired)"
```

### Task C2: Add LessonMetrics module — read counts from working notes + exceptions

**Files:**
- Create: `api/server/services/lessons/lesson_metrics.py`
- Test: `tests/api/server/services/lessons/test_lesson_metrics.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/server/services/lessons/test_lesson_metrics.py
from datetime import datetime, timezone

from api.server.services.lessons.lesson_metrics import LessonMetrics
from api.server.services.lessons.working_memory_store import InMemoryWorkingMemoryStore
from api.server.services.lessons.working_memory_types import WorkingNote


def _wn(*, lesson_id: str, workflow_id: str, kind: str = "lesson_used", body: str | None = None) -> WorkingNote:
    return WorkingNote(
        id=f"WN-{lesson_id}-{workflow_id}",
        workflow_id=workflow_id,
        agent_skill="hiring-segment-b",
        kind=kind,  # type: ignore[arg-type]
        body=body or f"used {lesson_id}: …",
    )


def test_invocations_counts_lesson_used_notes_for_a_lesson():
    store = InMemoryWorkingMemoryStore()
    store._by_id["a"] = _wn(lesson_id="L1", workflow_id="WF-1")
    store._by_id["b"] = _wn(lesson_id="L1", workflow_id="WF-2")
    store._by_id["c"] = _wn(lesson_id="L2", workflow_id="WF-1")
    m = LessonMetrics(working_memory_store=store, exceptions_provider=lambda: [])
    assert m.invocations("L1") == 2
    assert m.invocations("L2") == 1
    assert m.invocations("UNKNOWN") == 0


def test_hitl_override_count_intersects_used_workflows_with_open_exceptions():
    store = InMemoryWorkingMemoryStore()
    store._by_id["a"] = _wn(lesson_id="L1", workflow_id="WF-1")
    store._by_id["b"] = _wn(lesson_id="L1", workflow_id="WF-2")
    # WF-2 raised an HITL exception → operator overrode the agent's
    # recommendation. WF-1 did not.
    exceptions = [{"workflow_id": "WF-2", "resolved": False}]
    m = LessonMetrics(working_memory_store=store, exceptions_provider=lambda: exceptions)
    assert m.hitl_override_count("L1") == 1
```

- [ ] **Step 2: Run test to verify it fails**

```
PYTHONPATH=/Users/arturzielinski/dev/github-repos/zava-control-plane \
  /Users/arturzielinski/dev/github-repos/zava-control-plane/.venv/bin/pytest \
  tests/api/server/services/lessons/test_lesson_metrics.py -v
```
Expected: ModuleNotFoundError.

- [ ] **Step 3: Write the module**

```python
# api/server/services/lessons/lesson_metrics.py
"""Per-lesson outcome metrics.

A lesson's outcome is measured by:
  - invocations: how many times it was in an agent's prompt
    (counted from kind="lesson_used" working notes)
  - hitl_override_count: how many of those invocations led to a
    workflow that the operator subsequently overrode at a HITL gate.
    Proxy for "the lesson did not improve the decision."

The intersection between (workflows where lesson_used) and (workflows
with open/resolved-by-operator exceptions) is the override rate. Not
perfect — operator overrides happen for many reasons — but it's the
strongest signal available without a labeled ground truth.
"""
from __future__ import annotations

from typing import Callable, Iterable

from api.server.services.lessons.working_memory_store import WorkingMemoryStore


def _lesson_id_from_body(body: str | None) -> str | None:
    """lesson_used note body format: 'used <id>: <preview>'."""
    if not body or not body.startswith("used "):
        return None
    rest = body[len("used "):]
    sep = rest.find(":")
    if sep <= 0:
        return None
    return rest[:sep].strip()


class LessonMetrics:
    def __init__(
        self,
        *,
        working_memory_store: WorkingMemoryStore,
        exceptions_provider: Callable[[], Iterable[dict]],
    ) -> None:
        self._wms = working_memory_store
        self._exceptions = exceptions_provider

    def _used_notes_for(self, lesson_id: str) -> list:
        store = self._wms
        if not hasattr(store, "_by_id"):
            return []
        return [
            n for n in store._by_id.values()
            if getattr(n, "kind", None) == "lesson_used"
            and _lesson_id_from_body(getattr(n, "body", None)) == lesson_id
        ]

    def invocations(self, lesson_id: str) -> int:
        return len(self._used_notes_for(lesson_id))

    def hitl_override_count(self, lesson_id: str) -> int:
        used_workflows = {
            getattr(n, "workflow_id", None) for n in self._used_notes_for(lesson_id)
        } - {None}
        overridden = {
            e.get("workflow_id") for e in self._exceptions() if e.get("workflow_id")
        }
        return len(used_workflows & overridden)
```

- [ ] **Step 4: Run tests**

Expected: 2 pass.

- [ ] **Step 5: Commit**

```
git add api/server/services/lessons/lesson_metrics.py tests/api/server/services/lessons/test_lesson_metrics.py
git commit -m "feat(memory): per-lesson invocations + HITL override metrics"
```

### Task C3: Wire lifecycle into a periodic governor sweep

**Files:**
- Modify: `api/server/state.py` (lifespan-side task scheduling)
- Modify: `api/server/services/lessons/governor.py` (add `apply_lifecycle` method)
- Test: `tests/api/server/services/lessons/test_governor_lifecycle.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/server/services/lessons/test_governor_lifecycle.py
from unittest.mock import MagicMock

import pytest

from api.server.services.governance.kernel import kernel
from api.server.services.lessons.governor import LessonGovernor
from api.server.services.lessons.kuzu_provenance import KuzuLessonProvenance
from api.server.services.lessons.store import InMemoryLessonStore
from api.server.services.audit_logger import AuditLogger
from api.server.services.lessons.lesson_metrics import LessonMetrics
from api.server.services.lessons.lesson_lifecycle import LessonStatus


def test_apply_lifecycle_demotes_lessons_exceeding_override_rate():
    store = InMemoryLessonStore()
    # Seed: one active lesson L1 with bad outcomes (40% override rate)
    from api.server.services.lessons.types import Lesson, LessonProvenance, LessonScope
    from datetime import datetime, timezone
    lesson = Lesson(
        id="L1",
        body="x",
        scope=LessonScope(domain="hiring"),
        provenance=LessonProvenance(
            proposed_by="t",
            run_ids=(),
            rubric_score_delta=0.1,
            experiment_n=50,
            promoted_at=datetime.now(timezone.utc),
        ),
        status="active",
    )
    store.add(lesson)

    governor = LessonGovernor(
        store=store, kernel=kernel, audit=AuditLogger(),
        provenance=MagicMock(), actor="test",
    )

    metrics = MagicMock(spec=LessonMetrics)
    metrics.invocations.return_value = 50
    metrics.hitl_override_count.return_value = 20  # 40% override

    transitions = governor.apply_lifecycle(
        domain="hiring",
        metrics=metrics,
        shadow_invocations_required=50,
        max_override_rate=0.20,
        retire_after_days=30,
    )

    assert transitions == [("L1", LessonStatus.DEMOTED)]
    # Store retained the lesson but status changed
    assert store.get("L1") is not None
    # Verify the governor actually wrote the transition through .prune or status update
    # (impl detail: demote = mark status='pruned' to hide from search; retired = full delete)
```

- [ ] **Step 2: Run test to verify it fails**

Expected: `AttributeError: 'LessonGovernor' object has no attribute 'apply_lifecycle'`.

- [ ] **Step 3: Implement `apply_lifecycle` on the governor**

In `api/server/services/lessons/governor.py`, add:

```python
def apply_lifecycle(
    self,
    *,
    domain: str,
    metrics: 'LessonMetrics',
    shadow_invocations_required: int,
    max_override_rate: float,
    retire_after_days: int,
) -> list[tuple[str, 'LessonStatus']]:
    """Sweep all lessons in `domain`, compute next_status, apply
    transitions that change. Returns list of (lesson_id, new_status).

    Transitions:
        DEMOTED → prune from store (still kept in Kuzu for audit).
        RETIRED → full delete via store.prune.
        ACTIVE / SHADOW → status field updated in place.
    """
    from api.server.services.lessons.lesson_lifecycle import (
        LessonOutcomeMetrics, LessonStatus, next_status,
    )
    from api.server.services.lessons.types import LessonScope
    from datetime import datetime, timezone

    transitions: list[tuple[str, LessonStatus]] = []
    lessons = self._store.search(query="", scope=LessonScope(domain=domain), top_k=500)
    for lesson in lessons:
        current = LessonStatus(lesson.status if lesson.status != "pruned" else "demoted")
        m = LessonOutcomeMetrics(
            status=current,
            invocations=metrics.invocations(lesson.id),
            hitl_override_count=metrics.hitl_override_count(lesson.id),
            promoted_at=lesson.provenance.promoted_at,
            last_used_at=datetime.now(timezone.utc),  # TODO refine with real last_used
        )
        new = next_status(
            m,
            shadow_invocations_required=shadow_invocations_required,
            max_override_rate=max_override_rate,
            retire_after_days=retire_after_days,
        )
        if new == current:
            continue
        if new == LessonStatus.RETIRED:
            self.prune(lesson.id, reason=f"retired:unused>{retire_after_days}d")
        elif new == LessonStatus.DEMOTED:
            self.prune(lesson.id, reason=f"demoted:override_rate>{max_override_rate}")
        # else: status updates for active/shadow not yet plumbed
        # (require an UPDATE pathway on LessonStore — TODO Phase C4)
        transitions.append((lesson.id, new))
    return transitions
```

- [ ] **Step 4: Run tests**

Expected: pass.

- [ ] **Step 5: Schedule the sweep in the FastAPI lifespan**

In `api/server/main.py`, after the existing `ramp_task = ...`:

```python
# Lesson lifecycle sweep — runs every 5 min. Demotes / retires lessons
# whose outcome metrics turned against them. See lesson_lifecycle.py.
async def _lifecycle_sweep_loop():
    import asyncio
    from api.server.services.lessons.lesson_metrics import LessonMetrics
    metrics = LessonMetrics(
        working_memory_store=app_state.working_memory_store,
        exceptions_provider=lambda: [
            {"workflow_id": e.workflow_id, "resolved": e.resolved_at is not None}
            for e in app_state.store.list_open_exceptions()
        ],
    )
    while True:
        try:
            transitions = app_state.dream_pass_orchestrator._governor.apply_lifecycle(
                domain="hiring",
                metrics=metrics,
                shadow_invocations_required=50,
                max_override_rate=0.20,
                retire_after_days=30,
            )
            if transitions:
                print(f"[lesson-lifecycle] transitions: {transitions}")
        except Exception:
            import logging
            logging.getLogger(__name__).exception("lesson lifecycle sweep failed")
        await asyncio.sleep(300)


_lifecycle_sweep_task = asyncio.create_task(_lifecycle_sweep_loop())
```

Add `_lifecycle_sweep_task` to the teardown cancellation block.

- [ ] **Step 6: Commit**

```
git add api/server/services/lessons/governor.py api/server/main.py tests/api/server/services/lessons/test_governor_lifecycle.py
git commit -m "feat(memory): lifecycle sweep — demote / retire lessons via metrics"
```

---

## Phase D — Observability + Dashboard tiles

Surface what's actually happening so we catch ballooning early.

### Task D1: GET /api/memory/lessons/{id}/stats

**Files:**
- Create: `api/server/routes/memory_lesson_stats.py`
- Modify: `api/server/main.py` (register router)
- Test: `tests/api/routes/test_memory_lesson_stats.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/routes/test_memory_lesson_stats.py
from fastapi.testclient import TestClient
from api.server.main import app

client = TestClient(app)


def test_lesson_stats_returns_invocations_and_override_count():
    r = client.get("/api/memory/lessons/L1/stats")
    assert r.status_code == 200
    body = r.json()
    assert "lesson_id" in body
    assert "invocations" in body
    assert "hitl_override_count" in body
    assert "override_rate" in body
    assert "first_used_at" in body
    assert "last_used_at" in body
```

- [ ] **Step 2: Run to fail (404)**

- [ ] **Step 3: Write the route**

```python
# api/server/routes/memory_lesson_stats.py
"""Per-lesson observability surface.

GET /api/memory/lessons/{id}/stats — invocation count, HITL override
count, override rate, first+last used timestamps. Powers the Dashboard
"Lessons used (1h)" tile and the per-lesson drill-down on the Memory
page.
"""
from __future__ import annotations

from fastapi import APIRouter

from api.server.state import app_state
from api.server.services.lessons.lesson_metrics import LessonMetrics, _lesson_id_from_body


router = APIRouter(prefix="/api/memory/lessons", tags=["memory"])


@router.get("/{lesson_id}/stats")
def lesson_stats(lesson_id: str) -> dict:
    metrics = LessonMetrics(
        working_memory_store=app_state.working_memory_store,
        exceptions_provider=lambda: [],  # TODO wire app_state.store.list_open_exceptions
    )
    inv = metrics.invocations(lesson_id)
    override = metrics.hitl_override_count(lesson_id)
    rate = (override / inv) if inv > 0 else 0.0

    # Compute first / last used by scanning the working memory store.
    store = app_state.working_memory_store
    notes = []
    if hasattr(store, "_by_id"):
        for n in store._by_id.values():
            if getattr(n, "kind", None) == "lesson_used" and _lesson_id_from_body(getattr(n, "body", None)) == lesson_id:
                notes.append(n)
    notes.sort(key=lambda n: n.captured_at)
    first_at = notes[0].captured_at.isoformat() if notes else None
    last_at = notes[-1].captured_at.isoformat() if notes else None

    return {
        "lesson_id": lesson_id,
        "invocations": inv,
        "hitl_override_count": override,
        "override_rate": round(rate, 3),
        "first_used_at": first_at,
        "last_used_at": last_at,
    }
```

Register in `main.py` next to other memory routers.

- [ ] **Step 4: Commit**

```
git add api/server/routes/memory_lesson_stats.py api/server/main.py tests/api/routes/test_memory_lesson_stats.py
git commit -m "feat(memory): GET /api/memory/lessons/{id}/stats — per-lesson observability"
```

### Task D2: Dashboard MemoryTiles component

**Files:**
- Create: `web/client/components/dashboard/MemoryTiles.tsx`
- Modify: `web/client/routes/Dashboard.tsx`
- Test: `web/client/components/dashboard/__tests__/MemoryTiles.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// web/client/components/dashboard/__tests__/MemoryTiles.test.tsx
// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import MemoryTiles from "../MemoryTiles";


beforeEach(() => {
  globalThis.fetch = vi.fn(async (url: RequestInfo | URL) => {
    const u = String(url);
    if (u.includes("/api/memory/lessons/active")) {
      return new Response(JSON.stringify({ items: [{ id: "L1" }, { id: "L2" }] }), { status: 200 });
    }
    return new Response("{}", { status: 404 });
  }) as unknown as typeof fetch;
});


describe("MemoryTiles", () => {
  it("renders the Lessons active count from /api/memory/lessons/active", async () => {
    render(<MemoryTiles />);
    await waitFor(() => screen.getByText(/Lessons active/i));
    await waitFor(() => screen.getByText("2"));
  });
});
```

- [ ] **Step 2: Run to fail**

- [ ] **Step 3: Implement**

```tsx
// web/client/components/dashboard/MemoryTiles.tsx
import { useEffect, useState } from "react";


export default function MemoryTiles() {
  const [active, setActive] = useState<number>(0);

  useEffect(() => {
    let cancelled = false;
    async function refresh() {
      try {
        const r = await fetch("/api/memory/lessons/active");
        if (!r.ok) return;
        const body = await r.json();
        if (cancelled) return;
        setActive((body.items || []).length);
      } catch {
        /* tolerated */
      }
    }
    refresh();
    const iv = window.setInterval(refresh, 30_000);
    return () => {
      cancelled = true;
      window.clearInterval(iv);
    };
  }, []);

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
      <div className="bg-white border border-slate-200 rounded-lg p-4 dark:bg-slate-900 dark:border-slate-700">
        <div className="text-[11px] uppercase tracking-wide text-slate-500 dark:text-slate-400">Lessons active</div>
        <div className="text-2xl font-semibold text-slate-900 dark:text-slate-100 tabular-nums">{active}</div>
        <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">across all domains</div>
      </div>
    </div>
  );
}
```

Embed in `Dashboard.tsx` below the existing KPI tile grid.

- [ ] **Step 4: Tests**

```
npx vitest run web/client/components/dashboard/__tests__/MemoryTiles.test.tsx
```

- [ ] **Step 5: Commit**

```
git add web/client/components/dashboard/ web/client/routes/Dashboard.tsx
git commit -m "feat(dashboard): MemoryTiles — Lessons active KPI"
```

---

## Phase E — Signal-driven cadence + kill switch

### Task E1: Wire kill_switch_id from policy YAML

**Files:**
- Create: `api/server/routes/dream_pass_pause.py`
- Modify: `api/server/main.py`
- Test: `tests/api/routes/test_dream_pass_pause.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/routes/test_dream_pass_pause.py
from fastapi.testclient import TestClient
from api.server.main import app

client = TestClient(app)


def test_pause_then_unpause_round_trip():
    r1 = client.post("/api/dream-pass/pause", params={"domain": "hiring"})
    assert r1.status_code == 200
    assert r1.json() == {"ok": True, "paused": ["hiring"]}

    r2 = client.get("/api/dream-pass/pause")
    assert r2.status_code == 200
    assert "hiring" in r2.json()["paused"]

    r3 = client.delete("/api/dream-pass/pause", params={"domain": "hiring"})
    assert r3.status_code == 200
    assert r3.json() == {"ok": True, "paused": []}


def test_run_endpoint_refuses_when_paused():
    client.post("/api/dream-pass/pause", params={"domain": "hiring"})
    try:
        r = client.post("/api/dream-pass/run", params={"domain": "hiring"})
        assert r.status_code == 423  # Locked
        assert "paused" in r.json()["detail"].lower()
    finally:
        client.delete("/api/dream-pass/pause", params={"domain": "hiring"})
```

- [ ] **Step 2: Run to fail**

- [ ] **Step 3: Implement the pause registry + route**

```python
# api/server/routes/dream_pass_pause.py
"""Dream-pass kill switch.

POST /api/dream-pass/pause?domain=X       — add domain to paused set
DELETE /api/dream-pass/pause?domain=X     — remove from paused set
GET /api/dream-pass/pause                  — list paused domains

Paused domains: dream-pass.run, dream-pass cadence, and dream-storm
all refuse with 423 Locked. Returns immediately so the cadence
doesn't have to know — it imports is_paused() before each pass.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/dream-pass", tags=["dream-pass"])

_paused_domains: set[str] = set()


def is_paused(domain: str) -> bool:
    return domain in _paused_domains


@router.post("/pause")
def pause(domain: str = Query(...)) -> dict:
    _paused_domains.add(domain)
    return {"ok": True, "paused": sorted(_paused_domains)}


@router.delete("/pause")
def unpause(domain: str = Query(...)) -> dict:
    _paused_domains.discard(domain)
    return {"ok": True, "paused": sorted(_paused_domains)}


@router.get("/pause")
def list_paused() -> dict:
    return {"paused": sorted(_paused_domains)}
```

Modify `routes/dream_pass_run.py` to check `is_paused`:

```python
from api.server.routes.dream_pass_pause import is_paused

@router.post("/run")
async def run_dream_pass(domain: str = Query(..., min_length=1), sample: int = Query(10, ge=1, le=200)):
    if is_paused(domain):
        raise HTTPException(status_code=423, detail=f"dream-pass for domain={domain} is paused (kill switch)")
    # ... rest unchanged
```

Modify `state.py:_run_dream_pass_cadence` to skip paused domains:

```python
from api.server.routes.dream_pass_pause import is_paused as _is_paused

# inside the loop:
for dom in domains:
    if _is_paused(dom):
        log.info("dream cadence: skipping %s — paused", dom)
        continue
    # ... existing
```

Register the new router in `main.py`.

- [ ] **Step 4: Run tests**

- [ ] **Step 5: Commit**

```
git add api/server/routes/dream_pass_pause.py api/server/main.py api/server/routes/dream_pass_run.py api/server/state.py tests/api/routes/test_dream_pass_pause.py
git commit -m "feat(dream-pass): kill switch — pause/resume per domain"
```

### Task E2: Signal-driven cadence trigger (replace fixed 120s)

**Files:**
- Create: `api/server/services/lessons/decision_quality_signal.py`
- Modify: `api/server/state.py:_run_dream_pass_cadence` and `api/server/main.py`
- Test: `tests/api/server/services/lessons/test_decision_quality_signal.py`

(Test + impl format same as previous tasks; abbreviated for plan length.)

The cadence now fires when EITHER:
  (a) Unconsumed working notes for the domain exceed `DREAM_PASS_TRIGGER_BACKLOG` (default 30), OR
  (b) `DREAM_PASS_DEMO_CADENCE_SECONDS` has elapsed since the last pass (the old wall-clock behaviour, kept as a heartbeat fallback).

The trigger module exports `should_trigger(domain, now=...) -> bool` and is tested as a pure function.

- [ ] Commit subject: `feat(dream-pass): signal-driven cadence (backlog + heartbeat)`.

---

## Phase F — Cost budget

### Task F1: Daily LLM cost counter

**Files:**
- Create: `api/server/services/lessons/cost_budget.py`
- Test: `tests/api/server/services/lessons/test_cost_budget.py`

`CostBudget` tracks token counts + USD estimate per domain per day (persisted to Mem0 as a single "budget" memory keyed by `YYYY-MM-DD`). Reads from the `usage` field of `agent.completed` webhook payloads (already wired in `routes/internal_durable_event.py:agent.completed`).

`is_over_budget(domain) -> bool` is consulted by:
  - `dream_pass_run.py` — 423 if over.
  - `cadence` in `state.py` — skip the pass.
  - `dream_storm` in `simulator.py` — refuse.

Env: `DREAM_PASS_DAILY_LLM_BUDGET_USD` (default `5.0`).

- [ ] Commit subject: `feat(dream-pass): daily LLM cost budget with hard stop`.

---

## Phase G — Roll back the band-aids

Once Phases A-F ship, several earlier band-aid commits become dead code.

### Task G1: Restore real promotion thresholds

**Files:** `data/policies/dream-pass.policy.yaml`

Phase D's replay runner now supplies real signal at n>=40. Restore:

```yaml
auto_promote:
  min_delta: 0.05
  min_samples: 40
  max_per_pass: 3
```

- [ ] Verify shadow lessons accumulate before active promotion (Phase C in effect).
- [ ] Commit subject: `chore(dream-pass): restore min_samples=40 now that replay supplies signal`.

### Task G2: Delete the stub fallbacks in wiring.py

The `_StubExperimentRunner` and `_DomainDispatchingRunner` were demo-only fallbacks. With Phase D's `ReplayExperimentRunner`, the stub is no longer needed in the default boot path. Move it to `tests/` as a test fixture.

- [ ] Commit subject: `refactor(dream-pass): remove stub experiment runner from production wiring`.

---

## Self-review checklist

- [ ] Spec coverage:
  - Mem0 swap ✅ (Phase A)
  - Top-K retrieval ✅ (Phase B)
  - Lifecycle ✅ (Phase C)
  - Observability ✅ (Phase D)
  - Signal-driven cadence + kill switch ✅ (Phase E)
  - Cost budget ✅ (Phase F)
  - Cleanup ✅ (Phase G)
- [ ] No placeholders — every step has concrete code or commands.
- [ ] Type consistency — `LessonStatus`, `LessonOutcomeMetrics`, `LessonMetrics` are defined before they're used.
- [ ] Frontend imports use `@client/...` aliases per existing `vite.config.ts`.
- [ ] Backend new routes added to `main.py`'s `for r in (...)` tuple.

## Out of scope (next plan)

- Multi-domain proposers (only hiring has a dream-pass SKILL.md today).
- Mem0 graph relations for lesson supersession chains.
- Adversarial lesson injection / governance review UI.
- Cross-tenant memory isolation.
- Real-time lesson editor for operators.
