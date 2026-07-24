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

import pytest

from api.server.services.event_bus import EventBus
from api.server.services.replay.mutation_bus import MutationBus, set_active_bus
from api.server.services.state_store import StateStore
from api.server.services.substrate_to_agui import SubstrateToAGUI
from api.server.services.workflow_event_ingestor import WorkflowEventIngestor
from api.shared.types import Exception_ as WorkflowException
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
        domain_memories={},
        cost_budget=MagicMock(),
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


async def test_step_started_uses_system_unless_payload_names_real_agent():
    state, _ = _app_state()
    _seed(state, "ING-PHASE-AGENT")
    ing = WorkflowEventIngestor(state)

    await ing.ingest(
        "ING-PHASE-AGENT",
        "I-1",
        "step.started",
        {"step": "Deterministic validation"},
    )
    await ing.ingest(
        "ING-PHASE-AGENT",
        "I-1",
        "step.started",
        {"step": "Agent review"},
    )
    await ing.ingest(
        "ING-PHASE-AGENT",
        "I-1",
        "step.completed",
        {"step": "Agent review", "agent_id": "network-agent"},
    )

    phases = {phase.name: phase.agent_id for phase in state.store.get_phases("ING-PHASE-AGENT")}
    assert phases == {
        "Deterministic validation": "system",
        "Agent review": "network-agent",
    }


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


async def test_executor_span_preserves_invocation_and_phase():
    state, captured = _app_state()
    _seed(state, "ING-EXECUTOR")
    ing = WorkflowEventIngestor(state)
    payload = {
        "name": "agent_access_drafter",
        "type": "agent",
        "phase": "Access Draft",
        "invocation_id": "ar-shared-executor",
    }

    await ing.ingest(
        "ING-EXECUTOR",
        "I-1",
        "executor.invoked",
        {**payload, "stage": "start"},
        at=100.0,
    )
    await ing.ingest(
        "ING-EXECUTOR",
        "I-1",
        "executor.invoked",
        {**payload, "stage": "complete", "duration_ms": 25},
        at=100.025,
    )

    span = state.store.get_spans("ING-EXECUTOR")[0]
    assert span.attributes["workflow.phase"] == "Access Draft"
    assert span.attributes["zava.invocation.id"] == "ar-shared-executor"
    events = [event for event in captured if event.type == "durable.executor.invoked"]
    assert {event.invocation_id for event in events} == {"ar-shared-executor"}


async def test_mcp_call_appends_call():
    state, _ = _app_state()
    _seed(state, "ING-5")
    ing = WorkflowEventIngestor(state)

    await ing.ingest("ING-5", "I-1", "mcp.call", {
        "tool": "getSite", "url": "http://x", "method": "POST",
        "request": {}, "response": {}, "status_code": 200, "duration_ms": 2,
        "tool_call_id": "direct-call-5",
    })

    calls = state.store.get_mcp_calls("ING-5")
    assert calls and calls[-1].tool == "getSite"
    assert calls[-1].tool_call_id == "direct-call-5"


async def test_suspended_then_resumed_toggles_status():
    state, _ = _app_state()
    _seed(state, "ING-6")
    ing = WorkflowEventIngestor(state)

    await ing.ingest("ING-6", "I-1", "suspended",
                     {"reason": "approve", "wait_kind": "operator_review"})
    assert state.store.get_workflow("ING-6").status == "awaiting_hitl"

    await ing.ingest("ING-6", "I-1", "resumed", {})
    assert state.store.get_workflow("ING-6").status == "in_progress"


async def test_suspended_then_resumed_persists_hitl_phase_evidence():
    state, _ = _app_state()
    _seed(state, "ING-HITL-PHASE")
    ing = WorkflowEventIngestor(state)

    await ing.ingest(
        "ING-HITL-PHASE",
        "I-1",
        "suspended",
        {
            "reason": "awaiting_offer",
            "wait_kind": "external_party",
            "phase": "Offer",
            "persona": "candidate",
            "external_event": "offer_approval",
        },
        at=100.0,
    )
    assert [
        (phase.name, phase.status)
        for phase in state.store.get_phases("ING-HITL-PHASE")
    ] == [("Offer", "in_progress")]

    await ing.ingest(
        "ING-HITL-PHASE",
        "I-1",
        "resumed",
        {"phase": "Offer"},
        at=101.0,
    )
    phase = state.store.get_phases("ING-HITL-PHASE")[0]
    assert phase.status == "completed"
    assert phase.completed_at == 101.0


