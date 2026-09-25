"""Zava Bank deterministic actor world.

Owns the synthetic bank: retail customers and accounts, payment rails, the
receiving-provider estate, fraud claims, and the wholesale book of corporate
clients, counterparties, limits, exposures, positions and collateral.

Three things make this world read as a live institution rather than a static
diagram:

* it is seeded at institution scale;
* continuous SimPy loops keep payments settling and exposures revaluing, so
  the world is never still even when no workflow is running;
* the three seeded fraud claims differ only in their evidence, so the three
  demo outcomes are a property of the facts rather than of a code path.

Only ``sensor.tripped`` on the fraud sensor opens an objective. Background
loops emit ``banking.*`` events for life and never spawn work.

Every world event declares the organisational ``function`` that owns the
activity. The observatory relay forwards function-tagged world events as
ambient activity, so the organisation visibly works even when no workflow is
running. A world event without a function stays out of the visual stream.
"""
from __future__ import annotations

import copy
import dataclasses
import math
import os
import random
from collections import deque
from typing import Any

from api.server.world.model import SimulationCommand, SimulationEvent
from api.server.world.runtime import SimulationRuntime
from verticals.banking.fraud_constants import (
    FRAUD_CLAIM_BY_SCENARIO,
    FRAUD_COMMAND_TYPE,
    FRAUD_FUNCTION,
    FRAUD_RAIL_CHAPS,
    FRAUD_RAIL_FPS,
    FRAUD_REIMBURSEMENT_CAP_GBP,
    FRAUD_SCENARIOS,
    FRAUD_SENSOR_ID,
    FRAUD_SOURCE_EVENT_TYPE,
    FRAUD_STORY_BY_SCENARIO,
    FRAUD_SUCCESS_EVENT,
    FRAUD_WORKFLOW_TYPE,
)
from verticals.banking.flags import world_life_enabled, world_screening_enabled
from verticals.banking.support_constants import (
    MULE_COMMAND_TYPE,
    MULE_SENSOR_ID,
    MULE_SUCCESS_EVENT,
    MULE_WORKFLOW_TYPE,
)
from verticals.banking.worlds import reference_data
from verticals.banking.worlds.screening import default_screener
from verticals.banking.worlds.reactions import DECISION_WORDS, decision_kind, default_reactor, draw, reaction_odds
from verticals.banking.worlds.model import (
    Account,
    BeneficiaryAccount,
    CollateralAgreement,
    CorporateClient,
    Counterparty,
    CreditLimit,
    Customer,
    Exposure,
    FraudClaim,
    Investigation,
    Payment,
    PaymentRail,
    PaymentServiceProvider,
    ReimbursementCommand,
    ReimbursementEvaluation,
    TradingPosition,
)

# Background-life cadences, in synthetic minutes.
_PAYMENT_TICK_MINUTES = 3
_MARKET_TICK_MINUTES = 11
_RAIL_TICK_MINUTES = 7

_PAYMENTS_PER_TICK = 6
_EXPOSURES_PER_TICK = 4
_POSITIONS_PER_TICK = 3

# Organisational owner of each kind of world activity.
FUNCTION_PAYMENTS = "payments"
FUNCTION_CREDIT = "credit-risk"
FUNCTION_MARKETS = "markets"
FUNCTION_FINCRIME = "financial-crime"

# Bounded views keep /api/world/state small enough to poll every second. The
# full book (2,400 customers, 3,000+ payments) stays in the world; the
# snapshot carries counts plus the records a person can actually read.
_RECENT_SETTLEMENTS = 24
_RECENT_FLAGS = 8

# Phase 2 cadence, in synthetic minutes: a new payment arrives about every
# half hour and about a third are scams into a mule account. At the demo
# speed that opens a mule case every few minutes.
_NEW_PAYMENT_MINUTES = float(os.environ.get("BANKING_NEW_PAYMENT_MINUTES", "30"))
_SCAM_SHARE = float(os.environ.get("BANKING_SCAM_SHARE", "0.35"))
_MULE_CASE_CUSTOMERS = 2
_MULE_DISPOSITIONS = {
    "SYN-MULE-OPTION-RESTRAIN": "restrained",
    "SYN-MULE-OPTION-MONITOR": "monitored",
    "SYN-MULE-OPTION-CLOSE": "closed",
}
_MULE_INACTIVE = {"restrained", "closed", "frozen"}
_TOP_POSITIONS = 12


class ClaimObservationUnavailableError(RuntimeError):
    """Raised when no fraud claim scenario is active."""


def _json_value(value: Any) -> Any:
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    return value


def _record_view(record: Any) -> dict[str, Any]:
    return _json_value(dataclasses.asdict(record))


# Claims raised on demand. Their outcome follows from the drawn facts
# (amount, vulnerability, warnings) through the same admission, agent,
# governance and persona path as the seeded stories.
GENERATED_CLAIM_KINDS = ("any", "high-value", "vulnerable")
_CLAIM_WINDOW_MINUTES = 5 * 24 * 60.0


def _sync_record(record: Any, view: dict[str, Any]) -> None:
    for field in dataclasses.fields(record):
        if field.name in view:
            setattr(record, field.name, copy.deepcopy(view[field.name]))


def _rebuild(cls: type, view: dict[str, Any]) -> Any:
    return cls(**{f.name: copy.deepcopy(view[f.name]) for f in dataclasses.fields(cls) if f.name in view})


