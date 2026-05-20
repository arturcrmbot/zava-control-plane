from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.server.services.dream_pass.orchestrator import DreamPassOrchestrator
from api.server.services.dream_pass.proposer import StubProposer
from api.server.services.dream_pass.types import DreamSkill, Experiment


@pytest.fixture
def skill() -> DreamSkill:
    return DreamSkill(
        domain='hiring',
        version='1.0',
        max_candidates_per_pass=2,
        max_experiments_per_pass=2,
        body='x',
    )


@pytest.mark.asyncio
async def test_full_pass_promotes_winners_and_rejects_losers(skill: DreamSkill) -> None:
    partitioner = MagicMock()
    partitioner.next_split.return_value = MagicMock(held_out_ids=('C-001', 'C-002'))
    persisted: list[object] = []

    async def fake_run_experiment(*, experiment_id, candidate_lesson_id, candidate_body, cvs, active_lessons, rubric):
        if 'winner' in candidate_body:
            return Experiment(
                id=experiment_id,
                candidate_lesson_id=candidate_lesson_id,
                control_score=0.70,
                treatment_score=0.80,
                n_samples=40,
            )
        return Experiment(
            id=experiment_id,
            candidate_lesson_id=candidate_lesson_id,
            control_score=0.70,
            treatment_score=0.65,
            n_samples=40,
        )

    experiment_runner = MagicMock()
    experiment_runner.run = AsyncMock(side_effect=fake_run_experiment)
    proposer = StubProposer(candidates=[('winner lesson', 'good rationale'), ('loser lesson', 'poor rationale')])
    policy = MagicMock()
    policy.evaluate.side_effect = lambda **kwargs: (
        MagicMock(verdict='promote', reason='ok')
        if 'winner' in kwargs['candidate'].body
        else MagicMock(verdict='reject', reason='delta < 0')
    )

    orchestrator = DreamPassOrchestrator(
        proposer=proposer,
        partitioner=partitioner,
        experiment_runner=experiment_runner,
        policy=policy,
        list_persona_ids=lambda domain: ['C-001', 'C-002', 'C-003'],
        load_cvs=lambda ids: [{'candidate_id': candidate_id} for candidate_id in ids],
        load_recent_runs=lambda domain: [{'workflow_id': 'WF-RECENT-1'}],
        rubric=MagicMock(min_samples=40),
        persist_promoted_lesson=persisted.append,
    )

    result = await orchestrator.run_pass(skill=skill, sample_size=2)

    assert result.domain == 'hiring'
    assert len(result.experiments) == 2
    assert len(result.promoted_lesson_ids) == 1
    assert len(result.rejected_lesson_ids) == 1
    assert len(persisted) == 1
    written = persisted[0]
    assert written.body == 'winner lesson'
    assert written.provenance.rubric_score_delta == pytest.approx(0.10)
    assert written.provenance.experiment_n == 40


@pytest.mark.asyncio
async def test_skill_max_experiments_caps_loop(skill: DreamSkill) -> None:
    partitioner = MagicMock()
    partitioner.next_split.return_value = MagicMock(held_out_ids=('C-001',))
    experiment_runner = MagicMock()
    experiment_runner.run = AsyncMock(
        return_value=Experiment(
            id='EXP-X',
            candidate_lesson_id='L-X',
            control_score=0.7,
            treatment_score=0.72,
            n_samples=40,
        )
    )
    proposer = StubProposer(candidates=[('a', 'r'), ('b', 'r'), ('c', 'r')])
    policy = MagicMock()
    policy.evaluate.return_value = MagicMock(verdict='reject', reason='x')

    skill_capped = DreamSkill(
        domain='hiring',
        version='1.0',
        max_candidates_per_pass=3,
        max_experiments_per_pass=2,
        body='x',
    )

    orchestrator = DreamPassOrchestrator(
        proposer=proposer,
        partitioner=partitioner,
        experiment_runner=experiment_runner,
        policy=policy,
        list_persona_ids=lambda domain: ['C-001', 'C-002', 'C-003'],
        load_cvs=lambda ids: [{'candidate_id': candidate_id} for candidate_id in ids],
        load_recent_runs=lambda domain: [],
        rubric=MagicMock(min_samples=40),
    )
    result = await orchestrator.run_pass(skill=skill_capped, sample_size=1)

    assert len(result.experiments) == 2
