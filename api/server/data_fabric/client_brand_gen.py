"""Client + Brand generator — 6 holding clients with ~10 brands between
them, drawn from hand-curated holding-name and brand-name pools.

Per plan/feature-enterprise-pitch-readiness-1.md task pitch-b4.

Distribution (deterministic for a given seed):
  * 6 clients: 2 enterprise, 3 mid-market, 1 smb
  * brands per client: 2 (each enterprise), 1–2 (each mid-market), 1 (smb)
    ⇒ ~10 brands total
  * annual budget by tier:
      enterprise   £5–20M
      mid-market   £1–5M
      smb          £100k–500k
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass

__all__ = [
    "GeneratedClient",
    "GeneratedBrand",
    "generate_clients_and_brands",
]


# --- Hand-curated pools -------------------------------------------------------

# Plausible-looking fictional holding-company names. Order is fixed so the
# deterministic shuffle in generate_clients_and_brands stays stable.
_CLIENT_NAME_POOL: tuple[str, ...] = (
    "Globex Corporation",
    "Acme Holdings",
    "Initech Group",
    "Northwind Traders",
    "Umbrella Worldwide",
    "Stark Industries",
    "Wayne Enterprises",
    "Wonka Industries",
    "Soylent Group",
    "Tyrell Holdings",
    "Cyberdyne Systems",
    "Hooli Inc",
    "Pied Piper Holdings",
    "Massive Dynamic",
    "Vandelay Industries",
)

# Brand-name pool: each brand can be assigned to any tier/industry. We sample
# without replacement so brand names stay unique within a single run.
_BRAND_NAME_POOL: tuple[str, ...] = (
    "Aurora", "Beacon", "Cascade", "Drift", "Ember",
    "Flint", "Glide", "Halcyon", "Iris", "Junction",
    "Keystone", "Lumen", "Meridian", "Nimbus", "Onyx",
    "Pulse", "Quartz", "Reverie", "Solace", "Tide",
    "Umbra", "Vertex", "Willow", "Xenon", "Yonder",
    "Zephyr", "Atlas", "Brio", "Citrine", "Daze",
)

_INDUSTRIES: tuple[str, ...] = (
    "fmcg", "pharma", "fintech", "auto", "retail", "tech",
)

_REGIONS: tuple[str, ...] = ("EMEA", "AMER", "APAC", "LATAM")

_MARKET_SEGMENTS: tuple[str, ...] = ("mass", "premium", "niche")

# Tier composition is exact (totals exactly 6).
_TIER_COMPOSITION: tuple[tuple[str, int], ...] = (
    ("enterprise", 2),
    ("mid-market", 3),
    ("smb", 1),
)

# Tier → annual revenue range (GBP).
_REVENUE_RANGE: dict[str, tuple[float, float]] = {
    "enterprise": (250_000_000.0, 5_000_000_000.0),
    "mid-market": (50_000_000.0, 250_000_000.0),
    "smb":        (5_000_000.0, 50_000_000.0),
}

# Tier → annual brand budget range (GBP). Drives _budget_for().
_BUDGET_RANGE: dict[str, tuple[float, float]] = {
    "enterprise": (5_000_000.0, 20_000_000.0),
    "mid-market": (1_000_000.0, 5_000_000.0),
    "smb":        (100_000.0, 500_000.0),
}


@dataclass(frozen=True)
class GeneratedClient:
    id: str
    name: str
    tier: str
    industry: str
    region: str
    annual_revenue_gbp: float


@dataclass(frozen=True)
class GeneratedBrand:
    id: str
    name: str
    client_id: str
    annual_budget_gbp: float
    market_segment: str


# --- Helpers ------------------------------------------------------------------

def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "client"


def _money(rng: random.Random, low: float, high: float) -> float:
    """Sample within [low, high] and round to the nearest £1k for tidy demos."""
    raw = rng.uniform(low, high)
    return round(raw / 1000.0) * 1000.0


def _brands_for_tier(tier: str, rng: random.Random) -> int:
    if tier == "enterprise":
        return 2
    if tier == "mid-market":
        return rng.choice((1, 2))
    return 1  # smb


# --- Public API ---------------------------------------------------------------

def generate_clients_and_brands(
    *,
    seed: int = 42,
    client_count: int = 6,
) -> tuple[list[GeneratedClient], list[GeneratedBrand]]:
    """Return deterministic (clients, brands) lists.

    ``client_count`` defaults to 6 with the documented 2/3/1 tier split.
    Other counts scale the tiers proportionally using largest-remainder
    allocation; the 2/3/1 invariant is preserved at the default.
    """
    if client_count < 1:
        return [], []

    rng = random.Random(seed)

    # Tier assignment.
    if client_count == 6:
        tiers: list[str] = []
        for label, n in _TIER_COMPOSITION:
            tiers.extend([label] * n)
    else:
        # Proportional fallback for non-default counts.
        raw = [(label, n / 6 * client_count) for label, n in _TIER_COMPOSITION]
        floors = {label: int(value) for label, value in raw}
        remainder = client_count - sum(floors.values())
        leftovers = sorted(
            ((value - int(value), label) for label, value in raw),
            reverse=True,
        )
        for _, label in leftovers[:remainder]:
            floors[label] += 1
        tiers = []
        for label in ("enterprise", "mid-market", "smb"):
            tiers.extend([label] * floors[label])

    # Pick deterministic client names without replacement.
    name_pool = list(_CLIENT_NAME_POOL)
    rng.shuffle(name_pool)
    if client_count > len(name_pool):
        raise ValueError(
            f"client_count={client_count} exceeds curated pool size {len(name_pool)}"
        )
    chosen_names = name_pool[:client_count]

    clients: list[GeneratedClient] = []
    used_client_ids: set[str] = set()
    for name, tier in zip(chosen_names, tiers):
        slug = _slugify(name)
        candidate = f"ORG-client-{slug}"
        bumped = candidate
        suffix = 2
        while bumped in used_client_ids:
            bumped = f"{candidate}-{suffix}"
            suffix += 1
        used_client_ids.add(bumped)

        rev_low, rev_high = _REVENUE_RANGE[tier]
        clients.append(
            GeneratedClient(
                id=bumped,
                name=name,
                tier=tier,
                industry=rng.choice(_INDUSTRIES),
                region=rng.choice(_REGIONS),
                annual_revenue_gbp=_money(rng, rev_low, rev_high),
            )
        )

    # Brand pool sampled without replacement, in shuffled order.
    brand_pool = list(_BRAND_NAME_POOL)
    rng.shuffle(brand_pool)
    brand_cursor = 0

    brands: list[GeneratedBrand] = []
    used_brand_ids: set[str] = set()
    for client in clients:
        n_brands = _brands_for_tier(client.tier, rng)
        if brand_cursor + n_brands > len(brand_pool):
            raise ValueError("brand pool exhausted; widen _BRAND_NAME_POOL")
        for _ in range(n_brands):
            bname = brand_pool[brand_cursor]
            brand_cursor += 1
            slug = _slugify(bname)
            candidate = f"BRAND-{slug}"
            bumped = candidate
            suffix = 2
            while bumped in used_brand_ids:
                bumped = f"{candidate}-{suffix}"
                suffix += 1
            used_brand_ids.add(bumped)

            b_low, b_high = _BUDGET_RANGE[client.tier]
            brands.append(
                GeneratedBrand(
                    id=bumped,
                    name=bname,
                    client_id=client.id,
                    annual_budget_gbp=_money(rng, b_low, b_high),
                    market_segment=rng.choice(_MARKET_SEGMENTS),
                )
            )

    return clients, brands
