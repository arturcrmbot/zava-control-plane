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
from api.server.world.registry import resolve_objective_route

log = logging.getLogger("world_bridge")

SENSOR_EVENT = "world.sensor.tripped"
_EVALUATION_EVENTS = (
    "world.evaluation.resolved",
    "world.evaluation.failed",
    "world.evaluation.timed_out",
)

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
        self._in_flight_event_ids: set[str] = set()
        self._workflow_by_objective: dict[str, tuple[str, str | None]] = {}
        self._decision_ready: set[str] = set()
        self._pending_evaluations: dict[str, dict] = {}
        self._tasks: set[asyncio.Task] = set()
        self._off: list = []
        # Canonical Workflow lifecycle owner: mints the one StateStore Workflow
        # (deterministic sensor-event id) before Durable scheduling and routes
        # every lifecycle transition through the shared WorkflowEventIngestor.
        self._adapter = WorldWorkflowAdapter(app_state)

    def start(self) -> None:
        self._off.append(self._bus.on(SENSOR_EVENT, self._on_sensor))
        for event_type in _EVALUATION_EVENTS:
            self._off.append(self._bus.on(event_type, self._on_evaluation))
        log.info("world_bridge: armed; listening for %s", SENSOR_EVENT)

    def stop(self) -> None:
        for off in self._off:
            off()
        self._off.clear()
        for task in tuple(self._tasks):
            task.cancel()
        self._tasks.clear()
        self._in_flight_event_ids.clear()
        self._workflow_by_objective.clear()
        self._decision_ready.clear()
        self._pending_evaluations.clear()

    def _spawn(self, coroutine) -> None:
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def _on_sensor(self, event: FleetEvent) -> None:
        simulation_event = getattr(event, "simulation_event", None)
        if not isinstance(simulation_event, dict):
            log.error("world_bridge: sensor event missing simulation_event: %s", event)
            return
        event_id = simulation_event.get("event_id")
        if not event_id:
            log.error("world_bridge: sensor event missing event_id: %s", simulation_event)
            return
        if event_id in self._in_flight_event_ids:
            return
        self._in_flight_event_ids.add(event_id)
        self._spawn(self._drive(simulation_event))

    def _on_evaluation(self, event: FleetEvent) -> None:
        simulation_event = getattr(event, "simulation_event", None)
        if not isinstance(simulation_event, dict):
            log.error("world_bridge: evaluation event missing simulation_event: %s", event)
            return
        outcome = simulation_event.get("payload")
        if not isinstance(outcome, dict):
            log.error("world_bridge: evaluation event missing payload: %s", simulation_event)
            return
        obj_id = outcome.get("objective_id")
        if not obj_id or obj_id not in self._workflow_by_objective:
            return
        self._pending_evaluations[str(obj_id)] = outcome
        if obj_id not in self._decision_ready:
            return
        self._spawn(self._complete_from_evaluation(str(obj_id), outcome))

    async def _complete_from_evaluation(
        self, objective_id: str, outcome: dict
    ) -> None:
        workflow = self._workflow_by_objective.pop(objective_id, None)
        self._decision_ready.discard(objective_id)
        self._pending_evaluations.pop(objective_id, None)
        if workflow is None:
            return
        workflow_id, instance_id = workflow
        if outcome.get("status") == "resolved":
            await self._adapter.resolved(workflow_id, instance_id, outcome)
            return
        await self._adapter.evaluation_failed(workflow_id, instance_id, outcome)

    async def _drive(self, simulation_event: dict) -> None:
        trace_id = simulation_event.get("trace_id")
        service = None
        requested = None
        objective = None
        workflow_id = None
        instance_id = None
        try:
            service = self._app.world_service
            try:
                route = resolve_objective_route(
                    service.registration, simulation_event.get("actor_id")
                )
            except ValueError:
                service.record_external(
                    "objective.unroutable",
                    trace_id=trace_id,
                    cause_event_id=simulation_event.get("event_id"),
                    payload={
                        "sensor_id": simulation_event.get("actor_id"),
                        "sensor_event_id": simulation_event.get("event_id"),
                    },
                )
                return
            observation = service.build_observation(simulation_event)

            responder = resolve_responder(
                self._app.runtime,
                route.objective_type,
            )
            objective = service.open_objective(
                simulation_event, route, owner_function=responder.owner_function
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

            # Create/upsert exactly one canonical Workflow BEFORE scheduling the
            # Durable orchestration. The adapter derives the workflow id
            # deterministically from the sensor event id; it is the ONLY id used
            # for the Durable payload, StateStore, AG-UI and EntityReflector —
            # there is no independent prefix-trace reconstruction anywhere here.
            workflow_id = self._adapter.start(
                simulation_event, objective, responder, observation
            )
            requested = service.record_external(
                "responder.requested",
                trace_id=trace_id,
                cause_event_id=simulation_event.get("event_id"),
                payload={
                    "observation": observation,
                    "objective_id": objective.id,
                    "workflow_id": workflow_id,
                    "workflow_type": responder.workflow_type,
                },
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
            self._workflow_by_objective[objective.id] = (workflow_id, instance_id)
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
                    payload={
                        "instance_id": instance_id,
                        "error": "no orchestration output",
                        "workflow_id": workflow_id,
                        "workflow_type": responder.workflow_type,
                    },
                )
                service.fail_objective(objective.id, cause_event_id=failed.event_id)
                self._workflow_by_objective.pop(objective.id, None)
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
                    payload={
                        "instance_id": instance_id,
                        "reasoning": reasoning,
                        "workflow_id": workflow_id,
                        "workflow_type": responder.workflow_type,
                    },
                )
                service.fail_objective(objective.id, cause_event_id=deferred.event_id)
                self._workflow_by_objective.pop(objective.id, None)
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
                payload={
                    "instance_id": instance_id,
                    "command": command_data,
                    "reasoning": reasoning,
                    "workflow_id": workflow_id,
                    "workflow_type": responder.workflow_type,
                },
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
                self._workflow_by_objective.pop(objective.id, None)
                await self._adapter.failed(workflow_id, instance_id, reason)
                log.info("world_bridge: %s rejected command=%s trace=%s reason=%s",
                         instance_id, command.type, trace_id, reason)
                return

            # Record the decision boundaries + stash the command on the canonical
            # Workflow. NONTERMINAL by design: the world command has been applied
            # but its recovery/effectiveness is evaluated in Phase 3, so the
            # bridge never marks the workflow completed/resolved here.
            await self._adapter.decided(workflow_id, instance_id, command_data, reasoning)
            self._decision_ready.add(objective.id)
            pending = self._pending_evaluations.get(objective.id)
            if pending is None:
                final_objective = service.objectives.get(objective.id)
                evaluation = service.evaluator.for_objective(objective.id)
                if (
                    final_objective is not None
                    and final_objective.status in {"resolved", "failed"}
                    and evaluation is not None
                ):
                    pending = evaluation.to_dict()
            if pending is not None:
                await self._complete_from_evaluation(objective.id, pending)
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
                        self._workflow_by_objective.pop(objective.id, None)
                    if workflow_id is not None:
                        await self._adapter.failed(workflow_id, instance_id, str(ex))
                except Exception:  # noqa: BLE001 — never let failure-reporting itself crash
                    log.exception(
                        "world_bridge: failed to record responder.failed for trace=%s", trace_id
                    )
        finally:
            self._in_flight_event_ids.discard(simulation_event.get("event_id"))

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
