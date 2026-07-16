"""api/shared/authority.py — compatibility adapter over the active vertical pack.

pitch-d2 (track D, plan/feature-enterprise-pitch-readiness-1.md).

This module is a thin adapter, not a registry. It:

- re-exports the ``AuthorityRow`` contract type from
  :mod:`api.shared.authority_contracts`
- exposes ``AUTHORITY`` as the *active pack's* authority mapping only —
  sourced from ``active_runtime().pack.authority``
- exposes the existing helpers (``authority_check``, ``delegate_for``,
  ``is_ooo``)

Canonical authority-row declarations live in
``verticals/agency/authority.py`` and ``verticals/telco/authority.py``
(shared roles such as ``delivery_lead`` are declared once in each pack that
legitimately uses them). This module contains no authority-row
declarations, no all-vertical registry, and does not parse the environment
itself — vertical selection happens once, while ``active_runtime()`` builds
the selected pack.

The ``authority_check`` callable mirrors the return shape of
``api.server.services.persona_responder._sandbox_authority_check`` —
``{"allowed": bool, "reason": str, "governing_rule_id": str | None}``
— so existing ``decision_policy`` blocks (which destructure the dict)
keep working unchanged.

H3 (cross-domain entanglement) is the work that actually consumes
``delegate_to`` + ``ooo_today`` to re-route an approval. D2 only
provides the data; the routing change lands separately.
"""
from __future__ import annotations

from api.shared.authority_contracts import AuthorityRow
from api.shared.vertical_loader import active_runtime


__all__ = [
    "AuthorityRow",
    "AUTHORITY",
    "authority_check",
    "delegate_for",
    "is_ooo",
]

AUTHORITY: dict[str, AuthorityRow] = dict(active_runtime().pack.authority)


def authority_check(
    role: str,
    action: str,
    value: float | None = None,
    category: str | None = None,
    business_unit: str | None = None,
    geography: str | None = None,
    requester_role: str | None = None,
) -> dict:
    """Data-driven authority resolution against ``AUTHORITY``.

    Returns the SAME shape as
    ``api.server.services.persona_responder._sandbox_authority_check``:
    ``{"allowed": bool, "reason": str, "governing_rule_id": str|None}``.

    Resolution order:
      1. role unknown → deny.
      2. action not in role's ``approval_actions`` → deny.
      3. ``value`` exceeds ``spend_limit_gbp`` → deny (escalation hint
         in the reason).
      4. otherwise → allow.

    ``business_unit``, ``geography`` and ``requester_role`` are accepted
    for parity with the original sandbox helper. They aren't used by
    the matrix today but allow callers to pass them through unchanged.
    """
    row = AUTHORITY.get(role)
    if row is None:
        return {
            "allowed": False,
            "reason": f"role '{role}' not in authority matrix",
            "governing_rule_id": None,
        }
    if action not in row.approval_actions:
        return {
            "allowed": False,
            "reason": (
                f"role '{role}' is not authorised for action '{action}' "
                f"(authorised: {list(row.approval_actions)})"
            ),
            "governing_rule_id": f"AUTH-{role}-deny-action",
        }
    if value is not None and value > row.spend_limit_gbp:
        return {
            "allowed": False,
            "reason": (
                f"value GBP {value} exceeds {role} spend limit "
                f"GBP {row.spend_limit_gbp}"
            ),
            "governing_rule_id": f"AUTH-{role}-spend-limit",
        }
    return {
        "allowed": True,
        "reason": (
            f"{role} authorised for {action} "
            f"(value={value}, category={category})"
        ),
        "governing_rule_id": f"AUTH-{role}-{action}",
    }


def delegate_for(role: str) -> str | None:
    """Return the OOO delegate for ``role`` if recorded; else None."""
    row = AUTHORITY.get(role)
    return row.delegate_to if row else None


def is_ooo(role: str) -> bool:
    """True iff ``role`` is hand-flagged OOO for the demo."""
    row = AUTHORITY.get(role)
    return bool(row and row.ooo_today)
