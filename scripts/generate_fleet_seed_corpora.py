#!/usr/bin/env python3
"""Generate seed corpora for the six fleet-* domains.

One-shot generator — re-run when scenario mixes need to change. Each domain
gets a deterministic, hand-curated JSON list of >=40 records with `id`,
domain-semantic fields, and a `scenario` tag matching the per-domain mix
declared in plan/feature-fleet-domain-substrate-1.md (Phase 5).

Outputs:
  data/synthetic/travel-preapproval/trips.json
  data/synthetic/vendor-kyc/vendors.json
  data/synthetic/employee-onboarding/joiners.json
  data/synthetic/it-access-request/requests.json
  data/synthetic/contract-renewal/contracts.json
  data/synthetic/perf-review/reviewees.json

Determinism: seeded RNG (per-file seed) so re-running yields byte-identical
files. Demo recordings rely on this.
"""
from __future__ import annotations
import json
import random
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = REPO_ROOT / "data" / "synthetic"


# --------------------------------------------------------------------------
# Shared pickers
# --------------------------------------------------------------------------

_FIRST = ["Aisha", "Marco", "Yuki", "Lukas", "Priya", "Olu", "Ines", "Daniel",
          "Sophie", "James", "Eleanor", "Marcus", "Cara", "Nadia", "Ethan",
          "Hannah", "Liam", "Maya", "Owen", "Ruby", "Sam", "Tara", "Uma",
          "Victor", "Wren", "Xavier", "Yusuf", "Zara"]
_LAST  = ["Khan", "Rossi", "Tanaka", "Weber", "Sharma", "Adeyemi", "Costa",
          "Whitfield", "Lambert", "O'Connor", "Fitzgerald", "Bennett",
          "Iqbal", "Park", "Nakamura", "Foster", "Reed", "Choi", "Patel"]
_DEPTS = ["Account", "Creative", "Strategy", "Production", "Finance",
          "Engineering", "Legal", "Operations", "PR", "Data"]
_AGENCIES = ["Mindshare", "Wavemaker", "Mediacom", "EssenceMediacom",
             "Ogilvy", "Grey", "VMLY&R", "GroupM Central", "Hogarth"]


def _emp_id(rng: random.Random) -> str:
    return f"EMP-{rng.randint(1000, 9989):04d}"


def _name(rng: random.Random) -> str:
    return f"{rng.choice(_FIRST)} {rng.choice(_LAST)}"


# --------------------------------------------------------------------------
# travel-preapproval — 40 records, mix 60/25/15
# --------------------------------------------------------------------------

_AIRPORTS = ["LHR", "JFK", "NRT", "FRA", "CDG", "DXB", "SIN", "ZRH", "SYD",
             "LAX", "ORD", "GRU", "JNB", "HKG"]
_REASONS_OK = [
    "Q3 client review", "agency offsite", "regional MD summit",
    "global town hall delegate", "creative pitch attendance",
]
_REASONS_EXC = [
    "client emergency — same-week travel", "Cannes Lions critical attendance",
    "regulatory hearing — counsel required",
]
_REASONS_HIGH = [
    "executive escort — CEO offsite", "private aviation request — schedule conflict",
    "first-class long-haul — back-to-back board meetings",
]


def _gen_travel() -> list[dict]:
    rng = random.Random(20260504_01)
    out: list[dict] = []
    # 24 in-policy
    for i in range(24):
        out.append({
            "id": f"TRP-{i+1:03d}",
            "employee_id": _emp_id(rng),
            "origin": rng.choice(_AIRPORTS),
            "destination": rng.choice(_AIRPORTS),
            "depart_date": "2026-06-15", "return_date": "2026-06-18",
            "business_reason": rng.choice(_REASONS_OK),
            "scenario": "in-policy",
        })
    # 10 policy-exception (last-minute / regulatory)
    for i in range(10):
        out.append({
            "id": f"TRP-{i+25:03d}",
            "employee_id": _emp_id(rng),
            "origin": rng.choice(_AIRPORTS),
            "destination": rng.choice(_AIRPORTS),
            "depart_date": "2026-05-10", "return_date": "2026-05-12",
            "business_reason": rng.choice(_REASONS_EXC),
            "scenario": "policy-exception",
        })
    # 6 high-cost-band
    for i in range(6):
        out.append({
            "id": f"TRP-{i+35:03d}",
            "employee_id": _emp_id(rng),
            "origin": rng.choice(_AIRPORTS),
            "destination": rng.choice(_AIRPORTS),
            "depart_date": "2026-07-01", "return_date": "2026-07-05",
            "business_reason": rng.choice(_REASONS_HIGH),
            "scenario": "high-cost-band",
        })
    return out


