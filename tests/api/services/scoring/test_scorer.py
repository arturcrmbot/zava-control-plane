from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent

import pytest

from api.server.services.entity_graph import EntityGraph
from api.server.services.scoring.ground_truth import HiringLabelsGroundTruth
from api.server.services.scoring.rubric_loader import load_rubric
from api.server.services.scoring.scorer import RunScorer


@pytest.fixture
def graph_with_run(tmp_path: Path):
    g = EntityGraph(str(tmp_path / "scorer.kuzu"))
    g.query("CREATE (:Workflow {id: 'WF-1', workflow_type: 'hiring', status: 'complete'})")
    g.query("CREATE (:Person {id: 'C-001', name: 'Alice', role: 'engineer'})")
    g.query("CREATE (:Person {id: 'C-002', name: 'Bob', role: 'engineer'})")
    g.query(
        """
        CREATE (:Decision {id: 'D-1', workflow_id: 'WF-1', phase: 'arbitrate',
                           persona_role: 'recruiter', verdict: 'approve',
                           reason: 'level match'})
        """
    )
    g.query(
        """
        CREATE (:Decision {id: 'D-2', workflow_id: 'WF-1', phase: 'arbitrate',
                           persona_role: 'recruiter', verdict: 'reject',
                           reason: ''})
        """
    )
    now = datetime.now(timezone.utc)
    g.query(
        """
        MATCH (d:Decision {id: 'D-1'}), (p:Person {id: 'C-001'})
        CREATE (d)-[:DECIDED_PERSON {decided_at: $now}]->(p)
        """,
        {"now": now},
    )
    g.query(
        """
        MATCH (d:Decision {id: 'D-2'}), (p:Person {id: 'C-002'})
        CREATE (d)-[:DECIDED_PERSON {decided_at: $now}]->(p)
        """,
        {"now": now},
    )
    yield g
    g.close()


@pytest.fixture
def rubric_path(tmp_path: Path) -> Path:
    p = tmp_path / "rubric.yaml"
    p.write_text(dedent("""
        domain: hiring
        promotion_threshold: 0.05
        min_samples: 20
        checks:
          - name: decision_matches_label
            kind: decision_matches_label
            weight: 2.0
            params:
              labels_csv: REPLACED
          - name: policy_compliance
            kind: policy_compliance
            weight: 1.0
            params:
              forbid_blank_reason: true
          - name: rationale_present
            kind: rationale_present
            weight: 1.0
    """))
    return p


def test_score_run_against_rubric(
    graph_with_run: EntityGraph, rubric_path: Path, fake_labels_csv: Path
) -> None:
    rubric_path.write_text(rubric_path.read_text().replace("REPLACED", str(fake_labels_csv)))
    rubric = load_rubric(rubric_path)
    truth = HiringLabelsGroundTruth(labels_csv=fake_labels_csv)

    scorer = RunScorer(graph=graph_with_run, ground_truth=truth)
    score = scorer.score(workflow_id="WF-1", rubric=rubric)

    assert score.workflow_id == "WF-1"
    assert score.rubric_domain == "hiring"
    # D-1 approve/C-001 (expected approve) ✓; D-2 reject/C-002 (expected reject) ✓.
    # decision_matches_label = 2/2 = 1.0
    # policy_compliance (forbid_blank_reason): D-2 blank → 1/2 = 0.5
    # rationale_present: D-2 blank → 1/2 = 0.5
    # Normalised weights: 0.5, 0.25, 0.25
    # Rollup: 0.5*1.0 + 0.25*0.5 + 0.25*0.5 = 0.75
    rolled = score.rollup(rubric)
    assert rolled == pytest.approx(0.75)


def test_unknown_workflow_returns_zero_score(
    graph_with_run: EntityGraph, rubric_path: Path, fake_labels_csv: Path
) -> None:
    rubric_path.write_text(rubric_path.read_text().replace("REPLACED", str(fake_labels_csv)))
    rubric = load_rubric(rubric_path)
    truth = HiringLabelsGroundTruth(labels_csv=fake_labels_csv)
    scorer = RunScorer(graph=graph_with_run, ground_truth=truth)

    score = scorer.score(workflow_id="WF-MISSING", rubric=rubric)

    assert score.workflow_id == "WF-MISSING"
    assert score.rollup(rubric) == 0.0
