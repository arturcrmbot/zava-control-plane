"""Graph-shape adapter for the fleet-vendor-kyc-ubo-resolver validator.

In-graph validators return `{"ok": bool, ...}` so TrackedExecutor can emit
`validator.blocked` cleanly. Mirrors validate_classification_schema_node.py.
"""
from __future__ import annotations


async def execute(input: dict) -> dict:
    payload = input.get("ubo_resolver") or {}

    ubos_count = payload.get("ubos_count")
    if not isinstance(ubos_count, int) or ubos_count < 0:
        return {
            "ok": False,
            "blocked_reason": f"ubos_count must be a non-negative int; got {ubos_count!r}",
            "ubo_resolver": payload,
        }

    top_three = payload.get("top_three_by_ownership")
    if not isinstance(top_three, list):
        return {
            "ok": False,
            "blocked_reason": "top_three_by_ownership must be a list",
            "ubo_resolver": payload,
        }
    expected_top_len = min(3, ubos_count)
    if len(top_three) != expected_top_len:
        return {
            "ok": False,
            "blocked_reason": (
                f"top_three_by_ownership length must be min(3, ubos_count)={expected_top_len}; "
                f"got {len(top_three)}"
            ),
            "ubo_resolver": payload,
        }

    ubo_sanctions_hits = payload.get("ubo_sanctions_hits")
    if not isinstance(ubo_sanctions_hits, list):
        return {
            "ok": False,
            "blocked_reason": "ubo_sanctions_hits must be a list (empty if clean)",
            "ubo_resolver": payload,
        }

    adverse_media_hits = payload.get("adverse_media_hits")
    if not isinstance(adverse_media_hits, list):
        return {
            "ok": False,
            "blocked_reason": "adverse_media_hits must be a list (empty if clean)",
            "ubo_resolver": payload,
        }

    return {
        "ok": True,
        "ubo_resolver": payload,
        "ubo_sanctions_hits": ubo_sanctions_hits,
        "adverse_media_hits": adverse_media_hits,
    }
