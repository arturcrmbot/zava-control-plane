"""Graph-shape adapter for the fleet-it-access-request-rbac-resolver validator.

In-graph validators return `{"ok": bool, ...}` so TrackedExecutor can emit
`validator.blocked` cleanly. Mirrors validate_classification_schema_node.py.
"""
from __future__ import annotations


_ALLOWED_VERDICT = {"resolved", "blocked"}


async def execute(input: dict) -> dict:
    payload = input.get("rbac_resolver") or {}

    verdict = payload.get("verdict")
    if verdict not in _ALLOWED_VERDICT:
        return {
            "ok": False,
            "blocked_reason": f"verdict must be one of {sorted(_ALLOWED_VERDICT)}; got {verdict!r}",
            "rbac_resolver": payload,
        }

    proposed_bundle = payload.get("proposed_bundle")
    if not isinstance(proposed_bundle, list):
        return {
            "ok": False,
            "blocked_reason": "proposed_bundle must be a list of permission strings",
            "rbac_resolver": payload,
        }

    sod_conflicts = payload.get("sod_conflicts")
    if not isinstance(sod_conflicts, list):
        return {
            "ok": False,
            "blocked_reason": "sod_conflicts must be a list (empty if none)",
            "rbac_resolver": payload,
        }

    selected_templates = payload.get("selected_templates")
    if not isinstance(selected_templates, list):
        return {
            "ok": False,
            "blocked_reason": "selected_templates must be a list of template_id strings",
            "rbac_resolver": payload,
        }

    template_default_size = payload.get("template_default_size")
    if not isinstance(template_default_size, int):
        return {
            "ok": False,
            "blocked_reason": "template_default_size must be an integer",
            "rbac_resolver": payload,
        }

    # Cross-field invariant: resolved iff at least one template selected
    # AND proposed_bundle is non-empty.
    is_resolved = bool(selected_templates) and bool(proposed_bundle)
    if (verdict == "resolved") != is_resolved:
        return {
            "ok": False,
            "blocked_reason": (
                f"verdict/bundle inconsistent: verdict={verdict!r} but "
                f"selected_templates={len(selected_templates)} and "
                f"proposed_bundle={len(proposed_bundle)}"
            ),
            "rbac_resolver": payload,
        }

    return {
        "ok": True,
        "rbac_resolver": payload,
        "verdict": verdict,
        "sod_conflicts": sod_conflicts,
    }
