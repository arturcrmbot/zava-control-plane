"""Canonical Decision verdict vocabulary.

The graph today carries both `approve` (live event-bus path) and
`approved` (DataPack seed) as distinct verdict values. This module is
the single source of truth — every projection, the seed pack, and the
HTTP read layer call ``canonical_verdict`` so the column has one shape.
"""
from __future__ import annotations

VERDICTS: frozenset[str] = frozenset({
    "approve",
    "reject",
    "escalate",
    "defer",
    "request_changes",
    "partial",
    "void",
    # Policy verdicts written by `policy_set` workflows in
    # autonomous-domain-insights v1 (persona summary_policy → CEO approval).
    "freeze",
    "unfreeze",
    "cap",
})

_ALIASES: dict[str, str] = {
    "approved": "approve",
    "ok": "approve",
    "rejected": "reject",
    "deny": "reject",
    "denied": "reject",
    "escalated": "escalate",
    "deferred": "defer",
    "changes_requested": "request_changes",
    "voided": "void",
    # Past-tense aliases for the policy verdicts above.
    "frozen": "freeze",
    "unfrozen": "unfreeze",
    "capped": "cap",
}


def canonical_verdict(raw: str | None) -> str:
    if raw is None:
        return ""
    s = raw.strip().lower()
    return _ALIASES.get(s, s)


def is_valid_verdict(s: str | None) -> bool:
    return s in VERDICTS
