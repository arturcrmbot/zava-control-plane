"""Banking Hero 1 - deterministic admission for APP fraud reimbursement.

Pure and deterministic. No I/O, no world mutation, no clock. Given one
versioned claim observation it returns every candidate option together with
a feasibility verdict and the reasons behind it.

The division of labour is the point of the whole design:

* this module decides what is *permissible*;
* the agent only ranks what this module has already admitted;
* the governance kernel decides whether the approving human may authorise
  the selected option's value;
* the human decides.

An option this module refuses cannot be rescued by the agent's ranking, and
an option it admits can still be refused by the authority matrix.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

# --- Option identities ----------------------------------------------------

OPTION_REIMBURSE_FULL = "SYN-APP-OPTION-REIMBURSE-FULL"
OPTION_REIMBURSE_CAPPED = "SYN-APP-OPTION-REIMBURSE-CAPPED"
OPTION_REFUSE_CAUTION = "SYN-APP-OPTION-REFUSE-CAUTION"

KNOWN_OPTIONS = frozenset(
    {OPTION_REIMBURSE_FULL, OPTION_REIMBURSE_CAPPED, OPTION_REFUSE_CAUTION}
)

# Action verbs carried on the typed command.
ACTION_CREDIT_CUSTOMER = "credit_customer"
ACTION_FREEZE_BENEFICIARY = "freeze_beneficiary_funds"
ACTION_RAISE_PSP_SPLIT = "raise_receiving_psp_liability_split"
ACTION_RECORD_REFUSAL = "record_refusal_with_reason"
ACTION_OPEN_INVESTIGATION = "open_financial_crime_investigation"


@dataclass(frozen=True, slots=True)
class ClaimAction:
    action_type: str
    resource_id: str | None = None
    amount_gbp: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type,
            "resource_id": self.resource_id,
            "amount_gbp": self.amount_gbp,
        }


@dataclass(frozen=True, slots=True)
class ClaimOption:
    option_id: str
    impact: str
    value_gbp: float
    actions: tuple[ClaimAction, ...]
    evidence_versions: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class ClaimFeasibilityResult:
    option: ClaimOption
    feasible: bool
    reasons: tuple[str, ...]


# --- Helpers --------------------------------------------------------------


def _record(observation: dict[str, Any], key: str) -> dict[str, Any]:
    value = observation.get(key)
    return value if isinstance(value, dict) else {}


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _evidence_versions(observation: dict[str, Any]) -> tuple[tuple[str, int], ...]:
    versions = observation.get("evidence_versions")
    if not isinstance(versions, dict):
        return ()
    return tuple(
        sorted(
            (record_id, version)
            for record_id, version in versions.items()
            if isinstance(record_id, str)
            and isinstance(version, int)
            and not isinstance(version, bool)
        )
    )


def _evidence_is_current(observation: dict[str, Any]) -> bool:
    """Every named record must match the version the observation declares."""
    versions = observation.get("evidence_versions")
    if not isinstance(versions, dict) or not versions:
        return False
    named = ("claim", "customer", "payment", "beneficiary", "rail", "account")
    records = [_record(observation, key) for key in named]
    records = [record for record in records if record]
    if not records:
        return False
    return all(
        isinstance(record.get("id"), str)
        and versions.get(record["id"]) == record.get("version")
        for record in records
    )


def _scope_reasons(observation: dict[str, Any]) -> tuple[str, ...]:
    """Reasons the claim is out of scope entirely. Empty means in scope."""
    claim = _record(observation, "claim")
    payment = _record(observation, "payment")
    reasons: list[str] = []

    if not _evidence_is_current(observation):
        reasons.append("claim evidence is stale relative to the world")
    if claim.get("civil_dispute") is True:
        reasons.append("claim is a civil dispute, not an authorised push payment fraud")
    if claim.get("customer_account_of_own") is True:
        reasons.append("payment was made to an account the customer controls")
    if payment.get("authorised_by_customer") is not True:
        reasons.append("payment was not an authorised push payment")
    amount = _number(claim.get("amount_gbp"))
    if amount is None or amount <= 0:
        reasons.append("claim has no positive disputed amount")
    return tuple(reasons)


# --- Admission ------------------------------------------------------------


def admit_claim_options(observation: dict[str, Any]) -> list[ClaimFeasibilityResult]:
    """Return every candidate option with its deterministic verdict."""
    claim = _record(observation, "claim")
    beneficiary = _record(observation, "beneficiary")
    versions = _evidence_versions(observation)
    scope_reasons = _scope_reasons(observation)

    amount = _number(claim.get("amount_gbp")) or 0.0
    cap = _number(observation.get("reimbursement_cap_gbp")) or 0.0
    recoverable = _number(claim.get("recoverable_gbp")) or 0.0
    vulnerable = claim.get("vulnerability_flag") is True
    warning_shown = claim.get("warning_shown") is True
    specific_warning_ignored = claim.get("specific_warning_ignored") is True
    beneficiary_id = beneficiary.get("id") if isinstance(beneficiary.get("id"), str) else None
    claim_id = claim.get("id") if isinstance(claim.get("id"), str) else None

    within_cap = amount <= cap
    reimbursed_when_capped = min(amount, cap)

    results: list[ClaimFeasibilityResult] = []

    # 1. Reimburse in full -- only when the claim sits inside the cap.
    full_reasons = list(scope_reasons)
    if not within_cap:
        full_reasons.append(
            f"claim of GBP {amount:,.2f} exceeds the reimbursement cap of "
            f"GBP {cap:,.2f}"
        )
    results.append(
        ClaimFeasibilityResult(
            option=ClaimOption(
                option_id=OPTION_REIMBURSE_FULL,
                impact=(
                    "Reimburse the customer in full, freeze what remains in the "
                    "receiving account and raise the receiving provider's share."
                ),
                value_gbp=round(amount, 2),
                actions=(
                    ClaimAction(ACTION_CREDIT_CUSTOMER, claim_id, round(amount, 2)),
                    ClaimAction(
                        ACTION_FREEZE_BENEFICIARY, beneficiary_id, round(recoverable, 2)
                    ),
                    ClaimAction(
                        ACTION_RAISE_PSP_SPLIT, beneficiary_id, round(amount / 2, 2)
                    ),
                    ClaimAction(ACTION_OPEN_INVESTIGATION, beneficiary_id, None),
                ),
                evidence_versions=versions,
            ),
            feasible=not full_reasons,
            reasons=tuple(full_reasons),
        )
    )

    # 2. Reimburse at the cap -- only when the claim exceeds it.
    capped_reasons = list(scope_reasons)
    if within_cap:
        capped_reasons.append(
            f"claim of GBP {amount:,.2f} is within the cap; the full "
            "reimbursement option applies instead"
        )
    results.append(
        ClaimFeasibilityResult(
            option=ClaimOption(
                option_id=OPTION_REIMBURSE_CAPPED,
                impact=(
                    "Reimburse the customer up to the cap, freeze what remains "
                    "in the receiving account and raise the receiving "
                    "provider's share."
                ),
                value_gbp=round(reimbursed_when_capped, 2),
                actions=(
                    ClaimAction(
                        ACTION_CREDIT_CUSTOMER,
                        claim_id,
                        round(reimbursed_when_capped, 2),
                    ),
                    ClaimAction(
                        ACTION_FREEZE_BENEFICIARY, beneficiary_id, round(recoverable, 2)
                    ),
                    ClaimAction(
                        ACTION_RAISE_PSP_SPLIT,
                        beneficiary_id,
                        round(reimbursed_when_capped / 2, 2),
                    ),
                    ClaimAction(ACTION_OPEN_INVESTIGATION, beneficiary_id, None),
                ),
                evidence_versions=versions,
            ),
            feasible=not capped_reasons,
            reasons=tuple(capped_reasons),
        )
    )

    # 3. Refuse under the consumer standard of caution.
    #
    # The vulnerability test is evaluated first and on its own, so when a
    # customer carries a vulnerability marker the rejection reason names that
    # marker rather than some incidental second failure. This is the
    # deterministic override: no ranking, no model judgement and no human
    # discretion can admit a refusal here.
    refuse_reasons = list(scope_reasons)
    if vulnerable:
        refuse_reasons.append(
            "customer carries a vulnerability marker; refusal under the "
            "consumer standard of caution is not permitted"
        )
    else:
        if not warning_shown:
            refuse_reasons.append("no warning evidence is recorded against the payment")
        if not specific_warning_ignored:
            refuse_reasons.append(
                "no evidence the customer ignored a specific, tailored warning; "
                "ordinary carelessness does not meet the standard"
            )
    results.append(
        ClaimFeasibilityResult(
            option=ClaimOption(
                option_id=OPTION_REFUSE_CAUTION,
                impact=(
                    "Refuse reimbursement under the consumer standard of "
                    "caution and record the reason given to the customer."
                ),
                value_gbp=0.0,
                actions=(
                    ClaimAction(ACTION_RECORD_REFUSAL, claim_id, 0.0),
                    ClaimAction(ACTION_OPEN_INVESTIGATION, beneficiary_id, None),
                ),
                evidence_versions=versions,
            ),
            feasible=not refuse_reasons,
            reasons=tuple(refuse_reasons),
        )
    )

    return results


def option_for(
    observation: dict[str, Any], option_id: str
) -> ClaimFeasibilityResult | None:
    return next(
        (
            result
            for result in admit_claim_options(observation)
            if result.option.option_id == option_id
        ),
        None,
    )
