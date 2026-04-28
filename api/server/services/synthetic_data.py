# src/server/services/synthetic_data.py
"""Build synthetic POC1 workflows — invoice (legacy) and expense claim (current)."""
from __future__ import annotations
import json
import random
import time
from pathlib import Path
from api.shared.types import Workflow, Vendor, InvoiceData, InvoiceLineItem, ClaimData


_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
_CLAIMS_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "claims"
_EMPLOYEES_PATH = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "employees.json"


def _load_json(name: str) -> list:
    with open(_FIXTURES / name) as f:
        return json.load(f)


VENDORS = _load_json("vendors.json")
PURCHASE_ORDERS = _load_json("purchase-orders.json")
AGENCIES = _load_json("agencies.json")


def build_workflow(workflow_id: str) -> Workflow:
    """Generate a fresh synthetic Workflow with random vendor/PO/agency.

    Demo-scenario determinism (``demo-fail`` / ``demo-hitl``) is injected by
    the caller via orchestration-payload force flags, not by mutating the
    synthesised workflow. See ``simulator_orchestrator.spawn_workflow``.
    """
    vendor_data = random.choice(VENDORS)
    po = random.choice(PURCHASE_ORDERS)
    agency = random.choice(AGENCIES)
    now = time.time()
    line_count = po.get("lineCount", 1)
    return Workflow(
        id=workflow_id,
        type="invoice-p2p",
        current_phase="Intake",
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


def build_expense_workflow(workflow_id: str, claim_id: str | None = None) -> Workflow:
    """Generate a Workflow record over a synthetic expense claim.

    If `claim_id` is provided, that specific claim file is loaded (deterministic,
    used for repeat-offender/scenario seeding). Otherwise picks one at random
    from data/synthetic/claims/.
    """
    if claim_id is None:
        candidates = sorted(p.stem for p in _CLAIMS_DIR.glob("CLM-*.json"))
        if not candidates:
            raise FileNotFoundError(f"no claims under {_CLAIMS_DIR}")
        claim_id = random.choice(candidates)
    raw = json.loads((_CLAIMS_DIR / f"{claim_id}.json").read_text(encoding="utf-8"))
    employees = json.loads(_EMPLOYEES_PATH.read_text(encoding="utf-8"))
    emp = next((e for e in employees if e["id"] == raw["employee_id"]), None)
    agency_id = (emp or {}).get("agency", "GroupM")
    market = raw["market"]
    now = time.time()
    claim = ClaimData(
        claim_id=raw["claim_id"],
        employee_id=raw["employee_id"],
        submitted_at=raw["submitted_at"],
        market=market,
        currency=raw["currency"],
        category=raw["category"],
        vendor=raw["vendor"],
        amount=raw["amount"],
        attendees=raw.get("attendees", 1),
        receipt_filename=raw.get("receipt_filename"),
        receipt_mismatch_flavour=raw.get("receipt_mismatch_flavour"),
        ems_source=raw["ems_source"],
    )
    return Workflow(
        id=workflow_id,
        type="expense-claim",
        current_phase="Intake",
        created_at=now,
        sla_due_at=now + (1 + random.random() * 4) * 3600,
        claim=claim,
        jurisdiction=f"{market}-WPP",
        agency=agency_id,
    )
