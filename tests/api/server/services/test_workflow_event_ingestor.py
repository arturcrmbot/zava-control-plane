"""Behavioural tests for the non-HTTP WorkflowEventIngestor service.

Exercises :meth:`WorkflowEventIngestor.ingest` directly (no HTTP, no HMAC) so
the actor WorldBridge adapter's use of the same service is covered by the same
guarantees the route relies on: workflow history, phase append/update,
StateStore status transitions, ledger writes, and workflow-scoped FleetEvent
emission.
"""
from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import MagicMock

from api.server.services.event_bus import EventBus
from api.server.services.state_store import StateStore
from api.server.services.workflow_event_ingestor import WorkflowEventIngestor
from api.shared.types import Workflow


def _app_state():
    bus = EventBus()
    captured: list = []
    bus.on_any(lambda ev: captured.append(ev))
    state = SimpleNamespace(
        bus=bus,
        store=StateStore(),
        hub=MagicMock(),
        audit=MagicMock(),
        orchestration_history={},
    )
    return state, captured


def _seed(state, wid: str, wtype: str = "network-incident") -> Workflow:
    now = time.time()
    w = Workflow(
        id=wid, type=wtype, current_phase="Telemetry Correlation",
        created_at=now, sla_due_at=now + 86400,
        jurisdiction="London-Zava", agency="Zava-Test", payload={},
    )
    state.store.upsert_workflow(w)
    return w


async def test_workflow_started_records_history_ledger_and_events():
    state, captured = _app_state()
    _seed(state, "ING-1")
    ing = WorkflowEventIngestor(state)

    await ing.ingest("ING-1", "I-1", "workflow.started", {"workflow_type": "network-incident"})

    types = [e.type for e in captured]
    assert "workflow.started" in types
    assert "durable.workflow.started" in types
    # workflow_type cache forwards onto later events for the same workflow.
    assert state.orchestration_history["ING-1"][-1]["kind"] == "workflow.started"
    assert state.store.get_workflow("ING-1").action_ledger[-1].action == "workflow.started"
    state.hub.broadcast.assert_called()


async def test_step_started_appends_phase_and_sets_current_phase():
    state, captured = _app_state()
    _seed(state, "ING-2")
    ing = WorkflowEventIngestor(state)

    await ing.ingest("ING-2", "I-1", "step.started", {"step": "Impact Diagnosis"})

    phases = state.store.get_phases("ING-2")
    assert [(p.name, p.status) for p in phases] == [("Impact Diagnosis", "in_progress")]
    assert state.store.get_workflow("ING-2").current_phase == "Impact Diagnosis"
    types = [e.type for e in captured]
    assert "workflow.phase.started" in types
    assert "durable.step.started" in types


async def test_step_started_is_idempotent_across_replays():
    state, _ = _app_state()
    _seed(state, "ING-3")
    ing = WorkflowEventIngestor(state)

    for _ in range(3):
        await ing.ingest("ING-3", "I-1", "step.started", {"step": "Reroute Planning"})

    phases = [p for p in state.store.get_phases("ING-3") if p.name == "Reroute Planning"]
    assert len(phases) == 1


async def test_step_completed_marks_phase_completed():
    state, captured = _app_state()
    _seed(state, "ING-4")
    ing = WorkflowEventIngestor(state)

    await ing.ingest("ING-4", "I-1", "step.started", {"step": "Impact Diagnosis"})
    await ing.ingest("ING-4", "I-1", "step.completed",
                     {"step": "Impact Diagnosis", "duration_ms": 7})

    phases = {p.name: p.status for p in state.store.get_phases("ING-4")}
    assert phases["Impact Diagnosis"] == "completed"
    assert "durable.step.completed" in [e.type for e in captured]


async def test_mcp_call_appends_call():
    state, _ = _app_state()
    _seed(state, "ING-5")
    ing = WorkflowEventIngestor(state)

    await ing.ingest("ING-5", "I-1", "mcp.call", {
        "tool": "getSite", "url": "http://x", "method": "POST",
        "request": {}, "response": {}, "status_code": 200, "duration_ms": 2,
    })

    calls = state.store.get_mcp_calls("ING-5")
    assert calls and calls[-1].tool == "getSite"


async def test_suspended_then_resumed_toggles_status():
    state, _ = _app_state()
    _seed(state, "ING-6")
    ing = WorkflowEventIngestor(state)

    await ing.ingest("ING-6", "I-1", "suspended",
                     {"reason": "approve", "wait_kind": "operator_review"})
    assert state.store.get_workflow("ING-6").status == "awaiting_hitl"

    await ing.ingest("ING-6", "I-1", "resumed", {})
    assert state.store.get_workflow("ING-6").status == "in_progress"


async def test_workflow_completed_sets_completed_status():
    state, captured = _app_state()
    _seed(state, "ING-7")
    ing = WorkflowEventIngestor(state)

    await ing.ingest("ING-7", "I-1", "workflow.completed", {})

    assert state.store.get_workflow("ING-7").status == "completed"
    types = [e.type for e in captured]
    assert "durable.workflow.completed" in types
    assert "workflow.resolved" in types


async def test_workflow_rejected_sets_failed_and_emits_failed():
    state, captured = _app_state()
    _seed(state, "ING-8")
    ing = WorkflowEventIngestor(state)

    await ing.ingest("ING-8", "I-1", "workflow.rejected", {"by": "op", "reason": "no"})

    assert state.store.get_workflow("ING-8").status == "failed"
    types = [e.type for e in captured]
    assert "workflow.failed" in types
    assert "workflow.resolved" in types


async def test_at_override_stamps_history_timestamp():
    state, _ = _app_state()
    _seed(state, "ING-9")
    ing = WorkflowEventIngestor(state)

    await ing.ingest("ING-9", "I-1", "workflow.started",
                     {"workflow_type": "network-incident"}, at=1234.5)

    assert state.orchestration_history["ING-9"][-1]["at"] == 1234.5


async def test_unknown_kind_is_a_noop_but_still_records_history():
    state, captured = _app_state()
    _seed(state, "ING-10")
    ing = WorkflowEventIngestor(state)

    await ing.ingest("ING-10", "I-1", "totally.unknown.kind", {"x": 1})

    # Unknown kinds fall through the if/elif chain untouched, but history +
    # hub broadcast still happen (mirrors the pre-extraction route).
    assert state.orchestration_history["ING-10"][-1]["kind"] == "totally.unknown.kind"
    # No lifecycle FleetEvents for an unknown kind.
    assert captured == []