async def test_suspended_persists_persona_gate_for_recovery_sweeps():
    state, _ = _app_state()
    _seed(state, "ING-HITL", "field-repair-dispatch")
    ing = WorkflowEventIngestor(state)

    await ing.ingest("ING-HITL", "I-HITL", "suspended", {
        "reason": "awaiting_approval",
        "wait_kind": "operator_review",
        "phase": "Approve Dispatch Exception",
        "persona": "delivery_lead",
        "external_event": "delivery_lead_decision",
        "context": {
            "action": "delivery_lead_decision",
            "request": {"amount": 3500.0, "category": "dispatch_field_repair"},
        },
    })

    workflow = state.store.get_workflow("ING-HITL")
    assert workflow.current_phase == "Approve Dispatch Exception"
    assert workflow.payload["hitl_context"] == {
        "action": "delivery_lead_decision",
        "request": {"amount": 3500.0, "category": "dispatch_field_repair"},
        "phase": "Approve Dispatch Exception",
        "persona": "delivery_lead",
        "external_event": "delivery_lead_decision",
    }


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


async def test_ingested_lifecycle_aliases_translate_once_and_rejection_is_error_only():
    state, captured = _app_state()
    _seed(state, "ING-ALIASES")
    ing = WorkflowEventIngestor(state)
    translator = SubstrateToAGUI("ING-ALIASES")

    await ing.ingest("ING-ALIASES", "I-1", "workflow.started", {})
    await ing.ingest("ING-ALIASES", "I-1", "workflow.rejected", {
        "by": "operator",
        "reason": "evidence missing",
    })

    translated_types = [
        event.__class__.__name__
        for fleet_event in captured
        for event in translator.translate(fleet_event)
    ]

    assert translated_types == ["RunStarted", "RunError"]


async def test_validator_blocked_live_sequence_is_recoverable_and_can_complete():
    state, captured = _app_state()
    _seed(state, "ING-VALIDATOR-RECOVERY", "vendor-kyc")
    ing = WorkflowEventIngestor(state)
    translator = SubstrateToAGUI("ING-VALIDATOR-RECOVERY")

    await ing.ingest(
        "ING-VALIDATOR-RECOVERY",
        "I-1",
        "validator.blocked",
        {"name": "validate_signoff", "reason": "missing_signoff"},
    )
    await ing.ingest(
        "ING-VALIDATOR-RECOVERY",
        "I-1",
        "workflow.completed",
        {},
    )

    translated = [
        event
        for fleet_event in captured
        for event in translator.translate(fleet_event)
    ]

    assert [event.__class__.__name__ for event in translated] == [
        "CustomEvent",
        "CustomEvent",
        "RunFinished",
    ]
    assert translated[0].value == {
        "category": "validator-blocked",
        "severity": "high",
        "reason": "missing_signoff",
    }


async def test_workflow_failed_is_single_canonical_failure_terminal():
    state, captured = _app_state()
    _seed(state, "ING-FAILED")
    ing = WorkflowEventIngestor(state)

    await ing.ingest(
        "ING-FAILED",
        "I-1",
        "workflow.failed",
        {"by": "world_bridge", "reason": "no command"},
    )

    assert state.store.get_workflow("ING-FAILED").status == "failed"
    assert state.orchestration_history["ING-FAILED"][-1]["kind"] == "workflow.failed"
    types = [event.type for event in captured]
    assert types.count("workflow.failed") == 1
    assert "workflow.resolved" not in types
    assert "durable.workflow.completed" not in types


