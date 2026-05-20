# Memory Layer Visualisation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the substrate's **dreaming + memory** visible and demoable: emit live bus events from `DreamPassOrchestrator`, add a domain-generic Memory REST surface, build a Memory page into the Fleet UI alongside Dashboard / Constellation, and ship a one-click "trigger dream pass" + "dream storm" demo path that fires the loop end-to-end in seconds.

**Architecture:**

1. **Bus events at every dream stage.** The orchestrator already writes `DreamPass` and `Experiment` Kuzu nodes (`api/server/services/dream_pass/orchestrator.py:192-266`). Add a sibling `_emit(...)` next to each `_record_*` so every stage also fires a typed `FleetEvent` onto `app_state.bus`. Read-only consumers (whats-new, ticker, SSE bridge, new Memory page) get live updates with zero polling.
2. **App-state singletons for the dream stack.** Construct one `LessonStore`, one `LessonGovernor`, one `WorkingMemoryStore`, and one `DreamPassOrchestrator` on `AppState.__init__` so HTTP routes can call `app_state.dream_pass_orchestrator.run_pass(...)`. Tests pass mock collaborators in; production wires real ones.
3. **Domain-generic Memory REST surface.** New `routes/memory.py` exposes four GETs (`working-notes`, `lessons/active`, `dream-passes/recent`, `experiments/recent`) that read existing Kuzu nodes / lesson store — no schema changes.
4. **On-demand trigger + dream storm.** `POST /api/dream-pass/run?domain=hiring` runs one pass; `POST /api/simulator/dream-storm?domains=hiring,vendor_kyc&runs=3` runs N passes per domain back-to-back. Both honour the AGT kernel via the existing governor.
5. **Fleet UI Memory page.** New `/memory` route, three live columns: Working memory ticker (left), Active lessons grid (centre), Dream-pass timeline (right). Subscribes to existing `/api/stream/fleet` and the new dream.* event types so it auto-updates.

**Tech Stack:** Python 3.11, FastAPI, existing `EventBus` (`api/shared/events.py`), existing Kuzu via `EntityGraph`, existing AGT kernel, existing dream-pass machinery in `api/server/services/dream_pass/`. Frontend: React 19, Vite, existing `useSSE` / `useThrottledFetch` hooks, no new third-party deps.

---

## ⚠️ Relationship to other plans

- `docs/superpowers/plans/2026-05-19-dreaming-sessions.md` (committed, **not started**) replaces the human approval flow with a cron-based scheduler. It is **complementary**, not blocking: this plan only adds new visibility surfaces + an on-demand trigger; it does not touch the policy verdicts or the flagged-approval portal that plan removes. If both ship, the cron-scheduled passes will appear in this plan's UI automatically because both feed the same `DreamPass` / `Experiment` Kuzu nodes.
- `docs/superpowers/plans/2026-05-19-dream-pass-overview.md` documents the dream-pass mental model — read for context if you are new to the subsystem.

---

## File Structure

**New files:**
- `api/shared/dream_events.py` — `FleetEvent` subtype constants for the six dream stages
- `api/server/services/dream_pass/wiring.py` — `build_demo_orchestrator(graph, bus, audit)` factory used by `state.py` and tests
- `api/server/routes/memory.py` — `GET /api/memory/working-notes`, `lessons/active`, `dream-passes/recent`, `experiments/recent`
- `api/server/routes/dream_pass_run.py` — `POST /api/dream-pass/run` (on-demand trigger)
- `web/client/hooks/useMemoryQueries.ts` — polled fetch + SSE refresh for the four memory endpoints
- `web/client/routes/Memory.tsx` — three-column layout
- `web/client/components/memory/WorkingMemoryColumn.tsx` — left column, live ticker
- `web/client/components/memory/ActiveLessonsColumn.tsx` — centre column, grid
- `web/client/components/memory/DreamPassColumn.tsx` — right column, timeline + expand-on-click experiment details
- `tests/api/server/services/dream_pass/test_orchestrator_events.py`
- `tests/api/server/services/dream_pass/test_wiring.py`
- `tests/api/server/routes/test_memory.py`
- `tests/api/server/routes/test_dream_pass_run.py`
- `tests/api/server/routes/test_simulator_dream_storm.py`
- `web/client/hooks/__tests__/useMemoryQueries.test.tsx`
- `web/client/routes/__tests__/Memory.test.tsx`

**Modified files:**
- `api/server/services/dream_pass/orchestrator.py` — accept an optional `bus: EventBus` arg, emit six event types from existing `_record_*` sites
- `api/server/state.py` — construct `lesson_store`, `working_memory_store`, `lesson_governor`, `dream_pass_orchestrator` in `__init__`
- `api/server/main.py` — `app.include_router(memory_router)` + `app.include_router(dream_pass_run_router)`
- `api/server/routes/simulator.py` — add `POST /api/simulator/dream-storm`
- `api/server/routes/stream.py` — no change (existing `/api/stream/fleet` forwards all bus events; dream.* land for free)
- `web/client/components/feed/LeftRail.tsx` — add `Memory` link between `Dashboard` and `Constellation`
- `web/client/App.tsx` — register `/memory` route → `Memory` component
- `web/blueprint/src/pages/ConstellationPage.tsx` — (Phase 5 only, deferred to follow-on plan)

**Deleted files:** none.

---

## Conventions

- **TDD:** every backend task starts with a failing pytest. UI tasks start with a failing vitest. No implementation lands before a red test.
- **No new dependencies.** Reuse `EventBus`, `EntityGraph`, `useSSE`, `useThrottledFetch`.
- **Domain-generic.** No hard-coding of `hiring`, `vendor_kyc`, etc. in routes, hooks, or components. Domain is always a filter parameter.
- **Off-by-default for demo flags.** `DREAM_PASS_DEMO_CADENCE_SECONDS` is the only env added; unset = no extra loop fires. The on-demand trigger and the dream-storm are gated by no env — they are explicit operator clicks.
- **Read-only on the operator side.** The Memory page never mutates lessons. The only writing path is the dream-pass loop itself.
- **Reuse `app_state.entities`** in routes; do not construct a second `EntityGraph` (it holds a Kuzu single-writer file lock).
- **Stage handler pattern from `routes/ticker.py`** for SSE — async queue + `bus.on_any` subscription + `EventSourceResponse`.
- **Kuzu Cypher tips (verified in memory):** `Date.parse` requires UTC; param `$when` is reserved; combine prop-map and `WHERE` only in `WHERE`; `LIMIT` does not accept params; `$map` SET merge is not supported.

---

## Task 1: Define dream-pass bus event constants

**Files:**
- Create: `api/shared/dream_events.py`
- Test: `tests/api/shared/test_dream_events.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/shared/test_dream_events.py
from api.shared.dream_events import (
    DREAM_PASS_STARTED, DREAM_PROPOSAL_GENERATED, DREAM_EXPERIMENT_SCORED,
    DREAM_LESSON_PROMOTED, DREAM_LESSON_REJECTED, DREAM_PASS_FINISHED,
    ALL_DREAM_EVENT_TYPES,
)


def test_event_constants_are_distinct_dotted_strings():
    constants = [
        DREAM_PASS_STARTED, DREAM_PROPOSAL_GENERATED, DREAM_EXPERIMENT_SCORED,
        DREAM_LESSON_PROMOTED, DREAM_LESSON_REJECTED, DREAM_PASS_FINISHED,
    ]
    assert len(set(constants)) == len(constants)
    for c in constants:
        assert c.startswith("dream.")
        assert " " not in c


def test_all_dream_event_types_enumerates_every_constant():
    assert set(ALL_DREAM_EVENT_TYPES) == {
        DREAM_PASS_STARTED, DREAM_PROPOSAL_GENERATED, DREAM_EXPERIMENT_SCORED,
        DREAM_LESSON_PROMOTED, DREAM_LESSON_REJECTED, DREAM_PASS_FINISHED,
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/shared/test_dream_events.py -v`
Expected: `ModuleNotFoundError: No module named 'api.shared.dream_events'`

- [ ] **Step 3: Write minimal implementation**

