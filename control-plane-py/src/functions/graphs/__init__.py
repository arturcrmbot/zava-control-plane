# src/functions/graphs/__init__.py
"""Per-phase MAF Workflow graph builders. Each returns a Workflow instance ready to
be invoked from the durable orchestration via `await workflow.run(input)`."""
from .intake import build_intake_workflow
from .validation import build_validation_workflow
from .routing import build_routing_workflow
from .approval import build_approval_workflow
from .payment import build_payment_workflow
from .reconciliation import build_reconciliation_workflow

__all__ = [
    "build_intake_workflow",
    "build_validation_workflow",
    "build_routing_workflow",
    "build_approval_workflow",
    "build_payment_workflow",
    "build_reconciliation_workflow",
]
