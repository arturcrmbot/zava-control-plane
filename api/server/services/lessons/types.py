"""Value types for the lesson store."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Optional


@dataclass(frozen=True)
class LessonScope:
    """Scope of a lesson: which queries should be able to see it.

    Matching is asymmetric: a lesson scope matches a query scope iff every
    field set on the lesson is either None or equal to the corresponding
    query field. A None field on the lesson means "any". A None field on
    the query means "the query did not narrow on that dimension".
    """
    domain: str
    persona_role: Optional[str] = None
    market: Optional[str] = None

    def matches(self, query: "LessonScope") -> bool:
        if self.domain != query.domain:
            return False
        if self.persona_role is not None and self.persona_role != query.persona_role:
            return False
        if self.market is not None and self.market != query.market:
            return False
        return True


@dataclass(frozen=True)
class LessonProvenance:
    """Where a lesson came from. Required on every active lesson."""
    proposed_by: str
    run_ids: tuple[str, ...]
    rubric_score_delta: float
    experiment_n: int
    promoted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class Lesson:
    """An active lesson, readable by agents."""
    id: str
    body: str
    scope: LessonScope
    provenance: LessonProvenance
    status: Literal["candidate", "active", "superseded", "pruned"] = "active"
    supersedes: Optional[str] = None


@dataclass(frozen=True)
class LessonCandidate:
    """A proposed but not-yet-promoted lesson."""
    id: str
    body: str
    scope: LessonScope
    proposed_by: str
    rationale: str
