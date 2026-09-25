"""Customers react to decisions: the world's customers are not silent.

After a reimbursement decision is applied, Laya rates how upset the customer
is on a four-level scale. Measured, it orders outcomes sensibly: full refund
0.27-0.35 < partial 0.69-0.90 < refusal 0.99-1.30, whereas a yes/no "would they
complain?" stayed flat. The world then draws the customer's reaction from that
distribution with its own seeded stream, so reactions vary for grounded
reasons rather than fixed ones.

As with screening, the world never waits: a known situation is answered from
the cache, a new one on an asyncio task. With no loop or with Laya down, rules
by outcome decide (full -> accepts, capped -> chases, refused -> complains),
and every reaction says which decided.
"""
from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Any, Callable

from api.server.services.judgement.laya_client import LayaClient, LayaUnavailable, get_client
from verticals.banking.fraud_constraints import (
    OPTION_REFUSE_CAUTION,
    OPTION_REIMBURSE_CAPPED,
)

REACTIONS = ("accepts", "chases", "complains")

UPSET_QUESTION: dict[str, Any] = {
    "upset": {
        "type": "score",
        "instructions": "How upset is the customer with this decision?",
        "criteria": ["Satisfied", "Mildly unhappy", "Upset", "Furious"],
    }
}

DECISION_WORDS = {
    "full": "The bank reimbursed the full amount within two days.",
    "capped": "The bank reimbursed only part of the claim, up to the reimbursement cap.",
    "refused": "The bank refused the claim because the customer ignored a specific warning.",
}

# How each upset level tends to show: P(accepts), P(chases), P(complains).
_LEVEL_ODDS = (
    (1.0, 0.0, 0.0),   # satisfied
    (0.6, 0.4, 0.0),   # mildly unhappy
    (0.1, 0.5, 0.4),   # upset
    (0.0, 0.2, 0.8),   # furious
)
_RULE_LEVELS = {"full": (1.0, 0.0, 0.0, 0.0), "capped": (0.0, 0.0, 1.0, 0.0), "refused": (0.0, 0.0, 0.0, 1.0)}
_RULE_ODDS = {"full": "accepts", "capped": "chases", "refused": "complains"}


@dataclass(frozen=True, slots=True)
class Mood:
    levels: tuple[float, float, float, float]
    score: float
    by: str
    rule: str | None = None


def decision_kind(option_id: str) -> str:
    if option_id == OPTION_REFUSE_CAUTION:
        return "refused"
    if option_id == OPTION_REIMBURSE_CAPPED:
        return "capped"
    return "full"


def reaction_odds(mood: Mood) -> dict[str, float]:
    if mood.by == "rules" and mood.rule:
        return {reaction: 1.0 if reaction == _RULE_ODDS[mood.rule] else 0.0 for reaction in REACTIONS}
    total = sum(mood.levels) or 1.0
    odds = [0.0, 0.0, 0.0]
    for weight, level in zip(mood.levels, _LEVEL_ODDS):
        for index in range(3):
            odds[index] += (weight / total) * level[index]
    return dict(zip(REACTIONS, odds))


def draw(odds: dict[str, float], rng: random.Random) -> str:
    roll = rng.random()
    running = 0.0
    for reaction in REACTIONS:
        running += odds.get(reaction, 0.0)
        if roll < running:
            return reaction
    return max(odds, key=odds.get)


def rules_mood(kind: str) -> Mood:
    levels = _RULE_LEVELS[kind]
    return Mood(levels, float(sum(i * v for i, v in enumerate(levels))), "rules", rule=kind)


Callback = Callable[[Mood], None]


class RulesReactor:
    def submit(self, customer: str, decision: str, kind: str, callback: Callback) -> None:
        callback(rules_mood(kind))


class LayaReactor:
    def __init__(self, *, client_factory: Callable[[], LayaClient] = get_client) -> None:
        self._client_factory = client_factory
        self._cache: dict[tuple[str, str], Mood] = {}
        self._waiting: dict[tuple[str, str], list[Callback]] = {}

    def submit(self, customer: str, decision: str, kind: str, callback: Callback) -> None:
        key = (customer, decision)
        cached = self._cache.get(key)
        if cached is not None:
            callback(cached)
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            callback(rules_mood(kind))
            return
        client = self._client_factory()
        if not client.available():
            callback(rules_mood(kind))
            return
        waiting = self._waiting.setdefault(key, [])
        waiting.append(callback)
        if len(waiting) == 1:
            loop.create_task(self._read(key, kind, client))

    async def _read(self, key: tuple[str, str], kind: str, client: LayaClient) -> None:
        customer, decision = key
        try:
            result = await client.ask({"customer": customer, "decision": decision}, UPSET_QUESTION)
            answer = result.answers["upset"]
            levels = tuple(float(answer.probabilities.get(str(i), 0.0)) for i in range(4))
            mood = Mood(levels, float(answer.score if answer.score is not None else 0.0), "laya")
            self._cache[key] = mood
        except LayaUnavailable:
            mood = rules_mood(kind)
        for callback in self._waiting.pop(key, []):
            callback(mood)


def default_reactor() -> LayaReactor | RulesReactor:
    return LayaReactor() if get_client().enabled else RulesReactor()
