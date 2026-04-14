# src/functions/graphs/_tracked_executor.py
"""
TrackedExecutor: wraps one of our async `execute(input: dict) -> dict` functions as a real
MAF Executor that emits webhook events before/after invocation and forwards the merged
input+output dict to the next node.

`executor_type` is one of "deterministic" | "agent" | "validator" -- it labels the event
emission so the UI can render type-specific icons.
"""
from __future__ import annotations
import time
from typing import Awaitable, Callable
from agent_framework import Executor, WorkflowContext, handler
from src.functions.webhook import emit


ExecuteFn = Callable[[dict], Awaitable[dict]]


class TrackedExecutor(Executor):
    """Wraps an async execute(input)->dict function. On each invocation, emits webhooks
    and forwards the merged dict to the next node."""

    def __init__(self, *, id: str, name: str, executor_type: str, fn: ExecuteFn):
        super().__init__(id=id)
        self._name = name
        self._executor_type = executor_type
        self._fn = fn

    @handler(input=dict, output=dict)
    async def process(self, input: dict, ctx: WorkflowContext) -> None:
        wid = input.get("workflow_id", "?")
        iid = input.get("instance_id")
        t0 = time.time()
        await emit(wid, iid, "executor.invoked", {
            "name": self._name, "type": self._executor_type, "stage": "start"
        })
        try:
            result = await self._fn(input)
        except Exception as ex:
            await emit(wid, iid, "executor.invoked", {
                "name": self._name, "type": self._executor_type, "stage": "error",
                "error": str(ex), "duration_ms": int((time.time() - t0) * 1000)
            })
            raise
        await emit(wid, iid, "executor.invoked", {
            "name": self._name, "type": self._executor_type, "stage": "complete",
            "duration_ms": int((time.time() - t0) * 1000)
        })
        # Merge input + result so downstream nodes have full context
        merged = {**input, **result}
        # If a validator failed, emit dedicated event
        if self._executor_type == "validator" and result.get("ok") is False:
            await emit(wid, iid, "validator.blocked", {
                "name": self._name, "reason": result.get("blocked_reason") or result.get("missing") or "validation failed"
            })
            # Still forward -- orchestration generator decides what to do with ok=False
        await ctx.send_message(merged)


class TerminalExecutor(Executor):
    """Final node in a graph: yields the accumulated dict as the workflow output."""

    def __init__(self, *, id: str = "terminal"):
        super().__init__(id=id)

    @handler(input=dict, workflow_output=dict)
    async def process(self, input: dict, ctx: WorkflowContext) -> None:
        await ctx.yield_output(input)
