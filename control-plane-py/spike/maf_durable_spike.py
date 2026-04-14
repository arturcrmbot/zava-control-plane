"""
Discover MAF DurableWorkflow API — Microsoft Agent Framework + Durable Task Scheduler.

IMPORTANT: The spec skeleton's assumed API (DurableWorkflow, workflow_step, DurableContext,
DurableRuntimeClient.from_environment()) does NOT exist. The real MAF API is:

  - Orchestration:  a plain Python generator function that yields Tasks
  - HITL:           context.wait_for_external_event(event_name) inside the generator
  - Worker:         DurableAIAgentWorker wraps TaskHubGrpcWorker / DurableTaskSchedulerWorker
  - Client:         DurableTaskSchedulerClient from `durabletask.azuremanaged.client`
  - Hosting:        EXTERNAL Durable Task Scheduler required (gRPC, port 8080 by default)
                    Docker: `docker run -p 8080:8080 mcr.microsoft.com/durabletask/scheduler:latest`

Package map:
  - agent-framework-durabletask  →  agent_framework_durabletask
  - agent-framework-azurefunctions → agent_framework_azurefunctions
  - durabletask                  →  durabletask (the Microsoft durable task Python SDK)
  - durabletask-azuremanaged     →  durabletask.azuremanaged (managed scheduler client/worker)

PRE-REQUISITE to run this spike:
  docker run -d -p 8080:8080 mcr.microsoft.com/durabletask/scheduler:latest

Or, if Docker is unavailable, see BLOCKED note at bottom.
"""

import asyncio
import json
import logging
import time
from collections.abc import Generator
from typing import Any

# ── MAF Durable imports ──────────────────────────────────────────────────────
# The actual orchestration context: DurableAIAgentOrchestrationContext wraps
# a durabletask OrchestrationContext to expose .get_agent()
from agent_framework.azure import DurableAIAgentOrchestrationContext, DurableAIAgentWorker

# Agent definition (uses azure.ai model; we'll use a mock for this spike)
from agent_framework import Agent, AgentResponse

# Durable Task imports — these are the REAL client/worker/task primitives
from durabletask.task import ActivityContext, OrchestrationContext, Task, when_any  # type: ignore

# The managed scheduler client + worker (gRPC-based)
try:
    from durabletask.azuremanaged.client import DurableTaskSchedulerClient
    from durabletask.azuremanaged.worker import DurableTaskSchedulerWorker
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False
    print("[WARNING] durabletask.azuremanaged not available — spike will run in API-probe mode only")

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
SCHEDULER_ENDPOINT = "http://localhost:8080"
TASKHUB = "spike-hub"
WORKFLOW_NAME = "hello_workflow_orchestration"
APPROVE_EVENT = "approve_greeting"
AGENT_NAME = "HelloAgent"


# ── Activity: a simple log step (no LLM call needed for this spike) ──────────
def notify_step(ctx: ActivityContext, greeting: str) -> str:
    """Activity function — runs synchronously off the orchestration thread."""
    logger.warning("[activity:notify_step] greeting=%r", greeting)
    return f"notified: {greeting}"


