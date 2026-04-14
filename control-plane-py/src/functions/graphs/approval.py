# src/functions/graphs/approval.py
"""
Approval graph (deterministic):
  load_authority_policy -> apply_threshold_routing -> terminal

The `requires_hitl` flag in the output drives the orchestration generator (Phase 9)
to either proceed or pause via wait_for_external_event.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from src.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from src.functions.graphs.executors.deterministic import load_authority_policy, apply_threshold_routing


# apply_threshold_routing reads input["policy"] which is set by load_authority_policy.
# Our merge pattern wraps the policy dict under "policy" key explicitly.
async def wrap_policy(input: dict) -> dict:
    """Adapter: rename load_authority_policy output to nest under 'policy' key."""
    out = await load_authority_policy.execute(input)
    return {"policy": out}


def build_approval_workflow() -> Workflow:
    n1 = TrackedExecutor(id="load_policy", name="load_authority_policy",
                         executor_type="deterministic", fn=wrap_policy)
    n2 = TrackedExecutor(id="threshold", name="apply_threshold_routing",
                         executor_type="deterministic", fn=apply_threshold_routing.execute)
    term = TerminalExecutor(id="terminal")
    return WorkflowBuilder(start_executor=n1).add_edge(n1, n2).add_edge(n2, term).build()
