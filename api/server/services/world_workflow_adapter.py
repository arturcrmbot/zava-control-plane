"""WorldWorkflowAdapter — canonical Workflow lifecycle for actor-world responders.

The actor WorldBridge turns a live sensor trip into a real Durable
orchestration and applies its typed command back to the world. Historically it
constructed an ad-hoc ``f"{prefix}-{trace_id}"`` workflow id inline and never
materialised a StateStore :class:`~api.shared.types.Workflow` at all — so the
operator surfaces (StateStore, AG-UI, EntityReflector, Blueprint) saw nothing.

This adapter is the single owner of that canonical StateStore Workflow record,
but NOT the single owner of every lifecycle event. Event ownership follows the
REAL execution boundary so one workflow id yields exactly one logical lifecycle
across history, ledger/audit, FleetEvents, Blueprint and AG-UI:

* :meth:`start` derives a deterministic ``<prefix>-<sensor_event_id>`` id,
  builds the Workflow from registered domain metadata (via the shared
  :func:`~api.server.services.synthetic_data.build_registered_workflow`
  factory), upserts exactly one record BEFORE Durable scheduling, and returns
  the id. That returned id is the ONLY id the bridge subsequently uses for the
  Durable payload, StateStore, AG-UI and EntityReflector.
* :meth:`scheduled`, :meth:`decided`, :meth:`failed`, :meth:`resolved` route
  lifecycle transitions through the shared
  :class:`~api.server.services.workflow_event_ingestor.WorkflowEventIngestor`
  (``app_state.workflow_event_ingestor``) using the canonical event vocabulary
  the Durable route emits — so the adapter never re-implements phase / history
  logic.

Event ownership (network-incident):

* The **Durable orchestrator** is the sole owner of ``workflow.started`` and of
  the two deterministic phase boundaries it actually executes —
  ``Impact Diagnosis`` and ``Reroute Planning``. Those events arrive on this
  same ingestor via ``internal_durable_event`` while the bridge awaits the
  orchestration output. The adapter MUST NOT re-emit them: the ingestor only
  deduplicates the StateStore phase *table*, so a second emit would duplicate
  the orchestration history, ledger/audit, FleetEvents, Blueprint and AG-UI
  RunStarted/StepStarted for the one workflow id.
* The **bridge/adapter** owns only the boundaries that genuinely execute on its
  side: :meth:`scheduled` records ``Telemetry Correlation`` — the deterministic
  bridge-side sensor→observation gather that has already completed by scheduling
  time and which the orchestrator never checkpoints — and :meth:`decided`
  records a distinct NONTERMINAL world-side decision-ready event (a ledger-only
  ``log.action``) once the reroute command has been applied to the world.

``Recovery Verification`` is the later world-evaluation boundary (Phase 3) and
is deliberately NOT recorded here.

Terminal honesty: :meth:`decided` leaves a NONTERMINAL decision-ready state —
the world command has been applied but its recovery/effectiveness has not been
evaluated, so the workflow is NOT completed/resolved. :meth:`resolved` exists
for the future evidenced-terminal path but the WorldBridge must not call it (or
any completion) before world mutation + evaluation. :meth:`failed` marks a
genuine no-command / error episode failed (nothing was applied, nothing to
evaluate).
"""
from __future__ import annotations

import logging
from typing import Any

from api.server.services.synthetic_data import build_registered_workflow
from api.shared.world_contracts import ResponderRegistration

log = logging.getLogger("world_workflow_adapter")

# network-incident phase names — must match api/shared/domains.py so Blueprint /
# AG-UI / operator surfaces resolve the same phase vocabulary. Only
# ``Telemetry Correlation`` (the bridge-side scheduling boundary) is owned here;
# ``Impact Diagnosis`` / ``Reroute Planning`` are owned by the Durable
# orchestrator, which executes them and checkpoints them itself.
_TELEMETRY_CORRELATION = "Telemetry Correlation"


