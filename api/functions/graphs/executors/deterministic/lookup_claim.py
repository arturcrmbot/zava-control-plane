"""Phase 1a: lookup_claim — fetch from EMS (or normalise the already-fetched record).

Two ways this is called:
  1. The orchestrator/simulator already passed `input["claim"]` (full record) — we
     skip the network hop and just normalise field names.
  2. Only `input["claim_id"]` is present — call the claim.lookup MCP tool to
     fetch the record from the appropriate EMS mock (Workday today, Concur Day 8).

Output shape:
  - `claim_record`: the looked-up / normalised claim record
  - `raw_text` / `structure`: a synthesised OCR-style payload so the downstream
    `doc_intelligence_extract` and `agent_field_extractor` (invoice-shaped stubs)
    receive the same shape they always did.
"""
from __future__ import annotations
import json

from api.server.mcp_tools import claim_lookup


def _claim_to_raw_text(claim: dict) -> str:
    return (
        f"CLAIM {claim.get('claim_id')} "
        f"AMOUNT {claim.get('amount')} {claim.get('currency')} "
        f"CATEGORY {claim.get('category')} VENDOR {claim.get('vendor')}"
    )


def _claim_to_structure(claim: dict) -> dict:
    return {
        "claim_id": claim.get("claim_id"),
        "amount": claim.get("amount"),
        "currency": claim.get("currency"),
        "category": claim.get("category"),
        "market": claim.get("market"),
        "vendor": claim.get("vendor"),
        "attendees": claim.get("attendees"),
        "receipt_filename": claim.get("receipt_filename"),
        "ems_source": claim.get("ems_source"),
    }


async def execute(input: dict) -> dict:
    claim = input.get("claim")
    if not claim:
        claim_id = input.get("claim_id")
        if not claim_id:
            return {"claim_record": None, "raw_text": "", "structure": {}}
        ems_source = input.get("ems_source")
        claim = claim_lookup.lookup(claim_id, ems_source=ems_source)

    return {
        "claim_record": claim,
        "raw_text": _claim_to_raw_text(claim),
        "structure": _claim_to_structure(claim),
        "claim_payload": json.dumps(claim, default=str),
    }
