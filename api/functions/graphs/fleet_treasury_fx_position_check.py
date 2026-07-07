"""Phase 2 (Position Check) graph for Treasury FX domain.

Validates the proposed FX op against (synthetic) trading-limit headroom
on the currency pair. Returns a flags list the persona reads.
"""
from __future__ import annotations
import hashlib

from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.validators import validate_fleet_treasury_fx_position_check_schema


# Synthetic per-pair limits (GBP). Deterministic on the pair string.
def _pair_limit_gbp(currency_pair: str) -> int:
    seed = int(hashlib.sha256(currency_pair.encode()).hexdigest()[:6], 16)
    return 5_000_000 + (seed % 7) * 1_000_000  # 5M..11M


async def _position_check_execute(input: dict) -> dict:
    op = input.get("treasury_op") or {}
    lookup = input.get("op_lookup") or {}
    pair = lookup.get("currency_pair") or op.get("currency_pair", "GBP/USD")
    notional = lookup.get("notional_gbp") or op.get("notional_gbp", 0)
    limit = _pair_limit_gbp(pair)
    within_limit = notional <= limit
    flags = []
    if not within_limit:
        flags.append("over-pair-limit")
    return {
        "ok": True,
        "currency_pair": pair,
        "notional_gbp": notional,
        "pair_limit_gbp": limit,
        "within_limit": within_limit,
        "category": "standard",
        "flags": flags,
    }


def build_fleet_treasury_fx_position_check_workflow() -> Workflow:
    return build_linear_workflow([
        ("position_check", "deterministic_position_check", "deterministic", _position_check_execute),
        ("val_position_check", "validate_position_check_schema", "validator", validate_fleet_treasury_fx_position_check_schema.execute),
    ])