class ZavaBankWorld:
    """A bounded, deterministic synthetic universal bank."""

    def __init__(
        self,
        seed: int = reference_data.SEED,
        *,
        runtime: SimulationRuntime | None = None,
        screener: Any = None,
        reactor: Any = None,
    ) -> None:
        self.seed = seed
        self.runtime = runtime if runtime is not None else SimulationRuntime(seed)
        # Phase 2 (BANKING_WORLD_SCREENING=1): new payments carry references
        # the bank screens; mule accounts are hidden world truth.
        self._screening = world_screening_enabled()
        self._life_enabled = world_life_enabled()
        self.life: Any = None
        self._screener = screener
        self._mule_ids: set[str] = set()
        self._references: dict[str, str] = {}
        self._flags: dict[str, list[dict[str, Any]]] = {}
        self._mule_cases: dict[str, dict[str, Any]] = {}
        self._mule_case_by_sensor: dict[str, str] = {}
        # Which claim each sensor event raised, the claims whose case ended with
        # no decision, and how far the journal has been read for such endings.
        self._claim_by_sensor: dict[str, str] = {}
        self._ended_claims: set[str] = set()
        self._endings_read = 0
        # Claims copied in from another replica (the Functions worker's copy);
        # this copy never sees how they end, and the API world owns the rules.
        self._adopted_claims: set[str] = set()
        self._new_payments = 0
        self._scam_rng = random.Random(seed + 303)
        self.payments_screened_total = 0
        self.payments_flagged_total = 0
        self.recent_flags: deque[dict[str, Any]] = deque(maxlen=_RECENT_FLAGS)
        self._reactor = reactor
        self._reaction_rng = random.Random(seed + 404)
        self.customer_reactions: dict[str, int] = {"accepts": 0, "chases": 0, "complains": 0}

        self.customers: dict[str, Customer] = {}
        self.accounts: dict[str, Account] = {}
        self.payment_service_providers: dict[str, PaymentServiceProvider] = {}
        self.payment_rails: dict[str, PaymentRail] = {}
        self.payments: dict[str, Payment] = {}
        self.beneficiaries: dict[str, BeneficiaryAccount] = {}
        self.fraud_claims: dict[str, FraudClaim] = {}
        self.reimbursement_commands: dict[str, ReimbursementCommand] = {}
        self.reimbursement_evaluations: dict[str, ReimbursementEvaluation] = {}
        self.investigations: dict[str, Investigation] = {}

        self.corporate_clients: dict[str, CorporateClient] = {}
        self.counterparties: dict[str, Counterparty] = {}
        self.credit_limits: dict[str, CreditLimit] = {}
        self.exposures: dict[str, Exposure] = {}
        self.positions: dict[str, TradingPosition] = {}
        self.collateral_agreements: dict[str, CollateralAgreement] = {}

        self.claim_story_status: dict[str, str] = {}

        # Running totals for the operations floor. Counters, not lists: the
        # book is large and the snapshot is polled every second.
        self.payments_settled_total = 0
        self.settled_value_gbp = 0.0
        self.positions_marked_total = 0
        self.recent_settlements: deque[dict[str, Any]] = deque(
            maxlen=_RECENT_SETTLEMENTS
        )

        self._installed = False
        self._scenario_events: dict[str, SimulationEvent] = {}
        self._scenario_trace_overrides: dict[str, str] = {}
        self._active_claim_id: str | None = None
        # claim id -> the scenario that raised it and its causal trace, for
        # the seeded stories and for claims raised on demand alike.
        self._claim_scenarios: dict[str, str] = {}
        self._claim_traces: dict[str, str] = {}
        self._generated_claims = 0
        # Phase 3: claims raised when the presenter reports a customer's call,
        # with the customer's words and the (advisory) reading of them.
        self._statements: dict[str, dict[str, Any]] = {}
        self._called_claims = 0
        self._processed_commands: dict[str, tuple[SimulationCommand, SimulationEvent]] = {}

    # -- lifecycle ---------------------------------------------------------

    def install(self) -> None:
        if self._installed:
            return
        self.runtime.emit(
            "simulation.started",
            actor_id="scenario:zava-bank",
            payload={"seed": self.seed, "scale": "demo"},
        )
        self._seed(self.payment_service_providers,
                   reference_data.build_payment_service_providers(),
                   "banking.psp.seeded")
        self._seed(self.payment_rails, reference_data.build_payment_rails(),
                   "banking.rail.seeded")
        self._seed(self.customers, reference_data.build_customers(),
                   "banking.customer.seeded", quiet=True)
        self._seed(self.accounts, reference_data.build_accounts(),
                   "banking.account.seeded", quiet=True)
        self._seed(self.beneficiaries, reference_data.build_beneficiaries(),
                   "banking.beneficiary.seeded", quiet=True)
        self._seed(self.payments, reference_data.build_payments(),
                   "banking.payment.seeded", quiet=True)
        self._seed(self.fraud_claims, reference_data.build_fraud_claims(),
                   "banking.fraud_claim.seeded")
        self._seed(self.corporate_clients, reference_data.build_corporate_clients(),
                   "banking.corporate_client.seeded", quiet=True)
        self._seed(self.counterparties, reference_data.build_counterparties(),
                   "banking.counterparty.seeded", quiet=True)
        self._seed(self.credit_limits, reference_data.build_credit_limits(),
                   "banking.credit_limit.seeded", quiet=True)
        self._seed(self.exposures, reference_data.build_exposures(),
                   "banking.exposure.seeded")
        self._seed(self.positions, reference_data.build_positions(),
                   "banking.position.seeded", quiet=True)
        self._seed(self.collateral_agreements,
                   reference_data.build_collateral_agreements(),
                   "banking.collateral.seeded", quiet=True)

        if not self._life_enabled:
            # Without people living in it, the rails replay the seeded book.
            self.runtime.process(self._payments_loop())
        self.runtime.process(self._market_loop())
        if self._screening:
            self._mule_ids = set(reference_data.mule_beneficiary_ids())
            self._references = reference_data.build_payment_references(
                self.payments.values(), self._mule_ids
            )
            if self._screener is None:
                self._screener = default_screener()
            if self._reactor is None:
                self._reactor = default_reactor()
            if self._life_enabled:
                from verticals.banking.worlds.life import Life

                self.life = Life(self)
                self.life.install()
            else:
                self.runtime.process(self._new_payments_loop())
        self.runtime.process(self._rail_loop())
        self._installed = True

    def on_service_activate(self) -> None:
        from verticals.banking.worlds.active import register_active_banking_world

        register_active_banking_world(self)

    def on_service_deactivate(self) -> None:
        from verticals.banking.worlds.active import unregister_active_banking_world

        unregister_active_banking_world(self)

    def _seed(
        self,
        destination: dict[str, Any],
        records: list[Any],
        event_type: str,
        *,
        quiet: bool = False,
    ) -> None:
        """Seed a collection.

        ``quiet`` collections are installed without a per-record journal
        event. At institution scale a per-record event for every account and
        payment would bury the causal journal in setup noise; one summary
        event preserves provenance without drowning the signal.
        """
        for record in records:
            destination[record.id] = record
        if quiet:
            self.runtime.emit(
                event_type,
                actor_id=f"collection:{event_type}",
                payload={"count": len(records), "summary": True},
            )
            return
        for record in records:
            payload = _record_view(record)
            payload.pop("last_event_id", None)
            event = self.runtime.emit(event_type, actor_id=record.id, payload=payload)
            record.last_event_id = event.event_id

    # -- continuous life ---------------------------------------------------

    def _payments_loop(self):
        """Settle a handful of synthetic payments every few minutes."""
        rng = self.runtime.rng
        payment_ids = [
            payment_id
            for payment_id, payment in self.payments.items()
            if payment.status == "settled"
        ]
        while True:
            yield self.runtime.env.timeout(_PAYMENT_TICK_MINUTES)
            if not payment_ids:
                continue
            for _ in range(_PAYMENTS_PER_TICK):
                payment = self.payments[rng.choice(payment_ids)]
                if payment.status != "settled":
                    continue  # a customer called about it: it is under a claim now
                payment.version += 1
                event = self.runtime.emit(
                    "banking.payment.settled",
                    actor_id=payment.id,
                    target_id=payment.rail_id,
                    payload={
                        "rail_id": payment.rail_id,
                        "amount_gbp": payment.amount_gbp,
                        "location_id": payment.location_id,
                        "function": FUNCTION_PAYMENTS,
                    },
                )
                payment.last_event_id = event.event_id
                self.payments_settled_total += 1
                self.settled_value_gbp += payment.amount_gbp
                self.recent_settlements.append(
                    {
                        "payment_id": payment.id,
                        "rail_id": payment.rail_id,
                        "amount_gbp": payment.amount_gbp,
                        "sim_time": event.sim_time,
                        "event_id": event.event_id,
                    }
                )

    def _rail_loop(self):
        """Publish rail throughput so the payment floor keeps breathing.

        Throughput is telemetry, not material state, so it deliberately does
        not bump the record version. Evidence freshness guards compare
        versions to prove nothing material moved under a human decision; a
        counter ticking in the background must not be able to invalidate an
        approval that was correct when it was made.
        """
        rng = self.runtime.rng
        while True:
            yield self.runtime.env.timeout(_RAIL_TICK_MINUTES)
            for rail in self.payment_rails.values():
                rail.in_flight_count = rng.randint(40, 900)
                self.runtime.emit(
                    "banking.rail.throughput",
                    actor_id=rail.id,
                    payload={
                        "in_flight_count": rail.in_flight_count,
                        "status": rail.status,
                        "location_id": rail.location_id,
                        "function": FUNCTION_PAYMENTS,
                    },
                )

    def _market_loop(self):
        """Revalue a slice of the wholesale book on every market tick.

        Exposures revalue against their limits (Credit Risk owns that), and a
        few trading positions are marked to market (Markets owns that).
        """
        rng = self.runtime.rng
        exposure_ids = list(self.exposures)
        position_ids = list(self.positions)
        while True:
            yield self.runtime.env.timeout(_MARKET_TICK_MINUTES)
            for _ in range(_EXPOSURES_PER_TICK):
                exposure = self.exposures[rng.choice(exposure_ids)]
                limit = self.credit_limits[exposure.limit_id]
                move = rng.uniform(-0.06, 0.06)
                exposure.current_gbp = max(
                    0.0, round(exposure.current_gbp * (1.0 + move), 2)
                )
                excess = exposure.current_gbp - limit.limit_gbp
                exposure.excess_gbp = round(max(0.0, excess), 2)
                exposure.status = "excess" if exposure.excess_gbp > 0 else "within"
                limit.status = "breached" if exposure.excess_gbp > 0 else "within"
                exposure.version += 1
                event = self.runtime.emit(
                    "banking.exposure.revalued",
                    actor_id=exposure.id,
                    target_id=exposure.counterparty_id,
                    payload={
                        "current_gbp": exposure.current_gbp,
                        "limit_gbp": limit.limit_gbp,
                        "excess_gbp": exposure.excess_gbp,
                        "status": exposure.status,
                        "location_id": exposure.location_id,
                        "function": FUNCTION_CREDIT,
                    },
                )
                exposure.last_event_id = event.event_id
            for _ in range(_POSITIONS_PER_TICK):
                position = self.positions[rng.choice(position_ids)]
                move = rng.uniform(-0.04, 0.04) * position.notional_gbp
                position.mark_to_market_gbp = round(
                    position.mark_to_market_gbp + move, 2
                )
                position.version += 1
                event = self.runtime.emit(
                    "banking.position.marked",
                    actor_id=position.id,
                    target_id=position.counterparty_id,
                    payload={
                        "instrument": position.instrument,
                        "notional_gbp": position.notional_gbp,
                        "mark_to_market_gbp": position.mark_to_market_gbp,
                        "location_id": position.location_id,
                        "function": FUNCTION_MARKETS,
                    },
                )
                position.last_event_id = event.event_id
                self.positions_marked_total += 1

    # -- what the bank notices (phase 2) ------------------------------------

    def _new_payments_loop(self):
        """New payments arrive; some are scams into mule accounts. All are screened."""
        rng = self._scam_rng
        customers = sorted(c for c, customer in self.customers.items() if customer.status == "active")
        ordinary = sorted(b for b in self.beneficiaries if b not in self._mule_ids)
        while True:
            yield self.runtime.env.timeout(_NEW_PAYMENT_MINUTES * rng.uniform(0.6, 1.4))
            self._note_ended_cases()
            mules = self._active_mules()
            if mules and rng.random() < _SCAM_SHARE:
                amount = round(math.exp(rng.uniform(math.log(150), math.log(9_000))) / 5) * 5
                self._new_payment(rng.choice(customers), rng.choice(mules),
                                  rng.choice(reference_data.SCAM_REFERENCES), float(amount))
            else:
                self._new_payment(rng.choice(customers), rng.choice(ordinary),
                                  rng.choice(reference_data.ORDINARY_REFERENCES), float(rng.randint(5, 2_500)))

    def _active_mules(self) -> list[str]:
        return [b for b in sorted(self._mule_ids) if self.beneficiaries[b].status not in _MULE_INACTIVE]

    def _new_payment(self, customer_id: str, beneficiary_id: str, reference: str, amount: float) -> Payment:
        self._new_payments += 1
        customer = self.customers[customer_id]
        payment = Payment(
            id=f"SYN-PAY-N{self._new_payments:05d}", from_account_id=customer.account_id,
            to_beneficiary_id=beneficiary_id, rail_id=FRAUD_RAIL_FPS if amount < 5_000 else FRAUD_RAIL_CHAPS,
            amount_gbp=amount, location_id=customer.home_location_id,
        )
        self.payments[payment.id] = payment
        self._references[payment.id] = reference
        event = self.runtime.emit(
            "banking.payment.settled",
            actor_id=payment.id,
            target_id=beneficiary_id,
            payload={
                "rail_id": payment.rail_id,
                "amount_gbp": amount,
                "reference": reference,
                "customer_id": customer_id,
                "location_id": payment.location_id,
                "function": FUNCTION_PAYMENTS,
            },
        )
        payment.last_event_id = event.event_id
        self.payments_settled_total += 1
        self.settled_value_gbp += amount
        self.recent_settlements.append({
            "payment_id": payment.id, "rail_id": payment.rail_id, "amount_gbp": amount,
            "sim_time": event.sim_time, "event_id": event.event_id, "reference": reference,
        })
        self._screener.submit(reference, lambda screening, pid=payment.id: self._apply_screening(pid, screening))
        return payment

    def _apply_screening(self, payment_id: str, screening: Any) -> SimulationEvent | None:
        """The screen's answer for one payment; flag it and maybe open a mule case."""
        payment = self.payments.get(payment_id)
        if payment is None:
            return None
        self.payments_screened_total += 1
        if not screening.flagged:
            return None
        account = self.accounts.get(payment.from_account_id)
        customer_id = account.customer_id if account is not None else None
        reference = self._references.get(payment_id, "")
        record = {
            "payment_id": payment_id, "customer_id": customer_id, "reference": reference,
            "amount_gbp": payment.amount_gbp, **screening.to_dict(),
        }
        beneficiary_id = payment.to_beneficiary_id
        self._flags.setdefault(beneficiary_id, []).append(record)
        self.payments_flagged_total += 1
        flagged = self.runtime.emit(
            "banking.payment.flagged",
            actor_id=payment_id,
            target_id=beneficiary_id,
            cause_event_id=payment.last_event_id,
            payload={**record, "beneficiary_id": beneficiary_id, "function": FUNCTION_FINCRIME},
        )
        self.recent_flags.append({**record, "beneficiary_id": beneficiary_id, "event_id": flagged.event_id})
        return self._maybe_open_mule_case(beneficiary_id, flagged) or flagged

    def _maybe_open_mule_case(self, beneficiary_id: str, cause: SimulationEvent) -> SimulationEvent | None:
        """Trip the mule sensor once flagged payments from enough customers land here."""
        self._note_ended_cases()
        case = self._mule_cases.get(beneficiary_id)
        if case is not None and case["status"] == "open":
            return None
        if self._mule_case_waits(beneficiary_id):
            return None
        flags = self._flags.get(beneficiary_id, [])
        fresh = flags[case["flags_at_decision"]:] if case is not None else flags
        customers = sorted({f["customer_id"] for f in fresh if f["customer_id"]})
        if len(customers) < _MULE_CASE_CUSTOMERS:
            return None
        # Only a case that will open spends one of the world's case tokens.
        if self.life is not None and not self.life.dial.take():
            return None
        beneficiary = self.beneficiaries[beneficiary_id]
        took_review = beneficiary.status == "open"
        if took_review:
            beneficiary.status = "under_review"
            beneficiary.version += 1
        round_ = (case["round"] + 1) if case is not None else 1
        sensor = self.runtime.emit(
            "sensor.tripped",
            actor_id=MULE_SENSOR_ID,
            target_id=beneficiary_id,
            cause_event_id=cause.event_id,
            trace_id=cause.trace_id,
            payload={
                "sensor_id": MULE_SENSOR_ID,
                "workflow_type": MULE_WORKFLOW_TYPE,
                "beneficiary_id": beneficiary_id,
                "customer_count": len(customers),
                "flagged_payment_ids": [f["payment_id"] for f in fresh],
                "round": round_,
                "source_event_id": cause.event_id,
                "function": FUNCTION_FINCRIME,
            },
        )
        if took_review:
            beneficiary.last_event_id = sensor.event_id
        self._mule_cases[beneficiary_id] = {
            "status": "open", "trace_id": sensor.trace_id, "round": round_, "sensor_event_id": sensor.event_id,
            "flags": list(fresh), "flags_at_decision": len(flags), "took_review": took_review,
        }
        self._mule_case_by_sensor[sensor.event_id] = beneficiary_id
        return sensor

    def _mule_case_waits(self, beneficiary_id: str) -> bool:
        """One live case per account: a mule case waits while a claim on it is decided.

        The three story accounts are mules by design; their mule case also waits
        until their story has run, so a story is never blocked or voided by one.
        """
        if self._live_claims(beneficiary_id=beneficiary_id):
            return True
        return any(
            scenario_id not in self._scenario_events
            and self.fraud_claims[FRAUD_CLAIM_BY_SCENARIO[scenario_id]].beneficiary_id == beneficiary_id
            for scenario_id in FRAUD_SCENARIOS
        )

    def bind_story_workflow(self, sensor_event: dict[str, Any], workflow_id: str) -> None:
        """Remember which workflow decides a mule case the world opened."""
        beneficiary_id = self._mule_case_by_sensor.get(str((sensor_event or {}).get("event_id") or ""))
        case = self._mule_cases.get(beneficiary_id) if beneficiary_id else None
        if case is not None and case["status"] == "open":
            case["workflow_id"] = workflow_id

    def fail_story_workflow(self, workflow_id: str, reason: str) -> None:
        """The bridge failed a workflow; its objective failure is in the journal now."""
        self._note_ended_cases()

    def _note_ended_cases(self) -> None:
        """Read, from the journal, the cases that ended with no decision applied.

        Every such ending (the orchestration could not be scheduled or gave no
        output, a decline or timeout, a rejected command) fails the case's
        objective, journalled with the case's sensor event as first evidence. A
        claim then stops counting as being decided, and an open mule case closes.
        Nothing a claim's decision reads is changed.
        """
        journal = self.runtime.journal
        start, self._endings_read = self._endings_read, len(journal)
        for event in journal[start:]:
            if event.type not in ("objective.failed", "objective.superseded"):
                continue
            evidence = event.payload.get("evidence_event_ids") or ()
            sensor_id = str(evidence[0]) if evidence else ""
            claim_id = self._claim_by_sensor.get(sensor_id)
            if claim_id is not None:
                self._ended_claims.add(claim_id)
            elif sensor_id in self._mule_case_by_sensor:
                self._close_unresolved(self._mule_case_by_sensor[sensor_id], sensor_id, self._ending_reason(event))

    def _ending_reason(self, failed: SimulationEvent) -> str:
        reason = failed.payload.get("reason")
        cause = self._journal_event(failed.cause_event_id)
        if not reason and cause is not None:
            reason = cause.payload.get("reasoning") or cause.payload.get("error") or cause.payload.get("reason")
        return str(reason or "the case ended with no disposition")

    def _journal_event(self, event_id: str | None) -> SimulationEvent | None:
        journal = self.runtime.journal
        try:
            index = int(str(event_id).removeprefix("evt-")) - 1
        except ValueError:
            return None
        return journal[index] if 0 <= index < len(journal) and journal[index].event_id == event_id else None

    def _close_unresolved(self, beneficiary_id: str, sensor_id: str, reason: str) -> None:
        """A mule case that ends with no disposition closes, so the pattern can reopen it."""
        case = self._mule_cases.get(beneficiary_id)
        if case is None or case["status"] != "open" or case.get("sensor_event_id") != sensor_id:
            return
        case["status"] = "unresolved"
        case["flags_at_decision"] = len(self._flags.get(beneficiary_id, []))
        beneficiary = self.beneficiaries[beneficiary_id]
        restore = (case.get("took_review") and beneficiary.status == "under_review"
                   and not self._live_claims(beneficiary_id=beneficiary_id))
        if restore:
            beneficiary.status = "open"
            beneficiary.version += 1
        event = self.runtime.emit(
            "banking.mule_case.unresolved",
            actor_id=beneficiary_id,
            trace_id=case["trace_id"],
            payload={"beneficiary_id": beneficiary_id, "round": case["round"], "workflow_id": case.get("workflow_id"),
                     "reason": reason, "function": FUNCTION_FINCRIME},
        )
        if restore:
            beneficiary.last_event_id = event.event_id

    def _live_claims(self, *, customer_id: str | None = None, beneficiary_id: str | None = None) -> list[FraudClaim]:
        """Raised claims still being decided that involve this customer or receiving account."""
        return [
            claim for claim in self.fraud_claims.values()
            if claim.id in self._claim_scenarios and claim.status == "reported" and claim.id not in self._ended_claims
            and (claim.customer_id == customer_id or claim.beneficiary_id == beneficiary_id)
        ]

    def _busy(self, customer_id: str, beneficiary_id: str, *, called_only: bool = False) -> str | None:
        """Why a new claim here would move the evidence another live claim is decided on."""
        self._note_ended_cases()
        busy = [
            claim for claim in self._live_claims(customer_id=customer_id, beneficiary_id=beneficiary_id)
            if claim.id not in self._adopted_claims
            and (not called_only or self._claim_scenarios.get(claim.id, "").startswith("call:"))
        ]
        if not busy:
            return None
        whose = f"customer {customer_id}" if busy[0].customer_id == customer_id else f"receiving account {beneficiary_id}"
        return f"{whose} already has a claim being decided ({busy[0].id})"

    def mule_observation(self, beneficiary_id: str) -> dict[str, Any]:
        """The case the bank investigates, built from the world's own records."""
        case = self._mule_cases.get(beneficiary_id)
        if case is None:
            raise ClaimObservationUnavailableError(f"no mule case for {beneficiary_id!r}")
        beneficiary = self.beneficiaries[beneficiary_id]
        case_id = f"SYN-MULE-CASE-{beneficiary_id.removeprefix('SYN-')}-{case['round']}"
        customers = sorted({f["customer_id"] for f in case["flags"] if f["customer_id"]})
        return {
            "story_id": case_id,
            "scenario_id": "mule-pattern",
            "trace_id": case["trace_id"],
            "case": {
                "id": case_id,
                "subject_id": beneficiary_id,
                "subject_kind": "beneficiary",
                "risk_band": beneficiary.risk_band,
                "holder_kind": beneficiary.holder_kind,
                "linked_claim_count": len(customers),
                "balance_gbp": beneficiary.balance_gbp,
                "flagged_payments": [
                    {k: f[k] for k in ("payment_id", "reference", "pattern", "amount_gbp", "screened_by")}
                    for f in case["flags"]
                ],
                "round": case["round"],
                "version": beneficiary.version,
            },
            "evidence_versions": {case_id: beneficiary.version},
        }

    def _apply_mule_command(self, command: SimulationCommand) -> SimulationEvent:
        payload = command.payload
        beneficiary_id = str(payload.get("subject_id") or "")
        option_id = str(payload.get("option_id") or "")
        case = self._mule_cases.get(beneficiary_id)
        disposition = _MULE_DISPOSITIONS.get(option_id)
        reason = None
        if beneficiary_id not in self.beneficiaries:
            reason = f"unknown account {beneficiary_id!r}"
        elif case is None or case["status"] != "open":
            reason = f"no open mule case for {beneficiary_id}"
        elif payload.get("evidence_versions") != self.mule_observation(beneficiary_id)["evidence_versions"]:
            reason = "world evidence moved after the approval checkpoint"
        elif disposition is None:
            reason = f"unknown disposition {option_id!r}"
        if reason is not None:
            return self.runtime.emit(
                "command.rejected", actor_id=command.issued_by, trace_id=command.trace_id,
                payload={"command": command.to_dict(), "reason": reason},
            )
        beneficiary = self.beneficiaries[beneficiary_id]
        beneficiary.status = disposition
        if disposition == "restrained":
            beneficiary.frozen_gbp = round(beneficiary.frozen_gbp + beneficiary.balance_gbp, 2)
            beneficiary.balance_gbp = 0.0
        beneficiary.version += 1
        case["status"] = "decided"
        case["flags_at_decision"] = len(self._flags.get(beneficiary_id, []))
        event = self.runtime.emit(
            MULE_SUCCESS_EVENT,
            actor_id=beneficiary_id,
            trace_id=command.trace_id,
            payload={
                "beneficiary_id": beneficiary_id, "disposition": disposition, "option_id": option_id,
                "workflow_id": payload.get("workflow_id"), "persona": payload.get("persona"),
                "function": FUNCTION_FINCRIME,
            },
        )
        beneficiary.last_event_id = event.event_id
        return event

    def _mule_activity(self, beneficiary_id: str | None = None) -> SimulationEvent:
        """Two scam payments from different customers into one mule account."""
        if not self._screening:
            raise ValueError("mule activity needs BANKING_WORLD_SCREENING=1")
        self._note_ended_cases()
        mules = self._active_mules()
        if beneficiary_id is None:
            free = [b for b in mules if not self._mule_case_waits(b)
                    and (self._mule_cases.get(b) or {}).get("status") != "open"]
            if not free:
                raise ValueError("no mule account is free for a new case")
            target = self._scam_rng.choice(free)
        else:
            target = beneficiary_id
            if target not in mules:
                raise ValueError("no active mule account to send payments to")
        customers = sorted(c for c, customer in self.customers.items() if customer.status == "active")
        start = len(self.runtime.journal)
        for customer_id, reference in zip(self._scam_rng.sample(customers, 2),
                                          ("Safe account transfer as advised by bank", "Release fee to unlock withdrawal")):
            last = self._new_payment(customer_id, target, reference, float(self._scam_rng.randint(400, 6_000)))
        opened = [e for e in self.runtime.journal[start:]
                  if e.type == "sensor.tripped" and e.payload.get("sensor_id") == MULE_SENSOR_ID]
        if opened:
            return opened[-1]
        return next(e for e in reversed(self.runtime.journal) if e.actor_id == last.id)

    # -- scenarios ---------------------------------------------------------

    def bind_scenario_trace(self, scenario_id: str, trace_id: str) -> None:
        if scenario_id not in self._scenario_events:
            raise ValueError(f"scenario {scenario_id!r} is not active")
        if not isinstance(trace_id, str) or not trace_id.strip():
            raise ValueError("trace_id must be a non-empty string")
        self._scenario_trace_overrides[scenario_id] = trace_id
        claim_id = FRAUD_CLAIM_BY_SCENARIO.get(scenario_id)
        if claim_id is not None:
            self._claim_traces[claim_id] = trace_id

    def activate_scenario(self, scenario_id: str) -> SimulationEvent:
        if scenario_id not in FRAUD_SCENARIOS:
            raise ValueError(f"unsupported Banking scenario: {scenario_id!r}")
        if not self._installed:
            raise RuntimeError("ZavaBankWorld must be installed before activation")
        existing = self._scenario_events.get(scenario_id)
        if existing is not None:
            return existing

        claim_id = FRAUD_CLAIM_BY_SCENARIO[scenario_id]
        story_id = FRAUD_STORY_BY_SCENARIO[scenario_id]
        claim = self.fraud_claims[claim_id]
        busy = self._busy(claim.customer_id, claim.beneficiary_id, called_only=True)
        if busy is not None:
            raise ValueError(f"{busy}; start the story once it is decided")
        return self._raise(claim, scenario_id, story_id, keep_inactive=self._screening)

    def _raise(self, claim: FraudClaim, scenario_id: str, story_id: str, *,
               keep_inactive: bool = False) -> SimulationEvent:
        payment = self.payments[claim.payment_id]
        beneficiary = self.beneficiaries[claim.beneficiary_id]
        customer = self.customers[claim.customer_id]

        claim.status = "reported"
        claim.version += 1
        if not (keep_inactive and beneficiary.status in _MULE_INACTIVE):
            beneficiary.status = "under_review"
        beneficiary.version += 1
        customer.status = "in_claim"
        customer.version += 1

        raised = self.runtime.emit(
            FRAUD_SOURCE_EVENT_TYPE,
            actor_id=claim.id,
            target_id=beneficiary.id,
            payload={
                "claim_id": claim.id,
                "customer_id": customer.id,
                "payment_id": payment.id,
                "beneficiary_id": beneficiary.id,
                "amount_gbp": claim.amount_gbp,
                "rail_id": claim.rail_id,
                "vulnerability_flag": claim.vulnerability_flag,
                "location_id": claim.location_id,
                "scenario_id": scenario_id,
                "story_id": story_id,
                "function": FRAUD_FUNCTION,
            },
        )
        claim.last_event_id = raised.event_id

        sensor = self.runtime.emit(
            "sensor.tripped",
            actor_id=FRAUD_SENSOR_ID,
            target_id=claim.id,
            cause_event_id=raised.event_id,
            trace_id=raised.trace_id,
            payload={
                "sensor_id": FRAUD_SENSOR_ID,
                "workflow_type": FRAUD_WORKFLOW_TYPE,
                "scenario_id": scenario_id,
                "story_id": story_id,
                "claim_id": claim.id,
                "amount_gbp": claim.amount_gbp,
                "source_event_id": raised.event_id,
                "function": FRAUD_FUNCTION,
            },
        )
        self._scenario_events[scenario_id] = sensor
        self._claim_by_sensor[sensor.event_id] = claim.id
        self._active_claim_id = claim.id
        self.claim_story_status[story_id] = "active"
        self._claim_scenarios[claim.id] = scenario_id
        self._claim_traces[claim.id] = sensor.trace_id
        return sensor

    def raise_claim(self, kind: str = "any") -> SimulationEvent:
        """Raise a new claim with drawn facts; each call is a new case."""
        if kind not in GENERATED_CLAIM_KINDS:
            raise ValueError(f"unsupported claim kind: {kind!r}")
        if not self._installed:
            raise RuntimeError("ZavaBankWorld must be installed before raising a claim")
        rng = self.runtime.rng
        vulnerable = kind == "vulnerable" or (kind == "any" and rng.random() < 0.25)
        busy = {c.customer_id for c in self.fraud_claims.values() if c.id in self._claim_scenarios}
        customers = [
            cid for cid in sorted(self.customers)
            if self.customers[cid].vulnerability_flag == vulnerable
            and self.customers[cid].status == "active" and cid not in busy
        ]
        beneficiaries = [
            bid for bid in sorted(self.beneficiaries)
            if self.beneficiaries[bid].status == "open" and self.beneficiaries[bid].balance_gbp > 0
        ]
        if not customers or not beneficiaries:
            raise ValueError("no free customer or receiving account to raise a claim against")
        customer = self.customers[rng.choice(customers)]
        beneficiary = self.beneficiaries[rng.choice(beneficiaries)]
        if kind == "high-value":
            amount = rng.uniform(55_000, 120_000)
        elif vulnerable:
            amount = math.exp(rng.uniform(math.log(500), math.log(25_000)))
        else:
            amount = math.exp(rng.uniform(math.log(800), math.log(120_000)))
        amount = float(round(amount / 50) * 50)
        warning_shown = rng.random() < 0.6
        specific_ignored = kind == "any" and not vulnerable and warning_shown and rng.random() < 0.35
        recoverable = float(min(beneficiary.balance_gbp, round(amount * rng.uniform(0.1, 0.45) / 10) * 10))
        rail = FRAUD_RAIL_CHAPS if amount >= 25_000 else FRAUD_RAIL_FPS
        self._generated_claims += 1
        number = self._generated_claims
        payment = Payment(
            id=f"SYN-PAY-G{number:03d}", from_account_id=customer.account_id,
            to_beneficiary_id=beneficiary.id, rail_id=rail, amount_gbp=amount,
            location_id=customer.home_location_id, warning_shown=warning_shown,
        )
        now = float(self.runtime.env.now)
        claim = FraudClaim(
            id=f"SYN-CLAIM-G{number:03d}", customer_id=customer.id, payment_id=payment.id,
            beneficiary_id=beneficiary.id, rail_id=rail, amount_gbp=amount,
            location_id=customer.home_location_id, reported_at_minutes=now,
            deadline_minutes=now + _CLAIM_WINDOW_MINUTES,
            vulnerability_flag=customer.vulnerability_flag, warning_shown=warning_shown,
            specific_warning_ignored=specific_ignored, recoverable_gbp=recoverable,
        )
        self.payments[payment.id] = payment
        self.fraud_claims[claim.id] = claim
        return self._raise(claim, f"generated:{claim.id}", f"SYN-STORY-{claim.id}")

    def customer_calls(self, payment_id: str, statement: str, reading: dict[str, Any] | None) -> SimulationEvent:
        """A customer calls about one of their payments: a new claim on that payment.

        The claim is raised on the record's facts (amount, receiving account,
        warning shown, the customer's vulnerability marker). The customer's
        words and the reading of them travel with the claim as advisory context
        for the agent; they never change what the rules admit.
        """
        text = (statement or "").strip()
        if not text or len(text) > 1_200:
            raise ValueError("the customer's statement must be 1-1,200 characters")
        payment = self.payments.get(payment_id)
        if payment is None:
            raise ValueError(f"unknown payment {payment_id!r}")
        if payment.status != "settled" or any(c.payment_id == payment_id for c in self.fraud_claims.values()):
            raise ValueError(f"payment {payment_id} is already under a claim")
        account = self.accounts[payment.from_account_id]
        customer = self.customers[account.customer_id]
        beneficiary = self.beneficiaries[payment.to_beneficiary_id]
        busy = self._busy(customer.id, beneficiary.id)
        if busy is not None:
            raise ValueError(f"{busy}; call again once it is decided")
        mule_case = self._mule_cases.get(beneficiary.id)
        if mule_case is not None and mule_case["status"] == "open":
            raise ValueError(f"receiving account {beneficiary.id} is under a mule investigation; "
                             "call again once it is decided")
        rng = self.runtime.rng
        self._called_claims += 1
        now = float(self.runtime.env.now)
        claim = FraudClaim(
            id=f"SYN-CLAIM-C{self._called_claims:03d}", customer_id=customer.id, payment_id=payment.id,
            beneficiary_id=beneficiary.id, rail_id=payment.rail_id, amount_gbp=payment.amount_gbp,
            location_id=customer.home_location_id, reported_at_minutes=now,
            deadline_minutes=now + _CLAIM_WINDOW_MINUTES, vulnerability_flag=customer.vulnerability_flag,
            warning_shown=payment.warning_shown,
            recoverable_gbp=float(min(beneficiary.balance_gbp, round(payment.amount_gbp * rng.uniform(0.1, 0.45) / 10) * 10)),
        )
        payment.status = "disputed"
        payment.version += 1
        self.fraud_claims[claim.id] = claim
        self._statements[claim.id] = {"text": text, **(reading or {})}
        return self._raise(claim, f"call:{claim.id}", f"SYN-STORY-{claim.id}", keep_inactive=True)

    def read_customer_statement(self, statement: str):
        """Awaitable reading of a customer's words (Laya, rules when it is down)."""
        from verticals.banking.worlds.statements import read_statement

        return read_statement(statement)

    def adopt_claim(self, observation: dict[str, Any]) -> None:
        """Mirror a claim raised in another replica of this world.

        The observation carries every record the decision reads, with its
        version, so syncing those records makes the evidence match exactly.
        """
        claim_view = observation["claim"]
        payment_view = observation["payment"]
        if claim_view["id"] in self.fraud_claims:
            _sync_record(self.fraud_claims[claim_view["id"]], claim_view)
        else:
            self.fraud_claims[claim_view["id"]] = _rebuild(FraudClaim, claim_view)
        if payment_view["id"] in self.payments:
            _sync_record(self.payments[payment_view["id"]], payment_view)
        else:
            self.payments[payment_view["id"]] = _rebuild(Payment, payment_view)
        for key, store in (
            ("customer", self.customers), ("beneficiary", self.beneficiaries),
            ("rail", self.payment_rails), ("account", self.accounts),
            ("receiving_psp", self.payment_service_providers),
            ("corporate_holder", self.corporate_clients),
        ):
            view = observation.get(key)
            if isinstance(view, dict) and view.get("id") in store:
                _sync_record(store[view["id"]], view)
        claim_id = claim_view["id"]
        self._adopted_claims.add(claim_id)
        self._claim_scenarios[claim_id] = str(observation["scenario_id"])
        self._claim_traces[claim_id] = str(observation["trace_id"])
        self.claim_story_status[str(observation["story_id"])] = "active"
        self._active_claim_id = claim_id

    def run_scenario(self, scenario_id: str) -> dict[str, Any]:
        if scenario_id == "new-fraud-claim" or scenario_id.startswith("new-fraud-claim:"):
            event = self.raise_claim(scenario_id.partition(":")[2] or "any")
        elif scenario_id == "mule-activity" or scenario_id.startswith("mule-activity:"):
            event = self._mule_activity(scenario_id.partition(":")[2] or None)
        else:
            event = self.activate_scenario(scenario_id)
        return {"scenario": scenario_id, "event": event.to_dict()}

    # -- observations ------------------------------------------------------

    def _trace_for_claim(self, claim_id: str) -> str:
        trace = self._claim_traces.get(claim_id)
        if trace is not None:
            return trace
        raise ClaimObservationUnavailableError(
            f"claim {claim_id!r} has no active scenario"
        )

    def observation_for_claim(self, claim_id: str) -> dict[str, Any]:
        """Versioned evidence bundle for one claim.

        Every record the deterministic admission reads appears here with its
        current version, so a later commit can prove the evidence has not
        moved underneath the human decision.
        """
        claim = self.fraud_claims.get(claim_id)
        if claim is None:
            raise ClaimObservationUnavailableError(f"unknown claim {claim_id!r}")
        trace_id = self._trace_for_claim(claim_id)

        customer = self.customers[claim.customer_id]
        payment = self.payments[claim.payment_id]
        beneficiary = self.beneficiaries[claim.beneficiary_id]
        rail = self.payment_rails[claim.rail_id]
        account = self.accounts[customer.account_id]
        psp = self.payment_service_providers[beneficiary.psp_id]

        records = [claim, customer, payment, beneficiary, rail, account, psp]
        corporate = (
            self.corporate_clients.get(beneficiary.holder_id)
            if beneficiary.holder_kind == "corporate"
            else None
        )
        if corporate is not None:
            records.append(corporate)

        scenario_id = self._claim_scenarios[claim_id]
        observation: dict[str, Any] = {
            "story_id": FRAUD_STORY_BY_SCENARIO.get(scenario_id, f"SYN-STORY-{claim_id}"),
            "scenario_id": scenario_id,
            "trace_id": trace_id,
            "reimbursement_cap_gbp": FRAUD_REIMBURSEMENT_CAP_GBP,
            "claim": _record_view(claim),
            "customer": _record_view(customer),
            "payment": _record_view(payment),
            "beneficiary": _record_view(beneficiary),
            "rail": _record_view(rail),
            "account": _record_view(account),
            "receiving_psp": _record_view(psp),
            "corporate_holder": _record_view(corporate) if corporate else None,
            "evidence_versions": {record.id: record.version for record in records},
            "evidence_event_ids": [
                record.last_event_id for record in records if record.last_event_id
            ],
        }
        statement = self._statements.get(claim_id)
        if statement is not None:
            observation["customer_statement"] = dict(statement)
        return observation

    def current_fraud_observation(self) -> dict[str, Any]:
        if self._active_claim_id is None:
            raise ClaimObservationUnavailableError(
                "no fraud claim scenario is active"
            )
        return self.observation_for_claim(self._active_claim_id)

    def build_observation(
        self,
        source_sensor_event: dict[str, Any],
        now: float | None = None,
    ) -> dict[str, Any]:
        payload = source_sensor_event.get("payload") or {}
        if payload.get("sensor_id") == MULE_SENSOR_ID:
            return self.mule_observation(str(payload.get("beneficiary_id") or ""))
        claim_id = payload.get("claim_id") or self._active_claim_id
        if not isinstance(claim_id, str):
            raise ClaimObservationUnavailableError(
                "sensor event carries no claim_id"
            )
        return self.observation_for_claim(claim_id)

    # -- commands ----------------------------------------------------------

    def command_was_processed(self, command_id: str) -> bool:
        return command_id in self._processed_commands

    def command_for_claim_option(
        self,
        *,
        claim_id: str,
        option_id: str,
        workflow_id: str,
        decision_id: str,
        persona: str,
    ) -> SimulationCommand:
        from verticals.banking.actions.fraud_commands import build_reimbursement_command

        return build_reimbursement_command(
            self,
            claim_id=claim_id,
            option_id=option_id,
            workflow_id=workflow_id,
            decision_id=decision_id,
            persona=persona,
        )

    def apply_command(self, command: SimulationCommand) -> SimulationEvent:
        from verticals.banking.actions.fraud_commands import apply_reimbursement_command

        processed = self._processed_commands.get(command.command_id)
        if processed is not None:
            return processed[1]
        if command.type == MULE_COMMAND_TYPE and self._screening:
            event = self._apply_mule_command(command)
            if event.type == MULE_SUCCESS_EVENT:
                self._processed_commands[command.command_id] = (command, event)
            return event
        if command.type != FRAUD_COMMAND_TYPE:
            return self.runtime.emit(
                "command.rejected",
                actor_id=command.issued_by,
                trace_id=command.trace_id,
                payload={
                    "command": command.to_dict(),
                    "reason": f"unsupported command type {command.type!r}",
                },
            )
        event = apply_reimbursement_command(self, command)
        if event.type == FRAUD_SUCCESS_EVENT:
            self._processed_commands[command.command_id] = (command, event)
            if self._screening:
                self._customer_reacts(event)
            if self.life is not None:
                self.life.on_decision(event)
        return event

    def _customer_reacts(self, applied: SimulationEvent) -> None:
        """The customer reacts to the decision, read from the model's mood."""
        claim = self.fraud_claims.get(str(applied.payload.get("claim_id")))
        if claim is None:
            return
        customer = self.customers[claim.customer_id]
        kind = decision_kind(str(applied.payload.get("option_id")))
        who = (
            f"A {'vulnerable ' if claim.vulnerability_flag else ''}{customer.segment} customer who "
            f"lost GBP {claim.amount_gbp:,.0f} to a scam"
        )

        def react(mood: Any) -> None:
            reaction = draw(reaction_odds(mood), self._reaction_rng)
            self.customer_reactions[reaction] = self.customer_reactions.get(reaction, 0) + 1
            self.runtime.emit(
                "banking.customer.reacted",
                actor_id=customer.id,
                target_id=claim.id,
                cause_event_id=applied.event_id,
                trace_id=applied.trace_id,
                payload={
                    "customer_id": customer.id, "claim_id": claim.id, "decision": kind,
                    "reaction": reaction, "upset": round(mood.score, 2), "reacted_by": mood.by,
                    "function": FRAUD_FUNCTION,
                },
            )

        self._reactor.submit(who, DECISION_WORDS[kind], kind, react)

    # -- snapshot ----------------------------------------------------------

    def render_state(self) -> dict[str, Any]:
        """Snapshot for /api/world/state, polled every second by the floor.

        The full book stays in the world. The snapshot carries counts for the
        large collections and full records only for what a person reads:
        the rails, the claims, the beneficiaries under review, the wholesale
        book, the investigations. Serialising every customer and payment on
        every poll made the snapshot 2 MB a second.
        """
        beneficiaries_in_play = [
            _record_view(r)
            for r in self.beneficiaries.values()
            if r.status != "open"
        ]
        positions_by_size = sorted(
            self.positions.values(),
            key=lambda position: abs(position.mark_to_market_gbp),
            reverse=True,
        )
        return {
            "bank": {
                "customer_count": sum(1 for c in self.customers.values() if c.status != "left"),
                "vulnerable_customer_count": sum(
                    1 for c in self.customers.values() if c.vulnerability_flag
                ),
                "account_count": len(self.accounts),
                "payment_count": len(self.payments),
                "beneficiary_count": len(self.beneficiaries),
                "corporate_client_count": len(self.corporate_clients),
                "position_count": len(self.positions),
                "payments_settled_total": self.payments_settled_total,
                "settled_value_gbp": round(self.settled_value_gbp, 2),
                "positions_marked_total": self.positions_marked_total,
                "positions_mtm_gbp": round(
                    sum(p.mark_to_market_gbp for p in self.positions.values()), 2
                ),
            },
            "recent_settlements": list(self.recent_settlements),
            "payment_service_providers": [
                _record_view(r) for r in self.payment_service_providers.values()
            ],
            "payment_rails": [_record_view(r) for r in self.payment_rails.values()],
            "beneficiaries": beneficiaries_in_play,
            # Every hero claim exists from install; `raised` says whether its
            # story has actually started, so a surface never shows a dormant
            # claim as open work.
            "fraud_claims": [
                {
                    **_record_view(r),
                    "raised": r.id in self._claim_scenarios,
                }
                for r in self.fraud_claims.values()
            ],
            "reimbursement_commands": [
                _record_view(r) for r in self.reimbursement_commands.values()
            ],
            "reimbursement_evaluations": [
                _record_view(r) for r in self.reimbursement_evaluations.values()
            ],
            "investigations": [_record_view(r) for r in self.investigations.values()],
            "corporate_clients": [
                _record_view(r) for r in self.corporate_clients.values()
            ],
            "counterparties": [_record_view(r) for r in self.counterparties.values()],
            "credit_limits": [_record_view(r) for r in self.credit_limits.values()],
            "exposures": [_record_view(r) for r in self.exposures.values()],
            "positions": [_record_view(r) for r in positions_by_size[:_TOP_POSITIONS]],
            "collateral_agreements": [
                _record_view(r) for r in self.collateral_agreements.values()
            ],
            **({"screening": self._screening_state()} if self._screening else {}),
            **({"life": self.life.render()} if self.life is not None else {}),
        }

    def _screening_state(self) -> dict[str, Any]:
        return {
            "payments_screened": self.payments_screened_total,
            "payments_flagged": self.payments_flagged_total,
            "mule_cases_open": sum(1 for case in self._mule_cases.values() if case["status"] == "open"),
            "mule_cases_decided": sum(1 for case in self._mule_cases.values() if case["status"] == "decided"),
            "recent_flags": list(self.recent_flags),
            "customer_reactions": dict(self.customer_reactions),
        }