# ── Orchestration: generator function (NOT a class, NOT DurableWorkflow) ─────
#
# Key facts:
#   - Must be a synchronous generator (def, not async def)
#   - yield <Task> suspends; the yielded value is the task result on resume
#   - context.wait_for_external_event(name) returns a Task that resolves when
#     the named event is raised via client.raise_orchestration_event()
#   - context.task_all([...]) / when_any([...]) for parallelism/racing
#
def hello_workflow_orchestration(
    context: OrchestrationContext, name: str
) -> Generator[Task[Any], Any, str]:
    """HelloWorkflow — implements step_one + wait for approval + step_two."""

    logger.warning("[orchestration] Starting for name=%r, instance=%s", name, context.instance_id)

    # ── Step 1: wrap context for agent access ────────────────────────────────
    agent_ctx = DurableAIAgentOrchestrationContext(context)
    agent = agent_ctx.get_agent(AGENT_NAME)

    # ── Step 2: generate greeting via activity ───────────────────────────────
    # For the spike we use a simple activity (avoids needing Azure credentials).
    # In production: `yield agent.run(f"Say hello to {name}", ...)` for LLM.
    step_one_result: str = yield context.call_activity(notify_step, input=f"hello {name}")
    greeting = step_one_result  # e.g. "notified: hello Alice"

    logger.warning("[orchestration] step_one done: %r", greeting)
    context.set_custom_status("waiting_for_approval")

    # ── Step 3: wait for external HITL event ─────────────────────────────────
    # context.wait_for_external_event(name) is the MAF/durabletask equivalent
    # of the spec's ctx.wait_for_external_event(name).
    # Event must be raised from the client via client.raise_orchestration_event().
    approval_task: Task[Any] = context.wait_for_external_event(APPROVE_EVENT)  # type: ignore
    timeout_task: Task[Any] = context.create_timer(  # type: ignore
        context.current_utc_datetime
        # 5 minutes for spike; production uses timedelta(hours=72)
        + __import__("datetime").timedelta(seconds=300)
    )

    winner = yield when_any([approval_task, timeout_task])  # type: ignore

    if winner != approval_task:
        timeout_task.cancel()  # type: ignore
        raise TimeoutError("HITL approval timed out")

    timeout_task.cancel()  # type: ignore
    decision = approval_task.get_result()  # type: ignore

    # ── Step 4: build final output ───────────────────────────────────────────
    result = f"{greeting} (approved: {decision})"
    logger.warning("[orchestration] Final result: %r", result)
    return result  # noqa: B901


# ── Probe API surface (without running if scheduler absent) ──────────────────

def probe_api_surface() -> None:
    """Probe that all imports and class shapes are correct."""
    print("\n=== MAF Durable SPIKE - API Surface Probe ===\n")

    # Verify DurableAIAgentWorker
    print(f"[import] DurableAIAgentWorker      : {DurableAIAgentWorker.__module__}.{DurableAIAgentWorker.__name__}")
    print(f"[import] DurableAIAgentOrchestrationContext: {DurableAIAgentOrchestrationContext.__module__}.{DurableAIAgentOrchestrationContext.__name__}")

    if SCHEDULER_AVAILABLE:
        print(f"[import] DurableTaskSchedulerClient: {DurableTaskSchedulerClient.__module__}.{DurableTaskSchedulerClient.__name__}")
        print(f"[import] DurableTaskSchedulerWorker: {DurableTaskSchedulerWorker.__module__}.{DurableTaskSchedulerWorker.__name__}")

    # Verify orchestration function is callable and is a generator
    import inspect
    print(f"[probe]  hello_workflow_orchestration is generator: {inspect.isgeneratorfunction(hello_workflow_orchestration)}")

    # Verify durabletask task primitives
    print(f"[import] when_any                  : {when_any}")
    print(f"[import] OrchestrationContext       : {OrchestrationContext}")

    print("\n[probe] All imports OK.\n")