```python
# api/shared/dream_events.py
"""Bus event type constants for the dream-pass loop.

Every stage in DreamPassOrchestrator.run_pass emits one of these onto
app_state.bus so the live SSE stream (and the Fleet UI Memory page)
can show dreaming as it happens.
"""
from __future__ import annotations

DREAM_PASS_STARTED      = "dream.pass.started"
DREAM_PROPOSAL_GENERATED = "dream.proposal.generated"
DREAM_EXPERIMENT_SCORED  = "dream.experiment.scored"
DREAM_LESSON_PROMOTED    = "dream.lesson.promoted"
DREAM_LESSON_REJECTED    = "dream.lesson.rejected"
DREAM_PASS_FINISHED      = "dream.pass.finished"

ALL_DREAM_EVENT_TYPES: tuple[str, ...] = (
    DREAM_PASS_STARTED, DREAM_PROPOSAL_GENERATED, DREAM_EXPERIMENT_SCORED,
    DREAM_LESSON_PROMOTED, DREAM_LESSON_REJECTED, DREAM_PASS_FINISHED,
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/shared/test_dream_events.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add api/shared/dream_events.py tests/api/shared/test_dream_events.py
git commit -m "feat(dream-pass): introduce bus event type constants"
```

---

## Task 2: Emit bus events from `DreamPassOrchestrator`

**Files:**
- Modify: `api/server/services/dream_pass/orchestrator.py`
- Test: `tests/api/server/services/dream_pass/test_orchestrator_events.py`

The orchestrator currently has six "stage" sites: `_record_dream_pass_start`, the candidate iteration (proposal + experiment + promote/reject/flagged branches), and `_record_dream_pass_complete`. Each becomes a bus emit too.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/server/services/dream_pass/test_orchestrator_events.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.shared.dream_events import (
    DREAM_PASS_STARTED, DREAM_PROPOSAL_GENERATED, DREAM_EXPERIMENT_SCORED,
    DREAM_LESSON_PROMOTED, DREAM_LESSON_REJECTED, DREAM_PASS_FINISHED,
)
from api.shared.events import EventBus
from api.server.services.dream_pass.orchestrator import DreamPassOrchestrator
from api.server.services.dream_pass.proposer import StubProposer
from api.server.services.dream_pass.types import DreamSkill, Experiment


@pytest.mark.asyncio
async def test_orchestrator_emits_one_event_per_stage() -> None:
    skill = DreamSkill(domain='hiring', version='1.0',
                       max_candidates_per_pass=2, max_experiments_per_pass=2, body='x')
    bus = EventBus()
    received: list[tuple[str, dict]] = []
    bus.on_any(lambda ev: received.append((ev.type, ev.model_dump())))

    partitioner = MagicMock()
    partitioner.next_split.return_value = MagicMock(held_out_ids=('C-001', 'C-002'))
    experiment_runner = MagicMock()
    experiment_runner.run = AsyncMock(side_effect=lambda **kw: Experiment(
        id=kw['experiment_id'], candidate_lesson_id=kw['candidate_lesson_id'],
        control_score=0.7, treatment_score=(0.8 if 'winner' in kw['candidate_body'] else 0.65),
        n_samples=40,
    ))
    proposer = StubProposer(candidates=[('winner lesson', 'good'), ('loser lesson', 'bad')])
    policy = MagicMock()
    policy.evaluate.side_effect = lambda **kw: MagicMock(
        verdict=('promote' if 'winner' in kw['candidate'].body else 'reject'),
        reason='ok',
    )
    governor = MagicMock()

    orchestrator = DreamPassOrchestrator(
        governor=governor, proposer=proposer, partitioner=partitioner,
        experiment_runner=experiment_runner, policy=policy,
        list_persona_ids=lambda d: ['C-001', 'C-002'],
        load_cvs=lambda ids: [{'candidate_id': i} for i in ids],
        load_active_lessons=lambda d: [],
        load_recent_runs=lambda d: [],
        load_working_notes=lambda agents: [],
        rubric=MagicMock(min_samples=40),
        bus=bus,
    )

    await orchestrator.run_pass(skill=skill, sample_size=2)

    types = [t for t, _ in received]
    assert types[0] == DREAM_PASS_STARTED
    assert types[-1] == DREAM_PASS_FINISHED
    assert types.count(DREAM_PROPOSAL_GENERATED) == 2
    assert types.count(DREAM_EXPERIMENT_SCORED) == 2
    assert types.count(DREAM_LESSON_PROMOTED) == 1
    assert types.count(DREAM_LESSON_REJECTED) == 1


@pytest.mark.asyncio
async def test_orchestrator_without_bus_does_not_raise() -> None:
    """Bus is optional so existing call sites and tests still pass."""
    skill = DreamSkill(domain='hiring', version='1.0',
                       max_candidates_per_pass=1, max_experiments_per_pass=1, body='x')
    partitioner = MagicMock()
    partitioner.next_split.return_value = MagicMock(held_out_ids=('C-001',))
    experiment_runner = MagicMock()
    experiment_runner.run = AsyncMock(return_value=Experiment(
        id='e', candidate_lesson_id='c', control_score=0.7, treatment_score=0.8, n_samples=40))
    orchestrator = DreamPassOrchestrator(
        governor=MagicMock(),
        proposer=StubProposer(candidates=[('x', 'y')]),
        partitioner=partitioner,
        experiment_runner=experiment_runner,
        policy=MagicMock(evaluate=lambda **kw: MagicMock(verdict='promote', reason='ok')),
        list_persona_ids=lambda d: ['C-001'],
        load_cvs=lambda ids: [{}],
        load_active_lessons=lambda d: [],
        load_recent_runs=lambda d: [],
        load_working_notes=lambda agents: [],
        rubric=MagicMock(min_samples=40),
    )
    result = await orchestrator.run_pass(skill=skill, sample_size=1)
    assert len(result.promoted_lesson_ids) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/server/services/dream_pass/test_orchestrator_events.py -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'bus'`.

- [ ] **Step 3: Add `bus` arg + emit calls to the orchestrator**

Edit `api/server/services/dream_pass/orchestrator.py`. At the imports, add:

```python
from api.shared.dream_events import (
    DREAM_PASS_STARTED, DREAM_PROPOSAL_GENERATED, DREAM_EXPERIMENT_SCORED,
    DREAM_LESSON_PROMOTED, DREAM_LESSON_REJECTED, DREAM_PASS_FINISHED,
)
from api.shared.events import EventBus, FleetEvent
```

In `__init__`, add a new optional kwarg after `graph: EntityGraph | None = None`:

```python
        bus: EventBus | None = None,
```

…and store it:

```python
        self._bus = bus
```

Add a private helper at the bottom of the class:

```python
    def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        """Fire-and-forget bus emit. Silent when no bus configured (tests)."""
        if self._bus is None:
            return
        try:
            self._bus.emit(FleetEvent(type=event_type, **payload))
        except Exception:  # pragma: no cover — never let observability break the loop
            import logging
            logging.getLogger(__name__).warning(
                "dream-pass: bus emit failed for %s", event_type, exc_info=True,
            )
```

Inside `run_pass`, after the existing `self._record_dream_pass_start(...)` call, add:

```python
        self._emit(DREAM_PASS_STARTED, {
            "workflow_id": dream_pass_id,
            "domain": skill.domain,
            "skill_version": skill.version,
        })
```

After `candidates = await self._propose(...)` add one emit per candidate:

```python
        for candidate in candidates[: skill.max_candidates_per_pass]:
            self._emit(DREAM_PROPOSAL_GENERATED, {
                "workflow_id": dream_pass_id,
                "domain": skill.domain,
                "candidate_lesson_id": candidate.id,
                "body_preview": candidate.body[:140],
            })
```

(Note: this is a new sibling loop *before* the existing experiment loop — the existing one keeps its own iteration.)

Inside the existing experiment loop, after `experiments.append(experiment)`, add:

```python
            self._emit(DREAM_EXPERIMENT_SCORED, {
                "workflow_id": dream_pass_id,
                "domain": skill.domain,
                "experiment_id": experiment.id,
                "candidate_lesson_id": experiment.candidate_lesson_id,
                "control_score": experiment.control_score,
                "treatment_score": experiment.treatment_score,
                "delta": experiment.delta,
                "n_samples": experiment.n_samples,
            })
