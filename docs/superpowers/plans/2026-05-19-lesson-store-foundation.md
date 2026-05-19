# Lesson Store Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land a pluggable, AGT-governed `LessonStore` *and* `WorkingMemoryStore` with a Mem0 reference implementation and Kuzu-backed provenance, so later plans can build the dream-pass loop on a stable, auditable substrate.

**Architecture:** Two memory tiers, both Mem0-backed (different `user_id` buckets), both gated by AGT:

1. **LessonStore** — promoted, cross-agent, scoped per-domain. Read by *agents* (the LLM executors under `api/functions/graphs/executors/agents/`) at prompt-build time. The injection point is the `_build_prompt(input)` function of each agent executor, which already constructs the prompt that goes to `run_agent_session`. Plan 3 extends `_build_prompt` for the demo agent (`agent_interview_recommender`) to accept and embed lessons + working notes.
2. **WorkingMemoryStore** — per-`workflow_id` scratchpad, written from the existing OTEL session events emitted by `api/functions/graphs/executors/agents/_wrapper.py`. Captures what each agent invocation said, decided, and which tools it called. The dream pass (Plan 3) reads working memory as its raw material — it is what agents *actually noticed during real runs*, not patterns invented from outcome data alone.

Both stores expose a `LessonGovernor` / `WorkingMemoryGovernor` thin wrapper that calls `kernel().evaluate_tool_call()` and `AuditLogger.log()` for an AGT-signed ledger entry. Lesson provenance + scope metadata also lands in Kuzu as `Lesson` nodes linked to the runs that birthed them; the lesson body lives in Mem0. Working memory does **not** mirror to Kuzu — it is ephemeral by design, GC'd after the dream pass consolidates it.

**Tech Stack:** Python 3.11, `mem0ai>=0.1.115` (+`[nlp]` extras), `kuzu>=0.6,<0.7`, existing AGT 3.4 governance kernel, existing GHCP runtime (`runtime_ghcp.py`) for the LLM, pytest 8.3.

---

## File Structure

**New files:**
- `api/server/services/lessons/__init__.py` — package marker, re-exports
- `api/server/services/lessons/types.py` — `Lesson`, `LessonScope`, `LessonProvenance`, `LessonCandidate` dataclasses
- `api/server/services/lessons/store.py` — `LessonStore` Protocol + `InMemoryLessonStore` test double
- `api/server/services/lessons/mem0_store.py` — `Mem0LessonStore` implementation
- `api/server/services/lessons/governor.py` — `LessonGovernor` (AGT + ledger wrapper)
- `api/server/services/lessons/kuzu_provenance.py` — Kuzu node/edge writes for `Lesson` provenance
- `scripts/lessons_smoke.py` — CLI smoke test (write → search → prune; print ledger entries)
- `tests/api/services/lessons/__init__.py`
- `tests/api/services/lessons/test_types.py`
- `tests/api/services/lessons/test_in_memory_store.py`
- `tests/api/services/lessons/test_mem0_store.py`
- `tests/api/services/lessons/test_governor.py`
- `tests/api/services/lessons/test_kuzu_provenance.py`
- `tests/api/services/lessons/conftest.py` — shared fixtures

**Modified files:**
- `pyproject.toml` — add `mem0ai[nlp]>=0.1.115,<0.2`
- `api/server/services/entity_graph.py` — extend `_NODE_TABLES` with `Lesson`, extend `_REL_TABLES` with `LESSON_FROM_RUN`, `LESSON_ABOUT_PERSONA`, `LESSON_SUPERSEDES`
- `data/policies/tools.yaml` — register `lesson.write` and `lesson.prune` tools (initially `audit`-only, no enforce)

---

## Conventions

- All new code is type-annotated and passes `mypy --strict` on the new package.
- Tests use pytest, no class-based test classes, function-style with `pytest.fixture`.
- One assertion per test where practical; multiple are fine when they verify a single behaviour.
- Commit messages: Conventional Commits (`feat:`, `test:`, `chore:`).
- LLM/embedding configuration for Mem0 is driven entirely by env vars; no hardcoded providers.

---

## Task 1: Add mem0ai dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Read the current `[project] dependencies` block to find the right insertion point**

Run: `grep -n "kuzu" pyproject.toml`
Expected: a line of the form `"kuzu>=0.6,<0.7",` showing the current dependency style.

- [ ] **Step 2: Add the mem0ai dependency below the `kuzu` line**

Add this line immediately after the `kuzu` line in the `[project] dependencies` array:

```toml
    "mem0ai[nlp]>=0.1.115,<0.2",
```

- [ ] **Step 3: Install the dependency**

Run: `uv sync`
Expected: `mem0ai` and its transitive deps (qdrant-client, spacy, etc.) install without error.

- [ ] **Step 4: Download the spaCy English model required by Mem0's NLP extras**

Run: `uv run python -m spacy download en_core_web_sm`
Expected: model downloads to the venv site-packages.

- [ ] **Step 5: Smoke-import to verify the package loads**

Run: `uv run python -c "from mem0 import Memory; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore(lessons): add mem0ai[nlp] dependency"
```

---

## Task 2: Define lesson value types

**Files:**
- Create: `api/server/services/lessons/__init__.py`
- Create: `api/server/services/lessons/types.py`
- Test: `tests/api/services/lessons/__init__.py`, `tests/api/services/lessons/test_types.py`

- [ ] **Step 1: Create empty package markers**

Create `api/server/services/lessons/__init__.py` with content:

```python
"""Lesson store: shared, governed, cross-agent memory tier."""
```

Create `tests/api/services/lessons/__init__.py` with empty content.

- [ ] **Step 2: Write the failing test for `LessonScope`**

Create `tests/api/services/lessons/test_types.py`:

```python
from api.server.services.lessons.types import LessonScope


def test_lesson_scope_requires_domain() -> None:
    scope = LessonScope(domain="hiring")
    assert scope.domain == "hiring"
    assert scope.persona_role is None
    assert scope.market is None


def test_lesson_scope_full() -> None:
    scope = LessonScope(domain="hiring", persona_role="recruiter", market="UK")
    assert scope.persona_role == "recruiter"
    assert scope.market == "UK"


def test_lesson_scope_matches_strict_when_equal() -> None:
    a = LessonScope(domain="hiring", persona_role="recruiter")
    b = LessonScope(domain="hiring", persona_role="recruiter")
    assert a.matches(b)


def test_lesson_scope_matches_broader_query() -> None:
    # A lesson scoped to {domain=hiring} should be visible to a query
    # scoped to {domain=hiring, persona_role=recruiter}.
    lesson_scope = LessonScope(domain="hiring")
    query_scope = LessonScope(domain="hiring", persona_role="recruiter")
    assert lesson_scope.matches(query_scope)


def test_lesson_scope_does_not_match_narrower() -> None:
    # The reverse must NOT match.
    lesson_scope = LessonScope(domain="hiring", persona_role="recruiter")
    query_scope = LessonScope(domain="hiring")
    assert not lesson_scope.matches(query_scope)


def test_lesson_scope_cross_domain_never_matches() -> None:
    a = LessonScope(domain="hiring")
    b = LessonScope(domain="vendor_kyc")
    assert not a.matches(b)
    assert not b.matches(a)
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/api/services/lessons/test_types.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'api.server.services.lessons.types'`.

- [ ] **Step 4: Implement the types**

Create `api/server/services/lessons/types.py`:

