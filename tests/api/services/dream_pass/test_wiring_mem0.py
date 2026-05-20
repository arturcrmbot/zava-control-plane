from unittest.mock import MagicMock

from api.server.services.audit_logger import AuditLogger
from api.server.services.event_bus import EventBus
from api.server.services.lessons.mem0_store import Mem0LessonStore
from api.server.services.dream_pass.wiring import build_demo_orchestrator
from api.server.services.dream_pass.proposer import StubProposer

from tests.api.services.dream_pass._stub_runner import StubExperimentRunner


def test_factory_uses_mem0_when_provided():
    """Caller passes a Mem0LessonStore (with mocked Memory) - factory
    must bind THAT instance to the orchestrator's governor, not silently
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
        experiment_runner=StubExperimentRunner(),
    )
    # Governor's private store IS the Mem0LessonStore we passed in.
    assert orchestrator._governor._store is mem0_store
