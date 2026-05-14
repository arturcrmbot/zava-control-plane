"""Named, parametrised Cypher query templates for ``find_entities``.

Replaces the free-form ``cypher_pattern`` MCP surface (previously gated
only by a regex deny-list — bypassable). Each template:

* Has a fixed Cypher shape — no caller-supplied query text reaches Kuzu.
* Declares its allowed parameters and the validation each one passes
  through. Opaque values flow through ``$param`` bindings; identifier-
  shaped inputs (``kind``, ``rel``, ``attr_key``) are whitelisted /
  regex-validated and interpolated with backtick-quoted column names so
  reserved words remain legal.
* Inlines ``LIMIT`` as a validated int literal because Kuzu 0.6.1 rejects
  parameter substitution inside ``LIMIT``.

Mirrors the now-shipped ``query_precedents`` template-file pattern (see
``api/server/services/precedent_queries/`` / ``query_precedents.py``)
but keeps the templates in code so each one carries its own param
validator alongside the Cypher.

Plan: ``plan/refactor-repo-coherence-remediation-1.md`` — c2.
"""
from __future__ import annotations

from typing import Any, Callable

from api.server.services.entity_graph import (
    DECIDED_REL_NAMES,
    _VALID_ATTR_KEY,
    _VALID_KINDS,
    _VALID_RELS,
)


# ---------------------------------------------------------------------------
# Param validators
# ---------------------------------------------------------------------------


def _check_kind(value: Any) -> str:
    if not isinstance(value, str) or value not in _VALID_KINDS:
        raise ValueError(
            f"invalid kind: {value!r} (expected one of {sorted(_VALID_KINDS)})"
        )
    return value