```python
"""Value types for the lesson store."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Optional


@dataclass(frozen=True)
class LessonScope:
    """Scope of a lesson: which queries should be able to see it.

    Matching is asymmetric: a lesson scope matches a query scope iff every
    field set on the lesson is either None or equal to the corresponding
    query field. A None field on the lesson means "any". A None field on
    the query means "the query did not narrow on that dimension".
    """
    domain: str
    persona_role: Optional[str] = None
    market: Optional[str] = None

    def matches(self, query: "LessonScope") -> bool:
        if self.domain != query.domain:
            return False
        if self.persona_role is not None and self.persona_role != query.persona_role:
            return False
        if self.market is not None and self.market != query.market:
            return False
        return True


@dataclass(frozen=True)
class LessonProvenance:
    """Where a lesson came from. Required on every active lesson."""
    proposed_by: str  # dream-pass id or skill id
    run_ids: tuple[str, ...]  # workflow run ids that produced the evidence
    rubric_score_delta: float  # measured improvement (0.0 if untested)
    experiment_n: int  # held-out sample size used to measure delta
    promoted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class Lesson:
    """An active lesson, readable by agents."""
    id: str
    body: str
    scope: LessonScope
    provenance: LessonProvenance
    status: Literal["candidate", "active", "superseded", "pruned"] = "active"
    supersedes: Optional[str] = None


@dataclass(frozen=True)
class LessonCandidate:
    """A proposed but not-yet-promoted lesson."""
    id: str
    body: str
    scope: LessonScope
    proposed_by: str
    rationale: str  # human-readable why-this-might-help
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/api/services/lessons/test_types.py -v`
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add api/server/services/lessons/__init__.py api/server/services/lessons/types.py tests/api/services/lessons/__init__.py tests/api/services/lessons/test_types.py
git commit -m "feat(lessons): add Lesson/LessonScope/LessonProvenance value types"
```

---

## Task 3: Define the LessonStore Protocol + in-memory test double

**Files:**
- Create: `api/server/services/lessons/store.py`
- Test: `tests/api/services/lessons/test_in_memory_store.py`
- Test: `tests/api/services/lessons/conftest.py`

- [ ] **Step 1: Write the conftest with a small builder fixture**

Create `tests/api/services/lessons/conftest.py`:

```python
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from api.server.services.lessons.types import (
    Lesson,
    LessonProvenance,
    LessonScope,
)


@pytest.fixture
def make_lesson():
    def _make(
        body: str = "vendors from agency X often miss reference checks",
        domain: str = "hiring",
        persona_role: str | None = None,
        delta: float = 0.07,
        n: int = 40,
    ) -> Lesson:
        return Lesson(
            id=str(uuid.uuid4()),
            body=body,
            scope=LessonScope(domain=domain, persona_role=persona_role),
            provenance=LessonProvenance(
                proposed_by="dream-pass:hiring:test",
                run_ids=("WF-001", "WF-002"),
                rubric_score_delta=delta,
                experiment_n=n,
                promoted_at=datetime.now(timezone.utc),
            ),
        )
    return _make
```

- [ ] **Step 2: Write the failing test for the in-memory store**

Create `tests/api/services/lessons/test_in_memory_store.py`:

```python
from __future__ import annotations

from api.server.services.lessons.store import InMemoryLessonStore
from api.server.services.lessons.types import LessonScope


def test_add_then_get(make_lesson) -> None:
    store = InMemoryLessonStore()
    lesson = make_lesson()
    store.add(lesson)
    assert store.get(lesson.id) == lesson


def test_search_returns_in_scope_lessons(make_lesson) -> None:
    store = InMemoryLessonStore()
    hire = make_lesson(domain="hiring")
    kyc = make_lesson(domain="vendor_kyc")
    store.add(hire)
    store.add(kyc)

    results = store.search("reference checks", scope=LessonScope(domain="hiring"), top_k=5)

    assert hire in results
    assert kyc not in results


def test_search_respects_broader_lesson_scope(make_lesson) -> None:
    store = InMemoryLessonStore()
    broad = make_lesson(domain="hiring", persona_role=None)
    store.add(broad)

    results = store.search(
        "anything",
        scope=LessonScope(domain="hiring", persona_role="recruiter"),
        top_k=5,
    )

    assert broad in results


def test_search_does_not_return_pruned(make_lesson) -> None:
    store = InMemoryLessonStore()
    lesson = make_lesson()
    store.add(lesson)
    store.prune(lesson.id, reason="superseded by stronger evidence")

    results = store.search("anything", scope=lesson.scope, top_k=5)

    assert results == []


def test_prune_marks_status(make_lesson) -> None:
    store = InMemoryLessonStore()
    lesson = make_lesson()
    store.add(lesson)
    store.prune(lesson.id, reason="superseded by stronger evidence")

    stored = store.get(lesson.id)
    assert stored is not None
    assert stored.status == "pruned"
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/api/services/lessons/test_in_memory_store.py -v`
Expected: FAIL with `ImportError: cannot import name 'InMemoryLessonStore'`.

- [ ] **Step 4: Implement the Protocol + in-memory store**

Create `api/server/services/lessons/store.py`:

```python
"""LessonStore Protocol + a deterministic in-memory implementation for tests."""
from __future__ import annotations

from dataclasses import replace
from typing import Protocol, runtime_checkable

from api.server.services.lessons.types import Lesson, LessonScope


@runtime_checkable
class LessonStore(Protocol):
    """Pluggable backend for the lesson tier.

    Implementations: InMemoryLessonStore (tests), Mem0LessonStore (default).
    Future: AzureSearchLessonStore, PgVectorLessonStore.

    Implementations MUST be storage-only. Governance, ledger writes, and
    Kuzu provenance are added by LessonGovernor in governor.py.
    """

    def add(self, lesson: Lesson) -> None: ...

    def get(self, lesson_id: str) -> Lesson | None: ...

    def search(
        self,
        query: str,
        *,
        scope: LessonScope,
        top_k: int = 5,
    ) -> list[Lesson]: ...

    def prune(self, lesson_id: str, *, reason: str) -> None: ...


class InMemoryLessonStore:
    """Deterministic in-memory store. NOT for production — substring match only."""

    def __init__(self) -> None:
        self._by_id: dict[str, Lesson] = {}

    def add(self, lesson: Lesson) -> None:
        self._by_id[lesson.id] = lesson

    def get(self, lesson_id: str) -> Lesson | None:
        return self._by_id.get(lesson_id)

    def search(
        self,
        query: str,
        *,
        scope: LessonScope,
        top_k: int = 5,
    ) -> list[Lesson]:
        del query  # in-memory store ignores semantic relevance
        results = [
            lesson
            for lesson in self._by_id.values()
            if lesson.status == "active" and lesson.scope.matches(scope)
        ]
        return results[:top_k]

    def prune(self, lesson_id: str, *, reason: str) -> None:
        del reason
        existing = self._by_id.get(lesson_id)
        if existing is None:
            return
        self._by_id[lesson_id] = replace(existing, status="pruned")
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/api/services/lessons/test_in_memory_store.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add api/server/services/lessons/store.py tests/api/services/lessons/test_in_memory_store.py tests/api/services/lessons/conftest.py
git commit -m "feat(lessons): add LessonStore Protocol + InMemoryLessonStore"
```

---

## Task 4: Implement Mem0LessonStore

**Files:**
- Create: `api/server/services/lessons/mem0_store.py`
- Test: `tests/api/services/lessons/test_mem0_store.py`

The Mem0LessonStore uses Mem0's filter dict for scope and stores the full Lesson value type as JSON metadata so we can rehydrate it on search.

- [ ] **Step 1: Write the failing test**

Create `tests/api/services/lessons/test_mem0_store.py`:

```python
from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from api.server.services.lessons.mem0_store import Mem0LessonStore
from api.server.services.lessons.types import LessonScope


@pytest.fixture
def fake_memory() -> MagicMock:
    return MagicMock(name="mem0.Memory")


def test_add_calls_mem0_with_serialised_lesson(make_lesson, fake_memory) -> None:
    store = Mem0LessonStore(memory=fake_memory)
    lesson = make_lesson()

    store.add(lesson)

    fake_memory.add.assert_called_once()
    _, kwargs = fake_memory.add.call_args
    assert kwargs["user_id"] == "lesson-store"
    metadata = kwargs["metadata"]
    assert metadata["lesson_id"] == lesson.id
    assert metadata["domain"] == "hiring"
    assert "lesson_json" in metadata
    rehydrated = json.loads(metadata["lesson_json"])
    assert rehydrated["body"] == lesson.body


