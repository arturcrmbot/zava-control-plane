from __future__ import annotations

from api.shared.authority_contracts import AuthorityRow


AIRLINE_AUTHORITY: dict[str, AuthorityRow] = {
    "duty_operations_manager": AuthorityRow(
        role="duty_operations_manager",
        spend_limit_gbp=150_000.0,
        approval_actions=(
            "duty_operations_manager_decision",
            "airline.commit_recovery_plan",
        ),
        delegate_to=None,
    ),
}
