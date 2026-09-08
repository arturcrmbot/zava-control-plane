from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from api.functions.graphs import _tracked_executor as tracked
from api.functions.workflows import activities


async def test_blocked_validator_does_not_forward_to_next_executor(monkeypatch):
    emit = AsyncMock()
    monkeypatch.setattr(tracked, "emit", emit)
    ctx = SimpleNamespace(send_message=AsyncMock())
    executor = tracked.TrackedExecutor(
        id="guard", name="validate_evidence", executor_type="validator",
        fn=AsyncMock(return_value={"ok": False, "blocked_reason": "missing evidence"}),
    )

    with pytest.raises(ValueError, match="missing evidence"):
        await executor.process({"workflow_id": "WF-GUARD"}, ctx)

    ctx.send_message.assert_not_awaited()
    assert any(call.args[2] == "validator.blocked" for call in emit.await_args_list)
    stages = [
        call.args[3]["stage"]
        for call in emit.await_args_list
        if call.args[2] == "executor.invoked"
    ]
    assert stages == ["start", "error"]


async def test_valid_validator_preserves_context_and_forwards(monkeypatch):
    monkeypatch.setattr(tracked, "emit", AsyncMock())
    ctx = SimpleNamespace(send_message=AsyncMock())
    executor = tracked.TrackedExecutor(
        id="guard", name="validate_evidence", executor_type="validator",
        fn=AsyncMock(return_value={"ok": True}),
    )
    await executor.process({"workflow_id": "WF-GUARD", "evidence": "present"}, ctx)
    ctx.send_message.assert_awaited_once_with({
        "workflow_id": "WF-GUARD", "evidence": "present", "ok": True,
    })


async def test_failed_activity_surfaces_workflow_failure(monkeypatch):
    emit = AsyncMock()
    monkeypatch.setattr(activities, "emit", emit)
    workflow = SimpleNamespace(run=AsyncMock(side_effect=ValueError("missing evidence")))

    with pytest.raises(ValueError, match="missing evidence"):
        await activities._run_workflow(lambda: workflow, {"workflow_id": "WF-GUARD"}, "Classify")

    kinds = [call.args[2] for call in emit.await_args_list]
    assert "workflow.failed" in kinds
    assert "step.completed" not in kinds


async def test_activity_without_output_does_not_report_success(monkeypatch):
    emit = AsyncMock()
    monkeypatch.setattr(activities, "emit", emit)
    workflow = SimpleNamespace(
        run=AsyncMock(return_value=SimpleNamespace(get_outputs=lambda: []))
    )

    with pytest.raises(RuntimeError, match="no output"):
        await activities._run_workflow(lambda: workflow, {"workflow_id": "WF-GUARD"}, "Classify")

    assert "step.completed" not in [call.args[2] for call in emit.await_args_list]
