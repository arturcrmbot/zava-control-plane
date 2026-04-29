# api/server/services/exception_narrative.py
from __future__ import annotations
from api.shared.types import Workflow, Exception_ as Exception, ActionLedgerEntry


def _fmt_amount(amount: float, currency: str) -> str:
    return f"{currency} {amount:,.2f}"


def _agent_tried(ledger: list[ActionLedgerEntry], limit: int = 5) -> list[str]:
    """Prefer the most recent N agent-kind ledger actions, rendered as prose."""
    recent = [e for e in ledger if e.actor_kind == "agent"][-limit:]
    if not recent:
        return ["Orchestration started; no executor actions recorded yet."]
    bullets: list[str] = []
    for e in recent:
        if e.action.startswith("phase.completed:"):
            phase = e.action.split(":", 1)[1]
            bullets.append(f"{phase} phase completed")
        elif e.action == "validator.blocked":
            reason = e.details.get("reason", "validation failed")
            who = e.actor_id.replace("validator:", "")
            bullets.append(f"{who} rejected: {reason}")
        elif e.action == "suspended":
            bullets.append(
                f"Workflow suspended for HITL: "
                f"{e.details.get('reason', 'approval')}"
            )
        else:
            bullets.append(e.action)
    return bullets


def _describe_subject(workflow: Workflow) -> tuple[str, str]:
    """Return (subject_phrase, amount_str) tailored to the workflow type.

    Expense claims read from `workflow.claim`; invoices from `workflow.invoice`.
    """
    if workflow.type == "expense-claim" and workflow.claim:
        c = workflow.claim
        amount_str = _fmt_amount(c.amount, c.currency)
        subject = (
            f"Expense claim {c.claim_id} from {c.employee_id} "
            f"({c.category}, {c.vendor})"
        )
        return subject, amount_str
    if workflow.type == "hiring":
        amount_str = ""
        subject = f"Hiring workflow {workflow.id}"
        return subject, amount_str
    inv = workflow.invoice
    vendor = workflow.vendor.name if workflow.vendor else "<unknown vendor>"
    if inv:
        amount_str = _fmt_amount(inv.amount, inv.currency)
        subject = f"Invoice {inv.number} for {vendor}"
    else:
        amount_str = ""
        subject = f"Workflow {workflow.id} for {vendor}"
    return subject, amount_str


def compose(workflow: Workflow, exception: Exception,
            ledger: list[ActionLedgerEntry]) -> dict:
    phase = workflow.current_phase
    subject, amount_str = _describe_subject(workflow)
    money = f" ({amount_str})" if amount_str else ""

    if exception.category == "validator-blocked":
        what_happened = (
            f"{subject}{money} blocked at {phase}: {exception.summary}."
        )
    elif exception.category == "threshold-exceeded":
        what_happened = (
            f"{subject}{money} requires human approval at {phase}: "
            f"{exception.summary}."
        )
    else:
        what_happened = (
            f"{subject}{money} exception raised at {phase}: "
            f"{exception.summary}."
        )

    return {
        "whatHappened": what_happened,
        "whatAgentTried": _agent_tried(ledger),
        "agentRecommendation": exception.recommendation or
            "Review exception and select an Intervention Protocol.",
    }
