"""RunScorer — joins a workflow run's Kuzu decisions with a rubric + ground truth.

Plan deviation: uses EntityGraph.query() (the real API), not the plan's
.execute_cypher() which doesn't exist.
"""
from __future__ import annotations

from api.server.services.entity_graph import EntityGraph
from api.server.services.scoring.checks import (
    DecisionRecord,
    check_decision_matches_label,
    check_policy_compliance,
    check_rationale_present,
)
from api.server.services.scoring.ground_truth import HiringGroundTruth
from api.server.services.scoring.types import (
    CheckResult,
    Rubric,
    RubricCheck,
    RunScore,
)


class RunScorer:
    def __init__(self, *, graph: EntityGraph, ground_truth: HiringGroundTruth) -> None:
        self._graph = graph
        self._truth = ground_truth

    def score(self, *, workflow_id: str, rubric: Rubric) -> RunScore:
        decisions = self._load_decisions(workflow_id)
        results: list[CheckResult] = []
        for check in rubric.checks:
            results.append(self._dispatch(check, decisions))
        return RunScore(
            workflow_id=workflow_id,
            rubric_domain=rubric.domain,
            checks=tuple(results),
        )

    def _load_decisions(self, workflow_id: str) -> list[DecisionRecord]:
        rows = self._graph.query(
            """
            MATCH (d:Decision {workflow_id: $wf})-[:DECIDED_PERSON]->(p:Person)
            RETURN d.id AS id, d.verdict AS verdict, d.reason AS reason,
                   d.phase AS phase, p.id AS candidate_id
            """,
            {"wf": workflow_id},
        )
        return [
            DecisionRecord(
                decision_id=row["id"],
                candidate_id=row["candidate_id"],
                verdict=row["verdict"],
                reason=row["reason"] or "",
                phase=row["phase"],
            )
            for row in rows
        ]

    def _dispatch(
        self, check: RubricCheck, decisions: list[DecisionRecord]
    ) -> CheckResult:
        if check.kind == "decision_matches_label":
            return check_decision_matches_label(decisions, ground_truth=self._truth)
        if check.kind == "policy_compliance":
            return check_policy_compliance(
                decisions,
                forbid_blank_reason=bool(check.params.get("forbid_blank_reason", False)),
            )
        if check.kind == "rationale_present":
            return check_rationale_present(decisions)
        raise RuntimeError(
            f"unreachable: rubric loader should have rejected unknown kind '{check.kind}'"
        )
