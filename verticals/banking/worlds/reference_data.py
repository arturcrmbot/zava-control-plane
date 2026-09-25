"""Deterministic synthetic reference data for the Zava Bank world.

Everything here is generated from a fixed seed so a reset reproduces the
same bank, the same payments and the same claims. No value is drawn from a
real institution, customer, counterparty or payment.

Scale is deliberate. The bank seeds thousands of accounts and payments so
the operational surfaces read as an institution rather than a diagram. The
world scene binds only the decision-bearing collections, so density in the
data does not become density on the screen.
"""
from __future__ import annotations

import random
from typing import Any

from verticals.banking.fraud_constants import (
    FRAUD_BENEFICIARY_OVER_DELEGATION,
    FRAUD_BENEFICIARY_STANDARD,
    FRAUD_BENEFICIARY_VULNERABLE,
    FRAUD_CLAIM_OVER_DELEGATION,
    FRAUD_CLAIM_OVER_DELEGATION_AMOUNT_GBP,
    FRAUD_CLAIM_OVER_DELEGATION_CUSTOMER,
    FRAUD_CLAIM_OVER_DELEGATION_PAYMENT,
    FRAUD_CLAIM_STANDARD,
    FRAUD_CLAIM_STANDARD_AMOUNT_GBP,
    FRAUD_CLAIM_STANDARD_CUSTOMER,
    FRAUD_CLAIM_STANDARD_PAYMENT,
    FRAUD_CLAIM_VULNERABLE,
    FRAUD_CLAIM_VULNERABLE_AMOUNT_GBP,
    FRAUD_CLAIM_VULNERABLE_CUSTOMER,
    FRAUD_CLAIM_VULNERABLE_PAYMENT,
    FRAUD_RAIL_CHAPS,
    FRAUD_RAIL_FPS,
    FRAUD_RECEIVING_PSP,
    FRAUD_SHARED_CORPORATE_CLIENT,
)
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
    Payment,
    PaymentRail,
    PaymentServiceProvider,
    TradingPosition,
)

SEED = 42

# --- Locations ------------------------------------------------------------
# Normalised [0, 1] coordinates consumed by the world scene. Retail sits on
# the left, the payment rails run through the middle, and the wholesale bank
# sits on the right, so a cross-bank link is a visibly long edge.

LOC_RETAIL_NORTH = "SYN-RETAIL-NORTH"
LOC_RETAIL_SOUTH = "SYN-RETAIL-SOUTH"
LOC_RAIL_FLOOR = "SYN-RAIL-FLOOR"
LOC_PAYMENTS_HUB = "SYN-PAYMENTS-HUB"
LOC_EXTERNAL_PSP = "SYN-EXTERNAL-PSP"
LOC_FINCRIME = "SYN-FINCRIME-UNIT"
LOC_MARKETS = "SYN-MARKETS-FLOOR"
LOC_CREDIT = "SYN-CREDIT-RISK"
LOC_CLIENT_GOV = "SYN-CLIENT-GOVERNANCE"
LOC_WEALTH = "SYN-WEALTH-OFFICE"

LOCATIONS: tuple[tuple[str, str, float, float], ...] = (
    (LOC_RETAIL_NORTH, "Retail North", 0.10, 0.22),
    (LOC_RETAIL_SOUTH, "Retail South", 0.10, 0.72),
    (LOC_PAYMENTS_HUB, "Payments Hub", 0.31, 0.47),
    (LOC_RAIL_FLOOR, "Rail Floor", 0.46, 0.20),
    (LOC_EXTERNAL_PSP, "Receiving Providers", 0.46, 0.76),
    (LOC_FINCRIME, "Financial Crime", 0.62, 0.50),
    (LOC_MARKETS, "Markets Floor", 0.84, 0.20),
    (LOC_CREDIT, "Credit Risk", 0.84, 0.50),
    (LOC_CLIENT_GOV, "Client Governance", 0.70, 0.86),
    (LOC_WEALTH, "Wealth Office", 0.84, 0.80),
)

RETAIL_LOCATIONS = (LOC_RETAIL_NORTH, LOC_RETAIL_SOUTH)

# --- Scale ----------------------------------------------------------------

CUSTOMER_COUNT = 2_400
PAYMENT_COUNT = 3_000
BENEFICIARY_COUNT = 240
CORPORATE_CLIENT_COUNT = 40
COUNTERPARTY_COUNT = 24
POSITION_COUNT = 120

