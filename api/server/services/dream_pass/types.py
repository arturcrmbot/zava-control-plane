from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


ExperimentVerdict = Literal["promote", "reject", "inconclusive"]


@dataclass(frozen=True)
class LessonScope:
    domain: str
    persona_role: str | None = None
    market: str | None = None


@dataclass(frozen=True)
class LessonCandidate:
    id: str
    body: str
    scope: LessonScope
    proposed_by: str
    rationale: str = ""


@dataclass(frozen=True)
class LessonProvenance:
    proposed_by: str
    run_ids: tuple[str, ...]
    rubric_score_delta: float
    experiment_n: int
    promoted_at: datetime


@dataclass(frozen=True)
class Lesson:
    id: str
    body: str
    scope: LessonScope
    provenance: LessonProvenance
    status: str = "active"
    supersedes: str | None = None


@dataclass(frozen=True)
class DreamSkill:
    """Dream-pass skill metadata loaded from SKILL.md frontmatter."""

    domain: str
    version: str
    max_candidates_per_pass: int
    max_experiments_per_pass: int
    body: str


@dataclass(frozen=True)
class CorpusSplit:
    """One held-out evaluation slice plus the ids already burned."""

    held_out_ids: tuple[str, ...]
    already_used_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        overlap = set(self.held_out_ids) & set(self.already_used_ids)
        if overlap:
            raise ValueError(
                'held_out_ids and already_used_ids must be disjoint; '
                f'overlap={sorted(overlap)}'
            )


@dataclass(frozen=True)
class Experiment:
    """Result of one control-vs-treatment run for a candidate lesson."""

    id: str
    candidate_lesson_id: str
    control_score: float
    treatment_score: float
    n_samples: int
    run_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    workflow_ids: tuple[str, ...] = ()

    @property
    def delta(self) -> float:
        return self.treatment_score - self.control_score


@dataclass(frozen=True)
class DreamPassResult:
    """Final report for one dream pass execution."""

    dream_pass_id: str
    domain: str
    experiments: tuple[Experiment, ...]
    promoted_lesson_ids: tuple[str, ...]
    rejected_lesson_ids: tuple[str, ...]
    # Always () after the flagged→reject collapse (kept as zero-length tuple
    # for API back-compat with existing clients that destructure this field).
    flagged_lesson_ids: tuple[str, ...] = ()
