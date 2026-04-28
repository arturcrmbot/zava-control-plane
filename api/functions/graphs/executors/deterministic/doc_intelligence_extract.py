# src/functions/graphs/executors/deterministic/doc_intelligence_extract.py
"""Stub for Azure Document Intelligence.

Two input shapes are handled:
  - Expense (Week 2 default): upstream `lookup_claim` already wrote `raw_text`
    and `structure` — we surface them as-is so the next agent receives the
    canonical shape.
  - Invoice (legacy): `input["invoice"]` + `input["vendor"]` — synthesise the
    OCR-style payload from those fields.
"""
from __future__ import annotations


async def execute(input: dict) -> dict:
    if "structure" in input or "raw_text" in input:
        return {
            "raw_text": input.get("raw_text", ""),
            "structure": input.get("structure", {}),
        }
    invoice = input["invoice"]
    return {
        "raw_text": f"INVOICE {invoice['number']} FROM {input['vendor']['name']} TOTAL {invoice['amount']}",
        "structure": {
            "vendor_id": input["vendor"]["id"],
            "amount": invoice["amount"],
            "po_ref": invoice["po_ref"],
            "currency": invoice["currency"],
            "line_items": invoice.get("line_items", []),
        },
    }
