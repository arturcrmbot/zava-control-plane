from __future__ import annotations

import asyncio
import ast
import json
from pathlib import Path
import re
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from copilot.generated.session_events import Result, ResultKind, SessionEventType

from api.functions.graphs.executors.agents._wrapper import (
    _make_session_otel_bridge,
    run_agent_session,
)
from api.server.services.event_bus import EventBus
from api.server.services.state_store import StateStore
from api.server.services.workflow_event_ingestor import WorkflowEventIngestor
from api.shared.types import Workflow


def _ingestor() -> tuple[WorkflowEventIngestor, SimpleNamespace]:
    state = SimpleNamespace(
        bus=EventBus(),
        store=StateStore(),
        hub=MagicMock(),
        audit=MagicMock(),
        orchestration_history={},
        domain_memories={},
        cost_budget=MagicMock(),
    )
    state.store.upsert_workflow(Workflow(
        id="workflow-42",
        type="vendor-kyc",
        created_at=1.0,
        sla_due_at=2.0,
        jurisdiction="UK",
        agency="Zava",
    ))
    return WorkflowEventIngestor(state), state


@pytest.mark.asyncio
async def test_tool_webhook_uses_real_instance_id_at_checkpoint_ingestion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ingestor, state = _ingestor()
    ingested = asyncio.Event()

    async def ingest_webhook(workflow_id, instance_id, kind, payload):
        await ingestor.ingest(workflow_id, instance_id, kind, payload, at=10.0)
        ingested.set()

    monkeypatch.setattr("api.functions.webhook.emit", ingest_webhook)
    handler = _make_session_otel_bridge(
        [],
        workflow_id="workflow-42",
        instance_id="orchestration-instance-99",
        skill_label="kyc-diligence",
    )

    handler(SimpleNamespace(
        type=SessionEventType.TOOL_EXECUTION_START,
        data=SimpleNamespace(
            tool_name="vendor_registry_lookup",
            tool_call_id="call-7",
            tool_args={"vendor_id": "V-1"},
        ),
    ))
    await asyncio.wait_for(ingested.wait(), timeout=1)

    entry = state.orchestration_history["workflow-42"][-1]
    assert entry["instance_id"] == "orchestration-instance-99"
    assert entry["instance_id"] != "workflow-42"


