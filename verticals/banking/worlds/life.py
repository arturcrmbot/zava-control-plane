"""People living in Zava Bank's world, making their own choices through Laya.

A cast of named customers with private lives: who they are, their money, what
has happened to them lately. A few wake at a time and decide what to do next.
Laya reads the situation and picks from a short menu, a seeded draw turns its
odds into a choice, and code turns the choice into a real record: a payment, a
call to the bank, an account opened or closed. Scam crews pick tactics and
targets, and the people they reach decide whether to pay. With Laya down the
library's own weights decide, so the world keeps going.

A private life is world truth. It never reaches the evidence the bank's agents
read, and money only moves through customers' own payments and the bank's
governed decisions.
"""
from __future__ import annotations

import asyncio
import os
import random
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable

from api.server.services.judgement.laya_client import get_client
from verticals.banking.worlds import reference_data
from verticals.banking.worlds.model import Account, BeneficiaryAccount, Customer

FUNCTION_RETAIL = "retail-banking"
FUNCTION_FINCRIME = "financial-crime"

_CAST_SIZE = 200
_RESERVE_SIZE = 60
_WAKE_EVERY_MINUTES = 5.0
_WAKE_COUNT = 3
_CREW_EVERY_MINUTES = 40.0
_JOIN_EVERY_MINUTES = 150.0
_REALISE_AFTER_MINUTES = 180.0
_FEED_SIZE = 16
_STORY_KINDS = {"scam", "call", "life", "join", "leave", "stay"}

# -- the library ----------------------------------------------------------------------------

FIRST_NAMES = (
    "Amara", "Arthur", "Beatrice", "Callum", "Chloe", "Daniel", "Deepa", "Eilidh", "Ewan", "Farah",
    "Grace", "Hamza", "Harriet", "Ibrahim", "Isla", "Jack", "Joan", "Kofi", "Leah", "Liam", "Maya",
    "Megan", "Mohammed", "Nadia", "Niamh", "Oliver", "Olu", "Patrick", "Priya", "Rhys", "Rosa", "Ruth",
    "Samir", "Sian", "Sofia", "Tariq", "Thomas", "Una", "Wei", "Yusuf", "Zara", "Bronwen", "Connor",
    "Dorothy", "Emeka", "Fiona", "Gareth", "Hannah", "Imran", "Maureen", "Stanley", "Aisha",
)
LAST_NAMES = (
    "Abbott", "Adeyemi", "Ahmed", "Bell", "Brennan", "Chen", "Clarke", "Davies", "Evans", "Fraser", "Gill",
    "Hughes", "Iqbal", "Jones", "Kaur", "Kowalski", "Lewis", "MacLeod", "Mensah", "Murphy", "Nowak",
    "O'Brien", "Okafor", "Patel", "Price", "Quinn", "Rahman", "Reid", "Robertson", "Rossi", "Shah",
    "Singh", "Taylor", "Thomas", "Walsh", "Williams", "Wright", "Young", "Zhang", "Hussain",
)

# Life stages: who someone is, what they earn, how exposed they are to scams.
STAGES = (
    {"age": 21, "who": "a student sharing a flat", "work": "works shifts in a cafe", "band": "low", "exposure": 0.35},
    {"age": 27, "who": "renting a one-bedroom flat alone", "work": "a nurse on nights", "band": "middle", "exposure": 0.3},
    {"age": 26, "who": "new to the city", "work": "a junior developer", "band": "middle", "exposure": 0.3},
    {"age": 33, "who": "living with a partner and a toddler", "work": "a delivery driver", "band": "middle", "exposure": 0.35},
    {"age": 38, "who": "sending money home to family every month", "work": "a care worker", "band": "low", "exposure": 0.4},
    {"age": 41, "who": "a single parent of two", "work": "a teaching assistant", "band": "low", "exposure": 0.45},
    {"age": 46, "who": "married with teenagers", "work": "runs a small plumbing business", "band": "middle", "exposure": 0.35},
    {"age": 52, "who": "caring for a parent with dementia", "work": "works part time in a shop", "band": "low", "exposure": 0.5},
    {"age": 56, "who": "living with a partner, children grown up", "work": "an office manager", "band": "high", "exposure": 0.35},
    {"age": 64, "who": "recently retired", "work": "retired from the council", "band": "middle", "exposure": 0.55},
    {"age": 72, "who": "widowed and living alone", "work": "retired", "band": "low", "exposure": 0.75},
    {"age": 79, "who": "living alone and rarely going out", "work": "retired", "band": "low", "exposure": 0.85},
)
TRAITS = (
    "careful with money", "a bit impulsive", "trusts people who sound official", "suspicious of cold calls",
    "anxious about money", "generous with family", "loves a bargain", "rarely checks their balance",
)
# Circumstances the bank may not know about (world truth).
CIRCUMSTANCES = {
    "bereaved": ("recently lost their partner and is struggling", "Since my husband died last month I've been on my own."),
    "hospital": ("just out of hospital after a stroke", "I'm just out of hospital and I get confused easily."),
    "job_loss": ("lost their job last week and is worried about money", "I lost my job last week and I was desperate."),
    "isolated": ("lonely and has nobody to talk things through with", "I live on my own and there was nobody to ask."),
    "new_baby": ("has a new baby and hardly sleeps", "I have a newborn and I'm exhausted."),
}
LIFE_EVENTS = {
    "bereaved": "{name}'s partner died",
    "hospital": "{name} came home from hospital after a stroke",
    "job_loss": "{name} lost their job",
    "new_baby": "{name} had a baby",
}
BAND_BUDGET = {"low": 1_400.0, "middle": 2_600.0, "high": 5_200.0}
BAND_SALARY = {"low": 1_500.0, "middle": 2_800.0, "high": 5_600.0}

