# src/functions/graphs/executors/deterministic/doc_intelligence_extract.py
from __future__ import annotations


async def execute(input: dict) -> dict:
    """Stub: in production this calls Azure Document Intelligence. Here, return the seed
    invoice payload as if it had been OCR'd."""
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
