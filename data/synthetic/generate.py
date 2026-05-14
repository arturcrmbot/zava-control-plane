"""Deterministic synthetic expense claim generator.

Walks the synthetic T&E policy and emits 300 labelled claims with literal
policy-clause gold reasoning. Reading order: see policy.md sections 3.1-3.5
for the R/A/G rules driving label selection.

Distribution target: 210 green / 60 amber / 30 red, achieved by the
deterministic walk in `_label_for_index` (no random sampling).
"""
from __future__ import annotations
import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from api.shared.expense_taxonomy import CATEGORIES, CURRENCY_BY_MARKET as CURRENCY, MARKETS

DATA = Path(__file__).parent
CLAIMS = DATA / "claims"
LABELS = DATA / "labels.csv"
EMPLOYEES = DATA / "employees.json"

EMS = ("workday", "concur")

# ----------------------------------------------------------------------------
# Per-market caps mirroring policy.md section 3. The policy text remains the
# source of truth; these constants are the structured copy used to engineer
# claim amounts at chosen distance from the cap.
# ----------------------------------------------------------------------------

# section 3.1 Meals
MEAL_SOLO_CAP = {"UK": 40, "US": 50, "DE": 45, "IN": 2500}
MEAL_PER_ATTENDEE_CAP = {"UK": 75, "US": 75, "DE": 70, "IN": 4000}
RECEIPT_THRESHOLD = {"UK": 25, "US": 25, "DE": 0, "IN": 500}

# section 3.2 Travel — long-haul economy cap is the most-used in claims
TRAVEL_LONGHAUL_CAP = {"UK": 900, "US": 1200, "DE": 950, "IN": 60000}
TRAVEL_DOMESTIC_CAP = {"UK": 250, "US": 400, "DE": 300, "IN": 12000}

# section 3.3 Accommodation — Tier 1 surcharge cap (London/NYC/Mumbai/etc.)
ACCOM_TIER1_CAP = {"UK": 280, "US": 380, "DE": 240, "IN": 16000}
ACCOM_STANDARD_CAP = {"UK": 180, "US": 220, "DE": 170, "IN": 9000}

# section 3.4 Entertainment — per-head cap
ENT_PER_HEAD_CAP = {"UK": 110, "US": 130, "DE": 100, "IN": 5500}
ENT_ALCOHOL_PROHIBITED = {"DE", "IN"}

# section 3.5 Miscellaneous — conference/training fee (most-claimed sub-category)
MISC_CONFERENCE_CAP = {"UK": 1500, "US": 2000, "DE": 1600, "IN": 80000}

