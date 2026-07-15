"""World ↔ Durable bridge — closes the actor-simulation loop across processes.

This is the substrate glue that connects the live actor world (see
``api/server/world/service.py``) to a REAL Azure Durable Functions
orchestration. It lives on the FastAPI side (it imports the Durable client),
keeping ``api/server/world/`` free of any Durable dependency, exactly as the
spec's "couple only via the bus" seam requires.

Flow:
  1. Subscribe to the actor world's sensor event ``world.sensor.tripped``.
  2. On fire: extract the nested ``simulation_event``, build an observation
     from the live actor world, and open the world-pack's objective
     (``objective.opened``). A prior in-flight episode for the same objective
     (type + target) short-circuits here — no second orchestration.
  3. Claim the objective (``objective.claimed`` by the responder's owner
     function), journal ``responder.requested``, and schedule the responder
     resolved from the objective type — never a scenario branch
     (``SurgeStaffingOrchestrator`` for ``support_capacity``,
     ``NetworkIncidentOrchestrator`` for ``network_service_recovery``). Once
     scheduled, the objective moves to ``objective.acting``.
  4. Await the orchestration's completion and read its typed command.
  5. No command: journal ``responder.deferred`` and fail the objective — the
     world is unchanged. A command: journal ``responder.decided`` and apply it
     through ``world_service.apply_command`` — the world has been changed by a
     real Durable workflow. Any failure/timeout journals ``responder.failed``
     and fails the objective; the simulation keeps running.

One in-flight response is tracked per sensor trace (not a single global
flag), so independent trace firings never block each other.
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from api.shared.events import FleetEvent
from api.server.services.durable_client import schedule_new_orchestration
from api.server.services.world_responders import resolve_responder
from api.server.services.world_workflow_adapter import WorldWorkflowAdapter
from api.server.world.model import SimulationCommand
from api.server.world.objectives import objective_id

log = logging.getLogger("world_bridge")

SENSOR_EVENT = "world.sensor.tripped"

_TERMINAL_OK = "Completed"
_TERMINAL_BAD = {"Failed", "Terminated", "Canceled"}


def _command_failure_reason(result) -> str:
    payload = getattr(result, "payload", None)
    if isinstance(payload, dict):
        reason = payload.get("reason")
        if reason:
            return str(reason)
        if payload:
            return str(payload)
    return f"{getattr(result, 'type', 'command.rejected')} returned by world command gateway"


class WorldBridge:
    """Drives one Durable orchestration per sensor trace (never overlaps a trace)."""

    def __init__(self, app_state, *, poll_timeout: float = 90.0) -> None:
        self._app = app_state
        self._bus = app_state.bus
        self._poll_timeout = poll_timeout
        self._in_flight_traces: set[str] = set()
        self._off = None
        # Canonical Workflow lifecycle owner: mints the one StateStore Workflow
        # (deterministic sensor-event id) before Durable scheduling and routes
        # every lifecycle transition through the shared WorkflowEventIngestor.
        self._adapter = WorldWorkflowAdapter(app_state)

    def start(self) -> None:
        self._off = self._bus.on(SENSOR_EVENT, self._on_sensor)
        log.info("world_bridge: armed; listening for %s", SENSOR_EVENT)

    def stop(self) -> None:
        if self._off is not None:
            self._off()
            self._off = None
        self._in_flight_traces.clear()

    def _on_sensor(self, event: FleetEvent) -> None:
        simulation_event = getattr(event, "simulation_event", None)
        if not isinstance(simulation_event, dict):
            log.error("world_bridge: sensor event missing simulation_event: %s", event)
            return
        trace_id = simulation_event.get("trace_id")
        if not trace_id:
            log.error("world_bridge: sensor event missing trace_id: %s", simulation_event)
            return
        # Latched synchronously (before the task even runs) so a second sensor
        # firing for the same trace is suppressed while the first is in flight.
        if trace_id in self._in_flight_traces:
            return
        self._in_flight_traces.add(trace_id)
        asyncio.create_task(self._drive(simulation_event))

    async def _drive(self, simulation_event: dict) -> None:
        trace_id = simulation_event.get("trace_id")
        service = None
        requested = None
        objective = None
        workflow_id = None
        instance_id = None
        try:
            service = self._app.world_service
            observation = service.build_observation(simulation_event)

            responder = resolve_responder(service.registration.objective_type)
            objective = service.open_objective(
                simulation_event, owner_function=responder.owner_function
            )
            # A prior sensor episode already owns this (type + target)
            # objective: the manager returned it instead of a fresh one, so we
            # schedule no second orchestration for the same live objective.
            if objective.id != objective_id(simulation_event.get("event_id")):
                log.info("world_bridge: %s already active; skipping trace=%s",
                         objective.id, trace_id)
                return
            service.transition_objective(
                objective.id, "claimed", claimed_by=responder.owner_function
            )

            requested = service.record_external(
                "responder.requested",
                trace_id=trace_id,
                cause_event_id=simulation_event.get("event_id"),
                payload={"observation": observation, "objective_id": objective.id},
            )

            # Create/upsert exactly one canonical Workflow BEFORE scheduling the
            # Durable orchestration. The adapter derives the workflow id
            # deterministically from the sensor event id; it is the ONLY id used
            # for the Durable payload, StateStore, AG-UI and EntityReflector —
            # there is no independent prefix-trace reconstruction anywhere here.
            workflow_id = self._adapter.start(
                simulation_event, objective, responder, observation
            )

            payload = {
                "workflow_id": workflow_id,
                "type": responder.workflow_type,
                "trace_id": trace_id,
                "objective_id": objective.id,
                "observation": observation,
            }
            resp = await schedule_new_orchestration(payload, responder.orchestrator)
            instance_id = resp.get("id")
            status_uri = resp.get("statusQueryGetUri")
            log.info("world_bridge: scheduled %s instance=%s trace=%s",
                     responder.orchestrator, instance_id, trace_id)

            # Record ONLY the deterministic bridge-side Telemetry Correlation
            # boundary through the ingestor; the Durable orchestrator owns
            # workflow.started and emits it on the same ingestion path.
            await self._adapter.scheduled(workflow_id, instance_id)

            service.transition_objective(
                objective.id, "acting",
                cause_event_id=requested.event_id,
                payload={"instance_id": instance_id},
            )

            output = await self._await_output(instance_id, status_uri, responder.timeout_seconds)
            if not isinstance(output, dict):
                failed = service.record_external(
                    "responder.failed",
                    trace_id=trace_id,
                    cause_event_id=requested.event_id,
                    payload={"instance_id": instance_id, "error": "no orchestration output"},
                )
                service.fail_objective(objective.id, cause_event_id=failed.event_id)
                await self._adapter.failed(workflow_id, instance_id, "no orchestration output")
                log.error("world_bridge: %s produced no output for trace=%s", instance_id, trace_id)
                return

            command_data = output.get("command")
            reasoning = output.get("reasoning")
            if command_data is None:
                deferred = service.record_external(
                    "responder.deferred",
                    trace_id=trace_id,
                    cause_event_id=requested.event_id,
                    payload={"instance_id": instance_id, "reasoning": reasoning},
                )
                service.fail_objective(objective.id, cause_event_id=deferred.event_id)
                await self._adapter.failed(
                    workflow_id, instance_id, reasoning or "responder deferred"
                )
                log.info("world_bridge: %s deferred trace=%s reasoning=%s",
                         instance_id, trace_id, reasoning)
                return

            service.record_external(
                "responder.decided",
                trace_id=trace_id,
                cause_event_id=requested.event_id,
                payload={"instance_id": instance_id, "command": command_data, "reasoning": reasoning},
            )
            command = SimulationCommand(**command_data)
            result = service.apply_typed_command(objective, command)

            self._app.world_last_response = {
                "instance_id": instance_id,
                "observation": observation,
                "output": output,
                "command": command_data,
                "result_event_id": result.event_id,
                "result_type": result.type,
                "result_payload": getattr(result, "payload", None),
                "objective_id": objective.id,
                "workflow_id": workflow_id,
            }
            if result.type == "command.rejected":
                reason = _command_failure_reason(result)
                await self._adapter.failed(workflow_id, instance_id, reason)
                log.info("world_bridge: %s rejected command=%s trace=%s reason=%s",
                         instance_id, command.type, trace_id, reason)
                return

            # Record the decision boundaries + stash the command on the canonical
            # Workflow. NONTERMINAL by design: the world command has been applied
            # but its recovery/effectiveness is evaluated in Phase 3, so the
            # bridge never marks the workflow completed/resolved here.
            await self._adapter.decided(workflow_id, instance_id, command_data, reasoning)
            log.info("world_bridge: %s applied command=%s trace=%s",
                     instance_id, command.type, trace_id)
        except Exception as ex:  # noqa: BLE001 — bridge must never crash the simulation
            log.exception("world_bridge: drive failed for trace=%s: %s", trace_id, ex)
            if service is not None and trace_id:
                try:
                    failed = service.record_external(
                        "responder.failed",
                        trace_id=trace_id,
                        cause_event_id=requested.event_id if requested is not None else None,
                        payload={"error": str(ex)},
                    )
                    if objective is not None:
                        service.fail_objective(objective.id, cause_event_id=failed.event_id)
                    if workflow_id is not None:
                        await self._adapter.failed(workflow_id, instance_id, str(ex))
                except Exception:  # noqa: BLE001 — never let failure-reporting itself crash
                    log.exception(
                        "world_bridge: failed to record responder.failed for trace=%s", trace_id
                    )
        finally:
            self._in_flight_traces.discard(trace_id)

    async def _await_output(self, instance_id, status_uri, timeout: float | None = None):
        """Poll the Durable status endpoint until the orchestration is terminal."""
        if not status_uri:
            log.error("world_bridge: no statusQueryGetUri for %s", instance_id)
            return None
        deadline = asyncio.get_event_loop().time() + (timeout or self._poll_timeout)
        async with httpx.AsyncClient() as c:
            while asyncio.get_event_loop().time() < deadline:
                try:
                    data = (await c.get(status_uri, timeout=5)).json()
                    status = data.get("runtimeStatus")
                    if status == _TERMINAL_OK:
                        return data.get("output")
                    if status in _TERMINAL_BAD:
                        log.error("world_bridge: %s ended %s: %s",
                                  instance_id, status, data.get("output"))
                        return None
                except Exception:  # noqa: BLE001 — transient poll errors are fine
                    pass
                await asyncio.sleep(1.0)
        log.error("world_bridge: timed out awaiting %s", instance_id)
        return None
