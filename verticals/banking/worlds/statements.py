"""Reading what a customer says when they call: advisory, never deciding.

When the presenter reports a customer's call about a payment, Laya reads the
customer's own words: the kind of scam they describe and circumstances that
could make them vulnerable. The reading is shown on the case and passed to the
agent. It never changes admission: the claim is raised on the record's facts,
and the vulnerability marker on the record still decides.

Measured on 12 authored statements: 9 scam types right; the two confident
errors were a crypto investment with a release fee read as an advance fee,
and a police impersonation read as "not a scam". Narrow circumstance questions
caught 3 of 4 real cues with 2 false alarms on "money worries".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from api.server.services.judgement.laya_client import LayaClient, LayaUnavailable, get_client

MIN_LEAD = 0.25
CUE_LEAD = 0.3

SCAM_QUESTION: dict[str, Any] = {
    "type": "choice",
    "instructions": "What kind of case does the customer describe?",
    "criteria": {
        "bank_impersonation": "Someone pretending to be the customer's bank or its fraud team",
        "authority_impersonation": "Someone pretending to be the police, the tax office or a court",
        "romance": "A fake romantic partner asking for money",
        "investment": "A fake investment, trading or crypto opportunity",
        "purchase": "Paying for goods or tickets that never arrived",
        "invoice": "A supplier or tradesperson's bank details were changed",
        "advance_fee": "An upfront fee for a loan, prize or refund that never came",
        "not_scam": "Not a scam: a dispute with a real trader, or money sent to the customer's own account",
    },
}
CUE_QUESTIONS: dict[str, tuple[str, str]] = {
    "death": ("bereavement", "Does the customer mention that someone close to them has died?"),
    "illness": ("illness or hospital stay", "Does the customer mention an illness, a diagnosis or a stay in hospital?"),
    "confusion": ("confusion or memory", "Does the customer mention getting confused or forgetful?"),
    "isolation": ("isolation", "Does the customer mention being lonely or having nobody to talk to?"),
    "money_worries": ("money worries", "Does the customer mention debts, arrears or being desperate for money?"),
}

_SCAM_WORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("bank_impersonation", ("fraud team", "safe account", "from zava bank", "my bank called")),
    ("authority_impersonation", ("police", "tax office", "hmrc", "court", "arrested")),
    ("romance", ("dating", "boyfriend", "girlfriend", "partner i met")),
    ("investment", ("crypto", "broker", "investment", "trading", "returns", "bond", "pension")),
    ("invoice", ("bank details had changed", "details changed", "invoice")),
    ("advance_fee", ("fee first", "insurance fee", "release fee", "upfront")),
    ("purchase", ("never delivered", "never arrived", "tickets", "marketplace", "seller")),
    ("not_scam", ("own account", "work is poor", "won't come back")),
)
_CUE_WORDS: dict[str, tuple[str, ...]] = {
    "death": ("died", "passed away", "bereaved", "widow"),
    "illness": ("hospital", "diagnosis", "stroke", "illness", "cancer"),
    "confusion": ("confused", "forgetful", "memory"),
    "isolation": ("lonely", "alone", "nobody to talk"),
    "money_worries": ("behind on", "arrears", "desperate", "debt"),
}


@dataclass(frozen=True)
class StatementReading:
    scam_type: str
    scam_lead: float
    cues: list[str] = field(default_factory=list)
    read_by: str = "laya"

    def to_dict(self) -> dict[str, Any]:
        return {"scam_type": self.scam_type, "scam_lead": round(self.scam_lead, 3),
                "cues": list(self.cues), "read_by": self.read_by}


def rules_reading(text: str) -> StatementReading:
    lower = text.lower()
    scam = next((kind for kind, words in _SCAM_WORDS if any(w in lower for w in words)), "unclear")
    cues = [CUE_QUESTIONS[key][0] for key, words in _CUE_WORDS.items() if any(w in lower for w in words)]
    return StatementReading(scam, 1.0 if scam != "unclear" else 0.0, cues, "rules")


async def read_statement(text: str, client: LayaClient | None = None) -> StatementReading:
    client = client if client is not None else get_client()
    if client.available():
        questions: dict[str, Any] = {"scam_type": SCAM_QUESTION}
        questions.update({key: {"type": "noul", "instructions": ask} for key, (_label, ask) in CUE_QUESTIONS.items()})
        try:
            result = await client.ask({"customer_statement": text}, questions)
        except LayaUnavailable:
            return rules_reading(text)
        scam = result.answers["scam_type"]
        cues = [
            CUE_QUESTIONS[key][0]
            for key in CUE_QUESTIONS
            if result.answers[key].top == "yes" and result.answers[key].lead >= CUE_LEAD
        ]
        return StatementReading(scam.top if scam.lead >= MIN_LEAD else "unclear", scam.lead, cues, "laya")
    return rules_reading(text)
