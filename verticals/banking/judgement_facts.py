"""Banking facts adapters for persona judgement.

Code owns every fact, amount and comparison here; Laya only reads the texts.
Each adapter turns one gate's parked context into the texts to read, the facts
to compare, and plain words for the judge question and the deep review.

Thresholds such as "several linked claims" are code-owned facts, stated here so
the judgement never has to compare two numbers.
"""
from __future__ import annotations

from typing import Any

from api.server.services.judgement.profiles import GateFacts
from verticals.banking.fraud_constraints import (
    OPTION_REFUSE_CAUTION,
    OPTION_REIMBURSE_CAPPED,
    OPTION_REIMBURSE_FULL,
)

SEVERAL_LINKED_CLAIMS = 3
LARGE_MONTHLY_VOLUME_GBP = 500_000.0

_FRAUD_OPTION_WORDS = {
    OPTION_REIMBURSE_FULL: "Reimburse the customer in full",
    OPTION_REIMBURSE_CAPPED: "Reimburse the customer up to the cap",
    OPTION_REFUSE_CAUTION: "Refuse reimbursement under the consumer standard of caution",
}
_MULE_OPTION_WORDS = {
    "SYN-MULE-OPTION-RESTRAIN": "Restrain the account and preserve the balance",
    "SYN-MULE-OPTION-MONITOR": "Keep the account open under enhanced monitoring",
    "SYN-MULE-OPTION-CLOSE": "Close the account and return residual funds",
}
_MERCHANT_OPTION_WORDS = {
    "SYN-MER-OPTION-ONBOARD-STANDARD": "Onboard the merchant on standard terms",
    "SYN-MER-OPTION-ONBOARD-RESERVE": "Onboard the merchant with a rolling reserve",
    "SYN-MER-OPTION-DECLINE": "Decline the merchant's application",
}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _gbp(value: Any) -> str:
    try:
        return f"GBP {float(value):,.0f}"
    except (TypeError, ValueError):
        return "an unknown amount"


def _role_words(role: str) -> str:
    words = str(role).replace("_", " ")
    return words[:1].upper() + words[1:]


def _reasoning(context: dict[str, Any]) -> dict[str, str]:
    return {"agent_reasoning": str(_dict(context.get("ranking")).get("reasoning") or "")}


def _prior_concerns(context: dict[str, Any]) -> tuple[str, ...]:
    prior: list[str] = []
    for entry in context.get("held_by") or []:
        if not isinstance(entry, dict):
            continue
        concerns = [str(c) for c in entry.get("concerns") or [] if c]
        if concerns:
            prior.append(f"{_role_words(entry.get('persona') or 'a reviewer')}: {'; '.join(concerns)}")
    return tuple(prior)


def _authority_sentence(context: dict[str, Any]) -> str:
    if _dict(context.get("authority")).get("allowed") is True:
        return "The recommended value is within your delegated authority."
    return "The recommended value is above your delegated authority."


def _selected(context: dict[str, Any]) -> tuple[str, Any]:
    option = _dict(context.get("selected_option"))
    return str(option.get("option_id") or context.get("selected_option_id") or ""), option.get("value_gbp")


def fraud_gate(context: dict[str, Any]) -> GateFacts:
    observation = _dict(context.get("observation"))
    claim = _dict(observation.get("claim"))
    beneficiary = _dict(observation.get("beneficiary"))
    option_id, value = _selected(context)
    admitted = [str(_dict(o).get("option_id")) for o in context.get("admitted_options") or []]
    vulnerable = claim.get("vulnerability_flag") is True
    ignored = claim.get("specific_warning_ignored") is True

    if ignored:
        warning = "The customer ignored a specific, tailored warning about this payee."
    elif claim.get("warning_shown") is True:
        warning = "A general warning was shown; there is no evidence a specific warning was ignored."
    else:
        warning = "No warning was shown before the payment."
    receiving = (
        f"The money went to a {beneficiary.get('holder_kind') or 'receiving'} account rated "
        f"{beneficiary.get('risk_band') or 'unknown'} risk"
        + (", held by one of Zava Bank's own business clients" if observation.get("corporate_holder") else "")
        + f"; {_gbp(claim.get('recoverable_gbp'))} can still be recovered."
    )
    permitted = "; ".join(_FRAUD_OPTION_WORDS.get(o, o).lower() for o in admitted) or "nothing"
    case = " ".join([
        f"The customer reports an authorised push payment scam of {_gbp(claim.get('amount_gbp'))}.",
        "The customer carries a vulnerability marker." if vulnerable
        else "No vulnerability marker is recorded for the customer.",
        warning,
        f"The rules permit: {permitted}.",
        _authority_sentence(context),
        receiving,
    ])
    return GateFacts(
        texts=_reasoning(context),
        facts={
            "customer_vulnerable": vulnerable,
            "recommends_refusal": option_id == OPTION_REFUSE_CAUTION,
            "refusal_permitted": OPTION_REFUSE_CAUTION in admitted,
            "specific_warning_ignored": ignored,
        },
        recommendation=f"{_FRAUD_OPTION_WORDS.get(option_id, option_id)} ({_gbp(value)})",
        case=case,
        prior_concerns=_prior_concerns(context),
    )


def _case(context: dict[str, Any]) -> dict[str, Any]:
    return _dict(_dict(context.get("observation")).get("case"))


def mule_gate(context: dict[str, Any]) -> GateFacts:
    case = _case(context)
    option_id, _value = _selected(context)
    linked = int(case.get("linked_claim_count") or 0)
    monitoring = option_id.endswith("MONITOR")
    return GateFacts(
        texts=_reasoning(context),
        facts={
            "recommends_monitoring": monitoring,
            "recommends_closure": option_id.endswith("CLOSE"),
            "monitoring_despite_several_claims": monitoring and linked >= SEVERAL_LINKED_CLAIMS,
        },
        recommendation=_MULE_OPTION_WORDS.get(option_id, option_id),
        case=(
            f"A receiving account under investigation for money-mule activity, risk band "
            f"{case.get('risk_band') or 'unknown'}, linked to {linked} fraud claim"
            f"{'' if linked == 1 else 's'}, holding {_gbp(case.get('balance_gbp'))}. "
            + _authority_sentence(context)
        ),
        prior_concerns=_prior_concerns(context),
    )


def merchant_gate(context: dict[str, Any]) -> GateFacts:
    case = _case(context)
    option_id, _value = _selected(context)
    volume = float(case.get("projected_monthly_volume_gbp") or 0.0)
    standard = option_id.endswith("ONBOARD-STANDARD")
    return GateFacts(
        texts=_reasoning(context),
        facts={
            "recommends_standard_terms": standard,
            "recommends_decline": option_id.endswith("DECLINE"),
            "standard_terms_for_large_volume": standard and volume >= LARGE_MONTHLY_VOLUME_GBP,
        },
        recommendation=_MERCHANT_OPTION_WORDS.get(option_id, option_id),
        case=(
            f"A new merchant application, risk band {case.get('risk_band') or 'unknown'}, sector "
            f"{case.get('sector') or 'unknown'}, projected card volume {_gbp(volume)} a month. "
            + _authority_sentence(context)
        ),
        prior_concerns=_prior_concerns(context),
    )
