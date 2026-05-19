# Dream-Pass Exception Portal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the minimal portal surface for the *exception* path only — flagged candidate lessons that the dream-pass policy refused to auto-promote. The default path stays headless. This is governance theatre done honestly: humans only see the things AGT explicitly routed to them.

**Architecture:** A new backend route `/api/dream-pass/flagged` that reads `Lesson` candidate nodes from Kuzu where `status='candidate'` AND `flag_reason` is non-empty, plus their corresponding `Experiment` evidence. A new React page `web/portal/src/pages/DreamPassExceptions.tsx` lists them, lets an operator approve or reject with a reason. Approve/reject are themselves AGT-gated tool calls (`lesson.approve_flagged`, `lesson.reject_flagged`) — every action signed and ledger'd, just like the autonomous path.

**Tech Stack:** FastAPI route handler, React + Vite + TypeScript (existing portal stack), reuses Plan 1's `LessonGovernor` for the write side, reuses Plan 3's Kuzu `Lesson`/`Experiment` tables. No new dependencies.

---

## Prerequisites

This plan depends on:
- Plan 1 landed (`LessonGovernor`, Kuzu `Lesson` schema, `data/policies/tools.yaml`).
- Plan 3 landed (`Experiment` Kuzu schema, dream-pass orchestrator writes flagged candidates into `Lesson` table with `status='candidate'`).

A small **upstream change** in Plan 3 is required to make flagged candidates persist as `Lesson` rows with `status='candidate'`. Plan 3's orchestrator currently returns flagged IDs in memory but does not persist the candidate body. This plan does the persistence work as Task 1.

---

## File Structure

**New files:**
- `api/server/services/lessons/flagged_repo.py` — read flagged candidates + their experiments from Kuzu
- `api/server/routes/dream_pass_exceptions.py` — FastAPI route handlers
- `web/portal/src/pages/DreamPassExceptions.tsx` — React page
- `web/portal/src/api/dreamPassExceptions.ts` — typed client
- `tests/api/services/lessons/test_flagged_repo.py`
- `tests/api/routes/test_dream_pass_exceptions.py`
- `tests/api/services/lessons/test_governor_flagged.py`

**Modified files:**
- `api/server/services/dream_pass/orchestrator.py` — when verdict is `flagged`, persist a `Lesson` row with `status='candidate'` + `flag_reason` via the governor (new method)
- `api/server/services/lessons/governor.py` — add `write_flagged_candidate(candidate, experiment, flag_reason)` and `approve_flagged(lesson_id)` / `reject_flagged(lesson_id, reason)` methods
- `api/server/services/lessons/kuzu_provenance.py` — add `record_candidate(...)` that writes the Kuzu node with `status='candidate'`
- `data/policies/tools.yaml` — add `lesson.approve_flagged` and `lesson.reject_flagged` in `enforce` mode
- `web/portal/src/App.tsx` (or equivalent router) — add the `/dream-pass-exceptions` route
- `api/server/main.py` (or wherever routes are registered) — mount the new route

---

## Task 1: Persist flagged candidates as Lesson rows (governor + provenance + orchestrator)

**Files:**
- Modify: `api/server/services/lessons/governor.py`
- Modify: `api/server/services/lessons/kuzu_provenance.py`
- Modify: `api/server/services/dream_pass/orchestrator.py`
- Test: `tests/api/services/lessons/test_governor_flagged.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/services/lessons/test_governor_flagged.py`:

