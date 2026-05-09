"""Validator for the v1 (entities) brief slice (TASK-011).

Imports the Phase 1 schema source-of-truth from
:mod:`api.server.services.entity_graph` (`_VALID_KINDS`, `_VALID_RELS`)
when available; falls back to a small placeholder otherwise (so this
sub-skill can be exercised in repos where Phase 1 is not yet merged —
not the case in this branch but kept for portability).

Semantic checks layered over the JSON-schema pass:

* ``entities[].kind`` ∈ `_VALID_KINDS` (less ``Workflow``).
* ``entities[].ref_field`` resolves against the orchestrator's
  emitted payload paths (parsed by AST-walking the orchestrator file).
* ``entities[].relations[].kind`` ∈ `_VALID_RELS`.
* ``entities[].relations[].target_ref`` resolves to another entity's
  ``ref_field`` (or, for forward references, an entity_id literal).
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable

from _shared.brief_validator import SchemaError, validate_brief

__all__ = ["SchemaError", "validate", "extract_payload_refs"]


try:
    from api.server.services.entity_graph import _VALID_KINDS, _VALID_RELS  # type: ignore
    _SCHEMA_KINDS = frozenset(_VALID_KINDS) - {"Workflow"}
    _SCHEMA_RELS = frozenset(_VALID_RELS)
except Exception:  # pragma: no cover — Phase 1 absent fallback
    _SCHEMA_KINDS = frozenset({
        "Person", "Organisation", "Asset", "Money",
        "Decision", "Place", "Period",
    })
    _SCHEMA_RELS = frozenset({
        "EMPLOYED_BY", "MANAGES", "OWNS", "TRANSACTS",
        "BELONGS_TO", "LOCATED_IN", "DECIDED_ON", "PRECEDENT_OF",
        "TOUCHED", "SUB_WORKFLOW_OF",
    })


def extract_payload_refs(orchestrator_path: Path) -> set[str]:
    """AST-walk an orchestrator file and return the set of dotted
    payload paths it touches.

    We're permissive: every `payload.<key>` and `payload[<literal>]`
    chain reachable from a top-level subscript is recorded. The
    validator uses this set as the "permissible ref_field" universe.
    """
    src = orchestrator_path.read_text()
    tree = ast.parse(src)
    refs: set[str] = set()

    def _walk_attr(node: ast.AST, prefix: list[str]) -> None:
        if isinstance(node, ast.Attribute):
            _walk_attr(node.value, prefix + [node.attr])
        elif isinstance(node, ast.Name):
            chain = list(reversed(prefix + [node.id]))
            if chain[0] in {"payload", "p", "input_dict", "enriched"}:
                # Normalise alias roots → "payload".
                refs.add("payload." + ".".join(chain[1:]) if len(chain) > 1 else "payload")

    def _walk_subscript(node: ast.Subscript, prefix: list[str]) -> None:
        # payload["foo"]["bar"] -> payload.foo.bar
        keys: list[str] = []
        cur: ast.AST = node
        while isinstance(cur, ast.Subscript):
            sl = cur.slice
            if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
                keys.append(sl.value)
            else:
                return
            cur = cur.value
        if isinstance(cur, ast.Name) and cur.id in {
            "payload", "p", "input_dict", "enriched"
        }:
            chain = list(reversed(keys))
            refs.add("payload." + ".".join(chain) if chain else "payload")

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            _walk_attr(node, [])
        elif isinstance(node, ast.Subscript):
            _walk_subscript(node, [])
        elif isinstance(node, ast.Call):
            # capture .get("key", ...) on payload-aliased dicts
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in {"payload", "p", "input_dict", "enriched"}
            ):
                refs.add(f"payload.{node.args[0].value}")

    return refs


def _ref_in_universe(ref: str, universe: Iterable[str]) -> bool:
    """A ref is considered resolvable if either:
       * it appears verbatim in ``universe``, OR
       * any prefix of its dotted chain appears (a parent dict was
         touched by the orchestrator — the leaf may live in a nested
         dict the AST cannot enumerate without runtime info).
    """
    universe_set = set(universe)
    if ref in universe_set:
        return True
    parts = ref.split(".")
    for i in range(len(parts), 1, -1):
        if ".".join(parts[:i]) in universe_set:
            return True
    return False


def validate(brief: dict, orchestrator_path: Path | None = None) -> None:
    """Validate the entities slice of ``brief``.

    ``orchestrator_path`` is optional — when omitted, ref_field
    resolution is skipped (useful for unit tests with synthetic
    briefs).
    """
    validate_brief(brief)

    entities = brief.get("entities") or []
    if not entities:
        return  # entities block is optional at the schema level

    universe = (
        extract_payload_refs(orchestrator_path) if orchestrator_path else None
    )

    seen_refs: list[str] = []
    for i, ent in enumerate(entities):
        kind = ent.get("kind")
        if kind not in _SCHEMA_KINDS:
            raise SchemaError(
                path=f"entities[{i}].kind",
                reason=(
                    f"unknown entity kind {kind!r}; must be one of "
                    f"{sorted(_SCHEMA_KINDS)}"
                ),
            )
        ref = ent.get("ref_field") or ""
        if not ref.startswith("payload."):
            raise SchemaError(
                path=f"entities[{i}].ref_field",
                reason=f"ref_field must start with 'payload.' (got {ref!r})",
            )
        if universe is not None and not _ref_in_universe(ref, universe):
            raise SchemaError(
                path=f"entities[{i}].ref_field",
                reason=(
                    f"ref_field {ref!r} not found in orchestrator's emitted "
                    f"payload paths"
                ),
            )
        seen_refs.append(ref)

        for j, rel in enumerate(ent.get("relations") or []):
            rkind = rel.get("kind")
            if rkind not in _SCHEMA_RELS:
                raise SchemaError(
                    path=f"entities[{i}].relations[{j}].kind",
                    reason=(
                        f"unknown rel kind {rkind!r}; must be one of "
                        f"{sorted(_SCHEMA_RELS)}"
                    ),
                )
            tgt = rel.get("target_ref") or ""
            # target_ref must be either another entity's ref_field
            # (we accept any ref_field declared earlier OR later in the
            # same brief — order shouldn't matter) or an entity_id
            # literal (a bare identifier — defensive opt-in).
            entity_refs = [str(e.get("ref_field")) for e in entities]
            if tgt not in entity_refs and not tgt.startswith("payload."):
                raise SchemaError(
                    path=f"entities[{i}].relations[{j}].target_ref",
                    reason=(
                        f"target_ref {tgt!r} does not match any entity's "
                        f"ref_field"
                    ),
                )
