from __future__ import annotations

import dataclasses
from typing import Any

from api.server.world.model import SimulationEvent
from api.server.world.runtime import SimulationRuntime
from verticals.airline.process_profiles import (
    SCENARIO_ID,
    SENSOR_ID,
    STORY_ID,
    WORKFLOW_TYPE,
)
from verticals.airline.worlds import reference_data
from verticals.airline.worlds.model import (
    Aircraft,
    CrewDuty,
    PassengerCohort,
    Rotation,
    Sector,
    Slot,
    Stand,
)

_SOURCE_EVENT_TYPE = "airline.hub_disruption.detected"
_INBOUND_SECTOR_ID = "SYN-SECTOR-IN-001"
_CONSTRAINED_STAND_ID = "SYN-STAND-01"
_INBOUND_DELAY_MINUTES = 45


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
        self._installed = False
        self._scenario_events: dict[str, SimulationEvent] = {}

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
        self._installed = True

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
        if scenario_id != SCENARIO_ID:
            raise ValueError(f"unsupported Airline scenario: {scenario_id!r}")
        if not self._installed:
            raise RuntimeError("AirlineWorld must be installed before activation")
        existing = self._scenario_events.get(scenario_id)
        if existing is not None:
            return existing

        sector = self.sectors[_INBOUND_SECTOR_ID]
        stand = self.stands[_CONSTRAINED_STAND_ID]
        rotation = next(
            item for item in self.rotations.values() if sector.id in item.sector_ids
        )
        cohorts = [
            item
            for item in self.connection_cohorts.values()
            if item.inbound_sector_id == sector.id
        ]

        sector.delay_minutes = _INBOUND_DELAY_MINUTES
        sector.status = "delayed"
        sector.version += 1
        stand.status = "unavailable"
        stand.version += 1

        source = self.runtime.emit(
            _SOURCE_EVENT_TYPE,
            actor_id=f"scenario:{SCENARIO_ID}",
            target_id=sector.id,
            payload={
                "scenario_id": SCENARIO_ID,
                "story_id": STORY_ID,
                "inbound_sector_id": sector.id,
                "delay_minutes": sector.delay_minutes,
                "rotation_id": rotation.id,
                "stand_id": stand.id,
                "stand_status": stand.status,
                "connection_cohort_ids": [item.id for item in cohorts],
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
                "story_id": STORY_ID,
                "scenario_id": SCENARIO_ID,
                "source_event_id": source.event_id,
                "inbound_sector_id": sector.id,
                "stand_id": stand.id,
            },
        )
        self._scenario_events[scenario_id] = source
        return source

    def build_observation(
        self,
        sensor_event: dict[str, Any],
        *,
        now: float | None = None,
    ) -> dict[str, Any]:
        if (
            sensor_event.get("type") != "sensor.tripped"
            or sensor_event.get("actor_id") != SENSOR_ID
        ):
            raise ValueError("observation requires the integrated hub sensor event")
        payload = sensor_event.get("payload") or {}
        sector_id = payload.get("inbound_sector_id")
        stand_id = payload.get("stand_id")
        if sector_id not in self.sectors or stand_id not in self.stands:
            raise ValueError("integrated hub sensor references unknown world records")

        sector = self.sectors[sector_id]
        stand = self.stands[stand_id]
        rotation = next(
            item for item in self.rotations.values() if sector.id in item.sector_ids
        )
        cohorts = sorted(
            (
                item
                for item in self.connection_cohorts.values()
                if item.inbound_sector_id == sector.id
            ),
            key=lambda item: item.id,
        )
        return {
            "workflow_type": WORKFLOW_TYPE,
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
            "evidence_event_ids": [
                sensor_event.get("cause_event_id"),
                sensor_event.get("event_id"),
            ],
        }

    def render_state(self) -> dict[str, list[dict[str, Any]]]:
        def rows(records: dict[str, Any]) -> list[dict[str, Any]]:
            return [
                _record_view(record)
                for record in sorted(records.values(), key=lambda item: item.id)
            ]

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
        }
