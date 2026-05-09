"""Validator for the v3 (function membership) brief slice (TASK-019).

Imports the live ``FUNCTIONS`` registry from :mod:`api.shared.functions`
when importable — otherwise falls back to ``FUNCTIONS_PLACEHOLDER``,
the 10-key canonical whitelist mirrored verbatim from Phase 3 TASK-001
so Phase 2 can ship standalone before Phase 3 lands.

Drift between this list and Phase 3's keys would trip Phase 3's boot
validator; both lists must move together.
"""
from __future__ import annotations

from typing import Any

from _shared.brief_validator import SchemaError, validate_brief

__all__ = ["SchemaError", "FUNCTIONS_PLACEHOLDER", "validate"]


FUNCTIONS_PLACEHOLDER: frozenset[str] = frozenset({
    "finance", "hr", "revenue", "ops", "legal",
    "marketing", "tech", "data", "customer-success", "legacy",
})


def _resolve_functions() -> tuple[frozenset[str], dict[str, Any] | None]:
    """Return ``(valid_keys, live_registry_or_None)``.

    The live registry (when present) is consulted for orphan / dup
    checks; the placeholder is keys-only.
    """
    try:
        from api.shared.functions import FUNCTIONS  # type: ignore
    except Exception:
        return FUNCTIONS_PLACEHOLDER, None
    return frozenset(FUNCTIONS.keys()), FUNCTIONS


def validate(brief: dict, *, registry_override: dict[str, Any] | None = None) -> None:
    """Validate ``brief.function`` against the registry.

    ``registry_override`` lets tests inject a synthetic FUNCTIONS dict
    (mapping name -> object with ``owns_domains`` iterable) without
    monkey-patching the import.
    """
    validate_brief(brief)

    fn = brief.get("function")
    if fn is None:
        raise SchemaError(
            path="function",
            reason="brief is missing required 'function' key",
        )

    if registry_override is not None:
        valid_keys: frozenset[str] = frozenset(registry_override.keys())
        registry: dict[str, Any] | None = registry_override
    else:
        valid_keys, registry = _resolve_functions()

    if fn not in valid_keys:
        raise SchemaError(
            path="function",
            reason=(
                f"unknown function {fn!r}; must be one of {sorted(valid_keys)}"
            ),
        )

    if registry is None:
        return

    workflow_type = (brief.get("domain") or {}).get("workflow_type")
    if not workflow_type:
        return

    for key, entry in registry.items():
        owns = getattr(entry, "owns_domains", None) or []
        if workflow_type in owns and key != fn:
            raise SchemaError(
                path="function",
                reason=(
                    f"workflow_type {workflow_type!r} is already claimed by "
                    f"FUNCTIONS[{key!r}].owns_domains — cannot also belong "
                    f"to {fn!r} (orphan/dup)"
                ),
            )
