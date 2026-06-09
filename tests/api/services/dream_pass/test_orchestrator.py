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


@pytest.mark.asyncio
async def test_ex_flagged_candidate_now_rejected_with_prefixed_reason(
    skill: DreamSkill,
) -> None:
    """Regression test for the flagged→reject collapse.

    Before: a policy 'flagged' verdict took a dedicated branch that called
    `persist_flagged_candidate` (writing Lesson(status='candidate') to the
    graph). After: 'flagged' is no longer a verdict — the policy returns
    'reject' with a `flagged_<reason>:` prefix, and the orchestrator takes
    the normal reject branch (no Lesson row, just an Experiment with
    verdict='reject'). The DREAM_LESSON_REJECTED bus event includes the
    reason so consumers can still distinguish historical flag categories.
    """
    partitioner = MagicMock()
    partitioner.next_split.return_value = MagicMock(held_out_ids=('C-001',))
    experiment_runner = MagicMock()
    experiment_runner.run = AsyncMock(
        return_value=Experiment(
            id='EXP-FLAGGED',
            candidate_lesson_id='L-FLAG',
            control_score=0.70,
            treatment_score=0.96,  # delta = 0.26, > the 0.20 implausible threshold
            n_samples=40,
        )
    )
    proposer = StubProposer(candidates=[('implausibly good lesson', 'r')])
    # Real policy decision the new code would produce.
    policy = MagicMock()
    policy.evaluate.return_value = MagicMock(
        verdict='reject',
        reason='flagged_implausible_delta: delta exceeds review threshold',
    )

    rejected_events: list[dict] = []

    class _StubBus:
        def emit(self, event):
            rejected_events.append(event.model_dump())

    persist_promoted_calls: list[object] = []

    orchestrator = DreamPassOrchestrator(
        proposer=proposer,
        partitioner=partitioner,
        experiment_runner=experiment_runner,
        policy=policy,
        list_persona_ids=lambda domain: ['C-001', 'C-002'],
        load_cvs=lambda ids: [{'candidate_id': cid} for cid in ids],
        load_recent_runs=lambda domain: [],
        rubric=MagicMock(min_samples=40),
        persist_promoted_lesson=persist_promoted_calls.append,
        bus=_StubBus(),
    )

    result = await orchestrator.run_pass(skill=skill, sample_size=1)

    # The candidate landed in rejected_lesson_ids, NOT flagged_lesson_ids.
    assert len(result.rejected_lesson_ids) == 1
    assert result.flagged_lesson_ids == ()
    # No Lesson row was persisted (no promote path taken).
    assert persist_promoted_calls == []
    # The DREAM_LESSON_REJECTED event carries the flagged_<reason> prefix
    # so SSE/UI consumers can still distinguish historical flag categories.
    rejected = [e for e in rejected_events if e["type"] == "dream.lesson.rejected"]
    assert len(rejected) == 1
    assert "flagged_implausible_delta" in rejected[0]["reason"]


@pytest.mark.asyncio
async def test_persist_flagged_candidate_kwarg_removed(skill: DreamSkill) -> None:
    """Constructor must not accept the removed `persist_flagged_candidate`
    kwarg anymore — locks the collapse so it can't silently regress."""
    with pytest.raises(TypeError):
        DreamPassOrchestrator(
            proposer=StubProposer(candidates=[]),
            partitioner=MagicMock(),
            experiment_runner=MagicMock(),
            policy=MagicMock(),
            list_persona_ids=lambda domain: [],
            load_cvs=lambda ids: [],
            load_recent_runs=lambda domain: [],
            rubric=MagicMock(min_samples=1),
            persist_flagged_candidate=lambda **kw: None,
        )