```

In the `decision.verdict == 'promote'` branch, after `self._record_experiment(...)`:

```python
                self._emit(DREAM_LESSON_PROMOTED, {
                    "workflow_id": dream_pass_id,
                    "domain": skill.domain,
                    "lesson_id": lesson.id,
                    "body_preview": lesson.body[:140],
                    "delta": experiment.delta,
                })
```

In the `decision.verdict == 'reject'` branch, after `self._record_experiment(...)`:

```python
                self._emit(DREAM_LESSON_REJECTED, {
                    "workflow_id": dream_pass_id,
                    "domain": skill.domain,
                    "candidate_lesson_id": candidate.id,
                    "delta": experiment.delta,
                    "reason": decision.reason,
                })
```

After the existing `self._record_dream_pass_complete(...)`:

```python
        self._emit(DREAM_PASS_FINISHED, {
            "workflow_id": dream_pass_id,
            "domain": skill.domain,
            "candidates_proposed": len(candidates[: skill.max_candidates_per_pass]),
            "lessons_promoted": len(promoted),
            "lessons_rejected": len(rejected),
            "lessons_flagged": len(flagged),
        })
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/api/server/services/dream_pass/ -v`
Expected: all green (existing `test_orchestrator.py` + new `test_orchestrator_events.py`).

- [ ] **Step 5: Commit**

```bash
git add api/server/services/dream_pass/orchestrator.py tests/api/server/services/dream_pass/test_orchestrator_events.py
git commit -m "feat(dream-pass): emit live bus events from every stage"
```

---

## Task 3: Demo-orchestrator factory

The full orchestrator wires 11 collaborators. A `build_demo_orchestrator(graph, bus, audit)` factory hides the wiring so `state.py` and routes don't repeat it.

**Files:**
- Create: `api/server/services/dream_pass/wiring.py`
- Test: `tests/api/server/services/dream_pass/test_wiring.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/server/services/dream_pass/test_wiring.py
from unittest.mock import MagicMock

import pytest

from api.shared.events import EventBus
from api.server.services.audit_logger import AuditLogger
from api.server.services.dream_pass.orchestrator import DreamPassOrchestrator
from api.server.services.dream_pass.wiring import build_demo_orchestrator


def test_factory_returns_a_real_orchestrator():
    graph = MagicMock()
    orchestrator = build_demo_orchestrator(graph=graph, bus=EventBus(), audit=AuditLogger())
    assert isinstance(orchestrator, DreamPassOrchestrator)


def test_factory_with_no_graph_still_works():
    """The orchestrator already supports graph=None — factory must too."""
    orchestrator = build_demo_orchestrator(graph=None, bus=EventBus(), audit=AuditLogger())
    assert isinstance(orchestrator, DreamPassOrchestrator)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/server/services/dream_pass/test_wiring.py -v`
Expected: `ModuleNotFoundError: No module named 'api.server.services.dream_pass.wiring'`

- [ ] **Step 3: Write the factory**

```python
# api/server/services/dream_pass/wiring.py
"""Single-call factory that constructs the dream-pass + lessons stack
with sensible demo defaults. Used by AppState during startup and by
on-demand routes that need to spin a pass against the live entity graph
without rebuilding the wiring each call.
"""
from __future__ import annotations

from typing import Any

from api.shared.events import EventBus
from api.server.services.audit_logger import AuditLogger
from api.server.services.dream_pass.experiment import ExperimentRunner
from api.server.services.dream_pass.orchestrator import DreamPassOrchestrator
from api.server.services.dream_pass.partitioner import CorpusPartitioner
from api.server.services.dream_pass.policy import PromotionPolicy
from api.server.services.dream_pass.proposer import StubProposer
from api.server.services.entity_graph import EntityGraph
from api.server.services.governance.kernel import kernel
from api.server.services.lessons.governor import LessonGovernor
from api.server.services.lessons.kuzu_provenance import KuzuLessonProvenance
from api.server.services.lessons.store import InMemoryLessonStore
from api.server.services.lessons.working_memory_store import InMemoryWorkingMemoryStore
from api.server.services.scoring.types import Rubric


def build_demo_orchestrator(
    *,
    graph: EntityGraph | None,
    bus: EventBus,
    audit: AuditLogger,
) -> DreamPassOrchestrator:
    """Wire dream-pass with InMemory stores + StubProposer for demo runs.

    - StubProposer returns three deterministic candidate lessons; replace
      with GHCPProposer once an API key is configured.
    - InMemoryLessonStore / InMemoryWorkingMemoryStore mean lessons reset
      on server restart — fine for the demo loop where we explicitly
      trigger passes.
    - Kuzu provenance writes still go to the real graph so the Memory page
      can read DreamPass / Experiment nodes after restart.
    """
    lesson_store = InMemoryLessonStore()
    working_store = InMemoryWorkingMemoryStore()
    provenance = (
        KuzuLessonProvenance(graph) if graph is not None else _NoopProvenance()
    )
    governor = LessonGovernor(
        store=lesson_store, kernel=lambda: kernel(), audit=audit,
        provenance=provenance, actor='operator:demo',
    )
    proposer = StubProposer(candidates=[
        ('Trigger: candidate lacks recent leadership signal. '
         'Action: down-weight when role grade ≥ G5.', 'demo seed 1'),
        ('Trigger: jurisdiction is DE and Betriebsrat consultation missing. '
         'Action: route to gc before any offer.', 'demo seed 2'),
        ('Trigger: budget already at 90% and headcount delta > 0. '
         'Action: require finance_bp endorsement.', 'demo seed 3'),
    ])
    return DreamPassOrchestrator(
        governor=governor,
        proposer=proposer,
        partitioner=CorpusPartitioner(),
        experiment_runner=ExperimentRunner(),
        policy=PromotionPolicy(),
        list_persona_ids=lambda domain: [f'P-{i:03d}' for i in range(1, 11)],
        load_cvs=lambda ids: [{'candidate_id': i} for i in ids],
        load_active_lessons=lambda domain: list(lesson_store.search(domain=domain)),
        load_recent_runs=lambda domain: [],
        load_working_notes=lambda agents: list(working_store.list_recent(limit=20)),
        rubric=Rubric(min_samples=10, weights={}),
        mark_working_note_consumed=working_store.mark_consumed,
        graph=graph,
        bus=bus,
    )


class _NoopProvenance:
    """Stand-in when there's no graph (unit tests). Matches the duck shape
    of KuzuLessonProvenance enough for the governor's calls."""
    def record_promotion(self, *args, **kwargs) -> None: return None
    def record_pruning(self, *args, **kwargs) -> None: return None
```

> **Note on signatures:** verify `CorpusPartitioner()`, `ExperimentRunner()`, `PromotionPolicy()`, `Rubric(min_samples=..., weights={})`, `InMemoryLessonStore.search(domain=)`, `InMemoryWorkingMemoryStore.list_recent(limit=)`, `KuzuLessonProvenance(graph)`, `LessonGovernor.__init__` against the actual modules. If a constructor needs args we haven't provided, **fix it in this task** rather than papering over with `MagicMock`; the goal is real wiring.

- [ ] **Step 4: Run tests + smoke**

Run: `uv run pytest tests/api/server/services/dream_pass/test_wiring.py -v`
Expected: 2 passed.

Run a manual smoke (no event loop needed for construction):
```bash
uv run python -c "
from unittest.mock import MagicMock
from api.shared.events import EventBus
from api.server.services.audit_logger import AuditLogger
from api.server.services.dream_pass.wiring import build_demo_orchestrator
o = build_demo_orchestrator(graph=MagicMock(), bus=EventBus(), audit=AuditLogger())
print('built:', type(o).__name__)
"
```
Expected: `built: DreamPassOrchestrator`

- [ ] **Step 5: Commit**

```bash
git add api/server/services/dream_pass/wiring.py tests/api/server/services/dream_pass/test_wiring.py
git commit -m "feat(dream-pass): demo-orchestrator factory wires real Kuzu provenance"
```

---

## Task 4: Hang the orchestrator off `app_state`

**Files:**
- Modify: `api/server/state.py` (insert new attribute construction near line 156, after `self.blob_store = _build_blob_store()`)
- Test: extend `tests/api/server/test_state.py` (or create if absent)

- [ ] **Step 1: Write the failing test**

```python
# tests/api/server/test_state_dream_orchestrator.py
"""AppState constructs a dream-pass orchestrator on init."""
from api.server.services.dream_pass.orchestrator import DreamPassOrchestrator


