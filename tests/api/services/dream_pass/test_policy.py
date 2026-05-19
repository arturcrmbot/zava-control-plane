from __future__ import annotations

from pathlib import Path

import pytest

from api.server.services.dream_pass.policy import PromotionPolicy
from api.server.services.dream_pass.types import Experiment
from api.server.services.lessons.types import LessonCandidate, LessonScope


@pytest.fixture
def policy() -> PromotionPolicy:
    return PromotionPolicy.from_file(Path('data/policies/dream-pass.policy.yaml'))


def _candidate(scope_persona: str | None = None) -> LessonCandidate:
    return LessonCandidate(
        id='L-1',
        body='x',
        scope=LessonScope(domain='hiring', persona_role=scope_persona),
        proposed_by='dream-pass:hiring',
        rationale='r',
    )


def _experiment(delta: float, n: int = 40) -> Experiment:
    return Experiment(
        id='EXP-1',
        candidate_lesson_id='L-1',
        control_score=0.7,
        treatment_score=0.7 + delta,
        n_samples=n,
    )


def test_promote_when_delta_above_threshold(policy: PromotionPolicy) -> None:
    decision = policy.evaluate(
        domain='hiring',
        candidate=_candidate(),
        experiment=_experiment(delta=0.07),
        active_lessons=[],
        promoted_this_pass=0,
    )
    assert decision.verdict == 'promote'


def test_reject_when_delta_negative(policy: PromotionPolicy) -> None:
    decision = policy.evaluate(
        domain='hiring',
        candidate=_candidate(),
        experiment=_experiment(delta=-0.05),
        active_lessons=[],
        promoted_this_pass=0,
    )
    assert decision.verdict == 'reject'


def test_inconclusive_when_n_too_small(policy: PromotionPolicy) -> None:
    decision = policy.evaluate(
        domain='hiring',
        candidate=_candidate(),
        experiment=_experiment(delta=0.07, n=10),
        active_lessons=[],
        promoted_this_pass=0,
    )
    assert decision.verdict == 'inconclusive'


def test_flag_when_implausible_delta(policy: PromotionPolicy) -> None:
    decision = policy.evaluate(
        domain='hiring',
        candidate=_candidate(),
        experiment=_experiment(delta=0.25),
        active_lessons=[],
        promoted_this_pass=0,
    )
    assert decision.verdict == 'flagged'
    assert 'implausible_delta' in decision.reason


def test_inconclusive_when_max_per_pass_reached(policy: PromotionPolicy) -> None:
    decision = policy.evaluate(
        domain='hiring',
        candidate=_candidate(),
        experiment=_experiment(delta=0.07),
        active_lessons=[],
        promoted_this_pass=3,
    )
    assert decision.verdict == 'inconclusive'
    assert 'max_per_pass' in decision.reason
