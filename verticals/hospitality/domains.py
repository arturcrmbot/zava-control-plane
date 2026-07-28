from __future__ import annotations

from api.shared.domain_contracts import Domain, HitlGate, Phase


def _gate(phase: str, event: str, persona: str) -> tuple[HitlGate, ...]:
    return (HitlGate(phase, event, persona),)


HOSPITALITY_DOMAINS: dict[str, Domain] = {
    # --- hero: hotel-operations ---
    "hotel-operations-recovery": Domain(
        workflow_type="hotel-operations-recovery",
        display_name="Hotel Operations Recovery",
        workflow_id_prefix="HOPREC",
        orchestrator_name="HotelOperationsRecoveryOrchestrator",
        operator_surface="hotel-operations",
        function="hotel-operations",
        phases=(
            Phase("Detect Operational Risk", "deterministic"),
            Phase("Assess Guest and Operational Impact", "agent"),
            Phase("Plan Network Recovery", "agent"),
            Phase("Evaluate Policy and Authority", "deterministic"),
            Phase("Approve Recovery Exception", "hitl"),
            Phase("Execute Recovery Plan", "deterministic"),
            Phase("Verify Recovery Outcome", "deterministic"),
        ),
        hitl_gates=_gate(
            "Approve Recovery Exception",
            "regional_operations_manager_decision",
            "regional_operations_manager",
        ),
        skills=("hotel-impact-assessor", "hotel-network-recovery-planner"),
        stub=False,
    ),
    # --- profiled: hotel-operations ---
    "room-readiness-coordination": Domain(
        workflow_type="room-readiness-coordination",
        display_name="Room Readiness Coordination",
        workflow_id_prefix="ROOMS",
        orchestrator_name="RoomReadinessCoordinationOrchestrator",
        operator_surface="hotel-operations",
        function="hotel-operations",
        phases=(
            Phase("Detect Readiness Gap", "deterministic"),
            Phase("Assess Housekeeping Capacity", "agent"),
            Phase("Approve Readiness Plan", "hitl"),
            Phase("Apply Room Readiness Plan", "deterministic"),
            Phase("Verify Room Readiness", "deterministic"),
        ),
        hitl_gates=_gate(
            "Approve Readiness Plan",
            "hotel_general_manager_decision",
            "hotel_general_manager",
        ),
        skills=("room-readiness-coordinator",),
        stub=False,
    ),
    # --- profiled: engineering-and-estates ---
    "asset-maintenance-response": Domain(
        workflow_type="asset-maintenance-response",
        display_name="Asset Maintenance Response",
        workflow_id_prefix="MAINT",
        orchestrator_name="AssetMaintenanceResponseOrchestrator",
        operator_surface="engineering-and-estates",
        function="engineering-and-estates",
        phases=(
            Phase("Detect Asset Alert", "deterministic"),
            Phase("Assess Maintenance Options", "agent"),
            Phase("Approve Work Order", "hitl"),
            Phase("Dispatch Maintenance Work Order", "deterministic"),
            Phase("Verify Asset Recovery", "deterministic"),
        ),
        hitl_gates=_gate(
            "Approve Work Order",
            "maintenance_manager_decision",
            "maintenance_manager",
        ),
        skills=("maintenance-response-planner",),
        stub=False,
    ),
    # --- profiled: guest-and-commercial ---
    "guest-service-recovery": Domain(
        workflow_type="guest-service-recovery",
        display_name="Guest Service Recovery",
        workflow_id_prefix="GREC",
        orchestrator_name="GuestServiceRecoveryOrchestrator",
        operator_surface="guest-and-commercial",
        function="guest-and-commercial",
        phases=(
            Phase("Detect Service Failure", "deterministic"),
            Phase("Assess Guest Impact", "agent"),
            Phase("Approve Recovery Action", "hitl"),
            Phase("Issue Guest Recovery Action", "deterministic"),
            Phase("Verify Guest Resolution", "deterministic"),
        ),
        hitl_gates=_gate(
            "Approve Recovery Action",
            "guest_recovery_manager_decision",
            "guest_recovery_manager",
        ),
        skills=("guest-recovery-advisor",),
        stub=False,
    ),
    "occupancy-pressure-response": Domain(
        workflow_type="occupancy-pressure-response",
        display_name="Occupancy Pressure Response",
        workflow_id_prefix="OCC",
        orchestrator_name="OccupancyPressureResponseOrchestrator",
        operator_surface="guest-and-commercial",
        function="guest-and-commercial",
        phases=(
            Phase("Detect Inventory Shortfall", "deterministic"),
            Phase("Assess Booking Exposure", "agent"),
            Phase("Approve Inventory Plan", "hitl"),
            Phase("Apply Booking Inventory Plan", "deterministic"),
            Phase("Verify Occupancy Outcome", "deterministic"),
        ),
        hitl_gates=_gate(
            "Approve Inventory Plan",
            "commercial_director_decision",
            "commercial_director",
        ),
        skills=("occupancy-pressure-advisor",),
        stub=False,
    ),
    # --- profiled: people-and-workforce ---
    "workforce-demand-balancing": Domain(
        workflow_type="workforce-demand-balancing",
        display_name="Workforce Demand Balancing",
        workflow_id_prefix="WRKFRC",
        orchestrator_name="WorkforceDemandBalancingOrchestrator",
        operator_surface="people-and-workforce",
        function="people-and-workforce",
        phases=(
            Phase("Detect Demand Imbalance", "deterministic"),
            Phase("Assess Shift Coverage", "agent"),
            Phase("Approve Shift Plan", "hitl"),
            Phase("Apply Workforce Shift Plan", "deterministic"),
            Phase("Verify Coverage Outcome", "deterministic"),
        ),
        hitl_gates=_gate(
            "Approve Shift Plan",
            "workforce_planning_manager_decision",
            "workforce_planning_manager",
        ),
        skills=("workforce-balancing-advisor",),
        stub=False,
    ),
    # --- profiled: food-and-beverage ---
    "food-and-beverage-readiness": Domain(
        workflow_type="food-and-beverage-readiness",
        display_name="Food and Beverage Readiness",
        workflow_id_prefix="FNBRD",
        orchestrator_name="FoodAndBeverageReadinessOrchestrator",
        operator_surface="food-and-beverage",
        function="food-and-beverage",
        phases=(
            Phase("Detect Service Demand Gap", "deterministic"),
            Phase("Assess Service Capacity", "agent"),
            Phase("Approve Service Plan", "hitl"),
            Phase("Apply Food Beverage Service Plan", "deterministic"),
            Phase("Verify Service Readiness", "deterministic"),
        ),
        hitl_gates=_gate(
            "Approve Service Plan",
            "food_beverage_operations_manager_decision",
            "food_beverage_operations_manager",
        ),
        skills=("food-service-readiness-advisor",),
        stub=False,
    ),
    # --- profiled: sustainability-and-utilities ---
    "energy-anomaly-response": Domain(
        workflow_type="energy-anomaly-response",
        display_name="Energy Anomaly Response",
        workflow_id_prefix="ENERGY",
        orchestrator_name="EnergyAnomalyResponseOrchestrator",
        operator_surface="sustainability-and-utilities",
        function="sustainability-and-utilities",
        phases=(
            Phase("Detect Energy Anomaly", "deterministic"),
            Phase("Assess Consumption Pattern", "agent"),
            Phase("Approve Control Plan", "hitl"),
            Phase("Apply Energy Control Plan", "deterministic"),
            Phase("Verify Energy Outcome", "deterministic"),
        ),
        hitl_gates=_gate(
            "Approve Control Plan",
            "sustainability_operations_manager_decision",
            "sustainability_operations_manager",
        ),
        skills=("energy-anomaly-advisor",),
        stub=False,
    ),
}
