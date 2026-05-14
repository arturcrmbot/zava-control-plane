"""api/server/data_fabric/asset_gen.py — synthetic Asset generator.

Produces ~150 ``GeneratedAsset`` rows representing campaigns, MSAs,
SOWs, media plans, briefs, decks, and asset libraries — every asset
linked to a brand (where applicable), a client, and a Zava subsidiary.

Plan: plan/feature-enterprise-pitch-readiness-1.md (task ``pitch-b5``).
"""
from __future__ import annotations

import random
from dataclasses import dataclass

# 5 named subsidiaries — duplicated from employee_gen.py so this module
# stays importable even before the b1+b8 locale registry is wired.
DEFAULT_SUBSIDIARIES: tuple[str, ...] = (
    "ORG-zava-creative",
    "ORG-zava-media",
    "ORG-zava-production",
    "ORG-zava-data",
    "ORG-zava-group",
)

# Target distribution per asset kind (must sum to 1.0).
_KIND_DISTRIBUTION: tuple[tuple[str, float], ...] = (
    ("campaign", 0.30),
    ("msa", 0.15),
    ("sow", 0.15),
    ("media-plan", 0.15),
    ("brief", 0.10),
    ("deck", 0.10),
    ("asset-library", 0.05),
)

_STATUS_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("draft", 0.20),
    ("in-progress", 0.45),
    ("completed", 0.30),
    ("archived", 0.05),
)

# Whether the kind is brand-anchored. MSAs are negotiated at the client
# level and don't carry a brand_id; everything else does.
_KIND_HAS_BRAND: dict[str, bool] = {
    "campaign": True,
    "msa": False,
    "sow": True,
    "media-plan": True,
    "brief": True,
    "deck": True,
    "asset-library": True,
}

# Human-readable phrase fragments used to build the asset name.
_KIND_NAME_TEMPLATES: dict[str, str] = {
    "campaign": "{quarter} {brand} launch campaign",
    "msa": "{client} master services agreement",
    "sow": "{quarter} {brand} statement of work",
    "media-plan": "{quarter} {brand} media plan",
    "brief": "{brand} creative brief",
    "deck": "{brand} pitch deck",
    "asset-library": "{brand} asset library",
}

_QUARTERS: tuple[str, ...] = ("Q1", "Q2", "Q3", "Q4")


@dataclass(frozen=True)
class GeneratedAsset:
    id: str
    kind: str
    name: str
    brand_id: str | None
    client_id: str
    subsidiary_id: str
    status: str


def _per_kind_counts(count: int) -> dict[str, int]:
    """Round each share to the nearest int, then patch the largest bucket
    so the total exactly matches ``count``."""
    raw = {k: w * count for k, w in _KIND_DISTRIBUTION}
    rounded = {k: int(round(v)) for k, v in raw.items()}
    delta = count - sum(rounded.values())
    if delta != 0:
        # Adjust the bucket with the largest fractional residual (or the
        # campaign bucket as the natural default).
        biggest = max(rounded, key=lambda k: rounded[k])
        rounded[biggest] += delta
    return rounded


def _weighted_choice(rng: random.Random, choices: tuple[tuple[str, float], ...]) -> str:
    items = [c for c, _ in choices]
    weights = [w for _, w in choices]
    return rng.choices(items, weights=weights, k=1)[0]


def _attr(obj, name: str, default=None):
    """Tolerant attribute accessor — supports dataclasses, models, dicts."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def generate_assets(
    *,
    seed: int,
    brands: list,
    clients: list,
    subsidiaries: list[str],
    count: int = 150,
) -> list[GeneratedAsset]:
    """Materialise ``count`` deterministic Asset rows.

    ``brands`` is the list of GeneratedBrand-shaped objects from b4 (each
    must expose ``id``, ``name``, and ``client_id``). ``clients`` is the
    matching client list (each with ``id`` and ``name``). ``subsidiaries``
    is the 5-element subsidiary id list — falls back to
    ``DEFAULT_SUBSIDIARIES`` if empty.

    Output is sorted by id and fully deterministic for a given seed.
    """
    if not clients:
        raise ValueError("generate_assets requires at least one client")
    subs = tuple(subsidiaries) if subsidiaries else DEFAULT_SUBSIDIARIES

    rng = random.Random(seed)

    # Index brands by client_id so we can pick a brand belonging to the
    # asset's client (keeps the brand_id<->client_id link consistent).
    brands_by_client: dict[str, list] = {}
    for b in brands:
        cid = _attr(b, "client_id")
        if cid is None:
            continue
        brands_by_client.setdefault(cid, []).append(b)

    counts = _per_kind_counts(count)
    per_kind_counter: dict[str, int] = {k: 0 for k in counts}

    assets: list[GeneratedAsset] = []
    # Iterate kinds in declared (deterministic) order.
    for kind, _ in _KIND_DISTRIBUTION:
        target = counts[kind]
        for _ in range(target):
            client = clients[rng.randint(0, len(clients) - 1)]
            client_id = _attr(client, "id")
            client_name = _attr(client, "name", client_id)

            brand_id: str | None = None
            brand_name = client_name
            if _KIND_HAS_BRAND.get(kind, False):
                bucket = brands_by_client.get(client_id) or brands or []
                if bucket:
                    brand = bucket[rng.randint(0, len(bucket) - 1)]
                    brand_id = _attr(brand, "id")
                    brand_name = _attr(brand, "name", brand_id) or brand_name
                    # When the bucket came from another client, retarget
                    # the asset to the brand's actual client to keep the
                    # graph consistent.
                    bclient = _attr(brand, "client_id")
                    if bclient:
                        client_id = bclient
                        for c in clients:
                            if _attr(c, "id") == bclient:
                                client_name = _attr(c, "name", bclient)
                                break

            quarter = _QUARTERS[rng.randint(0, 3)]
            tmpl = _KIND_NAME_TEMPLATES[kind]
            name = tmpl.format(quarter=quarter, brand=brand_name, client=client_name)

            subsidiary_id = subs[len(assets) % len(subs)]
            status = _weighted_choice(rng, _STATUS_WEIGHTS)

            per_kind_counter[kind] += 1
            asset_id = f"ASSET-{kind}-{per_kind_counter[kind]:04d}"
            assets.append(
                GeneratedAsset(
                    id=asset_id,
                    kind=kind,
                    name=name,
                    brand_id=brand_id,
                    client_id=client_id,
                    subsidiary_id=subsidiary_id,
                    status=status,
                )
            )

    assets.sort(key=lambda a: a.id)
    return assets