def test_search_passes_scope_into_mem0_filters(make_lesson, fake_memory) -> None:
    store = Mem0LessonStore(memory=fake_memory)
    fake_memory.search.return_value = {"results": []}

    store.search(
        "reference",
        scope=LessonScope(domain="hiring", persona_role="recruiter"),
        top_k=3,
    )

    fake_memory.search.assert_called_once()
    _, kwargs = fake_memory.search.call_args
    assert kwargs["filters"] == {"user_id": "lesson-store", "domain": "hiring"}
    assert kwargs["top_k"] == 3


def test_search_rehydrates_lessons_and_filters_by_scope(
    make_lesson, fake_memory
) -> None:
    in_scope = make_lesson(domain="hiring", persona_role=None)
    narrower = make_lesson(domain="hiring", persona_role="hiring_manager")
    fake_memory.search.return_value = {
        "results": [
            {"metadata": _serialise(in_scope)},
            {"metadata": _serialise(narrower)},
        ]
    }

    store = Mem0LessonStore(memory=fake_memory)
    results = store.search(
        "anything",
        scope=LessonScope(domain="hiring", persona_role="recruiter"),
        top_k=5,
    )

    ids = {lesson.id for lesson in results}
    assert in_scope.id in ids
    assert narrower.id not in ids


def test_search_skips_non_active(make_lesson, fake_memory) -> None:
    from dataclasses import replace
    active = make_lesson()
    pruned = replace(make_lesson(), status="pruned")
    fake_memory.search.return_value = {
        "results": [
            {"metadata": _serialise(active)},
            {"metadata": _serialise(pruned)},
        ]
    }

    store = Mem0LessonStore(memory=fake_memory)
    results = store.search("x", scope=active.scope, top_k=5)

    ids = {lesson.id for lesson in results}
    assert active.id in ids
    assert pruned.id not in ids


def test_prune_marks_via_mem0_update(make_lesson, fake_memory) -> None:
    store = Mem0LessonStore(memory=fake_memory)
    lesson = make_lesson()
    store.add(lesson)
    fake_memory.reset_mock()

    store.prune(lesson.id, reason="superseded")

    fake_memory.delete.assert_called_once_with(memory_id=lesson.id)


def _serialise(lesson) -> dict[str, Any]:
    from api.server.services.lessons.mem0_store import _serialise_lesson
    return _serialise_lesson(lesson)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/api/services/lessons/test_mem0_store.py -v`
Expected: FAIL with `ImportError: cannot import name 'Mem0LessonStore'`.

- [ ] **Step 3: Implement Mem0LessonStore**

Create `api/server/services/lessons/mem0_store.py`:

```python
"""Mem0-backed implementation of LessonStore.

Mem0 is the storage tier only. Governance, audit ledger, and Kuzu
provenance are added by LessonGovernor — never call this class directly
from agent code.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from typing import Any, Protocol

from api.server.services.lessons.types import (
    Lesson,
    LessonProvenance,
    LessonScope,
)

_USER_ID = "lesson-store"  # Mem0's required entity scoping; we use one bucket


class _MemoryLike(Protocol):
    """Subset of mem0.Memory we depend on. Keeps tests fast."""
    def add(self, messages: str, *, user_id: str, metadata: dict[str, Any]) -> Any: ...
    def search(self, query: str, *, filters: dict[str, Any], top_k: int) -> Any: ...
    def delete(self, *, memory_id: str) -> Any: ...


class Mem0LessonStore:
    """Lesson store backed by mem0.Memory.

    Memories are scoped by `user_id="lesson-store"` and filtered by
    `domain` at search time. The full Lesson is serialised into metadata
    so we can rehydrate on read; this keeps Mem0 as a pure storage tier.
    """

    def __init__(self, *, memory: _MemoryLike | None = None) -> None:
        if memory is None:
            from mem0 import Memory
            memory = Memory()
        self._memory = memory

    def add(self, lesson: Lesson) -> None:
        self._memory.add(
            messages=lesson.body,
            user_id=_USER_ID,
            metadata=_serialise_lesson(lesson),
        )

    def get(self, lesson_id: str) -> Lesson | None:
        # Mem0's get-by-id is provider-specific; rely on a scoped search.
        results = self._memory.search(
            query=lesson_id,
            filters={"user_id": _USER_ID, "lesson_id": lesson_id},
            top_k=1,
        )
        for result in (results or {}).get("results", []):
            return _deserialise_lesson(result["metadata"])
        return None

    def search(
        self,
        query: str,
        *,
        scope: LessonScope,
        top_k: int = 5,
    ) -> list[Lesson]:
        results = self._memory.search(
            query=query,
            filters={"user_id": _USER_ID, "domain": scope.domain},
            top_k=top_k,
        )
        lessons: list[Lesson] = []
        for result in (results or {}).get("results", []):
            metadata = result.get("metadata") or {}
            try:
                lesson = _deserialise_lesson(metadata)
            except (KeyError, json.JSONDecodeError):
                continue
            if lesson.status != "active":
                continue
            if not lesson.scope.matches(scope):
                continue
            lessons.append(lesson)
        return lessons

    def prune(self, lesson_id: str, *, reason: str) -> None:
        del reason  # logged separately by LessonGovernor
        self._memory.delete(memory_id=lesson_id)


def _serialise_lesson(lesson: Lesson) -> dict[str, Any]:
    payload = asdict(lesson)
    payload["provenance"]["promoted_at"] = lesson.provenance.promoted_at.isoformat()
    return {
        "lesson_id": lesson.id,
        "domain": lesson.scope.domain,
        "persona_role": lesson.scope.persona_role or "",
        "market": lesson.scope.market or "",
        "status": lesson.status,
        "lesson_json": json.dumps(payload),
    }


def _deserialise_lesson(metadata: dict[str, Any]) -> Lesson:
    raw = json.loads(metadata["lesson_json"])
    scope = LessonScope(**raw["scope"])
    prov_raw = raw["provenance"]
    provenance = LessonProvenance(
        proposed_by=prov_raw["proposed_by"],
        run_ids=tuple(prov_raw["run_ids"]),
        rubric_score_delta=prov_raw["rubric_score_delta"],
        experiment_n=prov_raw["experiment_n"],
        promoted_at=datetime.fromisoformat(prov_raw["promoted_at"]),
    )
    return Lesson(
        id=raw["id"],
        body=raw["body"],
        scope=scope,
        provenance=provenance,
        status=raw["status"],
        supersedes=raw.get("supersedes"),
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/api/services/lessons/test_mem0_store.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add api/server/services/lessons/mem0_store.py tests/api/services/lessons/test_mem0_store.py
git commit -m "feat(lessons): add Mem0LessonStore implementation"
```

---

## Task 5: Extend Kuzu schema for lesson provenance

**Files:**
- Modify: `api/server/services/entity_graph.py` (the `_NODE_TABLES` and `_REL_TABLES` tuples)
- Test: `tests/api/services/lessons/test_kuzu_provenance.py`
- Create: `api/server/services/lessons/kuzu_provenance.py`

- [ ] **Step 1: Write the failing test for schema presence**

Create `tests/api/services/lessons/test_kuzu_provenance.py`:

```python
from __future__ import annotations

import pytest

from api.server.services.entity_graph import EntityGraph
from api.server.services.lessons.kuzu_provenance import KuzuLessonProvenance


@pytest.fixture
def graph(tmp_path):
    db_path = str(tmp_path / "lessons.kuzu")
    g = EntityGraph(db_path)
    yield g


def test_lesson_node_table_exists(graph) -> None:
    rows = graph.execute_cypher("CALL show_tables() RETURN name")
    names = {row["name"] for row in rows}
    assert "Lesson" in names


def test_lesson_from_run_rel_table_exists(graph) -> None:
    rows = graph.execute_cypher("CALL show_tables() RETURN name")
    names = {row["name"] for row in rows}
    assert "LESSON_FROM_RUN" in names


def test_record_lesson_inserts_node_and_run_edges(graph, make_lesson) -> None:
    lesson = make_lesson()
    # Pre-create the Workflow nodes the lesson points at.
    for run_id in lesson.provenance.run_ids:
        graph.execute_cypher(
            "CREATE (:Workflow {id: $id, workflow_type: 'hiring', status: 'complete'})",
            {"id": run_id},
        )

    provenance = KuzuLessonProvenance(graph)
    provenance.record(lesson)

    rows = graph.execute_cypher(
        "MATCH (l:Lesson {id: $id}) RETURN l.body AS body, l.domain AS domain",
        {"id": lesson.id},
    )
    assert rows[0]["body"] == lesson.body
    assert rows[0]["domain"] == "hiring"

    edge_rows = graph.execute_cypher(
        "MATCH (l:Lesson {id: $id})-[:LESSON_FROM_RUN]->(w:Workflow) RETURN w.id AS run_id",
        {"id": lesson.id},
    )
    assert {r["run_id"] for r in edge_rows} == set(lesson.provenance.run_ids)


def test_mark_pruned_updates_status(graph, make_lesson) -> None:
    lesson = make_lesson()
    for run_id in lesson.provenance.run_ids:
        graph.execute_cypher(
            "CREATE (:Workflow {id: $id, workflow_type: 'hiring', status: 'complete'})",
            {"id": run_id},
        )
    provenance = KuzuLessonProvenance(graph)
    provenance.record(lesson)

    provenance.mark_pruned(lesson.id, reason="superseded")

    rows = graph.execute_cypher(
        "MATCH (l:Lesson {id: $id}) RETURN l.status AS status, l.prune_reason AS reason",
        {"id": lesson.id},
    )
    assert rows[0]["status"] == "pruned"
    assert rows[0]["reason"] == "superseded"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/api/services/lessons/test_kuzu_provenance.py -v`
Expected: FAIL — first on missing module, then on missing tables.

- [ ] **Step 3: Add the Lesson node table and edge tables to the schema**

In `api/server/services/entity_graph.py`, find the `_NODE_TABLES` tuple. Add a new entry at the end of the tuple, immediately before the closing `)`:

```python
        ("Lesson", "CREATE NODE TABLE IF NOT EXISTS Lesson (id STRING, body STRING, domain STRING, persona_role STRING, market STRING, status STRING, proposed_by STRING, rubric_score_delta DOUBLE, experiment_n INT64, promoted_at TIMESTAMP, supersedes STRING, prune_reason STRING, PRIMARY KEY (id))"),
```

Find the `_REL_TABLES` tuple. Add three new entries at the end of the tuple, immediately before the closing `)`:

```python
        ("LESSON_FROM_RUN", "CREATE REL TABLE IF NOT EXISTS LESSON_FROM_RUN (FROM Lesson TO Workflow, recorded_at TIMESTAMP)"),
        ("LESSON_ABOUT_PERSONA", "CREATE REL TABLE IF NOT EXISTS LESSON_ABOUT_PERSONA (FROM Lesson TO Person, recorded_at TIMESTAMP)"),
        ("LESSON_SUPERSEDES", "CREATE REL TABLE IF NOT EXISTS LESSON_SUPERSEDES (FROM Lesson TO Lesson, recorded_at TIMESTAMP)"),
```

- [ ] **Step 4: Implement KuzuLessonProvenance**

Create `api/server/services/lessons/kuzu_provenance.py`:

```python
"""Kuzu writes for the Lesson provenance subgraph.

