from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.shared.dream_events import (
    DREAM_PASS_STARTED, DREAM_PROPOSAL_GENERATED, DREAM_EXPERIMENT_SCORED,
    DREAM_LESSON_PROMOTED, DREAM_LESSON_REJECTED, DREAM_PASS_FINISHED,
)
from api.shared.events import FleetEvent
from api.server.services.event_bus import EventBus
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
