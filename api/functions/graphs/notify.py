# src/functions/graphs/notify.py
"""Phase 5 (Notify) graph for expense claims.

  agent_notification -> terminal

Per spec §4.1 Phase 5: only runs on Red verdicts. Composes the Adaptive
Card + email body via the notification-composer skill, emits a
`notification.sent` FleetEvent, and returns. The orchestrator then enters
its `wait_for_external_event:justification` HITL gate (already wired in
expense_claim.py).
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_notification


def build_notify_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="notification_composer",
        name="agent_notification",
        executor_type="agent",
        fn=agent_notification.execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, term)
        .build()
    )
