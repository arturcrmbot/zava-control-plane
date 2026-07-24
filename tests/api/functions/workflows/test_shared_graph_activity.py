from __future__ import annotations

import re

import pytest

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import _wrapper
from api.functions.graphs.executors.agents.runtime import LLMRuntimeResult
from api.functions.workflows.activities import _run_workflow


@pytest.mark.asyncio
async def test_run_workflow_preserves_canonical_phase_through_agent_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Runtime:
        async def run_session(self, **_kwargs):
            return LLMRuntimeResult(
                text='{"verdict":"clear"}',
                tool_calls=[],
                input_tokens=11,
                output_tokens=3,
            )

    emitted: list[dict] = []

    async def capture(workflow_id, instance_id, kind, payload):
        emitted.append({
            "workflow_id": workflow_id,
            "instance_id": instance_id,
            "kind": kind,
            "payload": payload,
        })

    async def execute(input: dict) -> dict:
        assert input["phase"] == "KYC Diligence"
        results = []
        for prompt in ("Check this vendor", "Check its beneficial owners"):
            results.append(await _wrapper.run_agent_session(
                prompt=prompt,
                skill_label="kyc-diligence",
                workflow_id=input["workflow_id"],
                instance_id=input["instance_id"],
            ))
        return {"diligence": results}

    monkeypatch.setattr(_wrapper, "_get_runtime", lambda: Runtime())
    monkeypatch.setattr("api.functions.webhook.emit", capture)
    monkeypatch.setattr("api.functions.graphs._tracked_executor.emit", capture)
    payload = {
        "workflow_id": "VKY-42",
        "instance_id": "durable-instance-99",
        "vendor_id": "V-1",
    }

    result = await _run_workflow(
        lambda: build_linear_workflow([
            ("kyc", "agent_kyc_diligence", "agent", execute),
        ]),
        payload,
        "KYC Diligence",
    )

    assert "phase" not in payload
    assert result["phase"] == "KYC Diligence"
    executor_events = [
        event for event in emitted if event["kind"] == "executor.invoked"
    ]
    assert {event["payload"]["phase"] for event in executor_events} == {
        "KYC Diligence"
    }
    executor_invocations = {
        event["payload"]["invocation_id"] for event in executor_events
    }
    assert len(executor_invocations) == 1
    invocation_id = executor_invocations.pop()
    assert re.fullmatch(r"ar-[0-9a-f]{32}", invocation_id)
    completions = [
        event for event in emitted if event["kind"] == "agent.completed"
    ]
    assert len(completions) == 2
    assert {
        completion["workflow_id"] for completion in completions
    } == {"VKY-42"}
    assert {
        completion["instance_id"] for completion in completions
    } == {"durable-instance-99"}
    assert {
        completion["payload"]["phase"] for completion in completions
    } == {"KYC Diligence"}
    assert {
        completion["payload"]["invocation_id"] for completion in completions
    } == {invocation_id}
    agent_run_ids = {
        completion["payload"]["agent_run_id"] for completion in completions
    }
    assert len(agent_run_ids) == 2
    assert all(
        re.fullmatch(r"ar-[0-9a-f]{32}", agent_run_id)
        for agent_run_id in agent_run_ids
    )
    assert invocation_id not in agent_run_ids