def test_app_state_exposes_dream_pass_orchestrator():
    # Import-time AppState construction is already done by other tests
    # using ``from api.server.state import app_state``.
    from api.server.state import app_state
    assert isinstance(app_state.dream_pass_orchestrator, DreamPassOrchestrator)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/server/test_state_dream_orchestrator.py -v`
Expected: `AttributeError: 'AppState' object has no attribute 'dream_pass_orchestrator'`

- [ ] **Step 3: Wire it in `state.py`**

At the top of `api/server/state.py` add the import (near the other dream-pass-adjacent imports):

```python
from api.server.services.dream_pass.wiring import build_demo_orchestrator
```

In `AppState.__init__`, after the existing `self.blob_store = _build_blob_store()` line, add:

```python
        # Dream-pass + lessons stack. Constructed once so HTTP routes
        # can call app_state.dream_pass_orchestrator.run_pass(...) and
        # the on-screen Memory page sees one consistent set of lessons.
        # See api/server/services/dream_pass/wiring.py for the wiring
        # rationale and demo defaults.
        self.dream_pass_orchestrator = build_demo_orchestrator(
            graph=self.entities if self._entity_plane_enabled else None,
            bus=self.bus,
            audit=self.audit,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/server/test_state_dream_orchestrator.py -v`
Expected: 1 passed.

Also run the broader state-related tests:
```bash
uv run pytest tests/api/server/test_state.py tests/api/server/test_state_dream_orchestrator.py -v
```
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add api/server/state.py tests/api/server/test_state_dream_orchestrator.py
git commit -m "feat(dream-pass): hang orchestrator off app_state singleton"
```

---

## Task 5: `POST /api/dream-pass/run` on-demand trigger

**Files:**
- Create: `api/server/routes/dream_pass_run.py`
- Modify: `api/server/main.py` (add import + include_router)
- Test: `tests/api/server/routes/test_dream_pass_run.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/server/routes/test_dream_pass_run.py
from fastapi.testclient import TestClient

from api.server.main import app

client = TestClient(app)


def test_run_endpoint_returns_pass_summary():
    r = client.post("/api/dream-pass/run", params={"domain": "hiring", "sample": 10})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["domain"] == "hiring"
    assert "dream_pass_id" in body
    assert body["candidates_proposed"] >= 0
    assert isinstance(body["promoted_lesson_ids"], list)
    assert isinstance(body["rejected_lesson_ids"], list)


def test_run_endpoint_rejects_unknown_domain():
    r = client.post("/api/dream-pass/run", params={"domain": "does-not-exist"})
    assert r.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/server/routes/test_dream_pass_run.py -v`
Expected: `404 Not Found` on the endpoint.

- [ ] **Step 3: Write the route**

```python
# api/server/routes/dream_pass_run.py
"""On-demand dream-pass trigger.

POST /api/dream-pass/run?domain=hiring&sample=10

Runs one dream pass against app_state.dream_pass_orchestrator and
returns a summary. Live progress is observable via the SSE stream
on /api/stream/fleet (event types `dream.*`).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from api.server.services.dream_pass.skill_loader import (
    DreamSkillLoadError, load_dream_skill,
)
from api.server.state import app_state

router = APIRouter(prefix="/api/dream-pass", tags=["dream-pass"])


@router.post("/run")
async def run_dream_pass(
    domain: str = Query(..., min_length=1),
    sample: int = Query(10, ge=1, le=200),
):
    try:
        skill = load_dream_skill(domain)
    except DreamSkillLoadError as ex:
        raise HTTPException(status_code=422, detail=str(ex))
    result = await app_state.dream_pass_orchestrator.run_pass(
        skill=skill, sample_size=sample,
    )
    return {
        "dream_pass_id": result.dream_pass_id,
        "domain": result.domain,
        "candidates_proposed": len(result.experiments),
        "promoted_lesson_ids": list(result.promoted_lesson_ids),
        "rejected_lesson_ids": list(result.rejected_lesson_ids),
        "flagged_lesson_ids": list(result.flagged_lesson_ids),
        "experiments": [
            {
                "id": e.id, "candidate_lesson_id": e.candidate_lesson_id,
                "control_score": e.control_score, "treatment_score": e.treatment_score,
                "delta": e.delta, "n_samples": e.n_samples,
            }
            for e in result.experiments
        ],
    }
```

Modify `api/server/main.py`. Add near the other dream-pass import:

```python
from api.server.routes.dream_pass_run import router as dream_pass_run_router
```

Add `dream_pass_run_router` to the `for r in (...)` tuple at line 364.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/server/routes/test_dream_pass_run.py -v`
Expected: 2 passed.

Smoke against the live stack (the demo orchestrator's StubProposer returns 3 deterministic candidates, partitioner needs ≥ 1 persona id):
```bash
curl -s -X POST 'http://localhost:3101/api/dream-pass/run?domain=hiring&sample=5' | python3 -m json.tool
```
Expected: JSON with `dream_pass_id`, non-zero `candidates_proposed`, lesson id lists.

- [ ] **Step 5: Commit**

```bash
git add api/server/routes/dream_pass_run.py api/server/main.py tests/api/server/routes/test_dream_pass_run.py
git commit -m "feat(dream-pass): POST /api/dream-pass/run on-demand trigger"
```

---

## Task 6: Memory query API — `routes/memory.py`

Four GETs, each backed by data the orchestrator + governor already write. No new schema.

**Files:**
- Create: `api/server/routes/memory.py`
- Modify: `api/server/main.py` (import + include_router)
- Test: `tests/api/server/routes/test_memory.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/server/routes/test_memory.py
from fastapi.testclient import TestClient

from api.server.main import app

client = TestClient(app)


def test_working_notes_returns_list():
    r = client.get("/api/memory/working-notes", params={"limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert isinstance(body["items"], list)


def test_active_lessons_returns_list():
    r = client.get("/api/memory/lessons/active", params={"domain": "hiring"})
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["items"], list)


def test_dream_passes_recent_returns_list():
    r = client.get("/api/memory/dream-passes/recent", params={"limit": 10})
    assert r.status_code == 200
    body = r.json()
    items = body["items"]
    assert isinstance(items, list)
    for it in items:
        assert "id" in it and "domain" in it and "started_at" in it


def test_experiments_recent_returns_list():
    r = client.get("/api/memory/experiments/recent", params={"limit": 10})
    assert r.status_code == 200
    items = r.json()["items"]
    assert isinstance(items, list)
    for it in items:
        assert "id" in it
        assert "delta" in it
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/server/routes/test_memory.py -v`
Expected: 404s.

- [ ] **Step 3: Write the route**

```python
# api/server/routes/memory.py
"""Domain-generic memory layer surface.

Four read-only endpoints back the Fleet UI Memory page:
  GET /api/memory/working-notes?domain=&limit=
  GET /api/memory/lessons/active?domain=
  GET /api/memory/dream-passes/recent?limit=
  GET /api/memory/experiments/recent?limit=

All reads go through app_state singletons constructed in state.py.
No writes here — the only writers are the dream-pass loop and the
working-memory capture path inside persona_responder.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query

from api.server.state import app_state

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/memory", tags=["memory"])


def _graph():
    return getattr(app_state, "entities", None)


@router.get("/working-notes")
def working_notes(
    domain: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
) -> dict[str, list[dict[str, Any]]]:
    """Most recent WorkingNotes captured during persona decisions."""
    store = app_state.dream_pass_orchestrator._load_working_notes  # type: ignore[attr-defined]
    # The orchestrator's load_working_notes is a closure over the
    # InMemoryWorkingMemoryStore singleton from wiring.py; calling it
    # with no agents arg here would be domain-blind. Read the store
    # directly instead.
    from api.server.services.lessons.working_memory_store import (
        InMemoryWorkingMemoryStore,
    )
    inner = getattr(app_state, "_working_memory_store", None)
    if not isinstance(inner, InMemoryWorkingMemoryStore):
        return {"items": []}
    notes = list(inner.list_recent(limit=limit))
    if domain:
        notes = [n for n in notes if getattr(n, "domain", None) == domain]
    return {"items": [_note_to_dict(n) for n in notes]}


@router.get("/lessons/active")
def lessons_active(
    domain: str | None = Query(None),
) -> dict[str, list[dict[str, Any]]]:
    """Currently active (un-pruned) lessons. Optional domain filter."""
    store = getattr(app_state, "_lesson_store", None)
    if store is None:
        return {"items": []}
    rows = list(store.search(domain=domain) if domain else store.search())
    return {"items": [_lesson_to_dict(l) for l in rows]}


@router.get("/dream-passes/recent")
def dream_passes_recent(
    limit: int = Query(20, ge=1, le=200),
) -> dict[str, list[dict[str, Any]]]:
    """Recent DreamPass nodes, newest first."""
    g = _graph()
    if g is None:
        return {"items": []}
    try:
        rows = g.query(
            "MATCH (d:DreamPass) "
            "RETURN d.id AS id, d.domain AS domain, "
            "       d.skill_version AS skill_version, "
            "       d.started_at AS started_at, "
            "       d.completed_at AS completed_at, "
            "       d.status AS status, "
            "       d.candidates_proposed AS candidates_proposed, "
            "       d.candidates_promoted AS candidates_promoted "
            f"ORDER BY d.started_at DESC LIMIT {int(limit)}",
        )
    except Exception:
        log.exception("memory: dream-passes query failed")
        return {"items": []}
    return {"items": [{**r, **_iso_timestamps(r, ('started_at', 'completed_at'))} for r in rows]}


@router.get("/experiments/recent")
def experiments_recent(
    dream_pass_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
) -> dict[str, list[dict[str, Any]]]:
    """Recent Experiment nodes, optionally scoped to one dream pass."""
    g = _graph()
    if g is None:
        return {"items": []}
    where = "WHERE e.dream_pass_id = $dp" if dream_pass_id else ""
    params: dict[str, Any] = {"dp": dream_pass_id} if dream_pass_id else {}
    try:
        rows = g.query(
            "MATCH (e:Experiment) "
            f"{where} "
            "RETURN e.id AS id, e.dream_pass_id AS dream_pass_id, "
            "       e.candidate_lesson_id AS candidate_lesson_id, "
            "       e.control_score AS control_score, "
            "       e.treatment_score AS treatment_score, "
            "       e.delta AS delta, e.n_samples AS n_samples, "
            "       e.verdict AS verdict, e.run_at AS run_at "
            f"ORDER BY e.run_at DESC LIMIT {int(limit)}",
            params,
        )
    except Exception:
        log.exception("memory: experiments query failed")
        return {"items": []}
    return {"items": [{**r, **_iso_timestamps(r, ('run_at',))} for r in rows]}


def _note_to_dict(n: Any) -> dict[str, Any]:
    return {
        "id": getattr(n, "id", None),
        "domain": getattr(n, "domain", None),
        "agent": getattr(n, "agent", None),
        "body": getattr(n, "body", None),
        "captured_at": _iso(getattr(n, "captured_at", None)),
        "consumed_by_dream_pass": getattr(n, "consumed_by_dream_pass", None),
    }


def _lesson_to_dict(l: Any) -> dict[str, Any]:
    return {
        "id": getattr(l, "id", None),
        "body": getattr(l, "body", None),
        "domain": getattr(getattr(l, "scope", None), "domain", None),
        "promoted_at": _iso(getattr(getattr(l, "provenance", None), "promoted_at", None)),
        "rubric_score_delta": getattr(getattr(l, "provenance", None), "rubric_score_delta", None),
        "experiment_n": getattr(getattr(l, "provenance", None), "experiment_n", None),
        "proposed_by": getattr(getattr(l, "provenance", None), "proposed_by", None),
    }


def _iso(ts: Any) -> Any:
    return ts.isoformat() if hasattr(ts, "isoformat") else ts


def _iso_timestamps(row: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {k: _iso(row.get(k)) for k in keys}
```

> **Note:** the route reads `app_state._lesson_store` and `app_state._working_memory_store`. Extend Task 4 to set those attributes directly on AppState (so the route doesn't reach inside the closure). Add to `state.py` next to the orchestrator construction:
>
> ```python
> # Memory route reads these directly; orchestrator closes over them too.
> from api.server.services.lessons.store import InMemoryLessonStore
> from api.server.services.lessons.working_memory_store import InMemoryWorkingMemoryStore
> self._lesson_store = InMemoryLessonStore()
> self._working_memory_store = InMemoryWorkingMemoryStore()
> ```
>
> …and update `build_demo_orchestrator` to **accept** those stores as args instead of constructing its own, so all three writers (orchestrator, route, future scheduler) see the same in-memory instance.

Modify `api/server/main.py`:
```python
from api.server.routes.memory import router as memory_router
```
Add `memory_router` to the `for r in (...)` tuple at line 364.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/server/routes/test_memory.py -v`
Expected: 4 passed.

Smoke:
```bash
curl -s 'http://localhost:3101/api/memory/lessons/active' | python3 -m json.tool
curl -s 'http://localhost:3101/api/memory/dream-passes/recent?limit=5' | python3 -m json.tool
```

- [ ] **Step 5: Commit**

```bash
git add api/server/routes/memory.py api/server/main.py api/server/state.py api/server/services/dream_pass/wiring.py tests/api/server/routes/test_memory.py
git commit -m "feat(memory): GET /api/memory/{working-notes,lessons/active,dream-passes,experiments}"
```

---

## Task 7: Dream-storm simulator endpoint

**Files:**
- Modify: `api/server/routes/simulator.py` (add new endpoint near the existing `constellation-start` route)
- Test: `tests/api/server/routes/test_simulator_dream_storm.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/server/routes/test_simulator_dream_storm.py
from fastapi.testclient import TestClient

from api.server.main import app

client = TestClient(app)


def test_dream_storm_runs_n_passes_per_domain():
    r = client.post(
        "/api/simulator/dream-storm",
        params={"domains": "hiring", "runs": 2},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert len(body["passes"]) == 2
    assert all(p["domain"] == "hiring" for p in body["passes"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/server/routes/test_simulator_dream_storm.py -v`
Expected: 404 Not Found.

- [ ] **Step 3: Add the route**

Add to `api/server/routes/simulator.py` after the existing `constellation-start` route (around line 500):

```python
@router.post("/dream-storm")
async def dream_storm(
    domains: str = "hiring",
    runs: int = 3,
    sample: int = 10,
):
    """Fire N dream passes per domain back-to-back so the Memory page
    timeline fills in seconds. Demo-only: the autonomous cadence is
    DREAM_PASS_DEMO_CADENCE_SECONDS in state.py."""
    from api.server.services.dream_pass.skill_loader import (
        DreamSkillLoadError, load_dream_skill,
    )
    dom_list = [d.strip() for d in domains.split(",") if d.strip()]
    passes: list[dict] = []
    for dom in dom_list:
        try:
            skill = load_dream_skill(dom)
        except DreamSkillLoadError as ex:
            passes.append({"domain": dom, "error": str(ex)})
            continue
        for _ in range(max(1, int(runs))):
            result = await app_state.dream_pass_orchestrator.run_pass(
                skill=skill, sample_size=sample,
            )
            passes.append({
                "dream_pass_id": result.dream_pass_id,
                "domain": result.domain,
                "promoted": len(result.promoted_lesson_ids),
                "rejected": len(result.rejected_lesson_ids),
            })
    return {"ok": True, "count": len(passes), "passes": passes}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/server/routes/test_simulator_dream_storm.py -v`
Expected: 1 passed.

Smoke against the live stack:
```bash
curl -s -X POST 'http://localhost:3101/api/simulator/dream-storm?domains=hiring&runs=3' | python3 -m json.tool
```
Expected: 3 passes returned, dream-pass ids visible.

- [ ] **Step 5: Commit**

```bash
git add api/server/routes/simulator.py tests/api/server/routes/test_simulator_dream_storm.py
git commit -m "feat(simulator): POST /api/simulator/dream-storm fires N passes per domain"
```

---

## Task 8: Demo cadence env loop

**Files:**
- Modify: `api/server/state.py`
- Test: `tests/api/server/test_dream_cadence_loop.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/server/test_dream_cadence_loop.py
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_cadence_loop_no_op_when_env_unset(monkeypatch):
    monkeypatch.delenv("DREAM_PASS_DEMO_CADENCE_SECONDS", raising=False)
    from api.server.state import _run_dream_pass_cadence
    # When unset, the coroutine should return immediately.
    orchestrator = MagicMock()
    orchestrator.run_pass = AsyncMock()
    await asyncio.wait_for(_run_dream_pass_cadence(
        orchestrator, domains=("hiring",), interval_seconds=0
    ), timeout=1.0)
    orchestrator.run_pass.assert_not_called()


@pytest.mark.asyncio
async def test_cadence_loop_fires_when_interval_positive(monkeypatch):
    monkeypatch.setenv("DREAM_PASS_DEMO_CADENCE_SECONDS", "1")
    from api.server.state import _run_dream_pass_cadence
    orchestrator = MagicMock()
    orchestrator.run_pass = AsyncMock(return_value=MagicMock(promoted_lesson_ids=()))
    task = asyncio.create_task(_run_dream_pass_cadence(
        orchestrator, domains=("hiring",), interval_seconds=1,
    ))
    await asyncio.sleep(2.2)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert orchestrator.run_pass.call_count >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/server/test_dream_cadence_loop.py -v`
Expected: `ImportError: cannot import name '_run_dream_pass_cadence'`

- [ ] **Step 3: Add the loop to `state.py`**

Add this module-level function near the existing `_run_cadence` (around line 351):

```python
async def _run_dream_pass_cadence(
    orchestrator,
    *,
    domains: tuple[str, ...],
    interval_seconds: int,
) -> None:
    """Optional autonomous loop firing one dream pass per domain on a
    fixed wall-clock interval. Off unless DREAM_PASS_DEMO_CADENCE_SECONDS
    is set to a positive int. Sleeps cancel cleanly; failures of one
    domain do not block the next."""
    import asyncio as _asyncio
    import logging as _log
    if interval_seconds <= 0:
        return
    from api.server.services.dream_pass.skill_loader import (
        DreamSkillLoadError, load_dream_skill,
    )
    log = _log.getLogger(__name__)
    while True:
        for dom in domains:
            try:
                skill = load_dream_skill(dom)
                await orchestrator.run_pass(skill=skill, sample_size=10)
            except DreamSkillLoadError as ex:
                log.warning("dream cadence: skill %s missing (%s)", dom, ex)
            except Exception:
                log.exception("dream cadence: pass for %s failed", dom)
        try:
            await _asyncio.sleep(interval_seconds)
        except _asyncio.CancelledError:
            return
```

Inside `AppState.__init__`, near where `self._cadence_tasks` is appended to, add:

```python
        cadence_secs = int(os.getenv("DREAM_PASS_DEMO_CADENCE_SECONDS", "0") or "0")
        cadence_domains = tuple(
            d.strip() for d in os.getenv(
                "DREAM_PASS_DEMO_CADENCE_DOMAINS", "hiring",
            ).split(",") if d.strip()
        )
        if cadence_secs > 0:
            try:
                import asyncio as _asyncio
                _asyncio.get_running_loop()
                self._cadence_tasks.append(
                    _asyncio.create_task(_run_dream_pass_cadence(
                        self.dream_pass_orchestrator,
                        domains=cadence_domains,
                        interval_seconds=cadence_secs,
                    ))
                )
            except RuntimeError:
                pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/server/test_dream_cadence_loop.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add api/server/state.py tests/api/server/test_dream_cadence_loop.py
git commit -m "feat(dream-pass): optional DREAM_PASS_DEMO_CADENCE_SECONDS background loop"
```

---

## Task 9: Frontend hooks — `useMemoryQueries.ts`

**Files:**
- Create: `web/client/hooks/useMemoryQueries.ts`
- Test: `web/client/hooks/__tests__/useMemoryQueries.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// web/client/hooks/__tests__/useMemoryQueries.test.tsx
import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

import {
  useActiveLessons, useDreamPassesRecent, useWorkingNotes,
} from "../useMemoryQueries";

beforeEach(() => {
  globalThis.fetch = vi.fn(async (url: RequestInfo | URL) => {
    const u = String(url);
    if (u.includes("/api/memory/lessons/active")) {
      return new Response(JSON.stringify({ items: [{ id: "L1", body: "x" }] }), { status: 200 });
    }
    if (u.includes("/api/memory/dream-passes/recent")) {
      return new Response(JSON.stringify({ items: [{ id: "D1", domain: "hiring" }] }), { status: 200 });
    }
    if (u.includes("/api/memory/working-notes")) {
      return new Response(JSON.stringify({ items: [{ id: "N1" }] }), { status: 200 });
    }
    return new Response("{}", { status: 404 });
  }) as unknown as typeof fetch;
});


describe("useMemoryQueries", () => {
  it("loads active lessons", async () => {
    const { result } = renderHook(() => useActiveLessons("hiring"));
    await waitFor(() => expect(result.current.length).toBe(1));
    expect(result.current[0].id).toBe("L1");
  });

  it("loads recent dream passes", async () => {
    const { result } = renderHook(() => useDreamPassesRecent(10));
    await waitFor(() => expect(result.current.length).toBe(1));
    expect(result.current[0].id).toBe("D1");
  });

  it("loads working notes", async () => {
    const { result } = renderHook(() => useWorkingNotes(50));
    await waitFor(() => expect(result.current.length).toBe(1));
    expect(result.current[0].id).toBe("N1");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/client/hooks/__tests__/useMemoryQueries.test.tsx`
Expected: import error — module does not exist.

- [ ] **Step 3: Write the hook**

```ts
// web/client/hooks/useMemoryQueries.ts
//
// Polled fetches + SSE-driven refresh for the four memory endpoints.
// One hook per shape so components subscribe only to what they render.
// Uses the same throttled-fetch helper as useWorkflows / useExceptions
// so we don't fork connection-pool behaviour.
import { useCallback, useEffect, useState } from "react";
import { useSSE } from "./useSSE";
import { useThrottledFetch } from "./useThrottledFetch";

export interface ActiveLesson {
  id: string;
  body: string;
  domain: string | null;
  promoted_at: string | null;
  rubric_score_delta: number | null;
  experiment_n: number | null;
  proposed_by: string | null;
}

export interface DreamPassRow {
  id: string;
  domain: string;
  skill_version: string | null;
  started_at: string | null;
  completed_at: string | null;
  status: string | null;
  candidates_proposed: number | null;
  candidates_promoted: number | null;
}

export interface WorkingNote {
  id: string;
  domain: string | null;
  agent: string | null;
  body: string | null;
  captured_at: string | null;
  consumed_by_dream_pass: string | null;
}

interface Envelope<T> { items: T[] }

function useMemoryEndpoint<T>(url: string, refreshOnTypes: readonly string[]): T[] {
  const [items, setItems] = useState<T[]>([]);
  const refresh = useThrottledFetch<Envelope<T>>(
    url,
    (e) => setItems(e.items ?? []),
    750,
  );
  useEffect(() => { refresh(); }, [refresh]);
  useSSE<{ type: string }>(
    "/api/stream/fleet",
    useCallback((e) => {
      if (refreshOnTypes.includes(e.type)) refresh();
    }, [refresh, refreshOnTypes.join(",")]),
  );
  return items;
}

export function useActiveLessons(domain?: string): ActiveLesson[] {
  const url = domain
    ? `/api/memory/lessons/active?domain=${encodeURIComponent(domain)}`
    : "/api/memory/lessons/active";
  return useMemoryEndpoint<ActiveLesson>(url, ["dream.lesson.promoted"]);
}

export function useDreamPassesRecent(limit = 20): DreamPassRow[] {
  return useMemoryEndpoint<DreamPassRow>(
    `/api/memory/dream-passes/recent?limit=${limit}`,
    ["dream.pass.started", "dream.pass.finished"],
  );
}

export function useWorkingNotes(limit = 50, domain?: string): WorkingNote[] {
  const url = domain
    ? `/api/memory/working-notes?domain=${encodeURIComponent(domain)}&limit=${limit}`
    : `/api/memory/working-notes?limit=${limit}`;
  return useMemoryEndpoint<WorkingNote>(url, [
    // No explicit working-note event today; refresh on any pass-finished
    // so consumed-by-dream-pass markers update.
    "dream.pass.finished",
  ]);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/client/hooks/__tests__/useMemoryQueries.test.tsx`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add web/client/hooks/useMemoryQueries.ts web/client/hooks/__tests__/useMemoryQueries.test.tsx
git commit -m "feat(memory): useMemoryQueries hooks (lessons/passes/notes)"
```

---

## Task 10: Fleet UI Memory page

**Files:**
- Create: `web/client/routes/Memory.tsx`
- Create: `web/client/components/memory/WorkingMemoryColumn.tsx`
- Create: `web/client/components/memory/ActiveLessonsColumn.tsx`
- Create: `web/client/components/memory/DreamPassColumn.tsx`
- Test: `web/client/routes/__tests__/Memory.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// web/client/routes/__tests__/Memory.test.tsx
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import Memory from "../Memory";

beforeEach(() => {
  globalThis.fetch = vi.fn(async (url: RequestInfo | URL) => {
    const u = String(url);
    if (u.includes("/api/memory/lessons/active")) {
      return new Response(JSON.stringify({ items: [
        { id: "L-1", body: "Trigger: X. Action: Y.", domain: "hiring",
          promoted_at: "2026-05-20T08:00:00Z", rubric_score_delta: 0.12,
          experiment_n: 40, proposed_by: "ghcp" },
      ] }), { status: 200 });
    }
    if (u.includes("/api/memory/dream-passes/recent")) {
      return new Response(JSON.stringify({ items: [
        { id: "DP-1", domain: "hiring", skill_version: "1.0",
          started_at: "2026-05-20T07:55:00Z", completed_at: "2026-05-20T07:55:30Z",
          status: "complete", candidates_proposed: 3, candidates_promoted: 1 },
      ] }), { status: 200 });
    }
    if (u.includes("/api/memory/working-notes")) {
      return new Response(JSON.stringify({ items: [
        { id: "N-1", domain: "hiring", agent: "interview-recommender",
          body: "candidate weak on leadership", captured_at: "2026-05-20T07:50:00Z",
          consumed_by_dream_pass: null },
      ] }), { status: 200 });
    }
    return new Response("{}", { status: 404 });
  }) as unknown as typeof fetch;
});


describe("Memory route", () => {
  it("renders three columns with their respective data", async () => {
    render(<MemoryRouter><Memory /></MemoryRouter>);
    await waitFor(() => screen.getByText(/Working memory/i));
    expect(screen.getByText(/Active lessons/i)).toBeTruthy();
    expect(screen.getByText(/Dream passes/i)).toBeTruthy();
    await waitFor(() => screen.getByText(/Trigger: X/));
    expect(screen.getByText(/DP-1/)).toBeTruthy();
    expect(screen.getByText(/candidate weak on leadership/)).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/client/routes/__tests__/Memory.test.tsx`
Expected: import error.

- [ ] **Step 3: Write the three column components + the page**

```tsx
// web/client/components/memory/WorkingMemoryColumn.tsx
import { Brain } from "lucide-react";
import { useWorkingNotes } from "@client/hooks/useMemoryQueries";

export default function WorkingMemoryColumn({ domain }: { domain?: string }) {
  const notes = useWorkingNotes(50, domain);
  return (
    <section className="flex-1 min-w-0 bg-white border border-slate-200 rounded-lg p-3 dark:bg-slate-900 dark:border-slate-700">
      <header className="flex items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-100 mb-2">
        <Brain size={16} /> Working memory <span className="text-xs text-slate-400">({notes.length})</span>
      </header>
      <ul className="space-y-2 max-h-[70vh] overflow-y-auto">
        {notes.map((n) => (
          <li key={n.id} className="text-xs border-l-2 border-blue-400 pl-2">
            <div className="text-[10px] uppercase tracking-wide text-slate-400">{n.agent} · {n.domain ?? "—"}</div>
            <div className="text-slate-700 dark:text-slate-200">{n.body ?? <em>(empty)</em>}</div>
            <div className="text-[10px] text-slate-400 mt-0.5">{n.captured_at ?? "—"}{n.consumed_by_dream_pass ? " · consumed" : ""}</div>
          </li>
        ))}
        {notes.length === 0 && <li className="text-xs text-slate-400">No working notes yet.</li>}
      </ul>
    </section>
  );
}
```

```tsx
// web/client/components/memory/ActiveLessonsColumn.tsx
import { BookOpen } from "lucide-react";
import { useActiveLessons } from "@client/hooks/useMemoryQueries";

export default function ActiveLessonsColumn({ domain }: { domain?: string }) {
  const lessons = useActiveLessons(domain);
  return (
    <section className="flex-1 min-w-0 bg-white border border-slate-200 rounded-lg p-3 dark:bg-slate-900 dark:border-slate-700">
      <header className="flex items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-100 mb-2">
        <BookOpen size={16} /> Active lessons <span className="text-xs text-slate-400">({lessons.length})</span>
      </header>
      <ul className="grid grid-cols-1 gap-2 max-h-[70vh] overflow-y-auto">
        {lessons.map((l) => (
          <li key={l.id} className="text-xs p-2 rounded border border-slate-200 dark:border-slate-700">
            <div className="text-[10px] uppercase tracking-wide text-slate-400">{l.domain ?? "—"} · Δ {l.rubric_score_delta?.toFixed(2) ?? "—"} (n={l.experiment_n ?? "—"})</div>
            <div className="text-slate-700 dark:text-slate-200 leading-snug">{l.body}</div>
            <div className="text-[10px] text-slate-400 mt-1">promoted {l.promoted_at ?? "—"} · by {l.proposed_by ?? "—"}</div>
          </li>
        ))}
        {lessons.length === 0 && <li className="text-xs text-slate-400">No active lessons.</li>}
      </ul>
    </section>
  );
}
```

```tsx
// web/client/components/memory/DreamPassColumn.tsx
import { Sparkles } from "lucide-react";
import { useDreamPassesRecent } from "@client/hooks/useMemoryQueries";

export default function DreamPassColumn() {
  const passes = useDreamPassesRecent(30);
  return (
    <section className="flex-1 min-w-0 bg-white border border-slate-200 rounded-lg p-3 dark:bg-slate-900 dark:border-slate-700">
      <header className="flex items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-100 mb-2">
        <Sparkles size={16} /> Dream passes <span className="text-xs text-slate-400">({passes.length})</span>
      </header>
      <ol className="space-y-2 max-h-[70vh] overflow-y-auto">
        {passes.map((p) => (
          <li key={p.id} className="text-xs p-2 rounded border-l-2 border-purple-400 bg-slate-50 dark:bg-slate-800/40">
            <div className="text-[10px] uppercase tracking-wide text-slate-400">{p.id}</div>
            <div className="text-slate-700 dark:text-slate-200">
              <strong>{p.domain}</strong> · {p.status ?? "?"} ·
              proposed {p.candidates_proposed ?? 0}, promoted {p.candidates_promoted ?? 0}
            </div>
            <div className="text-[10px] text-slate-400 mt-0.5">{p.started_at ?? "—"} → {p.completed_at ?? "—"}</div>
          </li>
        ))}
        {passes.length === 0 && <li className="text-xs text-slate-400">No dream passes yet — try the Trigger button.</li>}
      </ol>
    </section>
  );
}
```

```tsx
// web/client/routes/Memory.tsx
import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Sparkles } from "lucide-react";

import WorkingMemoryColumn from "@client/components/memory/WorkingMemoryColumn";
import ActiveLessonsColumn from "@client/components/memory/ActiveLessonsColumn";
import DreamPassColumn from "@client/components/memory/DreamPassColumn";

const DOMAINS = ["hiring", "vendor_kyc", "expense_claim"];

export default function Memory() {
  const [domain, setDomain] = useState<string>("hiring");
  const [busy, setBusy] = useState(false);

  async function triggerPass() {
    setBusy(true);
    try {
      await fetch(
        `/api/dream-pass/run?domain=${encodeURIComponent(domain)}&sample=10`,
        { method: "POST" },
      );
    } finally {
      setBusy(false);
    }
  }

  async function dreamStorm() {
    setBusy(true);
    try {
      await fetch(
        `/api/simulator/dream-storm?domains=${DOMAINS.join(",")}&runs=3`,
        { method: "POST" },
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex-1 min-w-0 overflow-y-auto bg-slate-50 dark:bg-slate-950 p-6">
      <div className="max-w-7xl mx-auto space-y-4">
        <div className="flex items-center gap-3">
          <Link
            to="/"
            className="text-xs text-slate-500 hover:text-slate-800 flex items-center gap-1 dark:text-slate-400 dark:hover:text-slate-100"
          ><ArrowLeft size={14} /> Back to feed</Link>
        </div>
        <header className="flex items-center justify-between">
          <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Memory</h1>
          <div className="flex items-center gap-2">
            <select
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              className="text-xs border border-slate-300 dark:border-slate-700 dark:bg-slate-800 rounded px-2 py-1"
            >
              {DOMAINS.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
            <button
              type="button"
              disabled={busy}
              onClick={triggerPass}
              className="text-xs px-3 py-1.5 rounded font-medium bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-60 flex items-center gap-1"
            ><Sparkles size={14} /> Trigger dream pass</button>
            <button
              type="button"
              disabled={busy}
              onClick={dreamStorm}
              className="text-xs px-3 py-1.5 rounded font-medium bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-60"
            >Dream storm</button>
          </div>
        </header>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <WorkingMemoryColumn domain={domain} />
          <ActiveLessonsColumn domain={domain} />
          <DreamPassColumn />
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```
npx vitest run web/client/routes/__tests__/Memory.test.tsx web/client/hooks/__tests__/useMemoryQueries.test.tsx
```
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add web/client/routes/Memory.tsx web/client/components/memory/ web/client/routes/__tests__/Memory.test.tsx
git commit -m "feat(memory): Fleet UI Memory page (3 columns)"
```

---

## Task 11: Sidebar link + route registration

**Files:**
- Modify: `web/client/components/feed/LeftRail.tsx` (add `Memory` link between `Dashboard` and `Constellation`)
- Modify: `web/client/App.tsx` (register `/memory` → `Memory`)
- Test: `web/client/components/feed/__tests__/LeftRail.test.tsx` (extend if exists)

- [ ] **Step 1: Write the failing test**

```tsx
// web/client/components/feed/__tests__/LeftRail.memory-link.test.tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import LeftRail from "../LeftRail";


describe("LeftRail Memory link", () => {
  it("renders a Memory link pointing to /memory", () => {
    render(
      <MemoryRouter><LeftRail savedViews={[]} onApplyView={() => {}} /></MemoryRouter>,
    );
    const link = screen.getByRole("link", { name: /Memory/ });
    expect(link.getAttribute("href")).toBe("/memory");
  });
});
```

> If `LeftRail` requires more props than `savedViews` / `onApplyView`, copy the exact prop shape from `web/client/components/feed/LeftRail.tsx` and supply minimal stubs.

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/client/components/feed/__tests__/LeftRail.memory-link.test.tsx`
Expected: no Memory link rendered.

- [ ] **Step 3: Add the link in `LeftRail.tsx`**

Locate the existing block that renders the Dashboard link (search for `to="/dashboard"`). Immediately after it, insert:

```tsx
<Link
  to="/memory"
  className="flex items-center gap-2 px-3 py-2 rounded text-xs text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
>
  <Brain size={14} /> Memory
</Link>
```

Make sure `Link` is already imported from `react-router-dom` (it is — Dashboard uses it). Add `Brain` to the existing `lucide-react` import.

In `web/client/App.tsx`, register the route. Find the existing `<Route path="/dashboard" element={<Dashboard />} />` (or equivalent) and add immediately after:

```tsx
<Route path="/memory" element={<Memory />} />
```

…and add the import at the top:

```tsx
import Memory from "@client/routes/Memory";
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```
npx vitest run web/client/components/feed/__tests__/LeftRail.memory-link.test.tsx
```
Expected: 1 passed.

Rebuild + visual smoke:
```bash
npx vite build
# restart demo:ui (existing pattern) then visit http://localhost:5273/memory
```

- [ ] **Step 5: Commit**

```bash
git add web/client/components/feed/LeftRail.tsx web/client/App.tsx web/client/components/feed/__tests__/LeftRail.memory-link.test.tsx
git commit -m "feat(memory): sidebar link + /memory route"
```

---

## Task 12: Self-review and acceptance walk-through

- [ ] **Step 1: Full test sweep**

Run: `uv run pytest -q tests/api/server/services/dream_pass/ tests/api/server/routes/test_memory.py tests/api/server/routes/test_dream_pass_run.py tests/api/server/routes/test_simulator_dream_storm.py tests/api/server/test_state_dream_orchestrator.py tests/api/server/test_dream_cadence_loop.py`
Expected: all green.

Run: `npx vitest run web/client/hooks/__tests__/useMemoryQueries.test.tsx web/client/routes/__tests__/Memory.test.tsx web/client/components/feed/__tests__/LeftRail.memory-link.test.tsx`
Expected: all green.

- [ ] **Step 2: End-to-end demo dry-run**

```bash
make down && make up
# Wait until /api/healthz returns 200
sleep 30

# Trigger one pass
curl -s -X POST 'http://localhost:3101/api/dream-pass/run?domain=hiring&sample=10' | python3 -m json.tool
# Expect: dream_pass_id, candidates_proposed >= 1

# Inspect memory endpoints
curl -s 'http://localhost:3101/api/memory/lessons/active' | python3 -m json.tool
curl -s 'http://localhost:3101/api/memory/dream-passes/recent?limit=5' | python3 -m json.tool
curl -s 'http://localhost:3101/api/memory/working-notes?limit=10' | python3 -m json.tool
curl -s 'http://localhost:3101/api/memory/experiments/recent?limit=10' | python3 -m json.tool

# Dream storm
curl -s -X POST 'http://localhost:3101/api/simulator/dream-storm?domains=hiring&runs=3' | python3 -m json.tool
# Expect: 3 passes, each with promoted/rejected counts

# Verify SSE forwards dream.* events
timeout 5 curl -s -N -H 'Accept: text/event-stream' 'http://localhost:3101/api/stream/fleet' | grep -E '"dream\\.' | head
# Expect: at least one dream.* line during the next storm

# Fleet UI smoke
open http://localhost:5273/memory
# Click "Trigger dream pass" — expect right-column timeline to gain a new row within ~5s
# Click "Dream storm" — expect 3 new rows
```

- [ ] **Step 3: Final cleanup commit (only if anything was tweaked above)**

```bash
git add -A
git diff --cached --stat
git commit -m "chore(memory): polish from end-to-end dry-run"
```

---

## Self-review checklist

- [ ] Every route mentioned in the spec has a task: working-notes ✅, lessons/active ✅, dream-passes/recent ✅, experiments/recent ✅, dream-pass/run ✅, dream-storm ✅
- [ ] No placeholders: search the plan for "TBD", "TODO", "fill in", "similar to" — none should match
- [ ] Type consistency: `DreamPassRow`, `ActiveLesson`, `WorkingNote` field names match the route payload shapes in Task 6 — verify
- [ ] Bus event names: `DREAM_PASS_STARTED` etc. from Task 1 are the same strings used in Task 2 emits and Task 9 hook subscriptions — verify
- [ ] Frontend: imports use `@client/...` and `@shared/...` aliases consistent with the existing `vite.config.ts`
- [ ] Backend: every new route is added to `api/server/main.py`'s `for r in (...)` tuple

## Out of scope (follow-on plan)

- Constellation HUD `DreamPulse` widget (3D scene integration)
- Speed knob coupling `SIMULATOR_TIME_COMPRESSION` with dream cadence
- Persisting `InMemoryLessonStore` to disk (lost on restart)
- Replacing `StubProposer` with `GHCPProposer` (requires API key plumbing)
- Lesson rollback / diff UI (governor supports prune; no frontend yet)
- Merging this work with `2026-05-19-dreaming-sessions.md` (autonomous cadence + read-only lessons panel) — both can coexist; the existing `DreamingScheduler` plan complements but does not block this one
