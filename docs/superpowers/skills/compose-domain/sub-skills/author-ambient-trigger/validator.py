"""Validator for the v4 (ambient) brief slice (TASK-023).

Semantic checks layered over the JSON-schema pass:

* The trigger discriminated union is well-formed: each
  ``triggers[]`` entry's `kind` matches its keys.
    - ``bus``     → requires ``event_type`` (filter optional).
    - ``cypher``  → requires ``pattern`` + ``sweep_seconds``.
    - ``cadence`` → requires ``cron``.
* ``ambient.function`` matches ``brief.function`` (same owner).
* ``spawnable_workflow_types`` are members of
  ``api.shared.domains.DOMAINS`` (when importable) or equal to
  ``brief.domain.workflow_type`` (self-spawn forward-declaration).
"""
from __future__ import annotations

from typing import Iterable

from _shared.brief_validator import SchemaError, validate_brief

__all__ = ["SchemaError", "validate"]


_REQUIRED_KEYS_BY_KIND = {
    "bus": {"event_type"},
    "cypher": {"pattern", "sweep_seconds"},
    "cadence": {"cron"},
}
_OWNED_KEYS_BY_KIND = {
    "bus": {"event_type", "filter"},
    "cypher": {"pattern", "sweep_seconds"},
    "cadence": {"cron"},
}
_ALL_KIND_KEYS = {k for keys in _OWNED_KEYS_BY_KIND.values() for k in keys}


def _resolve_domains() -> set[str] | None:
    try:
        from api.shared.domains import DOMAINS  # type: ignore
    except Exception:
        return None
    # DOMAINS may be a dict, list of dicts, or list of dataclasses.
    if isinstance(DOMAINS, dict):
        return set(DOMAINS.keys())
    out: set[str] = set()
    for d in DOMAINS:
        if isinstance(d, dict):
            wt = d.get("workflow_type")
            if wt:
                out.add(wt)
        else:
            wt = getattr(d, "workflow_type", None)
            if wt:
                out.add(wt)
    return out


def validate(
    brief: dict,
    *,
    known_workflow_types: Iterable[str] | None = None,
) -> None:
    """Validate the ambient slice of ``brief``. ``ambient`` is optional."""
    validate_brief(brief)

    ambient = brief.get("ambient")
    if not ambient:
        return

    triggers = ambient.get("triggers") or []
    for i, trig in enumerate(triggers):
        kind = trig.get("kind")
        if kind not in _REQUIRED_KEYS_BY_KIND:
            raise SchemaError(
                path=f"ambient.triggers[{i}].kind",
                reason=(
                    f"unknown trigger kind {kind!r}; must be one of "
                    f"{sorted(_REQUIRED_KEYS_BY_KIND)}"
                ),
            )
        # Required keys for this kind.
        missing = _REQUIRED_KEYS_BY_KIND[kind] - set(trig.keys())
        if missing:
            raise SchemaError(
                path=f"ambient.triggers[{i}]",
                reason=(
                    f"trigger kind={kind!r} missing required keys: "
                    f"{sorted(missing)}"
                ),
            )
        # No keys belonging to other kinds.
        owned = _OWNED_KEYS_BY_KIND[kind]
        wrong = (set(trig.keys()) & _ALL_KIND_KEYS) - owned
        if wrong:
            raise SchemaError(
                path=f"ambient.triggers[{i}]",
                reason=(
                    f"trigger kind={kind!r} carries keys belonging to "
                    f"another kind: {sorted(wrong)}"
                ),
            )

    fn = ambient.get("function")
    brief_fn = brief.get("function")
    if brief_fn and fn and fn != brief_fn:
        raise SchemaError(
            path="ambient.function",
            reason=(
                f"ambient.function {fn!r} must match brief.function {brief_fn!r}"
            ),
        )

    # spawnable_workflow_types ∈ DOMAINS ∪ {self}.
    self_wt = (brief.get("domain") or {}).get("workflow_type")
    if known_workflow_types is None:
        live = _resolve_domains()
        # Treat live=None (DOMAINS not importable) as "skip the check".
        valid_wts: set[str] | None = (
            (live | {self_wt}) if live is not None and self_wt else live
        )
    else:
        valid_wts = set(known_workflow_types)
        if self_wt:
            valid_wts.add(self_wt)

    if valid_wts is not None:
        for j, wt in enumerate(ambient.get("spawnable_workflow_types") or []):
            if wt not in valid_wts:
                raise SchemaError(
                    path=f"ambient.spawnable_workflow_types[{j}]",
                    reason=(
                        f"workflow_type {wt!r} not in DOMAINS registry "
                        f"and is not the brief's own workflow_type"
                    ),
                )