```python
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from api.server.services.governance.kernel import Decision
from api.server.services.lessons.governor import LessonGovernor
from api.server.services.lessons.store import InMemoryLessonStore
from api.server.services.lessons.types import LessonCandidate, LessonScope


def _candidate() -> LessonCandidate:
    return LessonCandidate(
        id="L-FLAGGED-1",
        body="lessons in this domain should escalate to vendor review",
        scope=LessonScope(domain="hiring"),
        proposed_by="dream-pass:hiring",
        rationale="observed pattern",
    )


def test_write_flagged_candidate_records_status_candidate(make_lesson) -> None:
    kernel_factory = lambda: MagicMock(evaluate_tool_call=MagicMock(return_value=Decision(allowed=True, action="allow", reason="ok")))
    audit = MagicMock()
    provenance = MagicMock()
    store = InMemoryLessonStore()

    governor = LessonGovernor(
        store=store,
        kernel=kernel_factory,
        audit=audit,
        provenance=provenance,
        actor="dream-pass:hiring",
    )

    governor.write_flagged_candidate(
        candidate=_candidate(),
        experiment_id="EXP-1",
        delta=0.07,
        n=40,
        flag_reason="implausible_delta",
    )

    provenance.record_candidate.assert_called_once()
    _, kwargs = provenance.record_candidate.call_args
    assert kwargs["flag_reason"] == "implausible_delta"
    assert kwargs["experiment_id"] == "EXP-1"
    # Body must also be in Kuzu via record_candidate
    assert kwargs["body"] == "lessons in this domain should escalate to vendor review"

    # Audit ledger entry recorded
    audit.log.assert_called_once()
    _, log_kwargs = audit.log.call_args
    assert log_kwargs["action"] == "lesson.flag_candidate"
    assert log_kwargs["details"]["flag_reason"] == "implausible_delta"


def test_approve_flagged_promotes_via_existing_write(make_lesson) -> None:
    kernel_factory = lambda: MagicMock(evaluate_tool_call=MagicMock(return_value=Decision(allowed=True, action="allow", reason="ok")))
    audit = MagicMock()
    provenance = MagicMock()
    provenance.fetch_candidate.return_value = make_lesson(domain="hiring")
    store = InMemoryLessonStore()

    governor = LessonGovernor(
        store=store,
        kernel=kernel_factory,
        audit=audit,
        provenance=provenance,
        actor="operator:human",
    )

    governor.approve_flagged(lesson_id="some-id", approver="alice@example.com")

    # The approve flow re-uses provenance.record (status=active) + store.add + ledger
    provenance.record.assert_called_once()
    audit.log.assert_called_once()
    _, log_kwargs = audit.log.call_args
    assert log_kwargs["action"] == "lesson.approve_flagged"
    assert log_kwargs["details"]["approver"] == "alice@example.com"


def test_reject_flagged_marks_pruned_with_reason() -> None:
    kernel_factory = lambda: MagicMock(evaluate_tool_call=MagicMock(return_value=Decision(allowed=True, action="allow", reason="ok")))
    audit = MagicMock()
    provenance = MagicMock()
    store = InMemoryLessonStore()

    governor = LessonGovernor(
        store=store,
        kernel=kernel_factory,
        audit=audit,
        provenance=provenance,
        actor="operator:human",
    )

    governor.reject_flagged(lesson_id="some-id", reviewer="alice@example.com", reason="contradicts policy")

    provenance.mark_pruned.assert_called_once_with("some-id", reason="rejected_by_review: contradicts policy")
    audit.log.assert_called_once()
    _, log_kwargs = audit.log.call_args
    assert log_kwargs["action"] == "lesson.reject_flagged"
    assert log_kwargs["details"]["reviewer"] == "alice@example.com"
    assert log_kwargs["details"]["reason"] == "contradicts policy"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/api/services/lessons/test_governor_flagged.py -v`
Expected: FAIL on missing methods on `LessonGovernor`.

- [ ] **Step 3: Add `record_candidate` and `fetch_candidate` to `KuzuLessonProvenance`**

In `api/server/services/lessons/kuzu_provenance.py`, add two methods to the `KuzuLessonProvenance` class:

```python
    def record_candidate(
        self,
        *,
        candidate_id: str,
        body: str,
        domain: str,
        persona_role: str,
        market: str,
        proposed_by: str,
        experiment_id: str,
        delta: float,
        n: int,
        flag_reason: str,
    ) -> None:
        self._graph.execute_cypher(
            """
            MERGE (l:Lesson {id: $id})
            SET l.body = $body,
                l.domain = $domain,
                l.persona_role = $persona_role,
                l.market = $market,
                l.status = 'candidate',
                l.proposed_by = $proposed_by,
                l.rubric_score_delta = $delta,
                l.experiment_n = $n,
                l.promoted_at = $now,
                l.supersedes = '',
                l.prune_reason = $flag_reason
            """,
            {
                "id": candidate_id,
                "body": body,
                "domain": domain,
                "persona_role": persona_role,
                "market": market,
                "proposed_by": proposed_by,
                "delta": delta,
                "n": n,
                "flag_reason": flag_reason,
                "now": datetime.now(timezone.utc),
            },
        )
        self._graph.execute_cypher(
            """
            MERGE (e:Experiment {id: $eid})
            MERGE (l:Lesson {id: $lid})
            CREATE (e)-[:EXPERIMENT_FOR_LESSON {recorded_at: $now}]->(l)
            """,
            {"eid": experiment_id, "lid": candidate_id, "now": datetime.now(timezone.utc)},
        )

    def fetch_candidate(self, lesson_id: str):
        """Return a Lesson (status='candidate') hydrated from Kuzu, or None."""
        from api.server.services.lessons.types import (
            Lesson,
            LessonProvenance,
            LessonScope,
        )
        rows = self._graph.execute_cypher(
            """
            MATCH (l:Lesson {id: $id, status: 'candidate'})
            RETURN l.body AS body, l.domain AS domain,
                   l.persona_role AS persona_role, l.market AS market,
                   l.proposed_by AS proposed_by,
                   l.rubric_score_delta AS delta, l.experiment_n AS n,
                   l.promoted_at AS promoted_at, l.prune_reason AS flag_reason
            """,
            {"id": lesson_id},
        )
        if not rows:
            return None
        r = rows[0]
        return Lesson(
            id=lesson_id,
            body=r["body"],
            scope=LessonScope(
                domain=r["domain"],
                persona_role=r["persona_role"] or None,
                market=r["market"] or None,
            ),
            provenance=LessonProvenance(
                proposed_by=r["proposed_by"],
                run_ids=(),
                rubric_score_delta=r["delta"],
                experiment_n=r["n"],
                promoted_at=r["promoted_at"],
            ),
            status="candidate",
        )
```

