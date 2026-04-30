"""Adaptive Card composer + sender for the Finance BP HITL surface (§4.6).

Track B-flavour: Phase 1 (Budget) calls `compose_finance_bp_card(...)` to build
an Adaptive Card payload representing the budget-approval ask. The card is
posted via the Microsoft Graph mock (`graph-mcp`) to the Finance BP's email;
their click/decision posts back to the orchestrator via the FastAPI
`/api/webhooks/finance-bp/{workflow_id}` route, which raises the
`budget_approval` external event on the Durable instance.

The LLM never participates in the *send* — composition happens here, the send
is gated by an `onPreToolUse` hook in the runtime, and the response path is a
simple webhook. That preserves the §4.13 non-revocable-send invariant.

Local demo uses canned card payloads; a real implementation would use the
official AdaptiveCard schema and the Microsoft Teams app SDK.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal


@dataclass
class FinanceBpCard:
    workflow_id: str
    role: str
    cost_centre: str
    envelope_remaining_gbp: int
    delta_vs_midpoint_gbp: int
    severity: Literal["delegation_threshold", "out_of_envelope"]


def compose_finance_bp_card(
    *,
    workflow_id: str,
    role: str,
    cost_centre: str,
    envelope_remaining_gbp: int,
    delta_vs_midpoint_gbp: int,
    out_of_envelope: bool,
) -> dict:
    """Return a Finance-BP-flavoured Adaptive Card payload (Microsoft schema).

    Returns a payload dict ready to POST to `graph_mcp.graph_mail`. The
    `actions` block contains two buttons whose URLs hit the FastAPI webhook,
    which raises the `budget_approval` external event on the Durable instance.
    """
    severity: Literal["delegation_threshold", "out_of_envelope"] = (
        "out_of_envelope" if out_of_envelope else "delegation_threshold"
    )
    title = "Budget approval needed — out of envelope" if out_of_envelope else "Budget approval — over £10k delegation"
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "wpp": {
            "workflow_id": workflow_id,
            "card_kind": "finance_bp_budget",
            "severity": severity,
        },
        "body": [
            {"type": "TextBlock", "size": "Large", "weight": "Bolder", "text": title},
            {"type": "TextBlock", "text": f"Role: {role}"},
            {"type": "TextBlock", "text": f"Cost centre: {cost_centre}"},
            {"type": "FactSet", "facts": [
                {"title": "Envelope remaining", "value": f"£{envelope_remaining_gbp:,}"},
                {"title": "Δ vs band midpoint", "value": f"£{delta_vs_midpoint_gbp:+,}"},
            ]},
        ],
        "actions": [
            {"type": "Action.Http",
             "title": "Approve",
             "method": "POST",
             "url": f"/api/webhooks/finance-bp/{workflow_id}?decision=approve"},
            {"type": "Action.Http",
             "title": "Reject",
             "method": "POST",
             "url": f"/api/webhooks/finance-bp/{workflow_id}?decision=reject"},
            {"type": "Action.Http",
             "title": "Request more info",
             "method": "POST",
             "url": f"/api/webhooks/finance-bp/{workflow_id}?decision=needs_info"},
        ],
    }
