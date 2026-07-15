"""End-to-end service-integration proof for one actor-triggered network incident.

Drives the REAL telco ``ActorWorldService`` through the REAL ``WorldBridge`` →
``WorldWorkflowAdapter`` → ``WorkflowEventIngestor`` → ``EntityReflector`` chain.
Only the two genuine external boundaries are faked: the Durable client
(``schedule_new_orchestration`` + the status poller ``_await_output``, which
runs the REAL split decision activities) and the graph store (a capture-only
fake in place of the kuzu-backed ``EntityGraph``).

Proves the canonical actor-workflow lifecycle end to end:

* one StateStore Workflow is created BEFORE scheduling with a deterministic
  sensor-event-based id,
* its payload carries ``objective_id``, ``trace_id`` and the ``incident``
  observation,
* phases/history are recorded through the shared ingestor,
* workflow-scoped standard FleetEvents are accepted by Blueprint stream
  normalisation and produce AG-UI events for that exact workflow id,
* the EntityReflector runs the network_incident projection and writes the
  Workflow + cell-site Asset from that same stored Workflow,
* NO terminal completion/resolution is emitted before world mutation/evaluation,
* the existing WorldBridge actor command behaviour (typed reroute applied to the
  real session actors, objective → evaluating) is preserved.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from api.functions.workflows.network_incident import network_incident_orchestration
from api.functions.workflows.network_incident_activities import (
    network_incident_impact_activity,
    network_incident_reroute_activity,
)
from api.server.services.entity_reflector import EntityReflector
from api.server.services.event_bus import EventBus
from api.server.services.state_store import StateStore
from api.server.services.substrate_to_agui import SubstrateToAGUI
from api.server.services.workflow_event_ingestor import WorkflowEventIngestor
from api.server.services.world_bridge import WorldBridge
from api.server.world.service import ActorWorldService


class FakeGraph:
    """Capture-only stand-in for the kuzu-backed EntityGraph (mockable boundary)."""

    def __init__(self):
        self.upserts = []
        self.links = []
        self.decisions = []

    def upsert(self, op):
        self.upserts.append(op)

    def link(self, src_id, rel, dst_id, **attrs):
        self.links.append((src_id, rel, dst_id, attrs))

    def record_decision(self, *args):
        self.decisions.append(args)


def _reroute_from_observation(payload):
    """Run the REAL split activities exactly as the orchestrator would."""
    obs = payload["observation"]
    trace = payload["trace_id"]
    impact = network_incident_impact_activity({"trace_id": trace, "observation": obs})
    reroute = network_incident_reroute_activity({
        "trace_id": trace,
        "diagnosis": impact.get("diagnosis"),
        "diagnosis_reasoning": impact.get("reasoning"),
    })
    return {
        "status": "completed",
        "command": reroute.get("command"),
        "reasoning": reroute.get("reasoning"),
        "observation": obs,
    }


class _CheckpointRecordingContext:
    """Durable stub that runs the REAL activities and records the orchestrator's
    ``checkpoint_activity_trigger`` calls in order (see the coupled lifecycle
    test) so they can be replayed through the shared ingestor — the realistic
    durable→FastAPI path the pure-``_reroute_from_observation`` fake was missing."""

    def __init__(self, input_dict, instance_id):
        self.instance_id = instance_id
        self._input = input_dict
        self.checkpoints = []

    def get_input(self):
        return self._input

    def call_activity(self, name, payload):
        if name == "checkpoint_activity_trigger":
            self.checkpoints.append((payload["kind"], payload["payload"]))
            return {}
        if name == "network_incident_impact_activity_trigger":
            return network_incident_impact_activity(payload)
        if name == "network_incident_reroute_activity_trigger":
            return network_incident_reroute_activity(payload)
        return {}


async def _run_orchestrator(ingestor, payload, instance_id):
    """Drive the REAL orchestrator generator + activities and route every
    checkpoint through the shared ingestor, then return its typed output."""
    orch_input = {
        "workflow_id": payload["workflow_id"],
        "type": payload["type"],
        "trace_id": payload["trace_id"],
        "observation": payload["observation"],
    }
    ctx = _CheckpointRecordingContext(orch_input, instance_id)
    gen = network_incident_orchestration(ctx)  # type: ignore[arg-type]
    sent = None
    output = None
    while True:
        try:
            target = gen.send(sent) if sent is not None else next(gen)
        except StopIteration as stop:
            output = stop.value
            break
        sent = target
    for kind, cp in ctx.checkpoints:
        await ingestor.ingest(payload["workflow_id"], instance_id, kind, cp)
    return output


async def test_actor_network_incident_end_to_end(monkeypatch):
    # -- REAL telco world + REAL service wiring -------------------------------
    world = ActorWorldService.telco(seed=42, bus=EventBus(), minutes_per_second=1000)
    state = SimpleNamespace(
        bus=world.bus, world_service=world, world_last_response=None,
        store=StateStore(), hub=MagicMock(), audit=MagicMock(),
        orchestration_history={},
    )
    state.workflow_event_ingestor = WorkflowEventIngestor(state)

    # REAL EntityReflector with the graph-store boundary faked.
    graph = FakeGraph()
    reflector = EntityReflector(state.bus, state.store, graph, governance=None, audit=None)
    reflector.start()

    fleet_events: list = []
    state.bus.on_any(lambda ev: fleet_events.append(ev))

    # -- drive the real world to a cell-site failure + anomaly ----------------
    site_id = world.inject_site_failure()
    world.runtime.run_until(2)
    sensor = next(e for e in world.runtime.journal if e.type == "sensor.tripped")
    sensor_event = sensor.to_dict()
    event_id = sensor_event["event_id"]
    expected_wid = f"incident-{event_id}"
    expected_oid = f"obj-{event_id}"

    # -- bridge with only the Durable boundary faked --------------------------
    bridge = WorldBridge(state)
    captured: dict = {}

    async def fake_schedule(payload, orchestrator):
        # The canonical Workflow MUST already be in the store before scheduling.
        captured["pre_schedule"] = state.store.get_workflow(payload["workflow_id"])
        captured["payload"] = payload
        captured["orchestrator"] = orchestrator
        return {"id": "durable-ni-1", "statusQueryGetUri": "status://ni-1"}

    monkeypatch.setattr(
        "api.server.services.world_bridge.schedule_new_orchestration",
        AsyncMock(side_effect=fake_schedule),
    )

    async def fake_await_output(instance_id, status_uri, timeout=None):
        # Realistic durable boundary: the orchestrator runs its REAL checkpoint
        # sequence (workflow.started + the two deterministic phases) through the
        # SHARED ingestor before returning its typed output — exactly as the live
        # Functions host would via internal_durable_event.
        return await _run_orchestrator(
            state.workflow_event_ingestor, captured["payload"], instance_id
        )

    bridge._await_output = fake_await_output

    await bridge._drive(sensor_event)
    reflector.aclose()

    # === 1. one StateStore Workflow, created BEFORE scheduling, deterministic id
    assert captured["pre_schedule"] is not None, "workflow must exist before scheduling"
    assert captured["pre_schedule"].id == expected_wid
    w = state.store.get_workflow(expected_wid)
    assert w is not None
    assert w.type == "network-incident"
    # Never started on a hardcoded "Intake": the initial phase derived from the
    # registered domain (Telemetry Correlation) and then advanced through the
    # recorded boundaries to the last real phase (nonterminal, pre-Phase-3).
    assert w.current_phase == "Reroute Planning"
    assert w.current_phase != "Intake"

    # === 2. payload carries objective_id, trace_id and the incident observation
    assert w.payload["objective_id"] == expected_oid
    assert w.payload["trace_id"] == sensor_event["trace_id"]
    assert w.payload["incident"]["incident_site"]["id"] == site_id
    # Durable scheduled with the SAME canonical id + type + objective_id + observation.
    assert captured["payload"]["workflow_id"] == expected_wid
    assert captured["payload"]["type"] == "network-incident"
    assert captured["payload"]["objective_id"] == expected_oid
    assert captured["payload"]["observation"]["incident_site"]["id"] == site_id
    assert captured["orchestrator"] == "NetworkIncidentOrchestrator"

    # === 3. phases + history recorded through the shared ingestor
    phase_names = {p.name for p in state.store.get_phases(expected_wid)}
    assert {"Telemetry Correlation", "Impact Diagnosis", "Reroute Planning"} <= phase_names
    # Recovery Verification is the Phase 3 world-eval boundary — NOT recorded yet.
    assert "Recovery Verification" not in phase_names
    assert state.orchestration_history.get(expected_wid)

    # === 4. workflow-scoped standard FleetEvents accepted by Blueprint normalisation
    from api.server.routes import blueprint

    wf_events = [e for e in fleet_events if getattr(e, "workflow_id", None) == expected_wid]
    accepted = [n for n in (blueprint._normalise_event(e) for e in wf_events) if n is not None]
    accepted_types = {n["type"] for n in accepted}
    assert "durable.workflow.started" in accepted_types
    assert "durable.step.started" in accepted_types
    assert "durable.step.completed" in accepted_types
    assert all(n["workflow_id"] == expected_wid for n in accepted)
    assert all(n["workflow_type"] == "network-incident" for n in accepted)
    assert "planned" in w.payload["decision"]["reasoning"]
    assert "rerouted" not in w.payload["decision"]["reasoning"]

    # === 5. AG-UI events for that EXACT workflow id
    translator = SubstrateToAGUI(run_id=expected_wid)
    agui_names: list[str] = []
    for e in fleet_events:
        agui_names.extend(type(a).__name__ for a in translator.translate(e))
    assert "RunStarted" in agui_names
    assert "StepStarted" in agui_names
    # No terminal run-finish before Phase 3.
    assert "RunFinished" not in agui_names

    # === 6. EntityReflector ran the network_incident projection: Workflow + Asset
    workflow_writes = [
        op for op in graph.upserts
        if getattr(op, "kind", None) == "Workflow" and op.id == expected_wid
    ]
    asset_writes = [op for op in graph.upserts if getattr(op, "kind", None) == "Asset"]
    assert workflow_writes, "reflector should materialise the Workflow node"
    assert any(op.attrs.get("identifier") == site_id for op in asset_writes), (
        "projection should write the incident cell-site Asset"
    )
    assert any(op.attrs.get("kind") == "cell-site" for op in asset_writes)

    # === 7. NO terminal completion/resolution before world mutation/evaluation
    assert w.status == "in_progress"
    emitted_types = {e.type for e in fleet_events}
    assert "durable.workflow.completed" not in emitted_types
    assert "workflow.resolved" not in emitted_types

    # === 8. existing WorldBridge actor command behaviour preserved
    assert state.world_last_response is not None
    assert state.world_last_response["workflow_id"] == expected_wid
    journal_types = [e.type for e in world.runtime.journal]
    assert "session.rerouted" in journal_types  # real session actors moved
    assert "command.accepted" in journal_types
    # Objective walked open → claimed → acting → evaluating via the gateway.
    objective = world.objectives.get(expected_oid)
    assert objective is not None and objective.status == "evaluating"


async def test_actor_network_incident_workflow_id_is_idempotent(monkeypatch):
    """A duplicate drive for the same sensor event reuses the one Workflow."""
    world = ActorWorldService.telco(seed=42, bus=EventBus(), minutes_per_second=1000)
    state = SimpleNamespace(
        bus=world.bus, world_service=world, world_last_response=None,
        store=StateStore(), hub=MagicMock(), audit=MagicMock(),
        orchestration_history={},
    )
    state.workflow_event_ingestor = WorkflowEventIngestor(state)
    bridge = WorldBridge(state)

    monkeypatch.setattr(
        "api.server.services.world_bridge.schedule_new_orchestration",
        AsyncMock(return_value={"id": "durable-1", "statusQueryGetUri": "s://1"}),
    )
    bridge._await_output = AsyncMock(
        side_effect=lambda *a, **k: _reroute_from_observation(
            {"observation": world.build_observation(sensor_event), "trace_id": sensor_event["trace_id"]}
        )
    )

    world.inject_site_failure()
    world.runtime.run_until(2)
    sensor = next(e for e in world.runtime.journal if e.type == "sensor.tripped")
    sensor_event = sensor.to_dict()
    expected_wid = f"incident-{sensor_event['event_id']}"

    from api.server.services.world_workflow_adapter import WorldWorkflowAdapter

    adapter = WorldWorkflowAdapter(state)
    responder = SimpleNamespace(
        prefix="incident", workflow_type="network-incident", observation_key="incident",
    )
    objective = SimpleNamespace(id=f"obj-{sensor_event['event_id']}", trace_id=sensor_event["trace_id"])
    obs = world.build_observation(sensor_event)

    wid1 = adapter.start(sensor_event, objective, responder, obs)
    state.store.get_workflow(wid1).current_phase = "MUTATED"
    wid2 = adapter.start(sensor_event, objective, responder, obs)

    assert wid1 == wid2 == expected_wid
    # Idempotent: the existing workflow was returned unchanged, not rebuilt.
    assert state.store.get_workflow(expected_wid).current_phase == "MUTATED"