# Vendors per (category, market). Drawn from the worked examples in policy.md
# section 7 and plausible high-street brands per market.
VENDORS = {
    ("meals", "UK"): ["Cote Brasserie", "Pret A Manger", "The Ivy", "Dishoom", "Wagamama"],
    ("meals", "US"): ["Shake Shack", "Sweetgreen", "The Capital Grille", "Chipotle", "Joe's Pizza"],
    ("meals", "DE"): ["Vapiano", "Hofbraeuhaus", "Nordsee", "Block House", "L'Osteria"],
    ("meals", "IN"): ["Indian Accent", "Saravana Bhavan", "Bombay Canteen", "Karavalli", "Mahesh Lunch Home"],
    ("travel", "UK"): ["British Airways", "LNER", "Trainline", "Addison Lee", "Heathrow Express"],
    ("travel", "US"): ["Delta Airlines", "Amtrak Acela", "United Airlines", "Uber", "JetBlue"],
    ("travel", "DE"): ["Lufthansa", "Deutsche Bahn ICE", "FreeNow", "Eurowings", "DB Regio"],
    ("travel", "IN"): ["IndiGo", "Air India", "Ola Cabs", "Vistara", "IRCTC AC1"],
    ("accommodation", "UK"): ["Premier Inn London", "The Savoy", "Hilton Manchester", "Hotel Indigo Edinburgh", "Marriott Park Lane"],
    ("accommodation", "US"): ["Marriott Marquis NYC", "Hilton SF Union Square", "Hyatt Regency Boston", "Kimpton LA", "Westin Chicago"],
    ("accommodation", "DE"): ["Hotel Adlon Berlin", "Sofitel Munich", "Steigenberger Frankfurt", "Hyatt Hamburg", "Maritim Berlin"],
    ("accommodation", "IN"): ["Taj Mahal Palace Mumbai", "ITC Maurya Delhi", "The Oberoi Bangalore", "Trident Hyderabad", "JW Marriott Mumbai"],
    ("entertainment", "UK"): ["The Wolseley", "Hakkasan", "Sketch", "Scott's Mayfair", "The Ned"],
    ("entertainment", "US"): ["Eleven Madison Park", "The Polo Bar", "Nobu NYC", "RPM Steak Chicago", "Spago LA"],
    ("entertainment", "DE"): ["Restaurant Tantris", "Borchardt Berlin", "Restaurant Vau", "Goldenes Kalb", "Lutter & Wegner"],
    ("entertainment", "IN"): ["Wasabi by Morimoto", "Bukhara Delhi", "Indigo Mumbai", "Karavalli Bangalore", "Le Cirque Delhi"],
    ("miscellaneous", "UK"): ["WHSmith", "Atlassian Subscriptions", "Eventbrite UK", "John Lewis Business", "Adobe Creative Cloud"],
    ("miscellaneous", "US"): ["Staples", "Atlassian Subscriptions", "Eventbrite US", "Best Buy Business", "Adobe Creative Cloud"],
    ("miscellaneous", "DE"): ["Office Discount DE", "Atlassian Subscriptions", "XING Events", "MediaMarkt Business", "Adobe Creative Cloud"],
    ("miscellaneous", "IN"): ["Reliance Digital", "Atlassian Subscriptions", "BookMyShow Events", "Croma Business", "Adobe Creative Cloud"],
}

# Tier 1 city used in accommodation claim narrative per market (see section 3.3).
TIER1_CITY = {"UK": "London", "US": "New York", "DE": "Munich", "IN": "Mumbai"}


# ----------------------------------------------------------------------------
# Category generators. Each returns (amount, vendor, attendees, narrative,
# gold_reasoning, gold_policy_clause) for the requested target label.
# Amount engineering:
#   - green: comfortably within cap (0.55 - 0.95 of cap)
#   - amber: 1.00 - 1.10 of cap (the boundary band described in section 3 intro)
#   - red:  > 1.10 of cap (a clear breach)
# Reasoning quotes literal policy text so it can be string-similarity-compared
# against classifier output later.
# ----------------------------------------------------------------------------


def _round_to_pence(amount: float, market: str) -> float:
    # INR rounds to whole rupees; everything else rounds to two decimals.
    if market == "IN":
        return float(round(amount))
    return round(amount, 2)


def _gen_meals_claim(rng, target, market):
    cap = MEAL_SOLO_CAP[market]
    vendor = rng.choice(VENDORS[("meals", market)])
    attendees = 1
    if target == "green":
        amount = _round_to_pence(cap * rng.uniform(0.55, 0.92), market)
        clause = f"§3.1 Meals — {market} solo cap {CURRENCY[market]} {cap}"
        reasoning = (
            f"Claim of {CURRENCY[market]} {amount:.2f} is within the {market} solo meal cap of "
            f"{CURRENCY[market]} {cap}. Receipt provided where threshold applies. "
            f"Within solo cap, with receipt where receipt-threshold applies, attendees <=1, no alcohol — Green per §3.1."
        )
    elif target == "amber":
        amount = _round_to_pence(cap * rng.uniform(1.00, 1.10), market)
        clause = f"§3.1 Meals — {market} solo cap {CURRENCY[market]} {cap} (110% boundary)"
        reasoning = (
            f"Claim of {CURRENCY[market]} {amount:.2f} is above the {market} solo meal cap of "
            f"{CURRENCY[market]} {cap} but at or below 110% of the cap. "
            f"Above the cap but at or below 110% of the cap with receipt — Amber per §3.1, reviewer attention required."
        )
    else:  # red
        if market in {"DE", "IN"}:
            # Hard breach: alcohol where prohibited (DE entertainment / IN any meal).
            amount = _round_to_pence(cap * rng.uniform(0.6, 0.9), market)
            clause = f"§3.1 Meals — {market} alcohol prohibited"
            reasoning = (
                f"Alcohol present on a {market} meal claim. Per §3.1 alcohol is prohibited "
                f"({'DE entertainment' if market == 'DE' else 'IN any meal'}); "
                "alcohol where prohibited is a hard breach — Red."
            )
        else:
            amount = _round_to_pence(cap * rng.uniform(1.15, 1.45), market)
            clause = f"§3.1 Meals — {market} solo cap {CURRENCY[market]} {cap} (above 110%)"
            reasoning = (
                f"Claim of {CURRENCY[market]} {amount:.2f} is above 110% of the {market} solo meal cap "
                f"({CURRENCY[market]} {cap}). Above 110% of cap is a hard breach — Red per §3.1."
            )
    narrative = f"Solo dinner at {vendor}"
    return amount, vendor, attendees, narrative, reasoning, clause