# Fictional payees by kind, each with the references people actually write.
PAYEES = {
    "rent": (("Harbour Lettings", ("Rent {month}",)), ("Parkside Homes", ("Monthly rent flat {n}",)),
             ("Castlegate Property", ("Rent {month}",))),
    "groceries": (("Greenleaf Grocers", ("Weekly shop", "Groceries")), ("Corner Fresh", ("Groceries",)),
                  ("Market Basket", ("Weekly shop",))),
    "eat_out": (("Lucky Noodle", ("Takeaway",)), ("Bella Pizza", ("Pizza night", "Takeaway")),
                ("The Crown Arms", ("Dinner with friends",))),
    "shop_online": (("Parcelmart", ("Order {n}",)), ("Threadline Fashion", ("Online order {n}",)),
                    ("Gadget Barn", ("Order {n}",))),
    "bills": (("Northside Energy", ("Energy bill",)), ("Brightwater Water", ("Water bill",)),
              ("Kestrel Mobile", ("Phone contract",)), ("Riverside Council", ("Council tax",))),
    "transport": (("CityRail", ("Train tickets", "Season ticket")), ("Metro Fuel", ("Fuel",))),
    "treat": (("Pulse Gym", ("Gym membership",)), ("Page and Quill Books", ("Books",)),
              ("Starlight Cinema", ("Cinema tickets",))),
}
FAMILY_REFERENCES = ("For Mum", "Birthday money", "Help with the bills", "For the kids", "Paying you back")
AMOUNTS = {  # low, middle, high income bands: (min, max) in GBP
    "groceries": ((15, 45), (25, 90), (40, 140)),
    "eat_out": ((12, 30), (18, 60), (30, 120)),
    "shop_online": ((10, 60), (20, 150), (40, 400)),
    "bills": ((30, 90), (45, 140), (60, 220)),
    "family": ((20, 150), (50, 300), (100, 600)),
    "transport": ((5, 40), (8, 60), (10, 90)),
    "treat": ((8, 30), (15, 70), (25, 150)),
    "rent": ((450, 750), (800, 1_300), (1_400, 2_400)),
}
# Measured: with "family", "save" or "nothing" on the menu, or the person's money in
# the text, Laya picks the same option for almost everyone. Code decides whether
# someone spends and handles family transfers; Laya picks what, from who they are.
SPEND_OPTIONS = {
    "groceries": "Doing the food shopping",
    "eat_out": "Eating out or ordering a takeaway",
    "shop_online": "Buying something online",
    "bills": "Paying a household bill",
    "transport": "Paying for travel or fuel",
    "treat": "Spending on a hobby, the gym or a night out",
}
# Measured: asked whether someone would fall for a scam, Laya says yes for
# almost everyone (it follows the message, not the person). It does read how
# cautious a person is from who they are, so it rates that and code decides.
CAUTION_LEVELS = ("Never: very cautious and checks everything", "Unlikely: fairly cautious",
                  "Possibly: could be persuaded", "Easily: very trusting")
TACTIC_FIT = {  # which scams land on whom
    "bank": lambda p: 1.0 + (0.3 if p.stage["age"] >= 60 else 0.0),
    "tax": lambda p: 1.0 + (0.3 if p.stage["age"] >= 60 else 0.0),
    "romance": lambda p: 0.6 + (0.8 if p.circumstance in ("bereaved", "isolated") or "alone" in p.stage["who"] else 0.0),
    "investment": lambda p: 0.6 + (0.5 if p.stage["band"] != "low" else 0.0),
    "parcel": lambda p: 1.0 + (0.3 if p.stage["age"] < 40 else 0.0),
}

# Scam scripts the crews choose between.
TACTICS = {
    "bank": {"label": "fake bank fraud team", "range": (1_500, 12_000),
             "pitch": "Zava Bank fraud team here. Your account has been compromised. Move your savings to the safe account we give you now.",
             "references": ("Safe account transfer as advised by bank", "Protect funds new account"),
             "call": "Someone rang saying they were from Zava Bank's fraud team. They said my account was at risk and told me to move {amount} to a safe account. Now the number doesn't work."},
    "tax": {"label": "tax office penalty", "range": (300, 3_000),
            "pitch": "HMRC: you owe an unpaid tax penalty. Pay today or a warrant will be issued for your arrest.",
            "references": ("HMRC penalty urgent payment", "Tax penalty settlement"),
            "call": "I got a message from the tax office saying I owed a penalty and would be arrested. I paid {amount} and now I think it was a scam."},
    "romance": {"label": "romance", "range": (200, 4_000),
                "pitch": "It's Daniel. My card is blocked abroad and I need help with a hospital bill. I will pay you back next week, I promise.",
                "references": ("Loan to Daniel", "Hospital bill help"),
                "call": "I met Daniel online and he needed money for a hospital bill abroad. I sent him {amount} and now he has stopped answering."},
    "investment": {"label": "crypto investment", "range": (500, 15_000),
                   "pitch": "Our crypto platform members made 3 percent a week. Deposit today to lock in your place.",
                   "references": ("Crypto wallet top up guaranteed returns", "Investment platform deposit 3 percent weekly"),
                   "call": "A crypto platform promised 3 percent a week. I deposited {amount} and now they want a fee before I can withdraw."},
    "parcel": {"label": "parcel release fee", "range": (20, 400),
               "pitch": "Your parcel is held at customs. Pay the release fee today to get it delivered.",
               "references": ("Customs fee for held parcel", "Release fee to unlock withdrawal"),
               "call": "I paid a release fee of {amount} for a parcel held at customs. The parcel never came."},
}
BANK_WARNING = "Zava Bank warning: fraudsters pretend to be banks, officials or loved ones. We will never ask you to move money to keep it safe."

