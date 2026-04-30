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


_employees_cache: list[dict] | None = None


def _employees() -> list[dict]:
    """Lazy module-level cache of the employees fixture. The fixture is
    immutable at runtime (~10KB JSON committed to git); reading it on every
    build_expense_workflow call was costing ~300 redundant reads per ramp."""
    global _employees_cache
    if _employees_cache is None:
        _employees_cache = json.loads(_EMPLOYEES_PATH.read_text(encoding="utf-8"))
    return _employees_cache


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
    emp = next((e for e in _employees() if e["id"] == raw["employee_id"]), None)
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


_HIRING_CVS_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "hiring" / "cvs"


def build_hiring_workflow(workflow_id: str, candidate_id: str | None = None) -> Workflow:
    """Generate a Workflow record for a POC2 hiring run, picking a synthetic CV.

    If `candidate_id` is provided, that specific CV file is loaded; otherwise
    a random one is chosen from data/synthetic/hiring/cvs/.
    """
    if candidate_id is None:
        candidates = sorted(p.stem for p in _HIRING_CVS_DIR.glob("C-*.json"))
        if not candidates:
            raise FileNotFoundError(f"no hiring CVs under {_HIRING_CVS_DIR}")
        candidate_id = random.choice(candidates)
    raw = json.loads((_HIRING_CVS_DIR / f"{candidate_id}.json").read_text(encoding="utf-8"))
    jurisdiction = raw.get("jurisdiction_target") or raw.get("right_to_work", {}).get("jurisdiction") or "USA"
    market = "London" if jurisdiction == "USA" else "Berlin"
    now = time.time()

    # POC2 §4.21 AG-UI: if the fixture carries a hand-authored
    # component_spec, lift it onto agent_outputs.cv_crystalliser so the
    # WorkflowDetail scorecard renders the moment a seeded HIRE-* workflow
    # is opened — no real Triage run required for the demo.
    agent_outputs: dict = {}
    component_spec = raw.get("component_spec")
    if component_spec:
        agent_outputs["cv_crystalliser"] = {
            "candidate_id": candidate_id,
            "profile": {
                "candidate_id": candidate_id,
                "name": raw.get("name"),
                "current_title": raw.get("current_title"),
                "tenure_years_total": raw.get("tenure_years_total"),
                "skills": raw.get("skills"),
                "right_to_work": raw.get("right_to_work"),
            },
            "component_spec": component_spec,
            "inconsistencies": raw.get("inconsistencies", []),
        }

    return Workflow(
        id=workflow_id,
        type="hiring",
        current_phase="Budget",
        created_at=now,
        sla_due_at=now + 7 * 86400,  # 7-day SLA per BetrVG/HR BP windows
        jurisdiction=f"{market}-WPP",
        agency="WPP-HR",
        metadata={
            "candidate_id": candidate_id,
            "candidate_name": raw.get("name"),
            "role_family": raw.get("current_title"),
            "level_target": raw.get("level_target"),
            "jurisdiction": jurisdiction,
            "right_to_work": raw.get("right_to_work"),
        },
        agent_outputs=agent_outputs,
    )