def _gen_travel_claim(rng, target, market):
    cap = TRAVEL_LONGHAUL_CAP[market]
    vendor = rng.choice(VENDORS[("travel", market)])
    attendees = 1
    if target == "green":
        amount = _round_to_pence(cap * rng.uniform(0.55, 0.92), market)
        clause = f"§3.2 Travel — {market} long-haul economy cap {CURRENCY[market]} {cap}"
        reasoning = (
            f"Claim of {CURRENCY[market]} {amount:.2f} is at or below the {market} long-haul economy cap "
            f"of {CURRENCY[market]} {cap}, booked in economy with itinerary — Green per §3.2."
        )
    elif target == "amber":
        amount = _round_to_pence(cap * rng.uniform(1.00, 1.10), market)
        clause = f"§3.2 Travel — {market} long-haul economy cap {CURRENCY[market]} {cap} (110% boundary)"
        reasoning = (
            f"Booking of {CURRENCY[market]} {amount:.2f} is above the {market} long-haul economy cap "
            f"of {CURRENCY[market]} {cap} but at or below 110% of cap — Amber per §3.2, reviewer attention required."
        )
    else:  # red
        amount = _round_to_pence(cap * rng.uniform(1.15, 1.55), market)
        clause = f"§3.2 Travel — {market} long-haul economy cap {CURRENCY[market]} {cap} (above 110%)"
        reasoning = (
            f"Leg of {CURRENCY[market]} {amount:.2f} is above 110% of the {market} long-haul economy cap "
            f"({CURRENCY[market]} {cap}). Any leg above 110% of cap is a hard breach — Red per §3.2."
        )
    narrative = f"Long-haul return booking via {vendor}"
    return amount, vendor, attendees, narrative, reasoning, clause


def _gen_accommodation_claim(rng, target, market):
    cap = ACCOM_TIER1_CAP[market]
    vendor = rng.choice(VENDORS[("accommodation", market)])
    attendees = 1
    city = TIER1_CITY[market]
    if target == "green":
        amount = _round_to_pence(cap * rng.uniform(0.6, 0.92), market)
        clause = f"§3.3 Accommodation — {market} Tier 1 cap {CURRENCY[market]} {cap}"
        reasoning = (
            f"{city} hotel at {CURRENCY[market]} {amount:.2f}/night is at or below the Tier 1 cap of "
            f"{CURRENCY[market]} {cap}, with itemised hotel folio and dates aligned to itinerary — Green per §3.3."
        )
    elif target == "amber":
        amount = _round_to_pence(cap * rng.uniform(1.00, 1.10), market)
        clause = f"§3.3 Accommodation — {market} Tier 1 cap {CURRENCY[market]} {cap} (110% boundary)"
        reasoning = (
            f"{city} hotel at {CURRENCY[market]} {amount:.2f}/night is above the Tier 1 cap "
            f"({CURRENCY[market]} {cap}) but at or below 110% of cap — Amber per §3.3, reviewer attention required."
        )
    else:  # red
        amount = _round_to_pence(cap * rng.uniform(1.15, 1.45), market)
        clause = f"§3.3 Accommodation — {market} Tier 1 cap {CURRENCY[market]} {cap} (above 110%)"
        reasoning = (
            f"{city} hotel at {CURRENCY[market]} {amount:.2f}/night is above 110% of the Tier 1 cap "
            f"({CURRENCY[market]} {cap}). Above 110% of cap is a hard breach — Red per §3.3."
        )
    narrative = f"{city} stay at {vendor}"
    return amount, vendor, attendees, narrative, reasoning, clause


