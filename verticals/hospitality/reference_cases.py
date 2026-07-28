"""Immutable reference cases for the Hospitality vertical.

Each case maps a workflow type to a typed, deterministic set of subject IDs
and minimal facts. The hero case references the golden scenario and expected
sensor event. Supporting cases carry typed minimal facts for later tasks but
are not executable stubs or proofs of those workflows.

There are exactly eight cases — one per workflow in HOSPITALITY_DOMAINS.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HospitalityReferenceCase:
    """Immutable reference case for one hospitality workflow.

    Fields
    ------
    id:
        Unique case identifier.
    workflow_type:
        Must match a key in ``HOSPITALITY_DOMAINS``.
    subject_ids:
        Deterministic tuple of actor IDs relevant to this case.
    facts:
        Typed minimal facts for the case (not a stub; not proof).
    hero_scenario:
        Named scenario to trigger for the hero case; None for supporting cases.
    expected_event_type:
        Event type the sensor emits for this case; None for supporting cases.
    """

    id: str
    workflow_type: str
    subject_ids: tuple[str, ...]
    facts: dict[str, object]
    hero_scenario: str | None = None
    expected_event_type: str | None = None


def _case(
    case_id: str,
    workflow_type: str,
    subjects: tuple[str, ...],
    *,
    hero_scenario: str | None = None,
    expected_event_type: str | None = None,
    **facts: object,
) -> HospitalityReferenceCase:
    return HospitalityReferenceCase(
        id=case_id,
        workflow_type=workflow_type,
        subject_ids=subjects,
        facts=facts,
        hero_scenario=hero_scenario,
        expected_event_type=expected_event_type,
    )


HOSPITALITY_REFERENCE_CASES: dict[str, HospitalityReferenceCase] = {
    # ----- Hero: hotel-operations-recovery ----------------------------------
    "hotel-operations-recovery": _case(
        "CASE-HOPREC-001",
        "hotel-operations-recovery",
        (
            "HOTEL-RIVERSIDE-CENTRAL",
            "ASSET-RIVC-HW-01",
            "WO-RIVC-001",
        ),
        hero_scenario="riverside-hot-water-outage",
        expected_event_type="hotel.operations-risk.detected",
        affected_rooms=18,
        not_ready_rooms=7,
        arrivals_in_4h=44,
        occupancy_pct=0.96,
        relocations=10,
        rooms_to_restore=8,
        shift_reallocations=2,
        requires_hitl=True,
    ),
    # ----- Supporting: room-readiness-coordination --------------------------
    "room-readiness-coordination": _case(
        "CASE-ROOMS-001",
        "room-readiness-coordination",
        (
            "HOTEL-AIRPORT-NORTH",
            "TEAM-ANTH-HO-03",
        ),
        readiness_gap=12,
        arrivals_due=18,
        housekeeping_available=3,
        estimated_completion_hours=2.5,
    ),
    # ----- Supporting: asset-maintenance-response ---------------------------
    "asset-maintenance-response": _case(
        "CASE-MAINT-001",
        "asset-maintenance-response",
        (
            "ASSET-CGAT-HVAC-02",
            "HOTEL-CITY-GATE",
            "WO-CGAT-005",
        ),
        asset_type="hvac",
        rooms_affected=6,
        maintenance_cost_estimate_gbp=1_200.0,
        estimated_hours=4.0,
    ),
    # ----- Supporting: guest-service-recovery -------------------------------
    "guest-service-recovery": _case(
        "CASE-GREC-001",
        "guest-service-recovery",
        (
            "BKG-HARV-STAY-003",
            "GP-HARV-003",
            "HOTEL-HARBOUR-VIEW",
        ),
        service_failure="heating-outage-in-room",
        recovery_action="room-upgrade-and-voucher",
        recovery_value_gbp=120.0,
    ),
    # ----- Supporting: occupancy-pressure-response --------------------------
    "occupancy-pressure-response": _case(
        "CASE-OCC-001",
        "occupancy-pressure-response",
        (
            "HOTEL-MESSE-CENTRAL",
            "BKG-MESC-STAY-001",
        ),
        inventory_shortfall=8,
        protected_arrivals=3,
        sellable_rooms_remaining=2,
    ),
    # ----- Supporting: workforce-demand-balancing ---------------------------
    "workforce-demand-balancing": _case(
        "CASE-WRKFRC-001",
        "workforce-demand-balancing",
        (
            "HOTEL-RHINE-PARK",
            "SHIFT-TEAM-RPAR-HO-03",
            "SHIFT-TEAM-RPAR-HO-04",
        ),
        uncovered_shifts=4,
        forecast_arrivals=22,
        available_staff=2,
        overtime_risk=True,
    ),
    # ----- Supporting: food-and-beverage-readiness --------------------------
    "food-and-beverage-readiness": _case(
        "CASE-FNBRD-001",
        "food-and-beverage-readiness",
        (
            "FSP-ANTH-001",
            "HOTEL-AIRPORT-NORTH",
        ),
        covers_forecast=180,
        covers_prepared=120,
        shortfall=60,
        service_window_hours=3,
    ),
    # ----- Supporting: energy-anomaly-response ------------------------------
    "energy-anomaly-response": _case(
        "CASE-ENERGY-001",
        "energy-anomaly-response",
        (
            "EM-CGAT-ELEC-01",
            "HOTEL-CITY-GATE",
        ),
        reading_kwh=3_450.0,
        baseline_kwh=2_800.0,
        anomaly_pct=23.2,
        duration_hours=2.0,
    ),
}
