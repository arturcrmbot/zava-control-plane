from unittest.mock import MagicMock

from api.server.services.audit_logger import AuditLogger
from api.server.services.dream_pass.orchestrator import DreamPassOrchestrator
from api.server.services.dream_pass.proposer import StubProposer
from api.server.services.dream_pass.skill_loader import dream_skill_path, load_dream_skill
from api.server.services.dream_pass.wiring import build_demo_orchestrator
from api.server.services.event_bus import EventBus

from tests.api.services.dream_pass._stub_runner import StubExperimentRunner


_TEST_CANDIDATES = [("test winner", "demo"), ("test loser", "demo")]


def test_factory_returns_a_real_orchestrator():
    graph = MagicMock()
    orchestrator = build_demo_orchestrator(
        graph=graph, bus=EventBus(), audit=AuditLogger(),
        proposer=StubProposer(candidates=_TEST_CANDIDATES),
        experiment_runner=StubExperimentRunner(),
    )
    assert isinstance(orchestrator, DreamPassOrchestrator)


def test_factory_with_no_graph_still_works():
    orchestrator = build_demo_orchestrator(
        graph=None, bus=EventBus(), audit=AuditLogger(),
        proposer=StubProposer(candidates=_TEST_CANDIDATES),
        experiment_runner=StubExperimentRunner(),
    )
    assert isinstance(orchestrator, DreamPassOrchestrator)


def test_factory_default_proposer_falls_back_gracefully_when_unavailable():
    orchestrator = build_demo_orchestrator(
        graph=None, bus=EventBus(), audit=AuditLogger(),
        experiment_runner=StubExperimentRunner(),
    )
    assert isinstance(orchestrator, DreamPassOrchestrator)


def test_factory_default_runner_is_real_experiment_runner():
    from api.server.services.dream_pass.experiment import ExperimentRunner
    orchestrator = build_demo_orchestrator(
        graph=None, bus=EventBus(), audit=AuditLogger(),
        proposer=StubProposer(candidates=_TEST_CANDIDATES),
    )
    runner = orchestrator._experiment_runner
    assert isinstance(runner, ExperimentRunner)


async def test_factory_orchestrator_can_run_pass_end_to_end():
    bus = EventBus()
    received: list[str] = []
    bus.on_any(lambda ev: received.append(ev.type))

    orchestrator = build_demo_orchestrator(
        graph=None, bus=bus, audit=AuditLogger(),
        proposer=StubProposer(candidates=_TEST_CANDIDATES),
        experiment_runner=StubExperimentRunner(),
    )
    skill = load_dream_skill(dream_skill_path("hiring"))
    result = await orchestrator.run_pass(skill=skill, sample_size=3)
    assert result.domain == "hiring"
    assert len(result.experiments) >= 1
    assert "dream.pass.started" in received
    assert "dream.pass.finished" in received