- [ ] **Step 4: Add `write_flagged_candidate`, `approve_flagged`, `reject_flagged` to `LessonGovernor`**

In `api/server/services/lessons/governor.py`, add these methods to the `LessonGovernor` class:

```python
    def write_flagged_candidate(
        self,
        *,
        candidate,  # LessonCandidate
        experiment_id: str,
        delta: float,
        n: int,
        flag_reason: str,
    ) -> None:
        decision = self._kernel_factory().evaluate_tool_call(
            actor=self._actor,
            tool="lesson.write",  # same tool — candidates are still lesson writes, just status=candidate
            args={"lesson_id": candidate.id, "domain": candidate.scope.domain, "flag_reason": flag_reason},
            workflow_id=self._workflow_id,
        )
        self._enforce(decision, lesson_id=candidate.id, action="lesson.flag_candidate")
        self._provenance.record_candidate(
            candidate_id=candidate.id,
            body=candidate.body,
            domain=candidate.scope.domain,
            persona_role=candidate.scope.persona_role or "",
            market=candidate.scope.market or "",
            proposed_by=candidate.proposed_by,
            experiment_id=experiment_id,
            delta=delta,
            n=n,
            flag_reason=flag_reason,
        )
        self._record_ledger(decision, action="lesson.flag_candidate", details={
            "lesson_id": candidate.id,
            "domain": candidate.scope.domain,
            "flag_reason": flag_reason,
            "delta": delta,
            "n": n,
            "experiment_id": experiment_id,
            "governance_action": decision.action,
        })

    def approve_flagged(self, *, lesson_id: str, approver: str) -> None:
        decision = self._kernel_factory().evaluate_tool_call(
            actor=self._actor,
            tool="lesson.approve_flagged",
            args={"lesson_id": lesson_id, "approver": approver},
            workflow_id=self._workflow_id,
        )
        self._enforce(decision, lesson_id=lesson_id, action="lesson.approve_flagged")
        candidate = self._provenance.fetch_candidate(lesson_id)
        if candidate is None:
            raise LookupError(f"no candidate lesson found with id {lesson_id}")
        # Re-record as active (overwrites status field in Kuzu) and add to store.
        active = type(candidate)(
            id=candidate.id,
            body=candidate.body,
            scope=candidate.scope,
            provenance=candidate.provenance,
            status="active",
            supersedes=candidate.supersedes,
        )
        self._store.add(active)
        self._provenance.record(active)
        self._record_ledger(decision, action="lesson.approve_flagged", details={
            "lesson_id": lesson_id,
            "approver": approver,
            "governance_action": decision.action,
        })

    def reject_flagged(self, *, lesson_id: str, reviewer: str, reason: str) -> None:
        decision = self._kernel_factory().evaluate_tool_call(
            actor=self._actor,
            tool="lesson.reject_flagged",
            args={"lesson_id": lesson_id, "reviewer": reviewer, "reason": reason},
            workflow_id=self._workflow_id,
        )
        self._enforce(decision, lesson_id=lesson_id, action="lesson.reject_flagged")
        self._provenance.mark_pruned(lesson_id, reason=f"rejected_by_review: {reason}")
        self._record_ledger(decision, action="lesson.reject_flagged", details={
            "lesson_id": lesson_id,
            "reviewer": reviewer,
            "reason": reason,
            "governance_action": decision.action,
        })
```

