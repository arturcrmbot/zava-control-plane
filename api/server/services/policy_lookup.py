"""Active-policy lookup for persona decision_policy blocks.

A 'policy' here is a Decision with phase='policy_set' that has not yet
expired (decided_at + attributes.expiry_days >= now). Personas call this
helper at gate-time to discover policies that should constrain the
current decision.

Phase 2 of autonomous-domain-insights v1.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from api.server.services.entity_graph import EntityGraph

# Mirror of api/server/services/entity_graph.py:_DECIDED_REL_BY_KIND.
# Kept inline (rather than imported) to keep this module decoupled from
# the graph module's private constants — a regression here is caught by
# test_unknown_scope_kind_returns_empty.
_DECIDED_REL_BY_KIND: dict[str, str] = {
    "Person": "DECIDED_PERSON",
    "Money": "DECIDED_MONEY",
    "Asset": "DECIDED_ASSET",
    "Organisation": "DECIDED_ORG",
    "Period": "DECIDED_PERIOD",
    "Place": "DECIDED_PLACE",
    "Brand": "DECIDED_BRAND",
    "Campaign": "DECIDED_CAMPAIGN",
    "Pitch": "DECIDED_PITCH",
    "MediaPlan": "DECIDED_MEDIAPLAN",
    "Subsidiary": "DECIDED_SUBSIDIARY",
}


def active_policies_for(
    graph: EntityGraph,
    *,
    scope_kind: str,
    scope_id: str,
    verdict: str | None = None,
) -> list[dict[str, Any]]:
    """Return active policy_set Decisions whose decided_on includes scope_id.

    Args:
        graph: live EntityGraph (typically app_state.entities).
        scope_kind: target node kind (Brand, Money, ...). Unknown kinds
            return ``[]`` rather than raising — keeps persona policies
            future-proof against new kinds.
        scope_id: target node id (e.g. "BRAND-aurora").
        verdict: optional filter (e.g. "freeze"). When None, returns all
            verdicts including non-policy ones — callers SHOULD pass a
            specific verdict to avoid false positives from approve/reject
            Decisions that happen to share the policy_set phase.

    Returns:
        list of dicts with keys: id, verdict, decided_at, persona_role,
        reason, attributes (parsed dict). Sorted by decided_at descending
        (newest first) so latest-wins semantics are explicit at the
        callsite.
    """
    decided_rel = _DECIDED_REL_BY_KIND.get(scope_kind)
    if decided_rel is None:
        return []

    cypher = f"""
    MATCH (d:Decision {{phase: 'policy_set'}})-[:{decided_rel}]->(t:{scope_kind} {{id: $id}})
    RETURN d.id AS id, d.verdict AS verdict, d.decided_at AS decided_at,
           d.persona_role AS persona_role, d.reason AS reason,
           d.attributes AS attributes
    """
    rows = graph.query(cypher, {"id": scope_id})
    now = datetime.utcnow()
    out: list[dict[str, Any]] = []
    for r in rows:
        if verdict is not None and r["verdict"] != verdict:
            continue
        attrs: dict[str, Any] = {}
        raw_attrs = r.get("attributes")
        if raw_attrs:
            try:
                parsed = json.loads(raw_attrs)
                if isinstance(parsed, dict):
                    attrs = parsed
            except (TypeError, ValueError):
                pass
        expiry_days = attrs.get("expiry_days")
        decided_at = r["decided_at"]
        if expiry_days is not None and isinstance(decided_at, datetime):
            try:
                if decided_at + timedelta(days=int(expiry_days)) < now:
                    continue
            except (TypeError, ValueError):
                pass
        out.append({
            "id": r["id"],
            "verdict": r["verdict"],
            "decided_at": decided_at,
            "persona_role": r["persona_role"],
            "reason": r["reason"],
            "attributes": attrs,
        })
    out.sort(key=lambda d: d["decided_at"] or datetime.min, reverse=True)
    return out
