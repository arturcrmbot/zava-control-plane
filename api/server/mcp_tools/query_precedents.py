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

import re
from pathlib import Path
from typing import Any

from api.server.services.entity_graph import EntityGraph


_WRITE_VERBS = ("CREATE", "MERGE", "DELETE", "DETACH", "SET", "REMOVE", "DROP", "CALL")
_DENY_PATTERN = re.compile(
    r"\b(" + "|".join(_WRITE_VERBS) + r")\b", re.IGNORECASE
)

_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "services" / "precedent_queries"

_GENERIC_QUERY = (
    "MATCH (d:Decision)-[:DECIDED_ON]->(e {id: $entity_id}) "
    "WHERE d.persona_role = $persona_role "
    "RETURN d ORDER BY d.decided_at DESC LIMIT $limit"
)


def _load_template(workflow_type: str | None, phase: str | None) -> str:
    if not workflow_type or not phase:
        return _GENERIC_QUERY
    candidate = _TEMPLATE_DIR / f"{workflow_type}_{phase}.cypher"
    if not candidate.is_file():
        return _GENERIC_QUERY
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
    ) -> list[dict[str, Any]]:
        cypher = _load_template(workflow_type, phase)
        return graph.query(
            cypher,
            {
                "persona_role": persona_role,
                "entity_id": entity_id,
                "limit": int(limit),
            },
        )

    return query_precedents