- [ ] **Step 5: Wire the orchestrator to persist flagged candidates**

In `api/server/services/dream_pass/orchestrator.py`, find the branch handling `decision.verdict == "flagged"` (currently just appending to the in-memory `flagged` list) and prepend a governor call:

Replace:

```python
            elif decision.verdict == "flagged":
                flagged.append(candidate.id)
```

With:

```python
            elif decision.verdict == "flagged":
                self._governor.write_flagged_candidate(
                    candidate=candidate,
                    experiment_id=experiment.id,
                    delta=experiment.delta,
                    n=experiment.n_samples,
                    flag_reason=decision.reason,
                )
                flagged.append(candidate.id)
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `uv run pytest tests/api/services/lessons/test_governor_flagged.py -v`
Expected: 3 passed.

Then run Plan 3's orchestrator test to confirm no regression:

Run: `uv run pytest tests/api/services/dream_pass/test_orchestrator.py -v`
Expected: pass (test mocks the governor so the new call is captured as `governor.write_flagged_candidate.assert_called` if the test needs updating — if it fails because flagged branch was previously a no-op-only path, update the test to include a `write_flagged_candidate` assertion).

- [ ] **Step 7: Commit**

```bash
git add api/server/services/lessons/governor.py api/server/services/lessons/kuzu_provenance.py api/server/services/dream_pass/orchestrator.py tests/api/services/lessons/test_governor_flagged.py
git commit -m "feat(dream-pass): persist flagged candidates + approve/reject governor methods"
```

---

## Task 2: Register new tools in AGT policy

**Files:**
- Modify: `data/policies/tools.yaml`

- [ ] **Step 1: Append the two new tools**

Append to `data/policies/tools.yaml`:

```yaml
  - id: lesson.approve_flagged
    description: |
      Human-driven promotion of a previously-flagged candidate lesson.
      Required arguments: lesson_id, approver (operator email). Capability
      gate ensures only operators (not agents) can call this tool.
    reversibility: reversible
    enforcement: enforce
    capabilities_required: [lessons.write, operator]

  - id: lesson.reject_flagged
    description: |
      Human-driven rejection of a flagged candidate. Marks the Lesson
      node as pruned with reason prefix 'rejected_by_review:'.
    reversibility: reversible
    enforcement: enforce
    capabilities_required: [lessons.write, operator]
```

- [ ] **Step 2: Verify the bundle compiles**

Run: `uv run python -c "from api.server.services.governance.policy_compiler import compile_bundle; compile_bundle()"`
Expected: no exception.

- [ ] **Step 3: Commit**

```bash
git add data/policies/tools.yaml
git commit -m "feat(dream-pass): register approve_flagged/reject_flagged in AGT"
```

---

## Task 3: Flagged-candidate repo

**Files:**
- Create: `api/server/services/lessons/flagged_repo.py`
- Test: `tests/api/services/lessons/test_flagged_repo.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/services/lessons/test_flagged_repo.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from api.server.services.entity_graph import EntityGraph
from api.server.services.lessons.flagged_repo import FlaggedLessonRepo


@pytest.fixture
def graph(tmp_path: Path) -> EntityGraph:
    g = EntityGraph(str(tmp_path / "flagged.kuzu"))
    # Seed: 2 candidates (1 flagged hiring, 1 flagged vendor_kyc), 1 active.
    g.execute_cypher("""
        CREATE (:Lesson {id: 'L-FLAG-1', body: 'flagged hiring', domain: 'hiring',
                         persona_role: '', market: '', status: 'candidate',
                         proposed_by: 'dp:hiring', rubric_score_delta: 0.25,
                         experiment_n: 40, promoted_at: timestamp(),
                         supersedes: '', prune_reason: 'implausible_delta'})
    """)
    g.execute_cypher("""
        CREATE (:Lesson {id: 'L-FLAG-2', body: 'flagged kyc', domain: 'vendor_kyc',
                         persona_role: '', market: '', status: 'candidate',
                         proposed_by: 'dp:kyc', rubric_score_delta: 0.06,
                         experiment_n: 40, promoted_at: timestamp(),
                         supersedes: '', prune_reason: 'scope_expansion'})
    """)
    g.execute_cypher("""
        CREATE (:Lesson {id: 'L-ACTIVE', body: 'active', domain: 'hiring',
                         persona_role: '', market: '', status: 'active',
                         proposed_by: 'dp:hiring', rubric_score_delta: 0.08,
                         experiment_n: 40, promoted_at: timestamp(),
                         supersedes: '', prune_reason: ''})
    """)
    g.execute_cypher("""
        CREATE (:Experiment {id: 'EXP-1', dream_pass_id: 'DP-1', candidate_lesson_id: 'L-FLAG-1',
                             control_score: 0.70, treatment_score: 0.95, delta: 0.25,
                             n_samples: 40, verdict: 'flagged', run_at: timestamp()})
    """)
    g.execute_cypher("""
        MATCH (e:Experiment {id: 'EXP-1'}), (l:Lesson {id: 'L-FLAG-1'})
        CREATE (e)-[:EXPERIMENT_FOR_LESSON {recorded_at: timestamp()}]->(l)
    """)
    return g


