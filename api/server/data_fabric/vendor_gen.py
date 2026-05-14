"""Vendor generator — ~50 Org nodes representing the supplier side of an
agency holding company (production houses, freelancers, software vendors,
ad-tech, research, talent agencies).

Per plan/feature-enterprise-pitch-readiness-1.md task pitch-b3.

The generator is fully deterministic: same ``seed`` ⇒ same vendor list,
byte-for-byte. It performs no I/O and has no runtime dependency on user
data — output feeds the Plane-1 entity graph at demo-seed time.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass

from faker import Faker

__all__ = ["GeneratedVendor", "generate_vendors"]


# --- Distribution targets -----------------------------------------------------

_SUBKIND_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("production", 0.30),
    ("freelancer", 0.20),
    ("software", 0.15),
    ("ad-tech", 0.15),
    ("research", 0.10),
    ("talent-agency", 0.10),
)

_RISK_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("green", 0.70),
    ("amber", 0.25),
    ("red", 0.05),
)

_PAYMENT_TERMS = (14, 30, 45, 60, 90)
_ESG_RATINGS = ("A", "B", "C", "D")

_COUNTRIES = (
    "UK", "UK", "UK", "UK",                    # agency HQ-adjacent skew
    "US", "US", "US",
    "DE", "FR", "NL", "ES", "IT", "IE", "PL",
    "CA", "AU", "JP", "SG", "IN", "BR",
)


@dataclass(frozen=True)
class GeneratedVendor:
    """Single vendor Org node ready to feed the entity graph."""

    id: str
    name: str
    kind: str
    subkind: str
    country: str
    risk_band: str
    payment_terms_days: int
    esg_rating: str
    is_blocked: bool


# --- Helpers ------------------------------------------------------------------

def _slugify(value: str) -> str:
    """Lower-kebab slug stripped of punctuation. Stable for a given input."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "vendor"


def _allocate_counts(count: int, weights: tuple[tuple[str, float], ...]) -> dict[str, int]:
    """Deterministically split ``count`` across ``weights`` so that the totals
    sum exactly to ``count``. Largest-remainder allocation."""
    raw = [(label, weight * count) for label, weight in weights]
    floors = {label: int(value) for label, value in raw}
    remainder = count - sum(floors.values())
    # Distribute leftover units to the labels with the largest fractional part.
    leftovers = sorted(
        ((value - int(value), label) for label, value in raw),
        reverse=True,
    )
    for _, label in leftovers[:remainder]:
        floors[label] += 1
    return floors


def _name_for(subkind: str, fake: Faker) -> str:
    if subkind == "freelancer":
        return f"{fake.name()} (Freelance)"
    return fake.company()


# --- Public API ---------------------------------------------------------------

def generate_vendors(*, seed: int = 42, count: int = 50) -> list[GeneratedVendor]:
    """Return a deterministic list of synthetic vendor Org nodes.

    Distribution targets:
      * subkind: 30% production / 20% freelancer / 15% software /
        15% ad-tech / 10% research / 10% talent-agency
      * risk_band: 70% green / 25% amber / 5% red
      * ~3 of the red-band vendors are flagged ``is_blocked=True`` to
        represent recent KYC failures.
    """
    if count < 1:
        return []

    fake = Faker()
    Faker.seed(seed)
    rng = random.Random(seed)

    subkind_counts = _allocate_counts(count, _SUBKIND_WEIGHTS)
    risk_counts = _allocate_counts(count, _RISK_WEIGHTS)

    # Materialise per-vendor subkind / risk label arrays then shuffle so the
    # two dimensions decorrelate but their marginals stay exact.
    subkinds: list[str] = []
    for label, n in subkind_counts.items():
        subkinds.extend([label] * n)
    risks: list[str] = []
    for label, n in risk_counts.items():
        risks.extend([label] * n)
    rng.shuffle(subkinds)
    rng.shuffle(risks)

    # Decide which red-band vendors get the KYC-failure block. Target ~3.
    red_indices = [i for i, r in enumerate(risks) if r == "red"]
    blocked_target = min(len(red_indices), 3)
    blocked_set = set(rng.sample(red_indices, blocked_target)) if blocked_target else set()

    vendors: list[GeneratedVendor] = []
    used_ids: set[str] = set()
    for idx in range(count):
        subkind = subkinds[idx]
        risk = risks[idx]
        name = _name_for(subkind, fake)
        slug = _slugify(name)
        candidate = f"ORG-vendor-{slug}"
        # Faker can repeat company names; suffix on collision to keep ids unique.
        bumped = candidate
        suffix = 2
        while bumped in used_ids:
            bumped = f"{candidate}-{suffix}"
            suffix += 1
        used_ids.add(bumped)

        vendors.append(
            GeneratedVendor(
                id=bumped,
                name=name,
                kind="vendor",
                subkind=subkind,
                country=rng.choice(_COUNTRIES),
                risk_band=risk,
                payment_terms_days=rng.choice(_PAYMENT_TERMS),
                esg_rating=rng.choice(_ESG_RATINGS),
                is_blocked=idx in blocked_set,
            )
        )
    return vendors
