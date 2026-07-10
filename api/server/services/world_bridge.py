"""World ↔ Durable bridge — closes the world-simulator loop across processes.

This is the substrate glue that connects the (industry-generic) world engine to
a REAL Azure Durable Functions orchestration. It lives on the FastAPI side (it
imports the Durable client), keeping ``api/server/world/`` free of any Durable
dependency, exactly as the spec's "couple only via the bus" seam requires.

Flow:
  1. Subscribe to the world engine's sensor event ``ops.surge_staffing.requested``.
  2. On fire: snapshot world state and schedule the ``SurgeStaffingOrchestrator``
     on the func host (:7071) with that snapshot as input.
  3. Await the orchestration's completion and read the agent's decision (hired).
  4. Emit ``surge-staffing.completed(hired=N)`` on the bus — the world engine's
     actuator consumes it and raises agent capacity, so the simulated backlog
     drains. The world has been changed by a real Durable workflow.
"""
from __future__ import annotations

import asyncio
import logging
import time

import httpx

from api.shared.events import FleetEvent
from api.server.services.durable_client import schedule_new_orchestration

log = logging.getLogger("world_bridge")

SENSOR_EVENT = "ops.surge_staffing.requested"
ORCHESTRATOR = "SurgeStaffingOrchestrator"
COMPLETION_EVENT = "surge-staffing.completed"

_TERMINAL_OK = "Completed"
_TERMINAL_BAD = {"Failed", "Terminated", "Canceled"}


class WorldBridge:
    """Drives one Durable orchestration per sensor firing (serialised)."""

    def __init__(self, app_state, *, poll_timeout: float = 90.0) -> None:
        self._app = app_state
        self._bus = app_state.bus
        self._poll_timeout = poll_timeout
        self._in_flight = False
        self._off = None

    def start(self) -> None:
        self._off = self._bus.on(SENSOR_EVENT, self._on_sensor)
        log.info("world_bridge: armed; listening for %s", SENSOR_EVENT)

    def stop(self) -> None:
        if self._off is not None:
            self._off()
            self._off = None

    def _on_sensor(self, event: FleetEvent) -> None:
        # Sensor is edge-latched, but guard against overlapping episodes anyway.
        if self._in_flight:
            return
        self._in_flight = True
        asyncio.create_task(self._drive(event))

    async def _drive(self, event: FleetEvent) -> None:
        try:
            snapshot = self._snapshot()
            workflow_id = f"surge-{int(time.time() * 1000)}"
            payload = {"workflow_id": workflow_id, "type": "surge-staffing", "world": snapshot}

            resp = await schedule_new_orchestration(payload, ORCHESTRATOR)
            instance_id = resp.get("id")
            status_uri = resp.get("statusQueryGetUri")
            log.info("world_bridge: scheduled %s instance=%s world=%s",
                     ORCHESTRATOR, instance_id, snapshot)

            output = await self._await_output(instance_id, status_uri)
            hired = float(output.get("hired", 0.0)) if isinstance(output, dict) else 0.0

            self._app.world_last_response = {
                "instance_id": instance_id,
                "snapshot": snapshot,
                "output": output,
                "hired": hired,
                "at": time.time(),
            }
            self._bus.emit(FleetEvent(type=COMPLETION_EVENT, hired=hired, instance_id=instance_id))
            log.info("world_bridge: %s Completed hired=%s -> emitted %s",
                     instance_id, hired, COMPLETION_EVENT)
        except Exception as ex:  # noqa: BLE001 — bridge must never crash the loop
            log.exception("world_bridge: drive failed: %s", ex)
        finally:
            self._in_flight = False

    def _snapshot(self) -> dict:
        engine = getattr(self._app, "world_engine", None)
        st = engine.state
        return {
            "backlog": round(st.stocks.get("support_backlog", 0.0), 2),
            "arrival": round(st.inputs.get("ticket_arrival_rate", 0.0), 2),
            "agents": round(st.resources.get("agents", 0.0), 2),
            "handle": st.constants.get("HANDLE", 1.0),
        }

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
