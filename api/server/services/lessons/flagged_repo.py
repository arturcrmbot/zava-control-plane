"""Read-only repo for the dream-pass exception portal.

Joins flagged candidate Lessons (status='candidate') against their
triggering Experiment evidence so the operator UI can show the delta,
sample size, and pre/post scores in one place.
"""
from __future__ import annotations

from typing import Any

from api.server.services.entity_graph import EntityGraph


class FlaggedLessonRepo:
    def __init__(self, *, graph: EntityGraph) -> None:
        self._graph = graph

    def list_flagged(self, *, domain: str) -> list[dict[str, Any]]:
        rows = self._graph.query(
            """
            MATCH (l:Lesson {status: 'candidate', domain: $domain})
            OPTIONAL MATCH (e:Experiment)-[:EXPERIMENT_FOR_LESSON]->(l)
            RETURN l.id AS lesson_id,
                   l.body AS body,
                   l.proposed_by AS proposed_by,
                   l.prune_reason AS flag_reason,
                   l.rubric_score_delta AS delta,
                   l.experiment_n AS n,
                   l.promoted_at AS proposed_at,
                   e.id AS experiment_id,
                   e.control_score AS control_score,
                   e.treatment_score AS treatment_score,
                   e.delta AS exp_delta,
                   e.n_samples AS exp_n
            ORDER BY l.promoted_at DESC
            """,
            {"domain": domain},
        )
        out: list[dict[str, Any]] = []
        for r in rows:
            out.append({
                "lesson_id": r["lesson_id"],
                "body": r["body"],
                "proposed_by": r["proposed_by"],
                "flag_reason": r["flag_reason"],
                "delta": r["delta"],
                "n_samples": r["n"],
                "proposed_at": r["proposed_at"].isoformat() if r["proposed_at"] else None,
                "experiment": (
                    {
                        "id": r["experiment_id"],
                        "control_score": r["control_score"],
                        "treatment_score": r["treatment_score"],
                        "delta": r["exp_delta"],
                        "n_samples": r["exp_n"],
                    }
                    if r["experiment_id"]
                    else None
                ),
            })
        return out