def test_list_flagged_for_domain(graph: EntityGraph) -> None:
    repo = FlaggedLessonRepo(graph=graph)
    items = repo.list_flagged(domain="hiring")
    assert len(items) == 1
    assert items[0]["lesson_id"] == "L-FLAG-1"
    assert items[0]["flag_reason"] == "implausible_delta"
    assert items[0]["body"] == "flagged hiring"


def test_list_flagged_includes_experiment_evidence(graph: EntityGraph) -> None:
    repo = FlaggedLessonRepo(graph=graph)
    items = repo.list_flagged(domain="hiring")
    assert items[0]["experiment"] == {
        "id": "EXP-1",
        "control_score": 0.70,
        "treatment_score": 0.95,
        "delta": 0.25,
        "n_samples": 40,
    }


def test_list_flagged_returns_empty_for_unknown_domain(graph: EntityGraph) -> None:
    repo = FlaggedLessonRepo(graph=graph)
    assert repo.list_flagged(domain="nope") == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/api/services/lessons/test_flagged_repo.py -v`
Expected: FAIL on missing module.

- [ ] **Step 3: Implement the repo**

Create `api/server/services/lessons/flagged_repo.py`:

```python
"""Read-only repo for flagged-candidate listings."""
from __future__ import annotations

from typing import Any

from api.server.services.entity_graph import EntityGraph


class FlaggedLessonRepo:
    def __init__(self, *, graph: EntityGraph) -> None:
        self._graph = graph

    def list_flagged(self, *, domain: str) -> list[dict[str, Any]]:
        rows = self._graph.execute_cypher(
            """
            MATCH (l:Lesson {status: 'candidate', domain: $domain})
            OPTIONAL MATCH (e:Experiment)-[:EXPERIMENT_FOR_LESSON]->(l)
            RETURN l.id AS lesson_id,
                   l.body AS body,
                   l.proposed_by AS proposed_by,
                   l.prune_reason AS flag_reason,
                   l.rubric_score_delta AS delta,
                   l.experiment_n AS n,
                   l.promoted_at AS proposed_at,
                   e.id AS experiment_id,
                   e.control_score AS control_score,
                   e.treatment_score AS treatment_score,
                   e.delta AS exp_delta,
                   e.n_samples AS exp_n
            """,
            {"domain": domain},
        )
        out: list[dict[str, Any]] = []
        for r in rows:
            item = {
                "lesson_id": r["lesson_id"],
                "body": r["body"],
                "proposed_by": r["proposed_by"],
                "flag_reason": r["flag_reason"],
                "delta": r["delta"],
                "n_samples": r["n"],
                "proposed_at": r["proposed_at"].isoformat() if r["proposed_at"] else None,
                "experiment": (
                    {
                        "id": r["experiment_id"],
                        "control_score": r["control_score"],
                        "treatment_score": r["treatment_score"],
                        "delta": r["exp_delta"],
                        "n_samples": r["exp_n"],
                    }
                    if r["experiment_id"]
                    else None
                ),
            }
            out.append(item)
        return out
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/api/services/lessons/test_flagged_repo.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add api/server/services/lessons/flagged_repo.py tests/api/services/lessons/test_flagged_repo.py
git commit -m "feat(dream-pass): add FlaggedLessonRepo for portal reads"
```

---

## Task 4: FastAPI route

**Files:**
- Create: `api/server/routes/dream_pass_exceptions.py`
- Test: `tests/api/routes/test_dream_pass_exceptions.py`
- Modify: wherever `app = FastAPI(...)` mounts routers (likely `api/server/main.py`)

- [ ] **Step 0: Locate the route registration site**

Run: `grep -n "include_router" api/server/main.py`
Expected: see existing `app.include_router(...)` lines, and a `prefix=` convention. Mirror them.

- [ ] **Step 1: Write the failing test**

Create `tests/api/routes/test_dream_pass_exceptions.py`:

```python
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.server.routes.dream_pass_exceptions import router


