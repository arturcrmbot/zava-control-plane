"""validate_arbitration_schema — guardrail edge over agent_arbitration output."""
from __future__ import annotations


VALID_RECOMMENDATIONS = {
    "accept-justification", "require-repayment", "issue-warning", "escalate",
}


class ArbitrationSchemaError(ValueError):
    """Raised when an arbitration payload does not conform to the spec."""


def validate(payload: dict) -> None:
    if payload.get("parse_error"):
        raise ArbitrationSchemaError(
            f"parse_error: {(payload.get('raw') or '')[:200]}"
        )
    for required in ("recommendation", "rationale", "policy_clause", "confidence"):
        if required not in payload:
            raise ArbitrationSchemaError(f"missing field: {required}")
    if payload["recommendation"] not in VALID_RECOMMENDATIONS:
        raise ArbitrationSchemaError(
            f"recommendation must be one of {sorted(VALID_RECOMMENDATIONS)}; got {payload['recommendation']!r}"
        )
    if not isinstance(payload["rationale"], str) or not payload["rationale"].strip():
        raise ArbitrationSchemaError("rationale must be non-empty")
    if not isinstance(payload["policy_clause"], str) or not payload["policy_clause"].startswith("§"):
        raise ArbitrationSchemaError(
            f"policy_clause must start with §; got {payload['policy_clause']!r}"
        )
    conf = payload["confidence"]
    if not isinstance(conf, (int, float)) or not 0.0 <= float(conf) <= 1.0:
        raise ArbitrationSchemaError(f"confidence must be float in [0,1]; got {conf!r}")
    # cited_precedent_id may be null


async def execute(input: dict) -> dict:
    """Graph-node adapter."""
    arb = input.get("arbitration", {})
    try:
        validate(arb)
    except ArbitrationSchemaError as e:
        return {"ok": False, "blocked_reason": str(e), "arbitration": arb,
                **{k: v for k, v in input.items() if k != "arbitration"}}
    return {"ok": True, "arbitration": arb,
            "recommendation": arb["recommendation"],
            **{k: v for k, v in input.items() if k != "arbitration"}}
