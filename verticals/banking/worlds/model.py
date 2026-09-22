"""Zava Bank actor-world records.

Plain dataclasses only -- no behaviour. The scenario owns mutation and the
journal owns causality. Every record is synthetic; identifiers carry a
``SYN-`` prefix so no value can be mistaken for a real customer, account,
counterparty or payment.

Scale note: this world is seeded at telco scale (thousands of accounts and
payments) rather than airline scale (a dozen records). A bank that renders
as twelve boxes does not read as a bank.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Retail + payments substrate
# ---------------------------------------------------------------------------


@dataclass
class Customer:
    id: str
    display_name: str
    segment: str            # personal | microbusiness | charity
    home_location_id: str
    account_id: str
    vulnerability_flag: bool = False
    status: str = "active"  # active | in_claim | reimbursed | refused
    version: int = 1
    last_event_id: str | None = None


@dataclass
class Account:
    id: str
    customer_id: str
    sort_code: str
    kind: str               # current | savings | business
    balance_gbp: float
    location_id: str
    status: str = "open"
    version: int = 1
    last_event_id: str | None = None


@dataclass
class PaymentServiceProvider:
    id: str
    display_name: str
    location_id: str
    is_zava: bool = False
    status: str = "reachable"
    version: int = 1
    last_event_id: str | None = None


@dataclass
class PaymentRail:
    id: str
    display_name: str
    location_id: str
    settlement_window_minutes: int
    in_flight_count: int = 0
    status: str = "operational"   # operational | degraded
    version: int = 1
    last_event_id: str | None = None


@dataclass
class Payment:
    id: str
    from_account_id: str
    to_beneficiary_id: str
    rail_id: str
    amount_gbp: float
    location_id: str
    status: str = "settled"   # settled | disputed | recalled
    authorised_by_customer: bool = True
    warning_shown: bool = False
    version: int = 1
    last_event_id: str | None = None


@dataclass
class BeneficiaryAccount:
    """The receiving side of an authorised push payment."""

    id: str
    psp_id: str
    holder_id: str
    holder_kind: str          # individual | corporate
    location_id: str
    risk_band: str            # low | medium | high
    balance_gbp: float
    frozen_gbp: float = 0.0
    status: str = "open"      # open | under_review | frozen
    version: int = 1
    last_event_id: str | None = None


@dataclass
class FraudClaim:
    """A customer's authorised-push-payment fraud claim.

    ``deadline_minutes`` expresses the synthetic decision window. The
    deterministic scope phase reads every field here; nothing about the
    outcome is precomputed.
    """

    id: str
    customer_id: str
    payment_id: str
    beneficiary_id: str
    rail_id: str
    amount_gbp: float
    location_id: str
    reported_at_minutes: float
    deadline_minutes: float
    vulnerability_flag: bool
    warning_shown: bool
    # Refusal turns on whether the customer ignored a *specific, tailored*
    # warning, which is a materially higher bar than "a warning was shown".
    specific_warning_ignored: bool = False
    customer_account_of_own: bool = False
    civil_dispute: bool = False
    status: str = "reported"  # reported | assessed | reimbursed | refused | escalated
    recoverable_gbp: float = 0.0
    version: int = 1
    last_event_id: str | None = None


@dataclass
class ReimbursementCommand:
    id: str
    workflow_id: str
    decision_id: str
    claim_id: str
    option_id: str
    persona: str
    value_gbp: float
    action_types: tuple[str, ...]
    evidence_versions: tuple[tuple[str, int], ...]
    version: int = 1
    last_event_id: str | None = None


@dataclass
class ReimbursementEvaluation:
    id: str
    workflow_id: str
    command_id: str
    claim_id: str
    option_id: str
    status: str
    invariant_results: tuple[str, ...]
    reimbursed_gbp: float
    recovered_from_beneficiary_gbp: float
    receiving_psp_share_gbp: float
    decided_within_window: bool
    vulnerability_respected: bool
    synthetic_cost_gbp: float
    no_action_customer_loss_gbp: float
    version: int = 1
    last_event_id: str | None = None


# ---------------------------------------------------------------------------
# Corporate, markets and credit substrate
#
# Hero 1 only *reads* the corporate client that a mule beneficiary resolves
# to. These records also give the world enough shape to render a whole bank
# rather than one process, and they are the seam Hero 2 builds on.
# ---------------------------------------------------------------------------


@dataclass
class CorporateClient:
    id: str
    display_name: str
    sector: str
    jurisdiction: str
    location_id: str
    risk_band: str            # low | medium | high
    status: str = "active"    # active | under_review | restricted
    version: int = 1
    last_event_id: str | None = None


@dataclass
class Counterparty:
    id: str
    corporate_client_id: str
    display_name: str
    location_id: str
    rating: str
    status: str = "active"
    version: int = 1
    last_event_id: str | None = None


@dataclass
class CreditLimit:
    id: str
    counterparty_id: str
    location_id: str
    limit_gbp: float
    tenor_days: int
    status: str = "within"    # within | breached
    version: int = 1
    last_event_id: str | None = None


@dataclass
class Exposure:
    id: str
    counterparty_id: str
    limit_id: str
    location_id: str
    current_gbp: float
    excess_gbp: float = 0.0
    status: str = "within"    # within | excess
    version: int = 1
    last_event_id: str | None = None


@dataclass
class TradingPosition:
    id: str
    counterparty_id: str
    instrument: str
    location_id: str
    notional_gbp: float
    mark_to_market_gbp: float
    status: str = "open"
    version: int = 1
    last_event_id: str | None = None


@dataclass
class CollateralAgreement:
    id: str
    counterparty_id: str
    location_id: str
    posted_gbp: float
    threshold_gbp: float
    status: str = "sufficient"   # sufficient | call_due | disputed
    version: int = 1
    last_event_id: str | None = None


# ---------------------------------------------------------------------------
# Financial crime substrate
# ---------------------------------------------------------------------------


@dataclass
class Investigation:
    id: str
    subject_id: str           # beneficiary or corporate client
    subject_kind: str         # beneficiary | corporate_client
    location_id: str
    opened_by_workflow_id: str | None = None
    linked_claim_ids: tuple[str, ...] = field(default_factory=tuple)
    status: str = "open"      # open | substantiated | closed
    version: int = 1
    last_event_id: str | None = None
