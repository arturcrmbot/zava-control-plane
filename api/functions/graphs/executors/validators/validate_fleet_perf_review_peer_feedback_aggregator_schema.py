"""Graph-shape adapter for the fleet-perf-review-peer-feedback-aggregator validator.

In-graph validators return `{"ok": bool, ...}` so TrackedExecutor can emit
`validator.blocked` cleanly. Mirrors validate_classification_schema_node.py.
"""
from __future__ import annotations


_ALLOWED_VERDICT = {"aggregated", "blocked"}


async def execute(input: dict) -> dict:
    payload = input.get("peer_feedback_aggregator") or {}

    verdict = payload.get("verdict")
    if verdict not in _ALLOWED_VERDICT:
        return {
            "ok": False,
            "blocked_reason": f"verdict must be one of {sorted(_ALLOWED_VERDICT)}; got {verdict!r}",
            "peer_feedback_aggregator": payload,
        }

    peer_review_count = payload.get("peer_review_count")
    if not isinstance(peer_review_count, int) or isinstance(peer_review_count, bool) or peer_review_count < 0:
        return {
            "ok": False,
            "blocked_reason": f"peer_review_count must be a non-negative integer; got {peer_review_count!r}",
            "peer_feedback_aggregator": payload,
        }

    peer_reviews = payload.get("peer_reviews")
    if not isinstance(peer_reviews, list):
        return {
            "ok": False,
            "blocked_reason": "peer_reviews must be a list of {review_id, reviewer_id, relationship, sentiment, score_out_of_5} objects",
            "peer_feedback_aggregator": payload,
        }
    for entry in peer_reviews:
        if not isinstance(entry, dict) or not entry.get("review_id"):
            return {
                "ok": False,
                "blocked_reason": "peer_reviews entries must be objects carrying a review_id",
                "peer_feedback_aggregator": payload,
            }

    reporting_line = payload.get("reporting_line")
    if not isinstance(reporting_line, dict) or not reporting_line.get("manager_id"):
        return {
            "ok": False,
            "blocked_reason": "reporting_line must be an object carrying manager_id",
            "peer_feedback_aggregator": payload,
        }

    okr_results = payload.get("okr_results")
    if not isinstance(okr_results, dict):
        return {
            "ok": False,
            "blocked_reason": "okr_results must be an object with objective_count + overall_achievement_pct",
            "peer_feedback_aggregator": payload,
        }
    objective_count = okr_results.get("objective_count")
    if not isinstance(objective_count, int) or isinstance(objective_count, bool) or objective_count < 0:
        return {
            "ok": False,
            "blocked_reason": "okr_results.objective_count must be a non-negative integer",
            "peer_feedback_aggregator": payload,
        }
    overall_pct = okr_results.get("overall_achievement_pct")
    if not isinstance(overall_pct, (int, float)) or isinstance(overall_pct, bool):
        return {
            "ok": False,
            "blocked_reason": "okr_results.overall_achievement_pct must be a number",
            "peer_feedback_aggregator": payload,
        }

    # Cross-field invariant: peer_review_count must equal len(peer_reviews).
    if peer_review_count != len(peer_reviews):
        return {
            "ok": False,
            "blocked_reason": (
                f"peer_review_count={peer_review_count!r} disagrees with "
                f"len(peer_reviews)={len(peer_reviews)}"
            ),
            "peer_feedback_aggregator": payload,
        }

    # Cross-field invariant: aggregated iff at least one peer review AND at
    # least one OKR objective AND a non-empty reporting line.
    is_aggregated = (
        peer_review_count >= 1
        and objective_count >= 1
        and bool(reporting_line.get("manager_id"))
    )
    if (verdict == "aggregated") != is_aggregated:
        return {
            "ok": False,
            "blocked_reason": (
                f"verdict/evidence inconsistent: verdict={verdict!r} but "
                f"peer_review_count={peer_review_count!r}, "
                f"objective_count={objective_count!r}, "
                f"reporting_line.manager_id={reporting_line.get('manager_id')!r}"
            ),
            "peer_feedback_aggregator": payload,
        }

    return {
        "ok": True,
        "peer_feedback_aggregator": payload,
        "verdict": verdict,
        "peer_review_count": peer_review_count,
    }
