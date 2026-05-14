"""validate_classification_schema — guardrail edge over rag_classifier output."""
from __future__ import annotations

from api.shared.expense_taxonomy import VERDICTS


class ClassificationSchemaError(ValueError):
    """Raised when a classifier payload does not conform to the spec."""


def validate(payload: dict) -> None:
    if payload.get("parse_error"):
        raise ClassificationSchemaError(
            f"parse_error in classifier payload: {payload.get('raw', '')[:200]}"
        )

    for required in ("verdict", "policy_clause", "reasoning", "confidence", "competing_interpretations"):
        if required not in payload:
            raise ClassificationSchemaError(f"missing field: {required}")

    if payload["verdict"] not in VERDICTS:
        raise ClassificationSchemaError(
            f"verdict must be one of {VERDICTS}, got {payload['verdict']!r}"
        )

    if not isinstance(payload["policy_clause"], str) or not payload["policy_clause"].startswith("§"):
        raise ClassificationSchemaError(
            f"policy_clause must be a string starting with §; got {payload['policy_clause']!r}"
        )

    if not isinstance(payload["reasoning"], str) or not payload["reasoning"].strip():
        raise ClassificationSchemaError("reasoning must be a non-empty string")

    conf = payload["confidence"]
    if not isinstance(conf, (int, float)) or not 0.0 <= float(conf) <= 1.0:
        raise ClassificationSchemaError(f"confidence must be float in [0,1]; got {conf!r}")

    if not isinstance(payload["competing_interpretations"], list):
        raise ClassificationSchemaError("competing_interpretations must be a list")
