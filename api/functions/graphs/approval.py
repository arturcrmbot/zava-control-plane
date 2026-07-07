# src/functions/graphs/approval.py
"""
Approval graph (deterministic):
  load_authority_policy -> apply_threshold_routing -> terminal

The `requires_hitl` flag in the output drives the orchestration generator (Phase 9)
to either proceed or pause via wait_for_external_event.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.deterministic import load_authority_policy, apply_threshold_routing


# apply_threshold_routing reads input["policy"] which is set by load_authority_policy.
# Our merge pattern wraps the policy dict under "policy" key explicitly.
async def wrap_policy(input: dict) -> dict:
    """Adapter: rename load_authority_policy output to nest under 'policy' key."""
    out = await load_authority_policy.execute(input)
    return {"policy": out}


def build_approval_workflow() -> Workflow:
    return build_linear_workflow([
        ("load_policy", "load_authority_policy", "deterministic", wrap_policy),
        ("threshold", "apply_threshold_routing", "deterministic", apply_threshold_routing.execute),
    ])
