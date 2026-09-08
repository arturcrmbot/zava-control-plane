from __future__ import annotations

import copy
import dataclasses
from typing import Any

from api.server.world.model import SimulationCommand, SimulationEvent
from api.server.world.runtime import SimulationRuntime
from verticals.airline.aog_constants import (
    AOG_AFFECTED_TAIL_ID,
    AOG_COMMAND_TYPE,
    AOG_MAX_VALUE_GBP,
    AOG_ROTATION_ID,
    AOG_SCENARIO_ID,
    AOG_SENSOR_ID,
    AOG_SOURCE_EVENT_TYPE,
    AOG_STORY_ID,
    AOG_SUBSTITUTE_TAIL_ID,
    AOG_TASK_ID,
    AOG_TECH_STATUS_ID,
    AOG_THREATENED_SECTOR_ID,
    AOG_WORKFLOW_ID,
    AOG_WORKFLOW_TYPE,
)
from verticals.airline.process_profiles import (
    GOLDEN_WORKFLOW_ID,
    SCENARIO_ID,
    SENSOR_ID,
    STORY_ID,
    WORKFLOW_TYPE,
)
from verticals.airline.schedule_constants import (
    SCHED_SCENARIO_ID,
    SCHED_SENSOR_ID,
    SCHED_SOURCE_EVENT_TYPE,
    SCHED_STORY_ID,
    SCHED_WORKFLOW_ID,
    SCHED_WORKFLOW_TYPE,
)
from verticals.airline.worlds import reference_data
from verticals.airline.worlds.model import (
    Aircraft,
    AogRecoveryCommand,
    AogRecoveryEvaluation,
    ApprovedProvider,
    CrewDuty,
    EngineeringWorkOrder,
    ForecastConstraint,
    MaintenanceTask,
    PassengerCohort,
    RecoveryCommand,
    RecoveryEvaluation,
    Rotation,
    ScheduleAdjustmentCommand,
    ScheduleResilienceEvaluation,
    ScheduleRiskSignal,
    Sector,
    Slot,
    Spare,
    SpareMovement,
    Stand,
    TechnicalStatus,
)

_SOURCE_EVENT_TYPE = "airline.hub_disruption.detected"
_INBOUND_SECTOR_ID = "SYN-SECTOR-IN-001"
_CONSTRAINED_STAND_ID = "SYN-STAND-01"
_INBOUND_DELAY_MINUTES = 45


class RecoveryObservationUnavailableError(RuntimeError):
    pass


