"""Graph-shape adapter for the fleet-contract-renewal-renewal-terms-drafter validator.

In-graph validators return `{"ok": bool, ...}` so TrackedExecutor can emit
`validator.blocked` cleanly. Mirrors validate_classification_schema_node.py.
"""
from __future__ import annotations


_ALLOWED_VERDICT = {"drafted", "blocked"}


async def execute(input: dict) -> dict:
    payload = input.get("renewal_terms_drafter") or {}

    verdict = payload.get("verdict")
    if verdict not in _ALLOWED_VERDICT:
        return {
            "ok": False,
            "blocked_reason": f"verdict must be one of {sorted(_ALLOWED_VERDICT)}; got {verdict!r}",
            "renewal_terms_drafter": payload,
        }

    cost_change_pct = payload.get("cost_change_pct")
    if not isinstance(cost_change_pct, (int, float)) or isinstance(cost_change_pct, bool):
        return {
            "ok": False,
            "blocked_reason": f"cost_change_pct must be a number; got {cost_change_pct!r}",
            "renewal_terms_drafter": payload,
        }

    proposed_terms = payload.get("proposed_terms")
    if not isinstance(proposed_terms, list):
        return {
            "ok": False,
            "blocked_reason": "proposed_terms must be a list of {line_item, current, proposed} objects",
            "renewal_terms_drafter": payload,
        }
    for entry in proposed_terms:
        if not isinstance(entry, dict) or not entry.get("line_item"):
            return {
                "ok": False,
                "blocked_reason": "proposed_terms entries must be objects carrying a line_item",
                "renewal_terms_drafter": payload,
            }

    cited_clauses = payload.get("cited_clauses")
    if not isinstance(cited_clauses, list):
        return {
            "ok": False,
            "blocked_reason": "cited_clauses must be a list of {section, quote} objects",
            "renewal_terms_drafter": payload,
        }
    for entry in cited_clauses:
        if not isinstance(entry, dict) or not entry.get("section") or not entry.get("quote"):
            return {
                "ok": False,
                "blocked_reason": "cited_clauses entries must be objects carrying section + quote",
                "renewal_terms_drafter": payload,
            }

    proposed_annual_value_usd = payload.get("proposed_annual_value_usd")
    if (
        not isinstance(proposed_annual_value_usd, (int, float))
        or isinstance(proposed_annual_value_usd, bool)
        or proposed_annual_value_usd < 0
    ):
        return {
            "ok": False,
            "blocked_reason": "proposed_annual_value_usd must be a non-negative number",
            "renewal_terms_drafter": payload,
        }

    current_annual_value_usd = payload.get("current_annual_value_usd")
    if (
        not isinstance(current_annual_value_usd, (int, float))
        or isinstance(current_annual_value_usd, bool)
        or current_annual_value_usd <= 0
    ):
        return {
            "ok": False,
            "blocked_reason": "current_annual_value_usd must be a positive number",
            "renewal_terms_drafter": payload,
        }

    # Cross-field invariant: cost_change_pct must agree with the
    # proposed/current value pair within ±0.5% (rounding tolerance).
    derived_pct = (
        (proposed_annual_value_usd - current_annual_value_usd)
        / current_annual_value_usd
        * 100.0
    )
    if abs(derived_pct - cost_change_pct) > 0.5:
        return {
            "ok": False,
            "blocked_reason": (
                f"cost_change_pct={cost_change_pct!r} disagrees with "
                f"derived ({proposed_annual_value_usd}/{current_annual_value_usd}-1)*100"
                f"={round(derived_pct, 2)} by more than 0.5%"
            ),
            "renewal_terms_drafter": payload,
        }

    # Cross-field invariant: drafted iff at least one proposed_terms entry
    # AND at least one cited_clauses entry AND proposed_annual_value_usd > 0.
    is_drafted = (
        bool(proposed_terms)
        and bool(cited_clauses)
        and proposed_annual_value_usd > 0
    )
    if (verdict == "drafted") != is_drafted:
        return {
            "ok": False,
            "blocked_reason": (
                f"verdict/draft inconsistent: verdict={verdict!r} but "
                f"proposed_terms={len(proposed_terms)}, "
                f"cited_clauses={len(cited_clauses)}, "
                f"proposed_annual_value_usd={proposed_annual_value_usd!r}"
            ),
            "renewal_terms_drafter": payload,
        }

    return {
        "ok": True,
        "renewal_terms_drafter": payload,
        "verdict": verdict,
        "cost_change_pct": cost_change_pct,
    }
