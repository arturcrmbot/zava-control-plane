"""Graph-shape adapter for the fleet-it-access-request-risk-assessor validator.

In-graph validators return `{"ok": bool, ...}` so TrackedExecutor can emit
`validator.blocked` cleanly. Mirrors validate_classification_schema_node.py.
"""
from __future__ import annotations


_ALLOWED_RISK = {"low", "medium", "high"}


async def execute(input: dict) -> dict:
    payload = input.get("risk_assessor") or {}

    overall_risk = payload.get("overall_risk")
    if overall_risk not in _ALLOWED_RISK:
        return {
            "ok": False,
            "blocked_reason": f"overall_risk must be one of {sorted(_ALLOWED_RISK)}; got {overall_risk!r}",
            "risk_assessor": payload,
        }

    per_role_scores = payload.get("per_role_scores")
    if not isinstance(per_role_scores, list):
        return {
            "ok": False,
            "blocked_reason": "per_role_scores must be a list of {template_id, risk} objects",
            "risk_assessor": payload,
        }
    for entry in per_role_scores:
        if not isinstance(entry, dict):
            return {
                "ok": False,
                "blocked_reason": "per_role_scores entries must be objects",
                "risk_assessor": payload,
            }
        if entry.get("risk") not in _ALLOWED_RISK:
            return {
                "ok": False,
                "blocked_reason": (
                    f"per_role_scores entry risk must be one of {sorted(_ALLOWED_RISK)}; "
                    f"got {entry.get('risk')!r} for template_id={entry.get('template_id')!r}"
                ),
                "risk_assessor": payload,
            }

    breach_count = payload.get("breach_count")
    if not isinstance(breach_count, int) or breach_count < 0:
        return {
            "ok": False,
            "blocked_reason": "breach_count must be a non-negative integer",
            "risk_assessor": payload,
        }

    recent_grant_volume = payload.get("recent_grant_volume")
    if not isinstance(recent_grant_volume, int) or recent_grant_volume < 0:
        return {
            "ok": False,
            "blocked_reason": "recent_grant_volume must be a non-negative integer",
            "risk_assessor": payload,
        }

    # Cross-field invariant: overall_risk is the maximum of per_role_scores
    # (low < medium < high), unless per_role_scores is empty.
    if per_role_scores:
        rank = {"low": 0, "medium": 1, "high": 2}
        max_role = max(rank[entry["risk"]] for entry in per_role_scores)
        if rank[overall_risk] < max_role:
            return {
                "ok": False,
                "blocked_reason": (
                    f"overall_risk={overall_risk!r} is below the maximum "
                    f"per_role_scores risk; per-role scores require at least "
                    f"{[k for k, v in rank.items() if v == max_role][0]!r}"
                ),
                "risk_assessor": payload,
            }

    return {
        "ok": True,
        "risk_assessor": payload,
        "overall_risk": overall_risk,
    }
