from __future__ import annotations

from api.shared.all_authority import AuthorityRow
from api.shared.vertical_loader import active_runtime

__all__ = [
    "AUTHORITY",
    "AuthorityRow",
    "authority_check",
    "delegate_for",
    "is_ooo",
]


AUTHORITY = active_runtime().pack.authority


def authority_check(
    role: str,
    action: str,
    value: float | None = None,
    category: str | None = None,
    business_unit: str | None = None,
    geography: str | None = None,
    requester_role: str | None = None,
) -> dict:
    del business_unit, geography, requester_role
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
    row = AUTHORITY.get(role)
    return row.delegate_to if row else None


def is_ooo(role: str) -> bool:
    row = AUTHORITY.get(role)
    return bool(row and row.ooo_today)
