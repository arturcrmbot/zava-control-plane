from datetime import datetime, timedelta, timezone

from api.server.services.lessons.lesson_lifecycle import (
    LessonStatus,
    next_status,
    LessonOutcomeMetrics,
)


def test_candidate_with_enough_shadow_invocations_promotes_to_active():
    m = LessonOutcomeMetrics(
        status=LessonStatus.SHADOW,
        invocations=50,
        hitl_override_count=2,
        promoted_at=datetime.now(timezone.utc) - timedelta(hours=2),
        last_used_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    assert next_status(m, shadow_invocations_required=50,
                      max_override_rate=0.20, retire_after_days=30) == LessonStatus.ACTIVE


def test_active_with_high_override_rate_demotes():
    m = LessonOutcomeMetrics(
        status=LessonStatus.ACTIVE,
        invocations=40,
        hitl_override_count=20,
        promoted_at=datetime.now(timezone.utc) - timedelta(days=2),
        last_used_at=datetime.now(timezone.utc) - timedelta(minutes=10),
    )
    assert next_status(m, shadow_invocations_required=50,
                      max_override_rate=0.20, retire_after_days=30) == LessonStatus.DEMOTED


def test_unused_active_retires_after_window():
    m = LessonOutcomeMetrics(
        status=LessonStatus.ACTIVE,
        invocations=10,
        hitl_override_count=0,
        promoted_at=datetime.now(timezone.utc) - timedelta(days=60),
        last_used_at=datetime.now(timezone.utc) - timedelta(days=40),
    )
    assert next_status(m, shadow_invocations_required=50,
                      max_override_rate=0.20, retire_after_days=30) == LessonStatus.RETIRED


def test_demoted_with_recent_use_does_not_re_promote():
    m = LessonOutcomeMetrics(
        status=LessonStatus.DEMOTED,
        invocations=80,
        hitl_override_count=4,
        promoted_at=datetime.now(timezone.utc) - timedelta(days=1),
        last_used_at=datetime.now(timezone.utc) - timedelta(minutes=10),
    )
    assert next_status(m, shadow_invocations_required=50,
                      max_override_rate=0.20, retire_after_days=30) == LessonStatus.DEMOTED
