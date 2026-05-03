"""Graph-shape adapter for the fleet-perf-review-calibration-drafter validator.

In-graph validators return `{"ok": bool, ...}` so TrackedExecutor can emit
`validator.blocked` cleanly. Mirrors validate_classification_schema_node.py.
"""
from __future__ import annotations


_ALLOWED_VERDICT = {"drafted", "blocked"}
_ALLOWED_RATING = {
    "below-expectations",
    "meets-expectations",
    "exceeds-expectations",
    "outstanding",
}
_ALLOWED_DISTRIBUTION_FIT = {"fits", "over-cluster", "under-cluster"}


async def execute(input: dict) -> dict:
    payload = input.get("calibration_drafter") or {}

    verdict = payload.get("verdict")
    if verdict not in _ALLOWED_VERDICT:
        return {
            "ok": False,
            "blocked_reason": f"verdict must be one of {sorted(_ALLOWED_VERDICT)}; got {verdict!r}",
            "calibration_drafter": payload,
        }

    proposed_rating = payload.get("proposed_rating")
    if proposed_rating not in _ALLOWED_RATING:
        return {
            "ok": False,
            "blocked_reason": f"proposed_rating must be one of {sorted(_ALLOWED_RATING)}; got {proposed_rating!r}",
            "calibration_drafter": payload,
        }

    distribution_fit = payload.get("distribution_fit")
    if distribution_fit not in _ALLOWED_DISTRIBUTION_FIT:
        return {
            "ok": False,
            "blocked_reason": f"distribution_fit must be one of {sorted(_ALLOWED_DISTRIBUTION_FIT)}; got {distribution_fit!r}",
            "calibration_drafter": payload,
        }

    narrative = payload.get("narrative")
    if not isinstance(narrative, str) or not narrative.strip():
        return {
            "ok": False,
            "blocked_reason": "narrative must be a non-empty string",
            "calibration_drafter": payload,
        }

    grade_distribution_summary = payload.get("grade_distribution_summary")
    if not isinstance(grade_distribution_summary, dict):
        return {
            "ok": False,
            "blocked_reason": "grade_distribution_summary must be an object with grade + headroom_proposed_rating",
            "calibration_drafter": payload,
        }
    headroom = grade_distribution_summary.get("headroom_proposed_rating")
    if not isinstance(headroom, int) or isinstance(headroom, bool) or headroom < 0:
        return {
            "ok": False,
            "blocked_reason": "grade_distribution_summary.headroom_proposed_rating must be a non-negative integer",
            "calibration_drafter": payload,
        }

    calibration_history_summary = payload.get("calibration_history_summary")
    if not isinstance(calibration_history_summary, list):
        return {
            "ok": False,
            "blocked_reason": "calibration_history_summary must be a list of {cycle, rating} objects",
            "calibration_drafter": payload,
        }
    for entry in calibration_history_summary:
        if not isinstance(entry, dict) or not entry.get("cycle") or not entry.get("rating"):
            return {
                "ok": False,
                "blocked_reason": "calibration_history_summary entries must be objects carrying cycle + rating",
                "calibration_drafter": payload,
            }

    # Cross-field invariant: drafted iff proposed_rating + distribution_fit
    # are both populated AND narrative is non-empty.
    is_drafted = (
        proposed_rating in _ALLOWED_RATING
        and distribution_fit in _ALLOWED_DISTRIBUTION_FIT
        and bool(narrative.strip())
    )
    if (verdict == "drafted") != is_drafted:
        return {
            "ok": False,
            "blocked_reason": (
                f"verdict/draft inconsistent: verdict={verdict!r} but "
                f"proposed_rating={proposed_rating!r}, "
                f"distribution_fit={distribution_fit!r}, "
                f"narrative_present={bool(narrative.strip())!r}"
            ),
            "calibration_drafter": payload,
        }

    # Cross-field invariant: when distribution_fit is "over-cluster", the
    # proposed_rating must be one of the top two (the only ratings with
    # finite headroom). When distribution_fit is "under-cluster", the
    # proposed_rating must be one of the bottom two (where the
    # distribution norm forced a downgrade).
    if distribution_fit == "over-cluster" and proposed_rating not in {
        "exceeds-expectations", "outstanding",
    }:
        return {
            "ok": False,
            "blocked_reason": (
                f"distribution_fit/proposed_rating inconsistent: "
                f"over-cluster only applies to top ratings; "
                f"got proposed_rating={proposed_rating!r}"
            ),
            "calibration_drafter": payload,
        }
    if distribution_fit == "under-cluster" and proposed_rating not in {
        "below-expectations", "meets-expectations",
    }:
        return {
            "ok": False,
            "blocked_reason": (
                f"distribution_fit/proposed_rating inconsistent: "
                f"under-cluster only applies to bottom ratings; "
                f"got proposed_rating={proposed_rating!r}"
            ),
            "calibration_drafter": payload,
        }

    return {
        "ok": True,
        "calibration_drafter": payload,
        "verdict": verdict,
        "proposed_rating": proposed_rating,
        "distribution_fit": distribution_fit,
    }
