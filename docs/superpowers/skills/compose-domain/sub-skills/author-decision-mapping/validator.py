"""Validator for the v2 (decisions) brief slice (TASK-015).

Layered semantic checks on top of the JSON-schema pass:

* Every ``decisions[].phase`` exists in ``brief.phases`` with
  ``kind: hitl``.
* Every ``decisions[].persona`` matches a folder under
  ``api/server/personae/`` *when that directory is reachable from
  the cwd*. Skipped silently when the personae directory is missing
  (synthetic test environments).
* No two decisions name the same phase (Phase 1 dedupe contract).
* ``decided_on_entities`` refs all resolve to entries in
  ``brief.entities`` (when entities block is present).
"""
from __future__ import annotations

from pathlib import Path

from _shared.brief_validator import SchemaError, validate_brief

__all__ = ["SchemaError", "validate"]


def _list_personae(repo_root: Path) -> set[str]:
    pdir = repo_root / "api" / "server" / "personae"
    if not pdir.exists():
        return set()
    return {p.name for p in pdir.iterdir() if p.is_dir() and not p.name.startswith("_")}


def validate(brief: dict, repo_root: Path | None = None) -> None:
    """Validate the decisions slice of ``brief``.

    ``repo_root`` defaults to the current working directory; pass an
    explicit path in tests.
    """
    validate_brief(brief)

    decisions = brief.get("decisions") or []
    if not decisions:
        return

    phases_by_name = {p.get("name"): p for p in (brief.get("phases") or [])}
    entity_refs = {
        e.get("ref_field") for e in (brief.get("entities") or []) if e.get("ref_field")
    }

    personae_dir = repo_root or Path.cwd()
    known_personae = _list_personae(personae_dir)

    seen_phases: set[str] = set()
    for i, dec in enumerate(decisions):
        phase = dec.get("phase")
        if phase not in phases_by_name:
            raise SchemaError(
                path=f"decisions[{i}].phase",
                reason=f"phase {phase!r} not declared in brief.phases",
            )
        if phases_by_name[phase].get("kind") != "hitl":
            raise SchemaError(
                path=f"decisions[{i}].phase",
                reason=f"phase {phase!r} is not kind: hitl",
            )
        if phase in seen_phases:
            raise SchemaError(
                path=f"decisions[{i}].phase",
                reason=(
                    f"phase {phase!r} already claimed by an earlier decision; "
                    f"one decision per HITL phase"
                ),
            )
        seen_phases.add(phase)

        persona = dec.get("persona")
        if known_personae and persona not in known_personae:
            raise SchemaError(
                path=f"decisions[{i}].persona",
                reason=(
                    f"persona {persona!r} not registered under "
                    f"api/server/personae/"
                ),
            )

        for j, ref in enumerate(dec.get("decided_on_entities") or []):
            if entity_refs and ref not in entity_refs:
                raise SchemaError(
                    path=f"decisions[{i}].decided_on_entities[{j}]",
                    reason=(
                        f"ref {ref!r} does not match any entity's ref_field"
                    ),
                )