@pytest.mark.parametrize(
    ("kind", "payload", "expected_status", "expected_metadata"),
    (
        ("workflow.completed", {}, "completed", {}),
        (
            "workflow.failed",
            {"reason": "fatal"},
            "failed",
            {"failure_reason": "fatal"},
        ),
        (
            "workflow.rejected",
            {"by": "manager", "reason": "declined", "phase": "Offer"},
            "failed",
            {"rejected": True, "rejection_reason": "declined"},
        ),
    ),
)
async def test_terminal_replay_patch_contains_mutated_terminal_state(
    kind,
    payload,
    expected_status,
    expected_metadata,
):
    state, _ = _app_state()
    workflow_id = f"ING-REPLAY-{kind}"
    _seed(state, workflow_id)
    state.store.upsert_exception(WorkflowException(
        id=f"EXC-{kind}",
        workflow_id=workflow_id,
        composed_by="validator",
        severity="high",
        category="validator-blocked",
        summary="Needs review",
        recommendation="Resolve before terminal state",
        created_at=time.time(),
    ))
    ing = WorkflowEventIngestor(state)
    mutation_bus = MutationBus()
    set_active_bus(mutation_bus)
    try:
        await ing.ingest(workflow_id, "I-1", kind, payload)
    finally:
        set_active_bus(None)

    workflow_patches = [
        entry["patch"]
        for entry in mutation_bus.entries
        if entry["kind"] == "workflow" and entry["id"] == workflow_id
    ]
    assert workflow_patches[-1]["status"] == expected_status
    assert workflow_patches[-1]["metadata"] | expected_metadata == (
        workflow_patches[-1]["metadata"]
    )
    assert workflow_patches[-1]["activeExceptionId"] is None
    exception_patches = [
        entry["patch"]
        for entry in mutation_bus.entries
        if entry["kind"] == "exception" and entry["id"] == f"EXC-{kind}"
    ]
    assert exception_patches[-1]["resolvedAt"] is not None
    assert exception_patches[-1]["resolvedBy"] == f"auto-resolved:{kind.removeprefix('workflow.')}"
    if kind == "workflow.rejected":
        terminal = state.store.get_workflow(workflow_id).action_ledger[-1]
        assert terminal.details == {
            "phase": "Offer",
            "reason": "declined",
        }
        rejected_phase = state.store.get_phases(workflow_id)[0]
        assert (rejected_phase.name, rejected_phase.status) == ("Offer", "failed")


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


async def test_agent_completed_persists_ingest_completion_timestamp():
    state, _ = _app_state()
    _seed(state, "ING-AGENT")
    ing = WorkflowEventIngestor(state)

    await ing.ingest("ING-AGENT", "I-1", "agent.completed", {
        "agent_label": "risk_reviewer",
        "model": "gpt-4.1",
        "messages": [{"role": "assistant", "content": "Checked evidence"}],
        "tool_calls": [{"tool": "screenVendor", "result": {"clear": True}}],
        "extracted_json": {"verdict": "amber"},
        "latency_ms": 250,
        "usage": {"input_tokens": 12, "output_tokens": 3},
    }, at=1_234.5)

    reasoning = state.store.get_agent_reasoning("ING-AGENT")
    assert len(reasoning) == 1
    assert reasoning[0]["completed_at"] == 1_234.5
    assert reasoning[0]["messages"] == [
        {"role": "assistant", "content": "Checked evidence"},
    ]
    assert reasoning[0]["tool_calls"] == [
        {"tool": "screenVendor", "result": {"clear": True}},
    ]
    assert reasoning[0]["extracted_json"] == {"verdict": "amber"}
    assert reasoning[0]["latency_ms"] == 250
    assert reasoning[0]["usage"] == {"input_tokens": 12, "output_tokens": 3}


async def test_agent_completed_backfills_mcp_calls_when_tool_webhooks_are_lost():
    state, _ = _app_state()
    _seed(state, "ING-AGENT-TOOLS")
    ing = WorkflowEventIngestor(state)

    await ing.ingest("ING-AGENT-TOOLS", "I-1", "agent.completed", {
        "agent_label": "risk_reviewer",
        "agent_run_id": "agent-run-lost-tools",
        "messages": [],
        "tool_calls": [
            {
                "toolCallId": "call-empty",
                "name": "emptyLookup",
                "args": "",
                "result": "",
                "success": True,
                "durationMs": 0,
            },
            {
                "tool_call_id": "call-failed",
                "name": "screenVendor",
                "args": '{"vendorId":"V-404"}',
                "result": '{"error":{"code":"NOT_FOUND"}}',
                "success": False,
                "latency_ms": 17,
            },
        ],
        "extracted_json": {"verdict": "red"},
        "response_text": '{"verdict":"red"}',
        "usage": {"input_tokens": 12, "output_tokens": 3},
    }, at=1_234.5)

    calls = {
        call.tool_call_id: call
        for call in state.store.get_mcp_calls("ING-AGENT-TOOLS")
    }
    assert set(calls) == {"call-empty", "call-failed"}
    assert calls["call-empty"].tool == "emptyLookup"
    assert calls["call-empty"].request == {"args": ""}
    assert calls["call-empty"].response == {"result": ""}
    assert calls["call-empty"].status_code == 200
    assert calls["call-empty"].duration_ms == 0
    assert calls["call-empty"].timestamp == 1_234.5
    assert calls["call-failed"].request == {"vendorId": "V-404"}
    assert calls["call-failed"].response == {
        "error": {"code": "NOT_FOUND"},
    }
    assert calls["call-failed"].status_code == 500
    assert calls["call-failed"].duration_ms == 17


