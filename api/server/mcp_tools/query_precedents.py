"""query_precedents MCP tool — Phase 4 IP3 (TASK-014).

Read-only Cypher fetch of recent ``Decision`` nodes for a given persona
+ entity. Loads a per-``(workflow_type, phase)`` Cypher template from
``api/server/services/precedent_queries/<workflow_type>_<phase>.cypher``
when present; otherwise falls back to a generic decision-by-entity
query. Same write-verb deny-list as ``find_entities`` (SEC-006).

Resolves DEC-OQ1 (precedent retrieval = registered tool call, not
inline Cypher in personae).
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from api.server.services.entity_graph import DECIDED_REL_NAMES, EntityGraph


log = logging.getLogger(__name__)


_WRITE_VERBS = ("CREATE", "MERGE", "DELETE", "DETACH", "SET", "REMOVE", "DROP", "CALL")
_DENY_PATTERN = re.compile(
    r"\b(" + "|".join(_WRITE_VERBS) + r")\b", re.IGNORECASE
)

_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "services" / "precedent_queries"

# Comma-separated cypher list literal of every DECIDED_<KIND> rel-table the
# writer may emit (sourced from entity_graph.DECIDED_REL_NAMES so the reader
# stays in sync as new shards are added). Used by :data:`_GENERIC_QUERY` to
# match decisions across all sharded rel tables via ``label(r) IN [...]``
# rather than a hard-coded ``[:DECIDED_ON]`` (which post-Phase-1.5 only ever
# matches an empty backward-compat table).
_DECIDED_REL_LIST = ", ".join(f"'{name}'" for name in DECIDED_REL_NAMES)


def _generic_query(limit: int) -> str:
    """Build the generic precedent Cypher with ``limit`` inlined.

    Kuzu 0.6.1 does not accept parameterised ``LIMIT`` (parser rejects
    ``LIMIT $limit``), so we inline a validated int literal.

    The rel pattern is label-less + filtered by ``label(r) IN [...]``
    rather than ``[:DECIDED_ON]`` so every Decision→target shard
    (DECIDED_PERSON, DECIDED_MONEY, etc.) is matched. See PR sweep notes
    in ``plan/refactor-repo-coherence-remediation-1.md`` (a1).
    """
    return (
        "MATCH (d:Decision)-[r]->(e {id: $entity_id}) "
        "WHERE d.persona_role = $persona_role "
        f"AND label(r) IN [{_DECIDED_REL_LIST}] "
        f"RETURN d ORDER BY d.decided_at DESC LIMIT {int(limit)}"
    )


def _load_template(
    workflow_type: str | None, phase: str | None, limit: int
) -> str:
    if not workflow_type or not phase:
        return _generic_query(limit)
    candidate = _TEMPLATE_DIR / f"{workflow_type}_{phase}.cypher"
    if not candidate.is_file():
        return _generic_query(limit)
    text = candidate.read_text(encoding="utf-8")
    m = _DENY_PATTERN.search(text)
    if m:
        raise ValueError(
            f"query_precedents: read-only — write/DDL keyword not permitted "
            f"in {candidate.name} ({m.group(1).upper()})"
        )
    return text


def make_query_precedents_tool(graph: EntityGraph):
    """Build a ``query_precedents(persona_role, entity_id, limit=10, *,
    workflow_type=None, phase=None)`` callable bound to ``graph``."""

    def query_precedents(
        persona_role: str,
        entity_id: str,
        limit: int = 10,
        *,
        workflow_type: str | None = None,
        phase: str | None = None,
        cite_from_decision_id: str | None = None,
    ) -> list[dict[str, Any]]:
        limit_int = int(limit)
        cypher = _load_template(workflow_type, phase, limit_int)
        # ``limit`` is inlined into the cypher (Kuzu 0.6.1 rejects
        # ``LIMIT $limit``), so it must NOT be passed in the params dict —
        # Kuzu also rejects an unused-but-declared parameter.
        rows = graph.query(
            cypher,
            {
                "persona_role": persona_role,
                "entity_id": entity_id,
            },
        )

        # PRECEDENT_OF: when a caller passes ``cite_from_decision_id``, the
        # citing Decision is asserting that each returned row is a
        # precedent it considered. We write one Decision-[:PRECEDENT_OF]->
        # Decision edge per row. Failures are logged + swallowed so a
        # broken edge can't mask the actual precedent payload from the
        # caller. Default ``None`` → no-op (preserves existing callers).
        # The writer exists today; rows will only routinely land once the
        # i1 precedent-influenced persona policy starts passing the kwarg.
        if cite_from_decision_id is not None:
            for row in rows:
                decision = row.get("d") if isinstance(row, dict) else None
                target_id: str | None = None
                if isinstance(decision, dict):
                    target_id = decision.get("id")
                if not target_id:
                    continue
                try:
                    graph.link(cite_from_decision_id, "PRECEDENT_OF", target_id)
                except Exception:
                    log.warning(
                        "query_precedents: PRECEDENT_OF link failed "
                        "(from=%s to=%s)",
                        cite_from_decision_id, target_id,
                        exc_info=True,
                    )

        return rows

    return query_precedents
