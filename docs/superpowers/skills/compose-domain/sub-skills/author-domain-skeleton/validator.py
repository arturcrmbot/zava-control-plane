"""Validator for the v0 (skeleton) brief slice (TASK-007).

Layered on top of :mod:`_shared.brief_validator` (which runs the JSON
schema). This file enforces the *semantic* rules the schema cannot
express:

* ``domain.workflow_type`` and ``domain.prefix`` and ``domain.display_name``
  are present.
* ``phases`` is non-empty.
* every ``phase.kind`` is one of ``deterministic | agent | hitl | sub_orchestrator | graph``.
* every HITL phase carries ``persona`` and ``external_event``.
* ≥ 1 phase is ``kind: deterministic`` (the intake gate).
* ≥ 1 phase is ``kind: hitl`` (the operator gate).
"""
from __future__ import annotations

from _shared.brief_validator import SchemaError, validate_brief

__all__ = ["SchemaError", "validate"]

_VALID_KINDS = {"deterministic", "agent", "hitl", "sub_orchestrator", "graph"}


def validate(brief: dict) -> None:
    """Validate the skeleton (domain + phases) slice of ``brief``.

    Re-uses the JSON-schema pass first, then layers semantic checks.
    Raises :class:`SchemaError` on the first failure.
    """
    validate_brief(brief)

    domain = brief.get("domain") or {}
    for required in ("workflow_type", "prefix", "display_name"):
        if not domain.get(required):
            raise SchemaError(
                path=f"domain.{required}",
                reason=f"required key '{required}' missing from domain block",
            )

    phases = brief.get("phases") or []
    if not phases:
        raise SchemaError(path="phases", reason="phases must be non-empty")

    has_deterministic = False
    has_hitl = False
    for i, phase in enumerate(phases):
        name = phase.get("name") or f"<phase-{i}>"
        kind = phase.get("kind")
        if kind not in _VALID_KINDS:
            raise SchemaError(
                path=f"phases[{i}].kind",
                reason=(
                    f"phase '{name}' has unknown kind {kind!r}; "
                    f"must be one of {sorted(_VALID_KINDS)}"
                ),
            )
        if kind == "deterministic":
            has_deterministic = True
        if kind == "hitl":
            has_hitl = True
            if not phase.get("persona"):
                raise SchemaError(
                    path=f"phases[{i}].persona",
                    reason=f"HITL phase '{name}' must declare persona",
                )
            if not phase.get("external_event"):
                raise SchemaError(
                    path=f"phases[{i}].external_event",
                    reason=f"HITL phase '{name}' must declare external_event",
                )
        if kind == "sub_orchestrator":
            if not phase.get("target_workflow_type"):
                raise SchemaError(
                    path=f"phases[{i}].target_workflow_type",
                    reason=(
                        f"sub_orchestrator phase '{name}' must declare "
                        f"target_workflow_type"
                    ),
                )
            if not phase.get("payload_from"):
                raise SchemaError(
                    path=f"phases[{i}].payload_from",
                    reason=(
                        f"sub_orchestrator phase '{name}' must declare "
                        f"payload_from (Cypher snippet or python:<expr>)"
                    ),
                )

    if not has_deterministic:
        # Phase 4 IP4 (TASK-019): meta-workflows compose existing fleet
        # domains via `sub_orchestrator` phases — their intake gate is
        # the first sub-orchestrator's own intake. Relax the
        # deterministic requirement when sub_orchestrator is present.
        if not any(p.get("kind") == "sub_orchestrator" for p in phases):
            raise SchemaError(
                path="phases",
                reason="at least one phase must be kind: deterministic (the intake)",
            )
    if not has_hitl:
        raise SchemaError(
            path="phases",
            reason="at least one phase must be kind: hitl (the operator gate)",
        )