def _gen_entertainment_claim(rng, target, market):
    cap = ENT_PER_HEAD_CAP[market]
    vendor = rng.choice(VENDORS[("entertainment", market)])
    attendees = rng.randint(2, 4)
    if target == "green":
        per_head = cap * rng.uniform(0.6, 0.92)
        amount = _round_to_pence(per_head * attendees, market)
        clause = f"§3.4 Entertainment — {market} per-head cap {CURRENCY[market]} {cap}"
        reasoning = (
            f"Client entertainment at {CURRENCY[market]} {amount:.2f} for {attendees} attendees "
            f"({CURRENCY[market]} {per_head:.2f}/head) is within the per-head cap of {CURRENCY[market]} {cap}. "
            "Alcohol rules respected, all attendees named with org, ratio <=2:1, business purpose annotated — Green per §3.4."
        )
    elif target == "amber":
        per_head = cap * rng.uniform(1.00, 1.10)
        amount = _round_to_pence(per_head * attendees, market)
        clause = f"§3.4 Entertainment — {market} per-head cap {CURRENCY[market]} {cap} (110% boundary)"
        reasoning = (
            f"Client entertainment at {CURRENCY[market]} {per_head:.2f}/head is above the per-head cap "
            f"({CURRENCY[market]} {cap}) but at or below 110% of cap — Amber per §3.4, reviewer attention required."
        )
    else:  # red
        if market in ENT_ALCOHOL_PROHIBITED:
            per_head = cap * rng.uniform(0.7, 0.95)
            amount = _round_to_pence(per_head * attendees, market)
            clause = f"§3.4 Entertainment — {market} alcohol prohibited"
            reasoning = (
                f"Alcohol present on a {market} entertainment claim. Per §3.4 alcohol is prohibited in {market} entertainment; "
                "alcohol where prohibited (DE/IN) is a hard breach — Red, first-occurrence escalation."
            )
        else:
            per_head = cap * rng.uniform(1.15, 1.45)
            amount = _round_to_pence(per_head * attendees, market)
            clause = f"§3.4 Entertainment — {market} per-head cap {CURRENCY[market]} {cap} (above 110%)"
            reasoning = (
                f"Client entertainment at {CURRENCY[market]} {per_head:.2f}/head is above 110% of the per-head cap "
                f"({CURRENCY[market]} {cap}). Above 110% of per-head cap is a hard breach — Red per §3.4."
            )
    narrative = f"Client dinner at {vendor}, business-development discussion"
    return amount, vendor, attendees, narrative, reasoning, clause


