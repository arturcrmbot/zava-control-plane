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
    """Pure logic — also called from the /api/policy/dry-run route.

    For expense-claim policies, the simulation evaluates against ALL recent
    expense workflows (in-flight + completed) so the demo doesn't require
    waiting for full pipeline completion before showing impact.
    """
    cutoff = time.time() - scope_days * 86400
    workflows = [w for w in store.list_workflows() if w.created_at >= cutoff]
    expense = [w for w in workflows if w.type == "expense-claim" and w.claim is not None]
    completed_invoices = [w for w in workflows if w.status == "completed" and w.invoice is not None]

    would_be_different = 0
    impacted: list[str] = []

    if policy_id == "invoice-p2p.approval.auto_threshold":
        threshold = float(proposed_value)
        for w in completed_invoices:
            if w.invoice.amount <= threshold:
                would_be_different += 1
                impacted.append(w.id)
        return {
            "scopeDays": scope_days,
            "totalEvaluated": len(completed_invoices),
            "wouldBeDifferent": would_be_different,
            "impactedWorkflowIds": impacted[:20],
        }

    if policy_id == "expense.routing.amber_to_reviewer_threshold_usd":
        # Currently amber claims above this USD-equivalent route to reviewer.
        # New threshold flips routing for amber claims whose amount crosses it.
        threshold = float(proposed_value)
        # crude USD-equivalent (demo): use claim amount directly when USD; small
        # multipliers for other currencies (rough).
        fx = {"USD": 1.0, "GBP": 1.27, "EUR": 1.08, "INR": 0.012}
        for w in expense:
            usd = w.claim.amount * fx.get(w.claim.currency, 1.0)
            # we don't have stored verdicts on every claim; treat any claim
            # whose USD amount sits in the 50-USD band around the new
            # threshold as "would have routed differently".
            if (usd > threshold and usd <= threshold + 200) or (usd <= threshold and usd > threshold - 200):
                would_be_different += 1
                impacted.append(w.id)
        return {
            "scopeDays": scope_days,
            "totalEvaluated": len(expense),
            "wouldBeDifferent": would_be_different,
            "impactedWorkflowIds": impacted[:20],
        }

    if policy_id == "expense.policy.meal_per_attendee_limit_usd":
        cap = float(proposed_value)
        for w in expense:
            if w.claim.category == "meals" and w.claim.attendees > 0:
                per_head = w.claim.amount / w.claim.attendees
                if per_head > cap:
                    would_be_different += 1
                    impacted.append(w.id)
        return {
            "scopeDays": scope_days,
            "totalEvaluated": len([w for w in expense if w.claim.category == "meals"]),
            "wouldBeDifferent": would_be_different,
            "impactedWorkflowIds": impacted[:20],
        }

    if policy_id == "expense.classifier.confidence_floor":
        # We don't store classifier confidence per claim; demo-grade heuristic:
        # for floor 0.7 → 0.9 the count of claims that would flip from green
        # to amber roughly scales with the gap from current floor (0.78).
        try:
            floor = float(proposed_value)
            current = 0.78
            delta = max(0.0, floor - current)
            estimate = int(len(expense) * delta * 1.2)
            return {
                "scopeDays": scope_days,
                "totalEvaluated": len(expense),
                "wouldBeDifferent": min(estimate, len(expense)),
                "impactedWorkflowIds": [w.id for w in expense[:min(estimate, 20)]],
            }
        except (TypeError, ValueError):
            pass

    # Default: structural fallback — no behavioural change estimated.
    return {
        "scopeDays": scope_days,
        "totalEvaluated": len(expense) + len(completed_invoices),
        "wouldBeDifferent": 0,
        "impactedWorkflowIds": [],
    }


def make_dry_run_policy_tool(store: StateStore):
    @define_tool(description="Simulate a policy value change against completed workflows.", skip_permission=True)
    @traced_tool("dry_run_policy")
    def dry_run_policy(params: DryRunPolicyParams, invocation: ToolInvocation) -> ToolResult:
        result = dry_run_policy_impl(store, params.policy_id, params.proposed_value, params.scope_days)
        return ToolResult(text_result_for_llm=json.dumps(result), result_type="success")

    return dry_run_policy