_SEGMENTS = ("personal", "personal", "personal", "microbusiness", "charity")
_SECTORS = (
    "logistics", "wholesale", "construction", "hospitality",
    "professional-services", "manufacturing", "technology", "agriculture",
)
_JURISDICTIONS = ("SYN-UK", "SYN-IE", "SYN-LU", "SYN-SG")
_RATINGS = ("SYN-AA", "SYN-A", "SYN-BBB", "SYN-BB")
_INSTRUMENTS = ("SYN-IRS", "SYN-FXFWD", "SYN-CDS", "SYN-EQSWAP")


def _rng() -> random.Random:
    return random.Random(SEED)


def _customer_id(index: int) -> str:
    return f"SYN-CUST-{index:04d}"


def _account_id(index: int) -> str:
    return f"SYN-ACCT-{index:04d}"


# Customers named by the three seeded claims must exist with the right
# vulnerability flag regardless of where the generator lands them.
_CLAIM_CUSTOMERS = {
    FRAUD_CLAIM_STANDARD_CUSTOMER: False,
    FRAUD_CLAIM_VULNERABLE_CUSTOMER: True,
    FRAUD_CLAIM_OVER_DELEGATION_CUSTOMER: False,
}


def build_payment_service_providers() -> list[PaymentServiceProvider]:
    providers = [
        PaymentServiceProvider(
            id="SYN-PSP-001",
            display_name="Zava Bank",
            location_id=LOC_PAYMENTS_HUB,
            is_zava=True,
        )
    ]
    for index in range(2, 9):
        providers.append(
            PaymentServiceProvider(
                id=f"SYN-PSP-{index:03d}",
                display_name=f"Receiving Provider {index - 1}",
                location_id=LOC_EXTERNAL_PSP,
            )
        )
    return providers


def build_payment_rails() -> list[PaymentRail]:
    return [
        PaymentRail(
            id=FRAUD_RAIL_FPS,
            display_name="Faster Payments",
            location_id=LOC_RAIL_FLOOR,
            settlement_window_minutes=2,
        ),
        PaymentRail(
            id=FRAUD_RAIL_CHAPS,
            display_name="High Value Sterling",
            location_id=LOC_RAIL_FLOOR,
            settlement_window_minutes=45,
        ),
        PaymentRail(
            id="SYN-RAIL-BACS",
            display_name="Bulk Clearing",
            location_id=LOC_RAIL_FLOOR,
            settlement_window_minutes=4_320,
        ),
    ]


def build_customers() -> list[Customer]:
    rng = _rng()
    customers: list[Customer] = []
    for index in range(1, CUSTOMER_COUNT + 1):
        customer_id = _customer_id(index)
        vulnerable = _CLAIM_CUSTOMERS.get(customer_id)
        if vulnerable is None:
            # ~4% of the retail book carries a vulnerability marker.
            vulnerable = rng.random() < 0.04
        customers.append(
            Customer(
                id=customer_id,
                display_name=f"Customer {index:04d}",
                segment=rng.choice(_SEGMENTS),
                home_location_id=rng.choice(RETAIL_LOCATIONS),
                account_id=_account_id(index),
                vulnerability_flag=vulnerable,
            )
        )
    return customers


def build_accounts() -> list[Account]:
    rng = _rng()
    accounts: list[Account] = []
    for index in range(1, CUSTOMER_COUNT + 1):
        accounts.append(
            Account(
                id=_account_id(index),
                customer_id=_customer_id(index),
                sort_code=f"SYN-{rng.randint(10, 99)}-{rng.randint(10, 99)}",
                kind=rng.choice(("current", "current", "current", "savings", "business")),
                balance_gbp=float(rng.randint(240, 86_000)),
                location_id=rng.choice(RETAIL_LOCATIONS),
            )
        )
    return accounts


