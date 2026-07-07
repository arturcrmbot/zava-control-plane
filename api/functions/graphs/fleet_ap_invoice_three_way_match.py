"""Phase 2 (Three-Way Match) graph for AP invoice domain.

  deterministic_three_way_match -> validator -> terminal

Confirms the invoice has a matching PO and goods-receipt note (GRN), and
that all three values agree within tolerance. Outputs a `three_way_match`
verdict block the persona reads at the AP-clerk gate.

Phase intentionally non-agentic for the lab build — three-way match is
deterministic by definition. The full LLM pipeline graduation happens in
the engagement POC where line-item-level reasoning matters.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.validators import validate_fleet_ap_invoice_three_way_match_schema
from api.server.mcp_tools.invoice_repository import find_three_way_match


async def _three_way_match_execute(input: dict) -> dict:
    """Deterministic three-way match using the invoice_repository stub.

    Reads `invoice.invoice_id` (and optional `invoice.po_id`) from the
    orchestrator payload, plus the workflow-level `scenario` and
    `invoice.amount_gbp` so the seed corpus's scenario tag fully
    determines the verdict (matched-clean → matched, missing-po → not
    matched, etc.). Returns the structured verdict the validator +
    persona consume.
    """
    invoice = input.get("invoice") or {}
    invoice_id = invoice.get("invoice_id")
    if not invoice_id:
        return {"ok": False, "blocked_reason": "missing invoice.invoice_id"}
    po_id = invoice.get("po_id")  # may be null when scenario=missing-po
    scenario = input.get("scenario") or invoice.get("scenario")
    amount_gbp = invoice.get("amount_gbp") or invoice.get("amount")
    verdict = find_three_way_match(
        invoice_id,
        po_id=po_id,
        scenario=scenario,
        invoice_amount_gbp=amount_gbp,
    )
    # Re-key into the shape the validator expects.
    return {
        "ok": True,
        **verdict,
    }


def build_fleet_ap_invoice_three_way_match_workflow() -> Workflow:
    return build_linear_workflow([
        ("three_way_match", "deterministic_three_way_match", "deterministic", _three_way_match_execute),
        ("val_three_way_match", "validate_three_way_match_schema", "validator", validate_fleet_ap_invoice_three_way_match_schema.execute),
    ])
