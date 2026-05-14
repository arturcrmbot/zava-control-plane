"""Tests for api.server.data_fabric.asset_gen (pitch-b5)."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from api.server.data_fabric.asset_gen import (
    DEFAULT_SUBSIDIARIES,
    GeneratedAsset,
    generate_assets,
)


@dataclass(frozen=True)
class _FakeClient:
    id: str
    name: str
    tier: str = "enterprise"
    region: str = "UK"


@dataclass(frozen=True)
class _FakeBrand:
    id: str
    name: str
    client_id: str


def _fixture_pack() -> tuple[list[_FakeClient], list[_FakeBrand]]:
    clients = [
        _FakeClient(id=f"CLIENT-{i:02d}", name=f"Client {i}", tier="enterprise" if i < 3 else "mid")
        for i in range(1, 7)
    ]
    brands = []
    bn = 1
    for c in clients:
        for _ in range(2):  # 2 brands per client → 12 total
            brands.append(_FakeBrand(id=f"BRAND-{bn:03d}", name=f"Brand {bn}", client_id=c.id))
            bn += 1
    return clients, brands


def test_generate_assets_count_and_kind_distribution():
    clients, brands = _fixture_pack()
    assets = generate_assets(
        seed=7,
        brands=brands,
        clients=clients,
        subsidiaries=list(DEFAULT_SUBSIDIARIES),
        count=150,
    )
    assert len(assets) == 150

    targets = {
        "campaign": 45,
        "msa": 22,  # round(0.15*150)=22 or 23, allow ±5
        "sow": 22,
        "media-plan": 22,
        "brief": 15,
        "deck": 15,
        "asset-library": 8,  # round(0.05*150)=8, allow ±5
    }
    by_kind: dict[str, int] = {}
    for a in assets:
        by_kind[a.kind] = by_kind.get(a.kind, 0) + 1
    for kind, target in targets.items():
        actual = by_kind.get(kind, 0)
        assert abs(actual - target) <= 5, f"{kind}: expected ~{target}, got {actual}"


def test_generate_assets_fks_resolve():
    clients, brands = _fixture_pack()
    assets = generate_assets(
        seed=11,
        brands=brands,
        clients=clients,
        subsidiaries=list(DEFAULT_SUBSIDIARIES),
        count=150,
    )
    client_ids = {c.id for c in clients}
    brand_ids = {b.id for b in brands}
    sub_ids = set(DEFAULT_SUBSIDIARIES)
    brand_to_client = {b.id: b.client_id for b in brands}
    for a in assets:
        assert isinstance(a, GeneratedAsset)
        assert a.client_id in client_ids
        assert a.subsidiary_id in sub_ids
        if a.brand_id is not None:
            assert a.brand_id in brand_ids
            assert brand_to_client[a.brand_id] == a.client_id
        assert a.status in {"draft", "in-progress", "completed", "archived"}


def test_generate_assets_deterministic():
    clients, brands = _fixture_pack()
    a1 = generate_assets(seed=42, brands=brands, clients=clients, subsidiaries=list(DEFAULT_SUBSIDIARIES))
    a2 = generate_assets(seed=42, brands=brands, clients=clients, subsidiaries=list(DEFAULT_SUBSIDIARIES))
    assert a1 == a2


def test_generate_assets_requires_clients():
    with pytest.raises(ValueError):
        generate_assets(seed=1, brands=[], clients=[], subsidiaries=[])


def test_msa_assets_have_no_brand():
    clients, brands = _fixture_pack()
    assets = generate_assets(seed=3, brands=brands, clients=clients, subsidiaries=list(DEFAULT_SUBSIDIARIES))
    msas = [a for a in assets if a.kind == "msa"]
    assert msas, "expected some MSA rows"
    for a in msas:
        assert a.brand_id is None
