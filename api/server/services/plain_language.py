"""Plain-language translator for autonomous-org Decision and proposed-action payloads.

v1.1 polish (spec §9 item g). Maps technical fields (verdict, scope,
expiry_days, persona_role, decided_on) to buyer-comprehensible strings
("CFO Policy: Freeze Aurora POs (14 days)") used in the WorkflowDrawer
insight panel and the live ticker.
"""
from __future__ import annotations

from typing import Any

_VERDICT_LABEL: dict[str, str] = {
    "approve": "Approved",
    "reject": "Rejected",
    "escalate": "Escalated",
    "defer": "Deferred",
    "request_changes": "Changes requested",
    "freeze": "Freeze",
    "unfreeze": "Unfreeze",
    "cap": "Cap",
    "void": "Voided",
    "partial": "Partial approval",
}

_PERSONA_TITLE: dict[str, str] = {
    "cfo": "CFO",
    "ceo": "CEO",
    "controller": "Controller",
    "ap_clerk": "AP Clerk",
    "treasurer": "Treasurer",
    "hr_director": "HR Director",
    "sourcing_lead": "Sourcing Lead",
    "it_admin_director": "IT Director",
    "dpo": "Data Protection Officer",
    "cpo": "Chief People Officer",
    "ecd": "Executive Creative Director",
    "gc": "General Counsel",
    # Default falls back to title-cased role
}

_SCOPE_LABEL: dict[str, str] = {
    "po": "purchase orders",
    "vendor_po": "vendor POs",
    "hiring": "new hires",
    "fx": "FX hedges",
    "expense": "expenses",
    "access": "access requests",
    "data": "data access",
}

_ENTITY_PRETTY_PREFIX: dict[str, str] = {
    "BRAND-": "",            # Brand IDs already read like names
    "ORG-vendor-": "",       # Vendor names follow the prefix
    "FX:": "",               # FX pair already reads cleanly
    "DEPT:": "",             # Department names already read
}


def persona_title(role: str | None) -> str:
    if not role:
        return ""
    lookup = _PERSONA_TITLE.get(role.lower())
    if lookup:
        return lookup
    return role.replace("_", " ").title()


def verdict_label(verdict: str | None) -> str:
    if not verdict:
        return ""
    return _VERDICT_LABEL.get(verdict.lower(), verdict.replace("_", " ").title())


def scope_label(scope: str | None) -> str:
    if not scope:
        return ""
    return _SCOPE_LABEL.get(scope.lower(), scope.replace("_", " "))


def pretty_entity_id(eid: str | None) -> str:
    """Return a human-friendly form of a synthetic id like 'BRAND-aurora' -> 'Aurora'."""
    if not eid:
        return ""
    for prefix, _ in _ENTITY_PRETTY_PREFIX.items():
        if eid.startswith(prefix):
            tail = eid[len(prefix):]
            if prefix in ("FX:", "DEPT:"):
                return tail
            return tail.replace("-", " ").title()
    return eid


def pretty_action(action: dict[str, Any]) -> str:
    """Render a proposed_action dict as a one-line buyer-friendly string.

    Example output: "Freeze Aurora purchase orders (14 days)"
    Falls back to the action's "label" field when components are missing.
    """
    verdict = verdict_label(action.get("verdict"))
    scope = scope_label((action.get("attributes") or {}).get("scope"))
    targets = action.get("decided_on") or []
    target_str = ", ".join(pretty_entity_id(t) for t in targets[:3])
    expiry = (action.get("attributes") or {}).get("expiry_days")
    parts = []
    if verdict:
        parts.append(verdict)
    if target_str:
        parts.append(target_str)
    if scope:
        parts.append(scope)
    label = " ".join(parts).strip()
    if expiry:
        label += " (" + str(expiry) + " days)"
    return label or str(action.get("label") or "")


def pretty_decision(d: dict[str, Any]) -> str:
    """Render a Decision dict (from the ticker route) as 'CFO Policy: Freeze Aurora purchase orders (14d)'."""
    persona = persona_title(d.get("persona_role"))
    verdict = verdict_label(d.get("verdict"))
    targets = d.get("decided_on") or []
    target_str = ", ".join(pretty_entity_id(t) for t in targets[:3])
    phase = d.get("phase") or ""
    expiry = (d.get("attributes") or {}).get("expiry_days") if isinstance(d.get("attributes"), dict) else None

    if phase == "policy_set":
        prefix = persona + " Policy" if persona else "Policy"
        scope = scope_label((d.get("attributes") or {}).get("scope")) if isinstance(d.get("attributes"), dict) else ""
        tail = " (" + str(expiry) + "d)" if expiry else ""
        body_parts = [verdict]
        if target_str:
            body_parts.append(target_str)
        if scope:
            body_parts.append(scope)
        body = " ".join(p for p in body_parts if p)
        return prefix + ": " + body + tail

    if phase:
        # e.g. "AP Clerk approved INV-7841"
        return (persona + " " if persona else "") + verdict.lower() + (" " + target_str if target_str else "")

    return verdict + (" " + target_str if target_str else "")
