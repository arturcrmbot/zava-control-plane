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
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_notification


def build_notify_workflow() -> Workflow:
    return build_linear_workflow([
        ("notification_composer", "agent_notification", "agent", agent_notification.execute),
    ])