@pytest.mark.asyncio
async def test_completed_tool_webhook_preserves_result_as_historical_mcp_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ingestor, state = _ingestor()
    ingested = asyncio.Event()
    event_count = 0

    async def ingest_webhook(workflow_id, instance_id, kind, payload):
        nonlocal event_count
        await ingestor.ingest(workflow_id, instance_id, kind, payload, at=20.0 + event_count)
        event_count += 1
        if event_count == 2:
            ingested.set()

    monkeypatch.setattr("api.functions.webhook.emit", ingest_webhook)
    collected: list[dict] = []
    handler = _make_session_otel_bridge(
        collected,
        workflow_id="workflow-42",
        instance_id="orchestration-instance-99",
        skill_label="kyc-diligence",
    )
    handler(SimpleNamespace(
        type=SessionEventType.TOOL_EXECUTION_START,
        data=SimpleNamespace(
            tool_name="vendor_registry_lookup",
            tool_call_id="call-7",
            tool_args={"vendor_id": "V-1"},
        ),
    ))
    handler(SimpleNamespace(
        type=SessionEventType.TOOL_EXECUTION_COMPLETE,
        data=SimpleNamespace(
            tool_call_id="call-7",
            result={"vendor_id": "V-1", "status": "active"},
            success=True,
        ),
    ))
    await asyncio.wait_for(ingested.wait(), timeout=1)

    assert collected == [{
        "tool_call_id": "call-7",
        "name": "vendor_registry_lookup",
        "tool": "vendor_registry_lookup",
        "args": '{"vendor_id": "V-1"}',
        "result": '{"vendor_id": "V-1", "status": "active"}',
        "success": True,
        "latency_ms": collected[0]["latency_ms"],
    }]
    complete = state.orchestration_history["workflow-42"][-1]
    assert complete["payload"] == {
        "tool": "vendor_registry_lookup",
        "skill": "kyc-diligence",
        "stage": "complete",
        "tool_call_id": "call-7",
        "args": '{"vendor_id": "V-1"}',
        "result": '{"vendor_id": "V-1", "status": "active"}',
        "success": True,
        "duration_ms": collected[0]["latency_ms"],
    }
    calls = state.store.get_mcp_calls("workflow-42")
    assert len(calls) == 1
    assert calls[0].tool_call_id == "call-7"
    assert calls[0].tool == "vendor_registry_lookup"
    assert calls[0].request == {"vendor_id": "V-1"}
    assert calls[0].response == {"vendor_id": "V-1", "status": "active"}

    await ingestor.ingest(
        "workflow-42",
        "orchestration-instance-99",
        "agent.completed",
        {
            "agent_label": "kyc-diligence",
            "agent_run_id": "agent-run-call-7",
            "messages": [],
            "tool_calls": collected,
            "extracted_json": {"verdict": "clear"},
            "response_text": '{"verdict":"clear"}',
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
        at=23.0,
    )

    from api.server.routes import workflows

    state.audit.blob_url_for.return_value = None
    monkeypatch.setattr(workflows, "app_state", state)
    detail = await workflows.get_workflow("workflow-42")
    reasoning = next(row for row in detail["timeline"] if row["kind"] == "reasoning")
    tool_row = next(row for row in detail["timeline"] if row["kind"] == "tool")

    assert reasoning["toolCalls"][0]["toolCallId"] == "call-7"
    assert detail["mcpCalls"][0]["toolCallId"] == "call-7"
    assert tool_row["toolCallId"] == "call-7"
    assert tool_row["id"] == "call-7"


@pytest.mark.asyncio
async def test_completed_tool_preserves_full_sdk_result_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    emitted: list[dict] = []
    completed = asyncio.Event()

    async def capture(_workflow_id, _instance_id, _kind, payload):
        emitted.append(payload)
        if payload["stage"] == "complete":
            completed.set()

    monkeypatch.setattr("api.functions.webhook.emit", capture)
    collected: list[dict] = []
    handler = _make_session_otel_bridge(
        collected,
        workflow_id="workflow-42",
        instance_id="orchestration-instance-99",
        skill_label="kyc-diligence",
    )
    handler(SimpleNamespace(
        type=SessionEventType.TOOL_EXECUTION_START,
        data=SimpleNamespace(
            tool_name="vendor_registry_lookup",
            tool_call_id="call-sdk-1",
            arguments={"vendor_id": "V-1"},
        ),
    ))
    sdk_result = Result(
        content='{"vendor_id":"V-1","status":"active"}',
        detailed_content="registry lookup completed without truncation",
        kind=ResultKind.APPROVED,
    )
    handler(SimpleNamespace(
        type=SessionEventType.TOOL_EXECUTION_COMPLETE,
        data=SimpleNamespace(
            tool_call_id="call-sdk-1",
            result=sdk_result,
            success=True,
        ),
    ))
    await asyncio.wait_for(completed.wait(), timeout=1)

    expected = sdk_result.to_dict()
    assert json.loads(collected[0]["result"]) == expected
    complete_payload = next(item for item in emitted if item["stage"] == "complete")
    assert json.loads(complete_payload["result"]) == expected


@pytest.mark.asyncio
async def test_missing_sdk_tool_call_id_is_created_once_and_reused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    emitted: list[dict] = []
    completed = asyncio.Event()

    async def capture(_workflow_id, _instance_id, _kind, payload):
        emitted.append(payload)
        if payload["stage"] == "complete":
            completed.set()

    monkeypatch.setattr("api.functions.webhook.emit", capture)
    collected: list[dict] = []
    handler = _make_session_otel_bridge(
        collected,
        workflow_id="workflow-42",
        instance_id="orchestration-instance-99",
        skill_label="kyc-diligence",
    )

    handler(SimpleNamespace(
        type=SessionEventType.TOOL_EXECUTION_START,
        data=SimpleNamespace(
            tool_name="vendor_registry_lookup",
            arguments={"vendor_id": "V-1"},
        ),
    ))
    handler(SimpleNamespace(
        type=SessionEventType.TOOL_EXECUTION_COMPLETE,
        data=SimpleNamespace(
            result={"status": "active"},
            success=True,
        ),
    ))
    await asyncio.wait_for(completed.wait(), timeout=1)

    generated_id = emitted[0]["tool_call_id"]
    assert generated_id
    assert emitted[1]["tool_call_id"] == generated_id
    assert collected[0]["tool_call_id"] == generated_id


@pytest.mark.asyncio
async def test_tool_callback_preserves_valid_empty_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed = asyncio.Event()

    async def capture(_workflow_id, _instance_id, _kind, payload):
        if payload["stage"] == "complete":
            completed.set()

    monkeypatch.setattr("api.functions.webhook.emit", capture)
    collected: list[dict] = []
    handler = _make_session_otel_bridge(
        collected,
        workflow_id="workflow-42",
        instance_id="orchestration-instance-99",
        skill_label="kyc-diligence",
    )

    handler(SimpleNamespace(
        type=SessionEventType.TOOL_EXECUTION_START,
        data=SimpleNamespace(
            tool_name="vendor_registry_lookup",
            tool_call_id="call-empty-args",
            tool_args={},
            arguments={"must_not": "replace valid empty args"},
        ),
    ))
    handler(SimpleNamespace(
        type=SessionEventType.TOOL_EXECUTION_COMPLETE,
        data=SimpleNamespace(
            tool_call_id="call-empty-args",
            result={"status": "active"},
            success=True,
        ),
    ))
    await asyncio.wait_for(completed.wait(), timeout=1)

    assert json.loads(collected[0]["args"]) == {}


@pytest.mark.asyncio
async def test_failed_tool_callback_persists_sdk_error_as_mcp_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ingestor, state = _ingestor()
    completed = asyncio.Event()

    async def ingest_webhook(workflow_id, instance_id, kind, payload):
        await ingestor.ingest(workflow_id, instance_id, kind, payload, at=30.0)
        if payload["stage"] == "complete":
            completed.set()

    monkeypatch.setattr("api.functions.webhook.emit", ingest_webhook)
    collected: list[dict] = []
    handler = _make_session_otel_bridge(
        collected,
        workflow_id="workflow-42",
        instance_id="orchestration-instance-99",
        skill_label="kyc-diligence",
    )
    handler(SimpleNamespace(
        type=SessionEventType.TOOL_EXECUTION_START,
        data=SimpleNamespace(
            tool_name="vendor_registry_lookup",
            tool_call_id="call-failed",
            arguments={"vendor_id": "V-404"},
        ),
    ))
    handler(SimpleNamespace(
        type=SessionEventType.TOOL_EXECUTION_COMPLETE,
        data=SimpleNamespace(
            tool_call_id="call-failed",
            result=None,
            output=None,
            error={"code": "NOT_FOUND", "message": "Vendor V-404 was not found"},
            success=False,
        ),
    ))
    await asyncio.wait_for(completed.wait(), timeout=1)

    expected_error = {
        "error": {"code": "NOT_FOUND", "message": "Vendor V-404 was not found"},
    }
    assert json.loads(collected[0]["result"]) == expected_error
    calls = state.store.get_mcp_calls("workflow-42")
    assert len(calls) == 1
    assert collected[0]["tool_call_id"] == "call-failed"
    assert calls[0].tool_call_id == "call-failed"
    assert calls[0].status_code == 500
    assert calls[0].response == expected_error


@pytest.mark.asyncio
async def test_agent_completed_preserves_messages_runtime_tools_and_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from api.functions.graphs.executors.agents.runtime import LLMRuntimeResult

    runtime_tool_call = {
        "name": "policy_search",
        "tool": "policy_search",
        "args": '{"query":"travel"}',
        "result": '{"limit":500}',
        "success": True,
        "latency_ms": 12,
    }

    class _Runtime:
        async def run_session(self, **_kwargs):
            return LLMRuntimeResult(
                text='{"decision":"approve"}',
                tool_calls=[runtime_tool_call],
                input_tokens=21,
                output_tokens=8,
            )

    emitted: list[dict] = []

    async def capture(workflow_id, instance_id, kind, payload):
        emitted.append({
            "workflow_id": workflow_id,
            "instance_id": instance_id,
            "kind": kind,
            "payload": payload,
        })

    monkeypatch.setattr(
        "api.functions.graphs.executors.agents._wrapper._get_runtime",
        lambda: _Runtime(),
    )
    monkeypatch.setattr("api.functions.webhook.emit", capture)

    parsed = await run_agent_session(
        prompt="Review the travel request",
        skill_label="travel-policy",
        workflow_id="workflow-42",
        instance_id="orchestration-instance-99",
        covered_phases=["Policy Fit", "Risk Check"],
    )

    completed = next(event for event in emitted if event["kind"] == "agent.completed")
    assert completed["workflow_id"] == "workflow-42"
    assert completed["instance_id"] == "orchestration-instance-99"
    assert completed["payload"]["messages"] == [
        {"role": "user", "content": "Review the travel request"},
        {"role": "assistant", "content": '{"decision":"approve"}'},
    ]
    assert parsed["_raw_tool_calls"] == [runtime_tool_call]
    assert completed["payload"]["tool_calls"] == [runtime_tool_call]
    assert completed["payload"]["extracted_json"] == {"decision": "approve"}
    assert completed["payload"]["latency_ms"] >= 0
    assert completed["payload"]["usage"] == {
        "input_tokens": 21,
        "output_tokens": 8,
    }
    assert completed["payload"]["covered_phases"] == [
        "Policy Fit",
        "Risk Check",
    ]


@pytest.mark.asyncio
async def test_agent_completion_is_emitted_after_its_tool_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from api.functions.graphs.executors.agents.runtime import LLMRuntimeResult

    class _Runtime:
        callback_elapsed_s = 0.0

        async def run_session(self, **kwargs):
            on_event = kwargs["event_subscriber"]
            started_at = time.monotonic()
            on_event(SimpleNamespace(
                type=SessionEventType.TOOL_EXECUTION_START,
                data=SimpleNamespace(
                    tool_name="policy_search",
                    tool_call_id="call-order-1",
                    arguments={"query": "travel"},
                ),
            ))
            on_event(SimpleNamespace(
                type=SessionEventType.TOOL_EXECUTION_COMPLETE,
                data=SimpleNamespace(
                    tool_call_id="call-order-1",
                    result={"limit": 500},
                    success=True,
                ),
            ))
            self.callback_elapsed_s = time.monotonic() - started_at
            return LLMRuntimeResult(
                text='{"decision":"approve"}',
                tool_calls=[],
                input_tokens=21,
                output_tokens=8,
            )

    runtime = _Runtime()
    order: list[str] = []
    emitted: list[tuple[str, dict]] = []

    async def capture(_workflow_id, _instance_id, kind, payload):
        await asyncio.sleep(0.03)
        order.append(f"{kind}:{payload.get('stage', 'complete')}")
        emitted.append((kind, payload))

    monkeypatch.setattr(
        "api.functions.graphs.executors.agents._wrapper._get_runtime",
        lambda: runtime,
    )
    monkeypatch.setattr(
        "api.functions.graphs._tracked_executor.current_execution_invocation_id",
        lambda: "executor-parent-1",
    )
    monkeypatch.setattr("api.functions.webhook.emit", capture)

    await run_agent_session(
        prompt="Review the travel request",
        skill_label="travel-policy",
        workflow_id="workflow-42",
        instance_id="orchestration-instance-99",
    )

    assert runtime.callback_elapsed_s < 0.03
    assert order == [
        "tool.invoked:start",
        "tool.invoked:complete",
        "agent.completed:complete",
    ]
    completed = emitted[-1][1]
    assert re.fullmatch(r"ar-[0-9a-f]{32}", completed["agent_run_id"])
    tool_payloads = [payload for kind, payload in emitted if kind == "tool.invoked"]
    assert completed["invocation_id"] == "executor-parent-1"
    assert completed["agent_run_id"] != "executor-parent-1"
    assert {
        payload["invocation_id"] for payload in tool_payloads
    } == {"executor-parent-1"}
    assert {
        payload["agent_run_id"] for payload in tool_payloads
    } == {completed["agent_run_id"]}
    assert {
        payload["tool_call_id"] for payload in tool_payloads
    } == {"call-order-1"}


@pytest.mark.asyncio
async def test_webhook_flush_uses_one_bounded_deadline_and_cancels_pending_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from api.functions.graphs.executors.agents import _wrapper
    from api.functions.graphs.executors.agents.runtime import LLMRuntimeResult

    class _Runtime:
        async def run_session(self, **kwargs):
            on_event = kwargs["event_subscriber"]
            on_event(SimpleNamespace(
                type=SessionEventType.TOOL_EXECUTION_START,
                data=SimpleNamespace(
                    tool_name="policy_search",
                    tool_call_id="call-timeout-1",
                    arguments={"query": "travel"},
                ),
            ))
            on_event(SimpleNamespace(
                type=SessionEventType.TOOL_EXECUTION_COMPLETE,
                data=SimpleNamespace(
                    tool_call_id="call-timeout-1",
                    result={"limit": 500},
                    success=True,
                ),
            ))
            return LLMRuntimeResult(
                text='{"decision":"approve"}',
                tool_calls=[],
                input_tokens=21,
                output_tokens=8,
            )

    never_finishes = asyncio.Event()
    cancelled = asyncio.Event()

    async def blocked_emit(*_args, **_kwargs):
        try:
            await never_finishes.wait()
        finally:
            cancelled.set()

    monkeypatch.setattr(_wrapper, "_get_runtime", lambda: _Runtime())
    monkeypatch.setattr(_wrapper, "_WEBHOOK_FLUSH_TIMEOUT_S", 0.03, raising=False)
    monkeypatch.setattr(
        _wrapper,
        "_WEBHOOK_COMPLETION_TIMEOUT_S",
        0.03,
        raising=False,
    )
    monkeypatch.setattr("api.functions.webhook.emit", blocked_emit)

    parsed = await asyncio.wait_for(
        run_agent_session(
            prompt="Review the travel request",
            skill_label="travel-policy",
            workflow_id="workflow-42",
            instance_id="orchestration-instance-99",
        ),
        timeout=0.2,
    )

    assert parsed["decision"] == "approve"
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_completion_gets_an_independent_deadline_after_slow_tool_delivery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from api.functions.graphs.executors.agents import _wrapper
    from api.functions.graphs.executors.agents.runtime import LLMRuntimeResult

    class _Runtime:
        async def run_session(self, **kwargs):
            on_event = kwargs["event_subscriber"]
            on_event(SimpleNamespace(
                type=SessionEventType.TOOL_EXECUTION_START,
                data=SimpleNamespace(
                    tool_name="policy_search",
                    tool_call_id="call-slow-1",
                    arguments={"query": "travel"},
                ),
            ))
            on_event(SimpleNamespace(
                type=SessionEventType.TOOL_EXECUTION_COMPLETE,
                data=SimpleNamespace(
                    tool_call_id="call-slow-1",
                    result={"limit": 500},
                    success=True,
                ),
            ))
            return LLMRuntimeResult(
                text='{"decision":"approve"}',
                tool_calls=[],
                input_tokens=21,
                output_tokens=8,
            )

    attempts: list[str] = []

    async def slow_tool_emit(_workflow_id, _instance_id, kind, _payload):
        attempts.append(kind)
        if kind == "tool.invoked":
            await asyncio.sleep(0.02)

    monkeypatch.setattr(_wrapper, "_get_runtime", lambda: _Runtime())
    monkeypatch.setattr(
        _wrapper,
        "_WEBHOOK_FLUSH_TIMEOUT_S",
        0.03,
        raising=False,
    )
    monkeypatch.setattr("api.functions.webhook.emit", slow_tool_emit)

    parsed = await asyncio.wait_for(
        run_agent_session(
            prompt="Review the travel request",
            skill_label="travel-policy",
            workflow_id="workflow-42",
            instance_id="orchestration-instance-99",
        ),
        timeout=0.2,
    )

    assert parsed["decision"] == "approve"
    assert attempts[-1] == "agent.completed"


@pytest.mark.asyncio
async def test_webhook_queue_cancels_pending_work_on_post_session_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from api.functions.graphs.executors.agents import _wrapper

    emitter_started = asyncio.Event()
    release_emitter = asyncio.Event()
    cancelled = asyncio.Event()

    async def blocked_emit(*_args, **_kwargs):
        emitter_started.set()
        try:
            await release_emitter.wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    class _Runtime:
        async def run_session(self, **kwargs):
            on_event = kwargs["event_subscriber"]
            on_event(SimpleNamespace(
                type=SessionEventType.TOOL_EXECUTION_START,
                data=SimpleNamespace(
                    tool_name="policy_search",
                    tool_call_id="call-error-cleanup",
                    arguments={"query": "travel"},
                ),
            ))
            await emitter_started.wait()
            return SimpleNamespace(
                text='{"decision":"approve"}',
                tool_calls=[],
                input_tokens="invalid",
                output_tokens=8,
            )

    monkeypatch.setattr(_wrapper, "_get_runtime", lambda: _Runtime())
    monkeypatch.setattr("api.functions.webhook.emit", blocked_emit)

    try:
        with pytest.raises(ValueError):
            await run_agent_session(
                prompt="Review the travel request",
                skill_label="travel-policy",
                workflow_id="workflow-42",
                instance_id="orchestration-instance-99",
            )
        assert cancelled.is_set()
    finally:
        release_emitter.set()
        await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_generated_agent_forwards_production_instance_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from api.functions.graphs.executors.agents import (
        agent_fleet_vendor_kyc_kyc_diligence,
    )

    run = AsyncMock(return_value={"risk": "low"})
    monkeypatch.setattr(agent_fleet_vendor_kyc_kyc_diligence, "run_agent_session", run)

    await agent_fleet_vendor_kyc_kyc_diligence.execute({
        "workflow_id": "workflow-42",
        "instance_id": "orchestration-instance-99",
        "vendor_intake": {"vendor_name": "Acme", "country_of_incorporation": "GB"},
    })

    assert run.await_args.kwargs["workflow_id"] == "workflow-42"
    assert run.await_args.kwargs["instance_id"] == "orchestration-instance-99"


def test_all_durable_agent_wrapper_calls_forward_instance_id() -> None:
    missing: list[str] = []
    root = Path("api/functions")

    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"run_agent_session", "run_agent_skill"}
            ):
                continue
            keyword_names = {keyword.arg for keyword in node.keywords}
            if "workflow_id" in keyword_names and "instance_id" not in keyword_names:
                missing.append(f"{path}:{node.lineno}")

    assert missing == []
