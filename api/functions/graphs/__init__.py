# src/functions/graphs/__init__.py
"""Per-phase MAF Workflow graph builders. Each returns a Workflow instance ready to
be invoked from the durable orchestration via `await workflow.run(input)`.

ExpenseClaim 7-phase flow: Intake -> Classify -> Validate Receipt -> Route ->
Notify -> Arbitrate -> Audit. Phase 7 (Audit) is still a stub.
"""
from .intake import build_intake_workflow
from .intake_expense import build_intake_expense_workflow
from .classify import build_classify_workflow
from .receipt import build_receipt_workflow
from .route import build_route_workflow
from .notify import build_notify_workflow
from .arbitrate import build_arbitrate_workflow
from .approval import build_approval_workflow


__all__ = [
    "build_intake_workflow",
    "build_intake_expense_workflow",
    "build_classify_workflow",
    "build_approval_workflow",
    "build_receipt_workflow",
    "build_route_workflow",
    "build_notify_workflow",
    "build_arbitrate_workflow",
]
