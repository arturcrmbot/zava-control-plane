"""Phase 1 (Invoice Lookup) graph for AP invoice domain.

  deterministic_invoice_lookup -> terminal

Per-spec: read the invoice record (vendor, amount_gbp, gl_code, cost_centre,
due_date) from the invoice repository. Pass forward. No agent, no validator —
just a deterministic call producing the canonical phase output shape so
downstream phases can read the invoice's amount + category from a single dict.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.server.mcp_tools.invoice_repository import get_invoice


async def _invoice_lookup_execute(input: dict) -> dict:
    """Deterministic invoice lookup. Reads `invoice.invoice_id` from the
    orchestrator payload, calls the invoice_repository MCP tool directly
    (no agent session — pure I/O), returns the structured record."""
    invoice = input.get("invoice") or {}
    invoice_id = invoice.get("invoice_id")
    if not invoice_id:
        return {"ok": False, "blocked_reason": "missing invoice.invoice_id"}
    record = get_invoice(invoice_id)
    return {
        "ok": True,
        "invoice_id": record["invoice_id"],
        "vendor": record["vendor"],
        "amount_gbp": record["amount_gbp"],
        "currency": record["currency"],
        "gl_code": record["gl_code"],
        "gl_category": record["gl_category"],
        "cost_centre": record["cost_centre"],
        "received_date": record["received_date"],
        "due_date": record["due_date"],
    }


def build_fleet_ap_invoice_invoice_lookup_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="invoice_lookup",
        name="deterministic_invoice_lookup",
        executor_type="deterministic",
        fn=_invoice_lookup_execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, term)
        .build()
    )
