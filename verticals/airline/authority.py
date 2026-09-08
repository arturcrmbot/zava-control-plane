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
    "engineering_duty_manager": AuthorityRow(
        role="engineering_duty_manager",
        spend_limit_gbp=200_000.0,
        approval_actions=(
            "engineering_duty_manager_decision",
            "airline.commit_aog_recovery",
        ),
        delegate_to=None,
    ),
    "network_operations_director": AuthorityRow(
        role="network_operations_director",
        spend_limit_gbp=300_000.0,
        approval_actions=(
            "network_operations_director_decision",
            "airline.commit_schedule_adjustment",
        ),
        delegate_to=None,
    ),
}
