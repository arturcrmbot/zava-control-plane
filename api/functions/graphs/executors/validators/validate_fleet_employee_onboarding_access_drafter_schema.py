"""Graph-shape adapter for the fleet-employee-onboarding-access-drafter validator.

In-graph validators return `{"ok": bool, ...}` so TrackedExecutor can emit
`validator.blocked` cleanly. Mirrors validate_classification_schema_node.py.
"""
from __future__ import annotations


_ALLOWED_VERDICT = {"draft-ready", "draft-blocked"}


async def execute(input: dict) -> dict:
    payload = input.get("access_drafter") or {}

    verdict = payload.get("verdict")
    if verdict not in _ALLOWED_VERDICT:
        return {
            "ok": False,
            "blocked_reason": f"verdict must be one of {sorted(_ALLOWED_VERDICT)}; got {verdict!r}",
            "access_drafter": payload,
        }

    proposed_bundle = payload.get("proposed_bundle")
    if not isinstance(proposed_bundle, list):
        return {
            "ok": False,
            "blocked_reason": "proposed_bundle must be a list of permission strings",
            "access_drafter": payload,
        }

    sod_conflicts = payload.get("sod_conflicts")
    if not isinstance(sod_conflicts, list):
        return {
            "ok": False,
            "blocked_reason": "sod_conflicts must be a list (empty if none)",
            "access_drafter": payload,
        }

    template_default_size = payload.get("template_default_size")
    if not isinstance(template_default_size, int):
        return {
            "ok": False,
            "blocked_reason": "template_default_size must be an integer",
            "access_drafter": payload,
        }

    selected_templates = payload.get("selected_templates")
    if not isinstance(selected_templates, list):
        return {
            "ok": False,
            "blocked_reason": "selected_templates must be a list of template_id strings",
            "access_drafter": payload,
        }

    # Cross-field invariant: draft-ready iff at least one template selected
    # AND proposed_bundle is non-empty.
    is_ready = bool(selected_templates) and bool(proposed_bundle)
    if (verdict == "draft-ready") != is_ready:
        return {
            "ok": False,
            "blocked_reason": (
                f"verdict/bundle inconsistent: verdict={verdict!r} but "
                f"selected_templates={len(selected_templates)} and "
                f"proposed_bundle={len(proposed_bundle)}"
            ),
            "access_drafter": payload,
        }

    return {
        "ok": True,
        "access_drafter": payload,
        "verdict": verdict,
    }
