"""Graph-shape adapter for validate_classification_schema.

The Week 1 module's `validate(payload)` raises ClassificationSchemaError —
that's the off-graph guardrail pattern (used by the acceptance harness).
For an in-graph validator, TrackedExecutor expects `{"ok": bool, ...}` so it
can emit `validator.blocked` cleanly. This adapter wraps the raise into the
graph shape without breaking any existing caller.
"""
from __future__ import annotations

from .validate_classification_schema import (
    ClassificationSchemaError,
    validate,
)


async def execute(input: dict) -> dict:
    payload = input.get("classification") or {}
    try:
        validate(payload)
    except ClassificationSchemaError as ex:
        return {
            "ok": False,
            "blocked_reason": str(ex),
            "classification": payload,
        }
    return {
        "ok": True,
        "classification": payload,
        "verdict": payload.get("verdict"),
    }