def _json_value(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    return value


def _record_view(record: Any) -> dict[str, Any]:
    return _json_value(dataclasses.asdict(record))


class AirlineWorld:
    """A bounded deterministic morning-bank world for the golden Airline hero."""

    def __init__(
        self,
        seed: int = 42,
        *,
        runtime: SimulationRuntime | None = None,
    ) -> None:
        self.seed = seed
        self.runtime = runtime if runtime is not None else SimulationRuntime(seed)
        self.aircraft: dict[str, Aircraft] = {}
        self.sectors: dict[str, Sector] = {}
        self.rotations: dict[str, Rotation] = {}
        self.crew_duties: dict[str, CrewDuty] = {}
        self.slots: dict[str, Slot] = {}
        self.stands: dict[str, Stand] = {}
        self.connection_cohorts: dict[str, PassengerCohort] = {}
        self.recovery_commands: dict[str, RecoveryCommand] = {}
        self.recovery_evaluations: dict[str, RecoveryEvaluation] = {}
        # --- AOG Hero 2 collections ---
        self.technical_statuses: dict[str, TechnicalStatus] = {}
        self.maintenance_tasks: dict[str, MaintenanceTask] = {}
        self.approved_providers: dict[str, ApprovedProvider] = {}
        self.spares: dict[str, Spare] = {}
        self.engineering_work_orders: dict[str, EngineeringWorkOrder] = {}
        self.spare_movements: dict[str, SpareMovement] = {}
        self.aog_recovery_commands: dict[str, AogRecoveryCommand] = {}
        self.aog_recovery_evaluations: dict[str, AogRecoveryEvaluation] = {}
        self.aog_story_status: dict[str, str] = {}
        # --- Hero 3 – Preemptive Schedule Resilience collections ---
        self.schedule_risk_signals: dict[str, ScheduleRiskSignal] = {}
        self.forecast_constraints: dict[str, ForecastConstraint] = {}
        self.schedule_adjustment_commands: dict[str, ScheduleAdjustmentCommand] = {}
        self.schedule_resilience_evaluations: dict[str, ScheduleResilienceEvaluation] = {}
        self.sched_story_status: dict[str, str] = {}
        # ---
        self.disruption_status: dict[str, str] = {}
        self._installed = False
        self._scenario_events: dict[str, SimulationEvent] = {}
        self._scenario_trace_overrides: dict[str, str] = {}
        self._processed_commands: dict[str, tuple[SimulationCommand, SimulationEvent]] = {}
        self._command_conflicts: dict[str, SimulationEvent] = {}

    def bind_scenario_trace(self, scenario_id: str, trace_id: str) -> None:
        """Correlate a worker shadow scenario with its authoritative bridge trace."""
        if scenario_id not in self._scenario_events:
            raise ValueError(f"scenario {scenario_id!r} is not active")
        if not isinstance(trace_id, str) or not trace_id.strip():
            raise ValueError("trace_id must be a non-empty string")
        self._scenario_trace_overrides[scenario_id] = trace_id

    def install(self) -> None:
        if self._installed:
            return
        self.runtime.emit(
            "simulation.started",
            actor_id="scenario:airline-synthetic-hub",
            payload={"seed": self.seed, "scale": "demo"},
        )
        self._seed_collection(
            self.aircraft,
            reference_data.build_aircraft(),
            "airline.aircraft.seeded",
        )
        self._seed_collection(
            self.sectors,
            reference_data.build_sectors(),
            "airline.sector.seeded",
        )
        self._seed_collection(
            self.rotations,
            reference_data.build_rotations(),
            "airline.rotation.seeded",
        )
        self._seed_collection(
            self.crew_duties,
            reference_data.build_crew_duties(),
            "airline.crew_duty.seeded",
        )
        self._seed_collection(
            self.slots,
            reference_data.build_slots(),
            "airline.slot.seeded",
        )
        self._seed_collection(
            self.stands,
            reference_data.build_stands(),
            "airline.stand.seeded",
        )
        self._seed_collection(
            self.connection_cohorts,
            reference_data.build_connection_cohorts(),
            "airline.connection_cohort.seeded",
        )
        # AOG Hero 2 seed
        self._seed_collection(
            self.technical_statuses,
            reference_data.build_technical_statuses(),
            "airline.technical_status.seeded",
        )
        self._seed_collection(
            self.maintenance_tasks,
            reference_data.build_maintenance_tasks(),
            "airline.maintenance_task.seeded",
        )
        self._seed_collection(
            self.approved_providers,
            reference_data.build_approved_providers(),
            "airline.approved_provider.seeded",
        )
        self._seed_collection(
            self.spares,
            reference_data.build_spares(),
            "airline.spare.seeded",
        )
        # Hero 3 – Schedule Resilience seed
        self._seed_collection(
            self.schedule_risk_signals,
            [reference_data.build_schedule_risk_signal()],
            "airline.schedule_risk_signal.seeded",
        )
        self._seed_collection(
            self.forecast_constraints,
            reference_data.build_forecast_constraints(),
            "airline.forecast_constraint.seeded",
        )
        self._installed = True

    def on_service_activate(self) -> None:
        from verticals.airline.worlds.active import (
            register_active_airline_world,
        )

        register_active_airline_world(self)

    def on_service_deactivate(self) -> None:
        from verticals.airline.worlds.active import (
            unregister_active_airline_world,
        )

        unregister_active_airline_world(self)

    def _seed_collection(
        self,
        destination: dict[str, Any],
        records: list[Any],
        event_type: str,
    ) -> None:
        for record in records:
            destination[record.id] = record
            payload = _record_view(record)
            payload.pop("last_event_id")
            event = self.runtime.emit(
                event_type,
                actor_id=record.id,
                payload=payload,
            )
            record.last_event_id = event.event_id

    def activate_scenario(self, scenario_id: str) -> SimulationEvent:
        if scenario_id == SCENARIO_ID:
            return self._activate_hub_scenario()
        if scenario_id == AOG_SCENARIO_ID:
            return self._activate_aog_scenario()
        if scenario_id == SCHED_SCENARIO_ID:
            return self._activate_schedule_scenario()
        raise ValueError(f"unsupported Airline scenario: {scenario_id!r}")

    def _activate_hub_scenario(self) -> SimulationEvent:
        scenario_id = SCENARIO_ID
        if not self._installed:
            raise RuntimeError("AirlineWorld must be installed before activation")
        existing = self._scenario_events.get(scenario_id)
        if existing is not None:
            return existing

        sector = self.sectors[_INBOUND_SECTOR_ID]
        stand = self.stands[_CONSTRAINED_STAND_ID]
        rotation = next(item for item in self.rotations.values() if sector.id in item.sector_ids)
        cohorts = [item for item in self.connection_cohorts.values() if item.inbound_sector_id == sector.id]

        sector.delay_minutes = _INBOUND_DELAY_MINUTES
        sector.status = "delayed"
        sector.version += 1
        stand.status = "unavailable"
        stand.version += 1
        at_risk_cohorts = [
            cohort
            for cohort in cohorts
            if (
                cohort.connection_margin_minutes
                - sector.delay_minutes
            )
            < cohort.minimum_connection_minutes
        ]
        no_action_baseline = {
            "cancellations": int(
                sector.delay_minutes
                > rotation.minimum_turnaround_minutes
                and stand.status == "unavailable"
            ),
            "departure_zero_recovered": 0,
            "departure_within_fifteen_recovered": 0,
            "protected_connection_cohorts": (
                len(cohorts) - len(at_risk_cohorts)
            ),
            "passengers_requiring_rerouting": sum(
                cohort.passenger_count
                for cohort in at_risk_cohorts
            ),
        }

        source = self.runtime.emit(
            _SOURCE_EVENT_TYPE,
            actor_id=f"scenario:{SCENARIO_ID}",
            target_id=sector.id,
            payload={
                "scenario_id": SCENARIO_ID,
                "story_id": STORY_ID,
                "workflow_id": GOLDEN_WORKFLOW_ID,
                "inbound_sector_id": sector.id,
                "delay_minutes": sector.delay_minutes,
                "rotation_id": rotation.id,
                "stand_id": stand.id,
                "stand_status": stand.status,
                "connection_cohort_ids": [item.id for item in cohorts],
                "no_action_baseline": no_action_baseline,
                "evidence_versions": {
                    sector.id: sector.version,
                    stand.id: stand.version,
                },
            },
        )
        sector.last_event_id = source.event_id
        stand.last_event_id = source.event_id

        self.runtime.emit(
            "sensor.tripped",
            actor_id=SENSOR_ID,
            target_id=sector.id,
            cause_event_id=source.event_id,
            trace_id=source.trace_id,
            payload={
                "workflow_type": WORKFLOW_TYPE,
                "workflow_id": GOLDEN_WORKFLOW_ID,
                "story_id": STORY_ID,
                "scenario_id": SCENARIO_ID,
                "source_event_id": source.event_id,
                "inbound_sector_id": sector.id,
                "stand_id": stand.id,
            },
        )
        self._scenario_events[scenario_id] = source
        self.disruption_status[STORY_ID] = "active"
        return source

    def _activate_aog_scenario(self) -> SimulationEvent:
        if not self._installed:
            raise RuntimeError("AirlineWorld must be installed before activation")
        existing = self._scenario_events.get(AOG_SCENARIO_ID)
        if existing is not None:
            # Idempotent, matching _activate_hub_scenario: the reference-process
            # entry point and the orchestrator's evidence activity both activate
            # the scenario, so a re-entry must return the cached source event
            # rather than fail the run.
            return existing

        aircraft = self.aircraft[AOG_AFFECTED_TAIL_ID]
        tech = self.technical_statuses[AOG_TECH_STATUS_ID]
        task = self.maintenance_tasks[AOG_TASK_ID]
        rotation = self.rotations[AOG_ROTATION_ID]
        threatened_sector = self.sectors[AOG_THREATENED_SECTOR_ID]

        aircraft.status = "grounded"
        aircraft.version += 1
        tech.status = "grounded"
        tech.version += 1

        no_action_baseline = {
            "sectors_at_risk": 1,
            "rotation_cancelled": 0,
            "passengers_requiring_rerouting": 0,
        }

        source = self.runtime.emit(
            AOG_SOURCE_EVENT_TYPE,
            actor_id=f"scenario:{AOG_SCENARIO_ID}",
            target_id=aircraft.id,
            payload={
                "scenario_id": AOG_SCENARIO_ID,
                "story_id": AOG_STORY_ID,
                "workflow_id": AOG_WORKFLOW_ID,
                "affected_tail_id": aircraft.id,
                "defect_code": tech.defect_code,
                "technical_status_id": tech.id,
                "maintenance_task_id": task.id,
                "rotation_id": rotation.id,
                "threatened_sector_id": threatened_sector.id,
                "no_action_baseline": no_action_baseline,
                "evidence_versions": {
                    aircraft.id: aircraft.version,
                    tech.id: tech.version,
                },
            },
        )
        aircraft.last_event_id = source.event_id
        tech.last_event_id = source.event_id

        self.runtime.emit(
            "sensor.tripped",
            actor_id=AOG_SENSOR_ID,
            target_id=aircraft.id,
            cause_event_id=source.event_id,
            trace_id=source.trace_id,
            payload={
                "workflow_type": AOG_WORKFLOW_TYPE,
                "workflow_id": AOG_WORKFLOW_ID,
                "story_id": AOG_STORY_ID,
                "scenario_id": AOG_SCENARIO_ID,
                "source_event_id": source.event_id,
                "affected_tail_id": aircraft.id,
                "technical_status_id": tech.id,
                "rotation_id": rotation.id,
            },
        )
        self._scenario_events[AOG_SCENARIO_ID] = source
        self.aog_story_status[AOG_STORY_ID] = "active"
        return source

    def _activate_schedule_scenario(self) -> SimulationEvent:
        if not self._installed:
            raise RuntimeError("AirlineWorld must be installed before activation")
        existing = self._scenario_events.get(SCHED_SCENARIO_ID)
        if existing is not None:
            # Idempotent, matching _activate_hub_scenario -- see the AOG note.
            return existing

        signal = self.schedule_risk_signals["SYN-RISK-SCHED-001"]
        constraints = sorted(self.forecast_constraints.values(), key=lambda c: c.id)

        # Mark risk signal and constraints as active
        signal.status = "active"
        signal.version += 1
        for constraint in constraints:
            constraint.status = "active"
            constraint.version += 1

        affected_sector_ids = ["SYN-SECTOR-OUT-003", "SYN-SECTOR-OUT-004"]
        no_action_baseline = {
            "predicted_delays": len(affected_sector_ids),
            "predicted_cancellations": 0,
            "predicted_delay_per_sector": 45,
            "capacity_retained_pct": 60,
            "at_risk_cohort_ids": ["SYN-COHORT-002"],
        }

        evidence_versions = {signal.id: signal.version}
        for constraint in constraints:
            evidence_versions[constraint.id] = constraint.version

        source = self.runtime.emit(
            SCHED_SOURCE_EVENT_TYPE,
            actor_id=f"scenario:{SCHED_SCENARIO_ID}",
            target_id=signal.id,
            payload={
                "scenario_id": SCHED_SCENARIO_ID,
                "story_id": SCHED_STORY_ID,
                "workflow_id": SCHED_WORKFLOW_ID,
                "risk_signal_id": signal.id,
                "horizon_minutes": signal.horizon_minutes,
                "window_start_minutes": signal.window_start_minutes,
                "window_end_minutes": signal.window_end_minutes,
                "forecast_confidence": signal.confidence,
                "affected_sector_ids": affected_sector_ids,
                "no_action_baseline": no_action_baseline,
                "evidence_versions": evidence_versions,
            },
        )
        signal.last_event_id = source.event_id
        for constraint in constraints:
            constraint.last_event_id = source.event_id

        self.runtime.emit(
            "sensor.tripped",
            actor_id=SCHED_SENSOR_ID,
            target_id=signal.id,
            cause_event_id=source.event_id,
            trace_id=source.trace_id,
            payload={
                "workflow_type": SCHED_WORKFLOW_TYPE,
                "workflow_id": SCHED_WORKFLOW_ID,
                "story_id": SCHED_STORY_ID,
                "scenario_id": SCHED_SCENARIO_ID,
                "source_event_id": source.event_id,
                "risk_signal_id": signal.id,
                "affected_sector_ids": affected_sector_ids,
            },
        )
        self._scenario_events[SCHED_SCENARIO_ID] = source
        self.sched_story_status[SCHED_STORY_ID] = "active"
        return source

    def current_schedule_observation(self) -> dict[str, Any]:
        if self.sched_story_status.get(SCHED_STORY_ID) != "active":
            raise RecoveryObservationUnavailableError("schedule story is not active")
        sensor = next(
            (
                event
                for event in reversed(self.runtime.journal)
                if event.type == "sensor.tripped"
                and event.actor_id == SCHED_SENSOR_ID
                and event.payload.get("story_id") == SCHED_STORY_ID
            ),
            None,
        )
        if sensor is None:
            raise RecoveryObservationUnavailableError("schedule sensor evidence is missing")

        signal = self.schedule_risk_signals["SYN-RISK-SCHED-001"]
        constraints = sorted(self.forecast_constraints.values(), key=lambda c: c.id)

        affected_sectors = [
            self.sectors[sid]
            for sid in ["SYN-SECTOR-OUT-003", "SYN-SECTOR-OUT-004"]
            if sid in self.sectors
        ]
        affected_rotations = [
            self.rotations[rid]
            for rid in ["SYN-ROTATION-03", "SYN-ROTATION-04"]
            if rid in self.rotations
        ]
        affected_slots = [
            self.slots[slid]
            for slid in ["SYN-SLOT-07", "SYN-SLOT-08"]
            if slid in self.slots
        ]
        affected_crew = [
            self.crew_duties[cid]
            for cid in ["SYN-CREW-DUTY-05", "SYN-CREW-DUTY-04"]
            if cid in self.crew_duties
        ]
        affected_aircraft = [
            self.aircraft[aid]
            for aid in ["SYN-TAIL-003", "SYN-TAIL-004"]
            if aid in self.aircraft
        ]
        reserve_aircraft = self.aircraft["SYN-TAIL-005"]
        reserve_crew = self.crew_duties["SYN-DUTY-006"]

        source = next(
            (e for e in self.runtime.journal if e.event_id == sensor.cause_event_id),
            None,
        )

        all_evidence: list[Any] = [signal, *constraints, *affected_sectors, *affected_rotations,
                                    *affected_slots, *affected_crew, *affected_aircraft,
                                    reserve_aircraft, reserve_crew]
        evidence_versions = {r.id: r.version for r in all_evidence}

        return {
            "workflow_type": SCHED_WORKFLOW_TYPE,
            "workflow_id": SCHED_WORKFLOW_ID,
            "story_id": SCHED_STORY_ID,
            "scenario_id": SCHED_SCENARIO_ID,
            "trace_id": self._scenario_trace_overrides.get(
                SCHED_SCENARIO_ID,
                sensor.trace_id,
            ),
            "sensor_event_id": sensor.event_id,
            "source_event_id": sensor.cause_event_id,
            "observed_at": self.runtime.now,
            "sched_story_active": self.sched_story_status.get(SCHED_STORY_ID) == "active",
            "maximum_value_gbp": 300_000.0,
            "forecast_confidence": signal.confidence,
            "max_cancellations_permitted": signal.max_cancellations_permitted,
            "risk_signal": _record_view(signal),
            "forecast_constraints": [_record_view(c) for c in constraints],
            "affected_sectors": [_record_view(s) for s in affected_sectors],
            "affected_rotations": [_record_view(r) for r in affected_rotations],
            "affected_slots": [_record_view(sl) for sl in affected_slots],
            "affected_crew": [_record_view(c) for c in affected_crew],
            "affected_aircraft": [_record_view(a) for a in affected_aircraft],
            "reserve_aircraft": _record_view(reserve_aircraft),
            "reserve_crew": _record_view(reserve_crew),
            "sectors": [
                _record_view(s) for s in sorted(self.sectors.values(), key=lambda s: s.id)
            ],
            "evidence_versions": evidence_versions,
            "evidence_event_ids": [sensor.cause_event_id, sensor.event_id],
            "no_action_baseline": dict(
                source.payload.get("no_action_baseline") or {}
            )
            if source is not None
            else {},
        }

    def build_observation(
        self,
        sensor_event: dict[str, Any],
        *,
        now: float | None = None,
    ) -> dict[str, Any]:
        actor_id = sensor_event.get("actor_id")
        if sensor_event.get("type") == "sensor.tripped" and actor_id == AOG_SENSOR_ID:
            observation = self.current_aog_observation()
            if observation.get("sensor_event_id") != sensor_event.get("event_id"):
                raise ValueError("AOG observation does not match the supplied sensor event")
            return observation
        if sensor_event.get("type") == "sensor.tripped" and actor_id == SCHED_SENSOR_ID:
            observation = self.current_schedule_observation()
            if observation.get("sensor_event_id") != sensor_event.get("event_id"):
                raise ValueError("schedule observation does not match the supplied sensor event")
            return observation
        if sensor_event.get("type") == _SOURCE_EVENT_TYPE:
            source_event_id = sensor_event.get("event_id")
            sensor = next(
                (
                    event
                    for event in self.runtime.journal
                    if event.type == "sensor.tripped"
                    and event.actor_id == SENSOR_ID
                    and event.cause_event_id == source_event_id
                ),
                None,
            )
            if sensor is None:
                raise ValueError("source disruption has no integrated hub sensor event")
            sensor_event = sensor.to_dict()
        if sensor_event.get("type") != "sensor.tripped" or sensor_event.get("actor_id") != SENSOR_ID:
            raise ValueError("observation requires the integrated hub sensor event")
        payload = sensor_event.get("payload") or {}
        sector_id = payload.get("inbound_sector_id")
        stand_id = payload.get("stand_id")
        if sector_id not in self.sectors or stand_id not in self.stands:
            raise ValueError("integrated hub sensor references unknown world records")

        sector = self.sectors[sector_id]
        stand = self.stands[stand_id]
        rotation = next(item for item in self.rotations.values() if sector.id in item.sector_ids)
        cohorts = sorted(
            (item for item in self.connection_cohorts.values() if item.inbound_sector_id == sector.id),
            key=lambda item: item.id,
        )
        outbound_sector = self.sectors[rotation.sector_ids[-1]]
        outbound_aircraft = self.aircraft[outbound_sector.aircraft_id]
        outbound_crew = self.crew_duties[outbound_sector.crew_duty_id]
        outbound_slot = self.slots[outbound_sector.slot_id]
        candidate_aircraft = self.aircraft["SYN-TAIL-005"]
        candidate_crew = self.crew_duties["SYN-DUTY-006"]
        candidate_stand = self.stands["SYN-STAND-05"]
        evidence_records = {
            record.id: record
            for record in (
                sector,
                stand,
                rotation,
                self.aircraft[sector.aircraft_id],
                self.crew_duties[sector.crew_duty_id],
                self.slots[sector.slot_id],
                outbound_sector,
                outbound_aircraft,
                outbound_crew,
                outbound_slot,
                candidate_aircraft,
                candidate_crew,
                candidate_stand,
            )
        }
        source_event = next(
            (
                event
                for event in self.runtime.journal
                if event.event_id == sensor_event.get("cause_event_id")
            ),
            None,
        )
        return {
            "workflow_type": WORKFLOW_TYPE,
            "workflow_id": GOLDEN_WORKFLOW_ID,
            "story_id": STORY_ID,
            "scenario_id": SCENARIO_ID,
            "trace_id": sensor_event.get("trace_id"),
            "sensor_event_id": sensor_event.get("event_id"),
            "source_event_id": sensor_event.get("cause_event_id"),
            "observed_at": self.runtime.now if now is None else float(now),
            "sector": _record_view(sector),
            "stand": _record_view(stand),
            "rotation": _record_view(rotation),
            "aircraft": _record_view(self.aircraft[sector.aircraft_id]),
            "crew_duty": _record_view(self.crew_duties[sector.crew_duty_id]),
            "slot": _record_view(self.slots[sector.slot_id]),
            "connection_cohorts": [_record_view(item) for item in cohorts],
            "outbound_sector": _record_view(outbound_sector),
            "outbound_aircraft": _record_view(outbound_aircraft),
            "outbound_crew_duty": _record_view(outbound_crew),
            "outbound_slot": _record_view(outbound_slot),
            "candidate_aircraft": _record_view(candidate_aircraft),
            "candidate_crew_duty": _record_view(candidate_crew),
            "candidate_stand": _record_view(candidate_stand),
            "sectors": [
                _record_view(item) for item in sorted(self.sectors.values(), key=lambda item: item.id)
            ],
            "evidence_versions": {
                record_id: evidence_records[record_id].version for record_id in sorted(evidence_records)
            },
            "maximum_value_gbp": 150_000.0,
            "evidence_event_ids": [
                sensor_event.get("cause_event_id"),
                sensor_event.get("event_id"),
            ],
            "no_action_baseline": dict(
                source_event.payload.get("no_action_baseline") or {}
            )
            if source_event is not None
            else {},
        }

    def current_recovery_observation(self) -> dict[str, Any]:
        if self.disruption_status.get(STORY_ID) != "active":
            raise RecoveryObservationUnavailableError("integrated hub disruption is not active")
        sensor = next(
            (
                event
                for event in reversed(self.runtime.journal)
                if event.type == "sensor.tripped"
                and event.actor_id == SENSOR_ID
                and event.payload.get("story_id") == STORY_ID
            ),
            None,
        )
        if sensor is None:
            raise RecoveryObservationUnavailableError("integrated hub disruption sensor evidence is missing")
        return self.build_observation(sensor.to_dict())

    def current_aog_observation(self) -> dict[str, Any]:
        if self.aog_story_status.get(AOG_STORY_ID) != "active":
            raise RecoveryObservationUnavailableError("AOG story is not active")
        sensor = next(
            (
                event
                for event in reversed(self.runtime.journal)
                if event.type == "sensor.tripped"
                and event.actor_id == AOG_SENSOR_ID
                and event.payload.get("story_id") == AOG_STORY_ID
            ),
            None,
        )
        if sensor is None:
            raise RecoveryObservationUnavailableError("AOG sensor evidence is missing")
        source = next(
            (e for e in self.runtime.journal if e.event_id == sensor.cause_event_id),
            None,
        )
        aircraft = self.aircraft[AOG_AFFECTED_TAIL_ID]
        tech = self.technical_statuses[AOG_TECH_STATUS_ID]
        task = self.maintenance_tasks[AOG_TASK_ID]
        rotation = self.rotations[AOG_ROTATION_ID]
        threatened_sector = self.sectors[AOG_THREATENED_SECTOR_ID]
        substitute = self.aircraft[AOG_SUBSTITUTE_TAIL_ID]
        providers = sorted(self.approved_providers.values(), key=lambda p: p.id)
        spares = sorted(self.spares.values(), key=lambda s: s.id)
        evidence_records = {
            r.id: r
            for r in [aircraft, tech, task, rotation, threatened_sector, substitute, *providers, *spares]
        }
        return {
            "workflow_type": AOG_WORKFLOW_TYPE,
            "workflow_id": AOG_WORKFLOW_ID,
            "story_id": AOG_STORY_ID,
            "scenario_id": AOG_SCENARIO_ID,
            "trace_id": self._scenario_trace_overrides.get(
                AOG_SCENARIO_ID,
                sensor.trace_id,
            ),
            "sensor_event_id": sensor.event_id,
            "source_event_id": sensor.cause_event_id,
            "observed_at": self.runtime.now,
            "affected_tail_id": aircraft.id,
            "rotation_id": rotation.id,
            "technical_status": _record_view(tech),
            "maintenance_task": _record_view(task),
            "approved_providers": [_record_view(p) for p in providers],
            "spares": [_record_view(s) for s in spares],
            "threatened_sector": _record_view(threatened_sector),
            "substitute_candidate": _record_view(substitute),
            "sectors": [
                _record_view(item) for item in sorted(self.sectors.values(), key=lambda s: s.id)
            ],
            "evidence_versions": {
                rid: evidence_records[rid].version for rid in sorted(evidence_records)
            },
            "evidence_event_ids": [
                sensor.cause_event_id,
                sensor.event_id,
            ],
            "no_action_baseline": dict(
                source.payload.get("no_action_baseline") or {}
            )
            if source is not None
            else {},
            "maximum_value_gbp": AOG_MAX_VALUE_GBP,
            "aog_story_active": self.aog_story_status.get(AOG_STORY_ID) == "active",
        }

    def command_for_aog_option(
        self,
        *,
        option_id: str,
        workflow_id: str,
        decision_id: str,
        persona: str,
    ) -> SimulationCommand:
        from verticals.airline.actions.aog_commands import (
            aog_recovery_command_id,
            command_for_aog_option,
        )

        command_id = aog_recovery_command_id(
            workflow_id=workflow_id,
            decision_id=decision_id,
            option_id=option_id,
        )
        cached = self._processed_commands.get(command_id)
        if cached is not None:
            prior_command, _ = cached
            prior_identity = (
                prior_command.payload.get("workflow_id"),
                prior_command.payload.get("decision_id"),
                prior_command.payload.get("option_id"),
                prior_command.payload.get("persona"),
            )
            requested_identity = (workflow_id, decision_id, option_id, persona)
            if prior_identity != requested_identity:
                raise ValueError("AOG recovery command identity does not match the processed command")
            return copy.deepcopy(prior_command)
        return command_for_aog_option(
            self,
            option_id=option_id,
            workflow_id=workflow_id,
            decision_id=decision_id,
            persona=persona,
        )

    def command_for_schedule_option(
        self,
        *,
        option_id: str,
        workflow_id: str,
        decision_id: str,
        persona: str,
    ) -> SimulationCommand:
        from verticals.airline.actions.schedule_commands import (
            command_for_schedule_option,
            schedule_command_id,
        )

        command_id = schedule_command_id(
            workflow_id=workflow_id,
            decision_id=decision_id,
            option_id=option_id,
        )
        cached = self._processed_commands.get(command_id)
        if cached is not None:
            prior_command, _ = cached
            prior_identity = (
                prior_command.payload.get("workflow_id"),
                prior_command.payload.get("decision_id"),
                prior_command.payload.get("option_id"),
                prior_command.payload.get("persona"),
            )
            requested_identity = (workflow_id, decision_id, option_id, persona)
            if prior_identity != requested_identity:
                raise ValueError("schedule adjustment command identity does not match the processed command")
            return copy.deepcopy(prior_command)
        return command_for_schedule_option(
            self,
            option_id=option_id,
            workflow_id=workflow_id,
            decision_id=decision_id,
            persona=persona,
        )

    def command_for_option(
        self,
        *,
        option_id: str,
        workflow_id: str,
        decision_id: str,
        persona: str,
    ) -> SimulationCommand:
        from verticals.airline.actions.commands import (
            command_for_option,
            recovery_command_id,
        )

        command_id = recovery_command_id(
            workflow_id=workflow_id,
            decision_id=decision_id,
            option_id=option_id,
        )
        cached = self._processed_commands.get(command_id)
        if cached is not None:
            prior_command, _ = cached
            prior_identity = (
                prior_command.payload.get("workflow_id"),
                prior_command.payload.get("decision_id"),
                prior_command.payload.get("option_id"),
                prior_command.payload.get("persona"),
            )
            requested_identity = (workflow_id, decision_id, option_id, persona)
            if prior_identity != requested_identity:
                raise ValueError("recovery command identity does not match the processed command")
            return copy.deepcopy(prior_command)
        return command_for_option(
            self,
            option_id=option_id,
            workflow_id=workflow_id,
            decision_id=decision_id,
            persona=persona,
        )

    # Each hero is (scenario_id, sensor_id, workflow_id, story_id). Keyed by
    # workflow_type so the /world "Run scenario" buttons and the deterministic
    # story buttons resolve the same identities for all three heroes rather
    # than only Hero 1.
    _HERO_IDENTITIES: dict[str, tuple[str, str, str, str]] = {
        WORKFLOW_TYPE: (SCENARIO_ID, SENSOR_ID, GOLDEN_WORKFLOW_ID, STORY_ID),
        AOG_WORKFLOW_TYPE: (
            AOG_SCENARIO_ID,
            AOG_SENSOR_ID,
            AOG_WORKFLOW_ID,
            AOG_STORY_ID,
        ),
        SCHED_WORKFLOW_TYPE: (
            SCHED_SCENARIO_ID,
            SCHED_SENSOR_ID,
            SCHED_WORKFLOW_ID,
            SCHED_STORY_ID,
        ),
    }

    _SCENARIO_TO_WORKFLOW_TYPE: dict[str, str] = {
        SCENARIO_ID: WORKFLOW_TYPE,
        AOG_SCENARIO_ID: AOG_WORKFLOW_TYPE,
        SCHED_SCENARIO_ID: SCHED_WORKFLOW_TYPE,
    }

    reference_process_types = (
        WORKFLOW_TYPE,
        AOG_WORKFLOW_TYPE,
        SCHED_WORKFLOW_TYPE,
    )

    def run_scenario(self, scenario_id: str) -> dict[str, Any]:
        workflow_type = self._SCENARIO_TO_WORKFLOW_TYPE.get(scenario_id)
        if workflow_type is None:
            raise ValueError(f"unsupported Airline scenario: {scenario_id!r}")
        _, _, workflow_id, story_id = self._HERO_IDENTITIES[workflow_type]
        source = self.activate_scenario(scenario_id)
        return {
            "scenario_id": scenario_id,
            "root_event_id": source.event_id,
            "workflow_id": workflow_id,
            "story_id": story_id,
        }

    def run_reference_process(
        self,
        workflow_type: str,
    ) -> dict[str, Any]:
        identity = self._HERO_IDENTITIES.get(workflow_type)
        if identity is None:
            raise ValueError(f"unsupported Airline reference process: {workflow_type!r}")
        scenario_id, sensor_id, workflow_id, story_id = identity
        source = self.activate_scenario(scenario_id)
        sensor = next(
            event
            for event in self.runtime.journal
            if event.type == "sensor.tripped"
            and event.actor_id == sensor_id
            and event.cause_event_id == source.event_id
        )
        return {
            "workflow_type": workflow_type,
            "workflow_id": workflow_id,
            "scenario_id": scenario_id,
            "story_id": story_id,
            "source_event_id": source.event_id,
            "sensor_event_id": sensor.event_id,
        }

    def command_was_processed(self, command_id: str) -> bool:
        return command_id in self._processed_commands

    def apply_command(self, command: SimulationCommand) -> SimulationEvent:
        cached = self._processed_commands.get(command.command_id)
        if cached is not None:
            prior_command, prior_event = cached
            if prior_command == command:
                return prior_event
            conflict = self._command_conflicts.get(command.command_id)
            if conflict is not None:
                return conflict
            from verticals.airline.actions.commands import reject

            conflict = reject(
                self,
                command,
                "idempotency key was reused with a different command payload",
            )
            self._command_conflicts[command.command_id] = conflict
            return conflict

        if command.type == AOG_COMMAND_TYPE:
            from verticals.airline.actions.aog_commands import apply_aog_recovery_command

            result = apply_aog_recovery_command(self, command)
        elif command.type == "airline.commit_schedule_adjustment":
            from verticals.airline.actions.schedule_commands import apply_schedule_adjustment_command

            result = apply_schedule_adjustment_command(self, command)
        else:
            from verticals.airline.actions.commands import apply_recovery_command

            result = apply_recovery_command(self, command)
        self._processed_commands[command.command_id] = (copy.deepcopy(command), result)
        return result

    def render_state(self) -> dict[str, list[dict[str, Any]]]:
        def rows(records: dict[str, Any]) -> list[dict[str, Any]]:
            return [_record_view(record) for record in sorted(records.values(), key=lambda item: item.id)]

        cohort_rows = rows(self.connection_cohorts)
        for row in cohort_rows:
            row["location_id"] = reference_data.HUB_ID
        return {
            "aircraft": rows(self.aircraft),
            "sectors": rows(self.sectors),
            "rotations": rows(self.rotations),
            "crew_duties": rows(self.crew_duties),
            "slots": rows(self.slots),
            "stands": rows(self.stands),
            "connection_cohorts": cohort_rows,
            "recovery_commands": rows(self.recovery_commands),
            "recovery_evaluations": rows(self.recovery_evaluations),
            "technical_statuses": rows(self.technical_statuses),
            "maintenance_tasks": rows(self.maintenance_tasks),
            "approved_providers": rows(self.approved_providers),
            "spares": rows(self.spares),
            "engineering_work_orders": rows(self.engineering_work_orders),
            "spare_movements": rows(self.spare_movements),
            "aog_recovery_commands": rows(self.aog_recovery_commands),
            "aog_recovery_evaluations": rows(self.aog_recovery_evaluations),
            "schedule_risk_signals": rows(self.schedule_risk_signals),
            "forecast_constraints": rows(self.forecast_constraints),
            "schedule_adjustment_commands": rows(self.schedule_adjustment_commands),
            "schedule_resilience_evaluations": rows(self.schedule_resilience_evaluations),
        }
