from __future__ import annotations

from api.shared.function_contracts import Function, PersonaTree

HOSPITALITY_FUNCTIONS: dict[str, Function] = {
    "hotel-operations": Function(
        name="hotel-operations",
        display="Hotel Operations",
        operator_surface="hotel-operations",
        owns_domains=(
            "hotel-operations-recovery",
            "room-readiness-coordination",
        ),
        ambient_agents=(),
        kpis=(
            "sellable-rooms",
            "protected-arrivals",
            "room-readiness-sla",
            "recovery-time",
        ),
        persona_hierarchy=PersonaTree(
            role="hotel_operations_director",
            manages=(
                PersonaTree(
                    role="regional_operations_manager",
                    manages=(PersonaTree(role="hotel_general_manager"),),
                ),
            ),
        ),
    ),
    "engineering-and-estates": Function(
        name="engineering-and-estates",
        display="Engineering & Estates",
        operator_surface="engineering-and-estates",
        owns_domains=("asset-maintenance-response",),
        ambient_agents=(),
        kpis=(
            "asset-uptime",
            "rooms-out-of-service",
            "first-time-fix",
            "maintenance-cost",
        ),
        persona_hierarchy=PersonaTree(
            role="estates_director",
            manages=(PersonaTree(role="maintenance_manager"),),
        ),
    ),
    "guest-and-commercial": Function(
        name="guest-and-commercial",
        display="Guest & Commercial",
        operator_surface="guest-and-commercial",
        owns_domains=(
            "guest-service-recovery",
            "occupancy-pressure-response",
        ),
        ambient_agents=(),
        kpis=(
            "arrival-fulfilment",
            "relocation-rate",
            "guest-disruption",
            "revenue-at-risk",
        ),
        persona_hierarchy=PersonaTree(
            role="commercial_director",
            manages=(PersonaTree(role="guest_recovery_manager"),),
        ),
    ),
    "people-and-workforce": Function(
        name="people-and-workforce",
        display="People & Workforce",
        operator_surface="people-and-workforce",
        owns_domains=("workforce-demand-balancing",),
        ambient_agents=(),
        kpis=(
            "labour-coverage",
            "overtime",
            "productivity",
            "unfilled-critical-shifts",
        ),
        persona_hierarchy=PersonaTree(
            role="people_operations_director",
            manages=(PersonaTree(role="workforce_planning_manager"),),
        ),
    ),
    "food-and-beverage": Function(
        name="food-and-beverage",
        display="Food & Beverage",
        operator_surface="food-and-beverage",
        owns_domains=("food-and-beverage-readiness",),
        ambient_agents=(),
        kpis=(
            "service-capacity",
            "forecast-coverage",
            "waste-exposure",
            "guest-attach-readiness",
        ),
        persona_hierarchy=PersonaTree(role="food_beverage_operations_manager"),
    ),
    "sustainability-and-utilities": Function(
        name="sustainability-and-utilities",
        display="Sustainability & Utilities",
        operator_surface="sustainability-and-utilities",
        owns_domains=("energy-anomaly-response",),
        ambient_agents=(),
        kpis=(
            "energy-intensity",
            "anomaly-duration",
            "avoided-consumption",
            "comfort-exceptions",
        ),
        persona_hierarchy=PersonaTree(
            role="sustainability_director",
            manages=(PersonaTree(role="sustainability_operations_manager"),),
        ),
    ),
}