def build_beneficiaries() -> list[BeneficiaryAccount]:
    """Receiving accounts. Three are named by the seeded claims.

    ``SYN-BENE-002`` is held by ``SYN-CORP-014`` -- the same synthetic
    corporate client that carries the wholesale exposure. That shared
    holder is what lets one claim in Retail and one exposure in Markets
    resolve to a single client.
    """
    rng = _rng()
    named = {
        FRAUD_BENEFICIARY_STANDARD: ("corporate", FRAUD_SHARED_CORPORATE_CLIENT, "high"),
        FRAUD_BENEFICIARY_VULNERABLE: ("individual", "SYN-MULE-001", "medium"),
        FRAUD_BENEFICIARY_OVER_DELEGATION: ("individual", "SYN-MULE-002", "high"),
    }
    beneficiaries: list[BeneficiaryAccount] = []
    for index in range(1, BENEFICIARY_COUNT + 1):
        beneficiary_id = f"SYN-BENE-{index:03d}"
        holder_kind, holder_id, risk_band = named.get(
            beneficiary_id,
            (
                "corporate" if rng.random() < 0.2 else "individual",
                f"SYN-HOLDER-{index:03d}",
                rng.choice(("low", "low", "medium", "high")),
            ),
        )
        beneficiaries.append(
            BeneficiaryAccount(
                id=beneficiary_id,
                psp_id=(
                    FRAUD_RECEIVING_PSP
                    if beneficiary_id in named
                    else f"SYN-PSP-{rng.randint(2, 8):03d}"
                ),
                holder_id=holder_id,
                holder_kind=holder_kind,
                location_id=LOC_EXTERNAL_PSP,
                risk_band=risk_band,
                balance_gbp=float(rng.randint(0, 120_000)),
            )
        )
    return beneficiaries


def build_payments() -> list[Payment]:
    """Settled payment history plus the three payments the claims dispute."""
    rng = _rng()
    payments: list[Payment] = []
    named = {
        FRAUD_CLAIM_STANDARD_PAYMENT: (
            FRAUD_CLAIM_STANDARD_CUSTOMER,
            FRAUD_BENEFICIARY_STANDARD,
            FRAUD_CLAIM_STANDARD_AMOUNT_GBP,
            True,
        ),
        FRAUD_CLAIM_VULNERABLE_PAYMENT: (
            FRAUD_CLAIM_VULNERABLE_CUSTOMER,
            FRAUD_BENEFICIARY_VULNERABLE,
            FRAUD_CLAIM_VULNERABLE_AMOUNT_GBP,
            False,
        ),
        FRAUD_CLAIM_OVER_DELEGATION_PAYMENT: (
            FRAUD_CLAIM_OVER_DELEGATION_CUSTOMER,
            FRAUD_BENEFICIARY_OVER_DELEGATION,
            FRAUD_CLAIM_OVER_DELEGATION_AMOUNT_GBP,
            True,
        ),
    }
    for payment_id, (customer_id, beneficiary_id, amount, warned) in named.items():
        account_index = int(customer_id.rsplit("-", 1)[1])
        payments.append(
            Payment(
                id=payment_id,
                from_account_id=_account_id(account_index),
                to_beneficiary_id=beneficiary_id,
                rail_id=FRAUD_RAIL_FPS if amount < 50_000 else FRAUD_RAIL_CHAPS,
                amount_gbp=amount,
                location_id=LOC_RAIL_FLOOR,
                status="disputed",
                warning_shown=warned,
            )
        )
    for index in range(1, PAYMENT_COUNT + 1):
        payment_id = f"SYN-PAY-{index:05d}"
        amount = float(rng.randint(5, 9_400))
        payments.append(
            Payment(
                id=payment_id,
                from_account_id=_account_id(rng.randint(1, CUSTOMER_COUNT)),
                to_beneficiary_id=f"SYN-BENE-{rng.randint(1, BENEFICIARY_COUNT):03d}",
                rail_id=FRAUD_RAIL_FPS if amount < 5_000 else FRAUD_RAIL_CHAPS,
                amount_gbp=amount,
                location_id=LOC_RAIL_FLOOR,
                warning_shown=rng.random() < 0.18,
            )
        )
    return payments