async def test_agent_completed_normalises_camel_only_tool_fallback_before_persistence():
    state, _ = _app_state()
    _seed(state, "ING-AGENT-CAMEL")
    ing = WorkflowEventIngestor(state)

    await ing.ingest("ING-AGENT-CAMEL", "I-1", "agent.completed", {
        "agent_label": "risk_reviewer",
        "toolCalls": [{
            "callId": "call-camel",
            "toolName": "screenVendor",
            "arguments": '{"vendorId":"V-7"}',
            "output": '{"clear":true}',
            "durationMs": 23,
            "statusCode": 201,
        }],
        "response_text": "{}",
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }, at=1_234.5)

    calls = state.store.get_mcp_calls("ING-AGENT-CAMEL")
    assert len(calls) == 1
    assert calls[0].tool_call_id == "call-camel"
    assert calls[0].tool == "screenVendor"
    assert calls[0].request == {"vendorId": "V-7"}
    assert calls[0].response == {"clear": True}
    assert calls[0].status_code == 201
    assert calls[0].duration_ms == 23
    reasoning = state.store.get_agent_reasoning("ING-AGENT-CAMEL")[0]
    assert reasoning["toolCalls"][0]["callId"] == "call-camel"


async def test_tool_ingestion_normalises_aliases_and_dedupes_agent_fallback_by_id():
    state, _ = _app_state()
    _seed(state, "ING-TOOL-CAMEL")
    ing = WorkflowEventIngestor(state)

    await ing.ingest("ING-TOOL-CAMEL", "I-1", "tool.invoked", {
        "stage": "complete",
        "callId": "call-shared-camel",
        "toolName": "screenVendor",
        "arguments": '{"source":"tool-event"}',
        "output": '{"clear":false}',
        "latencyMs": 31,
        "status": "failed",
    }, at=10.0)
    await ing.ingest("ING-TOOL-CAMEL", "I-1", "agent.completed", {
        "agent_label": "risk_reviewer",
        "toolCalls": [{
            "id": "call-shared-camel",
            "name": "screenVendor",
            "request": '{"source":"agent-fallback"}',
            "response": '{"clear":false}',
            "latency_ms": 99,
            "success": True,
        }],
        "response_text": "{}",
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }, at=11.0)

    calls = state.store.get_mcp_calls("ING-TOOL-CAMEL")
    assert len(calls) == 1
    assert calls[0].tool_call_id == "call-shared-camel"
    assert calls[0].request == {"source": "tool-event"}
    assert calls[0].response == {"clear": False}
    assert calls[0].status_code == 500
    assert calls[0].duration_ms == 31


