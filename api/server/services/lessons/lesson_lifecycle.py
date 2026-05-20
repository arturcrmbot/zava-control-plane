"""Pure-logic lesson lifecycle transitions.

Lifecycle:
    candidate → shadow → active ⇄ demoted → retired

- candidate: proposer just emitted it. Not used at runtime.
- shadow: promoted by policy but not yet trusted. Used in N shadow
  invocations (silently included in prompt; outcome measured).
- active: trusted. Returned by /api/memory/lessons/recall and
  prepended to agent prompts.
- demoted: outcome metrics turned against it. NOT returned by recall.
  Stays in Mem0 for audit + manual re-evaluation.
- retired: unused for `retire_after_days`. Deleted from Mem0 (via
  governor.prune so ledger + provenance record the retirement).

Driven by LessonOutcomeMetrics; no I/O. The governor wraps this and
applies the transition through AGT + audit + Kuzu.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum


class LessonStatus(str, Enum):
    CANDIDATE = "candidate"
    SHADOW = "shadow"
    ACTIVE = "active"
    DEMOTED = "demoted"
    RETIRED = "retired"


@dataclass(frozen=True)
class LessonOutcomeMetrics:
    """Snapshot of a lesson's outcome signals at one point in time."""

    status: LessonStatus
    invocations: int
    hitl_override_count: int
    promoted_at: datetime
    last_used_at: datetime | None


def next_status(
    metrics: LessonOutcomeMetrics,
    *,
    shadow_invocations_required: int,
    max_override_rate: float,
    retire_after_days: int,
) -> LessonStatus:
    """Compute the next lifecycle status. Pure function; idempotent."""
    now = datetime.now(timezone.utc)
    s = metrics.status

    if metrics.last_used_at is not None:
        unused_for = now - metrics.last_used_at
        if unused_for > timedelta(days=retire_after_days) and s in (LessonStatus.ACTIVE, LessonStatus.SHADOW, LessonStatus.DEMOTED):
            return LessonStatus.RETIRED

    if s == LessonStatus.CANDIDATE:
        return LessonStatus.CANDIDATE

    if s == LessonStatus.SHADOW:
        if metrics.invocations >= shadow_invocations_required:
            if metrics.invocations > 0:
                rate = metrics.hitl_override_count / metrics.invocations
                if rate > max_override_rate:
                    return LessonStatus.DEMOTED
            return LessonStatus.ACTIVE
        return LessonStatus.SHADOW

    if s == LessonStatus.ACTIVE:
        if metrics.invocations > 0:
            rate = metrics.hitl_override_count / metrics.invocations
            if rate > max_override_rate:
                return LessonStatus.DEMOTED
        return LessonStatus.ACTIVE

    if s == LessonStatus.DEMOTED:
        return LessonStatus.DEMOTED

    return s