@pytest.fixture
def app():
    from fastapi import FastAPI
    application = FastAPI()
    application.include_router(router)
    return application


@pytest.fixture
def client(app):
    return TestClient(app)


def test_list_flagged_returns_repo_items(client) -> None:
    with patch("api.server.routes.dream_pass_exceptions._repo") as repo_factory:
        repo = MagicMock()
        repo.list_flagged.return_value = [
            {"lesson_id": "L-1", "body": "x", "flag_reason": "implausible_delta",
             "delta": 0.25, "n_samples": 40, "experiment": None,
             "proposed_by": "dp", "proposed_at": "2026-05-19T10:00:00+00:00"},
        ]
        repo_factory.return_value = repo

        resp = client.get("/api/dream-pass/flagged?domain=hiring")

    assert resp.status_code == 200
    body = resp.json()
    assert body["items"][0]["lesson_id"] == "L-1"


def test_approve_calls_governor(client) -> None:
    with patch("api.server.routes.dream_pass_exceptions._governor") as gov_factory:
        gov = MagicMock()
        gov_factory.return_value = gov

        resp = client.post(
            "/api/dream-pass/flagged/L-1/approve",
            json={"approver": "alice@example.com"},
        )

    assert resp.status_code == 200
    gov.approve_flagged.assert_called_once_with(
        lesson_id="L-1", approver="alice@example.com"
    )


