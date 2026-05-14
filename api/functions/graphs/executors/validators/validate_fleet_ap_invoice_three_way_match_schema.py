"""Schema validator for the AP-invoice three-way-match phase output.

Confirms the deterministic match step produced the expected verdict
shape and that the invariants hold:
  - matched: bool
  - invoice_id: non-empty str
  - po_present, grn_present, amount_within_tolerance: bool
  - matched == (po_present AND grn_present AND amount_within_tolerance)
  - discrepancies: list (empty when matched=True)

Returns the payload back through under `three_way_match` so the persona
context block at the AP-clerk gate can read it directly.
"""
from __future__ import annotations


async def execute(input: dict) -> dict:
    payload = input or {}

    if payload.get("ok") is not True:
        return {
            "ok": False,
            "blocked_reason": payload.get("blocked_reason") or "three_way_match phase did not return ok=True",
            "three_way_match": payload,
        }

    matched = payload.get("matched")
    if not isinstance(matched, bool):
        return {
            "ok": False,
            "blocked_reason": f"matched must be bool; got {matched!r}",
            "three_way_match": payload,
        }

    invoice_id = payload.get("invoice_id")
    if not isinstance(invoice_id, str) or not invoice_id:
        return {
            "ok": False,
            "blocked_reason": "invoice_id must be a non-empty string",
            "three_way_match": payload,
        }

    for flag in ("po_present", "grn_present", "amount_within_tolerance"):
        if not isinstance(payload.get(flag), bool):
            return {
                "ok": False,
                "blocked_reason": f"{flag} must be bool; got {payload.get(flag)!r}",
                "three_way_match": payload,
            }

    derived = (
        payload["po_present"]
        and payload["grn_present"]
        and payload["amount_within_tolerance"]
    )
    if matched != derived:
        return {
            "ok": False,
            "blocked_reason": (
                f"matched={matched} disagrees with "
                f"po_present={payload['po_present']} AND "
                f"grn_present={payload['grn_present']} AND "
                f"amount_within_tolerance={payload['amount_within_tolerance']}"
            ),
            "three_way_match": payload,
        }

    discrepancies = payload.get("discrepancies")
    if not isinstance(discrepancies, list):
        return {
            "ok": False,
            "blocked_reason": "discrepancies must be a list",
            "three_way_match": payload,
        }
    if matched and discrepancies:
        return {
            "ok": False,
            "blocked_reason": "matched=True but discrepancies is non-empty",
            "three_way_match": payload,
        }

    return {
        "ok": True,
        "three_way_match": payload,
        "matched": matched,
    }
