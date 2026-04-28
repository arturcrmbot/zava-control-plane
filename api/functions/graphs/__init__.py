# src/functions/graphs/__init__.py
"""Per-phase MAF Workflow graph builders. Each returns a Workflow instance ready to
be invoked from the durable orchestration via `await workflow.run(input)`.

Week 2 pivot: the active 7-phase ExpenseClaim flow is being wired progressively.
Phase 1 (Intake) and Phase 2 (Classify) ship in Day 6; Phases 3, 4, 5 follow on
Days 7, 9, 10.
"""
from .intake import build_intake_workflow
from .intake_expense import build_intake_expense_workflow
from .approval import build_approval_workflow


def build_receipt_workflow():
    raise NotImplementedError("Phase 3 (Validate Receipt) — Day 7")


def build_route_workflow():
    raise NotImplementedError("Phase 4 (Route by Verdict) — Day 9")


def build_notify_workflow():
    raise NotImplementedError("Phase 5 (Notify) — Day 10")


__all__ = [
    "build_intake_workflow",
    "build_intake_expense_workflow",
    "build_approval_workflow",
    "build_receipt_workflow",
    "build_route_workflow",
    "build_notify_workflow",
]