Stores the *structured* side of a lesson (provenance, scope, links to
runs). The free-text body lives in the LessonStore (Mem0); both are
joined by the lesson id.
"""
from __future__ import annotations

from datetime import datetime, timezone

from api.server.services.entity_graph import EntityGraph
from api.server.services.lessons.types import Lesson


class KuzuLessonProvenance:
    def __init__(self, graph: EntityGraph) -> None:
        self._graph = graph

    def record(self, lesson: Lesson) -> None:
        self._graph.execute_cypher(
            """
            MERGE (l:Lesson {id: $id})
            SET l.body = $body,
                l.domain = $domain,
                l.persona_role = $persona_role,
                l.market = $market,
                l.status = $status,
                l.proposed_by = $proposed_by,
                l.rubric_score_delta = $delta,
                l.experiment_n = $n,
                l.promoted_at = $promoted_at,
                l.supersedes = $supersedes
            """,
            {
                "id": lesson.id,
                "body": lesson.body,
                "domain": lesson.scope.domain,
                "persona_role": lesson.scope.persona_role or "",
                "market": lesson.scope.market or "",
                "status": lesson.status,
                "proposed_by": lesson.provenance.proposed_by,
                "delta": lesson.provenance.rubric_score_delta,
                "n": lesson.provenance.experiment_n,
                "promoted_at": lesson.provenance.promoted_at,
                "supersedes": lesson.supersedes or "",
            },
        )
        for run_id in lesson.provenance.run_ids:
            self._graph.execute_cypher(
                """
                MATCH (l:Lesson {id: $lesson_id}), (w:Workflow {id: $run_id})
                CREATE (l)-[:LESSON_FROM_RUN {recorded_at: $now}]->(w)
                """,
                {
                    "lesson_id": lesson.id,
                    "run_id": run_id,
                    "now": datetime.now(timezone.utc),
                },
            )
        if lesson.supersedes:
            self._graph.execute_cypher(
                """
                MATCH (l:Lesson {id: $new}), (prev:Lesson {id: $prev})
                CREATE (l)-[:LESSON_SUPERSEDES {recorded_at: $now}]->(prev)
                """,
                {
                    "new": lesson.id,
                    "prev": lesson.supersedes,
                    "now": datetime.now(timezone.utc),
                },
            )

    def mark_pruned(self, lesson_id: str, *, reason: str) -> None:
        self._graph.execute_cypher(
            """
            MATCH (l:Lesson {id: $id})
            SET l.status = 'pruned', l.prune_reason = $reason
            """,
            {"id": lesson_id, "reason": reason},
        )
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/api/services/lessons/test_kuzu_provenance.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add api/server/services/entity_graph.py api/server/services/lessons/kuzu_provenance.py tests/api/services/lessons/test_kuzu_provenance.py
git commit -m "feat(lessons): add Lesson node + provenance edges to Kuzu schema"
```

---

## Task 6: Register lesson.write / lesson.prune tools in the AGT policy bundle

**Files:**
- Modify: `data/policies/tools.yaml`

- [ ] **Step 1: Read the current tools.yaml to find the format**

Run: `head -40 data/policies/tools.yaml`
Expected: see existing tool entries (e.g. `greenhouse_get_candidate`, `concur_submit_expense`) so you can mirror the format.

- [ ] **Step 2: Add the two new tools**

Append to `data/policies/tools.yaml`:

```yaml
  - id: lesson.write
    description: |
      Writes a promoted Lesson into the LessonStore. Invoked exclusively by
      the dream-pass loop, never by domain agents directly. Body, scope, and
      provenance are governed by dream-pass.policy.yaml in Plan 3.
    reversibility: reversible          # prune undoes it
    enforcement: audit                 # log_only during Plan 1; promoted to enforce in Plan 3
    capabilities_required: [lessons.write]

  - id: lesson.prune
    description: |
      Soft-deletes a Lesson by marking status=pruned in both the LessonStore
      and the Kuzu provenance node. Reason is recorded in the ledger.
    reversibility: reversible
    enforcement: audit
    capabilities_required: [lessons.write]
```

- [ ] **Step 3: Verify the policy bundle still compiles**

Run: `uv run python -c "from api.server.services.governance.policy_compiler import compile_bundle; print(compile_bundle()[:80])"`
Expected: prints first 80 chars of compiled YAML, no exception.

- [ ] **Step 4: Commit**

```bash
git add data/policies/tools.yaml
git commit -m "feat(lessons): register lesson.write/lesson.prune in AGT tool policy"
```

---

## Task 7: Implement LessonGovernor (AGT-gated wrapper)

**Files:**
- Create: `api/server/services/lessons/governor.py`
- Test: `tests/api/services/lessons/test_governor.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/services/lessons/test_governor.py`:

```python
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from api.server.services.governance.kernel import Decision, GovernanceDenied
from api.server.services.lessons.governor import LessonGovernor
from api.server.services.lessons.store import InMemoryLessonStore


@pytest.fixture
def fake_kernel() -> MagicMock:
    return MagicMock(name="GovernanceKernel")


@pytest.fixture
def fake_audit() -> MagicMock:
    return MagicMock(name="AuditLogger")


@pytest.fixture
def fake_provenance() -> MagicMock:
    return MagicMock(name="KuzuLessonProvenance")


def test_write_calls_kernel_then_store_then_audit(
    make_lesson, fake_kernel, fake_audit, fake_provenance
) -> None:
    fake_kernel.evaluate_tool_call.return_value = Decision(
        allowed=True, action="allow", reason="ok"
    )
    store = InMemoryLessonStore()
    governor = LessonGovernor(
        store=store,
        kernel=lambda: fake_kernel,
        audit=fake_audit,
        provenance=fake_provenance,
        actor="dream-pass:hiring",
    )
    lesson = make_lesson()

    governor.write(lesson)

    fake_kernel.evaluate_tool_call.assert_called_once()
    _, kwargs = fake_kernel.evaluate_tool_call.call_args
    assert kwargs["actor"] == "dream-pass:hiring"
    assert kwargs["tool"] == "lesson.write"
    assert kwargs["args"]["lesson_id"] == lesson.id
    assert store.get(lesson.id) == lesson
    fake_provenance.record.assert_called_once_with(lesson)
    fake_audit.log.assert_called_once()


def test_write_denied_does_not_touch_store(
    make_lesson, fake_kernel, fake_audit, fake_provenance
) -> None:
    fake_kernel.evaluate_tool_call.return_value = Decision(
        allowed=False,
        action="deny",
        reason="capability missing",
        enforcement_mode="enforce",
    )
    store = InMemoryLessonStore()
    governor = LessonGovernor(
        store=store,
        kernel=lambda: fake_kernel,
        audit=fake_audit,
        provenance=fake_provenance,
        actor="dream-pass:hiring",
    )
    lesson = make_lesson()

    with pytest.raises(GovernanceDenied):
        governor.write(lesson)

    assert store.get(lesson.id) is None
    fake_provenance.record.assert_not_called()


def test_write_denied_in_audit_mode_still_writes_but_logs_deny(
    make_lesson, fake_kernel, fake_audit, fake_provenance
) -> None:
    fake_kernel.evaluate_tool_call.return_value = Decision(
        allowed=False,
        action="deny",
        reason="capability missing",
        enforcement_mode="log_only",
    )
    store = InMemoryLessonStore()
    governor = LessonGovernor(
        store=store,
        kernel=lambda: fake_kernel,
        audit=fake_audit,
        provenance=fake_provenance,
        actor="dream-pass:hiring",
    )
    lesson = make_lesson()

    governor.write(lesson)  # log_only mode: write proceeds

    assert store.get(lesson.id) == lesson
    fake_audit.log.assert_called_once()
    _, kwargs = fake_audit.log.call_args
    assert kwargs["details"]["governance_action"] == "deny"


def test_prune_records_in_ledger_with_reason(
    make_lesson, fake_kernel, fake_audit, fake_provenance
) -> None:
    fake_kernel.evaluate_tool_call.return_value = Decision(
        allowed=True, action="allow", reason="ok"
    )
    store = InMemoryLessonStore()
    lesson = make_lesson()
    store.add(lesson)
    governor = LessonGovernor(
        store=store,
        kernel=lambda: fake_kernel,
        audit=fake_audit,
        provenance=fake_provenance,
        actor="dream-pass:hiring",
    )

    governor.prune(lesson.id, reason="superseded by stronger evidence")

    _, kwargs = fake_audit.log.call_args
    assert kwargs["action"] == "lesson.prune"
    assert kwargs["details"]["reason"] == "superseded by stronger evidence"
    fake_provenance.mark_pruned.assert_called_once_with(
        lesson.id, reason="superseded by stronger evidence"
    )
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/api/services/lessons/test_governor.py -v`
Expected: FAIL with `ImportError: cannot import name 'LessonGovernor'`.

- [ ] **Step 3: Implement LessonGovernor**

Create `api/server/services/lessons/governor.py`:

```python
"""LessonGovernor — the one path agents (and the dream pass) use.

