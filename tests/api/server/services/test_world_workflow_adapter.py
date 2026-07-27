"""Tests for the WorldWorkflowAdapter — canonical Workflow lifecycle seam.

The adapter is the single owner of the canonical StateStore Workflow for an
actor-world responder episode: it derives a deterministic sensor-event-based
workflow id, mints the Workflow via the shared registered-domain factory
BEFORE Durable scheduling, and routes lifecycle transitions
(scheduled/decided/failed/resolved) through the shared
``WorkflowEventIngestor`` — never re-implementing phase/history logic.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from api.server.services.event_bus import EventBus
from api.server.services.state_store import StateStore
from api.server.services.workflow_event_ingestor import WorkflowEventIngestor
from api.server.services.world_responders import (
    resolve_responder as _resolve_responder,
)
from api.server.services.world_workflow_adapter import WorldWorkflowAdapter
from api.shared.vertical_loader import build_runtime


_TELCO_RUNTIME = build_runtime(
    {"ZAVA_VERTICAL": "telco"},
    data_root=Path("/tmp"),
)
_AGENCY_RUNTIME = build_runtime({}, data_root=Path("/tmp"))


def resolve_responder(objective_type: str):
    runtime = (
        _AGENCY_RUNTIME
        if objective_type == "support_capacity"
        else _TELCO_RUNTIME
    )
    return _resolve_responder(runtime, objective_type)


def _app_state():
    bus = EventBus()
    captured: list = []
    bus.on_any(lambda ev: captured.append(ev))
    state = SimpleNamespace(
        bus=bus, store=StateStore(), hub=MagicMock(), audit=MagicMock(),
        orchestration_history={}, domain_memories={},
        runtime=_TELCO_RUNTIME,
    )
    state.workflow_event_ingestor = WorkflowEventIngestor(state)
    return state, captured


def _sensor(event_id="evt-00000042", trace="network-anomaly-SITE-01-42"):
    return {
        "event_id": event_id,
        "trace_id": trace,
        "target_id": "SITE-01",
        "type": "sensor.tripped",
        "payload": {"measurements": {"site_id": "SITE-01"}},
    }


def _objective(oid="obj-evt-00000042", trace="network-anomaly-SITE-01-42"):
    return SimpleNamespace(id=oid, trace_id=trace, status="claimed")


def _observation():
    return {
        "trace_id": "network-anomaly-SITE-01-42",
        "sensor_event_id": "evt-00000042",
        "incident_site": {"id": "SITE-01", "region": "north", "status": "failed"},
        "neighbor_sites": [{"id": "SITE-02", "status": "healthy", "spare_mbps": 50.0}],
        "affected_sessions": [{"id": "SESS-1", "kind": "voice", "demand_mbps": 0.1}],
        "allowed_commands": ["reroute_sessions"],
    }


def test_start_creates_canonical_workflow_with_deterministic_id():
    state, _ = _app_state()
    adapter = WorldWorkflowAdapter(state)
    responder = resolve_responder("network_service_recovery")

    wid = adapter.start(_sensor(), _objective(), responder, _observation())

    # Deterministic id: <prefix>-<sensor_event_id>, full sensor id preserved.
    assert wid == "incident-evt-00000042"
    w = state.store.get_workflow(wid)
    assert w is not None
    assert w.type == "network-incident"
    # Initial phase from the registered domain (NOT Intake).
    assert w.current_phase == "Telemetry Correlation"
    # Observation nested under the projection-expected key "incident".
    assert w.payload["incident"]["incident_site"]["id"] == "SITE-01"
    # objective_id + trace_id stamped at the payload top level.
    assert w.payload["objective_id"] == "obj-evt-00000042"
    assert w.payload["trace_id"] == "network-anomaly-SITE-01-42"


def test_start_is_idempotent_for_duplicate_calls():
    state, _ = _app_state()
    adapter = WorldWorkflowAdapter(state)
    responder = resolve_responder("network_service_recovery")

    wid1 = adapter.start(_sensor(), _objective(), responder, _observation())
    first = state.store.get_workflow(wid1)
    # Mutate the stored workflow so a re-create would be observable.
    first.current_phase = "MUTATED"
    state.store.upsert_workflow(first)

    wid2 = adapter.start(_sensor(), _objective(), responder, _observation())
    assert wid2 == wid1
    # The existing workflow was returned unchanged (not rebuilt).
    assert state.store.get_workflow(wid1).current_phase == "MUTATED"


async def test_scheduled_records_scheduling_boundary_not_workflow_started():
    state, captured = _app_state()
    adapter = WorldWorkflowAdapter(state)
    responder = resolve_responder("network_service_recovery")
    wid = adapter.start(_sensor(), _objective(), responder, _observation())

    await adapter.scheduled(wid, "durable-instance-1")

    # instance id persisted on the workflow.
    assert state.store.get_workflow(wid).orchestration_instance_id == "durable-instance-1"
    types = [e.type for e in captured]
    # The Durable orchestrator owns workflow.started — the adapter must NOT emit
    # it (doing so duplicates the logical run start across history/ledger/AG-UI).
    assert "durable.workflow.started" not in types
    assert "workflow.started" not in types
    # The adapter owns ONLY the bridge-side scheduling boundary.
    phases = {p.name for p in state.store.get_phases(wid)}
    assert "Telemetry Correlation" in phases
    assert "Impact Diagnosis" not in phases
    assert "Reroute Planning" not in phases
    # Telemetry Correlation FleetEvent carries the resolved domain type so
    # Blueprint can resolve `domain` even before the orchestrator's started lands.
    step = next(e for e in captured if e.type == "durable.step.started")
    assert getattr(step, "phase", None) == "Telemetry Correlation"
    assert getattr(step, "workflow_type", None) == "network-incident"


async def test_decided_is_nonterminal_and_does_not_rerecord_orchestrator_phases():
    state, captured = _app_state()
    adapter = WorldWorkflowAdapter(state)
    responder = resolve_responder("network_service_recovery")
    wid = adapter.start(_sensor(), _objective(), responder, _observation())
    await adapter.scheduled(wid, "durable-instance-1")

    command = {"type": "reroute_sessions", "payload": {"incident_site_id": "SITE-01"}}
    await adapter.decided(
        wid,
        "durable-instance-1",
        command,
        reasoning="planned 1 session assignment for world execution",
    )

    # The orchestrator owns Impact Diagnosis / Reroute Planning — decided() must
    # NOT record them (only Telemetry Correlation from scheduled() is present).
    phases = {p.name for p in state.store.get_phases(wid)}
    assert phases == {"Telemetry Correlation"}
    w = state.store.get_workflow(wid)
    # Decision stashed onto the workflow payload.
    assert w.payload["decision"]["command"] == command
    assert w.payload["decision"]["reasoning"] == "planned 1 session assignment for world execution"
    # Distinct nonterminal world-side decision event on the ledger/audit trail.
    assert "responder.decided" in [e.action for e in w.action_ledger]
    # Ledger-only: no fabricated phase / terminal FleetEvent.
    assert "responder.decided" not in {e.type for e in captured}
    # NONTERMINAL: no completion/resolution before Phase 3 world evaluation.
    assert w.status == "in_progress"
    assert w.metadata["world_lifecycle"] == "decision_ready"
    terminal = {"durable.workflow.completed", "workflow.resolved"}
    assert not (terminal & {e.type for e in captured})


async def test_decided_records_order_service_activation_after_world_mutation():
    state, _ = _app_state()
    adapter = WorldWorkflowAdapter(state)
    responder = resolve_responder("order_to_activate")
    workflow_id = adapter.start(
        _sensor(event_id="evt-order", trace="service-order-1"),
        _objective(oid="obj-evt-order", trace="service-order-1"),
        responder,
        {"order": {"id": "ORD-00002"}},
    )

    await adapter.decided(
        workflow_id,
        "order-instance",
        {"type": "activate_service_order"},
    )

    assert {
        phase.name for phase in state.store.get_phases(workflow_id)
    } == {"Service Activation"}


async def test_failed_marks_failed_without_completion():
    state, captured = _app_state()
    adapter = WorldWorkflowAdapter(state)
    responder = resolve_responder("network_service_recovery")
    wid = adapter.start(_sensor(), _objective(), responder, _observation())
    await adapter.scheduled(wid, "durable-instance-1")

    await adapter.failed(wid, "durable-instance-1", "no healthy neighbour capacity")

    w = state.store.get_workflow(wid)
    assert w.status == "failed"
    # Never claims success before evaluation.
    assert "workflow.failed" in {e.type for e in captured}
    assert "durable.workflow.completed" not in {e.type for e in captured}
    assert "workflow.resolved" not in {e.type for e in captured}


async def test_evaluation_failed_preserves_terminal_world_evidence():
    state, captured = _app_state()
    adapter = WorldWorkflowAdapter(state)
    responder = resolve_responder("network_service_recovery")
    workflow_id = adapter.start(_sensor(), _objective(), responder, _observation())
    outcome = {
        "status": "failed",
        "reason": "packet loss remained above threshold",
        "evidence_event_type": "site.degraded",
        "evidence_event_id": "evt-evidence-1",
    }

    await adapter.evaluation_failed(workflow_id, "durable-instance-1", outcome)

    workflow = state.store.get_workflow(workflow_id)
    assert workflow.status == "failed"
    assert workflow.payload["outcome"] == outcome
    assert workflow.metadata["world_lifecycle"] == "failed"
    assert workflow.current_phase == "Recovery Verification"
    phases = {phase.name: phase.status for phase in state.store.get_phases(workflow_id)}
    assert phases["Recovery Verification"] == "failed"
    assert "workflow.failed" in {event.type for event in captured}
    assert "workflow.resolved" not in {event.type for event in captured}


async def test_resolved_is_defined_for_future_terminal_path():
    state, captured = _app_state()
    adapter = WorldWorkflowAdapter(state)
    responder = resolve_responder("network_service_recovery")
    wid = adapter.start(_sensor(), _objective(), responder, _observation())

    await adapter.resolved(wid, "durable-instance-1")

    assert state.store.get_workflow(wid).status == "completed"
    assert "durable.workflow.completed" in {e.type for e in captured}


async def test_resolved_uses_registered_domain_outcome_phase():
    state, _ = _app_state()
    adapter = WorldWorkflowAdapter(state)
    responder = resolve_responder("proactive_customer_care")
    sensor = _sensor(event_id="evt-care", trace="incident-root")
    objective = _objective(oid="obj-evt-care", trace="incident-root")
    observation = {"impacted_accounts": [{"id": "ACC-00001"}]}
    workflow_id = adapter.start(sensor, objective, responder, observation)

    await adapter.resolved(workflow_id, "care-instance", {"status": "resolved"})

    assert state.store.get_workflow(workflow_id).current_phase == "Outcome Verification"


async def test_scheduled_does_not_fabricate_network_phase_for_other_domains():
    state, _ = _app_state()
    adapter = WorldWorkflowAdapter(state)
    responder = resolve_responder("order_to_activate")
    workflow_id = adapter.start(
        _sensor(event_id="evt-order", trace="service-order-1"),
        _objective(oid="obj-evt-order", trace="service-order-1"),
        responder,
        {"order": {"id": "ORD-00002"}},
    )

    await adapter.scheduled(workflow_id, "order-instance")

    assert state.store.get_phases(workflow_id) == []


async def test_resolved_captures_truthful_operational_memory():
    state, _ = _app_state()
    memory = MagicMock()
    state.domain_memories["network-incident"] = memory
    adapter = WorldWorkflowAdapter(state)
    responder = resolve_responder("network_service_recovery")
    workflow_id = adapter.start(_sensor(), _objective(), responder, _observation())
    workflow = state.store.get_workflow(workflow_id)
    workflow.payload["evidence"] = {
        "command": {"id": "cmd-1", "payload": {"alpha": 1}},
        "workflow_id": workflow_id,
    }
    workflow.payload["observation"] = {
        "readings": [1, {"site": "SITE-01"}],
        "site": {"id": "SITE-01"},
    }

    await adapter.resolved(
        workflow_id,
        "network-instance",
        {"status": "resolved", "evidence_event_type": "site.recovered"},
    )

    memory.add.assert_called_once()
    text = memory.add.call_args.args[0]
    assert "site.recovered" in text
    assert '"command"' in text
    assert '"readings"' in text
    assert '"status":"resolved"' in text
    assert "SITE-01" in text
    assert memory.add.call_args.kwargs["workflow_id"] == workflow_id
    assert memory.add.call_args.kwargs["agent_skill"] == ""


def test_capture_operational_memory_uses_scalar_metadata_and_compact_json():
    state, _ = _app_state()

    class CapturingMemory:
        def __init__(self) -> None:
            self.calls = []

        def add(self, text, *, agent_skill="", workflow_id="", extra_metadata=None):
            self.calls.append(
                {
                    "text": text,
                    "agent_skill": agent_skill,
                    "workflow_id": workflow_id,
                    "extra_metadata": extra_metadata,
                }
            )
            return []

    memory = CapturingMemory()
    state.domain_memories["network-incident"] = memory
    adapter = WorldWorkflowAdapter(state)
    responder = resolve_responder("network_service_recovery")
    workflow_id = adapter.start(_sensor(), _objective(), responder, _observation())
    workflow = state.store.get_workflow(workflow_id)
    workflow.payload["evidence"] = {
        "workflow_id": workflow_id,
        "command": {"id": "cmd-1", "payload": {"alpha": 1, "beta": True}},
        "nested": {"z": 2, "a": 1},
    }
    workflow.payload["observation"] = {
        "site": {"id": "SITE-01", "region": "north"},
        "readings": [3, {"b": 2, "a": 1}],
    }
    workflow.status = "completed"
    final_measurements = {
        "status": "resolved",
        "evidence_event_type": "site.recovered",
        "final_measurements": {"z": 2, "a": 1},
    }

    adapter._capture_operational_memory(workflow, final_measurements)

    assert len(memory.calls) == 1
    call = memory.calls[0]
    metadata = call["extra_metadata"]
    assert call["workflow_id"] == workflow_id
    assert workflow_id in call["text"]
    assert all(isinstance(value, (str, int, float, bool)) for value in metadata.values())
    assert metadata["source"] == "world_outcome_evaluator"
    assert metadata["evidence_event_type"] == "site.recovered"
    assert metadata["workflow_type"] == "network-incident"
    assert metadata["workflow_status"] == "completed"
    assert metadata["evidence_json"] == (
        '{"command":{"id":"cmd-1","payload":{"alpha":1,"beta":true}},'
        '"nested":{"a":1,"z":2},"workflow_id":"' + workflow_id + '"}'
    )
    assert metadata["observation_json"] == (
        '{"readings":[3,{"a":1,"b":2}],"site":{"id":"SITE-01","region":"north"}}'
    )
    assert metadata["outcome_json"] == (
        '{"evidence_event_type":"site.recovered","final_measurements":{"a":1,"z":2},'
        '"status":"resolved"}'
    )


def test_capture_operational_memory_swallows_serialization_failure_and_skips_memory_add(
    caplog,
):
    state, _ = _app_state()
    memory = MagicMock()
    state.domain_memories["network-incident"] = memory
    adapter = WorldWorkflowAdapter(state)
    responder = resolve_responder("network_service_recovery")
    workflow_id = adapter.start(_sensor(), _objective(), responder, _observation())
    workflow = state.store.get_workflow(workflow_id)
    workflow.payload["evidence"] = {1: "one", "two": 2}
    workflow.status = "completed"

    with caplog.at_level("ERROR", logger="world_workflow_adapter"):
        adapter._capture_operational_memory(
            workflow,
            {"status": "resolved", "evidence_event_type": "site.recovered"},
        )

    memory.add.assert_not_called()
    assert "operational memory write failed for workflow=" in caplog.text


def test_start_supports_support_world_observation_key():
    # Support world (surge-staffing) nests under the default "observation" key.
    state, _ = _app_state()
    adapter = WorldWorkflowAdapter(state)
    responder = resolve_responder("support_capacity")
    sensor = _sensor(event_id="evt-00000007", trace="support-pressure-5")
    obj = _objective(oid="obj-evt-00000007", trace="support-pressure-5")

    wid = adapter.start(sensor, obj, responder, {"queued_tickets": []})

    assert wid == "surge-evt-00000007"
    w = state.store.get_workflow(wid)
    assert "observation" in w.payload
