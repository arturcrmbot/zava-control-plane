"""validate_receipt_schema — guardrail edge over agent_receipt_validator output.

Two-surface pattern (mirrors validate_classification_schema):
  - `validate(payload)` — raises on bad shape; usable directly from tests.
  - `execute(input)` — graph-node adapter returning `{"ok": bool, ...}`.
"""
from __future__ import annotations


VALID_FLAVOURS = {
    "correct", "wrong-amount", "wrong-date", "wrong-vendor",
    "missing-line-item", "missing-receipt",
}


class ReceiptSchemaError(ValueError):
    """Raised when a receipt-validator payload does not conform to the spec."""


def validate(payload: dict) -> None:
    if payload.get("parse_error"):
        raise ReceiptSchemaError(
            f"parse_error in receipt-validator payload: "
            f"{(payload.get('raw') or '')[:200]}"
        )

    for required in ("verdict", "flavour", "evidence", "confidence"):
        if required not in payload:
            raise ReceiptSchemaError(f"missing field: {required}")

    if payload["verdict"] not in {"match", "mismatch"}:
        raise ReceiptSchemaError(
            f"verdict must be 'match' or 'mismatch'; got {payload['verdict']!r}"
        )

    if payload["flavour"] not in VALID_FLAVOURS:
        raise ReceiptSchemaError(
            f"flavour must be one of {sorted(VALID_FLAVOURS)}; got {payload['flavour']!r}"
        )

    # `verdict == "match"` iff `flavour == "correct"`.
    if (payload["verdict"] == "match") != (payload["flavour"] == "correct"):
        raise ReceiptSchemaError(
            f"verdict/flavour disagreement: verdict={payload['verdict']!r}, "
            f"flavour={payload['flavour']!r}"
        )

    if not isinstance(payload["evidence"], str) or not payload["evidence"].strip():
        raise ReceiptSchemaError("evidence must be a non-empty string")

    conf = payload["confidence"]
    if not isinstance(conf, (int, float)) or not 0.0 <= float(conf) <= 1.0:
        raise ReceiptSchemaError(f"confidence must be float in [0,1]; got {conf!r}")


async def execute(input: dict) -> dict:
    """Graph-node adapter — wraps validate() into the {ok: bool} shape that
    TrackedExecutor.process keys off for `validator.blocked` events."""
    receipt_validation = input.get("receipt_validation", {})
    try:
        validate(receipt_validation)
    except ReceiptSchemaError as e:
        return {
            "ok": False,
            "blocked_reason": str(e),
            "receipt_validation": receipt_validation,
            **{k: v for k, v in input.items() if k not in {"receipt_validation"}},
        }
    return {
        "ok": True,
        "receipt_validation": receipt_validation,
        "flavour": receipt_validation["flavour"],
        "verdict": receipt_validation["verdict"],
        **{k: v for k, v in input.items() if k not in {"receipt_validation"}},
    }