@pytest.mark.parametrize("webhook_first", [True, False])
async def test_tool_webhook_and_agent_fallback_do_not_duplicate_mcp_call(
    webhook_first,
):
    state, _ = _app_state()
    workflow_id = f"ING-AGENT-DUP-{webhook_first}"
    _seed(state, workflow_id)
    ing = WorkflowEventIngestor(state)
    webhook_payload = {
        "tool": "screenVendor",
        "stage": "complete",
        "tool_call_id": "call-shared",
        "args": '{"source":"webhook"}',
        "result": '{"error":{"code":"DENIED"}}',
        "success": False,
        "duration_ms": 9,
    }
    completion_payload = {
        "agent_label": "risk_reviewer",
        "agent_run_id": "agent-run-duplicate-tool",
        "messages": [],
        "tool_calls": [{
            "toolCallId": "call-shared",
            "name": "screenVendor",
            "args": '{"source":"agent"}',
            "result": '{"error":{"code":"DENIED"}}',
            "success": False,
            "durationMs": 9,
        }],
        "response_text": "{}",
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }

    if webhook_first:
        await ing.ingest(
            workflow_id,
            "I-1",
            "tool.invoked",
            webhook_payload,
            at=10.0,
        )
        await ing.ingest(
            workflow_id,
            "I-1",
            "agent.completed",
            completion_payload,
            at=11.0,
        )
    else:
        await ing.ingest(
            workflow_id,
            "I-1",
            "agent.completed",
            completion_payload,
            at=10.0,
        )
        await ing.ingest(
            workflow_id,
            "I-1",
            "tool.invoked",
            webhook_payload,
            at=11.0,
        )

    calls = state.store.get_mcp_calls(workflow_id)
    assert len(calls) == 1
    assert calls[0].tool_call_id == "call-shared"
    assert calls[0].request == {
        "source": "webhook" if webhook_first else "agent",
    }
    assert calls[0].response == {"error": {"code": "DENIED"}}
    assert calls[0].status_code == 500
    assert calls[0].timestamp == 10.0


async def test_agent_completed_span_carries_shared_invocation_and_phase():
    state, _ = _app_state()
    _seed(state, "ING-AGENT-CORRELATION", "vendor-kyc")
    ing = WorkflowEventIngestor(state)

    await ing.ingest("ING-AGENT-CORRELATION", "I-1", "agent.completed", {
        "agent_label": "fleet-vendor-kyc-kyc-diligence-checker",
        "agent_run_id": "ar-shared-1",
        "phase": "KYC Diligence",
        "latency_ms": 250,
        "usage": {"input_tokens": 12, "output_tokens": 3},
    }, at=1_234.5)

    spans = state.store.get_spans("ING-AGENT-CORRELATION")

    assert len(spans) == 1
    assert spans[0].attributes["gen_ai.agent.run_id"] == "ar-shared-1"
    assert spans[0].attributes["workflow.phase"] == "KYC Diligence"


async def test_agent_completed_waits_for_accepted_step_before_completing_phase():
    state, _ = _app_state()
    workflow = _seed(state, "ING-SEGMENT-PHASES", "hiring")
    ing = WorkflowEventIngestor(state)

    await ing.ingest(
        "ING-SEGMENT-PHASES",
        "I-1",
        "step.started",
        {"step": "Screening", "agent_id": "hiring-segment-b"},
        at=1_234.0,
    )
    await ing.ingest("ING-SEGMENT-PHASES", "I-1", "agent.completed", {
        "agent_label": "hiring-segment-b",
        "agent_run_id": "ar-segment-b",
        "covered_phases": ["Screening"],
        "latency_ms": 250,
        "usage": {"input_tokens": 12, "output_tokens": 3},
    }, at=1_234.5)

    phase = state.store.get_phases("ING-SEGMENT-PHASES")[0]
    assert (phase.name, phase.status, phase.completed_at) == (
        "Screening",
        "in_progress",
        None,
    )
    assert workflow.current_phase == "Screening"
    assert state.store.get_agent_reasoning("ING-SEGMENT-PHASES")[0][
        "covered_phases"
    ] == ["Screening"]

    await ing.ingest(
        "ING-SEGMENT-PHASES",
        "I-1",
        "step.completed",
        {"step": "Screening", "agent_id": "hiring-segment-b"},
        at=1_235.0,
    )

    assert (phase.status, phase.completed_at) == ("completed", 1_235.0)


