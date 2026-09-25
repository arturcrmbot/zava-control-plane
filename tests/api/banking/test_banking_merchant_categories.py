"""Merchant risk read from the merchant's own description (phase 2)."""
from __future__ import annotations

import asyncio
import importlib

import pytest

from api.server.services.judgement.laya_client import LayaAnswer, LayaResult, LayaUnavailable
from verticals.banking import merchant_categories as mc


def test_every_category_maps_to_a_band_in_code() -> None:
    assert set(mc.BAND_BY_CATEGORY) == set(mc.CATEGORY_QUESTION["category"]["criteria"])
    assert mc.BAND_BY_CATEGORY["unclear"] == "medium"
    assert {mc.BAND_BY_CATEGORY[c] for c in ("crypto_or_gambling", "prepaid_future")} == {"high"}


def test_the_rules_read_most_authored_descriptions() -> None:
    right = sum(mc.rules_category(text) == truth for text, truth in mc.DESCRIPTIONS)
    assert right >= len(mc.DESCRIPTIONS) - 2


class _Client:
    enabled = True

    def __init__(self, top: str, lead: float, *, fail: bool = False) -> None:
        self.top, self.lead, self.fail = top, lead, fail

    def available(self) -> bool:
        return True

    async def ask(self, state, questions):
        if self.fail:
            raise LayaUnavailable("down")
        probs = {self.top: 0.5 + self.lead / 2, "unclear": 0.5 - self.lead / 2}
        return LayaResult({"category": LayaAnswer("choice", probs, self.top, self.lead)}, 30.0, 31.0)


@pytest.mark.parametrize(
    ("client", "expected"),
    [
        (_Client("crypto_or_gambling", 0.63), ("crypto_or_gambling", "high", "laya")),
        (_Client("online_goods", 0.1), ("unclear", "medium", "laya")),
        (_Client("online_goods", 0.9, fail=True), ("crypto_or_gambling", "high", "rules")),
    ],
)
def test_categorise_reads_with_laya_and_falls_back_to_rules(client, expected) -> None:
    reading = asyncio.run(mc.categorise("Crypto exchange for retail traders", client=client))
    assert (reading.category, reading.band, reading.by) == expected


@pytest.fixture
def spawner(monkeypatch):
    from api.server.state import app_state
    from verticals.banking import spawners

    scheduled: list[dict] = []

    async def schedule(payload, function_name):
        scheduled.append(payload)
        return {"id": "inst-merchant"}

    monkeypatch.setattr(spawners, "schedule_new_orchestration", schedule)
    monkeypatch.setattr(app_state.store, "upsert_workflow", lambda w: None)
    return spawners, scheduled


def test_with_screening_on_a_merchant_application_is_read_from_its_description(spawner, monkeypatch) -> None:
    spawners, scheduled = spawner
    monkeypatch.setenv("BANKING_WORLD_SCREENING", "1")
    monkeypatch.delenv("BANKING_WORLD_LIFE", raising=False)

    async def categorise(description, client=None):
        return mc.Reading("subscriptions", "medium", 0.99, "laya")

    monkeypatch.setattr(spawners, "categorise", categorise)
    asyncio.run(spawners.spawn_merchant_onboarding_workflow())
    case = scheduled[-1]["case"]
    assert case["description"] in {text for text, _ in mc.DESCRIPTIONS}
    assert (case["risk_band"], case["sector"], case["categorised_by"], case["category_lead"]) == (
        "medium", "subscriptions", "laya", 0.99)


def test_with_screening_off_a_merchant_application_is_as_before(spawner, monkeypatch) -> None:
    spawners, scheduled = spawner
    monkeypatch.delenv("BANKING_WORLD_SCREENING", raising=False)
    monkeypatch.delenv("BANKING_WORLD_LIFE", raising=False)
    asyncio.run(spawners.spawn_merchant_onboarding_workflow())
    case = scheduled[-1]["case"]
    assert set(case) == {"id", "subject_id", "subject_kind", "risk_band", "sector",
                         "projected_monthly_volume_gbp", "version"}
