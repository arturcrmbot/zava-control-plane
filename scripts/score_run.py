"""Score one workflow run against a domain rubric.

Usage:
    uv run python scripts/score_run.py --workflow-id WF-xxx --rubric hiring
"""
from __future__ import annotations

import argparse
from pathlib import Path

from api.server.services.entity_graph import EntityGraph
from api.server.services.scoring import (
    HiringLabelsGroundTruth,
    RunScorer,
    load_rubric,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow-id", required=True)
    parser.add_argument("--rubric", required=True, help="rubric name, e.g. 'hiring'")
    parser.add_argument(
        "--kuzu-path",
        default="data/portal/entity_graph.kuzu",
        help="path to the Kuzu DB",
    )
    args = parser.parse_args()

    rubric_path = Path(f"data/rubrics/{args.rubric}.yaml")
    rubric = load_rubric(rubric_path)

    # The labels_csv path lives on the decision_matches_label check params.
    labels_csv = Path("data/synthetic/hiring/labels.csv")
    for check in rubric.checks:
        if check.kind == "decision_matches_label" and "labels_csv" in check.params:
            labels_csv = Path(check.params["labels_csv"])
            break

    truth = HiringLabelsGroundTruth(labels_csv=labels_csv)
    graph = EntityGraph(args.kuzu_path)
    try:
        scorer = RunScorer(graph=graph, ground_truth=truth)
        score = scorer.score(workflow_id=args.workflow_id, rubric=rubric)

        print(f"workflow:  {score.workflow_id}")
        print(f"domain:    {score.rubric_domain}")
        print(f"rollup:    {score.rollup(rubric):.4f}")
        print("checks:")
        for check in score.checks:
            marker = "PASS" if check.passed else "FAIL"
            print(f"  [{marker}] {check.name:30s} score={check.score:.3f}  {check.detail}")
    finally:
        graph.close()


if __name__ == "__main__":
    main()
