from __future__ import annotations

from api.shared.persona_contracts import Persona


def _persona(role: str, label: str, event: str, colour: str) -> Persona:
    return Persona(
        role=role,
        archetype="approver",
        scope_function="commercial",
        workflow_label=label,
        external_event_default=event,
        default_authority_band="policy-bound",
        uses_authority_mcp=True,
        description=f"{label}; reviews evidenced hospitality operational exceptions.",
        display_color=colour,
    )


HOSPITALITY_PERSONAS: dict[str, Persona] = {
    # hotel-operations hierarchy
    "hotel_general_manager": _persona(
        "hotel_general_manager",
        "Hotel General Manager",
        "hotel_general_manager_decision",
        "#0369a1",
    ),
    "regional_operations_manager": _persona(
        "regional_operations_manager",
        "Regional Operations Manager",
        "regional_operations_manager_decision",
        "#0284c7",
    ),
    "hotel_operations_director": _persona(
        "hotel_operations_director",
        "Hotel Operations Director",
        "hotel_operations_director_decision",
        "#075985",
    ),
    # engineering-and-estates hierarchy
    "maintenance_manager": _persona(
        "maintenance_manager",
        "Maintenance Manager",
        "maintenance_manager_decision",
        "#b45309",
    ),
    "estates_director": _persona(
        "estates_director",
        "Estates Director",
        "estates_director_decision",
        "#92400e",
    ),
    # guest-and-commercial hierarchy
    "guest_recovery_manager": _persona(
        "guest_recovery_manager",
        "Guest Recovery Manager",
        "guest_recovery_manager_decision",
        "#be123c",
    ),
    "commercial_director": _persona(
        "commercial_director",
        "Commercial Director",
        "commercial_director_decision",
        "#9f1239",
    ),
    # people-and-workforce hierarchy
    "workforce_planning_manager": _persona(
        "workforce_planning_manager",
        "Workforce Planning Manager",
        "workforce_planning_manager_decision",
        "#6d28d9",
    ),
    "people_operations_director": _persona(
        "people_operations_director",
        "People Operations Director",
        "people_operations_director_decision",
        "#5b21b6",
    ),
    # food-and-beverage
    "food_beverage_operations_manager": _persona(
        "food_beverage_operations_manager",
        "Food & Beverage Operations Manager",
        "food_beverage_operations_manager_decision",
        "#15803d",
    ),
    # sustainability-and-utilities hierarchy
    "sustainability_operations_manager": _persona(
        "sustainability_operations_manager",
        "Sustainability Operations Manager",
        "sustainability_operations_manager_decision",
        "#0f766e",
    ),
    "sustainability_director": _persona(
        "sustainability_director",
        "Sustainability Director",
        "sustainability_director_decision",
        "#115e59",
    ),
}
