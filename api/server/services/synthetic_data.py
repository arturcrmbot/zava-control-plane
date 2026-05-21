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
        jurisdiction=f"{market}-Zava",
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
        jurisdiction=f"{market}-Zava",
        agency="Zava-HR",
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


# ---------------------------------------------------------------------------
# Fleet-* builders (compose-domain v3 generated domains).
#
# Each builder constructs a Workflow with workflow_type set, a sensible
# initial current_phase (matches the FIRST step.started the orchestrator
# emits), and `payload` carrying the domain-specific input dict that the
# orchestration generator and downstream activities read.
#
# Builders are intentionally tolerant: pass `record=<dict-from-seed-corpus>`
# for the Phase 5 path, OR pass individual kwargs to synthesise inline.
# ---------------------------------------------------------------------------


def _now_with_jitter() -> tuple[float, float]:
    """Return (created_at, sla_due_at) with a domain-default 7-day SLA."""
    now = time.time()
    return now, now + 7 * 86400


def build_fleet_travel_preapproval_workflow(
    workflow_id: str, record: dict | None = None,
) -> Workflow:
    """Travel pre-approval workflow record. `record` is one trip from
    data/synthetic/travel-preapproval/trips.json when seeded; otherwise a
    minimal trip is synthesised inline."""
    r = record or {}
    employee_id = r.get("employee_id") or f"EMP-{random.randint(1000, 9999):04d}"
    trip = {
        "employee_id": employee_id,
        "origin": r.get("origin", "LHR"),
        "destination": r.get("destination", "JFK"),
        "depart_date": r.get("depart_date", "2026-06-15"),
        "return_date": r.get("return_date", "2026-06-18"),
        "business_reason": r.get("business_reason", "Q3 client review"),
    }
    created_at, sla = _now_with_jitter()
    return Workflow(
        id=workflow_id,
        type="travel-preapproval",
        current_phase="Employee Lookup",
        created_at=created_at,
        sla_due_at=sla,
        jurisdiction="London-Zava",
        agency="Zava",
        payload={"trip": trip, "scenario": r.get("scenario")},
    )


def build_fleet_vendor_kyc_workflow(
    workflow_id: str, record: dict | None = None,
) -> Workflow:
    """Vendor KYC workflow record. `record` is one vendor from
    data/synthetic/vendor-kyc/vendors.json when seeded."""
    r = record or {}
    vendor = {
        "name": r.get("vendor_name", f"Acme {workflow_id}"),
        "country_of_incorporation": r.get("country_of_incorporation", "GB"),
        "proposing_agency": r.get("proposing_agency", "Mindshare"),
    }
    created_at, sla = _now_with_jitter()
    return Workflow(
        id=workflow_id,
        type="vendor-kyc",
        current_phase="Vendor Intake",
        created_at=created_at,
        sla_due_at=sla,
        jurisdiction=f"{vendor['country_of_incorporation']}-Zava",
        agency=vendor["proposing_agency"],
        payload={"vendor": vendor, "scenario": r.get("scenario")},
    )


def build_fleet_employee_onboarding_workflow(
    workflow_id: str, record: dict | None = None,
) -> Workflow:
    """Employee onboarding workflow record. `record` is one joiner from
    data/synthetic/employee-onboarding/joiners.json when seeded."""
    r = record or {}
    joiner = {
        "employee_id": r.get("employee_id") or f"EMP-{random.randint(1000, 9999):04d}",
        "department": r.get("department", "Engineering"),
        "buddy_id": r.get("buddy_id") or f"EMP-{random.randint(1000, 9999):04d}",
        "start_date": r.get("start_date", "2026-06-15"),
    }
    created_at, sla = _now_with_jitter()
    return Workflow(
        id=workflow_id,
        type="employee-onboarding",
        current_phase="Employee Lookup",
        created_at=created_at,
        sla_due_at=sla,
        jurisdiction="London-Zava",
        agency="Zava",
        payload={"joiner": joiner, "scenario": r.get("scenario")},
    )


def build_fleet_employee_transfer_workflow(
    workflow_id: str, record: dict | None = None,
) -> Workflow:
    """Employee transfer workflow record. `record` may carry a
    pre-populated transfer dict (employee_id, source/target org, effective
    date, target role, business reason); defaults are deterministic."""
    r = record or {}
    transfer = r.get("transfer") if "transfer" in r else r
    transfer = transfer or {}
    transfer = {
        "employee_id": transfer.get("employee_id") or f"EMP-{random.randint(1000, 9999):04d}",
        "source_org_id": transfer.get("source_org_id", "ORG-HELIOS-UK"),
        "target_org_id": transfer.get("target_org_id", "ORG-NORTHWIND-DE"),
        "effective_date": transfer.get("effective_date", "2026-07-01"),
        "target_role": transfer.get("target_role", "Senior Planner"),
        "business_reason": transfer.get("business_reason", "Regional rebalance"),
    }
    created_at, sla = _now_with_jitter()
    return Workflow(
        id=workflow_id,
        type="employee-transfer",
        current_phase="Transfer Intake",
        created_at=created_at,
        sla_due_at=sla,
        jurisdiction="London-Zava",
        agency="Zava",
        payload={"transfer": transfer, "scenario": r.get("scenario")},
    )


