from __future__ import annotations

from api.shared.agent_contracts import AgentRegistryEntry
from verticals.hospitality.authority import HOSPITALITY_AUTHORITY

# One agent per workflow; tool IDs prefixed hospitality_.
# scope_function matches a declared HOSPITALITY_FUNCTIONS key.

_WORKFLOW_TOOLS: dict[str, tuple[str, str]] = {
    "hotel-operations-recovery": ("hospitality_read_hotel_operations", "hotel-operations"),
    "room-readiness-coordination": ("hospitality_read_room_readiness", "hotel-operations"),
    "asset-maintenance-response": ("hospitality_read_asset_maintenance", "engineering-and-estates"),
    "guest-service-recovery": ("hospitality_read_guest_recovery", "guest-and-commercial"),
    "occupancy-pressure-response": ("hospitality_read_occupancy_pressure", "guest-and-commercial"),
    "workforce-demand-balancing": ("hospitality_read_workforce_demand", "people-and-workforce"),
    "food-and-beverage-readiness": ("hospitality_read_food_beverage_readiness", "food-and-beverage"),
    "energy-anomaly-response": ("hospitality_read_energy_anomaly", "sustainability-and-utilities"),
}

# Maps each workflow to the authority role whose spend_limit_gbp caps that agent.
_WORKFLOW_AUTHORITY_ROLE: dict[str, str] = {
    "hotel-operations-recovery": "regional_operations_manager",
    "room-readiness-coordination": "hotel_general_manager",
    "asset-maintenance-response": "maintenance_manager",
    "guest-service-recovery": "guest_recovery_manager",
    "occupancy-pressure-response": "commercial_director",
    "workforce-demand-balancing": "workforce_planning_manager",
    "food-and-beverage-readiness": "food_beverage_operations_manager",
    "energy-anomaly-response": "sustainability_operations_manager",
}

HOSPITALITY_AGENTS: dict[str, AgentRegistryEntry] = {
    workflow_id: AgentRegistryEntry(
        agent_id=workflow_id,
        allowed_tools=(tool,),
        max_value_gbp=HOSPITALITY_AUTHORITY[_WORKFLOW_AUTHORITY_ROLE[workflow_id]].spend_limit_gbp,
        reversible_only=True,
        scope_function=scope_fn,
        description=f"Hospitality agent for {workflow_id.replace('-', ' ')}.",
    )
    for workflow_id, (tool, scope_fn) in _WORKFLOW_TOOLS.items()
}
