"""AppState exposes a dream-pass orchestrator + lesson / working-memory
singletons (orchestrator built lazily) so HTTP routes can read and the
orchestrator can write against the same in-memory instances."""
from datetime import datetime, timezone

from api.server.services.dream_pass.orchestrator import DreamPassOrchestrator
from api.server.services.lessons.store import InMemoryLessonStore
from api.server.services.lessons.working_memory_store import InMemoryWorkingMemoryStore
from api.server.services.lessons.types import (
    Lesson,
    LessonProvenance,
    LessonScope,
)


def test_app_state_exposes_dream_pass_orchestrator():
    from api.server.state import app_state
    assert isinstance(app_state.dream_pass_orchestrator, DreamPassOrchestrator)


def test_app_state_exposes_in_memory_lesson_store():
    from api.server.state import app_state
    assert isinstance(app_state.lesson_store, InMemoryLessonStore)


def test_app_state_exposes_in_memory_working_memory_store():
    from api.server.state import app_state
    assert isinstance(app_state.working_memory_store, InMemoryWorkingMemoryStore)


def test_dream_pass_orchestrator_is_memoised():
    """Lazy property must cache so producer/consumer share state."""
    from api.server.state import app_state
    assert app_state.dream_pass_orchestrator is app_state.dream_pass_orchestrator


def test_orchestrator_shares_lesson_store_with_app_state():
    """The orchestrator's governor writes to the same in-memory store the
    Task 6 memory routes read from."""
    from api.server.state import app_state

    lesson = Lesson(
        id="test-shared-store-01",
        body="Test lesson for shared-store verification.",
        scope=LessonScope(domain="hiring"),
        provenance=LessonProvenance(
            proposed_by="test",
            run_ids=(),
            rubric_score_delta=0.1,
            experiment_n=10,
            promoted_at=datetime.now(timezone.utc),
        ),
    )
    # Write via the orchestrator's governor (the producer path).
    app_state.dream_pass_orchestrator._governor.write(lesson)
    # Read via the public store (what Task 6 routes will use).
    found = list(
        app_state.lesson_store.search(
            query="", scope=LessonScope(domain="hiring"), top_k=100
        )
    )
    assert any(l.id == "test-shared-store-01" for l in found), (
        "lesson written by orchestrator.governor must be visible via app_state.lesson_store"
    )
