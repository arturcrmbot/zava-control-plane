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
from types import SimpleNamespace

import httpx

from api.shared.events import FleetEvent
from api.server.services.durable_client import schedule_new_orchestration
from api.server.services.world_responders import resolve_responder
from api.server.services.world_workflow_adapter import WorldWorkflowAdapter, workflow_id_for
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


def _hitl_gate(data) -> dict | None:
    """Extract a HITL wait declaration from a Durable status-query response.

    Any generated orchestrator (of any vertical) may call the standard,
    non-Travel-specific ``context.set_custom_status(...)`` right before
    racing a HITL wait; that value round-trips onto this same status-query
    response's ``customStatus`` field. Returns the raw ``customStatus`` dict
    only when it plausibly declares an active wait -- a truthy ``phase`` AND
    a truthy ``external_event`` -- else ``None``. Never guesses or fabricates
    a gate from a missing/malformed ``customStatus``; pure and side-effect
    free so it needs no HTTP/async fixture to test.
    """
    if not isinstance(data, dict):
        return None
    status = data.get("customStatus")
    if not isinstance(status, dict):
        return None
    if not status.get("phase") or not status.get("external_event"):
        return None
    return status


def _sensor_id(simulation_event: dict) -> str | None:
    """Resolve the registered ``ObjectiveRoute.sensor_id`` for a raw sensor event.

    Most detectors reuse ``actor_id`` to carry the sensor id directly. Some
    need ``actor_id`` for their own causal-chain identity instead (e.g. which
    disruption/resource record tripped the condition) and publish the
    intended route's sensor id inside ``payload["sensor_id"]``. Prefers the
    payload value when present so both conventions route correctly; falls
    back to ``actor_id`` so every existing detector without that payload key
    keeps working unchanged. Pure and side-effect free.
    """
    payload = simulation_event.get("payload")
    if isinstance(payload, dict):
        sensor_id = payload.get("sensor_id")
        if sensor_id:
            return sensor_id
    return simulation_event.get("actor_id")


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
        self._off: list = []
        # Canonical Workflow lifecycle owner: mints the one StateStore Workflow
        # only after Durable accepts the deterministic sensor-event id, then routes
        # every lifecycle transition through the shared WorkflowEventIngestor.
        self._adapter = WorldWorkflowAdapter(app_state)

    def start(self) -> None:
        self._off.append(self._bus.on(SENSOR_EVENT, self._on_sensor))
        for event_type in _EVALUATION_EVENTS:
            self._off.append(self._bus.on(event_type, self._on_evaluation))
        log.info("world_bridge: armed; listening for %s", SENSOR_EVENT)

    async def start_diagnostic(
        self,
        *,
        sensor_event: dict,
        responder,
        observation: dict,
    ) -> str:
        """Start a real Durable diagnostic without a live actor-world service."""
        sensor_event_id = sensor_event["event_id"]
        workflow_id = workflow_id_for(responder.prefix, sensor_event_id)
        existing = self._app.store.get_workflow(workflow_id)
        if existing is not None:
            return workflow_id

        trace_id = sensor_event.get("trace_id")
        objective = SimpleNamespace(
            id=f"diagnostic-{sensor_event_id}",
            trace_id=trace_id,
        )
        payload = {
            "workflow_id": workflow_id,
            "type": responder.workflow_type,
            "trace_id": trace_id,
            "objective_id": objective.id,
            "observation": observation,
        }
        response = await schedule_new_orchestration(payload, responder.orchestrator)
        instance_id = response.get("id")
        status_uri = response.get("statusQueryGetUri")
        workflow_id = self._adapter.start(
            sensor_event, objective, responder, observation
        )
        self._workflow_by_objective[objective.id] = (workflow_id, instance_id)
        await self._adapter.scheduled(workflow_id, instance_id)
        asyncio.create_task(
            self._finish_diagnostic(
                objective.id,
                workflow_id,
                instance_id,
                status_uri,
                responder.timeout_seconds,
                sensor_event,
            )
        )
        return workflow_id

    async def _finish_diagnostic(
        self,
        objective_id: str,
        workflow_id: str,
        instance_id: str | None,
        status_uri: str | None,
        timeout: float,
        sensor_event: dict,
    ) -> None:
        """Close only a diagnostic result with a real typed command."""
        try:
            output = await self._await_output(instance_id, status_uri, timeout)
            if not isinstance(output, dict):
                await self._adapter.failed(
                    workflow_id, instance_id, "diagnostic Durable output was unavailable"
                )
                return
            if output.get("workflow_id") != workflow_id:
                await self._adapter.failed(
                    workflow_id, instance_id, "diagnostic Durable output changed workflow id"
                )
                return
            if not isinstance(output.get("command"), dict):
                await self._adapter.failed(
                    workflow_id, instance_id, "diagnostic Durable output had no typed command"
                )
                return
            workflow = self._app.store.get_workflow(workflow_id)
            if workflow is not None:
                if not isinstance(workflow.payload, dict):
                    workflow.payload = {}
                workflow.payload["evidence"] = output
                workflow.payload["diagnostic"] = {
                    "source_sensor_event_id": (
                        sensor_event.get("payload") or {}
                    ).get("source_sensor_event_id"),
                    "actor_world_enabled": False,
                }
                workflow.metadata = dict(workflow.metadata or {})
                workflow.metadata["diagnostic_only"] = True
                self._app.store.upsert_workflow(workflow)
            await self._adapter.resolved(
                workflow_id,
                instance_id,
                {
                    "status": "diagnostic_completed",
                    "diagnostic": True,
                    "evidence_event_type": "Durable diagnostic",
                },
            )
        except Exception as ex:  # noqa: BLE001 -- persist diagnostic failure
            log.exception("world_bridge: diagnostic failed workflow=%s", workflow_id)
            await self._adapter.failed(workflow_id, instance_id, str(ex))
        finally:
            self._workflow_by_objective.pop(objective_id, None)

    def stop(self) -> None:
        for off in self._off:
            off()
        self._off.clear()
        self._in_flight_event_ids.clear()
        self._workflow_by_objective.clear()
        self._decision_ready.clear()
        self._pending_evaluations.clear()

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
        asyncio.create_task(self._drive(simulation_event))

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
        asyncio.create_task(
            self._complete_from_evaluation(str(obj_id), outcome)
        )

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
            sensor_id = _sensor_id(simulation_event)
            try:
                route = resolve_objective_route(service.registration, sensor_id)
            except ValueError:
                service.record_external(
                    "objective.unroutable",
                    trace_id=trace_id,
                    cause_event_id=simulation_event.get("event_id"),
                    payload={
                        "sensor_id": sensor_id,
                        "sensor_event_id": simulation_event.get("event_id"),
                    },
                )
                return
            observation = service.build_observation(simulation_event)

            responder = resolve_responder(
                self._app.runtime,
                route.objective_type,
            )

            # Transport-level duplicate guard: the canonical Workflow id is
            # deterministic in the sensor event id alone
            # (`workflow_id_for`/`WorldWorkflowAdapter.start`). If a workflow
            # for THIS exact event id already carries a Durable
            # `orchestration_instance_id`, this is a redelivery (e.g.
            # at-least-once transport replay) of an event we have already
            # scheduled -- a pure no-op, checked BEFORE opening/re-claiming
            # any objective so a redelivery can never re-run the claim/act
            # sequence or schedule a second orchestration. This is stronger
            # than the "already active" objective check below: that one only
            # stops a *different*, overlapping sensor event while a prior
            # objective for the same (type, target) is still live: it does
            # nothing once the objective has gone terminal (or a permissive
            # world hands back a fresh-looking objective for the identical
            # id), since `objective.id` still equals `objective_id(event_id)`
            # in either case.
            sensor_event_id = simulation_event.get("event_id")
            prospective_workflow_id = workflow_id_for(responder.prefix, sensor_event_id)
            already_scheduled = self._app.store.get_workflow(prospective_workflow_id)
            if already_scheduled is not None and already_scheduled.orchestration_instance_id:
                log.info(
                    "world_bridge: workflow %s already scheduled instance=%s; "
                    "skipping duplicate delivery trace=%s",
                    prospective_workflow_id,
                    already_scheduled.orchestration_instance_id,
                    trace_id,
                )
                return

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

            requested = service.record_external(
                "responder.requested",
                trace_id=trace_id,
                cause_event_id=simulation_event.get("event_id"),
                payload={"observation": observation, "objective_id": objective.id},
            )

            payload = {
                # The deterministic id is known before any state mutation. Keep
                # it in the real Durable input, but do not materialise a local
                # workflow until the Functions host actually accepts it: an
                # unavailable host must not leave a phantom failed workflow.
                "workflow_id": prospective_workflow_id,
                "type": responder.workflow_type,
                "trace_id": trace_id,
                "objective_id": objective.id,
                "observation": observation,
            }
            resp = await schedule_new_orchestration(payload, responder.orchestrator)
            instance_id = resp.get("id")
            status_uri = resp.get("statusQueryGetUri")
            workflow_id = self._adapter.start(
                simulation_event, objective, responder, observation
            )
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
                    payload={"instance_id": instance_id, "error": "no orchestration output"},
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
                    payload={"instance_id": instance_id, "reasoning": reasoning},
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
                self._workflow_by_objective.pop(objective.id, None)
                await self._adapter.failed(workflow_id, instance_id, reason)
                log.info("world_bridge: %s rejected command=%s trace=%s reason=%s",
                         instance_id, command.type, trace_id, reason)
                return

            # Record the decision boundaries + stash the command on the canonical
            # Workflow. NONTERMINAL by design: the world command has been applied
            # but its recovery/effectiveness is evaluated in Phase 3, so the
            # bridge never marks the workflow completed/resolved here.
            await self._adapter.decided(workflow_id, instance_id, command_data, reasoning, evidence=output)
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
        """Poll the Durable status endpoint until the orchestration is terminal.

        Whenever a poll's response carries a ``customStatus`` HITL gate (see
        ``_hitl_gate``), ingest it as a ``"suspended"`` durable event exactly
        once -- reusing the already-generic, already-tested
        ``WorkflowEventIngestor`` "suspended"/"resumed" handling (the same
        path a hand-built domain's suspend/resume already drives), so the
        gate becomes visible through the StateStore workflow status,
        ``pending_gates`` cache, and the existing
        ``/api/exceptions/{id}/resolve`` operator route with zero new
        vertical-specific plumbing. The paired ``"resumed"`` event is ingested
        once more, right before returning, whenever a gate was seen -- so no
        terminal orchestration ever leaves a stale "awaiting" gate behind.

        The signature is deliberately unchanged from before this gate was
        added -- ``workflow_id`` is recovered from ``self._workflow_by_objective``
        (keyed by the globally-unique Durable ``instance_id``, already
        populated by ``_drive`` before scheduling completes) rather than
        threaded through as a new parameter, so any test double that already
        replaces this whole method with a fixed-arity stub keeps working
        unmodified.

        Only narrow, transient HTTP transport/status/JSON-decode errors from
        the poll itself are caught and retried. The ``"suspended"``/``"resumed"``
        ingest calls are state-mutating (StateStore, ``pending_gates``, ledger,
        audit) and are deliberately NOT covered by that catch: a genuine ingest
        bug raises straight out of this method rather than being silently
        swallowed and repolled until the deadline -- which would otherwise
        risk losing a real, already-Completed Durable ``output`` and
        misreporting a successful recovery as though nothing had come back at
        all.
        """
        if not status_uri:
            log.error("world_bridge: no statusQueryGetUri for %s", instance_id)
            return None
        workflow_id = next(
            (wid for wid, iid in self._workflow_by_objective.values() if iid == instance_id),
            None,
        )
        deadline = asyncio.get_event_loop().time() + (timeout or self._poll_timeout)
        suspended = False
        async with httpx.AsyncClient() as c:
            while asyncio.get_event_loop().time() < deadline:
                try:
                    response = await c.get(status_uri, timeout=5)
                    response.raise_for_status()
                    data = response.json()
                except (httpx.HTTPError, ValueError) as poll_error:
                    # Narrow, transient transport/status/JSON-decode errors
                    # only -- retry on the next tick. The ingest calls below
                    # are deliberately OUTSIDE this except: they mutate real
                    # StateStore/pending-gates/ledger/audit state, so a
                    # genuine ingest bug must raise and surface immediately
                    # rather than being swallowed and silently retried.
                    log.warning(
                        "world_bridge: transient poll error for %s: %s",
                        instance_id, poll_error,
                    )
                    await asyncio.sleep(1.0)
                    continue

                status = data.get("runtimeStatus")
                gate = _hitl_gate(data) if workflow_id else None
                if gate is not None and not suspended:
                    wait_seconds = gate.get("wait_seconds")
                    if (
                        isinstance(wait_seconds, (int, float))
                        and not isinstance(wait_seconds, bool)
                        and 0 < wait_seconds < float("inf")
                    ):
                        deadline = max(
                            deadline,
                            asyncio.get_event_loop().time() + float(wait_seconds),
                        )
                    await self._app.workflow_event_ingestor.ingest(
                        workflow_id, instance_id, "suspended",
                        {
                            "phase": gate.get("phase"),
                            "external_event": gate.get("external_event"),
                            "reason": gate.get("reason", "approval"),
                            "wait_kind": gate.get("wait_kind", "operator_review"),
                        },
                    )
                    # Only bookkeep locally once the ingest itself actually
                    # succeeded -- an ingest failure raises above and leaves
                    # this gate un-recorded rather than being silently
                    # treated as already-handled.
                    suspended = True
                if status == _TERMINAL_OK:
                    # Capture the terminal output before the "resumed"
                    # bookkeeping ingest -- a real Completed output must
                    # never be lost or turned into None by anything that
                    # happens afterward.
                    output = data.get("output")
                    if suspended:
                        await self._app.workflow_event_ingestor.ingest(
                            workflow_id, instance_id, "resumed", {}
                        )
                    return output
                if status in _TERMINAL_BAD:
                    log.error("world_bridge: %s ended %s: %s",
                              instance_id, status, data.get("output"))
                    if suspended:
                        await self._app.workflow_event_ingestor.ingest(
                            workflow_id, instance_id, "resumed", {}
                        )
                    return None
                await asyncio.sleep(1.0)
        log.error("world_bridge: timed out awaiting %s", instance_id)
        return None
