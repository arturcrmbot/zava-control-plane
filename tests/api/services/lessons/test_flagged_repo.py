from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from api.server.services.entity_graph import EntityGraph
from api.server.services.lessons.flagged_repo import FlaggedLessonRepo


@pytest.fixture
def graph(tmp_path: Path):
    g = EntityGraph(str(tmp_path / "flagged.kuzu"))
    now = datetime.now(timezone.utc)
    g.query(
        """
        CREATE (:Lesson {id: 'L-FLAG-1', body: 'flagged hiring', domain: 'hiring',
                         persona_role: '', market: '', status: 'candidate',
                         proposed_by: 'dp:hiring', rubric_score_delta: 0.25,
                         experiment_n: 40, promoted_at: $now,
                         supersedes: '', prune_reason: 'implausible_delta'})
        """,
        {"now": now},
    )
    g.query(
        """
        CREATE (:Lesson {id: 'L-FLAG-2', body: 'flagged kyc', domain: 'vendor_kyc',
                         persona_role: '', market: '', status: 'candidate',
                         proposed_by: 'dp:kyc', rubric_score_delta: 0.06,
                         experiment_n: 40, promoted_at: $now,
                         supersedes: '', prune_reason: 'scope_expansion'})
        """,
        {"now": now},
    )
    g.query(
        """
        CREATE (:Lesson {id: 'L-ACTIVE', body: 'active', domain: 'hiring',
                         persona_role: '', market: '', status: 'active',
                         proposed_by: 'dp:hiring', rubric_score_delta: 0.08,
                         experiment_n: 40, promoted_at: $now,
                         supersedes: '', prune_reason: ''})
        """,
        {"now": now},
    )
    g.query(
        """
        CREATE (:Experiment {id: 'EXP-1', dream_pass_id: 'DP-1',
                             candidate_lesson_id: 'L-FLAG-1',
                             control_score: 0.70, treatment_score: 0.95,
                             delta: 0.25, n_samples: 40, verdict: 'flagged',
                             run_at: $now})
        """,
        {"now": now},
    )
    g.query(
        """
        MATCH (e:Experiment {id: 'EXP-1'}), (l:Lesson {id: 'L-FLAG-1'})
        CREATE (e)-[:EXPERIMENT_FOR_LESSON {recorded_at: $now}]->(l)
        """,
        {"now": now},
    )
    yield g
    g.close()


def test_list_flagged_for_domain(graph) -> None:
    repo = FlaggedLessonRepo(graph=graph)
    items = repo.list_flagged(domain="hiring")
    assert len(items) == 1
    assert items[0]["lesson_id"] == "L-FLAG-1"
    assert items[0]["flag_reason"] == "implausible_delta"
    assert items[0]["body"] == "flagged hiring"


def test_list_flagged_includes_experiment_evidence(graph) -> None:
    repo = FlaggedLessonRepo(graph=graph)
    items = repo.list_flagged(domain="hiring")
    exp = items[0]["experiment"]
    assert exp["id"] == "EXP-1"
    assert exp["control_score"] == pytest.approx(0.70)
    assert exp["treatment_score"] == pytest.approx(0.95)
    assert exp["delta"] == pytest.approx(0.25)
    assert exp["n_samples"] == 40


def test_list_flagged_returns_empty_for_unknown_domain(graph) -> None:
    repo = FlaggedLessonRepo(graph=graph)
    assert repo.list_flagged(domain="nope") == []


def test_list_flagged_excludes_active(graph) -> None:
    repo = FlaggedLessonRepo(graph=graph)
    items = repo.list_flagged(domain="hiring")
    assert all(i["lesson_id"] != "L-ACTIVE" for i in items)