# Measured: asked which scam to try next, Laya repeats whatever the history
# mentions, failures included. It does match a scam to a person's profile
# (romance for the lonely, tax or bank for trusting retirees, parcel fees for
# busy people), leaning towards romance, so its fit is blended with an even
# spread and weighted by what has worked for the crew.
FIT_OPTIONS = {
    "bank": "A call pretending to be their bank's fraud team",
    "tax": "A threatening message from the tax office",
    "romance": "A fake online romance asking for money",
    "investment": "A fake crypto investment with big returns",
    "parcel": "A text asking for a small parcel delivery fee",
}
CREWS = ("Crew North", "Crew Harbour", "Crew Delta")

VICTIM_OPTIONS = {
    "pay": "Do what the message asks and send the money",
    "check": "Stop and call Zava Bank to check first",
    "ignore": "Ignore it, it looks like a scam",
}


# -- Laya, with a seeded draw and a rules fallback ------------------------------------------------

def draw(weights: dict[str, float], rng: random.Random) -> str:
    total = sum(max(0.0, w) for w in weights.values()) or 1.0
    pick, running = rng.random() * total, 0.0
    for option, weight in weights.items():
        running += max(0.0, weight)
        if pick < running:
            return option
    return next(iter(weights))


@dataclass
class Decision:
    """One choice: what was picked, who picked it, the odds and Laya's time."""

    choice: str
    by: str  # laya | rules
    odds: dict[str, float]
    ms: float | None = None


def _normalised(weights: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, w) for w in weights.values()) or 1.0
    return {k: max(0.0, w) / total for k, w in weights.items()}


class Chooser:
    """Laya reads a situation and gives odds over a menu; a seeded draw decides."""

    def __init__(self, rng: random.Random, *, client_factory: Callable[[], Any] = get_client,
                 max_in_flight: int = 4, min_lead: float = 0.12) -> None:
        self._rng = rng
        self._client_factory = client_factory
        self._max_in_flight = max_in_flight
        self._min_lead = min_lead
        self._in_flight = 0
        self.decided = {"laya": 0, "rules": 0}
        self.latencies: deque[float] = deque(maxlen=60)

    def avg_ms(self) -> float | None:
        return round(sum(self.latencies) / len(self.latencies), 1) if self.latencies else None

    def choose(self, state: dict[str, str], question: dict[str, Any], fallback: dict[str, float],
               done: Callable[[Decision], None], *, min_lead: float | None = None, draw_it: bool = True) -> None:
        """Ask Laya for odds over the menu; draw from them (or the fallback) and call back."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        client = self._client_factory() if loop is not None else None
        if client is None or not client.available() or self._in_flight >= self._max_in_flight:
            odds = _normalised(fallback)
            self._finish(Decision(draw(odds, self._rng) if draw_it else max(odds, key=odds.get), "rules", odds), done)
            return
        self._in_flight += 1
        threshold = self._min_lead if min_lead is None else min_lead
        loop.create_task(self._ask(client, state, question, fallback, done, threshold, draw_it))

    async def _ask(self, client, state, question, fallback, done, threshold: float, draw_it: bool) -> None:
        decision = None
        started = time.perf_counter()
        try:
            answer = (await client.ask(state, {"q": question})).answers["q"]
            ms = (time.perf_counter() - started) * 1000
            self.latencies.append(ms)
            if answer.lead >= threshold:
                odds = _normalised(dict(answer.probabilities))
                decision = Decision(draw(odds, self._rng) if draw_it else answer.top, "laya", odds, ms)
        except Exception:  # Laya down or slow: the library decides
            pass
        finally:
            self._in_flight -= 1
        if decision is None:
            odds = _normalised(fallback)
            decision = Decision(draw(odds, self._rng) if draw_it else max(odds, key=odds.get), "rules", odds)
        self._finish(decision, done)

    def _finish(self, decision: Decision, done: Callable[[Decision], None]) -> None:
        self.decided[decision.by] += 1
        done(decision)

    def odds(self, state: dict[str, str], question: dict[str, Any], fallback: dict[str, float],
             done: Callable[[Decision], None]) -> None:
        """Laya's odds over the menu (the fallback weights when it is down), not drawn."""
        self.choose(state, question, fallback, done, min_lead=0.0, draw_it=False)


def choice_question(instructions: str, options: dict[str, str]) -> dict[str, Any]:
    return {"type": "choice", "instructions": instructions, "criteria": dict(options)}


