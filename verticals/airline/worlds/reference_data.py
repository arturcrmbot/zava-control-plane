from __future__ import annotations

from verticals.airline.worlds.model import (
    Aircraft,
    ApprovedProvider,
    CrewDuty,
    ForecastConstraint,
    MaintenanceTask,
    PassengerCohort,
    Rotation,
    Sector,
    ScheduleRiskSignal,
    Slot,
    Spare,
    Stand,
    TechnicalStatus,
)

HUB_ID = "SYN-HUB-01"
OUTSTATION_IDS = (
    "SYN-OUT-01",
    "SYN-OUT-02",
    "SYN-OUT-03",
    "SYN-OUT-04",
)


def build_aircraft() -> list[Aircraft]:
    return [
        Aircraft("SYN-TAIL-001", "A320", "operational", "SYN-OUT-01"),
        Aircraft("SYN-TAIL-002", "A320", "operational", "SYN-OUT-02"),
        Aircraft("SYN-TAIL-003", "A321", "operational", "SYN-OUT-03"),
        Aircraft("SYN-TAIL-004", "A320", "operational", "SYN-OUT-04"),
        Aircraft("SYN-TAIL-005", "A320", "reserve", HUB_ID),
    ]


def build_sectors() -> list[Sector]:
    return [
        Sector(
            "SYN-SECTOR-IN-001",
            "SYN-OUT-01",
            HUB_ID,
            "SYN-TAIL-001",
            "SYN-CREW-DUTY-01",
            "SYN-SLOT-01",
            "SYN-STAND-01",
            60.0,
        ),
        Sector(
            "SYN-SECTOR-OUT-001",
            HUB_ID,
            "SYN-OUT-01",
            "SYN-TAIL-001",
            "SYN-CREW-DUTY-01",
            "SYN-SLOT-05",
            "SYN-STAND-01",
            150.0,
        ),
        Sector(
            "SYN-SECTOR-IN-002",
            "SYN-OUT-02",
            HUB_ID,
            "SYN-TAIL-002",
            "SYN-CREW-DUTY-02",
            "SYN-SLOT-02",
            "SYN-STAND-02",
            70.0,
        ),
        Sector(
            "SYN-SECTOR-OUT-002",
            HUB_ID,
            "SYN-OUT-02",
            "SYN-TAIL-002",
            "SYN-CREW-DUTY-02",
            "SYN-SLOT-06",
            "SYN-STAND-02",
            160.0,
        ),
        Sector(
            "SYN-SECTOR-IN-003",
            "SYN-OUT-03",
            HUB_ID,
            "SYN-TAIL-003",
            "SYN-CREW-DUTY-03",
            "SYN-SLOT-03",
            "SYN-STAND-03",
            80.0,
        ),
        Sector(
            "SYN-SECTOR-OUT-003",
            HUB_ID,
            "SYN-OUT-03",
            "SYN-TAIL-003",
            "SYN-CREW-DUTY-05",
            "SYN-SLOT-07",
            "SYN-STAND-03",
            170.0,
        ),
        Sector(
            "SYN-SECTOR-IN-004",
            "SYN-OUT-04",
            HUB_ID,
            "SYN-TAIL-004",
            "SYN-CREW-DUTY-04",
            "SYN-SLOT-04",
            "SYN-STAND-04",
            90.0,
        ),
        Sector(
            "SYN-SECTOR-OUT-004",
            HUB_ID,
            "SYN-OUT-04",
            "SYN-TAIL-004",
            "SYN-CREW-DUTY-04",
            "SYN-SLOT-08",
            "SYN-STAND-04",
            180.0,
        ),
    ]


def build_rotations() -> list[Rotation]:
    return [
        Rotation(
            "SYN-ROTATION-01",
            "SYN-TAIL-001",
            ("SYN-SECTOR-IN-001", "SYN-SECTOR-OUT-001"),
            40,
            "planned",
        ),
        Rotation(
            "SYN-ROTATION-02",
            "SYN-TAIL-002",
            ("SYN-SECTOR-IN-002", "SYN-SECTOR-OUT-002"),
            40,
            "planned",
        ),
        Rotation(
            "SYN-ROTATION-03",
            "SYN-TAIL-003",
            ("SYN-SECTOR-IN-003", "SYN-SECTOR-OUT-003"),
            45,
            "planned",
        ),
        Rotation(
            "SYN-ROTATION-04",
            "SYN-TAIL-004",
            ("SYN-SECTOR-IN-004", "SYN-SECTOR-OUT-004"),
            40,
            "planned",
        ),
    ]