class WorldWorkflowAdapter:
    """Owns the canonical StateStore Workflow for one actor-world responder."""

    def __init__(self, app_state) -> None:
        self._app = app_state

    # -- creation --------------------------------------------------------

    def start(
        self,
        sensor_event: dict[str, Any],
        objective: Any,
        responder: ResponderRegistration,
        observation: dict[str, Any],
    ) -> str:
        """Create (or return the existing) canonical Workflow for a sensor trip.

        The id is deterministic in the sensor event id — ``<prefix>-<event_id>``
        — so a duplicate start for the same sensor event is idempotent and never
        mints a second Workflow. Returns the canonical workflow id.
        """
        sensor_event_id = sensor_event["event_id"]
        workflow_id = f"{responder.prefix}-{sensor_event_id}"

        existing = self._app.store.get_workflow(workflow_id)
        if existing is not None:
            # Idempotent: a duplicate sensor episode reuses the one workflow.
            return workflow_id

        workflow = build_registered_workflow(
            workflow_id,
            responder.workflow_type,
            responder.observation_key,
            observation,
            extra_payload={
                "objective_id": getattr(objective, "id", None),
                "trace_id": getattr(objective, "trace_id", None),
            },
            domains=self._app.runtime.pack.domains,
        )
        self._app.store.upsert_workflow(workflow)
        return workflow_id

    # -- lifecycle -------------------------------------------------------

    async def scheduled(self, workflow_id: str, instance_id: str | None) -> None:
        """Record the bridge-side scheduling boundary and persist the Durable id.

        Owns ONLY ``Telemetry Correlation`` — the deterministic sensor→observation
        gather that completes on the bridge before scheduling and that the
        orchestrator never checkpoints. It deliberately does NOT emit
        ``workflow.started``: the Durable orchestrator owns that lifecycle event
        (it arrives on this same ingestor via ``internal_durable_event``), so
        emitting it here too would duplicate the logical run start across
        history, ledger, FleetEvents, Blueprint and AG-UI.
        """
        w = self._app.store.get_workflow(workflow_id)
        workflow_type = getattr(w, "type", None)
        if w is not None and instance_id:
            w.orchestration_instance_id = instance_id
            self._app.store.upsert_workflow(w)

        # Telemetry Correlation belongs only to network-incident. Other
        # responders checkpoint their own first phase inside their orchestrator.
        if workflow_type == "network-incident":
            await self._record_phase(
                workflow_id, instance_id, _TELEMETRY_CORRELATION, workflow_type,
            )

    async def decided(
        self,
        workflow_id: str,
        instance_id: str | None,
        command: Any,
        reasoning: str | None = None,
    ) -> None:
        """Record the nonterminal world-side decision and stash the command.

        Owns ONLY the distinct world-side ``decision_ready`` transition, routed
        through the ingestor as a ledger-only ``log.action`` — it does NOT
        re-record ``Impact Diagnosis`` / ``Reroute Planning``: those are the
        orchestrator's deterministic phase boundaries and it already checkpoints
        them on this same ingestor.

        NONTERMINAL: the world command has been applied but recovery /
        effectiveness evaluation is Phase 3, so the workflow is left
        ``in_progress`` — never completed/resolved here.
        """
        w = self._app.store.get_workflow(workflow_id)
        if w is not None:
            if not isinstance(w.payload, dict):
                w.payload = {}
            w.payload["decision"] = {"command": command, "reasoning": reasoning}
            w.metadata = dict(w.metadata or {})
            # Truthful nonterminal marker: the reroute is decided + applied,
            # world recovery/effectiveness evaluation (Phase 3) is pending.
            w.metadata["world_lifecycle"] = "decision_ready"
            w.status = "in_progress"
            self._app.store.upsert_workflow(w)

        # Distinct nonterminal world-side event on the ledger/audit trail. Truthful
        # (the command was decided + applied to the world) and coherent: log.action
        # is ledger-only, so it fabricates no registered phase and emits no
        # FleetEvent/Blueprint/AG-UI terminal.
        await self._ingest(
            workflow_id, instance_id, "log.action",
            {"by": "world_bridge", "action": "responder.decided"},
        )
        if getattr(w, "type", None) == "order-to-activate":
            await self._record_phase(
                workflow_id,
                instance_id,
                "Service Activation",
                "order-to-activate",
            )

    async def failed(
        self, workflow_id: str, instance_id: str | None, reason: Any
    ) -> None:
        """Mark a genuine no-command / error episode failed.

        Nothing was applied to the world, so there is nothing to evaluate — this
        is a truthful terminal failure, not a premature success completion.
        """
        w = self._app.store.get_workflow(workflow_id)
        if w is not None:
            w.metadata = dict(w.metadata or {})
            w.metadata["world_lifecycle"] = "failed"
            w.metadata["failure_reason"] = str(reason)
            w.status = "failed"
            self._app.store.upsert_workflow(w)
        await self._ingest(
            workflow_id,
            instance_id,
            "workflow.failed",
            {"by": "world_bridge", "reason": str(reason)},
        )

    async def resolved(
        self,
        workflow_id: str,
        instance_id: str | None,
        outcome: dict[str, Any] | None = None,
    ) -> None:
        """Future/evidenced terminal path (Phase 3).

        Emits the canonical ``workflow.completed`` through the ingestor. The
        WorldBridge MUST NOT call this before world mutation + evaluation; it is
        defined here so the terminal seam exists for the coupled Phase 3 slice.
        """
        w = self._app.store.get_workflow(workflow_id)
        if w is not None:
            if not isinstance(w.payload, dict):
                w.payload = {}
            if outcome is not None:
                w.payload["outcome"] = outcome
            w.metadata = dict(w.metadata or {})
            w.metadata["world_lifecycle"] = "resolved"
            self._app.store.upsert_workflow(w)
        final_phase = "Outcome Verification"
        if w is not None:
            domain = self._app.runtime.pack.domains.get(w.type)
            if domain is not None and domain.phases:
                final_phase = domain.phases[-1].name
        await self._ingest(
            workflow_id,
            instance_id,
            "step.started",
            {"step": final_phase, "workflow_type": getattr(w, "type", None)},
        )
        await self._ingest(
            workflow_id,
            instance_id,
            "step.completed",
            {
                "step": final_phase,
                "duration_ms": 0,
                "workflow_type": getattr(w, "type", None),
            },
        )
        await self._ingest(workflow_id, instance_id, "workflow.completed", {})
        self._capture_operational_memory(w, outcome)

    async def evaluation_failed(
        self,
        workflow_id: str,
        instance_id: str | None,
        outcome: dict[str, Any],
    ) -> None:
        """Close a post-command failure from explicit world evidence."""
        w = self._app.store.get_workflow(workflow_id)
        if w is not None:
            if not isinstance(w.payload, dict):
                w.payload = {}
            w.payload["outcome"] = outcome
            w.metadata = dict(w.metadata or {})
            w.metadata["world_lifecycle"] = "failed"
            w.metadata["failure_reason"] = str(
                outcome.get("reason") or outcome.get("status") or "evaluation failed"
            )
            self._app.store.upsert_workflow(w)
        final_phase = "Outcome Verification"
        if w is not None:
            domain = self._app.runtime.pack.domains.get(w.type)
            if domain is not None and domain.phases:
                final_phase = domain.phases[-1].name
        await self._ingest(
            workflow_id,
            instance_id,
            "step.started",
            {"step": final_phase, "workflow_type": getattr(w, "type", None)},
        )
        await self._ingest(
            workflow_id,
            instance_id,
            "step.failed",
            {
                "step": final_phase,
                "error": str(outcome.get("reason") or outcome.get("status")),
                "workflow_type": getattr(w, "type", None),
            },
        )
        await self._ingest(
            workflow_id,
            instance_id,
            "workflow.failed",
            {
                "by": "world_outcome_evaluator",
                "reason": str(outcome.get("reason") or outcome.get("status")),
            },
        )

    # -- helpers ---------------------------------------------------------

    def _capture_operational_memory(
        self, workflow: Any, outcome: dict[str, Any] | None
    ) -> None:
        if workflow is None:
            return
        memory = getattr(self._app, "domain_memories", {}).get(workflow.type)
        if memory is None:
            return
        evidence = (outcome or {}).get("evidence_event_type") or "world evidence"
        text = (
            f"Workflow {workflow.id} resolved from {evidence}; "
            f"trace_id={(workflow.payload or {}).get('trace_id', '')}."
        )
        try:
            memory.add(
                text,
                agent_skill="",
                workflow_id=workflow.id,
                extra_metadata={
                    "source": "world_outcome_evaluator",
                    "evidence_event_type": evidence,
                },
            )
        except Exception:
            log.exception(
                "operational memory write failed for workflow=%s", workflow.id
            )

    async def _record_phase(
        self, workflow_id: str, instance_id: str | None, phase: str,
        workflow_type: str | None = None,
    ) -> None:
        """Record one deterministic phase boundary via the shared ingestor.

        ``step.started`` is idempotent on the phase name in the StateStore phase
        table. ``workflow_type`` (when known) is stamped into the checkpoint
        payload so the ingestor caches it and the emitted FleetEvent resolves
        ``domain`` even before the orchestrator's own ``workflow.started`` lands.
        """
        started: dict = {"step": phase}
        completed: dict = {"step": phase, "duration_ms": 0}
        if workflow_type:
            started["workflow_type"] = workflow_type
            completed["workflow_type"] = workflow_type
        await self._ingest(workflow_id, instance_id, "step.started", started)
        await self._ingest(workflow_id, instance_id, "step.completed", completed)

    async def _ingest(
        self, workflow_id: str, instance_id: str | None, kind: str, payload: dict
    ) -> None:
        await self._app.workflow_event_ingestor.ingest(
            workflow_id, instance_id, kind, payload
        )