def build_fraud_claims() -> list[FraudClaim]:
    """The three seeded claims. One engine, three different evidence shapes.

    Nothing here encodes an outcome: the deterministic admission reads the
    vulnerability flag, the warning evidence and the amount, and the three
    cases diverge because those facts differ.
    """
    window = 5 * 24 * 60.0  # five synthetic days, in minutes
    return [
        FraudClaim(
            id=FRAUD_CLAIM_STANDARD,
            customer_id=FRAUD_CLAIM_STANDARD_CUSTOMER,
            payment_id=FRAUD_CLAIM_STANDARD_PAYMENT,
            beneficiary_id=FRAUD_BENEFICIARY_STANDARD,
            rail_id=FRAUD_RAIL_FPS,
            amount_gbp=FRAUD_CLAIM_STANDARD_AMOUNT_GBP,
            location_id=LOC_RETAIL_NORTH,
            reported_at_minutes=0.0,
            deadline_minutes=window,
            vulnerability_flag=False,
            warning_shown=True,
            recoverable_gbp=6_100.0,
        ),
        FraudClaim(
            id=FRAUD_CLAIM_VULNERABLE,
            customer_id=FRAUD_CLAIM_VULNERABLE_CUSTOMER,
            payment_id=FRAUD_CLAIM_VULNERABLE_PAYMENT,
            beneficiary_id=FRAUD_BENEFICIARY_VULNERABLE,
            rail_id=FRAUD_RAIL_FPS,
            amount_gbp=FRAUD_CLAIM_VULNERABLE_AMOUNT_GBP,
            location_id=LOC_RETAIL_SOUTH,
            reported_at_minutes=0.0,
            deadline_minutes=window,
            vulnerability_flag=True,
            warning_shown=False,
            recoverable_gbp=1_250.0,
        ),
        FraudClaim(
            id=FRAUD_CLAIM_OVER_DELEGATION,
            customer_id=FRAUD_CLAIM_OVER_DELEGATION_CUSTOMER,
            payment_id=FRAUD_CLAIM_OVER_DELEGATION_PAYMENT,
            beneficiary_id=FRAUD_BENEFICIARY_OVER_DELEGATION,
            rail_id=FRAUD_RAIL_CHAPS,
            amount_gbp=FRAUD_CLAIM_OVER_DELEGATION_AMOUNT_GBP,
            location_id=LOC_RETAIL_NORTH,
            reported_at_minutes=0.0,
            deadline_minutes=window,
            vulnerability_flag=False,
            warning_shown=True,
            recoverable_gbp=11_400.0,
        ),
    ]


def build_corporate_clients() -> list[CorporateClient]:
    rng = _rng()
    clients: list[CorporateClient] = []
    for index in range(1, CORPORATE_CLIENT_COUNT + 1):
        client_id = f"SYN-CORP-{index:03d}"
        shared = client_id == FRAUD_SHARED_CORPORATE_CLIENT
        clients.append(
            CorporateClient(
                id=client_id,
                display_name=f"Corporate Client {index:03d}",
                sector=rng.choice(_SECTORS),
                jurisdiction=rng.choice(_JURISDICTIONS),
                location_id=LOC_CLIENT_GOV if shared else LOC_MARKETS,
                risk_band="high" if shared else rng.choice(("low", "low", "medium")),
            )
        )
    return clients


def build_counterparties() -> list[Counterparty]:
    rng = _rng()
    counterparties: list[Counterparty] = []
    for index in range(1, COUNTERPARTY_COUNT + 1):
        # SYN-CPTY-007 belongs to the shared corporate client.
        client_id = (
            FRAUD_SHARED_CORPORATE_CLIENT
            if index == 7
            else f"SYN-CORP-{rng.randint(1, CORPORATE_CLIENT_COUNT):03d}"
        )
        counterparties.append(
            Counterparty(
                id=f"SYN-CPTY-{index:03d}",
                corporate_client_id=client_id,
                display_name=f"Counterparty {index:03d}",
                location_id=LOC_MARKETS,
                rating=rng.choice(_RATINGS),
            )
        )
    return counterparties


def build_credit_limits() -> list[CreditLimit]:
    rng = _rng()
    return [
        CreditLimit(
            id=f"SYN-LIMIT-{index:03d}",
            counterparty_id=f"SYN-CPTY-{index:03d}",
            location_id=LOC_CREDIT,
            limit_gbp=float(rng.randint(8, 60) * 1_000_000),
            tenor_days=rng.choice((30, 90, 180, 365)),
        )
        for index in range(1, COUNTERPARTY_COUNT + 1)
    ]


def build_exposures() -> list[Exposure]:
    rng = _rng()
    exposures: list[Exposure] = []
    limits = {limit.counterparty_id: limit for limit in build_credit_limits()}
    for index in range(1, COUNTERPARTY_COUNT + 1):
        counterparty_id = f"SYN-CPTY-{index:03d}"
        limit = limits[counterparty_id]
        # Seeded healthy: every exposure starts inside its limit.
        current = limit.limit_gbp * rng.uniform(0.35, 0.82)
        exposures.append(
            Exposure(
                id=f"SYN-EXP-{index:03d}",
                counterparty_id=counterparty_id,
                limit_id=limit.id,
                location_id=LOC_CREDIT,
                current_gbp=round(current, 2),
            )
        )
    return exposures


