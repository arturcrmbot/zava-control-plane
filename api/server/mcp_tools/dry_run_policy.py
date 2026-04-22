# src/server/mcp_tools/dry_run_policy.py
from __future__ import annotations
import json
import time
from typing import Any
from pydantic import BaseModel, Field
from copilot.tools import define_tool, ToolInvocation, ToolResult
from api.server.services.state_store import StateStore
from ._otel import traced_tool


class DryRunPolicyParams(BaseModel):
    policy_id: str
    proposed_value: float | str | bool
    scope_days: int = 7


def dry_run_policy_impl(store: StateStore, policy_id: str, proposed_value: Any, scope_days: int = 7) -> dict:
    """Pure logic — also called from the /api/policy/dry-run route."""
    cutoff = time.time() - scope_days * 86400
    completed = [w for w in store.list_workflows() if w.status == "completed" and w.created_at >= cutoff]
    would_be_different = 0
    impacted = []
    if policy_id == "invoice-p2p.approval.auto_threshold":
        threshold = float(proposed_value)
        for w in completed:
            if w.invoice.amount <= threshold:
                would_be_different += 1
                impacted.append(w.id)
    return {
        "scope_days": scope_days,
        "total_evaluated": len(completed),
        "would_be_different": would_be_different,
        "impacted_workflow_ids": impacted[:20],
    }


def make_dry_run_policy_tool(store: StateStore):
    @define_tool(description="Simulate a policy value change against completed workflows.", skip_permission=True)
    @traced_tool("dry_run_policy")
    def dry_run_policy(params: DryRunPolicyParams, invocation: ToolInvocation) -> ToolResult:
        result = dry_run_policy_impl(store, params.policy_id, params.proposed_value, params.scope_days)
        return ToolResult(text_result_for_llm=json.dumps(result), result_type="success")

    return dry_run_policy