def test_reject_calls_governor(client) -> None:
    with patch("api.server.routes.dream_pass_exceptions._governor") as gov_factory:
        gov = MagicMock()
        gov_factory.return_value = gov

        resp = client.post(
            "/api/dream-pass/flagged/L-1/reject",
            json={"reviewer": "alice@example.com", "reason": "contradicts policy"},
        )

    assert resp.status_code == 200
    gov.reject_flagged.assert_called_once_with(
        lesson_id="L-1", reviewer="alice@example.com", reason="contradicts policy"
    )
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/api/routes/test_dream_pass_exceptions.py -v`
Expected: FAIL on missing module.

- [ ] **Step 3: Implement the route**

Create `api/server/routes/dream_pass_exceptions.py`:

```python
"""Dream-pass exception portal API.

These routes are the *only* surface where humans intervene in the
lesson lifecycle. All other paths (write, prune) are autonomous and
AGT-gated.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.server.services.audit_logger import AuditLogger
from api.server.services.entity_graph import EntityGraph
from api.server.services.governance import kernel
from api.server.services.lessons.flagged_repo import FlaggedLessonRepo
from api.server.services.lessons.governor import LessonGovernor
from api.server.services.lessons.kuzu_provenance import KuzuLessonProvenance
from api.server.services.lessons.mem0_store import Mem0LessonStore


router = APIRouter(prefix="/api/dream-pass", tags=["dream-pass"])


def _graph() -> EntityGraph:
    return EntityGraph("data/portal/entity_graph.kuzu")


def _repo() -> FlaggedLessonRepo:
    return FlaggedLessonRepo(graph=_graph())


def _governor() -> LessonGovernor:
    graph = _graph()
    return LessonGovernor(
        store=Mem0LessonStore(),
        kernel=kernel,
        audit=AuditLogger(),
        provenance=KuzuLessonProvenance(graph),
        actor="operator:portal",
    )


class FlaggedItem(BaseModel):
    lesson_id: str
    body: str
    proposed_by: str
    flag_reason: str
    delta: float
    n_samples: int
    proposed_at: str | None = None
    experiment: dict[str, Any] | None = None


class FlaggedList(BaseModel):
    items: list[FlaggedItem]


class ApproveBody(BaseModel):
    approver: str = Field(..., description="operator email")


class RejectBody(BaseModel):
    reviewer: str = Field(..., description="operator email")
    reason: str = Field(..., min_length=1)


@router.get("/flagged", response_model=FlaggedList)
def list_flagged(domain: str) -> FlaggedList:
    items = _repo().list_flagged(domain=domain)
    return FlaggedList(items=[FlaggedItem(**i) for i in items])


@router.post("/flagged/{lesson_id}/approve")
def approve(lesson_id: str, body: ApproveBody) -> dict[str, str]:
    try:
        _governor().approve_flagged(lesson_id=lesson_id, approver=body.approver)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"status": "approved", "lesson_id": lesson_id}


@router.post("/flagged/{lesson_id}/reject")
def reject(lesson_id: str, body: RejectBody) -> dict[str, str]:
    _governor().reject_flagged(
        lesson_id=lesson_id, reviewer=body.reviewer, reason=body.reason
    )
    return {"status": "rejected", "lesson_id": lesson_id}
```

- [ ] **Step 4: Mount the router**

In `api/server/main.py` (or the equivalent app composition module), find the existing `app.include_router(...)` block and add:

```python
from api.server.routes.dream_pass_exceptions import router as dream_pass_exceptions_router

app.include_router(dream_pass_exceptions_router)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/api/routes/test_dream_pass_exceptions.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add api/server/routes/dream_pass_exceptions.py tests/api/routes/test_dream_pass_exceptions.py api/server/main.py
git commit -m "feat(dream-pass): add /api/dream-pass/flagged route + approve/reject"
```

---

## Task 5: Typed React client

**Files:**
- Create: `web/portal/src/api/dreamPassExceptions.ts`

- [ ] **Step 1: Implement the client**

Create `web/portal/src/api/dreamPassExceptions.ts`:

```ts
export interface FlaggedExperiment {
  id: string;
  control_score: number;
  treatment_score: number;
  delta: number;
  n_samples: number;
}

export interface FlaggedItem {
  lesson_id: string;
  body: string;
  proposed_by: string;
  flag_reason: string;
  delta: number;
  n_samples: number;
  proposed_at: string | null;
  experiment: FlaggedExperiment | null;
}

export async function listFlagged(domain: string): Promise<FlaggedItem[]> {
  const resp = await fetch(`/api/dream-pass/flagged?domain=${encodeURIComponent(domain)}`);
  if (!resp.ok) throw new Error(`list flagged failed: ${resp.status}`);
  const body = await resp.json();
  return body.items as FlaggedItem[];
}

export async function approveFlagged(lessonId: string, approver: string): Promise<void> {
  const resp = await fetch(`/api/dream-pass/flagged/${encodeURIComponent(lessonId)}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approver }),
  });
  if (!resp.ok) throw new Error(`approve failed: ${resp.status}`);
}

export async function rejectFlagged(
  lessonId: string,
  reviewer: string,
  reason: string,
): Promise<void> {
  const resp = await fetch(`/api/dream-pass/flagged/${encodeURIComponent(lessonId)}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reviewer, reason }),
  });
  if (!resp.ok) throw new Error(`reject failed: ${resp.status}`);
}
```

- [ ] **Step 2: Commit**

```bash
git add web/portal/src/api/dreamPassExceptions.ts
git commit -m "feat(dream-pass): add typed React client for exceptions API"
```

---

## Task 6: React page + route

**Files:**
- Create: `web/portal/src/pages/DreamPassExceptions.tsx`
- Modify: `web/portal/src/App.tsx` (or whichever file owns the routing table)

- [ ] **Step 0: Locate the router**

Run: `grep -rn "createBrowserRouter\|<Routes>\|<Route" web/portal/src/ | head`
Expected: identify the central router file. Add one new route alongside existing ones. The path used below is `/dream-pass-exceptions`.

- [ ] **Step 1: Implement the page**

Create `web/portal/src/pages/DreamPassExceptions.tsx`:

```tsx
import { useEffect, useState } from "react";
import {
  FlaggedItem,
  approveFlagged,
  listFlagged,
  rejectFlagged,
} from "../api/dreamPassExceptions";

const DOMAINS = ["hiring", "vendor_kyc", "expense_claim"];

export default function DreamPassExceptions() {
  const [domain, setDomain] = useState("hiring");
  const [items, setItems] = useState<FlaggedItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    setError(null);
    try {
      setItems(await listFlagged(domain));
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [domain]);

  async function onApprove(item: FlaggedItem) {
    const approver = prompt("operator email")?.trim();
    if (!approver) return;
    setBusy(true);
    try {
      await approveFlagged(item.lesson_id, approver);
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onReject(item: FlaggedItem) {
    const reviewer = prompt("operator email")?.trim();
    if (!reviewer) return;
    const reason = prompt("reject reason")?.trim();
    if (!reason) return;
    setBusy(true);
    try {
      await rejectFlagged(item.lesson_id, reviewer, reason);
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ padding: 16, fontFamily: "system-ui, sans-serif" }}>
      <h1>Dream-pass exceptions</h1>
      <p>
        Candidate lessons the dream-pass policy refused to auto-promote.
        Approve to make active, reject to prune.
      </p>
      <label>
        Domain:&nbsp;
        <select value={domain} onChange={(e) => setDomain(e.target.value)} disabled={busy}>
          {DOMAINS.map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
      </label>

      {error && (
        <div style={{ color: "red", marginTop: 12 }}>{error}</div>
      )}

      <table style={{ width: "100%", marginTop: 16, borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th align="left">Lesson</th>
            <th align="left">Flag reason</th>
            <th align="right">Δ</th>
            <th align="right">n</th>
            <th align="left">Proposed by</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.lesson_id} style={{ borderTop: "1px solid #ddd" }}>
              <td style={{ padding: "8px 0" }}>{item.body}</td>
              <td>{item.flag_reason}</td>
              <td align="right">{item.delta.toFixed(3)}</td>
              <td align="right">{item.n_samples}</td>
              <td>{item.proposed_by}</td>
              <td>
                <button onClick={() => onApprove(item)} disabled={busy}>Approve</button>
                <button onClick={() => onReject(item)} disabled={busy} style={{ marginLeft: 4 }}>
                  Reject
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {items.length === 0 && !error && (
        <p style={{ marginTop: 16, color: "#666" }}>No flagged candidates for {domain}.</p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Add the route**

In the router file located in Step 0, add a route entry that maps `/dream-pass-exceptions` to the new `DreamPassExceptions` component, following the existing pattern.

If the router uses `createBrowserRouter`, add an entry like:

```ts
{ path: "/dream-pass-exceptions", element: <DreamPassExceptions /> },
```

If it uses `<Routes><Route>`, add:

```tsx
<Route path="/dream-pass-exceptions" element={<DreamPassExceptions />} />
```

Import the page at the top of the file:

```tsx
import DreamPassExceptions from "./pages/DreamPassExceptions";
```

- [ ] **Step 3: Build the portal to confirm no TypeScript errors**

Run: `npm --prefix web/portal run build`
Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add web/portal/src/pages/DreamPassExceptions.tsx web/portal/src/App.tsx
git commit -m "feat(dream-pass): add /dream-pass-exceptions portal page"
```

---

## Task 7: Final regression + Definition of Done

- [ ] **Step 1: Run the full Python test suite**

Run: `uv run pytest tests/api -x --tb=short`
Expected: all tests pass.

- [ ] **Step 2: Run mypy on all new packages**

Run: `uv run mypy api/server/services/lessons/ api/server/services/dream_pass/ api/server/routes/dream_pass_exceptions.py`
Expected: `Success`.

- [ ] **Step 3: End-to-end smoke**

In one terminal:
```bash
uv run uvicorn api.server.main:app --reload --port 8000
```

In another:
```bash
# Trigger a dream pass that produces a flagged candidate (use stub proposer with a body containing an implausible-delta trigger).
uv run python scripts/dream_pass.py --domain hiring --sample-size 4 --use-stub-proposer
# List flagged via the API:
curl -s "http://localhost:8000/api/dream-pass/flagged?domain=hiring" | python -m json.tool
```
Expected: at least one flagged item appears.

Open `http://localhost:8000/dream-pass-exceptions` (if the portal is served by the same app) or the portal dev server URL. Confirm the row renders, approve / reject buttons hit the API, and the row disappears on refresh.

---

## Definition of Done

- A dream pass that produces a `flagged` verdict persists a `Lesson` row with `status='candidate'` and an `EXPERIMENT_FOR_LESSON` edge to the originating experiment.
- `GET /api/dream-pass/flagged?domain=...` returns those candidates with their experiment evidence.
- `POST /api/dream-pass/flagged/{id}/approve` promotes the candidate via `LessonGovernor.approve_flagged`, going through AGT, leaving a signed ledger entry naming the approver.
- `POST /api/dream-pass/flagged/{id}/reject` prunes the candidate via `LessonGovernor.reject_flagged`, with the reason recorded in the ledger.
- The React page `/dream-pass-exceptions` renders the flagged list and exposes approve / reject.
- All existing tests still pass; new tests cover governor, repo, route, and persistence.
- The default dream-pass path remains headless; humans only interact when AGT explicitly routes a candidate to this surface.
