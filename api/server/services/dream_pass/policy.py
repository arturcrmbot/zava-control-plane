from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from api.server.services.dream_pass.types import Experiment, ExperimentVerdict, Lesson, LessonCandidate


@dataclass(frozen=True)
class PromotionDecision:
    verdict: ExperimentVerdict
    reason: str


class PromotionPolicy:
    """Pure dream-pass promotion policy evaluator."""

    def __init__(self, raw: dict[str, Any]) -> None:
        self._raw = raw

    @classmethod
    def from_file(cls, path: Path) -> 'PromotionPolicy':
        return cls(yaml.safe_load(path.read_text(encoding='utf-8')) or {})

    def evaluate(
        self,
        *,
        domain: str,
        candidate: LessonCandidate,
        experiment: Experiment,
        active_lessons: list[Lesson | str],
        promoted_this_pass: int,
    ) -> PromotionDecision:
        cfg = ((self._raw.get('domains') or {}).get(domain) or {})
        auto = cfg.get('auto_promote') or {}
        min_delta = float(auto.get('min_delta', 0.0))
        min_samples = int(auto.get('min_samples', 1))
        max_per_pass = int(auto.get('max_per_pass', 999999))
        reject_below = float((cfg.get('reject') or {}).get('when_delta_below', 0.0))

        if candidate.scope.domain != domain:
            return PromotionDecision('reject', 'flagged_scope_expansion: candidate domain differs from pass domain')
        if experiment.delta > 0.20:
            return PromotionDecision('reject', 'flagged_implausible_delta: delta exceeds review threshold')
        if _contradicts_active(candidate.body, active_lessons):
            return PromotionDecision('reject', 'flagged_contradicts_active: candidate duplicates or conflicts with an active lesson')
        if promoted_this_pass >= max_per_pass:
            return PromotionDecision('inconclusive', 'max_per_pass reached for this dream pass')
        if experiment.n_samples < min_samples:
            return PromotionDecision('inconclusive', 'sample size below min_samples threshold')
        if experiment.delta < reject_below:
            return PromotionDecision('reject', 'delta below rejection threshold')
        if experiment.delta >= min_delta:
            return PromotionDecision('promote', 'delta exceeds auto-promote threshold')
        return PromotionDecision('inconclusive', 'delta did not clear promotion threshold')


def _contradicts_active(candidate_body: str, active_lessons: list[Lesson | str]) -> bool:
    candidate_norm = _normalise(candidate_body)
    if not candidate_norm:
        return False
    active_bodies = [_lesson_body(lesson) for lesson in active_lessons]
    return any(_normalise(body) == candidate_norm for body in active_bodies if body)


def _lesson_body(lesson: Lesson | str) -> str:
    if isinstance(lesson, Lesson):
        return lesson.body
    return str(lesson)


def _normalise(text: str) -> str:
    return ' '.join((text or '').lower().split())
