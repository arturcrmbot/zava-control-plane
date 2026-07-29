"""Hospitality world registration and the shared-runtime scenario adapter.

``HospitalityScenario`` is a thin adapter: it owns one real
:class:`~verticals.hospitality.world.HospitalityWorld` and projects it onto the
generic ``SimulationRuntime`` surfaces the shared world service needs
(``install`` / ``render_state`` / ``build_observation`` / ``apply_command`` /
``run_scenario`` / ``run_reference_process``).

All causality is real: the hero process triggers the golden outage in the
underlying world, converts its genuine ``hotel.operations-risk.detected``
measurement into exactly one shared ``sensor.tripped`` event, and the hero
command is validated and applied by the underlying typed command layer.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from api.server.world.model import SimulationCommand, SimulationEvent
from api.server.world.runtime import SimulationRuntime
from api.shared.world_contracts import (
    ObjectiveRoute,
    ResponderRegistration,
    WorldPackRegistration,
    WorldScaleProfile,
    validate_world_scene,
)
from verticals.hospitality.process_profiles import (
    HospitalityProcessProfile,
    HOSPITALITY_PROCESS_PROFILES,
)
from verticals.hospitality.recovery import plan_recovery
from verticals.hospitality.reference_actions import HOSPITALITY_REFERENCE_ACTIONS
from verticals.hospitality.reference_cases import HOSPITALITY_REFERENCE_CASES
from verticals.hospitality.world import HospitalityWorld


PACK_ROOT = Path(__file__).resolve().parent

HERO_WORKFLOW = "hotel-operations-recovery"
GOLDEN_SCENARIO = "riverside-hot-water-outage"
HEARTBEAT_MINUTES = 15.0

# Bounded scene budget — the scene shows aggregates, never 240 rooms.
COVERAGE_SKILLS = ("housekeeping", "engineering")
ARRIVAL_BANDS = ("protected", "standard")
ROOM_TYPES = ("standard", "family", "accessible", "premium")

_TOOL_BY_WORKFLOW = {
    "hotel-operations-recovery": "hospitality_read_hotel_operations",
    "room-readiness-coordination": "hospitality_read_room_readiness",
    "asset-maintenance-response": "hospitality_read_asset_maintenance",
    "guest-service-recovery": "hospitality_read_guest_recovery",
    "occupancy-pressure-response": "hospitality_read_occupancy_pressure",
    "workforce-demand-balancing": "hospitality_read_workforce_demand",
    "food-and-beverage-readiness": "hospitality_read_food_beverage_readiness",
    "energy-anomaly-response": "hospitality_read_energy_anomaly",
}


def _profile_for_command(command_type: str) -> HospitalityProcessProfile | None:
    return next(
        (
            profile
            for profile in HOSPITALITY_PROCESS_PROFILES.values()
            if profile.command_type == command_type
        ),
        None,
    )


def _profile_for_sensor(sensor_id: str | None) -> HospitalityProcessProfile | None:
    return next(
        (
            profile
            for profile in HOSPITALITY_PROCESS_PROFILES.values()
            if profile.sensor_id == sensor_id
        ),
        None,
    )


class HospitalityScenario:
    """Adapter binding the deterministic hotel world to the shared runtime."""

    reference_process_types = tuple(HOSPITALITY_PROCESS_PROFILES)

    def __init__(self, runtime: SimulationRuntime) -> None:
        self.runtime = runtime
        self.world = HospitalityWorld.demo(runtime.seed)
        self._installed = False
        self._hero_result: dict[str, Any] | None = None
        self._reference_results: dict[str, dict[str, Any]] = {}
        self._applied_command_ids: set[str] = set()
        self._heartbeat = 0

    # -- lifecycle ---------------------------------------------------------

    def install(self) -> None:
        if self._installed:
            return
        self.world.reset(self.runtime.seed)
        self._installed = True
        self.runtime.process(self._heartbeat_lifecycle())

    def _heartbeat_lifecycle(self):
        """Keep the shared world service running without inventing an outage."""
        hotel_ids = tuple(self.world.hotels)
        while True:
            yield self.runtime.env.timeout(HEARTBEAT_MINUTES)
            self._heartbeat += 1
            hotel_id = hotel_ids[self._heartbeat % len(hotel_ids)]
            hotel = self.world.hotels[hotel_id]
            self.runtime.emit(
                "hotel.readiness.observed",
                actor_id=hotel_id,
                target_id=hotel_id,
                trace_id=f"hosp-heartbeat-{self.runtime.seed}",
                payload={
                    "location_id": hotel_id,
                    "status": hotel.status,
                    "occupancy_pct": hotel.occupancy_pct,
                    "arrivals_in_4h": hotel.arrivals_in_4h,
                },
            )

    # -- process entry points ---------------------------------------------

    def run_scenario(self, name: str) -> dict[str, Any]:
        if name != GOLDEN_SCENARIO:
            raise ValueError(f"unknown Hospitality scenario {name!r}")
        if self._hero_result is not None:
            return dict(self._hero_result)

        self.world.trigger_scenario(name)
        world_events = self.world.poll_sensor_events()
        if not world_events:
            raise ValueError(
                f"scenario {name!r} did not produce a hotel operations risk "
                "measurement"
            )
        world_event = world_events[0]
        profile = HOSPITALITY_PROCESS_PROFILES[HERO_WORKFLOW]
        case = HOSPITALITY_REFERENCE_CASES[HERO_WORKFLOW]
        measurement = dict(world_event.payload)

        detected = self.runtime.emit(
            world_event.type,
            actor_id=world_event.source,
            target_id=measurement["hotel_id"],
            trace_id=world_event.trace_id,
            payload={
                "location_id": measurement["hotel_id"],
                "scenario": name,
                "world_event_id": world_event.event_id,
                "actor_ids": list(world_event.actor_ids),
                "measurements": measurement,
            },
        )
        tripped = self.runtime.emit(
            "sensor.tripped",
            actor_id=profile.sensor_id,
            target_id=measurement["hotel_id"],
            cause_event_id=detected.event_id,
            trace_id=world_event.trace_id,
            payload={
                "workflow_type": HERO_WORKFLOW,
                "case_id": case.id,
                "location_id": measurement["hotel_id"],
                "world_event_id": world_event.event_id,
                "world_event_type": world_event.type,
                "actor_ids": list(world_event.actor_ids),
                "measurements": measurement,
                "threshold": {
                    "crossed": True,
                    "occupancy_pct_gte": 0.90,
                    "affected_rooms_gte": 10,
                    "critical_asset_fault": True,
                },
            },
        )
        self._hero_result = {
            "event_id": tripped.event_id,
            "trace_id": tripped.trace_id,
            "case_id": case.id,
            "world_event_id": world_event.event_id,
        }
        return dict(self._hero_result)

    def run_reference_process(self, workflow_type: str) -> dict[str, Any]:
        profile = HOSPITALITY_PROCESS_PROFILES.get(workflow_type)
        if profile is None:
            raise ValueError(f"unknown Hospitality process {workflow_type!r}")
        if workflow_type == HERO_WORKFLOW:
            return self.run_scenario(GOLDEN_SCENARIO)
        cached = self._reference_results.get(workflow_type)
        if cached is not None:
            return dict(cached)

        case = HOSPITALITY_REFERENCE_CASES[workflow_type]
        location_id = next(
            (
                subject
                for subject in case.subject_ids
                if subject in self.world.hotels
            ),
            None,
        )
        event = self.runtime.emit(
            "sensor.tripped",
            actor_id=profile.sensor_id,
            target_id=case.subject_ids[0] if case.subject_ids else case.id,
            trace_id=f"hosp-{profile.prefix}-{self.runtime.seed}",
            payload={
                "workflow_type": workflow_type,
                "case_id": case.id,
                "location_id": location_id,
                "actor_ids": list(case.subject_ids),
                "measurements": dict(case.facts),
                "diagnostic": True,
            },
        )
        result = {
            "event_id": event.event_id,
            "trace_id": event.trace_id,
            "case_id": case.id,
        }
        self._reference_results[workflow_type] = result
        return dict(result)

    # -- observation -------------------------------------------------------

    def build_observation(
        self,
        sensor_event: dict[str, Any],
        *,
        now: float,
    ) -> dict[str, Any]:
        sensor_id = sensor_event.get("actor_id")
        profile = _profile_for_sensor(sensor_id)
        if profile is None:
            raise ValueError(f"unknown Hospitality sensor {sensor_id!r}")
        payload = sensor_event.get("payload") or {}
        case = HOSPITALITY_REFERENCE_CASES[profile.workflow_type]
        actor_ids = [
            str(value) for value in payload.get("actor_ids") or case.subject_ids
        ]
        observation: dict[str, Any] = {
            "workflow_type": profile.workflow_type,
            "case": {
                "id": case.id,
                "workflow_type": case.workflow_type,
                "subject_ids": list(case.subject_ids),
                "facts": dict(case.facts),
            },
            "actor_ids": actor_ids,
            "event_ids": [str(sensor_event["event_id"])],
            "trace_id": str(sensor_event["trace_id"]),
            "as_of_sim_time": float(now),
            "measurements": dict(payload.get("measurements") or {}),
            "skills": [profile.skill],
            "mcp_tools": [_TOOL_BY_WORKFLOW[profile.workflow_type]],
            "authority": {
                "persona": profile.hitl_persona,
                "external_event": profile.hitl_event,
            },
            "policy": {
                "decision": "approval_required",
                "reason": f"{profile.hitl_event} is required for "
                f"{profile.display_name}",
                "persona": profile.hitl_persona,
            },
            "typed_command": profile.command_type,
        }
        world_event_id = payload.get("world_event_id")
        if world_event_id:
            observation["world_event_id"] = str(world_event_id)
        if profile.workflow_type == HERO_WORKFLOW:
            observation["recovery_plan"] = self._recovery_plan_summary()
            observation["policy"]["reason"] = (
                "cross-property relocation requires named approval"
            )
        return observation

    def _recovery_plan_summary(self) -> dict[str, Any]:
        result = plan_recovery(self.world.snapshot())
        if result.status != "selected" or result.plan is None:
            return {
                "status": result.status,
                "binding_constraints": list(result.binding_constraints),
            }
        plan = result.plan
        return {
            "status": result.status,
            "plan_id": plan.plan_id,
            "work_order_id": plan.work_order_id,
            "rooms_to_restore": len(plan.rooms_to_restore),
            "relocations": len(plan.relocations),
            "shift_moves": len(plan.shift_reallocations),
            "requires_hitl": plan.requires_hitl,
            "estimated_recovery_cost_gbp": plan.estimated_recovery_cost_gbp,
            "revenue_protected_gbp": plan.revenue_protected_gbp,
            "residual_shortfall": plan.residual_shortfall,
            "guest_disruption_count": plan.guest_disruption_count,
            "binding_constraints": list(plan.binding_constraints),
            "evidence_versions": dict(plan.evidence_versions),
        }

    # -- commands ----------------------------------------------------------

    def apply_command(self, command: SimulationCommand) -> SimulationEvent:
        if command.command_id in self._applied_command_ids:
            return self.runtime.emit(
                "command.duplicate",
                actor_id=command.issued_by,
                trace_id=command.trace_id,
                payload={"command_id": command.command_id},
            )

        payload = command.payload or {}
        workflow_type = str(payload.get("workflow_type") or "")
        profile = HOSPITALITY_PROCESS_PROFILES.get(workflow_type)
        if profile is None:
            profile = _profile_for_command(command.type)
        if profile is None:
            return self._reject(command, f"unknown command type {command.type!r}")
        if profile.command_type != command.type:
            return self._reject(
                command,
                f"command {command.type!r} does not belong to "
                f"{profile.workflow_type!r}",
            )

        approval_decision = payload.get("approval_decision")
        if profile.hitl_persona and approval_decision != "approve":
            return self._reject(
                command,
                f"{profile.hitl_event} approval is required",
            )
        evidence_digest = payload.get("evidence_digest")
        if not evidence_digest:
            return self._reject(command, "validated evidence digest is required")

        if profile.workflow_type == HERO_WORKFLOW and self._hero_result is None:
            return self._reject(
                command,
                "hero command requires the golden scenario to have run",
            )

        try:
            action = dict(
                HOSPITALITY_REFERENCE_ACTIONS[profile.workflow_type](self.world)
            )
        except ValueError as error:
            return self._reject(command, str(error))

        approval_reference = payload.get("approval_reference")
        action.update(
            {
                "command_id": command.command_id,
                "workflow_id": str(
                    payload.get("workflow_id") or command.command_id
                ),
                "evidence_digest": str(evidence_digest),
                "approval_ref": (
                    f"{profile.hitl_event}:approved:{approval_reference}"
                    if approval_reference
                    else action.get("approval_ref")
                ),
            }
        )

        result = self.world.apply_command(action)
        if not result.accepted:
            return self._reject(
                command,
                f"{result.reason}: {json.dumps(dict(result.details), sort_keys=True)}",
            )

        self._applied_command_ids.add(command.command_id)
        accepted = self.runtime.emit(
            "command.accepted",
            actor_id=command.issued_by,
            target_id=action["workflow_id"],
            trace_id=command.trace_id,
            payload={"command": command.to_dict()},
        )
        summaries: dict[str, int] = {}
        for event in result.events:
            summaries[event.type] = summaries.get(event.type, 0) + 1
        return self.runtime.emit(
            profile.success_event,
            actor_id=command.issued_by,
            target_id=self._primary_location(profile.workflow_type),
            cause_event_id=accepted.event_id,
            trace_id=command.trace_id,
            payload={
                "workflow_id": action["workflow_id"],
                "workflow_type": profile.workflow_type,
                "command_id": command.command_id,
                "location_id": self._primary_location(profile.workflow_type),
                "approval_reference": approval_reference,
                "evidence_digest": str(evidence_digest),
                "world_events": summaries,
                "world_snapshot_digest": result.snapshot_digest,
                "measurements": self._success_measurements(
                    profile.workflow_type, summaries
                ),
            },
        )

    def _success_measurements(
        self,
        workflow_type: str,
        summaries: dict[str, int],
    ) -> dict[str, Any]:
        measurements: dict[str, Any] = {
            "world_event_count": sum(summaries.values()),
        }
        if workflow_type == HERO_WORKFLOW:
            measurements.update(
                {
                    "rooms_restored": summaries.get(
                        "hotel-recovery.room.restored", 0
                    ),
                    "bookings_relocated": summaries.get(
                        "hotel-recovery.booking.relocated", 0
                    ),
                    "shifts_reallocated": summaries.get(
                        "hotel-recovery.shift.reallocated", 0
                    ),
                    "work_orders_expedited": summaries.get(
                        "hotel-recovery.work-order.expedited", 0
                    ),
                }
            )
        hotel_id = self._primary_location(workflow_type)
        hotel = self.world.hotels.get(hotel_id or "")
        if hotel is not None:
            measurements["sellable_rooms"] = (
                hotel.available_standard_rooms
                + hotel.available_family_rooms
                + hotel.available_accessible_rooms
                + hotel.available_premium_rooms
            )
            measurements["occupancy_pct"] = hotel.occupancy_pct
        return measurements

    def _primary_location(self, workflow_type: str) -> str | None:
        case = HOSPITALITY_REFERENCE_CASES[workflow_type]
        return next(
            (
                subject
                for subject in case.subject_ids
                if subject in self.world.hotels
            ),
            None,
        )

    def _reject(self, command: SimulationCommand, reason: str) -> SimulationEvent:
        return self.runtime.emit(
            "command.rejected",
            actor_id=command.issued_by,
            trace_id=command.trace_id,
            payload={"command": command.to_dict(), "reason": reason},
        )

    # -- render ------------------------------------------------------------

    def render_state(self) -> dict[str, Any]:
        return {
            "room_blocks": self._room_blocks(),
            "critical_assets": self._critical_assets(),
            "work_orders": self._work_orders(),
            "coverage": self._coverage(),
            "arrivals": self._arrivals(),
            "hotels": [
                {
                    "id": hotel.id,
                    "location_id": hotel.id,
                    "label": hotel.name,
                    "status": hotel.status,
                    "occupancy_pct": hotel.occupancy_pct,
                    "arrivals_in_4h": hotel.arrivals_in_4h,
                }
                for hotel in self.world.hotels.values()
            ],
            "threshold_state": {
                "sensor_id": HOSPITALITY_PROCESS_PROFILES[
                    HERO_WORKFLOW
                ].sensor_id,
                "active": self._hero_result is not None,
                "scenario": self.world.snapshot()["scenario"],
            },
            "ordinary_activity_count": self._heartbeat,
        }

    def _room_blocks(self) -> list[dict[str, Any]]:
        blocks: dict[tuple[str, str], dict[str, Any]] = {
            (hotel_id, room_type): {
                "id": f"BLOCK-{hotel_id}-{room_type.upper()}",
                "location_id": hotel_id,
                "room_type": room_type,
                "total": 0,
                "available": 0,
                "unavailable": 0,
                "not_ready": 0,
                "occupied": 0,
                "status": "ready",
            }
            for hotel_id in self.world.hotels
            for room_type in ROOM_TYPES
        }
        for room in self.world.rooms.values():
            block = blocks.get((room.hotel_id, room.room_type))
            if block is None:
                continue
            block["total"] += 1
            if room.status in block:
                block[room.status] += 1
        for block in blocks.values():
            if block["unavailable"]:
                block["status"] = "out-of-service"
            elif block["not_ready"]:
                block["status"] = "not-ready"
            elif block["available"]:
                block["status"] = "ready"
            else:
                block["status"] = "fully-occupied"
        return list(blocks.values())

    def _critical_assets(self) -> list[dict[str, Any]]:
        return [
            {
                "id": asset.id,
                "location_id": asset.hotel_id,
                "asset_type": asset.asset_type,
                "status": asset.status,
                "affected_rooms": len(asset.affected_room_ids),
            }
            for asset in self.world.critical_assets.values()
        ]

    def _work_orders(self) -> list[dict[str, Any]]:
        return [
            {
                "id": order.id,
                "location_id": order.hotel_id,
                "status": order.status,
                "priority": order.priority,
                "asset_id": order.asset_id,
            }
            for order in self.world.work_orders.values()
        ]

    def _coverage(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for hotel_id in self.world.hotels:
            for skill in COVERAGE_SKILLS:
                members = [
                    member
                    for member in self.world.team_members.values()
                    if member.hotel_id == hotel_id and member.skill == skill
                ]
                available = sum(
                    1 for member in members if member.status == "available"
                )
                shifts = [
                    shift
                    for shift in self.world.shifts.values()
                    if shift.hotel_id == hotel_id and shift.skill == skill
                ]
                rows.append(
                    {
                        "id": f"COVER-{hotel_id}-{skill.upper()}",
                        "location_id": hotel_id,
                        "skill": skill,
                        "headcount": len(members),
                        "available": available,
                        "shifts": len(shifts),
                        "status": "covered" if available else "uncovered",
                    }
                )
        return rows

    def _arrivals(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for hotel_id in self.world.hotels:
            for band in ARRIVAL_BANDS:
                protected = band == "protected"
                bookings = [
                    booking
                    for booking in self.world.bookings.values()
                    if booking.hotel_id == hotel_id
                    and booking.status == "arriving"
                    and booking.protected is protected
                ]
                rows.append(
                    {
                        "id": f"ARRIVALS-{hotel_id}-{band.upper()}",
                        "location_id": hotel_id,
                        "band": band,
                        "count": len(bookings),
                        "status": (
                            f"{len(bookings)} arriving" if bookings else "clear"
                        ),
                    }
                )
        return rows


def build_hospitality_demo(runtime: SimulationRuntime) -> HospitalityScenario:
    return HospitalityScenario(runtime)


_SCENE = validate_world_scene(
    json.loads((PACK_ROOT / "ui" / "world-scene.json").read_text(encoding="utf-8"))
)

HOSPITALITY_WORLD = WorldPackRegistration(
    name="hospitality",
    scales={
        "demo": WorldScaleProfile(
            name="demo",
            build_scenario=build_hospitality_demo,
            default_minutes_per_second=6.0,
        )
    },
    default_scale="demo",
    objective_routes=tuple(
        ObjectiveRoute(
            sensor_id=profile.sensor_id,
            objective_type=profile.objective_type,
            allowed_command_types=frozenset({profile.command_type}),
            success_event_types=frozenset({profile.success_event}),
            failure_event_types=frozenset({"command.rejected"}),
            evaluation_timeout_minutes=180.0,
        )
        for profile in HOSPITALITY_PROCESS_PROFILES.values()
    ),
    responders={
        profile.objective_type: ResponderRegistration(
            objective_type=profile.objective_type,
            orchestrator=profile.orchestrator,
            workflow_type=profile.workflow_type,
            prefix=profile.prefix,
            owner_function=profile.function,
            timeout_seconds=900.0,
            observation_key="hospitality_case",
        )
        for profile in HOSPITALITY_PROCESS_PROFILES.values()
    },
    scene=_SCENE,
)

HOSPITALITY_WORLDS = {"hospitality": HOSPITALITY_WORLD}
