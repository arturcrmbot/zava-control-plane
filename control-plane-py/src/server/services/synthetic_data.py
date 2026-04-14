# src/server/services/synthetic_data.py
"""Build a synthetic POC1 invoice workflow from v1 fixtures."""
from __future__ import annotations
import json
import random
import time
from pathlib import Path
from src.shared.types import Workflow, Vendor, InvoiceData, InvoiceLineItem


_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _load_json(name: str) -> list:
    with open(_FIXTURES / name) as f:
        return json.load(f)


VENDORS = _load_json("vendors.json")
PURCHASE_ORDERS = _load_json("purchase-orders.json")
AGENCIES = _load_json("agencies.json")


def build_workflow(workflow_id: str, force_demo_fail: bool = False) -> Workflow:
    """Generate a fresh synthetic Workflow with random vendor/PO/agency.
    If force_demo_fail, append 'DEMO_FAIL' to vendor name — triggers the
    bounded-probabilism demo path in agent_gl_coder."""
    vendor_data = random.choice(VENDORS)
    if force_demo_fail:
        vendor_data = {**vendor_data, "name": vendor_data["name"] + " DEMO_FAIL"}
    po = random.choice(PURCHASE_ORDERS)
    agency = random.choice(AGENCIES)
    now = time.time()
    line_count = po.get("lineCount", 1)
    return Workflow(
        id=workflow_id,
        created_at=now,
        sla_due_at=now + (1 + random.random() * 4) * 3600,
        vendor=Vendor(id=vendor_data["id"], name=vendor_data["name"], country=vendor_data["country"]),
        invoice=InvoiceData(
            number=f"INV-{random.randint(100000, 999999)}",
            amount=round(po["amount"] * (0.98 + random.random() * 0.05), 2),
            currency=po["currency"],
            line_items=[InvoiceLineItem(description=f"Line {i+1}", qty=1.0, unit_price=po["amount"]/line_count) for i in range(line_count)],
            po_ref=po["id"],
        ),
        jurisdiction=f"{vendor_data['country']}-CA",
        agency=agency["id"],
    )
