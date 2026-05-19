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
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from api.functions.webhook import emit


ExecuteFn = Callable[[dict], Awaitable[dict]]

_tracer = trace.get_tracer("zava.graphs.executor")


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
        phase = input.get("phase")
        t0 = time.time()
        await emit(wid, iid, "executor.invoked", {
            "name": self._name, "type": self._executor_type, "stage": "start"
        })
        with _tracer.start_as_current_span(f"executor.{self._name}") as span:
            span.set_attribute("zava.workflow.id", str(wid))
            if iid is not None:
                span.set_attribute("zava.workflow.instance_id", str(iid))
            if phase is not None:
                span.set_attribute("zava.workflow.phase", str(phase))
            span.set_attribute("zava.executor.type", self._executor_type)
            span.set_attribute("zava.executor.name", self._name)
            if self._executor_type == "agent":
                # Each executor name corresponds to a skill, which is its
                # own agent in the AGT design. Tag the span with the
                # executor name so audit/Foundry can attribute by agent.
                span.set_attribute("gen_ai.agent.name", self._name)

            try:
                result = await self._fn(input)
            except Exception as ex:
                span.record_exception(ex)
                span.set_status(Status(StatusCode.ERROR, str(ex)))
                await emit(wid, iid, "executor.invoked", {
                    "name": self._name, "type": self._executor_type, "stage": "error",
                    "error": str(ex), "duration_ms": int((time.time() - t0) * 1000)
                })
                raise

            if self._executor_type == "validator" and result.get("ok") is False:
                reason = result.get("blocked_reason") or result.get("missing") or "validation failed"
                span.set_status(Status(StatusCode.ERROR, str(reason)))
                span.add_event("validator.blocked", {"reason": str(reason)})

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
