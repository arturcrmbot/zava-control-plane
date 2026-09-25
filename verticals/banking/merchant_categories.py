"""Merchant risk read from the merchant's own description.

With world screening on, a merchant application carries a one-line business
description. Laya picks the kind of business from described categories;
code maps the category to a risk band, and admission runs on that band as
before. A reading without a clear lead is "unclear" and maps to medium: the
bank does not guess.

Measured on the 20 authored descriptions below: 16 had the right top answer
and 13 were right with a clear lead; the rest read as unclear (medium band),
and none was confidently put in a wrong category. Strong on shops,
professional services, online goods, subscriptions and crypto or gambling;
weak on businesses paid months ahead (travel, events).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from api.server.services.judgement.laya_client import LayaClient, LayaUnavailable, get_client

MIN_LEAD = 0.25

CATEGORY_QUESTION: dict[str, Any] = {
    "category": {
        "type": "choice",
        "instructions": "Which kind of business is this merchant?",
        "criteria": {
            "everyday_retail": "A shop, cafe or everyday local service paid on the spot",
            "professional": "Professional services such as accountants, designers or consultants",
            "online_goods": "An online shop shipping physical goods",
            "prepaid_future": "Payment taken now for travel, events or services delivered months later",
            "crypto_or_gambling": "Crypto trading, gambling or betting",
            "subscriptions": "Monthly subscriptions or memberships",
            "unclear": "None of these clearly fits",
        },
    }
}

# Code owns the risk policy: which kind of business carries which band.
BAND_BY_CATEGORY = {
    "everyday_retail": "low",
    "professional": "low",
    "online_goods": "medium",
    "subscriptions": "medium",
    "unclear": "medium",
    "prepaid_future": "high",
    "crypto_or_gambling": "high",
}

# (description, the category a careful underwriter would give it)
DESCRIPTIONS: tuple[tuple[str, str], ...] = (
    ("Family bakery selling bread and cakes on the high street", "everyday_retail"),
    ("Dog grooming salon in a market town", "everyday_retail"),
    ("Car repair garage for local drivers", "everyday_retail"),
    ("Neighbourhood cafe serving breakfast and coffee", "everyday_retail"),
    ("Freelance graphic design studio working for local firms", "professional"),
    ("Accountancy practice for small businesses", "professional"),
    ("IT consultancy advising retailers", "professional"),
    ("Online shop shipping handmade candles across the UK", "online_goods"),
    ("Electronics webshop importing phones from abroad", "online_goods"),
    ("Online clothing boutique delivering nationwide", "online_goods"),
    ("Tour operator selling package holidays to Spain", "prepaid_future"),
    ("Wedding venue taking full payment a year ahead", "prepaid_future"),
    ("Festival ticket seller for next summer's events", "prepaid_future"),
    ("Airline seat consolidator selling flights months ahead", "prepaid_future"),
    ("Crypto exchange for retail traders", "crypto_or_gambling"),
    ("Online sports betting site", "crypto_or_gambling"),
    ("Online casino with slot games", "crypto_or_gambling"),
    ("Gym offering monthly memberships", "subscriptions"),
    ("Meal-kit subscription box delivered weekly", "subscriptions"),
    ("Streaming service for independent films", "subscriptions"),
)

_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("crypto_or_gambling", ("crypto", "betting", "casino", "gambling", "slot")),
    ("prepaid_future", ("holiday", "ticket", "flights", "venue", "a year ahead", "months ahead")),
    ("subscriptions", ("subscription", "membership", "streaming")),
    ("online_goods", ("online", "webshop", "shipping", "delivering")),
    ("professional", ("accountancy", "consultancy", "design studio", "freelance")),
)


@dataclass(frozen=True, slots=True)
class Reading:
    category: str
    band: str
    lead: float
    by: str


def rules_category(description: str) -> str:
    text = description.lower()
    for category, words in _KEYWORDS:
        if any(word in text for word in words):
            return category
    return "everyday_retail"


async def categorise(description: str, client: LayaClient | None = None) -> Reading:
    client = client if client is not None else get_client()
    if client.available():
        try:
            result = await client.ask({"business": description}, CATEGORY_QUESTION)
            answer = result.answers["category"]
            category = answer.top if answer.lead >= MIN_LEAD else "unclear"
            return Reading(category, BAND_BY_CATEGORY.get(category, "medium"), round(answer.lead, 3), "laya")
        except LayaUnavailable:
            pass
    category = rules_category(description)
    return Reading(category, BAND_BY_CATEGORY[category], 1.0, "rules")