def yes_no(instructions: str) -> dict[str, Any]:
    return {"type": "noul", "instructions": instructions}


def rating(instructions: str, levels: tuple[str, ...]) -> dict[str, Any]:
    return {"type": "score", "instructions": instructions, "criteria": list(levels)}


def step(question: str, labels: dict[Any, str], decision: "Decision", top: int = 4, *, mark: bool = True) -> dict[str, Any]:
    """One step of a decision for the floor: the question, the top odds, what was chosen.

    ``mark=False`` for a step that only gives odds another step draws from.
    """
    names = {str(k): v for k, v in labels.items()}
    ranked = sorted(decision.odds.items(), key=lambda kv: -kv[1])[:top]
    if decision.choice not in {k for k, _ in ranked} and decision.choice in decision.odds:
        ranked = ranked[: top - 1] + [(decision.choice, decision.odds[decision.choice])]
    return {"by": decision.by, "question": question, "chose": decision.choice if mark else "",
            "chose_label": names.get(decision.choice, decision.choice) if mark else "",
            "ms": round(decision.ms) if decision.ms else None,
            "options": [{"id": k, "label": names.get(k, k), "p": round(p, 3)} for k, p in ranked]}


class CaseDial:
    """At most ``per_hour`` cases the world opens on its own, in wall-clock time."""

    def __init__(self, per_hour: float, clock: Callable[[], float] = time.monotonic) -> None:
        self.per_hour = max(0.0, per_hour)
        self._clock = clock
        self._capacity = max(1.0, self.per_hour / 4)
        self._tokens = self._capacity
        self._at = clock()
        self.taken = 0

    def take(self) -> bool:
        now = self._clock()
        self._tokens = min(self._capacity, self._tokens + (now - self._at) * self.per_hour / 3600)
        self._at = now
        if self._tokens >= 1:
            self._tokens -= 1
            self.taken += 1
            return True
        return False

    def give_back(self) -> None:
        self._tokens = min(self._capacity, self._tokens + 1)
        self.taken = max(0, self.taken - 1)


# -- the people -------------------------------------------------------------------------------

@dataclass
class Person:
    customer_id: str
    name: str
    stage: dict[str, Any]
    trait: str
    circumstance: str | None
    payees: dict[str, str]
    payday: int
    budget: float
    scam: dict[str, Any] | None = None
    paid_day: int = -1
    rent_day: int = -1
    caution: int | None = None
    caution_by: str = "rules"
    caution_odds: dict[str, float] | None = None
    since: float = -1.0
    diary: deque = field(default_factory=lambda: deque(maxlen=4))

    def who(self) -> str:
        stage = self.stage
        text = f"{self.name}, {stage['age']}, {stage['who']}, {stage['work']}. {self.trait.capitalize()}."
        if self.circumstance:
            text += f" {CIRCUMSTANCES[self.circumstance][0].capitalize()}."
        return text


