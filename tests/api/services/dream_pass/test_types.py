from __future__ import annotations

import pytest

from api.server.services.dream_pass.types import CorpusSplit, DreamSkill, Experiment, ExperimentVerdict


def test_dream_skill_minimal() -> None:
    skill = DreamSkill(
        domain='hiring',
        version='1.0',
        max_candidates_per_pass=3,
        max_experiments_per_pass=9,
        body='Look for recurring rejection patterns.',
    )
    assert skill.domain == 'hiring'
    assert skill.max_candidates_per_pass == 3


def test_corpus_split_disjoint() -> None:
    split = CorpusSplit(
        held_out_ids=('C-001', 'C-002', 'C-003'),
        already_used_ids=('C-100', 'C-101'),
    )
    assert set(split.held_out_ids).isdisjoint(set(split.already_used_ids))


def test_corpus_split_rejects_overlap() -> None:
    with pytest.raises(ValueError):
        CorpusSplit(held_out_ids=('C-1',), already_used_ids=('C-1',))


def test_experiment_delta() -> None:
    experiment = Experiment(
        id='EXP-1',
        candidate_lesson_id='L-1',
        control_score=0.70,
        treatment_score=0.80,
        n_samples=40,
    )
    assert experiment.delta == pytest.approx(0.10)


def test_experiment_verdict_values() -> None:
    valid: ExperimentVerdict
    valid = 'promote'
    valid = 'reject'
    valid = 'inconclusive'
    assert valid == 'inconclusive'