def build_crew_duties() -> list[CrewDuty]:
    return [
        CrewDuty(
            "SYN-CREW-DUTY-01",
            "A320",
            ("SYN-SECTOR-IN-001", "SYN-SECTOR-OUT-001"),
            0.0,
            600,
            360,
            "active",
        ),
        CrewDuty(
            "SYN-CREW-DUTY-02",
            "A320",
            ("SYN-SECTOR-IN-002", "SYN-SECTOR-OUT-002"),
            0.0,
            600,
            350,
            "active",
        ),
        CrewDuty(
            "SYN-CREW-DUTY-03",
            "A321",
            ("SYN-SECTOR-IN-003",),
            10.0,
            570,
            330,
            "active",
        ),
        CrewDuty(
            "SYN-CREW-DUTY-04",
            "A320",
            ("SYN-SECTOR-IN-004", "SYN-SECTOR-OUT-004"),
            10.0,
            600,
            340,
            "active",
        ),
        CrewDuty(
            "SYN-CREW-DUTY-05",
            "A321",
            ("SYN-SECTOR-OUT-003",),
            90.0,
            540,
            390,
            "active",
        ),
        CrewDuty(
            "SYN-DUTY-006",
            "A320",
            (),
            60.0,
            540,
            480,
            "reserve",
            is_reserve=True,
        ),
    ]


def build_slots() -> list[Slot]:
    definitions = (
        ("SYN-SLOT-01", "SYN-SECTOR-IN-001", "SYN-OUT-01", 60.0),
        ("SYN-SLOT-02", "SYN-SECTOR-IN-002", "SYN-OUT-02", 70.0),
        ("SYN-SLOT-03", "SYN-SECTOR-IN-003", "SYN-OUT-03", 80.0),
        ("SYN-SLOT-04", "SYN-SECTOR-IN-004", "SYN-OUT-04", 90.0),
        ("SYN-SLOT-05", "SYN-SECTOR-OUT-001", HUB_ID, 150.0),
        ("SYN-SLOT-06", "SYN-SECTOR-OUT-002", HUB_ID, 160.0),
        ("SYN-SLOT-07", "SYN-SECTOR-OUT-003", HUB_ID, 170.0),
        ("SYN-SLOT-08", "SYN-SECTOR-OUT-004", HUB_ID, 180.0),
    )
    return [
        Slot(slot_id, sector_id, station_id, scheduled_time, 15, "allocated")
        for slot_id, sector_id, station_id, scheduled_time in definitions
    ]


def build_stands() -> list[Stand]:
    return [
        Stand(
            f"SYN-STAND-{number:02d}",
            HUB_ID,
            ("A320", "A321"),
            "available",
        )
        for number in range(1, 6)
    ]


def build_connection_cohorts() -> list[PassengerCohort]:
    return [
        PassengerCohort(
            "SYN-COHORT-001",
            "SYN-SECTOR-IN-001",
            "SYN-SECTOR-OUT-002",
            26,
            45,
            55,
            False,
            "protected",
        ),
        PassengerCohort(
            "SYN-COHORT-002",
            "SYN-SECTOR-IN-003",
            "SYN-SECTOR-OUT-004",
            12,
            55,
            65,
            True,
            "protected",
        ),
    ]


# ---------------------------------------------------------------------------
# AOG Engineering Recovery – Hero 2 reference data
# ---------------------------------------------------------------------------

AOG_DEFECT_CODE = "DEF-HYD-ACTUATOR"
AOG_CAPABILITY = "hydraulic-actuator-replacement"
AOG_PART_NUMBER = "SYN-PART-HYD-001"


