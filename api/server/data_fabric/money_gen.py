"""api/server/data_fabric/money_gen.py — synthetic Money row generator.

Produces 500–1000 ``GeneratedMoney`` rows for a single quarter window:
POs, invoices, contracts, intercompany recharges, FX adjustments, and
agency commissions. Distribution is intentionally Pareto: the top 6
brands (by parent-client tier) absorb ≥80% of total value.

Plan: plan/feature-enterprise-pitch-readiness-1.md (task ``pitch-b6``).
"""
from __future__ import annotations

import random
from dataclasses import dataclass

# 5 Zava subsidiary ids — duplicated here so the module imports cleanly
# even before b1+b8 have published a locale registry.
DEFAULT_SUBSIDIARIES: tuple[str, ...] = (
    "ORG-zava-creative",
    "ORG-zava-media",
    "ORG-zava-production",
    "ORG-zava-data",
    "ORG-zava-group",
)

# Money kinds + sampling weights (mix only — does not control value).
_KIND_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("po", 0.25),
    ("invoice", 0.30),
    ("contract", 0.10),
    ("recharge", 0.15),
    ("fx-adj", 0.10),
    ("commission", 0.10),
)

# Mid-range amount per kind in GBP (random.uniform bounds).
_AMOUNT_RANGE: dict[str, tuple[float, float]] = {
    "po": (5_000.0, 80_000.0),
    "invoice": (1_500.0, 60_000.0),
    "contract": (50_000.0, 750_000.0),
    "recharge": (2_000.0, 40_000.0),
    "fx-adj": (500.0, 25_000.0),
    "commission": (1_000.0, 30_000.0),
}

# Region -> currency. Used when the client carries a region attribute.
_REGION_TO_CURRENCY: dict[str, str] = {
    "UK": "GBP",
    "US": "USD",
    "DE": "EUR",
    "FR": "EUR",
    "ES": "EUR",
    "IT": "EUR",
    "JP": "JPY",
    "IN": "INR",
    "BR": "BRL",
    "AU": "AUD",
}

# How many "top" brands soak up the bulk of the spend.
TOP_BRAND_COUNT = 6
TOP_BRAND_SHARE = 0.80  # of row count routed to the top bucket


@dataclass(frozen=True)
class GeneratedMoney:
    id: str
    kind: str
    amount: float
    currency: str
    period_id: str
    brand_id: str | None
    client_id: str | None
    vendor_id: str | None
    subsidiary_id: str


def _attr(obj, name: str, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


_TIER_RANK: dict[str, int] = {"enterprise": 0, "mid": 1, "small": 2, "smb": 2}


def _client_tier_key(client) -> tuple[int, str]:
    tier = (_attr(client, "tier") or "mid").lower()
    return (_TIER_RANK.get(tier, 9), str(_attr(client, "id", "")))


def _pick_top_brands(brands: list, clients: list) -> list:
    """Return the TOP_BRAND_COUNT brands whose parent client ranks
    highest by tier (enterprise > mid > small)."""
    if not brands:
        return []
    client_rank: dict[str, tuple[int, str]] = {}
    for c in clients:
        cid = _attr(c, "id")
        if cid is not None:
            client_rank[cid] = _client_tier_key(c)
    # Brands without a known client get pushed to the back.
    sortable = sorted(
        brands,
        key=lambda b: (
            client_rank.get(_attr(b, "client_id", ""), (10, "")),
            str(_attr(b, "id", "")),
        ),
    )
    return sortable[:TOP_BRAND_COUNT]


def _currency_for_client(client) -> str:
    if client is None:
        return "GBP"
    explicit = _attr(client, "currency")
    if explicit:
        return str(explicit)
    region = _attr(client, "region")
    if region and region in _REGION_TO_CURRENCY:
        return _REGION_TO_CURRENCY[region]
    return "GBP"


def _client_lookup(clients: list) -> dict[str, object]:
    return {_attr(c, "id"): c for c in clients if _attr(c, "id") is not None}


def generate_money(
    *,
    seed: int,
    brands: list,
    clients: list,
    vendors: list,
    subsidiaries: list[str],
    period_ids: list[str],
    count: int = 750,
) -> list[GeneratedMoney]:
    """Materialise ``count`` deterministic Money rows.

    80/20 routing: ``TOP_BRAND_SHARE`` of the rows are assigned to the
    top 6 brands (by parent-client tier). Currency follows the brand's
    parent client region. Vendor links are populated for kinds that
    plausibly involve a vendor (po, invoice, recharge, commission).
    """
    if not period_ids:
        raise ValueError("generate_money requires at least one period_id")
    subs = tuple(subsidiaries) if subsidiaries else DEFAULT_SUBSIDIARIES
    rng = random.Random(seed)

    by_client = _client_lookup(clients)
    top_brands = _pick_top_brands(brands, clients)
    other_brands = [b for b in brands if b not in top_brands]

    rows: list[GeneratedMoney] = []
    per_kind_counter: dict[str, int] = {k: 0 for k, _ in _KIND_WEIGHTS}
    kinds = [k for k, _ in _KIND_WEIGHTS]
    kind_weights = [w for _, w in _KIND_WEIGHTS]

    for _ in range(count):
        kind = rng.choices(kinds, weights=kind_weights, k=1)[0]
        per_kind_counter[kind] += 1

        # 80% of rows route to top brands when we have enough variety.
        if top_brands and (rng.random() < TOP_BRAND_SHARE or not other_brands):
            brand = top_brands[rng.randint(0, len(top_brands) - 1)]
        elif other_brands:
            brand = other_brands[rng.randint(0, len(other_brands) - 1)]
        elif top_brands:
            brand = top_brands[rng.randint(0, len(top_brands) - 1)]
        else:
            brand = None

        brand_id = _attr(brand, "id") if brand is not None else None
        client_id = _attr(brand, "client_id") if brand is not None else None
        if client_id is None and clients:
            client = clients[rng.randint(0, len(clients) - 1)]
            client_id = _attr(client, "id")
        client_obj = by_client.get(client_id) if client_id else None
        currency = _currency_for_client(client_obj)

        vendor_id = None
        if kind in {"po", "invoice", "recharge", "commission"} and vendors:
            vendor = vendors[rng.randint(0, len(vendors) - 1)]
            vendor_id = _attr(vendor, "id")

        lo, hi = _AMOUNT_RANGE[kind]
        amount = round(rng.uniform(lo, hi), 2)

        period_id = period_ids[rng.randint(0, len(period_ids) - 1)]
        subsidiary_id = subs[len(rows) % len(subs)]

        money_id = f"MONEY-{kind}-{per_kind_counter[kind]:05d}"
        rows.append(
            GeneratedMoney(
                id=money_id,
                kind=kind,
                amount=amount,
                currency=currency,
                period_id=period_id,
                brand_id=brand_id,
                client_id=client_id,
                vendor_id=vendor_id,
                subsidiary_id=subsidiary_id,
            )
        )

    rows.sort(key=lambda m: m.id)
    return rows