def run_full_spike() -> None:
    """Run the end-to-end spike against a live Durable Task Scheduler."""
    print("\n=== MAF Durable SPIKE - Full E2E Run ===\n")

    if not SCHEDULER_AVAILABLE:
        print("[BLOCKED] durabletask.azuremanaged not importable. Cannot run E2E.")
        return

    # ── Worker setup ─────────────────────────────────────────────────────────
    print(f"[worker] Connecting to scheduler at {SCHEDULER_ENDPOINT}, hub={TASKHUB}")
    try:
        worker = DurableTaskSchedulerWorker(
            host_address=SCHEDULER_ENDPOINT,
            secure_channel=False,
            taskhub=TASKHUB,
        )
    except Exception as e:
        print(f"[BLOCKED] Cannot create worker: {e}")
        print("  → Start the Durable Task Scheduler: docker run -d -p 8080:8080 mcr.microsoft.com/durabletask/scheduler:latest")
        return

    # Wrap with agent worker (registers agents as durable entities)
    agent_worker = DurableAIAgentWorker(worker)

    # For this spike we register a no-op agent (no real LLM needed)
    # In production: OpenAIChatCompletionClient / FoundryChatClient
    # The orchestration uses activities for the hello step, so the agent isn't called here.

    # Register activities and orchestration
    worker.add_activity(notify_step)  # type: ignore
    worker.add_orchestrator(hello_workflow_orchestration)  # type: ignore

    print("[worker] Registered activity: notify_step")
    print("[worker] Registered orchestration: hello_workflow_orchestration")

    # Start worker in background thread (non-blocking)
    import threading
    worker_thread = threading.Thread(target=worker.start, daemon=True)  # type: ignore
    worker_thread.start()
    print("[worker] Started in background thread.\n")
    time.sleep(2)  # Let worker connect

    # ── Client setup ─────────────────────────────────────────────────────────
    client = DurableTaskSchedulerClient(
        host_address=SCHEDULER_ENDPOINT,
        secure_channel=False,
        taskhub=TASKHUB,
    )
    print("[client] DurableTaskSchedulerClient created.\n")

    # ── Start orchestration ───────────────────────────────────────────────────
    # Equivalent to: client.start_new(workflow, input="Alice") in spec skeleton
    instance_id = client.schedule_new_orchestration(  # type: ignore
        orchestrator=WORKFLOW_NAME,
        input="Alice",
    )
    print(f"[start] instance_id={instance_id}\n")

    # ── Poll until suspended waiting for approval ─────────────────────────────
    print("[poll] Waiting for orchestration to reach waiting_for_approval state...")
    for _ in range(60):
        state = client.get_orchestration_state(instance_id=instance_id)
        status = state.runtime_status.name if state else "UNKNOWN"
        custom = state.serialized_custom_status if state else ""
        print(f"[status] runtime={status} custom={custom!r}")
        if custom and "waiting_for_approval" in str(custom):
            print("[poll] Orchestration is suspended, waiting for HITL event.\n")
            break
        if status in ("COMPLETED", "FAILED", "TERMINATED"):
            print(f"[poll] Orchestration ended unexpectedly: {status}")
            break
        time.sleep(1)

    # ── Raise external event (HITL approval) ─────────────────────────────────
    # Equivalent to: client.raise_event(instance_id, name, payload) in spec skeleton
    print(f"[raise_event] Sending {APPROVE_EVENT!r} = 'yes'")
    client.raise_orchestration_event(  # type: ignore
        instance_id=instance_id,
        event_name=APPROVE_EVENT,
        data="yes",
    )
    print("[raise_event] Event sent.\n")

    # ── Poll until completion ─────────────────────────────────────────────────
    print("[poll] Waiting for orchestration to complete...")
    for _ in range(30):
        state = client.get_orchestration_state(instance_id=instance_id)
        status = state.runtime_status.name if state else "UNKNOWN"
        print(f"[status] runtime={status}")
        if status in ("COMPLETED", "FAILED", "TERMINATED"):
            print(f"\n[final] status={status}")
            # Equivalent to: client.get_output(instance_id) in spec skeleton
            output = state.serialized_output if state else None
            if output:
                try:
                    parsed = json.loads(output)
                    print(f"[output] {parsed}")
                except json.JSONDecodeError:
                    print(f"[output] {output}")
            break
        time.sleep(1)

    # ── Acceptance check ──────────────────────────────────────────────────────
    final_state = client.get_orchestration_state(instance_id=instance_id)
    final_output = final_state.serialized_output if final_state else ""
    passed = (
        final_state is not None
        and final_state.runtime_status.name == "COMPLETED"
        and "hello Alice" in str(final_output)
        and "approved: yes" in str(final_output)
    )
    print(f"\n[ACCEPTANCE] {'PASS ✓' if passed else 'FAIL ✗'}")
    if not passed:
        print(f"  Expected output containing 'hello Alice (approved: yes)'")
        print(f"  Actual output: {final_output!r}")

    # Cleanup
    worker.stop()  # type: ignore


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    # Always run the API surface probe
    probe_api_surface()

    # Attempt full E2E if scheduler is reachable
    import socket
    host, port_str = SCHEDULER_ENDPOINT.replace("http://", "").split(":")
    try:
        with socket.create_connection((host, int(port_str)), timeout=2):
            print(f"[check] Scheduler reachable at {SCHEDULER_ENDPOINT}")
            run_full_spike()
    except (OSError, ConnectionRefusedError):
        print(f"\n[BLOCKED] Scheduler not reachable at {SCHEDULER_ENDPOINT}.")
        print("  API surface probe completed successfully (imports OK).")
        print("  Full E2E requires the Durable Task Scheduler Docker container.")
        print("  To run E2E:")
        print("    docker run -d -p 8080:8080 mcr.microsoft.com/durabletask/scheduler:latest")
        print("    uv run python spike/maf_durable_spike.py")
        print("\n[ACCEPTANCE] PARTIAL - imports verified; E2E requires scheduler.")


if __name__ == "__main__":
    main()