def build_technical_statuses() -> list[TechnicalStatus]:
    return [
        TechnicalStatus(
            id="SYN-TECH-003",
            aircraft_id="SYN-TAIL-003",
            defect_code=AOG_DEFECT_CODE,
            description="Hydraulic actuator fault – aircraft grounded pending engineering assessment",
            status="serviceable",  # will be set to 'grounded' on scenario activation
        ),
    ]


def build_maintenance_tasks() -> list[MaintenanceTask]:
    return [
        MaintenanceTask(
            id="SYN-TASK-001",
            technical_status_id="SYN-TECH-003",
            aircraft_id="SYN-TAIL-003",
            task_type="component-replacement",
            required_capability=AOG_CAPABILITY,
            spare_part_number=AOG_PART_NUMBER,
            provider_id=None,
            status="open",
        ),
    ]


def build_approved_providers() -> list[ApprovedProvider]:
    return [
        # Approved MRO at SYN-OUT-03 with correct capability
        ApprovedProvider(
            id="SYN-PROV-001",
            name="Synthetic MRO Services OUT-03",
            station_id="SYN-OUT-03",
            capabilities=(AOG_CAPABILITY, "general-inspection"),
            approved=True,
        ),
        # Deliberately unapproved provider – infeasible option
        ApprovedProvider(
            id="SYN-PROV-UNAP-001",
            name="Synthetic Non-Approved Engineering Ltd",
            station_id="SYN-OUT-03",
            capabilities=(AOG_CAPABILITY,),
            approved=False,
        ),
    ]


def build_spares() -> list[Spare]:
    return [
        # Local traceable spare at SYN-OUT-03 (immediate lead time)
        Spare(
            id="SYN-SPARE-LOCAL-001",
            part_number=AOG_PART_NUMBER,
            traceable=True,
            station_id="SYN-OUT-03",
            status="available",
            lead_time_minutes=60,
        ),
        # Repositionable traceable spare at hub (longer lead time)
        Spare(
            id="SYN-SPARE-REPO-001",
            part_number=AOG_PART_NUMBER,
            traceable=True,
            station_id=HUB_ID,
            status="available",
            lead_time_minutes=180,
        ),
        # Untraceable spare – deliberately infeasible
        Spare(
            id="SYN-SPARE-UNTRACED-001",
            part_number=AOG_PART_NUMBER,
            traceable=False,
            station_id="SYN-OUT-03",
            status="available",
            lead_time_minutes=30,
        ),
    ]


# ---------------------------------------------------------------------------
# Hero 3 – Preemptive Schedule Resilience seed data
# ---------------------------------------------------------------------------


def build_schedule_risk_signal() -> ScheduleRiskSignal:
    """One forecast risk signal for the synthetic-schedule-restriction scenario."""
    return ScheduleRiskSignal(
        id="SYN-RISK-SCHED-001",
        scenario_id="synthetic-schedule-restriction",
        story_id="SYN-STORY-SCHED-001",
        source="eurocontrol_forecast",
        horizon_minutes=120,
        window_start_minutes=120,
        window_end_minutes=240,
        confidence=0.82,
        max_cancellations_permitted=1,
        status="detected",
    )


def build_forecast_constraints() -> list[ForecastConstraint]:
    """Two deterministic forecast constraints covering the 120-240 min window."""
    return [
        ForecastConstraint(
            id="SYN-FCAST-SLOT-001",
            constraint_type="reduced_slot_capacity",
            station_id=HUB_ID,
            affected_sector_ids=("SYN-SECTOR-OUT-003", "SYN-SECTOR-OUT-004"),
            window_start_minutes=120,
            window_end_minutes=240,
            capacity_reduction_pct=40,
            status="forecast",
        ),
        ForecastConstraint(
            id="SYN-FCAST-GROUND-001",
            constraint_type="reduced_ground_capacity",
            station_id=HUB_ID,
            affected_sector_ids=("SYN-SECTOR-OUT-003", "SYN-SECTOR-OUT-004"),
            window_start_minutes=120,
            window_end_minutes=240,
            capacity_reduction_pct=25,
            status="forecast",
        ),
    ]
