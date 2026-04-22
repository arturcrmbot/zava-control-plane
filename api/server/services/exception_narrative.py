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


def compose(workflow: Workflow, exception: Exception,
            ledger: list[ActionLedgerEntry]) -> dict:
    inv = workflow.invoice
    phase = workflow.current_phase
    amount_str = _fmt_amount(inv.amount, inv.currency)
    vendor = workflow.vendor.name

    if exception.category == "validator-blocked":
        what_happened = (
            f"Invoice {inv.number} for {vendor} ({amount_str}) blocked at "
            f"{phase}: {exception.summary}."
        )
    elif exception.category == "threshold-exceeded":
        what_happened = (
            f"Invoice {inv.number} for {vendor} ({amount_str}) requires "
            f"human approval at {phase}: {exception.summary}."
        )
    else:
        what_happened = (
            f"Invoice {inv.number} for {vendor} ({amount_str}) exception "
            f"raised at {phase}: {exception.summary}."
        )

    return {
        "whatHappened": what_happened,
        "whatAgentTried": _agent_tried(ledger),
        "agentRecommendation": exception.recommendation or
            "Review exception and select an Intervention Protocol.",
    }