# --------------------------------------------------------------------------
# vendor-kyc — 42 records
# --------------------------------------------------------------------------

_VENDOR_NAMES_CLEAN = [
    "Acme Holdings", "Northwind Trading", "Initech Systems", "Globex Industries",
    "Umbrella Logistics", "Hooli Capital", "Pied Piper Services", "Stark Materials",
    "Wonka Confectionery", "Monsters Power", "Tyrell Robotics", "Cyberdyne Analytics",
    "Soylent Foods", "Wayne Enterprises", "Stark Industries", "Oscorp Genetics",
    "Daily Planet Media", "Daily Bugle Press", "InGen Bio", "Macrosoft Cloud",
    "Pinetree Hosting", "Seabreeze Logistics", "Alpine Audit",
    "Riverbend Consulting", "Highland Partners",
]
_VENDOR_NAMES_RISKY = [
    "Pacific Maritime Holdings", "Eastern Star Trading", "Volga Industrial Group",
    "Caspian Resources", "Black Sea Shipping", "Steppe Capital",
    "North Korean Goods Coop", "Crimson Dawn Logistics", "Phoenix Strategic",
    "Saffron Trading Co.",
]
_COUNTRIES_OK = ["GB", "US", "DE", "FR", "JP", "AE", "SG", "CH", "NL", "SE"]
_COUNTRIES_RISKY = ["RU", "BY", "IR", "KP", "SY", "VE"]


def _gen_vendor_kyc() -> list[dict]:
    rng = random.Random(20260504_02)
    out: list[dict] = []
    # 24 clean
    for i in range(24):
        out.append({
            "id": f"VND-{i+1:03d}",
            "vendor_name": _VENDOR_NAMES_CLEAN[i % len(_VENDOR_NAMES_CLEAN)],
            "country_of_incorporation": rng.choice(_COUNTRIES_OK),
            "proposing_agency": rng.choice(_AGENCIES),
            "scenario": "clean",
        })
    # 6 sanctions-hit-entity (high-risk country)
    for i in range(6):
        out.append({
            "id": f"VND-{i+25:03d}",
            "vendor_name": _VENDOR_NAMES_RISKY[i % len(_VENDOR_NAMES_RISKY)],
            "country_of_incorporation": rng.choice(_COUNTRIES_RISKY),
            "proposing_agency": rng.choice(_AGENCIES),
            "scenario": "sanctions-hit-entity",
        })
    # 6 sanctions-hit-ubo (clean entity, risky UBO via name)
    for i in range(6):
        out.append({
            "id": f"VND-{i+31:03d}",
            "vendor_name": _VENDOR_NAMES_CLEAN[(i + 5) % len(_VENDOR_NAMES_CLEAN)],
            "country_of_incorporation": rng.choice(_COUNTRIES_OK),
            "proposing_agency": rng.choice(_AGENCIES),
            "scenario": "sanctions-hit-ubo",
        })
    # 6 adverse-media
    for i in range(6):
        out.append({
            "id": f"VND-{i+37:03d}",
            "vendor_name": _VENDOR_NAMES_RISKY[(i + 4) % len(_VENDOR_NAMES_RISKY)],
            "country_of_incorporation": rng.choice(_COUNTRIES_OK),
            "proposing_agency": rng.choice(_AGENCIES),
            "scenario": "adverse-media",
        })
    return out


# --------------------------------------------------------------------------
# employee-onboarding — 40 records
# --------------------------------------------------------------------------

