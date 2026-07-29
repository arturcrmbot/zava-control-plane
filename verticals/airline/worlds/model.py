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


@dataclass
class RecoveryCommand:
    id: str
    workflow_id: str
    decision_id: str
    option_id: str
    persona: str
    value_gbp: float
    action_types: tuple[str, ...]
    evidence_versions: tuple[tuple[str, int], ...]
    version: int = 1
    last_event_id: str | None = None


@dataclass
class RecoveryEvaluation:
    id: str
    workflow_id: str
    command_id: str
    option_id: str
    status: str
    invariant_results: tuple[str, ...]
    cancellations_avoided: int
    departure_zero_recovered: int
    departure_within_fifteen_recovered: int
    minimum_remaining_crew_duty_minutes: int
    resolved_slot_stand_conflicts: int
    protected_connection_cohorts: int
    passengers_requiring_rerouting: int
    synthetic_recovery_cost_gbp: float
    version: int = 1
    last_event_id: str | None = None
