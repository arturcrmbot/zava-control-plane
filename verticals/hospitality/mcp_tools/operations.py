"""The eight registered read-only Hospitality operations tools.

Tool names are exactly those declared on ``HOSPITALITY_AGENTS``; each returns
the supplied versioned evidence, never a mutation.
"""
from __future__ import annotations

from copilot.tools import ToolResult, define_tool

from .common import HospitalityEvidence, evidence_result


TOOL_NAMES = {
    "hospitality_read_hotel_operations",
    "hospitality_read_room_readiness",
    "hospitality_read_asset_maintenance",
    "hospitality_read_guest_recovery",
    "hospitality_read_occupancy_pressure",
    "hospitality_read_workforce_demand",
    "hospitality_read_food_beverage_readiness",
    "hospitality_read_energy_anomaly",
}


@define_tool(
    name="hospitality_read_hotel_operations",
    description="Read versioned hotel operations risk, capacity and arrival evidence.",
)
def hospitality_read_hotel_operations(params: HospitalityEvidence) -> ToolResult:
    return evidence_result(params, operation="read_hotel_operations")


@define_tool(
    name="hospitality_read_room_readiness",
    description="Read versioned room readiness and housekeeping capacity evidence.",
)
def hospitality_read_room_readiness(params: HospitalityEvidence) -> ToolResult:
    return evidence_result(params, operation="read_room_readiness")


@define_tool(
    name="hospitality_read_asset_maintenance",
    description="Read versioned critical asset and work order evidence.",
)
def hospitality_read_asset_maintenance(params: HospitalityEvidence) -> ToolResult:
    return evidence_result(params, operation="read_asset_maintenance")


@define_tool(
    name="hospitality_read_guest_recovery",
    description="Read versioned guest service failure and booking evidence.",
)
def hospitality_read_guest_recovery(params: HospitalityEvidence) -> ToolResult:
    return evidence_result(params, operation="read_guest_recovery")


@define_tool(
    name="hospitality_read_occupancy_pressure",
    description="Read versioned sellable inventory and protected arrival evidence.",
)
def hospitality_read_occupancy_pressure(params: HospitalityEvidence) -> ToolResult:
    return evidence_result(params, operation="read_occupancy_pressure")


@define_tool(
    name="hospitality_read_workforce_demand",
    description="Read versioned shift coverage and demand forecast evidence.",
)
def hospitality_read_workforce_demand(params: HospitalityEvidence) -> ToolResult:
    return evidence_result(params, operation="read_workforce_demand")


@define_tool(
    name="hospitality_read_food_beverage_readiness",
    description="Read versioned covers forecast and service capacity evidence.",
)
def hospitality_read_food_beverage_readiness(
    params: HospitalityEvidence,
) -> ToolResult:
    return evidence_result(params, operation="read_food_beverage_readiness")


@define_tool(
    name="hospitality_read_energy_anomaly",
    description="Read versioned energy meter reading and baseline evidence.",
)
def hospitality_read_energy_anomaly(params: HospitalityEvidence) -> ToolResult:
    return evidence_result(params, operation="read_energy_anomaly")


TOOL_BY_NAME = {
    "hospitality_read_hotel_operations": hospitality_read_hotel_operations,
    "hospitality_read_room_readiness": hospitality_read_room_readiness,
    "hospitality_read_asset_maintenance": hospitality_read_asset_maintenance,
    "hospitality_read_guest_recovery": hospitality_read_guest_recovery,
    "hospitality_read_occupancy_pressure": hospitality_read_occupancy_pressure,
    "hospitality_read_workforce_demand": hospitality_read_workforce_demand,
    "hospitality_read_food_beverage_readiness": (
        hospitality_read_food_beverage_readiness
    ),
    "hospitality_read_energy_anomaly": hospitality_read_energy_anomaly,
}
