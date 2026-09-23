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
from collections import deque
from typing import Any

from api.server.world.model import SimulationCommand, SimulationEvent
from api.server.world.runtime import SimulationRuntime
from verticals.banking.fraud_constants import (
    FRAUD_CLAIM_BY_SCENARIO,
    FRAUD_COMMAND_TYPE,
    FRAUD_FUNCTION,
    FRAUD_REIMBURSEMENT_CAP_GBP,
    FRAUD_SCENARIOS,
    FRAUD_SENSOR_ID,
    FRAUD_SOURCE_EVENT_TYPE,
    FRAUD_STORY_BY_SCENARIO,
    FRAUD_SUCCESS_EVENT,
    FRAUD_WORKFLOW_TYPE,
)
from verticals.banking.worlds import reference_data
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


class ZavaBankWorld:
    """A bounded, deterministic synthetic universal bank."""

    def __init__(
        self,
        seed: int = reference_data.SEED,
        *,
        runtime: SimulationRuntime | None = None,
    ) -> None:
        self.seed = seed
        self.runtime = runtime if runtime is not None else SimulationRuntime(seed)

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

        self.runtime.process(self._payments_loop())
        self.runtime.process(self._market_loop())
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

    # -- scenarios ---------------------------------------------------------

    def bind_scenario_trace(self, scenario_id: str, trace_id: str) -> None:
        if scenario_id not in self._scenario_events:
            raise ValueError(f"scenario {scenario_id!r} is not active")
        if not isinstance(trace_id, str) or not trace_id.strip():
            raise ValueError("trace_id must be a non-empty string")
        self._scenario_trace_overrides[scenario_id] = trace_id

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
        payment = self.payments[claim.payment_id]
        beneficiary = self.beneficiaries[claim.beneficiary_id]
        customer = self.customers[claim.customer_id]

        claim.status = "reported"
        claim.version += 1
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
        self._active_claim_id = claim.id
        self.claim_story_status[story_id] = "active"
        return sensor

    def run_scenario(self, scenario_id: str) -> dict[str, Any]:
        event = self.activate_scenario(scenario_id)
        return {"scenario": scenario_id, "event": event.to_dict()}

    # -- observations ------------------------------------------------------

    def _trace_for_claim(self, claim_id: str) -> str:
        for scenario_id, sensor in self._scenario_events.items():
            if FRAUD_CLAIM_BY_SCENARIO[scenario_id] == claim_id:
                return self._scenario_trace_overrides.get(scenario_id, sensor.trace_id)
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

        scenario_id = next(
            scenario
            for scenario, mapped in FRAUD_CLAIM_BY_SCENARIO.items()
            if mapped == claim_id
        )
        observation: dict[str, Any] = {
            "story_id": FRAUD_STORY_BY_SCENARIO[scenario_id],
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
        return event

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
                "customer_count": len(self.customers),
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
                    "raised": any(
                        FRAUD_CLAIM_BY_SCENARIO[scenario_id] == r.id
                        for scenario_id in self._scenario_events
                    ),
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
        }