Wraps a LessonStore with:
  1. AGT policy evaluation on every write/prune.
  2. Kuzu provenance writes pointing at the runs that birthed the lesson.
  3. ActionLedgerEntry writes for a signed, hash-chained audit trail.

Never bypass this. The dream pass uses `governor.write(lesson)`,
never `store.add(lesson)` directly.
"""
from __future__ import annotations

import time
from typing import Callable, Protocol

from api.server.services.governance.kernel import (
    Decision,
    GovernanceDenied,
    GovernanceKernel,
)
from api.server.services.lessons.kuzu_provenance import KuzuLessonProvenance
from api.server.services.lessons.store import LessonStore
from api.server.services.lessons.types import Lesson


class _AuditLike(Protocol):
    def log(
        self,
        *,
        workflow_id: str,
        actor_kind: str,
        actor_id: str,
        action: str,
        revocable: bool,
        details: dict,
        decision_id: str | None,
        policy_version: str | None,
        enforcement_mode: str | None,
    ) -> None: ...


class LessonGovernor:
    def __init__(
        self,
        *,
        store: LessonStore,
        kernel: Callable[[], GovernanceKernel],
        audit: _AuditLike,
        provenance: KuzuLessonProvenance,
        actor: str,
        workflow_id: str = "system:lessons",
    ) -> None:
        self._store = store
        self._kernel_factory = kernel
        self._audit = audit
        self._provenance = provenance
        self._actor = actor
        self._workflow_id = workflow_id

    def write(self, lesson: Lesson) -> None:
        decision = self._kernel_factory().evaluate_tool_call(
            actor=self._actor,
            tool="lesson.write",
            args={
                "lesson_id": lesson.id,
                "domain": lesson.scope.domain,
                "delta": lesson.provenance.rubric_score_delta,
                "n": lesson.provenance.experiment_n,
            },
            workflow_id=self._workflow_id,
        )
        self._enforce(decision, lesson_id=lesson.id, action="lesson.write")
        self._store.add(lesson)
        self._provenance.record(lesson)
        self._record_ledger(decision, action="lesson.write", details={
            "lesson_id": lesson.id,
            "domain": lesson.scope.domain,
            "delta": lesson.provenance.rubric_score_delta,
            "n": lesson.provenance.experiment_n,
            "governance_action": decision.action,
        })

    def prune(self, lesson_id: str, *, reason: str) -> None:
        decision = self._kernel_factory().evaluate_tool_call(
            actor=self._actor,
            tool="lesson.prune",
            args={"lesson_id": lesson_id, "reason": reason},
            workflow_id=self._workflow_id,
        )
        self._enforce(decision, lesson_id=lesson_id, action="lesson.prune")
        self._store.prune(lesson_id, reason=reason)
        self._provenance.mark_pruned(lesson_id, reason=reason)
        self._record_ledger(decision, action="lesson.prune", details={
            "lesson_id": lesson_id,
            "reason": reason,
            "governance_action": decision.action,
        })

    def _enforce(self, decision: Decision, *, lesson_id: str, action: str) -> None:
        if decision.allowed:
            return
        if decision.enforcement_mode == "enforce":
            raise GovernanceDenied(decision)
        # log_only: write proceeds; the ledger entry will mark governance_action=deny

    def _record_ledger(self, decision: Decision, *, action: str, details: dict) -> None:
        self._audit.log(
            workflow_id=self._workflow_id,
            actor_kind="agent",
            actor_id=self._actor,
            action=action,
            revocable=True,
            details=details,
            decision_id=decision.decision_id,
            policy_version=decision.policy_version,
            enforcement_mode=decision.enforcement_mode,
        )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/api/services/lessons/test_governor.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add api/server/services/lessons/governor.py tests/api/services/lessons/test_governor.py
git commit -m "feat(lessons): add AGT-gated LessonGovernor wrapper"
```

---

## Task 8: Wire the package surface in `__init__.py`

**Files:**
- Modify: `api/server/services/lessons/__init__.py`

- [ ] **Step 1: Re-export the public surface**

Replace the content of `api/server/services/lessons/__init__.py` with:

```python
"""Lesson store: shared, governed, cross-agent memory tier.

