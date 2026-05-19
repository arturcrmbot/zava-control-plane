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

    # ------------------------------------------------------------------
    # D1 exception portal: candidate (status='candidate') persistence.
    # ------------------------------------------------------------------

    def record_candidate(
        self,
        *,
        candidate_id: str,
        body: str,
        domain: str,
        persona_role: str,
        market: str,
        proposed_by: str,
        experiment_id: str,
        delta: float,
        n: int,
        flag_reason: str,
    ) -> None:
        now = datetime.now(timezone.utc)
        self._graph.query(
            """
            MERGE (l:Lesson {id: $id})
            SET l.body = $body,
                l.domain = $domain,
                l.persona_role = $persona_role,
                l.market = $market,
                l.status = 'candidate',
                l.proposed_by = $proposed_by,
                l.rubric_score_delta = $delta,
                l.experiment_n = $n,
                l.promoted_at = $now,
                l.supersedes = '',
                l.prune_reason = $flag_reason
            """,
            {
                "id": candidate_id,
                "body": body,
                "domain": domain,
                "persona_role": persona_role,
                "market": market,
                "proposed_by": proposed_by,
                "delta": delta,
                "n": n,
                "flag_reason": flag_reason,
                "now": now,
            },
        )
        self._graph.query(
            """
            MERGE (e:Experiment {id: $eid})
            WITH e
            MATCH (l:Lesson {id: $lid})
            CREATE (e)-[:EXPERIMENT_FOR_LESSON {recorded_at: $now}]->(l)
            """,
            {"eid": experiment_id, "lid": candidate_id, "now": now},
        )

    def fetch_candidate(self, lesson_id: str):
        """Return a Lesson (status='candidate') hydrated from Kuzu, or None."""
        from api.server.services.lessons.types import (
            Lesson,
            LessonProvenance,
            LessonScope,
        )
        rows = self._graph.query(
            """
            MATCH (l:Lesson {id: $id, status: 'candidate'})
            RETURN l.body AS body, l.domain AS domain,
                   l.persona_role AS persona_role, l.market AS market,
                   l.proposed_by AS proposed_by,
                   l.rubric_score_delta AS delta, l.experiment_n AS n,
                   l.promoted_at AS promoted_at,
                   l.prune_reason AS flag_reason
            """,
            {"id": lesson_id},
        )
        if not rows:
            return None
        r = rows[0]
        return Lesson(
            id=lesson_id,
            body=r["body"],
            scope=LessonScope(
                domain=r["domain"],
                persona_role=r["persona_role"] or None,
                market=r["market"] or None,
            ),
            provenance=LessonProvenance(
                proposed_by=r["proposed_by"],
                run_ids=(),
                rubric_score_delta=r["delta"],
                experiment_n=r["n"],
                promoted_at=r["promoted_at"],
            ),
            status="candidate",
        )

    def list_flagged(self, *, limit: int = 50) -> list[dict]:
        """Return flagged candidates (status='candidate') with experiment evidence."""
        rows = self._graph.query(
            """
            MATCH (l:Lesson {status: 'candidate'})
            OPTIONAL MATCH (e:Experiment)-[:EXPERIMENT_FOR_LESSON]->(l)
            RETURN l.id AS lesson_id, l.body AS body, l.domain AS domain,
                   l.persona_role AS persona_role, l.market AS market,
                   l.proposed_by AS proposed_by,
                   l.rubric_score_delta AS delta, l.experiment_n AS n,
                   l.promoted_at AS flagged_at,
                   l.prune_reason AS flag_reason,
                   e.id AS experiment_id
            ORDER BY l.promoted_at DESC
            LIMIT $limit
            """,
            {"limit": limit},
        )
        return rows