def _gen_onboarding() -> list[dict]:
    rng = random.Random(20260504_03)
    out: list[dict] = []
    # 24 standard
    for i in range(24):
        out.append({
            "id": f"JNR-{i+1:03d}",
            "employee_id": _emp_id(rng),
            "department": rng.choice(_DEPTS),
            "buddy_id": _emp_id(rng),
            "start_date": "2026-06-15",
            "scenario": "standard",
        })
    # 10 elevated-access-request (engineering/data joiners with broad scope)
    for i in range(10):
        out.append({
            "id": f"JNR-{i+25:03d}",
            "employee_id": _emp_id(rng),
            "department": rng.choice(["Engineering", "Data", "Operations"]),
            "buddy_id": _emp_id(rng),
            "start_date": "2026-06-15",
            "scenario": "elevated-access-request",
        })
    # 6 external-contractor (contract roles)
    for i in range(6):
        out.append({
            "id": f"JNR-{i+35:03d}",
            "employee_id": f"CON-{rng.randint(1000, 9999):04d}",
            "department": rng.choice(["Creative", "PR", "Production"]),
            "buddy_id": _emp_id(rng),
            "start_date": "2026-06-15",
            "scenario": "external-contractor",
        })
    return out


# --------------------------------------------------------------------------
# it-access-request — 40 records
# --------------------------------------------------------------------------

def _gen_it_access() -> list[dict]:
    rng = random.Random(20260504_04)
    out: list[dict] = []
    # 24 routine-rotation
    for i in range(24):
        dep = rng.choice(_DEPTS)
        prefix = dep.lower()[:3]
        out.append({
            "id": f"REQ-{i+1:03d}",
            "employee_id": _emp_id(rng),
            "department": dep,
            "requested_role_templates": [
                f"tmpl-{prefix}-g3-{rng.randint(1, 99):02d}",
                f"tmpl-{prefix}-g3-{rng.randint(1, 99):02d}",
            ],
            "business_justification": (
                f"Project rotation onto Q3 {dep.lower()} workstream; "
                f"needs read-access to dashboards."
            ),
            "scenario": "routine-rotation",
        })
    # 10 privileged-broad (>=4 templates)
    for i in range(10):
        dep = rng.choice(["Finance", "Engineering", "Legal"])
        prefix = dep.lower()[:3]
        out.append({
            "id": f"REQ-{i+25:03d}",
            "employee_id": _emp_id(rng),
            "department": dep,
            "requested_role_templates": [
                f"tmpl-{prefix}-g4-{rng.randint(1, 99):02d}" for _ in range(rng.randint(4, 6))
            ],
            "business_justification": (
                "Cross-functional incident-response role; "
                "needs broad write-access across systems."
            ),
            "scenario": "privileged-broad",
        })
    # 6 post-incident-narrow
    for i in range(6):
        dep = rng.choice(_DEPTS)
        prefix = dep.lower()[:3]
        out.append({
            "id": f"REQ-{i+35:03d}",
            "employee_id": _emp_id(rng),
            "department": dep,
            "requested_role_templates": [f"tmpl-{prefix}-g2-readonly-01"],
            "business_justification": (
                "Post-incident audit access; read-only to a single folder for 14 days."
            ),
            "scenario": "post-incident-narrow",
        })
    return out


# --------------------------------------------------------------------------
# contract-renewal — 40 records
# --------------------------------------------------------------------------

