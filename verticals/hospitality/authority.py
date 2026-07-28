from __future__ import annotations

from api.shared.authority_contracts import AuthorityRow

# Approval actions align with the design mapping.
# Spend limits are synthetic demo assumptions only.

HOSPITALITY_AUTHORITY: dict[str, AuthorityRow] = {
    # --- hotel-operations hierarchy ---
    "hotel_general_manager": AuthorityRow(
        role="hotel_general_manager",
        spend_limit_gbp=2_500.0,
        approval_actions=("hotel_general_manager_decision", "apply_room_readiness_plan"),
        delegate_to="regional_operations_manager",
    ),
    "regional_operations_manager": AuthorityRow(
        role="regional_operations_manager",
        spend_limit_gbp=15_000.0,
        approval_actions=("regional_operations_manager_decision", "execute_hotel_recovery"),
        delegate_to="hotel_operations_director",
    ),
    "hotel_operations_director": AuthorityRow(
        role="hotel_operations_director",
        spend_limit_gbp=150_000.0,
        approval_actions=("hotel_operations_director_decision",),
        delegate_to=None,
    ),
    # --- engineering-and-estates hierarchy ---
    "maintenance_manager": AuthorityRow(
        role="maintenance_manager",
        spend_limit_gbp=10_000.0,
        approval_actions=("maintenance_manager_decision", "dispatch_maintenance_work_order"),
        delegate_to="estates_director",
    ),
    "estates_director": AuthorityRow(
        role="estates_director",
        spend_limit_gbp=250_000.0,
        approval_actions=("estates_director_decision",),
        delegate_to=None,
    ),
    # --- guest-and-commercial hierarchy ---
    "guest_recovery_manager": AuthorityRow(
        role="guest_recovery_manager",
        spend_limit_gbp=2_000.0,
        approval_actions=("guest_recovery_manager_decision", "issue_guest_recovery_action"),
        delegate_to="commercial_director",
    ),
    "commercial_director": AuthorityRow(
        role="commercial_director",
        spend_limit_gbp=100_000.0,
        approval_actions=("commercial_director_decision", "apply_booking_inventory_plan"),
        delegate_to=None,
    ),
    # --- people-and-workforce hierarchy ---
    "workforce_planning_manager": AuthorityRow(
        role="workforce_planning_manager",
        spend_limit_gbp=5_000.0,
        approval_actions=("workforce_planning_manager_decision", "apply_workforce_shift_plan"),
        delegate_to="people_operations_director",
    ),
    "people_operations_director": AuthorityRow(
        role="people_operations_director",
        spend_limit_gbp=50_000.0,
        approval_actions=("people_operations_director_decision",),
        delegate_to=None,
    ),
    # --- food-and-beverage ---
    "food_beverage_operations_manager": AuthorityRow(
        role="food_beverage_operations_manager",
        spend_limit_gbp=5_000.0,
        approval_actions=(
            "food_beverage_operations_manager_decision",
            "apply_food_beverage_service_plan",
        ),
        delegate_to=None,
    ),
    # --- sustainability-and-utilities hierarchy ---
    "sustainability_operations_manager": AuthorityRow(
        role="sustainability_operations_manager",
        spend_limit_gbp=25_000.0,
        approval_actions=(
            "sustainability_operations_manager_decision",
            "apply_energy_control_plan",
        ),
        delegate_to="sustainability_director",
    ),
    "sustainability_director": AuthorityRow(
        role="sustainability_director",
        spend_limit_gbp=100_000.0,
        approval_actions=("sustainability_director_decision",),
        delegate_to=None,
    ),
}