class Life:
    """The cast, the scam crews and the bank's customers joining and leaving."""

    def __init__(self, world: Any, *, chooser: Chooser | None = None,
                 clock: Callable[[], float] = time.monotonic, cases_per_hour: float | None = None) -> None:
        self.world = world
        self.rng = random.Random(world.seed + 505)
        self.chooser = chooser or Chooser(random.Random(world.seed + 606))
        per_hour = cases_per_hour if cases_per_hour is not None else float(os.environ.get("BANKING_WORLD_CASES_PER_HOUR", "10"))
        self.dial = CaseDial(per_hour, clock)
        self.people: dict[str, Person] = {}
        self.reserve: list[dict[str, Any]] = []
        self.payee_names: dict[str, str] = {}
        self.payee_ids: dict[str, list[str]] = {}
        self.family_ids: list[str] = []
        self.crew_record: dict[str, dict[str, list[int]]] = {}
        self.feed: deque[dict[str, Any]] = deque(maxlen=_FEED_SIZE)
        self.stories: deque[dict[str, Any]] = deque(maxlen=_FEED_SIZE)
        # Each decision as steps: what Laya was asked and its odds, what code
        # weighed, what happened. Scams are kept apart: they are rarer.
        self.decisions: deque[dict[str, Any]] = deque(maxlen=8)
        self.scam_decisions: deque[dict[str, Any]] = deque(maxlen=4)
        self.counts = {"payments": 0, "scams_tried": 0, "scams_paid": 0, "scams_stopped": 0,
                       "scams_ignored": 0, "calls": 0, "joined": 0, "left": 0, "life_events": 0}
        self._spent_gbp = 0.0

    # -- install ----------------------------------------------------------------------------

    def install(self) -> None:
        self._build_payees()
        self._build_cast()
        runtime = self.world.runtime
        runtime.process(self._days())
        runtime.process(self._crews())
        runtime.process(self._joins())

    def _build_payees(self) -> None:
        psp = sorted(self.world.payment_service_providers)[0]
        number = 0
        self.payee_references: dict[str, tuple[str, ...]] = {}
        for kind, payees in PAYEES.items():
            for name, references in payees:
                number += 1
                bene_id = f"SYN-BENE-P{number:02d}"
                self.world.beneficiaries[bene_id] = BeneficiaryAccount(
                    id=bene_id, psp_id=psp, holder_id=f"SYN-HOLDER-P{number:02d}", holder_kind="corporate",
                    location_id=reference_data.LOC_EXTERNAL_PSP, risk_band="low", balance_gbp=0.0)
                self.payee_names[bene_id] = name
                self.payee_references[bene_id] = references
                self.payee_ids.setdefault(kind, []).append(bene_id)
        mules = set(reference_data.mule_beneficiary_ids())
        self.family_ids = [b for b, record in sorted(self.world.beneficiaries.items())
                           if record.holder_kind == "individual" and b not in mules and not b.startswith("SYN-BENE-P")][:60]

    def _profile(self) -> dict[str, Any]:
        return {"name": f"{self.rng.choice(FIRST_NAMES)} {self.rng.choice(LAST_NAMES)}",
                "stage": self.rng.choice(STAGES), "trait": self.rng.choice(TRAITS)}

    def _build_cast(self) -> None:
        heroes = {c.customer_id for c in self.world.fraud_claims.values()}
        pool = sorted(c for c, customer in self.world.customers.items()
                      if customer.segment == "personal" and customer.status == "active" and c not in heroes)
        for customer_id in self.rng.sample(pool, min(_CAST_SIZE, len(pool))):
            self._adopt(customer_id, self._profile())
        self.reserve = [self._profile() for _ in range(_RESERVE_SIZE)]

    def _adopt(self, customer_id: str, profile: dict[str, Any]) -> Person:
        customer = self.world.customers[customer_id]
        customer.display_name = profile["name"]
        stage = profile["stage"]
        # The bank's marker is what the bank knows; circumstances are what is true.
        if customer.vulnerability_flag:
            circumstance = self.rng.choice(("bereaved", "hospital", "isolated"))
        else:
            circumstance = self.rng.choice(tuple(CIRCUMSTANCES)) if self.rng.random() < 0.08 else None
        payees = {kind: self.rng.choice(ids) for kind, ids in self.payee_ids.items()}
        if self.family_ids:
            payees["family"] = self.rng.choice(self.family_ids)
        person = Person(customer_id=customer_id, name=profile["name"], stage=stage, trait=profile["trait"],
                        circumstance=circumstance, payees=payees, payday=self.rng.randrange(7),
                        budget=BAND_BUDGET[stage["band"]])
        self.people[customer_id] = person
        return person

    # -- telling the world what happened ---------------------------------------------------------

    def _note(self, person: Person | None, text: str, by: str, kind: str) -> None:
        now = float(self.world.runtime.now)
        entry = {"t": round(now, 1), "when": _when(now), "who": person.name if person else None,
                 "text": text, "by": by, "kind": kind}
        self.feed.appendleft(entry)
        if kind in _STORY_KINDS:
            self.stories.appendleft(entry)
        if person is not None:
            person.diary.append(text)

    def _trace(self, kind: str, person: Person, title: str, steps: list[dict[str, Any]], outcome: str) -> None:
        now = float(self.world.runtime.now)
        entry = {"t": round(now, 1), "when": _when(now), "kind": kind, "who": person.name, "profile": person.who(),
                 "title": title, "steps": steps, "outcome": outcome}
        (self.scam_decisions if kind == "scam" else self.decisions).appendleft(entry)

    def _emit(self, event_type: str, person: Person, payload: dict[str, Any], function: str = FUNCTION_RETAIL):
        return self.world.runtime.emit(event_type, actor_id=person.customer_id,
                                       payload={"customer_id": person.customer_id, **payload, "function": function})

    def _free(self, person: Person) -> bool:
        customer = self.world.customers.get(person.customer_id)
        if customer is None or customer.status == "left":
            return False
        return not self.world._live_claims(customer_id=person.customer_id)

    def _account(self, person: Person) -> Account:
        return self.world.accounts[self.world.customers[person.customer_id].account_id]

    def _money_words(self, person: Person) -> str:
        left = self._account(person).balance_gbp / person.budget
        if left > 0.6:
            return "They have plenty of money left this month."
        if left > 0.3:
            return "They have about half their money left until payday."
        if left > 0.1:
            return "Money is getting tight until payday."
        return "They have almost nothing left until payday."

    def _amount(self, kind: str, person: Person) -> float:
        low, high = AMOUNTS[kind][("low", "middle", "high").index(person.stage["band"])]
        return float(round(self.rng.uniform(low, high)))

    def _pay(self, person: Person, payee_id: str, reference: str, amount: float, *, warning: bool = False):
        account = self._account(person)
        if account.balance_gbp < amount:
            return None
        payment = self.world._new_payment(person.customer_id, payee_id, reference, amount)
        payment.warning_shown = warning
        account.balance_gbp = round(account.balance_gbp - amount, 2)
        account.version += 1
        self.counts["payments"] += 1
        self._spent_gbp += amount
        return payment

    # -- days: obligations by rule, choices by Laya ----------------------------------------------

    def _days(self):
        env = self.world.runtime.env
        while True:
            yield env.timeout(_WAKE_EVERY_MINUTES)
            self.world._note_ended_cases()
            now = float(self.world.runtime.now)
            victims = [p for p in self.people.values()
                       if p.scam and not p.scam["called"] and now - p.scam["at"] >= _REALISE_AFTER_MINUTES and self._free(p)]
            for person in victims[:1]:
                self._maybe_realise(person)
            awake = [p for p in self.people.values() if self._free(p) and p not in victims]
            for person in self.rng.sample(awake, min(_WAKE_COUNT, len(awake))):
                self._wake(person)

    def _wake(self, person: Person) -> None:
        now = float(self.world.runtime.now)
        day = int(now // 1440)
        if day % 7 == person.payday and person.paid_day != day:
            person.paid_day = day
            account = self._account(person)
            account.balance_gbp = round(account.balance_gbp + BAND_SALARY[person.stage["band"]], 2)
            account.version += 1
            self._note(person, f"{person.name}'s salary arrived", "rules", "money")
            return
        if self.rng.random() < 0.015 and not person.circumstance:
            event = self.rng.choice(tuple(LIFE_EVENTS))
            person.circumstance = event
            person.since = now
            self.counts["life_events"] += 1
            self._emit("banking.customer.life_event", person, {"event": event})
            self._note(person, LIFE_EVENTS[event].format(name=person.name) + " (the bank doesn't know)", "world", "life")
            return
        if day % 7 == (person.payday + 3) % 7 and person.rent_day != day:
            person.rent_day = day
            self._spend(person, "rent", "rules")
            return
        left = self._account(person).balance_gbp / person.budget
        if self.rng.random() < (0.8 if left < 0.1 else 0.45 if left < 0.3 else 0.2):
            return  # not spending right now
        if "family" in person.stage["who"] and self.rng.random() < 0.3:
            self._spend(person, "family", "rules")
            return
        state = {"person": person.who(), "time": f"It is {_when(now)}."}
        fallback = {"groceries": 3, "eat_out": 2, "shop_online": 2, "bills": 1, "transport": 2, "treat": 1}
        self.chooser.choose(state, choice_question("What is this person most likely to spend money on right now?", SPEND_OPTIONS),
                            fallback, lambda d: self._spend(person, d.choice, d.by, d), min_lead=0.0)

    def _spend(self, person: Person, kind: str, by: str, decision: Decision | None = None) -> None:
        if not self._free(person):
            return
        if kind in ("nothing", "save"):
            if kind == "save" and by == "laya":
                self._note(person, f"{person.name} put some money aside", by, "money")
            return
        payee = person.payees.get(kind)
        if payee is None:
            return
        amount = self._amount(kind, person)
        month = _MONTHS[int(self.world.runtime.now // (1440 * 30)) % 12]
        references = self.payee_references.get(payee, FAMILY_REFERENCES)
        reference = self.rng.choice(references).format(month=month, n=self.rng.randint(1000, 9999))
        if self._pay(person, payee, reference, amount) is None:
            return
        if payee in self.payee_names:
            text = f"{person.name} paid {self.payee_names[payee]} GBP {amount:,.0f}: \"{reference}\""
        else:
            text = f"{person.name} sent GBP {amount:,.0f} to family: \"{reference}\""
        self._note(person, text, by, "payment")
        if decision is not None:
            first = person.name.split()[0]
            self._trace("spend", person, f"{person.name}, {_when(float(self.world.runtime.now))}",
                        [step(f"What is {first} most likely to spend money on right now?", SPEND_OPTIONS, decision)],
                        text.replace(person.name + " ", "", 1))

    # -- scams that happen to someone ------------------------------------------------------------

    def _crews(self):
        env = self.world.runtime.env
        while True:
            yield env.timeout(_CREW_EVERY_MINUTES * self.rng.uniform(0.6, 1.4))
            targets = [p for p in self.people.values() if self._free(p) and p.scam is None]
            if not targets or not self.world._active_mules():
                continue
            crew = self.rng.choice(CREWS)
            weights = [p.stage["exposure"] + (0.3 if p.circumstance else 0.0) for p in targets]
            person = self.rng.choices(targets, weights=weights, k=1)[0]
            record = self.crew_record.setdefault(crew, {t: [0, 0] for t in TACTICS})

            def pick(fit: Decision, crew=crew, person=person, record=record) -> None:
                odds = _normalised({t: (0.5 * fit.odds.get(t, 0.0) + 0.5 / len(TACTICS)) * (1 + 2 * record[t][1]) / (1 + record[t][0])
                                    for t in TACTICS})
                tactic = draw(odds, self.rng)
                first = person.name.split()[0]
                steps = [step(f"Which scam would most likely work on {first}?", FIT_OPTIONS, fit, mark=False),
                         step(f"{crew} weighs that against what has worked for it", FIT_OPTIONS,
                              Decision(tactic, "code", odds))]
                self._approach(crew, tactic, person, fit.by, steps)

            self.chooser.odds({"person": person.who()},
                              choice_question("Which of these scams would be most likely to work on this person?", FIT_OPTIONS),
                              {t: 1.0 for t in TACTICS}, pick)

    def _approach(self, crew: str, tactic_id: str, person: Person, crew_by: str,
                  steps: list[dict[str, Any]] | None = None) -> None:
        if not self._free(person) or person.scam is not None or not self.world._active_mules():
            return
        self.crew_record.setdefault(crew, {t: [0, 0] for t in TACTICS})[tactic_id][0] += 1
        tactic = TACTICS[tactic_id]
        amount = float(round(self.rng.uniform(*tactic["range"]) / 10) * 10)
        warning = amount >= 1_000
        self.counts["scams_tried"] += 1
        self._emit("banking.scam.attempted", person, {"crew": crew, "tactic": tactic_id}, FUNCTION_FINCRIME)

        def decide() -> None:
            # How cautious they are (Laya's reading), whether this scam fits them,
            # whether the bank warned them: the seeded draw does the rest.
            trust = (person.caution or 0) / 3
            pay = trust * 0.7 * TACTIC_FIT[tactic_id](person) * (0.6 if warning else 1.0)
            if person.circumstance:
                pay += 0.12
            pay = min(0.85, max(0.03, pay))
            check = (1 - pay) * (0.25 + 0.5 * (1 - trust))
            odds = {"pay": pay, "check": check, "ignore": max(0.0, 1 - pay - check)}
            choice = draw(odds, self.rng)
            first = person.name.split()[0]
            caution = Decision(str(person.caution or 0), person.caution_by, person.caution_odds or {str(person.caution or 0): 1.0})
            trail = list(steps or []) + [
                step(f"How easily could a stranger talk {first} into sending money?", dict(enumerate(CAUTION_LEVELS)), caution),
                step("Combines that caution, how well the scam fits and " + ("the bank's warning" if warning else "no warning shown"),
                     VICTIM_OPTIONS, Decision(choice, "code", odds)),
            ]
            self._victim(crew, tactic_id, person, amount, warning, choice, person.caution_by, trail)

        if person.caution is not None:
            decide()
            return
        exposure = person.stage["exposure"] + (0.2 if person.circumstance else 0.0)
        fallback = {"0": 1 - exposure, "1": 1.2 - exposure, "2": exposure, "3": exposure * 0.8}

        def read(d: Decision) -> None:
            person.caution, person.caution_by, person.caution_odds = int(d.choice), d.by, d.odds
            decide()

        self.chooser.choose({"person": person.who()},
                            rating("How easily could a stranger talk this person into sending money?", CAUTION_LEVELS),
                            fallback, read, min_lead=0.0)

    def _victim(self, crew: str, tactic_id: str, person: Person, amount: float, warning: bool, choice: str, by: str,
                steps: list[dict[str, Any]] | None = None) -> None:
        record = self.crew_record.setdefault(crew, {t: [0, 0] for t in TACTICS})
        label = TACTICS[tactic_id]["label"]
        if choice == "pay" and self._free(person):
            mules = self.world._active_mules()
            reference = self.rng.choice(TACTICS[tactic_id]["references"])
            payment = self._pay(person, self.rng.choice(mules), reference, amount, warning=warning) if mules else None
            if payment is not None:
                person.scam = {"tactic": tactic_id, "payment_id": payment.id, "amount": amount,
                               "at": float(self.world.runtime.now), "called": False}
                self.counts["scams_paid"] += 1
                record[tactic_id][1] += 1
                text = (f"{person.name} fell for a {label} scam and sent GBP {amount:,.0f}"
                        + (" despite the bank's warning" if warning else ""))
                self._note(person, text, by, "scam")
                self._trace("scam", person, f"{crew} tried a {label} scam on {person.name}", steps or [],
                            text.replace(person.name + " ", "", 1))
                return
        if choice == "check":
            self.counts["scams_stopped"] += 1
            text = f"{person.name} called Zava Bank before paying a {label} scam"
        else:
            self.counts["scams_ignored"] += 1
            text = f"{person.name} ignored a {label} message"
        self._note(person, text, by, "scam")
        self._trace("scam", person, f"{crew} tried a {label} scam on {person.name}", steps or [],
                    text.replace(person.name + " ", "", 1))

    def _maybe_realise(self, person: Person) -> None:
        scam = person.scam
        hours = (float(self.world.runtime.now) - scam["at"]) / 60
        state = {"person": person.who(),
                 "what happened": f"{hours:.0f} hours ago they sent GBP {scam['amount']:,.0f} after this message: "
                                  f"{TACTICS[scam['tactic']]['pitch']} Since then nothing they were promised has happened."}
        fallback = {"yes": min(0.9, hours / 12), "no": 1.0}
        def realised(d: Decision) -> None:
            first = person.name.split()[0]
            outcome = "believes it was a scam and rings the bank" if d.choice == "yes" else "still hopes the money is coming"
            self._trace("realise", person, f"{person.name}, {hours:.0f} hours after paying",
                        [step(f"Does {first} now believe it was a scam?", {"yes": "Yes", "no": "Not yet"}, d)], outcome)
            if d.choice == "yes":
                self._call_bank(person, d.by)

        self.chooser.choose(state, yes_no("Does this person now believe they were scammed?"), fallback, realised)

    def _call_bank(self, person: Person, by: str) -> None:
        scam = person.scam
        if not scam or scam["called"] or not self.dial.take():
            return
        statement = TACTICS[scam["tactic"]]["call"].format(amount=f"GBP {scam['amount']:,.0f}")
        if person.circumstance:
            statement += " " + CIRCUMSTANCES[person.circumstance][1]
        scam["called"] = True

        def raise_claim(reading: dict[str, Any] | None) -> None:
            try:
                self.world.customer_calls(scam["payment_id"], statement, reading)
            except ValueError:
                scam["called"] = False
                self.dial.give_back()
                return
            self.counts["calls"] += 1
            self._note(person, f"{person.name} rang the bank: \"{statement[:90]}...\"", by, "call")
            person.scam = None

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is None:
            from verticals.banking.worlds.statements import rules_reading
            raise_claim(rules_reading(statement).to_dict())
            return

        async def read_then_raise() -> None:
            from verticals.banking.worlds.statements import read_statement
            reading = await read_statement(statement)
            raise_claim(reading.to_dict())

        loop.create_task(read_then_raise())

    # -- joining and leaving ---------------------------------------------------------------------

    def _joins(self):
        env = self.world.runtime.env
        while True:
            yield env.timeout(_JOIN_EVERY_MINUTES * self.rng.uniform(0.6, 1.4))
            if not self.reserve:
                continue
            profile = self.reserve.pop()
            index = len(self.world.customers) + 1
            customer_id = reference_data._customer_id(index)
            if customer_id in self.world.customers:
                continue
            account_id = reference_data._account_id(index)
            self.world.customers[customer_id] = Customer(
                id=customer_id, display_name=profile["name"], segment="personal",
                home_location_id=self.rng.choice(reference_data.RETAIL_LOCATIONS), account_id=account_id)
            self.world.accounts[account_id] = Account(
                id=account_id, customer_id=customer_id, sort_code=f"SYN-{self.rng.randint(10, 99)}-{self.rng.randint(10, 99)}",
                kind="current", balance_gbp=BAND_BUDGET[profile["stage"]["band"]], location_id=reference_data.LOC_RETAIL_NORTH)
            person = self._adopt(customer_id, profile)
            self.counts["joined"] += 1
            self._emit("banking.customer.joined", person, {"name": person.name})
            self._note(person, f"{person.name} opened an account with Zava Bank", "world", "join")

    def on_decision(self, applied: Any) -> None:
        """After a reimbursement decision, a customer who was let down may leave."""
        claim = self.world.fraud_claims.get(str(applied.payload.get("claim_id")))
        person = self.people.get(claim.customer_id) if claim else None
        if person is None:
            return
        option = str(applied.payload.get("option_id") or "")
        outcome = ("refused" if "REFUSE" in option else "partly refunded" if "CAPPED" in option or "PARTIAL" in option
                   else "fully refunded")
        state = {"person": person.who(),
                 "what happened": f"Zava Bank {outcome} their GBP {claim.amount_gbp:,.0f} scam claim."}
        fallback = {"yes": 0.6 if outcome == "refused" else 0.05, "no": 1.0}
        self.chooser.choose(state, yes_no("Would this person move their account to another bank?"),
                            fallback, lambda d: self._leave(person, outcome, d.choice, d.by, d))

    def _leave(self, person: Person, outcome: str, answer: str, by: str, decision: Decision | None = None) -> None:
        if decision is not None:
            first = person.name.split()[0]
            self._trace("leave", person, f"{person.name}, after being {outcome}",
                        [step(f"Would {first} move their account to another bank?", {"yes": "Yes, leave", "no": "No, stay"}, decision)],
                        "closes the account" if answer == "yes" else "stays with Zava Bank")
        if answer != "yes":
            self._note(person, f"{person.name} is staying with Zava Bank after being {outcome}", by, "stay")
            return
        customer = self.world.customers[person.customer_id]
        customer.status = "left"
        self._account(person).status = "closed"
        self.counts["left"] += 1
        self._emit("banking.customer.left", person, {"after": outcome})
        self._note(person, f"{person.name} closed their account after being {outcome}", by, "leave")

    # -- the floor ------------------------------------------------------------------------------

    def render(self) -> dict[str, Any]:
        active = sum(1 for p in self.people.values() if self.world.customers[p.customer_id].status != "left")
        decided = self.chooser.decided
        total = decided["laya"] + decided["rules"]
        unknown = sorted(
            (p for p in self.people.values()
             if p.circumstance and not self.world.customers[p.customer_id].vulnerability_flag
             and self.world.customers[p.customer_id].status != "left"),
            key=lambda p: p.since, reverse=True)[:8]
        crews = {crew: {TACTICS[t]["label"]: {"tried": r[0], "paid": r[1]} for t, r in record.items() if r[0]}
                 for crew, record in sorted(self.crew_record.items())}
        return {"people": active, **self.counts, "spent_gbp": round(self._spent_gbp, 2),
                "decided_by_laya": decided["laya"], "decided_by_rules": decided["rules"],
                "laya_share": round(decided["laya"] / total, 3) if total else 0.0,
                "laya_avg_ms": self.chooser.avg_ms(),
                "cases_per_hour": self.dial.per_hour, "cases_opened": self.dial.taken,
                "decisions": list(self.decisions), "scam_decisions": list(self.scam_decisions),
                "unknown_to_bank": [{"name": p.name, "circumstance": CIRCUMSTANCES[p.circumstance][0]} for p in unknown],
                "crews": crews, "feed": list(self.feed), "stories": list(self.stories)}


_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September",
           "October", "November", "December")
_DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _when(now_minutes: float) -> str:
    day = int(now_minutes // 1440)
    hour = int((now_minutes % 1440) // 60)
    part = "morning" if 6 <= hour < 12 else "afternoon" if 12 <= hour < 18 else "evening" if 18 <= hour < 23 else "night"
    return f"{_DAYS[day % 7]} {part}"