Public surface:
  - Lesson, LessonScope, LessonProvenance, LessonCandidate (types)
  - LessonStore (Protocol), InMemoryLessonStore (tests)
  - Mem0LessonStore (default impl)
  - LessonGovernor (the one path callers use)
  - KuzuLessonProvenance (provenance writes)
"""
from api.server.services.lessons.governor import LessonGovernor
from api.server.services.lessons.kuzu_provenance import KuzuLessonProvenance
from api.server.services.lessons.mem0_store import Mem0LessonStore
from api.server.services.lessons.store import InMemoryLessonStore, LessonStore
from api.server.services.lessons.types import (
    Lesson,
    LessonCandidate,
    LessonProvenance,
    LessonScope,
)

__all__ = [
    "Lesson",
    "LessonCandidate",
    "LessonGovernor",
    "LessonProvenance",
    "LessonScope",
    "LessonStore",
    "InMemoryLessonStore",
    "KuzuLessonProvenance",
    "Mem0LessonStore",
]
```

- [ ] **Step 2: Verify import works**

Run: `uv run python -c "from api.server.services.lessons import LessonGovernor, Mem0LessonStore; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add api/server/services/lessons/__init__.py
git commit -m "chore(lessons): export public surface from package"
```

---

## Task 9: CLI smoke script

**Files:**
- Create: `scripts/lessons_smoke.py`

- [ ] **Step 1: Implement the script**

Create `scripts/lessons_smoke.py`:

```python
"""End-to-end smoke test for the lesson store foundation.

Usage:
    uv run python scripts/lessons_smoke.py

Writes one lesson via LessonGovernor → reads it back → prunes it.
Prints the resulting ActionLedgerEntry stream so you can eyeball the
chain. Uses InMemoryLessonStore so it requires no Mem0 server.
"""
from __future__ import annotations

import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from api.server.services.audit_logger import AuditLogger
from api.server.services.entity_graph import EntityGraph
from api.server.services.governance import kernel
from api.server.services.lessons import (
    InMemoryLessonStore,
    KuzuLessonProvenance,
    Lesson,
    LessonGovernor,
    LessonProvenance,
    LessonScope,
)


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="lessons-smoke-"))
    graph = EntityGraph(str(tmp / "smoke.kuzu"))
    # Seed a Workflow node so the provenance edge has something to point at.
    run_id = "WF-SMOKE-001"
    graph.execute_cypher(
        "CREATE (:Workflow {id: $id, workflow_type: 'hiring', status: 'complete'})",
        {"id": run_id},
    )

    store = InMemoryLessonStore()
    provenance = KuzuLessonProvenance(graph)
    audit = AuditLogger()  # writes to the local default sink
    governor = LessonGovernor(
        store=store,
        kernel=kernel,
        audit=audit,
        provenance=provenance,
        actor="dream-pass:hiring:smoke",
    )

    lesson = Lesson(
        id=str(uuid.uuid4()),
        body="vendors from agency X often miss reference checks at step 3",
        scope=LessonScope(domain="hiring"),
        provenance=LessonProvenance(
            proposed_by="dream-pass:hiring:smoke",
            run_ids=(run_id,),
            rubric_score_delta=0.08,
            experiment_n=40,
            promoted_at=datetime.now(timezone.utc),
        ),
    )

    print(f"writing lesson {lesson.id} ...")
    governor.write(lesson)
    print(f"  scope={lesson.scope}")
    print(f"  delta={lesson.provenance.rubric_score_delta} n={lesson.provenance.experiment_n}")

    found = store.search("reference checks", scope=lesson.scope, top_k=5)
    print(f"search returned {len(found)} lesson(s); ids={[l.id for l in found]}")

    print(f"pruning lesson {lesson.id} ...")
    governor.prune(lesson.id, reason="smoke run complete")

    after = store.search("reference checks", scope=lesson.scope, top_k=5)
    print(f"search after prune: {len(after)} (expected 0)")

    rows = graph.execute_cypher(
        "MATCH (l:Lesson {id: $id}) RETURN l.status AS status, l.prune_reason AS reason",
        {"id": lesson.id},
    )
    print(f"kuzu lesson row: {rows}")

    print("smoke ok")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the script**

Run: `uv run python scripts/lessons_smoke.py`
Expected: prints `smoke ok` and shows lesson written, searched, pruned, with Kuzu row showing `status='pruned'`.

- [ ] **Step 3: Commit**

```bash
git add scripts/lessons_smoke.py
git commit -m "feat(lessons): add end-to-end CLI smoke script"
```

---

## Task 11: Working memory types

**Files:**
- Create: `api/server/services/lessons/working_memory_types.py`
- Test: `tests/api/services/lessons/test_working_memory_types.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/services/lessons/test_working_memory_types.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from api.server.services.lessons.working_memory_types import (
    WorkingNote,
    WorkingNoteKind,
)


def test_working_note_minimal() -> None:
    note = WorkingNote(
        id="WN-1",
        workflow_id="WF-1",
        agent_skill="interview-recommender",
        kind="observation",
        body="screening flagged employment-date inconsistency",
    )
    assert note.workflow_id == "WF-1"
    assert note.kind == "observation"
    assert note.consumed_by_dream_pass is None


def test_working_note_kind_alphabet_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        WorkingNote(
            id="WN-1",
            workflow_id="WF-1",
            agent_skill="x",
            kind="bogus",   # type: ignore[arg-type]
            body="x",
        )


def test_working_note_mark_consumed_returns_new_instance() -> None:
    note = WorkingNote(
        id="WN-1",
        workflow_id="WF-1",
        agent_skill="x",
        kind="observation",
        body="x",
    )
    consumed = note.mark_consumed(dream_pass_id="DP-1")
    assert consumed.consumed_by_dream_pass == "DP-1"
    assert note.consumed_by_dream_pass is None  # original unchanged
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/api/services/lessons/test_working_memory_types.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement the types**

Create `api/server/services/lessons/working_memory_types.py`:

```python
"""Value types for the working memory tier."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Literal, Optional


WorkingNoteKind = Literal[
    "observation",   # something the agent noticed (free text)
    "decision",      # what the agent decided + brief why
    "tool_call",     # a tool invocation captured from session events
    "surprise",      # explicit "this differed from expectation"
]


@dataclass(frozen=True)
class WorkingNote:
    id: str
    workflow_id: str
    agent_skill: str        # e.g. "interview-recommender"
    kind: WorkingNoteKind
    body: str
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    consumed_by_dream_pass: Optional[str] = None

    def __post_init__(self) -> None:
        from typing import get_args
        if self.kind not in get_args(WorkingNoteKind):
            raise ValueError(f"unknown WorkingNoteKind {self.kind!r}")

    def mark_consumed(self, *, dream_pass_id: str) -> "WorkingNote":
        return replace(self, consumed_by_dream_pass=dream_pass_id)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/api/services/lessons/test_working_memory_types.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add api/server/services/lessons/working_memory_types.py tests/api/services/lessons/test_working_memory_types.py
git commit -m "feat(lessons): add WorkingNote value type"
```

---

## Task 12: WorkingMemoryStore (Mem0-backed, scoped by workflow_id)

**Files:**
- Create: `api/server/services/lessons/working_memory_store.py`
- Test: `tests/api/services/lessons/test_working_memory_store.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/services/lessons/test_working_memory_store.py`:

```python
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from api.server.services.lessons.working_memory_store import (
    InMemoryWorkingMemoryStore,
    Mem0WorkingMemoryStore,
    _user_id_for,
)
from api.server.services.lessons.working_memory_types import WorkingNote


def _note(workflow_id: str = "WF-1", agent_skill: str = "interview-recommender") -> WorkingNote:
    return WorkingNote(
        id="WN-1",
        workflow_id=workflow_id,
        agent_skill=agent_skill,
        kind="observation",
        body="screening flagged employment-date inconsistency",
    )


def test_user_id_isolation_per_workflow() -> None:
    a = _user_id_for("WF-1")
    b = _user_id_for("WF-2")
    assert a != b
    assert a.startswith("working-memory:")


