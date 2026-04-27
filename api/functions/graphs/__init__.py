# src/functions/graphs/__init__.py
"""Per-phase MAF Workflow graph builders. Each returns a Workflow instance ready to
be invoked from the durable orchestration via `await workflow.run(input)`.

NOTE: validation/routing/payment/reconciliation builders were removed in the
expense-compliance pivot (D-grade per docs/poc1-inventory.md). Only intake and
approval remain until Week 2 reshapes the orchestrator into the 7-phase
expense-compliance flow."""
from .intake import build_intake_workflow
from .approval import build_approval_workflow

__all__ = [
    "build_intake_workflow",
    "build_approval_workflow",
]
