from __future__ import annotations

from verticals.airline.worlds.model import (
    Aircraft,
    CrewDuty,
    PassengerCohort,
    Rotation,
    Sector,
    Slot,
    Stand,
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
        Aircraft("SYN-AIRCRAFT-01", "A320", "operational", "SYN-OUT-01"),
        Aircraft("SYN-AIRCRAFT-02", "A320", "operational", "SYN-OUT-02"),
        Aircraft("SYN-AIRCRAFT-03", "A321", "operational", "SYN-OUT-03"),
        Aircraft("SYN-AIRCRAFT-04", "A320", "operational", "SYN-OUT-04"),
        Aircraft("SYN-AIRCRAFT-05", "A320", "reserve", HUB_ID),
    ]


def build_sectors() -> list[Sector]:
    return [
        Sector(
            "SYN-SECTOR-IN-001",
            "SYN-OUT-01",
            HUB_ID,
            "SYN-AIRCRAFT-01",
            "SYN-CREW-DUTY-01",
            "SYN-SLOT-01",
            "SYN-STAND-01",
            60.0,
        ),
        Sector(
            "SYN-SECTOR-OUT-001",
            HUB_ID,
            "SYN-OUT-01",
            "SYN-AIRCRAFT-01",
            "SYN-CREW-DUTY-01",
            "SYN-SLOT-05",
            "SYN-STAND-01",
            150.0,
        ),
        Sector(
            "SYN-SECTOR-IN-002",
            "SYN-OUT-02",
            HUB_ID,
            "SYN-AIRCRAFT-02",
            "SYN-CREW-DUTY-02",
            "SYN-SLOT-02",
            "SYN-STAND-02",
            70.0,
        ),
        Sector(
            "SYN-SECTOR-OUT-002",
            HUB_ID,
            "SYN-OUT-02",
            "SYN-AIRCRAFT-02",
            "SYN-CREW-DUTY-02",
            "SYN-SLOT-06",
            "SYN-STAND-02",
            160.0,
        ),
        Sector(
            "SYN-SECTOR-IN-003",
            "SYN-OUT-03",
            HUB_ID,
            "SYN-AIRCRAFT-03",
            "SYN-CREW-DUTY-03",
            "SYN-SLOT-03",
            "SYN-STAND-03",
            80.0,
        ),
        Sector(
            "SYN-SECTOR-OUT-003",
            HUB_ID,
            "SYN-OUT-03",
            "SYN-AIRCRAFT-03",
            "SYN-CREW-DUTY-05",
            "SYN-SLOT-07",
            "SYN-STAND-03",
            170.0,
        ),
        Sector(
            "SYN-SECTOR-IN-004",
            "SYN-OUT-04",
            HUB_ID,
            "SYN-AIRCRAFT-04",
            "SYN-CREW-DUTY-04",
            "SYN-SLOT-04",
            "SYN-STAND-04",
            90.0,
        ),
        Sector(
            "SYN-SECTOR-OUT-004",
            HUB_ID,
            "SYN-OUT-04",
            "SYN-AIRCRAFT-04",
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
            "SYN-AIRCRAFT-01",
            ("SYN-SECTOR-IN-001", "SYN-SECTOR-OUT-001"),
            40,
            "planned",
        ),
        Rotation(
            "SYN-ROTATION-02",
            "SYN-AIRCRAFT-02",
            ("SYN-SECTOR-IN-002", "SYN-SECTOR-OUT-002"),
            40,
            "planned",
        ),
        Rotation(
            "SYN-ROTATION-03",
            "SYN-AIRCRAFT-03",
            ("SYN-SECTOR-IN-003", "SYN-SECTOR-OUT-003"),
            45,
            "planned",
        ),
        Rotation(
            "SYN-ROTATION-04",
            "SYN-AIRCRAFT-04",
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
            "SYN-CREW-DUTY-06",
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
