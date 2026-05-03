"""Graph-shape adapter for the fleet-contract-renewal-market-benchmarker validator.

In-graph validators return `{"ok": bool, ...}` so TrackedExecutor can emit
`validator.blocked` cleanly. Mirrors validate_classification_schema_node.py.
"""
from __future__ import annotations


_ALLOWED_VERDICT = {"benchmarked", "blocked"}


async def execute(input: dict) -> dict:
    payload = input.get("market_benchmarker") or {}

    verdict = payload.get("verdict")
    if verdict not in _ALLOWED_VERDICT:
        return {
            "ok": False,
            "blocked_reason": f"verdict must be one of {sorted(_ALLOWED_VERDICT)}; got {verdict!r}",
            "market_benchmarker": payload,
        }

    comparable_contracts = payload.get("comparable_contracts")
    if not isinstance(comparable_contracts, list):
        return {
            "ok": False,
            "blocked_reason": "comparable_contracts must be a list of {contract_id, annual_value_usd, term_years} objects",
            "market_benchmarker": payload,
        }
    for entry in comparable_contracts:
        if not isinstance(entry, dict) or not entry.get("contract_id"):
            return {
                "ok": False,
                "blocked_reason": "comparable_contracts entries must be objects carrying a contract_id",
                "market_benchmarker": payload,
            }

    market_quotes = payload.get("market_quotes")
    if not isinstance(market_quotes, list):
        return {
            "ok": False,
            "blocked_reason": "market_quotes must be a list of {vendor, annual_value_usd} objects",
            "market_benchmarker": payload,
        }
    for entry in market_quotes:
        if not isinstance(entry, dict) or not entry.get("vendor"):
            return {
                "ok": False,
                "blocked_reason": "market_quotes entries must be objects carrying a vendor",
                "market_benchmarker": payload,
            }

    amendment_summary = payload.get("amendment_summary")
    if not isinstance(amendment_summary, dict):
        return {
            "ok": False,
            "blocked_reason": "amendment_summary must be an object with amendment_count + scope_creep_detected",
            "market_benchmarker": payload,
        }
    if not isinstance(amendment_summary.get("amendment_count"), int):
        return {
            "ok": False,
            "blocked_reason": "amendment_summary.amendment_count must be an integer",
            "market_benchmarker": payload,
        }

    band_low = payload.get("benchmark_band_low_usd")
    band_high = payload.get("benchmark_band_high_usd")
    if not isinstance(band_low, (int, float)) or band_low < 0:
        return {
            "ok": False,
            "blocked_reason": "benchmark_band_low_usd must be a non-negative number",
            "market_benchmarker": payload,
        }
    if not isinstance(band_high, (int, float)) or band_high < 0:
        return {
            "ok": False,
            "blocked_reason": "benchmark_band_high_usd must be a non-negative number",
            "market_benchmarker": payload,
        }
    if band_low > band_high:
        return {
            "ok": False,
            "blocked_reason": (
                f"benchmark band inverted: low={band_low!r} > high={band_high!r}"
            ),
            "market_benchmarker": payload,
        }

    # Cross-field invariant: benchmarked iff at least one comparable contract
    # AND at least one market quote AND a positive band span.
    is_benchmarked = (
        bool(comparable_contracts)
        and bool(market_quotes)
        and band_high > 0
    )
    if (verdict == "benchmarked") != is_benchmarked:
        return {
            "ok": False,
            "blocked_reason": (
                f"verdict/evidence inconsistent: verdict={verdict!r} but "
                f"comparable_contracts={len(comparable_contracts)}, "
                f"market_quotes={len(market_quotes)}, "
                f"benchmark_band_high_usd={band_high!r}"
            ),
            "market_benchmarker": payload,
        }

    return {
        "ok": True,
        "market_benchmarker": payload,
        "verdict": verdict,
        "benchmark_band_low_usd": band_low,
        "benchmark_band_high_usd": band_high,
    }
