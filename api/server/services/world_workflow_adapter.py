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

Event ownership is pack-declared:

* A responder with ``lifecycle_start_via_bridge=False`` leaves
  ``workflow.started`` to its Durable orchestrator. A responder with
  ``lifecycle_start_via_bridge=True`` uses the adapter because its selected
  Durable implementation has no lifecycle webhook activity. Exactly one
  boundary owns the event, so the history remains contiguous without a
  duplicate AG-UI run start.
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

import json
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


def _json_compact(value: Any) -> str:
    """Serialize operational-memory payloads as deterministic compact JSON."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )



def workflow_id_for(responder_prefix: str, sensor_event_id: str) -> str:
    """Deterministic canonical Workflow id for one sensor event.

    The ONE formula behind :meth:`WorldWorkflowAdapter.start`'s idempotent
    lookup. Also called by the bridge BEFORE it opens/re-claims an objective,
    so a sensor event redelivered after its workflow already exists (and has
    already been scheduled) short-circuits without ever touching objective
    state — there is still no independent prefix-id reconstruction anywhere
    else.
    """
    return f"{responder_prefix}-{sensor_event_id}"


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
        workflow_id = workflow_id_for(responder.prefix, sensor_event_id)

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
        workflow.metadata = dict(workflow.metadata or {})
        workflow.metadata["lifecycle_start_via_bridge"] = (
            responder.lifecycle_start_via_bridge
        )
        self._app.store.upsert_workflow(workflow)
        return workflow_id

    # -- lifecycle -------------------------------------------------------

    async def scheduled(self, workflow_id: str, instance_id: str | None) -> None:
        """Record the bridge-side scheduling boundary and persist the Durable id.

        The configured lifecycle boundary owns ``workflow.started``. The
        adapter emits it only for responders that declare
        ``lifecycle_start_via_bridge``; all other responders leave it to their
        Durable webhook activity. It also records ``Telemetry Correlation``
        only for the legacy network-incident bridge-side phase.
        """
        w = self._app.store.get_workflow(workflow_id)
        workflow_type = getattr(w, "type", None)
        if w is not None and instance_id:
            w.orchestration_instance_id = instance_id
            self._app.store.upsert_workflow(w)

        # Some selected packs emit durable lifecycle webhooks from their
        # own activities; others expose a real Durable orchestrator without a
        # webhook activity. The responder registration makes that execution
        # boundary explicit, so exactly one component owns workflow.started.
        if w is not None and w.metadata.get("lifecycle_start_via_bridge"):
            await self._ingest(
                workflow_id,
                instance_id,
                "workflow.started",
                {"workflow_type": workflow_type},
            )

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
        *,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        """Record the nonterminal world-side decision and stash the command.

        Owns ONLY the distinct world-side ``decision_ready`` transition, routed
        through the ingestor as a ledger-only ``log.action`` — it does NOT
        re-record ``Impact Diagnosis`` / ``Reroute Planning``: those are the
        orchestrator's deterministic phase boundaries and it already checkpoints
        them on this same ingestor.

        ``evidence`` is an optional, fully industry-neutral passthrough of
        whatever generic evidence envelope the calling responder's own
        orchestration output already carries (e.g. ordered phase records,
        skills/tools used, reasoning, HITL audit, typed command, evaluation
        intent) — stored verbatim on ``workflow.payload["evidence"]`` when
        provided, never fabricated when absent. This lets any pack-owned
        workflow-detail hook or Knowledge projection consume the real
        terminal orchestration evidence without this shared adapter needing
        to know anything about any particular vertical's own shape.

        NONTERMINAL: the world command has been applied but recovery /
        effectiveness evaluation is Phase 3, so the workflow is left
        ``in_progress`` — never completed/resolved here.
        """
        w = self._app.store.get_workflow(workflow_id)
        if w is not None:
            if not isinstance(w.payload, dict):
                w.payload = {}
            w.payload["decision"] = {"command": command, "reasoning": reasoning}
            if evidence is not None:
                w.payload["evidence"] = evidence
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
        """Write one operational-memory record for the resolved workflow.

        Fully industry-neutral: this reads only the generic evidence the
        shared adapter already owns -- ``workflow.type``/``workflow.status``,
        whatever ``workflow.payload["evidence"]``/``["observation"]`` the
        real orchestration/trigger already stored (never re-derived or
        vertical-branched here), and the full ``outcome`` the world's own
        generic :class:`~api.server.world.evaluations.Evaluation` produced
        (its own ``id``/``command_id``/``trace_id``/``final_measurements``
        already carry whatever real ids and actor identities the concrete
        domain's terminal success event happened to publish). No Travel (or
        any other vertical) name/id format is hardcoded here.
        """
        if workflow is None:
            return
        memory = getattr(self._app, "domain_memories", {}).get(workflow.type)
        if memory is None:
            return
        payload = workflow.payload if isinstance(workflow.payload, dict) else {}
        evidence = payload.get("evidence") or {}
        observation = payload.get("observation") or {}
        outcome = outcome or {}
        evidence_kind = outcome.get("evidence_event_type") or "world evidence"
        trace_id = payload.get("trace_id", "")
        try:
            evidence_json = _json_compact(evidence)
            observation_json = _json_compact(observation)
            outcome_json = _json_compact(outcome)
            text = (
                f"Workflow {workflow.id} ({workflow.type}) resolved from {evidence_kind}; "
                f"trace_id={trace_id}; status={workflow.status}; "
                f"evidence={evidence_json}; "
                f"observation={observation_json}; "
                f"outcome={outcome_json}."
            )
            memory.add(
                text,
                agent_skill="",
                workflow_id=workflow.id,
                extra_metadata={
                    "source": "world_outcome_evaluator",
                    "evidence_event_type": evidence_kind,
                    "workflow_type": workflow.type,
                    "workflow_status": workflow.status,
                    "evidence_json": evidence_json,
                    "observation_json": observation_json,
                    "outcome_json": outcome_json,
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
