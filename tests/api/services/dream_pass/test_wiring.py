from unittest.mock import MagicMock

import pytest

from api.server.services.audit_logger import AuditLogger
from api.server.services.dream_pass.orchestrator import DreamPassOrchestrator
from api.server.services.dream_pass.proposer import StubProposer
from api.server.services.dream_pass.skill_loader import dream_skill_path, load_dream_skill
from api.server.services.dream_pass.wiring import _NoopProvenance, build_demo_orchestrator
from api.server.services.event_bus import EventBus


_TEST_CANDIDATES = [("test winner", "demo"), ("test loser", "demo")]


def test_noop_provenance_implements_every_governor_call():
    """LessonGovernor calls record / mark_pruned / record_candidate /
    fetch_candidate on its _provenance. The no-graph stub must answer
    all four without AttributeError, otherwise the demo path explodes
    the moment policy flips a verdict away from promote/reject."""
    prov = _NoopProvenance()
    assert prov.record(lesson=object()) is None
    assert prov.mark_pruned("id-1", reason="why") is None
    assert prov.record_candidate(
        candidate_id="c1", body="b", domain="d", persona_role="",
        market="", proposed_by="p", experiment_id="e", delta=0.0,
        n=1, flag_reason="dup",
    ) is None
    assert prov.fetch_candidate("c1") is None


def test_factory_returns_a_real_orchestrator():
    graph = MagicMock()
    orchestrator = build_demo_orchestrator(
        graph=graph, bus=EventBus(), audit=AuditLogger(),
        proposer=StubProposer(candidates=_TEST_CANDIDATES),
    )
    assert isinstance(orchestrator, DreamPassOrchestrator)


def test_factory_with_no_graph_still_works():
    orchestrator = build_demo_orchestrator(
        graph=None, bus=EventBus(), audit=AuditLogger(),
        proposer=StubProposer(candidates=_TEST_CANDIDATES),
    )
    assert isinstance(orchestrator, DreamPassOrchestrator)


def test_factory_default_proposer_falls_back_gracefully_when_unavailable():
    """No proposer kwarg → factory must build GHCPProposer OR fall back
    to StubProposer; either way the result is a valid orchestrator."""
    orchestrator = build_demo_orchestrator(
        graph=None, bus=EventBus(), audit=AuditLogger(),
    )
    assert isinstance(orchestrator, DreamPassOrchestrator)


async def test_factory_orchestrator_can_run_pass_end_to_end():
    """Build the orchestrator without a graph and run one full pass.
    Verifies the wiring is consistent (proposer + partitioner + stub
    runner + policy + governor + in-memory stores all line up)."""
    bus = EventBus()
    received: list[str] = []
    bus.on_any(lambda ev: received.append(ev.type))

    orchestrator = build_demo_orchestrator(
        graph=None, bus=bus, audit=AuditLogger(),
        proposer=StubProposer(candidates=_TEST_CANDIDATES),
    )
    skill = load_dream_skill(dream_skill_path("hiring"))
    result = await orchestrator.run_pass(skill=skill, sample_size=3)
    assert result.domain == "hiring"
    # Stub proposer returns 3 candidates; cap is whatever the SKILL.md sets.
    assert len(result.experiments) >= 1
    assert "dream.pass.started" in received
    assert "dream.pass.finished" in received
