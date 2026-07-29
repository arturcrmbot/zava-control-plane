"""Immutable process profiles binding Hospitality domains to world runtime.

One profile per workflow in ``HOSPITALITY_DOMAINS``. Each profile is the
single place that joins a domain (phases, HITL gate, skills) to the shared
world contracts (sensor, objective, typed command, success event) and to the
Durable orchestrator that runs it.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HospitalityProcessProfile:
    workflow_type: str
    display_name: str
    function: str
    sensor_id: str
    objective_type: str
    command_type: str
    success_event: str
    orchestrator: str
    prefix: str
    skill: str
    hitl_persona: str | None
    hitl_event: str | None
    maturity: str = "standard"


HOSPITALITY_PROCESS_PROFILES: dict[str, HospitalityProcessProfile] = {
    "hotel-operations-recovery": HospitalityProcessProfile(
        workflow_type="hotel-operations-recovery",
        display_name="Hotel Operations Recovery",
        function="hotel-operations",
        sensor_id="sensor:hotel_operations_risk",
        objective_type="hotel_operations_recovery",
        command_type="hotel.recovery.execute",
        success_event="hotel.recovery.executed",
        orchestrator="HotelOperationsRecoveryOrchestrator",
        prefix="hoprec",
        skill="hotel-network-recovery-planner",
        hitl_persona="regional_operations_manager",
        hitl_event="regional_operations_manager_decision",
        maturity="hero",
    ),
    "room-readiness-coordination": HospitalityProcessProfile(
        workflow_type="room-readiness-coordination",
        display_name="Room Readiness Coordination",
        function="hotel-operations",
        sensor_id="sensor:room_readiness_gap",
        objective_type="room_readiness_coordination",
        command_type="room.readiness-plan.apply",
        success_event="room.readiness-plan.applied",
        orchestrator="RoomReadinessCoordinationOrchestrator",
        prefix="rooms",
        skill="room-readiness-coordinator",
        hitl_persona="hotel_general_manager",
        hitl_event="hotel_general_manager_decision",
    ),
    "asset-maintenance-response": HospitalityProcessProfile(
        workflow_type="asset-maintenance-response",
        display_name="Asset Maintenance Response",
        function="engineering-and-estates",
        sensor_id="sensor:asset_fault_alert",
        objective_type="asset_maintenance_response",
        command_type="maintenance.work-order.dispatch",
        success_event="maintenance.work-order.dispatched",
        orchestrator="AssetMaintenanceResponseOrchestrator",
        prefix="maint",
        skill="maintenance-response-planner",
        hitl_persona="maintenance_manager",
        hitl_event="maintenance_manager_decision",
    ),
    "guest-service-recovery": HospitalityProcessProfile(
        workflow_type="guest-service-recovery",
        display_name="Guest Service Recovery",
        function="guest-and-commercial",
        sensor_id="sensor:guest_service_failure",
        objective_type="guest_service_recovery",
        command_type="guest.recovery-action.issue",
        success_event="guest.recovery-action.issued",
        orchestrator="GuestServiceRecoveryOrchestrator",
        prefix="grec",
        skill="guest-recovery-advisor",
        hitl_persona="guest_recovery_manager",
        hitl_event="guest_recovery_manager_decision",
    ),
    "occupancy-pressure-response": HospitalityProcessProfile(
        workflow_type="occupancy-pressure-response",
        display_name="Occupancy Pressure Response",
        function="guest-and-commercial",
        sensor_id="sensor:occupancy_pressure",
        objective_type="occupancy_pressure_response",
        command_type="booking.inventory-plan.apply",
        success_event="booking.inventory-plan.applied",
        orchestrator="OccupancyPressureResponseOrchestrator",
        prefix="occ",
        skill="occupancy-pressure-advisor",
        hitl_persona="commercial_director",
        hitl_event="commercial_director_decision",
    ),
    "workforce-demand-balancing": HospitalityProcessProfile(
        workflow_type="workforce-demand-balancing",
        display_name="Workforce Demand Balancing",
        function="people-and-workforce",
        sensor_id="sensor:workforce_demand_imbalance",
        objective_type="workforce_demand_balancing",
        command_type="workforce.shift-plan.apply",
        success_event="workforce.shift-plan.applied",
        orchestrator="WorkforceDemandBalancingOrchestrator",
        prefix="wrkfrc",
        skill="workforce-balancing-advisor",
        hitl_persona="workforce_planning_manager",
        hitl_event="workforce_planning_manager_decision",
    ),
    "food-and-beverage-readiness": HospitalityProcessProfile(
        workflow_type="food-and-beverage-readiness",
        display_name="Food and Beverage Readiness",
        function="food-and-beverage",
        sensor_id="sensor:food_service_gap",
        objective_type="food_and_beverage_readiness",
        command_type="food-beverage.service-plan.apply",
        success_event="food-beverage.service-plan.applied",
        orchestrator="FoodAndBeverageReadinessOrchestrator",
        prefix="fnbrd",
        skill="food-service-readiness-advisor",
        hitl_persona="food_beverage_operations_manager",
        hitl_event="food_beverage_operations_manager_decision",
    ),
    "energy-anomaly-response": HospitalityProcessProfile(
        workflow_type="energy-anomaly-response",
        display_name="Energy Anomaly Response",
        function="sustainability-and-utilities",
        sensor_id="sensor:energy_anomaly",
        objective_type="energy_anomaly_response",
        command_type="energy.control-plan.apply",
        success_event="energy.control-plan.applied",
        orchestrator="EnergyAnomalyResponseOrchestrator",
        prefix="energy",
        skill="energy-anomaly-advisor",
        hitl_persona="sustainability_operations_manager",
        hitl_event="sustainability_operations_manager_decision",
    ),
}
