"""Graph-shape adapter for the fleet-travel-preapproval-policy-fit-check validator.

In-graph validators return `{"ok": bool, ...}` so TrackedExecutor can emit
`validator.blocked` cleanly. Mirrors validate_classification_schema_node.py.
"""
from __future__ import annotations


_ALLOWED_FIT = {"in-policy", "out-of-policy"}
_ALLOWED_BAND = {"low", "mid", "high"}


async def execute(input: dict) -> dict:
    payload = input.get("policy_fit_check") or {}

    fit = payload.get("policy_fit")
    if fit not in _ALLOWED_FIT:
        return {
            "ok": False,
            "blocked_reason": f"policy_fit must be one of {sorted(_ALLOWED_FIT)}; got {fit!r}",
            "policy_fit_check": payload,
        }

    band = payload.get("band")
    if band not in _ALLOWED_BAND:
        return {
            "ok": False,
            "blocked_reason": f"band must be one of {sorted(_ALLOWED_BAND)}; got {band!r}",
            "policy_fit_check": payload,
        }

    violated = payload.get("violated_clauses")
    if not isinstance(violated, list):
        return {
            "ok": False,
            "blocked_reason": "violated_clauses must be a list (empty if in-policy)",
            "policy_fit_check": payload,
        }

    # Cross-field invariant: in-policy iff no violated clauses.
    if (fit == "in-policy") != (len(violated) == 0):
        return {
            "ok": False,
            "blocked_reason": (
                f"policy_fit/violated_clauses inconsistent: "
                f"fit={fit!r} but violated_clauses={violated!r}"
            ),
            "policy_fit_check": payload,
        }

    return {
        "ok": True,
        "policy_fit_check": payload,
        "policy_fit": fit,
        "band": band,
    }
