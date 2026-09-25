"""People living in Zava Bank's world, deciding through Laya (rules when it is down)."""
from __future__ import annotations

import asyncio
import json

import pytest

from api.server.services.judgement.laya_client import LayaAnswer, LayaResult
from api.server.world.runtime import SimulationRuntime
from verticals.banking.worlds.life import CIRCUMSTANCES, CaseDial, Chooser
from verticals.banking.worlds.scenario import ZavaBankWorld


@pytest.fixture
def life_on(monkeypatch):
    monkeypatch.setenv("BANKING_WORLD_LIFE", "1")


def _world() -> ZavaBankWorld:
    world = ZavaBankWorld(seed=42, runtime=SimulationRuntime(42))
    world.install()
    return world


def _run(world: ZavaBankWorld, hours: float) -> None:
    world.runtime.env.run(until=world.runtime.env.now + hours * 60)


def test_without_the_flag_nobody_lives_in_the_world(monkeypatch) -> None:
    monkeypatch.delenv("BANKING_WORLD_LIFE", raising=False)
    world = _world()
    _run(world, 2)
    assert world.life is None and "life" not in world.render_state()
    assert world.render_state()["bank"]["customer_count"] == len(world.customers)


def test_people_pay_for_their_lives_scams_happen_and_customers_join(life_on) -> None:
    world = _world()
    before = world.render_state()["bank"]["customer_count"]
    _run(world, 36)
    life = world.render_state()["life"]
    assert life["people"] >= 200 and life["payments"] > 200
    assert life["scams_tried"] > 0 and life["scams_paid"] + life["scams_stopped"] + life["scams_ignored"] == life["scams_tried"]
    assert life["joined"] > 0 and world.render_state()["bank"]["customer_count"] == before + life["joined"] - life["left"]
    assert life["decided_by_laya"] == 0 and life["decided_by_rules"] > 0  # no event loop: the rules decide
    kinds = {entry["kind"] for entry in life["stories"]} | {entry["kind"] for entry in life["feed"]}
    assert "payment" in kinds and kinds & {"scam", "join", "life", "money"}
    # People pay real payees with references, not a replay of the seeded book.
    settled = [e for e in world.runtime.journal if e.type == "banking.payment.settled"]
    assert settled and all(e.payload.get("reference") for e in settled)
    assert {e.actor_id for e in settled} <= set(world.payments)
    assert not any(e.actor_id.startswith("SYN-PAY-0") for e in settled)


def test_a_victim_who_realises_calls_the_bank_and_the_claim_follows(life_on) -> None:
    world = _world()
    world.life.dial = CaseDial(1_000)
    _run(world, 48)
    claims = [c for c in world.fraud_claims.values() if c.id in world._claim_scenarios]
    assert world.render_state()["life"]["calls"] >= 1 and claims
    claim = claims[0]
    observation = json.dumps(world.observation_for_claim(claim.id))
    person = world.life.people.get(claim.customer_id)
    assert person is not None
    # A private life is world truth: the bank's evidence carries only the record and the call.
    assert person.who() not in observation and person.stage["who"] not in observation
    assert CIRCUMSTANCES.get(person.circumstance or "", ("never in evidence",))[0] not in observation


class _Laya:
    enabled = True

    def __init__(self, probabilities: dict[str, float], lead: float) -> None:
        self.probabilities, self.lead, self.calls = probabilities, lead, 0

    def available(self) -> bool:
        return True

    async def ask(self, state, questions):
        self.calls += 1
        top = max(self.probabilities, key=self.probabilities.get)
        return LayaResult({"q": LayaAnswer("choice", dict(self.probabilities), top, self.lead)}, 40.0, 41.0)


def _choose(chooser: Chooser, fallback: dict[str, float]) -> list[tuple[str, str]]:
    got: list[tuple[str, str]] = []

    async def run() -> None:
        chooser.choose({"person": "x"}, {"type": "choice", "instructions": "?", "criteria": {"a": "A", "b": "B"}},
                       fallback, lambda choice, by: got.append((choice, by)))
        for _ in range(5):
            await asyncio.sleep(0)

    asyncio.run(run())
    return got


def test_laya_decides_when_its_answer_is_clear_and_the_library_otherwise() -> None:
    import random

    clear = _Laya({"a": 0.98, "b": 0.02}, 0.96)
    assert _choose(Chooser(random.Random(1), client_factory=lambda: clear), {"b": 1.0}) == [("a", "laya")]
    unsure = _Laya({"a": 0.52, "b": 0.48}, 0.04)
    assert _choose(Chooser(random.Random(1), client_factory=lambda: unsure), {"b": 1.0}) == [("b", "rules")]
    busy = Chooser(random.Random(1), client_factory=lambda: clear, max_in_flight=0)
    assert _choose(busy, {"b": 1.0}) == [("b", "rules")] and clear.calls == 1


def test_the_case_dial_lets_about_its_rate_through() -> None:
    now = [0.0]
    dial = CaseDial(8, clock=lambda: now[0])
    assert [dial.take() for _ in range(3)] == [True, True, False]
    now[0] += 450  # an eighth of an hour
    assert dial.take() is True and dial.take() is False
    dial.give_back()
    assert dial.take() is True


def test_a_customer_let_down_by_the_bank_may_leave(life_on) -> None:
    world = _world()
    person = next(iter(world.life.people.values()))
    claim_id = next(c.id for c in world.fraud_claims.values())
    world.fraud_claims[claim_id].customer_id = person.customer_id
    world.life.chooser = Chooser(__import__("random").Random(3))
    world.life._leave(person, "refused", "yes", "rules")
    assert world.customers[person.customer_id].status == "left"
    assert world.render_state()["bank"]["customer_count"] == len(world.customers) - 1
    assert any(e.type == "banking.customer.left" for e in world.runtime.journal)