def test_in_memory_add_then_list() -> None:
    store = InMemoryWorkingMemoryStore()
    note = _note()
    store.add(note)
    notes = store.list_for_workflow(workflow_id="WF-1")
    assert notes == [note]


def test_in_memory_list_skips_consumed() -> None:
    store = InMemoryWorkingMemoryStore()
    n = _note()
    store.add(n)
    store.mark_consumed(note_id=n.id, dream_pass_id="DP-1")
    assert store.list_for_workflow(workflow_id="WF-1") == []


def test_in_memory_list_recent_across_workflows() -> None:
    store = InMemoryWorkingMemoryStore()
    store.add(_note(workflow_id="WF-1"))
    other = WorkingNote(id="WN-2", workflow_id="WF-2", agent_skill="x", kind="observation", body="y")
    store.add(other)
    notes = store.list_recent_unconsumed(domain_agents=("interview-recommender", "x"), limit=10)
    assert {n.id for n in notes} == {"WN-1", "WN-2"}


def test_mem0_add_uses_workflow_scoped_user_id() -> None:
    fake = MagicMock()
    store = Mem0WorkingMemoryStore(memory=fake)
    note = _note(workflow_id="WF-7")

    store.add(note)

    fake.add.assert_called_once()
    _, kwargs = fake.add.call_args
    assert kwargs["user_id"] == _user_id_for("WF-7")
    assert kwargs["metadata"]["agent_skill"] == "interview-recommender"
    assert kwargs["metadata"]["kind"] == "observation"


def test_mem0_list_recent_filters_consumed_in_memory(make_lesson) -> None:
    fake = MagicMock()
    fake.search.return_value = {
        "results": [
            {"metadata": _serialise(_note())},
        ]
    }
    store = Mem0WorkingMemoryStore(memory=fake)

    notes = store.list_recent_unconsumed(domain_agents=("interview-recommender",), limit=10)

    assert len(notes) == 1
    assert notes[0].id == "WN-1"


def _serialise(note: WorkingNote) -> dict:
    from api.server.services.lessons.working_memory_store import _serialise_note
    return _serialise_note(note)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/api/services/lessons/test_working_memory_store.py -v`
Expected: `ImportError`.

- [ ] **Step 3: Implement both stores**

Create `api/server/services/lessons/working_memory_store.py`:

```python
"""Working memory tier.

Per-workflow_id scratchpad written by agents during a run; consumed by
the dream pass between runs. Mem0-backed for production, in-memory for
tests. Like LessonStore, this is storage only — governance and ledger
writes live in WorkingMemoryGovernor (Task 13).
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from typing import Any, Protocol

from api.server.services.lessons.working_memory_types import WorkingNote


def _user_id_for(workflow_id: str) -> str:
    return f"working-memory:{workflow_id}"


class WorkingMemoryStore(Protocol):
    def add(self, note: WorkingNote) -> None: ...
    def list_for_workflow(self, *, workflow_id: str) -> list[WorkingNote]: ...
    def list_recent_unconsumed(
        self, *, domain_agents: tuple[str, ...], limit: int = 200
    ) -> list[WorkingNote]: ...
    def mark_consumed(self, *, note_id: str, dream_pass_id: str) -> None: ...


class InMemoryWorkingMemoryStore:
    def __init__(self) -> None:
        self._by_id: dict[str, WorkingNote] = {}

    def add(self, note: WorkingNote) -> None:
        self._by_id[note.id] = note

    def list_for_workflow(self, *, workflow_id: str) -> list[WorkingNote]:
        return [
            n for n in self._by_id.values()
            if n.workflow_id == workflow_id and n.consumed_by_dream_pass is None
        ]

    def list_recent_unconsumed(
        self, *, domain_agents: tuple[str, ...], limit: int = 200
    ) -> list[WorkingNote]:
        out = [
            n for n in self._by_id.values()
            if n.consumed_by_dream_pass is None and n.agent_skill in domain_agents
        ]
        out.sort(key=lambda n: n.captured_at, reverse=True)
        return out[:limit]

    def mark_consumed(self, *, note_id: str, dream_pass_id: str) -> None:
        existing = self._by_id.get(note_id)
        if existing is None:
            return
        self._by_id[note_id] = existing.mark_consumed(dream_pass_id=dream_pass_id)


class _MemoryLike(Protocol):
    def add(self, messages: str, *, user_id: str, metadata: dict[str, Any]) -> Any: ...
    def search(self, query: str, *, filters: dict[str, Any], top_k: int) -> Any: ...
    def update(self, *, memory_id: str, data: str | None = None, metadata: dict[str, Any] | None = None) -> Any: ...


class Mem0WorkingMemoryStore:
    def __init__(self, *, memory: _MemoryLike | None = None) -> None:
        if memory is None:
            from mem0 import Memory
            memory = Memory()
        self._memory = memory

    def add(self, note: WorkingNote) -> None:
        self._memory.add(
            messages=note.body,
            user_id=_user_id_for(note.workflow_id),
            metadata=_serialise_note(note),
        )

    def list_for_workflow(self, *, workflow_id: str) -> list[WorkingNote]:
        results = self._memory.search(
            query="",
            filters={"user_id": _user_id_for(workflow_id)},
            top_k=200,
        )
        return [
            n for n in (_deserialise_note(r.get("metadata") or {}) for r in (results or {}).get("results", []))
            if n is not None and n.consumed_by_dream_pass is None
        ]

    def list_recent_unconsumed(
        self, *, domain_agents: tuple[str, ...], limit: int = 200
    ) -> list[WorkingNote]:
        # Mem0 doesn't natively filter across user_ids, so we filter by metadata.
        results = self._memory.search(
            query="",
            filters={"agent_skill": list(domain_agents)},  # mem0 list-in semantics
            top_k=limit,
        )
        notes: list[WorkingNote] = []
        for r in (results or {}).get("results", []):
            n = _deserialise_note(r.get("metadata") or {})
            if n is not None and n.consumed_by_dream_pass is None:
                notes.append(n)
        notes.sort(key=lambda n: n.captured_at, reverse=True)
        return notes[:limit]

    def mark_consumed(self, *, note_id: str, dream_pass_id: str) -> None:
        # Soft-delete via metadata update; the actual prune happens in GC.
        self._memory.update(
            memory_id=note_id,
            metadata={"consumed_by_dream_pass": dream_pass_id},
        )


def _serialise_note(note: WorkingNote) -> dict[str, Any]:
    payload = asdict(note)
    payload["captured_at"] = note.captured_at.isoformat()
    return {
        "note_id": note.id,
        "workflow_id": note.workflow_id,
        "agent_skill": note.agent_skill,
        "kind": note.kind,
        "captured_at": payload["captured_at"],
        "consumed_by_dream_pass": note.consumed_by_dream_pass or "",
        "note_json": json.dumps(payload),
    }


def _deserialise_note(metadata: dict[str, Any]) -> WorkingNote | None:
    raw_json = metadata.get("note_json")
    if not raw_json:
        return None
    try:
        raw = json.loads(raw_json)
    except json.JSONDecodeError:
        return None
    return WorkingNote(
        id=raw["id"],
        workflow_id=raw["workflow_id"],
        agent_skill=raw["agent_skill"],
        kind=raw["kind"],
        body=raw["body"],
        captured_at=datetime.fromisoformat(raw["captured_at"]),
        consumed_by_dream_pass=(raw.get("consumed_by_dream_pass") or None) or None,
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/api/services/lessons/test_working_memory_store.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add api/server/services/lessons/working_memory_store.py tests/api/services/lessons/test_working_memory_store.py
git commit -m "feat(lessons): add WorkingMemoryStore (in-memory + Mem0 impls)"
```

---

## Task 13: Capture working notes from existing OTEL session events

**Files:**
- Create: `api/server/services/lessons/working_memory_capture.py`
- Test: `tests/api/services/lessons/test_working_memory_capture.py`
- Modify: `api/functions/graphs/executors/agents/_wrapper.py` — add a single hook line that calls into `working_memory_capture` when an agent session completes

The substrate's `_wrapper.py` already emits `FleetEvent("agent.completed", ...)` for every agent session and already streams tool-call events via the OTEL bridge. Working memory capture is a passive subscriber that turns those events into `WorkingNote` rows.

- [ ] **Step 0: Verify the existing event surface**

Run: `grep -n "agent.completed\|FleetEvent\|on_event\|TOOL_EXECUTION" api/functions/graphs/executors/agents/_wrapper.py | head -30`

Expected: confirm the events you'll subscribe to (`agent.completed`, `TOOL_EXECUTION_COMPLETE`). Note the exact payload shape — the test fixture in Step 1 must mirror it.

- [ ] **Step 1: Write the failing test**

Create `tests/api/services/lessons/test_working_memory_capture.py`:

```python
from __future__ import annotations

from unittest.mock import MagicMock

from api.server.services.lessons.working_memory_capture import (
    WorkingMemoryCapture,
)
from api.server.services.lessons.working_memory_store import (
    InMemoryWorkingMemoryStore,
)


def test_agent_completed_event_produces_decision_note() -> None:
    store = InMemoryWorkingMemoryStore()
    capture = WorkingMemoryCapture(store=store)

    capture.on_agent_completed(
        workflow_id="WF-1",
        agent_skill="interview-recommender",
        response_text='{"decision": "advance", "rationale": "level signal strong"}',
        tool_calls=[],
    )

    notes = store.list_for_workflow(workflow_id="WF-1")
    assert len(notes) == 1
    assert notes[0].kind == "decision"
    assert "advance" in notes[0].body


def test_tool_call_event_produces_tool_note() -> None:
    store = InMemoryWorkingMemoryStore()
    capture = WorkingMemoryCapture(store=store)

    capture.on_agent_completed(
        workflow_id="WF-1",
        agent_skill="interview-recommender",
        response_text="{}",
        tool_calls=[
            {"tool": "greenhouse_get_candidate", "args": {"id": "C-001"}, "latency_ms": 120},
        ],
    )

    notes = store.list_for_workflow(workflow_id="WF-1")
    tool_notes = [n for n in notes if n.kind == "tool_call"]
    assert len(tool_notes) == 1
    assert "greenhouse_get_candidate" in tool_notes[0].body


def test_capture_ignores_workflow_id_none() -> None:
    store = InMemoryWorkingMemoryStore()
    capture = WorkingMemoryCapture(store=store)

    capture.on_agent_completed(
        workflow_id=None,
        agent_skill="x",
        response_text="{}",
        tool_calls=[],
    )

    assert store.list_for_workflow(workflow_id="WF-anything") == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/api/services/lessons/test_working_memory_capture.py -v`
Expected: `ImportError`.

- [ ] **Step 3: Implement the capture**

Create `api/server/services/lessons/working_memory_capture.py`:

```python
"""Capture agent session events into working memory.

