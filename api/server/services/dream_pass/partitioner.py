from __future__ import annotations

from datetime import datetime, timezone

from api.server.services.dream_pass.types import CorpusSplit
from api.server.services.entity_graph import EntityGraph


class CorpusPartitioner:
    """Rotate through unseen synthetic personas and track burns in Kuzu."""

    def __init__(self, *, graph: EntityGraph, domain: str) -> None:
        self._graph = graph
        self._domain = domain

    def next_split(self, *, available: list[str], n: int) -> CorpusSplit:
        used = self._used_ids()
        unseen = [persona_id for persona_id in available if persona_id not in used]
        if len(unseen) < n:
            raise ValueError(
                f'insufficient unseen personas: need {n}, have {len(unseen)} '
                f'({len(used)} already used in domain={self._domain})'
            )
        return CorpusSplit(
            held_out_ids=tuple(unseen[:n]),
            already_used_ids=tuple(sorted(used)),
        )

    def mark_used(
        self,
        *,
        experiment_id: str,
        persona_ids: tuple[str, ...],
        arm: str,
    ) -> None:
        now = datetime.now(timezone.utc)
        self._graph.query(
            """
            MERGE (e:Experiment {id: $eid})
            SET e.dream_pass_id = '',
                e.candidate_lesson_id = '',
                e.control_score = 0.0,
                e.treatment_score = 0.0,
                e.delta = 0.0,
                e.n_samples = 0,
                e.verdict = 'inconclusive',
                e.run_at = $now
            """,
            {'eid': experiment_id, 'now': now},
        )
        for persona_id in persona_ids:
            self._graph.query(
                """
                MERGE (p:Person {id: $pid})
                SET p.name = $pid,
                    p.role = 'synthetic'
                """,
                {'pid': persona_id},
            )
            self._graph.query(
                """
                MATCH (e:Experiment {id: $eid}), (p:Person {id: $pid})
                CREATE (e)-[:EXPERIMENT_USED_PERSONA {arm: $arm, recorded_at: $now}]->(p)
                """,
                {
                    'eid': experiment_id,
                    'pid': persona_id,
                    'arm': arm,
                    'now': now,
                },
            )

    def _used_ids(self) -> set[str]:
        rows = self._graph.query(
            """
            MATCH (e:Experiment)-[:EXPERIMENT_USED_PERSONA]->(p:Person)
            RETURN DISTINCT p.id AS pid
            """
        )
        return {str(row['pid']) for row in rows if row.get('pid')}