def _check_rel(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError(f"invalid rel: {value!r} (must be string)")
    upper = value.upper()
    if upper not in _VALID_RELS:
        raise ValueError(
            f"invalid rel: {value!r} (expected one of {sorted(_VALID_RELS)})"
        )
    return upper


def _check_attr_key(value: Any) -> str:
    if not isinstance(value, str) or not _VALID_ATTR_KEY.match(value):
        raise ValueError(
            f"invalid attr_key: {value!r} "
            f"(must match {_VALID_ATTR_KEY.pattern})"
        )
    return value


def _check_limit(value: Any, *, default: int = 100, maximum: int = 1000) -> int:
    if value is None:
        return default
    try:
        out = int(value)
    except (TypeError, ValueError) as ex:
        raise ValueError(f"invalid limit: {value!r}") from ex
    if out < 1 or out > maximum:
        raise ValueError(f"limit must be in 1..{maximum}, got {out}")
    return out


def _check_nonempty_str(name: str) -> Callable[[Any], str]:
    def _validate(value: Any) -> str:
        if not isinstance(value, str) or not value:
            raise ValueError(
                f"invalid {name}: {value!r} (must be non-empty string)"
            )
        return value
    return _validate


def _check_scalar(name: str, value: Any) -> Any:
    if not isinstance(value, (str, int, float, bool)):
        raise ValueError(
            f"invalid {name}: {value!r} (must be a scalar str/int/float/bool)"
        )
    return value


# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------

# name -> {"build": fn(params)->(cypher, bind), "describe": str,
#          "params": tuple of declared param names (for tool docs)}
PATTERNS: dict[str, dict[str, Any]] = {}


def _register(name: str, describe: str, params: tuple[str, ...]):
    def deco(fn: Callable[[dict[str, Any]], tuple[str, dict[str, Any]]]):
        PATTERNS[name] = {"build": fn, "describe": describe, "params": params}
        return fn
    return deco


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


@_register(
    "entity_by_id",
    "Fetch one node by (kind, id).",
    ("kind", "id"),
)
def _entity_by_id(p: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    kind = _check_kind(p["kind"])
    id_ = _check_nonempty_str("id")(p["id"])
    return (
        f"MATCH (n:{kind}) WHERE n.id = $id RETURN n",
        {"id": id_},
    )


@_register(
    "entities_by_kind",
    "List up to ``limit`` nodes of a given kind.",
    ("kind", "limit"),
)
def _entities_by_kind(p: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    kind = _check_kind(p["kind"])
    limit = _check_limit(p.get("limit"))
    return (
        f"MATCH (n:{kind}) RETURN n LIMIT {limit}",
        {},
    )


@_register(
    "entities_by_attr",
    "List nodes of a kind matching a single attribute equality.",
    ("kind", "attr_key", "attr_value", "limit"),
)
def _entities_by_attr(p: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    kind = _check_kind(p["kind"])
    attr_key = _check_attr_key(p["attr_key"])
    attr_value = _check_scalar("attr_value", p["attr_value"])
    limit = _check_limit(p.get("limit"))
    return (
        f"MATCH (n:{kind}) WHERE n.`{attr_key}` = $attr_value "
        f"RETURN n LIMIT {limit}",
        {"attr_value": attr_value},
    )


@_register(
    "entities_touched_by_workflow",
    "List entities whose source_workflows contains the given workflow id.",
    ("workflow_id", "limit"),
)
def _entities_touched_by_workflow(
    p: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    workflow_id = _check_nonempty_str("workflow_id")(p["workflow_id"])
    limit = _check_limit(p.get("limit"))
    return (
        "MATCH (n) WHERE $wid IN n.source_workflows "
        f"RETURN n LIMIT {limit}",
        {"wid": workflow_id},
    )


@_register(
    "linked_outgoing",
    "Outgoing neighbours of a node id, optionally filtered by rel.",
    ("id", "rel", "limit"),
)
def _linked_outgoing(p: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    id_ = _check_nonempty_str("id")(p["id"])
    limit = _check_limit(p.get("limit"))
    rel = p.get("rel")
    if rel in (None, ""):
        return (
            "MATCH ({id: $id})-[r]->(n) "
            f"RETURN n, label(r) AS rel LIMIT {limit}",
            {"id": id_},
        )
    rel_upper = _check_rel(rel)
    return (
        f"MATCH ({{id: $id}})-[r:{rel_upper}]->(n) "
        f"RETURN n, label(r) AS rel LIMIT {limit}",
        {"id": id_},
    )


@_register(
    "linked_incoming",
    "Incoming neighbours of a node id, optionally filtered by rel.",
    ("id", "rel", "limit"),
)
def _linked_incoming(p: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    id_ = _check_nonempty_str("id")(p["id"])
    limit = _check_limit(p.get("limit"))
    rel = p.get("rel")
    if rel in (None, ""):
        return (
            "MATCH (n)-[r]->({id: $id}) "
            f"RETURN n, label(r) AS rel LIMIT {limit}",
            {"id": id_},
        )
    rel_upper = _check_rel(rel)
    return (
        f"MATCH (n)-[r:{rel_upper}]->({{id: $id}}) "
        f"RETURN n, label(r) AS rel LIMIT {limit}",
        {"id": id_},
    )


_DECIDED_REL_LIST = ", ".join(f"'{n}'" for n in DECIDED_REL_NAMES)


@_register(
    "decisions_by_workflow",
    "Recent Decision nodes for a workflow id, newest first.",
    ("workflow_id", "limit"),
)
def _decisions_by_workflow(p: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    workflow_id = _check_nonempty_str("workflow_id")(p["workflow_id"])
    limit = _check_limit(p.get("limit"), default=10)
    return (
        "MATCH (d:Decision) WHERE d.workflow_id = $wid "
        f"RETURN d ORDER BY d.decided_at DESC LIMIT {limit}",
        {"wid": workflow_id},
    )


@_register(
    "decisions_by_persona_and_entity",
    "Recent Decision nodes for a persona role decided about an entity id.",
    ("persona_role", "entity_id", "limit"),
)
def _decisions_by_persona_and_entity(
    p: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    persona_role = _check_nonempty_str("persona_role")(p["persona_role"])
    entity_id = _check_nonempty_str("entity_id")(p["entity_id"])
    limit = _check_limit(p.get("limit"), default=10)
    return (
        "MATCH (d:Decision)-[r]->(e {id: $entity_id}) "
        "WHERE d.persona_role = $persona_role "
        f"AND label(r) IN [{_DECIDED_REL_LIST}] "
        f"RETURN d ORDER BY d.decided_at DESC LIMIT {limit}",
        {"persona_role": persona_role, "entity_id": entity_id},
    )


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def render(
    name: str, params: dict[str, Any] | None
) -> tuple[str, dict[str, Any]]:
    """Return ``(cypher, bind_params)`` for the named template.

    Raises :class:`KeyError` for unknown ``name``; param-validation
    errors (including missing required keys) surface as
    :class:`ValueError`.
    """
    if name not in PATTERNS:
        raise KeyError(
            f"unknown find_entities pattern: {name!r} "
            f"(expected one of {sorted(PATTERNS)})"
        )
    try:
        return PATTERNS[name]["build"](params or {})
    except KeyError as ex:
        raise ValueError(
            f"missing required param for pattern {name!r}: {ex.args[0]!r}"
        ) from ex


def pattern_names() -> list[str]:
    """Sorted list of registered pattern names."""
    return sorted(PATTERNS)


def describe_patterns() -> dict[str, dict[str, Any]]:
    """Per-pattern ``{describe, params}`` for tool documentation."""
    return {
        name: {"describe": entry["describe"], "params": list(entry["params"])}
        for name, entry in PATTERNS.items()
    }