Subscribes to the existing `agent.completed` FleetEvent stream and the
tool-call events emitted by `_wrapper.py`. Turns each session into a
small bundle of WorkingNotes: one `decision` (the parsed response), one
`tool_call` per invocation. The dream pass reads these later.

This module is *passive*: it does not change the agent runtime, it only
turns events into structured notes the dream pass can consume.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from api.server.services.lessons.working_memory_store import WorkingMemoryStore
from api.server.services.lessons.working_memory_types import WorkingNote


class WorkingMemoryCapture:
    def __init__(self, *, store: WorkingMemoryStore) -> None:
        self._store = store

    def on_agent_completed(
        self,
        *,
        workflow_id: str | None,
        agent_skill: str,
        response_text: str,
        tool_calls: list[dict[str, Any]],
    ) -> None:
        if not workflow_id:
            return  # synthetic / unattributed sessions don't write working memory

        decision_body = self._summarise_decision(response_text)
        self._store.add(WorkingNote(
            id=f"WN-{uuid.uuid4()}",
            workflow_id=workflow_id,
            agent_skill=agent_skill,
            kind="decision",
            body=decision_body,
        ))

        for tc in tool_calls:
            tool = str(tc.get("tool", "unknown"))
            latency = tc.get("latency_ms")
            body = f"called {tool}" + (f" ({latency}ms)" if latency is not None else "")
            self._store.add(WorkingNote(
                id=f"WN-{uuid.uuid4()}",
                workflow_id=workflow_id,
                agent_skill=agent_skill,
                kind="tool_call",
                body=body,
            ))

    @staticmethod
    def _summarise_decision(response_text: str) -> str:
        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError:
            return response_text[:240]
        if isinstance(parsed, dict):
            decision = parsed.get("decision")
            rationale = parsed.get("rationale") or parsed.get("reason")
            if decision and rationale:
                return f"{decision}: {rationale}"
            if decision:
                return f"decision={decision}"
        return response_text[:240]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/api/services/lessons/test_working_memory_capture.py -v`
Expected: 3 passed.

- [ ] **Step 5: Wire the capture into `_wrapper.py`**

Find the `FleetEvent("agent.completed", ...)` emit site in `api/functions/graphs/executors/agents/_wrapper.py`. Immediately after that emit, add a singleton call into the capture:

```python
        # Working memory capture — passive, never raises into the caller.
        try:
            from api.server.services.lessons.working_memory_capture import WorkingMemoryCapture
            from api.server.services.lessons.working_memory_store import Mem0WorkingMemoryStore
            WorkingMemoryCapture(store=Mem0WorkingMemoryStore()).on_agent_completed(
                workflow_id=workflow_id,
                agent_skill=skill_label or "unknown",
                response_text=str(result.text or ""),
                tool_calls=tool_calls_out,
            )
        except Exception:
            pass  # never break an agent session on working-memory write failure
```

(The exact local variable names — `workflow_id`, `skill_label`, `result`, `tool_calls_out` — should already be in scope at the FleetEvent emit site. Use the actual names from the file.)

- [ ] **Step 6: Run the full lessons suite to confirm no regression**

Run: `uv run pytest tests/api/services/lessons/ -v`
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add api/server/services/lessons/working_memory_capture.py tests/api/services/lessons/test_working_memory_capture.py api/functions/graphs/executors/agents/_wrapper.py
git commit -m "feat(lessons): capture working memory from agent.completed events"
```

---

## Task 14: Full test suite + final commit

- [ ] **Step 1: Run the full lessons package test suite**

Run: `uv run pytest tests/api/services/lessons/ -v`
Expected: all tests pass (Tasks 2, 3, 4, 5, 7 = 5+5+5+4+4 = 23 tests).

- [ ] **Step 2: Run mypy on the new package**

Run: `uv run mypy api/server/services/lessons/`
Expected: `Success: no issues found`.

- [ ] **Step 3: Run the full project test suite to confirm no regressions**

Run: `uv run pytest tests/api -x --tb=short`
Expected: all existing tests still pass, including the AGT governance suite and entity-graph tests (the Kuzu schema change is additive).

- [ ] **Step 4: Commit any final lint/format fixes**

If steps 2 or 3 surfaced issues, fix them in place and commit:

```bash
git add -p
git commit -m "chore(lessons): fix lint/mypy follow-ups"
```

---

## Definition of Done

- All tests in `tests/api/services/lessons/` pass.
- `scripts/lessons_smoke.py` runs cleanly end-to-end.
- The `Lesson` node and three new edge tables exist in the Kuzu schema, additively (no existing tables changed).
- `lesson.write` and `lesson.prune` appear in the compiled AGT policy bundle in `audit` enforcement.
- **`WorkingMemoryStore` exists, is Mem0-backed (scoped by `workflow_id`), and is populated automatically by `_wrapper.py` for every agent session via passive capture from existing OTEL/FleetEvent stream — no agent code changes.**
- **`WorkingNote` rows include `kind`, `body`, `agent_skill`, `workflow_id`, `captured_at`, `consumed_by_dream_pass` and can be queried by Plan 3.**
- The full existing test suite still passes — additive change only.
- Plan 2 (`domain-rubric-scorer`) and Plan 3 (`experimental-dream-pass`) can now be authored against this foundation.
