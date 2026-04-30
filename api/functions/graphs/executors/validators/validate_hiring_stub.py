# src/functions/graphs/executors/validators/validate_hiring_stub.py
"""Placeholder validator for the POC2 hiring spine.

Per-phase validators (validate_jd_schema, validate_shortlist_schema,
validate_offer_schema, validate_compliance_schema, ...) replace this in
Track A. For now it always passes — the spine exists to prove the wiring,
not to guard payload shapes that don't exist yet.
"""
from __future__ import annotations


async def execute(input: dict) -> dict:
    return {"ok": True}