def build_positions() -> list[TradingPosition]:
    rng = _rng()
    return [
        TradingPosition(
            id=f"SYN-POS-{index:04d}",
            counterparty_id=f"SYN-CPTY-{rng.randint(1, COUNTERPARTY_COUNT):03d}",
            instrument=rng.choice(_INSTRUMENTS),
            location_id=LOC_MARKETS,
            notional_gbp=float(rng.randint(1, 40) * 1_000_000),
            mark_to_market_gbp=float(rng.randint(-4_000, 9_000) * 1_000),
        )
        for index in range(1, POSITION_COUNT + 1)
    ]


def build_collateral_agreements() -> list[CollateralAgreement]:
    rng = _rng()
    return [
        CollateralAgreement(
            id=f"SYN-CSA-{index:03d}",
            counterparty_id=f"SYN-CPTY-{index:03d}",
            location_id=LOC_CREDIT,
            posted_gbp=float(rng.randint(2, 30) * 1_000_000),
            threshold_gbp=float(rng.randint(1, 5) * 1_000_000),
        )
        for index in range(1, COUNTERPARTY_COUNT + 1)
    ]


# --- What the bank can notice (phase 2, BANKING_WORLD_SCREENING=1) --------------------
# Payment references and which receiving accounts are mule accounts. Both come
# from their own random streams, so the seeded book above is unchanged. Which
# accounts are mules is hidden world truth: it is never put on a record the
# bank's decisions read.
#
# The reference lists were measured against Laya's described-pattern question
# (tools/laya_eval): none of the 30 ordinary references is flagged, 13 of the
# 18 scam references are. The five it misses stay, as a real screen misses some.

ORDINARY_REFERENCES: tuple[str, ...] = (
    "Rent October flat 3", "Council tax September", "Payroll SEP26 ACME LTD", "Invoice 2291 kitchen units",
    "Birthday present for Mia", "Gym membership", "Car insurance renewal", "Nursery fees autumn term",
    "Electricity bill", "Groceries", "Dinner split", "Window cleaner", "Piano lessons", "Season ticket",
    "School trip deposit", "Water bill Q3", "Mortgage overpayment", "Football subs", "Dentist invoice 118",
    "Broadband October", "Wedding gift", "Plumber invoice 442", "Train fare refund", "Book club", "Pocket money",
    "Car service", "Phone bill", "Taxi share", "Garden centre", "Vet bill",
)
SCAM_REFERENCES: tuple[str, ...] = (
    "Safe account transfer as advised by bank", "HMRC penalty urgent payment",
    "Crypto wallet top up guaranteed returns", "Release fee to unlock withdrawal",
    "Loan insurance fee before payout", "Investment platform deposit 3 percent weekly",
    "Transfer to secure account fraud team", "Tax refund processing fee", "Fee to release parcel",
    "Bitcoin mining guaranteed profit", "Court fine settle today", "Account verification transfer",
    "Prize claim admin fee", "Move savings protected account", "Police case funds protection",
    "Customs fee for held parcel", "Forex trading 20 percent monthly", "Unlock inheritance fee",
)
MULE_ACCOUNT_COUNT = 12


def mule_beneficiary_ids() -> tuple[str, ...]:
    """Receiving accounts controlled by fraudsters: the three hero ones and nine more."""
    rng = random.Random(SEED + 101)
    named = {FRAUD_BENEFICIARY_STANDARD, FRAUD_BENEFICIARY_VULNERABLE, FRAUD_BENEFICIARY_OVER_DELEGATION}
    others = [f"SYN-BENE-{index:03d}" for index in range(1, BENEFICIARY_COUNT + 1)]
    others = [bene for bene in others if bene not in named]
    return tuple(sorted(named | set(rng.sample(others, MULE_ACCOUNT_COUNT - len(named)))))


def build_payment_references(payments: list[Payment] | Any, mule_ids: set[str]) -> dict[str, str]:
    """A reference for every payment: scam patterns into mule accounts, ordinary otherwise."""
    rng = random.Random(SEED + 202)
    return {
        payment.id: rng.choice(SCAM_REFERENCES if payment.to_beneficiary_id in mule_ids else ORDINARY_REFERENCES)
        for payment in payments
    }