def build_fleet_it_access_request_workflow(
    workflow_id: str, record: dict | None = None,
) -> Workflow:
    """IT access request workflow record. `record` is one request from
    data/synthetic/it-access-request/requests.json when seeded."""
    r = record or {}
    request = {
        "employee_id": r.get("employee_id") or f"EMP-{random.randint(1000, 9999):04d}",
        "department": r.get("department", "Finance"),
        "requested_role_templates": r.get("requested_role_templates",
                                          ["tmpl-fin-g3-01", "tmpl-fin-g3-02"]),
        "business_justification": r.get(
            "business_justification",
            "Project rotation onto Q3 finance-analytics workstream.",
        ),
    }
    created_at, sla = _now_with_jitter()
    return Workflow(
        id=workflow_id,
        type="it-access-request",
        current_phase="Employee Lookup",
        created_at=created_at,
        sla_due_at=sla,
        jurisdiction="London-Zava",
        agency="Zava",
        payload={"request": request, "scenario": r.get("scenario")},
    )


def build_fleet_contract_renewal_workflow(
    workflow_id: str, record: dict | None = None,
) -> Workflow:
    """Contract renewal workflow record. `record` is one contract from
    data/synthetic/contract-renewal/contracts.json when seeded."""
    r = record or {}
    contract = {
        "contract_id": r.get("contract_id") or f"CNT-{random.randint(1000, 9999):04d}",
        "vendor_name": r.get("vendor_name", "Globex Industries"),
        "current_annual_value": r.get("current_annual_value", 100000),
        "proposed_annual_value": r.get("proposed_annual_value", 110000),
    }
    created_at, sla = _now_with_jitter()
    return Workflow(
        id=workflow_id,
        type="contract-renewal",
        current_phase="Contract Lookup",
        created_at=created_at,
        sla_due_at=sla,
        jurisdiction="London-Zava",
        agency="Zava",
        payload={"contract": contract, "scenario": r.get("scenario")},
    )


def build_fleet_perf_review_workflow(
    workflow_id: str, record: dict | None = None,
) -> Workflow:
    """Performance review workflow record. `record` is one reviewee from
    data/synthetic/perf-review/reviewees.json when seeded."""
    r = record or {}
    review = {
        "employee_id": r.get("employee_id") or f"EMP-{random.randint(1000, 9999):04d}",
        "cycle": r.get("cycle", "2026-H1"),
        "prior_rating": r.get("prior_rating", "meets"),
    }
    created_at, sla = _now_with_jitter()
    return Workflow(
        id=workflow_id,
        type="perf-review",
        current_phase="Employee Lookup",
        created_at=created_at,
        sla_due_at=sla,
        jurisdiction="London-Zava",
        agency="Zava",
        payload={"review": review, "scenario": r.get("scenario")},
    )


def build_fleet_ap_invoice_workflow(
    workflow_id: str, record: dict | None = None,
) -> Workflow:
    """AP invoice workflow record. `record` is one invoice from
    data/synthetic/ap-invoice/invoices.json when seeded."""
    r = record or {}
    invoice = {
        "invoice_id": r.get("invoice_id") or f"INV-2026-{random.randint(10000, 99999):05d}",
        "vendor_name": r.get("vendor_name", "Globex Industries"),
        "amount_gbp": r.get("amount_gbp", 1500),
        "category": r.get("category", "standard"),
        "currency": r.get("currency", "GBP"),
        "po_id": r.get("po_id"),  # may be None for missing-po scenario
    }
    created_at, sla = _now_with_jitter()
    return Workflow(
        id=workflow_id,
        type="ap-invoice",
        current_phase="Invoice Lookup",
        created_at=created_at,
        sla_due_at=sla,
        jurisdiction="London-Zava",
        agency="Zava",
        payload={"invoice": invoice, "scenario": r.get("scenario")},
    )


# Hand-graduated wave 2: purchase-order, contract-review, privacy-dpia, treasury-fx

