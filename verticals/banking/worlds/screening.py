"""Screening payment references: the bank reads what customers wrote.

Laya matches a reference to one of a few described scam patterns (the domain
knowledge lives in the options, which measured 16/16 on clear references
against 9/16 for a bare "is this a scam?"). A match needs a clear lead to flag
a payment; an unclear answer flags nothing and spends nothing.

The world never waits on the model. A cached reference applies at once; a new
one is read on an asyncio task and the world publishes the result on its next
step. With no running loop (tests, the Functions worker) or with Laya down,
keyword rules decide, and every screening says which of the two read it.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable

from api.server.services.judgement.laya_client import LayaClient, LayaUnavailable, get_client

FLAG_PATTERNS = frozenset({"safe_account", "authority_demand", "unlock_fee", "high_returns"})
MIN_LEAD = 0.25

PATTERN_QUESTION: dict[str, Any] = {
    "pattern": {
        "type": "choice",
        "instructions": "Which description matches this payment reference?",
        "criteria": {
            "safe_account": "Moving money to a safe account to protect it",
            "authority_demand": "Paying a penalty, fine or demand from tax office, police or courts",
            "unlock_fee": "Paying a fee to release money, a parcel, a loan or a prize",
            "high_returns": "Investing for guaranteed or very high returns",
            "ordinary": "An ordinary bill, purchase, wage, gift or subscription",
            "unclear": "None of these clearly fits",
        },
    }
}

_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("safe_account", ("safe account", "secure account", "protected account", "funds protection")),
    ("authority_demand", ("hmrc", "penalty", "court fine", "police case", "tax refund")),
    ("unlock_fee", ("release fee", "unlock", "admin fee", "processing fee", "customs fee", "fee before payout",
                    "fee to release", "verification transfer")),
    ("high_returns", ("guaranteed", "percent weekly", "percent monthly", "crypto", "bitcoin", "forex")),
)


@dataclass(frozen=True, slots=True)
class Screening:
    pattern: str
    lead: float
    by: str

    @property
    def flagged(self) -> bool:
        return self.pattern in FLAG_PATTERNS and (self.by == "rules" or self.lead >= MIN_LEAD)

    def to_dict(self) -> dict[str, Any]:
        return {"pattern": self.pattern, "lead": round(self.lead, 3), "screened_by": self.by}


def rules_screen(reference: str) -> Screening:
    text = reference.lower()
    for pattern, words in _KEYWORDS:
        if any(word in text for word in words):
            return Screening(pattern, 1.0, "rules")
    return Screening("ordinary", 1.0, "rules")


Callback = Callable[[Screening], None]


class RulesScreener:
    def submit(self, reference: str, callback: Callback) -> None:
        callback(rules_screen(reference))


class LayaScreener:
    def __init__(self, *, client_factory: Callable[[], LayaClient] = get_client) -> None:
        self._client_factory = client_factory
        self._cache: dict[str, Screening] = {}
        self._waiting: dict[str, list[Callback]] = {}

    def submit(self, reference: str, callback: Callback) -> None:
        cached = self._cache.get(reference)
        if cached is not None:
            callback(cached)
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            callback(rules_screen(reference))
            return
        client = self._client_factory()
        if not client.available():
            callback(rules_screen(reference))
            return
        waiting = self._waiting.setdefault(reference, [])
        waiting.append(callback)
        if len(waiting) == 1:
            loop.create_task(self._read(reference, client))

    async def _read(self, reference: str, client: LayaClient) -> None:
        try:
            result = await client.ask({"payment_reference": reference}, PATTERN_QUESTION)
            answer = result.answers["pattern"]
            screening = Screening(answer.top, answer.lead, "laya")
            self._cache[reference] = screening
        except LayaUnavailable:
            screening = rules_screen(reference)  # not cached: Laya is asked again next time
        for callback in self._waiting.pop(reference, []):
            callback(screening)


def default_screener() -> LayaScreener | RulesScreener:
    return LayaScreener() if get_client().enabled else RulesScreener()
