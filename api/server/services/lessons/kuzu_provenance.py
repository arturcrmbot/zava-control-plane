"""Kuzu writes for the Lesson provenance subgraph.

Stores the *structured* side of a lesson (provenance, scope, links to
runs). The free-text body lives in the LessonStore (Mem0); both are
joined by the lesson id.
"""
from __future__ import annotations

from datetime import datetime, timezone

from api.server.services.entity_graph import EntityGraph
from api.server.services.lessons.types import Lesson


class KuzuLessonProvenance:
    def __init__(self, graph: EntityGraph) -> None:
        self._graph = graph

    def record(self, lesson: Lesson) -> None:
        self._graph.query(
            """
            MERGE (l:Lesson {id: $id})
            SET l.body = $body,
                l.domain = $domain,
                l.persona_role = $persona_role,
                l.market = $market,
                l.status = $status,
                l.proposed_by = $proposed_by,
                l.rubric_score_delta = $delta,
                l.experiment_n = $n,
                l.promoted_at = $promoted_at,
                l.supersedes = $supersedes
            """,
            {
                "id": lesson.id,
                "body": lesson.body,
                "domain": lesson.scope.domain,
                "persona_role": lesson.scope.persona_role or "",
                "market": lesson.scope.market or "",
                "status": lesson.status,
                "proposed_by": lesson.provenance.proposed_by,
                "delta": lesson.provenance.rubric_score_delta,
                "n": lesson.provenance.experiment_n,
                "promoted_at": lesson.provenance.promoted_at,
                "supersedes": lesson.supersedes or "",
            },
        )
        for run_id in lesson.provenance.run_ids:
            self._graph.query(
                """
                MATCH (l:Lesson {id: $lesson_id}), (w:Workflow {id: $run_id})
                CREATE (l)-[:LESSON_FROM_RUN {recorded_at: $now}]->(w)
                """,
                {
                    "lesson_id": lesson.id,
                    "run_id": run_id,
                    "now": datetime.now(timezone.utc),
                },
            )
        if lesson.supersedes:
            self._graph.query(
                """
                MATCH (l:Lesson {id: $new}), (prev:Lesson {id: $prev})
                CREATE (l)-[:LESSON_SUPERSEDES {recorded_at: $now}]->(prev)
                """,
                {
                    "new": lesson.id,
                    "prev": lesson.supersedes,
                    "now": datetime.now(timezone.utc),
                },
            )

    def mark_pruned(self, lesson_id: str, *, reason: str) -> None:
        self._graph.query(
            """
            MATCH (l:Lesson {id: $id})
            SET l.status = 'pruned', l.prune_reason = $reason
            """,
            {"id": lesson_id, "reason": reason},
        )
