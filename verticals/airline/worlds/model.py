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
class TechnicalStatus:
    id: str
    aircraft_id: str
    defect_code: str
    description: str
    status: str  # grounded | work_in_progress
    version: int = 1
    last_event_id: str | None = None


@dataclass
class MaintenanceTask:
    id: str
    technical_status_id: str
    aircraft_id: str
    task_type: str
    required_capability: str
    spare_part_number: str | None
    provider_id: str | None
    status: str  # open | in_progress
    version: int = 1
    last_event_id: str | None = None


@dataclass
class ApprovedProvider:
    id: str
    name: str
    station_id: str
    capabilities: tuple[str, ...]
    approved: bool
    version: int = 1
    last_event_id: str | None = None


@dataclass
class Spare:
    id: str
    part_number: str
    traceable: bool
    station_id: str
    status: str  # available | reserved | dispatched
    lead_time_minutes: int
    version: int = 1
    last_event_id: str | None = None


@dataclass
class EngineeringWorkOrder:
    id: str
    workflow_id: str
    technical_status_id: str
    maintenance_task_id: str
    provider_id: str
    spare_id: str | None
    status: str  # open | in_progress
    version: int = 1
    last_event_id: str | None = None


@dataclass
class SpareMovement:
    id: str
    spare_id: str
    workflow_id: str
    from_station_id: str
    to_station_id: str
    status: str  # reserved | dispatched
    version: int = 1
    last_event_id: str | None = None


@dataclass
class AogRecoveryCommand:
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
class AogRecoveryEvaluation:
    id: str
    workflow_id: str
    command_id: str
    option_id: str
    status: str
    invariant_results: tuple[str, ...]
    sectors_protected: int
    projected_aog_duration_minutes: int
    spare_lead_time_minutes: int
    approved_provider_coverage: bool
    synthetic_recovery_cost_gbp: float
    aircraft_released_by_ai: bool
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


# ---------------------------------------------------------------------------
# Hero 3 – Preemptive Schedule Resilience
# ---------------------------------------------------------------------------

@dataclass
class ScheduleRiskSignal:
    id: str
    scenario_id: str
    story_id: str
    source: str
    horizon_minutes: int
    window_start_minutes: int
    window_end_minutes: int
    confidence: float
    max_cancellations_permitted: int
    status: str  # detected | active | monitored | resolved
    version: int = 1
    last_event_id: str | None = None


@dataclass
class ForecastConstraint:
    id: str
    constraint_type: str
    station_id: str
    affected_sector_ids: tuple[str, ...]
    window_start_minutes: int
    window_end_minutes: int
    capacity_reduction_pct: int
    status: str  # forecast | active
    version: int = 1
    last_event_id: str | None = None


@dataclass
class ScheduleAdjustmentCommand:
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
class ScheduleResilienceEvaluation:
    id: str
    workflow_id: str
    command_id: str
    option_id: str
    status: str
    invariant_results: tuple[str, ...]
    predicted_delay_reduction_minutes: int
    cancellations_reduced: int
    aircraft_feasibility_restored: bool
    crew_feasibility_restored: bool
    slot_feasibility_restored: bool
    protected_cohorts: int
    capacity_retained_pct: float
    synthetic_cost_gbp: float
    forecast_confidence: float
    false_positive_exposure: str
    no_action_cancellations: int
    no_action_delay_minutes: int
    selected_action: str
    version: int = 1
    last_event_id: str | None = None