def build_fleet_purchase_order_workflow(workflow_id: str, record: dict | None = None) -> Workflow:
    """Purchase Order workflow record. `record` is one PO from data/synthetic/purchase-order/pos.json."""
    r = record or {}
    purchase_order = {
        "po_id": r.get("po_id") or f"PO-2026-{random.randint(10000, 99999):05d}",
        "vendor_name": r.get("vendor_name", "Globex Industries"),
        "amount_gbp": r.get("amount_gbp", 5000),
        "category": r.get("category", "standard"),
        "supplier_on_approved_list": r.get("supplier_on_approved_list", True),
    }
    created_at, sla = _now_with_jitter()
    return Workflow(
        id=workflow_id,
        type="purchase-order",
        current_phase="PO Lookup",
        created_at=created_at,
        sla_due_at=sla,
        jurisdiction="London-Zava",
        agency="Zava",
        payload={"purchase_order": purchase_order, "scenario": r.get("scenario")},
    )


def build_fleet_contract_review_workflow(workflow_id: str, record: dict | None = None) -> Workflow:
    """Contract Review workflow record."""
    r = record or {}
    contract_review = {
        "contract_id": r.get("contract_id") or f"CR-2026-{random.randint(10000, 99999):05d}",
        "vendor_name": r.get("vendor_name", "Acme Holdings"),
        "contract_type": r.get("contract_type", "msa"),
        "amount_gbp": r.get("amount_gbp", 50000),
        "deviates_from_template": r.get("deviates_from_template", False),
    }
    created_at, sla = _now_with_jitter()
    return Workflow(
        id=workflow_id,
        type="contract-review",
        current_phase="Contract Intake",
        created_at=created_at,
        sla_due_at=sla,
        jurisdiction="London-Zava",
        agency="Zava",
        payload={"contract_review": contract_review, "scenario": r.get("scenario")},
    )


def build_fleet_privacy_dpia_workflow(workflow_id: str, record: dict | None = None) -> Workflow:
    """Privacy DPIA workflow record."""
    r = record or {}
    dpia = {
        "dpia_id": r.get("dpia_id") or f"DPIA-2026-{random.randint(10000, 99999):05d}",
        "system_name": r.get("system_name", "Unnamed System"),
        "risk_tier": r.get("risk_tier", "low_risk"),
        "geography": r.get("geography", "EMEA"),
    }
    created_at, sla = _now_with_jitter()
    return Workflow(
        id=workflow_id,
        type="privacy-dpia",
        current_phase="DPIA Intake",
        created_at=created_at,
        sla_due_at=sla,
        jurisdiction="London-Zava",
        agency="Zava",
        payload={"dpia": dpia, "scenario": r.get("scenario")},
    )


def build_fleet_treasury_fx_workflow(workflow_id: str, record: dict | None = None) -> Workflow:
    """Treasury FX workflow record."""
    r = record or {}
    treasury_op = {
        "op_id": r.get("op_id") or f"FX-2026-{random.randint(10000, 99999):05d}",
        "op_kind": r.get("op_kind", "spot-hedge"),
        "currency_pair": r.get("currency_pair", "GBP/USD"),
        "notional_gbp": r.get("notional_gbp", 250000),
    }
    created_at, sla = _now_with_jitter()
    return Workflow(
        id=workflow_id,
        type="treasury-fx",
        current_phase="Op Lookup",
        created_at=created_at,
        sla_due_at=sla,
        jurisdiction="London-Zava",
        agency="Zava",
        payload={"treasury_op": treasury_op, "scenario": r.get("scenario")},
    )


# POC3: creative-campaign

def build_creative_campaign_workflow(
    workflow_id: str, record: dict | None = None,
) -> Workflow:
    """Creative campaign workflow record. `record` is one brief from
    data/synthetic/creative-campaign/briefs.json when seeded; otherwise
    a minimal brief is synthesised inline."""
    r = record or {}
    brief = {
        "id": r.get("id") or f"BRF-{random.randint(1000, 9999):04d}",
        "client_brand": r.get("client_brand", "Solene"),
        "category": r.get("category", "luxury_fragrance"),
        "audience": r.get("audience", "Aspirational European 25-44"),
        "mandatory_messages": r.get(
            "mandatory_messages",
            ["regenerative provenance", "low-impact craftsmanship"],
        ),
        "channels": r.get("channels", ["CTV", "OOH", "social"]),
        "kpis": r.get("kpis", {"awareness": "+15%", "intent": "+8%"}),
        "constraints": r.get("constraints", []),
        "jurisdictions": r.get("jurisdictions", ["UK", "FR"]),
    }
    created_at, sla = _now_with_jitter()
    return Workflow(
        id=workflow_id,
        type="creative-campaign",
        current_phase="brief_capture",
        created_at=created_at,
        sla_due_at=sla,
        jurisdiction=brief["jurisdictions"][0] + "-Zava",
        agency=r.get("agency", "Ogilvy"),
        payload={"brief": brief, "scenario": r.get("scenario")},
    )