def _gen_contract_renewal() -> list[dict]:
    rng = random.Random(20260504_05)
    out: list[dict] = []
    base_vendors = (_VENDOR_NAMES_CLEAN + _VENDOR_NAMES_RISKY)
    # 20 flat-renewal
    for i in range(20):
        cur = rng.randint(50_000, 250_000)
        out.append({
            "id": f"CNT-{i+1:03d}",
            "contract_id": f"CNT-{i+1:04d}",
            "vendor_name": base_vendors[i % len(base_vendors)],
            "current_annual_value": cur,
            "proposed_annual_value": cur,
            "scenario": "flat-renewal",
        })
    # 8 price-jump (>25%)
    for i in range(8):
        cur = rng.randint(50_000, 250_000)
        prop = int(cur * rng.uniform(1.30, 1.85))
        out.append({
            "id": f"CNT-{i+21:03d}",
            "contract_id": f"CNT-{i+21:04d}",
            "vendor_name": base_vendors[(i + 5) % len(base_vendors)],
            "current_annual_value": cur,
            "proposed_annual_value": prop,
            "scenario": "price-jump",
        })
    # 8 scope-expansion (modest price-up but lots of new SKUs/lines)
    for i in range(8):
        cur = rng.randint(50_000, 250_000)
        prop = int(cur * rng.uniform(1.10, 1.20))
        out.append({
            "id": f"CNT-{i+29:03d}",
            "contract_id": f"CNT-{i+29:04d}",
            "vendor_name": base_vendors[(i + 11) % len(base_vendors)],
            "current_annual_value": cur,
            "proposed_annual_value": prop,
            "scenario": "scope-expansion",
        })
    # 4 below-market (price drop)
    for i in range(4):
        cur = rng.randint(50_000, 250_000)
        prop = int(cur * rng.uniform(0.75, 0.92))
        out.append({
            "id": f"CNT-{i+37:03d}",
            "contract_id": f"CNT-{i+37:04d}",
            "vendor_name": base_vendors[(i + 17) % len(base_vendors)],
            "current_annual_value": cur,
            "proposed_annual_value": prop,
            "scenario": "below-market",
        })
    return out


# --------------------------------------------------------------------------
# perf-review — 40 records
# --------------------------------------------------------------------------

_RATINGS = ["below", "meets", "exceeds"]


def _gen_perf_review() -> list[dict]:
    rng = random.Random(20260504_06)
    out: list[dict] = []
    # 24 on-track
    for i in range(24):
        out.append({
            "id": f"REV-{i+1:03d}",
            "employee_id": _emp_id(rng),
            "cycle": "2026-H1",
            "prior_rating": "meets",
            "scenario": "on-track",
        })
    # 6 calibration-outlier-high (peers say exceeds, prior says meets)
    for i in range(6):
        out.append({
            "id": f"REV-{i+25:03d}",
            "employee_id": _emp_id(rng),
            "cycle": "2026-H1",
            "prior_rating": "meets",
            "scenario": "calibration-outlier-high",
        })
    # 6 calibration-outlier-low
    for i in range(6):
        out.append({
            "id": f"REV-{i+31:03d}",
            "employee_id": _emp_id(rng),
            "cycle": "2026-H1",
            "prior_rating": "exceeds",
            "scenario": "calibration-outlier-low",
        })
    # 4 promotion-candidate
    for i in range(4):
        out.append({
            "id": f"REV-{i+37:03d}",
            "employee_id": _emp_id(rng),
            "cycle": "2026-H1",
            "prior_rating": "exceeds",
            "scenario": "promotion-candidate",
        })
    return out


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------

DOMAINS: dict[str, tuple[str, callable]] = {
    "travel-preapproval/trips.json": ("travel-preapproval", _gen_travel),
    "vendor-kyc/vendors.json":       ("vendor-kyc", _gen_vendor_kyc),
    "employee-onboarding/joiners.json": ("employee-onboarding", _gen_onboarding),
    "it-access-request/requests.json": ("it-access-request", _gen_it_access),
    "contract-renewal/contracts.json": ("contract-renewal", _gen_contract_renewal),
    "perf-review/reviewees.json":      ("perf-review", _gen_perf_review),
}


def main() -> None:
    for rel, (label, gen) in DOMAINS.items():
        records = gen()
        path = OUT_ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
        scenarios: dict[str, int] = {}
        for r in records:
            scenarios[r["scenario"]] = scenarios.get(r["scenario"], 0) + 1
        scen_str = ", ".join(f"{k}={v}" for k, v in sorted(scenarios.items()))
        print(f"  {label}: {len(records)} records -> {path.relative_to(REPO_ROOT)}")
        print(f"    scenarios: {scen_str}")


if __name__ == "__main__":
    main()