@pytest.mark.parametrize(
    "failure_kind",
    ["segment.failed", "segment.failed.irreversible", "segment.rejected"],
)
async def test_failed_segment_retry_is_not_completed_by_agent_event(failure_kind):
    state, _ = _app_state()
    _seed(state, f"ING-SEGMENT-RETRY-{failure_kind}", "hiring")
    ing = WorkflowEventIngestor(state)
    workflow_id = f"ING-SEGMENT-RETRY-{failure_kind}"

    await ing.ingest(
        workflow_id,
        "I-1",
        "step.started",
        {"step": "Screening"},
        at=10.0,
    )
    await ing.ingest(
        workflow_id,
        "I-1",
        failure_kind,
        {"phase": "Screening", "reason": "validator rejected output"},
        at=11.0,
    )
    phase = state.store.get_phases(workflow_id)[0]
    assert (phase.status, phase.completed_at) == ("failed", 11.0)
    failure_entry = state.store.get_workflow(workflow_id).action_ledger[-1]
    assert failure_entry.action == "phase.failed:Screening"
    assert failure_entry.details == {"reason": "validator rejected output"}

    await ing.ingest(
        workflow_id,
        "I-1",
        "step.started",
        {"step": "Screening"},
        at=12.0,
    )
    await ing.ingest(
        workflow_id,
        "I-1",
        "agent.completed",
        {
            "agent_label": "hiring-segment-b",
            "agent_run_id": "ar-segment-b-retry",
            "covered_phases": ["Screening"],
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
        at=13.0,
    )

    assert (phase.status, phase.completed_at) == ("in_progress", None)

    await ing.ingest(
        workflow_id,
        "I-1",
        "step.completed",
        {"step": "Screening"},
        at=14.0,
    )
    assert (phase.status, phase.completed_at) == ("completed", 14.0)


async def test_agent_output_persists_ingestion_timestamp_without_mutating_output():
    state, _ = _app_state()
    _seed(state, "ING-OUTPUT")
    ing = WorkflowEventIngestor(state)
    output = {
        "verdict": "green",
        "profile": {"current_title": "Senior Data Engineer"},
    }

    await ing.ingest(
        "ING-OUTPUT",
        "I-OUTPUT",
        "agent_output",
        {"agent": "cv_crystalliser", "output": output},
        at=1_345.5,
    )

    assert state.store.get_agent_outputs("ING-OUTPUT") == {
        "cv_crystalliser": output,
    }
    assert state.store.get_agent_output_recorded_at(
        "ING-OUTPUT",
        "cv_crystalliser",
    ) == 1_345.5
    assert "recorded_at" not in output


async def test_completed_wrapper_tool_persists_real_request_and_result():
    state, captured = _app_state()
    _seed(state, "ING-TOOL")
    ing = WorkflowEventIngestor(state)

    await ing.ingest("ING-TOOL", "I-TOOL", "tool.invoked", {
        "tool": "screenVendor",
        "skill": "risk_reviewer",
        "stage": "start",
        "tool_call_id": "call-7",
        "agent_run_id": "session-run-7",
        "invocation_id": "executor-parent-7",
        "args": '{"vendorId":"V-1"}',
    }, at=10.0)
    assert state.store.get_mcp_calls("ING-TOOL") == []

    await ing.ingest("ING-TOOL", "I-TOOL", "tool.invoked", {
        "tool": "screenVendor",
        "skill": "risk_reviewer",
        "stage": "complete",
        "tool_call_id": "call-7",
        "agent_run_id": "session-run-7",
        "invocation_id": "executor-parent-7",
        "args": '{"vendorId":"V-1"}',
        "result": '{"clear":true,"matches":[]}',
        "success": True,
        "duration_ms": 25,
    }, at=10.025)

    calls = state.store.get_mcp_calls("ING-TOOL")
    assert len(calls) == 1
    assert calls[0].request == {"vendorId": "V-1"}
    assert calls[0].response == {"clear": True, "matches": []}
    assert calls[0].status_code == 200
    assert calls[0].duration_ms == 25
    tool_events = [
        event
        for event in captured
        if event.type == "durable.executor.invoked"
        and event.executor_type == "tool"
    ]
    assert {event.agent_run_id for event in tool_events} == {"session-run-7"}
    assert {event.invocation_id for event in tool_events} == {
        "executor-parent-7"
    }


async def test_deterministic_executor_does_not_fabricate_an_mcp_call():
    state, _ = _app_state()
    _seed(state, "ING-DETERMINISTIC")
    ing = WorkflowEventIngestor(state)

    await ing.ingest("ING-DETERMINISTIC", "I-DET", "executor.invoked", {
        "name": "calculate_rebalance",
        "type": "deterministic",
        "stage": "complete",
        "duration_ms": 7,
    }, at=10.0)

    assert state.store.get_mcp_calls("ING-DETERMINISTIC") == []
    spans = state.store.get_spans("ING-DETERMINISTIC")
    assert len(spans) == 1
    assert spans[0].attributes["executor.type"] == "deterministic"
