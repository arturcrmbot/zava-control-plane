"""World ↔ Durable bridge — closes the actor-simulation loop across processes.

This is the substrate glue that connects the live actor world (see
``api/server/world/service.py``) to a REAL Azure Durable Functions
orchestration. It lives on the FastAPI side (it imports the Durable client),
keeping ``api/server/world/`` free of any Durable dependency, exactly as the
spec's "couple only via the bus" seam requires.

Flow:
  1. Subscribe to the actor world's sensor event ``world.sensor.tripped``.
  2. On fire: extract the nested ``simulation_event``, build an observation
     from the live actor world, and journal ``responder.requested``.
  3. Schedule the scenario's Durable responder on the func host (:7071) with
     the trace ID and observation as input (``SurgeStaffingOrchestrator`` for
     support, ``NetworkIncidentOrchestrator`` for telco).
  4. Await the orchestration's completion and read its typed command.
  5. No command: journal ``responder.deferred`` — the world is unchanged. A
     command: journal ``responder.decided`` and apply it through
     ``world_service.apply_command`` — the world has been changed by a real
     Durable workflow. Any failure/timeout journals ``responder.failed`` and
     the simulation keeps running.

One in-flight response is tracked per sensor trace (not a single global
flag), so independent trace firings never block each other.
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from api.shared.events import FleetEvent
from api.server.services.durable_client import schedule_new_orchestration
from api.server.world.model import SimulationCommand

log = logging.getLogger("world_bridge")

SENSOR_EVENT = "world.sensor.tripped"

# One Durable responder per live scenario. Exactly one world is active per
# process (selected by ZAVA_WORLD in main.py); the bridge picks the responder
# from the service's ``scenario_name`` (defaulting to support so any service
# stand-in without the attribute keeps the original behaviour).
_RESPONDERS: dict[str, dict[str, str]] = {
    "support": {
        "orchestrator": "SurgeStaffingOrchestrator",
        "type": "surge-staffing",
        "prefix": "surge",
    },
    "telco": {
        "orchestrator": "NetworkIncidentOrchestrator",
        "type": "network-incident",
        "prefix": "incident",
    },
}

_TERMINAL_OK = "Completed"
_TERMINAL_BAD = {"Failed", "Terminated", "Canceled"}


class WorldBridge:
    """Drives one Durable orchestration per sensor trace (never overlaps a trace)."""

    def __init__(self, app_state, *, poll_timeout: float = 90.0) -> None:
        self._app = app_state
        self._bus = app_state.bus
        self._poll_timeout = poll_timeout
        self._in_flight_traces: set[str] = set()
        self._off = None

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
        try:
            service = self._app.world_service
            observation = service.build_observation(simulation_event)
            requested = service.record_external(
                "responder.requested",
                trace_id=trace_id,
                cause_event_id=simulation_event.get("event_id"),
                payload={"observation": observation},
            )

            responder = _RESPONDERS.get(
                getattr(service, "scenario_name", "support"), _RESPONDERS["support"]
            )
            orchestrator = responder["orchestrator"]
            payload = {
                "workflow_id": f"{responder['prefix']}-{trace_id}",
                "type": responder["type"],
                "trace_id": trace_id,
                "observation": observation,
            }
            resp = await schedule_new_orchestration(payload, orchestrator)
            instance_id = resp.get("id")
            status_uri = resp.get("statusQueryGetUri")
            log.info("world_bridge: scheduled %s instance=%s trace=%s",
                     orchestrator, instance_id, trace_id)

            output = await self._await_output(instance_id, status_uri)
            if not isinstance(output, dict):
                service.record_external(
                    "responder.failed",
                    trace_id=trace_id,
                    cause_event_id=requested.event_id,
                    payload={"instance_id": instance_id, "error": "no orchestration output"},
                )
                log.error("world_bridge: %s produced no output for trace=%s", instance_id, trace_id)
                return

            command_data = output.get("command")
            reasoning = output.get("reasoning")
            if command_data is None:
                service.record_external(
                    "responder.deferred",
                    trace_id=trace_id,
                    cause_event_id=requested.event_id,
                    payload={"instance_id": instance_id, "reasoning": reasoning},
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
            result = service.apply_command(command)

            self._app.world_last_response = {
                "instance_id": instance_id,
                "observation": observation,
                "output": output,
                "command": command_data,
                "result_event_id": result.event_id,
                "result_type": result.type,
            }
            log.info("world_bridge: %s applied command=%s trace=%s",
                     instance_id, command.type, trace_id)
        except Exception as ex:  # noqa: BLE001 — bridge must never crash the simulation
            log.exception("world_bridge: drive failed for trace=%s: %s", trace_id, ex)
            if service is not None and trace_id:
                try:
                    service.record_external(
                        "responder.failed",
                        trace_id=trace_id,
                        cause_event_id=requested.event_id if requested is not None else None,
                        payload={"error": str(ex)},
                    )
                except Exception:  # noqa: BLE001 — never let failure-reporting itself crash
                    log.exception(
                        "world_bridge: failed to record responder.failed for trace=%s", trace_id
                    )
        finally:
            self._in_flight_traces.discard(trace_id)

    async def _await_output(self, instance_id, status_uri):
        """Poll the Durable status endpoint until the orchestration is terminal."""
        if not status_uri:
            log.error("world_bridge: no statusQueryGetUri for %s", instance_id)
            return None
        deadline = asyncio.get_event_loop().time() + self._poll_timeout
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
