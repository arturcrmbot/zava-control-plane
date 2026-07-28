from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Aircraft:
    id: str
    configuration: str
    status: str
    current_station_id: str
    version: int = 1
    last_event_id: str | None = None


@dataclass
class Sector:
    id: str
    origin_id: str
    destination_id: str
    aircraft_id: str
    crew_duty_id: str
    slot_id: str
    stand_id: str
    scheduled_departure: float
    delay_minutes: int = 0
    status: str = "scheduled"
    version: int = 1
    last_event_id: str | None = None


@dataclass
class Rotation:
    id: str
    aircraft_id: str
    sector_ids: tuple[str, ...]
    minimum_turnaround_minutes: int
    status: str
    version: int = 1
    last_event_id: str | None = None


@dataclass
class CrewDuty:
    id: str
    qualification: str
    sector_ids: tuple[str, ...]
    duty_start: float
    duty_limit_minutes: int
    remaining_duty_minutes: int
    status: str
    is_reserve: bool = False
    version: int = 1
    last_event_id: str | None = None


@dataclass
class Slot:
    id: str
    sector_id: str
    station_id: str
    scheduled_time: float
    tolerance_minutes: int
    status: str
    version: int = 1
    last_event_id: str | None = None


@dataclass
class Stand:
    id: str
    station_id: str
    compatible_configurations: tuple[str, ...]
    status: str
    version: int = 1
    last_event_id: str | None = None


@dataclass
class PassengerCohort:
    id: str
    inbound_sector_id: str
    outbound_sector_id: str
    passenger_count: int
    minimum_connection_minutes: int
    connection_margin_minutes: int
    assistance_required: bool
    status: str
    version: int = 1
    last_event_id: str | None = None
