"""Combined bridge-adapter + real-orchestrator checkpoint lifecycle proof.

This is the coupled test the isolated Phase 2 suites were missing: it drives the
REAL :class:`WorldWorkflowAdapter` (``scheduled`` + ``decided``) *and* the REAL
``network_incident_orchestration`` checkpoint sequence (its actual generator +
the real deterministic activities) through the SAME shared
:class:`WorkflowEventIngestor` — exactly as the live system does across the
FastAPI ↔ Durable seam, but without launching Functions.

Because both the adapter and the orchestrator historically emitted
``workflow.started`` and the ``Impact Diagnosis`` / ``Reroute Planning`` phase
boundaries for the ONE canonical workflow id, ingesting them together produced a
duplicate logical lifecycle: two ``workflow.started`` history/ledger/FleetEvent
rows and two phase.started/completed rows per orchestrator phase (the ingestor
only deduplicates the StateStore phase *table*, not history, ledger, FleetEvents,
Blueprint or AG-UI). This test asserts a SINGLE-OWNER lifecycle:

* the Durable orchestrator is the sole owner of ``workflow.started`` and the two
  deterministic phases it actually executes (Impact Diagnosis, Reroute Planning),
* the bridge/adapter owns only the scheduling boundary (Telemetry Correlation)
  and a distinct nonterminal world-side decision event,

so every logical event/history/ledger/FleetEvent/Blueprint/AG-UI surface shows
the phase exactly once, for the exact workflow id, with no terminal completion.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from api.functions.workflows.network_incident import network_incident_orchestration
from api.functions.workflows.network_incident_activities import (
    network_incident_impact_activity,
    network_incident_reroute_activity,
)
from api.server.services.event_bus import EventBus
from api.server.services.state_store import StateStore
from api.server.services.substrate_to_agui import SubstrateToAGUI
from api.server.services.workflow_event_ingestor import WorkflowEventIngestor
from api.server.services.world_responders import resolve_responder
from api.server.services.world_workflow_adapter import WorldWorkflowAdapter
from api.server.world.service import ActorWorldService


class _CheckpointRecordingContext:
    """Durable stub that runs the REAL activities and records the orchestrator's
    ``checkpoint_activity_trigger`` calls in order, so they can be replayed
    through the shared ingestor exactly as ``internal_durable_event`` would."""

    def __init__(self, input_dict: dict) -> None:
        self.instance_id = input_dict.get("_instance_id", "durable-instance-1")
        self._input = input_dict
        self.checkpoints: list[tuple[str, dict]] = []

    def get_input(self) -> dict:
        return self._input

    def call_activity(self, name: str, payload: dict) -> Any:
        if name == "checkpoint_activity_trigger":
            self.checkpoints.append((payload["kind"], payload["payload"]))
            return {}
        if name == "network_incident_impact_activity_trigger":
            return network_incident_impact_activity(payload)
        if name == "network_incident_reroute_activity_trigger":
            return network_incident_reroute_activity(payload)
        return {}


def _drive_generator(ctx: _CheckpointRecordingContext) -> dict | None:
    gen = network_incident_orchestration(ctx)  # type: ignore[arg-type]
    sent: Any = None
    while True:
        try:
            target = gen.send(sent) if sent is not None else next(gen)
        except StopIteration as stop:
            return stop.value
        sent = target


async def _run_orchestrator_checkpoints(
    ingestor: WorkflowEventIngestor, input_dict: dict, instance_id: str
) -> dict | None:
    """Run the REAL orchestrator generator + activities and route every
    checkpoint it emits through the shared ingestor (the durable→FastAPI path)."""
    ctx = _CheckpointRecordingContext({**input_dict, "_instance_id": instance_id})
    output = _drive_generator(ctx)
    for kind, payload in ctx.checkpoints:
        await ingestor.ingest(input_dict["workflow_id"], instance_id, kind, payload)
    return output


def _app_state():
    world = ActorWorldService.telco(seed=42, bus=EventBus(), minutes_per_second=1000)
    state = SimpleNamespace(
        bus=world.bus, world_service=world, store=StateStore(),
        hub=MagicMock(), audit=MagicMock(), orchestration_history={},
    )
    state.workflow_event_ingestor = WorkflowEventIngestor(state)
    return state, world


async def test_combined_adapter_and_orchestrator_single_owner_lifecycle():
    state, world = _app_state()
    fleet_events: list = []
    state.bus.on_any(lambda ev: fleet_events.append(ev))

    # -- real sensor trip + observation from the live telco world -------------
    world.inject_site_failure()
    world.runtime.run_until(2)
    sensor = next(
        e for e in world.runtime.journal
        if e.type == "sensor.tripped" and e.actor_id == "sensor:network_anomaly"
    )
    sensor_event = sensor.to_dict()
    event_id = sensor_event["event_id"]
    expected_wid = f"incident-{event_id}"
    instance_id = "durable-ni-1"

    responder = resolve_responder(
        world.registration.objective_routes[0].objective_type
    )
    objective = SimpleNamespace(
        id=f"obj-{event_id}", trace_id=sensor_event["trace_id"], status="claimed",
    )
    observation = world.build_observation(sensor_event)

    adapter = WorldWorkflowAdapter(state)

    # === the real coupled sequence (bridge order): ===========================
    # 1. adapter mints the one canonical Workflow before scheduling.
    wid = adapter.start(sensor_event, objective, responder, observation)
    assert wid == expected_wid
    # 2. bridge records the scheduling boundary (Telemetry Correlation).
    await adapter.scheduled(wid, instance_id)
    # 3. the Durable orchestrator runs and checkpoints through the SAME ingestor.
    orch_input = {
        "workflow_id": wid,
        "type": "network-incident",
        "trace_id": sensor_event["trace_id"],
        "observation": observation,
    }
    output = await _run_orchestrator_checkpoints(
        state.workflow_event_ingestor, orch_input, instance_id
    )
    assert output and output.get("command")
    # 4. bridge records the nonterminal world-side decision (command applied).
    await adapter.decided(wid, instance_id, output["command"], output.get("reasoning"))

    # === exact workflow id, single canonical record ==========================
    w = state.store.get_workflow(expected_wid)
    assert w is not None and w.type == "network-incident"

    # === one logical event per phase in orchestration_history ================
    hist = state.orchestration_history.get(expected_wid) or []
    started_hist = [h for h in hist if h["kind"] == "workflow.started"]
    assert len(started_hist) == 1, f"duplicate workflow.started in history: {started_hist}"
    for phase in ("Impact Diagnosis", "Reroute Planning"):
        starts = [h for h in hist
                  if h["kind"] == "step.started" and h["payload"].get("step") == phase]
        assert len(starts) == 1, f"duplicate history step.started for {phase}: {starts}"
    # Telemetry Correlation is the adapter-owned scheduling boundary — once.
    tel = [h for h in hist
           if h["kind"] == "step.started"
           and h["payload"].get("step") == "Telemetry Correlation"]
    assert len(tel) == 1

    # === one phase row per phase (no duplicate rows) =========================
    phases = [p.name for p in state.store.get_phases(expected_wid)]
    for phase in ("Telemetry Correlation", "Impact Diagnosis", "Reroute Planning"):
        assert phases.count(phase) == 1, f"duplicate phase row for {phase}: {phases}"
    # Recovery Verification is the Phase 3 world-eval boundary — NOT recorded.
    assert "Recovery Verification" not in phases

    # === one ledger entry per logical phase / lifecycle ======================
    ledger_actions = [e.action for e in w.action_ledger]
    assert ledger_actions.count("workflow.started") == 1, ledger_actions
    for phase in ("Impact Diagnosis", "Reroute Planning"):
        assert ledger_actions.count(f"phase.completed:{phase}") == 1, ledger_actions

    # === no duplicate Blueprint (observatory) events =========================
    from api.server.routes import blueprint

    wf_events = [e for e in fleet_events
                 if getattr(e, "workflow_id", None) == expected_wid]
    accepted = [n for n in (blueprint._normalise_event(e) for e in wf_events)
                if n is not None]
    assert all(n["workflow_id"] == expected_wid for n in accepted)
    assert all(n["workflow_type"] == "network-incident" for n in accepted)
    start_bp = [n for n in accepted if n["type"] == "durable.workflow.started"]
    assert len(start_bp) == 1, f"duplicate Blueprint workflow.started: {start_bp}"
    # durable.step.started carries the phase under `phase`; count per phase on
    # the raw FleetEvents so a duplicate boundary is caught.
    for phase in ("Impact Diagnosis", "Reroute Planning", "Telemetry Correlation"):
        raw = [e for e in wf_events
               if e.type == "durable.step.started"
               and getattr(e, "phase", None) == phase]
        assert len(raw) == 1, f"duplicate durable.step.started for {phase}: {raw}"

    # === AG-UI: single logical RunStarted, no terminal RunFinished ===========
    translator = SubstrateToAGUI(run_id=expected_wid)
    agui_names: list[str] = []
    for e in fleet_events:
        agui_names.extend(type(a).__name__ for a in translator.translate(e))
    # One logical lifecycle-start. The ingestor emits the canonical
    # durable.workflow.started plus the deprecated workflow.started alias for a
    # SINGLE workflow.started ingest, so one lifecycle == 2 RunStarted here.
    # Duplicate ownership (adapter + orchestrator both emitting workflow.started)
    # produced 4.
    assert agui_names.count("RunStarted") == 2, agui_names
    assert "StepStarted" in agui_names
    assert "RunFinished" not in agui_names

    # === truthful nonterminal state ==========================================
    assert w.status == "in_progress"
    assert w.metadata.get("world_lifecycle") == "decision_ready"
    assert "planned" in (w.payload.get("decision") or {}).get("reasoning", "")
    assert "rerouted" not in (w.payload.get("decision") or {}).get("reasoning", "")
    emitted_types = {e.type for e in fleet_events}
    assert "durable.workflow.completed" not in emitted_types
    assert "workflow.resolved" not in emitted_types
    # Exactly one canonical + one legacy lifecycle-start FleetEvent (no dup).
    assert sum(1 for e in wf_events if e.type == "durable.workflow.started") == 1
    assert sum(1 for e in wf_events if e.type == "workflow.started") == 1
