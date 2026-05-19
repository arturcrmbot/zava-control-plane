from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from api.server.services.lessons.types import (
    Lesson,
    LessonProvenance,
    LessonScope,
)


@pytest.fixture
def make_lesson():
    def _make(
        body: str = "vendors from agency X often miss reference checks",
        domain: str = "hiring",
        persona_role: str | None = None,
        delta: float = 0.07,
        n: int = 40,
    ) -> Lesson:
        return Lesson(
            id=str(uuid.uuid4()),
            body=body,
            scope=LessonScope(domain=domain, persona_role=persona_role),
            provenance=LessonProvenance(
                proposed_by="dream-pass:hiring:test",
                run_ids=("WF-001", "WF-002"),
                rubric_score_delta=delta,
                experiment_n=n,
                promoted_at=datetime.now(timezone.utc),
            ),
        )
    return _make