def _gen_misc_claim(rng, target, market):
    cap = MISC_CONFERENCE_CAP[market]
    vendor = rng.choice(VENDORS[("miscellaneous", market)])
    attendees = 1
    if target == "green":
        amount = _round_to_pence(cap * rng.uniform(0.5, 0.92), market)
        clause = f"§3.5 Miscellaneous — {market} conference/training cap {CURRENCY[market]} {cap}"
        reasoning = (
            f"Conference fee of {CURRENCY[market]} {amount:.2f} is within the {market} conference/training cap "
            f"of {CURRENCY[market]} {cap}, vendor recognisable, business purpose annotated — Green per §3.5."
        )
    elif target == "amber":
        amount = _round_to_pence(cap * rng.uniform(1.00, 1.10), market)
        clause = f"§3.5 Miscellaneous — {market} conference cap {CURRENCY[market]} {cap} (110% boundary)"
        reasoning = (
            f"Conference fee of {CURRENCY[market]} {amount:.2f} is above the {market} conference/training cap "
            f"({CURRENCY[market]} {cap}) but at or below 110% of cap — Amber per §3.5, reviewer attention required."
        )
    else:  # red
        amount = _round_to_pence(cap * rng.uniform(1.15, 1.45), market)
        clause = f"§3.5 Miscellaneous — {market} conference cap {CURRENCY[market]} {cap} (above 110%)"
        reasoning = (
            f"Conference fee of {CURRENCY[market]} {amount:.2f} is above 110% of the {market} conference/training cap "
            f"({CURRENCY[market]} {cap}). Above 110% of cap is a hard breach — Red per §3.5."
        )
    narrative = f"Conference registration via {vendor}"
    return amount, vendor, attendees, narrative, reasoning, clause


_GENERATORS = {
    "meals": _gen_meals_claim,
    "travel": _gen_travel_claim,
    "accommodation": _gen_accommodation_claim,
    "entertainment": _gen_entertainment_claim,
    "miscellaneous": _gen_misc_claim,
}


def _label_for_index(i: int) -> str:
    """Stable 70/20/10 sequence by deterministic walk, not random sampling.

    indices 0-6 within each block of 10 → green   (7/10 = 70%)
    indices 7-8 within each block of 10 → amber   (2/10 = 20%)
    index 9 within each block of 10    → red     (1/10 = 10%)
    """
    r = i % 10
    if r <= 6:
        return "green"
    if r <= 8:
        return "amber"
    return "red"


def _pick_employee_for_market(rng, employees, market):
    pool = [e for e in employees if e["market"] == market]
    return rng.choice(pool)


def run(seed: int = 20260427, count: int = 300) -> None:
    rng = random.Random(seed)
    CLAIMS.mkdir(parents=True, exist_ok=True)
    employees = json.loads(EMPLOYEES.read_text(encoding="utf-8"))

    base_dt = datetime(2026, 4, 1)
    rows = []
    for i in range(count):
        target = _label_for_index(i)
        # Rotate categories and markets so all 5x4 cells always appear.
        category = CATEGORIES[i % len(CATEGORIES)]
        market = MARKETS[i % len(MARKETS)]
        employee = _pick_employee_for_market(rng, employees, market)

        amount, vendor, attendees, narrative, reasoning, clause = _GENERATORS[category](
            rng, target, market
        )

        claim_id = f"CLM-{i:04d}"
        # Deterministic submission timestamp: spread across April 2026.
        submitted = base_dt + timedelta(days=i // 10, hours=rng.randrange(8, 19),
                                        minutes=rng.randrange(0, 60))
        receipt_filename = f"{claim_id}.png"
        ems_source = EMS[i % len(EMS)]

        claim = {
            "claim_id": claim_id,
            "employee_id": employee["id"],
            "submitted_at": submitted.isoformat(),
            "market": market,
            "currency": CURRENCY[market],
            "category": category,
            "vendor": vendor,
            "amount": amount,
            "attendees": attendees,
            "narrative": narrative,
            "receipt_filename": receipt_filename,
            "ems_source": ems_source,
            "gold_label": target,
            "gold_reasoning": reasoning,
            "gold_policy_clause": clause,
        }

        out_path = CLAIMS / f"{claim_id}.json"
        out_path.write_text(
            json.dumps(claim, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        rows.append({
            "claim_id": claim_id,
            "category": category,
            "market": market,
            "amount": amount,
            "currency": CURRENCY[market],
            "gold_label": target,
            "gold_policy_clause": clause,
        })

    fieldnames = ["claim_id", "category", "market", "amount", "currency",
                  "gold_label", "gold_policy_clause"]
    with LABELS.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


if __name__ == "__main__":
    run()
    print(f"Wrote {len(list(CLAIMS.glob('CLM-*.json')))} claims to {CLAIMS}")
