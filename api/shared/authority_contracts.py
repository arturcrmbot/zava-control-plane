from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuthorityRow:
    role: str
    spend_limit_gbp: float
    approval_actions: tuple[str, ...]
    delegate_to: str | None
    ooo_today: bool = False
