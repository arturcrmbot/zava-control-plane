"""Live golden set: the real banking profiles against a running Laya server.

Skipped unless Laya answers ``$LAYA_URL/health`` (default http://127.0.0.1:8765).
No model quota is used: the deep review is a fake that records whether it
was asked, so each case shows whether Laya decided or handed off.

    LAYA_PORT=8766 ~/.copilot/skills/laya/scripts/start.sh &
    LAYA_URL=http://127.0.0.1:8766 ZAVA_VERTICAL=banking \\
        .venv/bin/python -m pytest tests/api/judgement/test_laya_live.py -q
"""
from __future__ import annotations

import asyncio
import copy
import os
import urllib.request
from pathlib import Path

import pytest
import yaml

from api.server.services.judgement.engine import judge_gate
from api.server.services.judgement.evidence import DeepReviewRecord
from api.server.services.judgement.laya_client import LayaClient
from api.server.services.judgement.profiles import parse_profile
from api.server.world.runtime import SimulationRuntime
from verticals.banking.fraud_constants import FRAUD_SCENARIO_STANDARD, FRAUD_SCENARIO_VULNERABLE
from verticals.banking.fraud_constraints import OPTION_REFUSE_CAUTION, admit_claim_options
from verticals.banking.worlds.scenario import ZavaBankWorld

LAYA_URL = os.environ.get("LAYA_URL", "http://127.0.0.1:8765").rstrip("/")


def _laya_up() -> bool:
    try:
        with urllib.request.urlopen(f"{LAYA_URL.removesuffix('/v1/systemone')}/health", timeout=1) as response:
            return response.status == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _laya_up(), reason=f"Laya is not answering at {LAYA_URL}")

PERSONAE = Path(__file__).resolve().parents[3] / "verticals" / "banking" / "personae"

# Recorded LLM reasoning from the 22 Sep 2026 banking tapes.
REAL_STANDARD = (
    "The only admitted option reimburses the customer in full, freezes recoverable funds in the "
    "beneficiary account, and raises the receiving provider's liability. This prioritizes customer "
    "harm recovery, maximizes available recovery, and ensures the receiving provider is engaged for "
    "their share. No vulnerability flag is present, so no additional protections apply. Not acting "
    "would leave the customer uncompensated and allow proceeds to remain with the beneficiary. There "
    "is no uncertainty in ranking as only one admitted, feasible option is present."
)
REAL_VULNERABLE = (
    "The customer is flagged as vulnerable and suffered APP fraud. The admitted option reimburses the "
    "customer in full, freezes recoverable funds in the beneficiary account, and splits liability with "
    "the receiving provider. This prioritizes customer recovery and harm mitigation, ensures some "
    "recovery from the beneficiary, and holds the receiving provider accountable. No-action would leave "
    "a vulnerable customer uncompensated and undermine trust. There is no uncertainty in the admitted "
    "option; refusal is not possible for a vulnerable customer in this scenario."
)


class RecordingReviewer:
    def __init__(self) -> None:
        self.asked = 0

    async def review(self, request):
        self.asked += 1
        return DeepReviewRecord("hold", "Recorded for the golden set.", 1.0, model="fake")


@pytest.fixture(autouse=True)
def _enabled(monkeypatch):
    monkeypatch.setenv("JUDGEMENT_ENABLED", "1")
    monkeypatch.delenv("JUDGEMENT_MIN_LEAD", raising=False)


def _profile(role: str):
    text = (PERSONAE / role / "SKILL.md").read_text(encoding="utf-8")
    return parse_profile(role, yaml.safe_load(text.split("---", 2)[1])["judgement"])


def _judge(role: str, label: str, context: dict, *, next_role: str | None):
    reviewer = RecordingReviewer()
    ceiling = {"decision": "approve", "reason": "within delegation", "persona": role,
               "selected_option_id": context["selected_option"]["option_id"]}
    outcome = asyncio.run(judge_gate(
        persona_role=role, persona_label=label, instructions="", profile=_profile(role),
        context=context, ceiling=ceiling, workflow_id="LIVE", gate_phase="gate", next_role=next_role,
        client=LayaClient(LAYA_URL, timeout_s=10.0), reviewer=reviewer,
    ))
    return outcome, reviewer.asked


def _fraud(scenario: str, reasoning: str, *, refuse: bool = False) -> dict:
    world = ZavaBankWorld(seed=42, runtime=SimulationRuntime(42))
    world.install()
    world.activate_scenario(scenario)
    observation = copy.deepcopy(world.current_fraud_observation())
    if refuse:
        observation["claim"]["specific_warning_ignored"] = True
    admitted = [{"option_id": r.option.option_id, "value_gbp": r.option.value_gbp}
                for r in admit_claim_options(observation) if r.feasible]
    selected = next(o for o in admitted if (o["option_id"] == OPTION_REFUSE_CAUTION) == refuse)
    return {"workflow_type": "app-fraud-reimbursement", "observation": observation,
            "admitted_options": admitted, "selected_option": selected,
            "ranking": {"reasoning": reasoning}, "authority": {"allowed": True}}


def test_the_standard_claim_is_approved_by_fast_judgement() -> None:
    outcome, asked = _judge("fraud_decision_manager", "Fraud Decision Manager",
                            _fraud(FRAUD_SCENARIO_STANDARD, REAL_STANDARD), next_role="financial_crime_lead")
    record = outcome.judgement
    assert (record.decided_by, record.verdict, asked) == ("laya", "approve", 0), record.to_dict()
    assert record.concerns == []


def test_the_vulnerable_claim_is_approved_by_fast_judgement() -> None:
    outcome, asked = _judge("fraud_decision_manager", "Fraud Decision Manager",
                            _fraud(FRAUD_SCENARIO_VULNERABLE, REAL_VULNERABLE), next_role="financial_crime_lead")
    record = outcome.judgement
    assert (record.decided_by, record.verdict, asked) == ("laya", "approve", 0), record.to_dict()


def test_reasoning_that_contradicts_the_record_is_held_and_handed_up() -> None:
    outcome, _asked = _judge("fraud_decision_manager", "Fraud Decision Manager",
                             _fraud(FRAUD_SCENARIO_VULNERABLE, REAL_STANDARD), next_role="financial_crime_lead")
    record = outcome.judgement
    assert "the agent's reasoning says there is no vulnerability marker, but the record shows one" in record.concerns
    assert outcome.payload["decision"] != "approve" or record.decided_by == "llm", record.to_dict()
    assert outcome.hold is True, record.to_dict()


def test_a_refusal_is_never_waved_through() -> None:
    reasoning = ("The customer ignored a specific, tailored warning about this payee, which meets the consumer "
                 "standard of caution. Refusing reimbursement is ranked first; the account is still frozen.")
    outcome, asked = _judge("fraud_decision_manager", "Fraud Decision Manager",
                            _fraud(FRAUD_SCENARIO_STANDARD, reasoning, refuse=True), next_role="financial_crime_lead")
    record = outcome.judgement
    assert any("refusals always get a second pair of eyes" in c for c in record.concerns)
    assert not (record.decided_by == "laya" and record.verdict == "approve"), record.to_dict()


def _case(workflow_type: str, case: dict, option_id: str, reasoning: str) -> dict:
    return {"workflow_type": workflow_type, "observation": {"case": case},
            "selected_option": {"option_id": option_id, "value_gbp": 1_000.0},
            "ranking": {"reasoning": reasoning}, "authority": {"allowed": True}}


MULE = {"id": "SYN-MULE-CASE-1", "risk_band": "medium", "linked_claim_count": 5, "balance_gbp": 42_000.0}


def test_a_mule_account_kept_open_despite_many_claims_is_held() -> None:
    reasoning = ("Enhanced monitoring is proportionate for a medium-risk account. It keeps the account open "
                 "while the bank gathers more evidence. Doing nothing would leave the pattern unwatched.")
    outcome, asked = _judge("financial_crime_lead", "Financial Crime Lead",
                            _case("mule-account-investigation", MULE, "SYN-MULE-OPTION-MONITOR", reasoning),
                            next_role=None)
    record = outcome.judgement
    assert any("several fraud claims" in c for c in record.concerns), record.to_dict()
    assert not (record.decided_by == "laya" and record.verdict == "approve"), record.to_dict()


def test_a_sound_restraint_is_approved_by_fast_judgement() -> None:
    reasoning = ("Five fraud claims from different victims point to mule activity. Restraining the account "
                 "preserves the GBP 42,000 still in it for the victims' recovery. Doing nothing would let the "
                 "controller move the money out.")
    outcome, asked = _judge("financial_crime_lead", "Financial Crime Lead",
                            _case("mule-account-investigation", MULE, "SYN-MULE-OPTION-RESTRAIN", reasoning),
                            next_role=None)
    record = outcome.judgement
    assert (record.decided_by, record.verdict, asked) == ("laya", "approve", 0), record.to_dict()


MERCHANT = {"id": "SYN-MER-CASE-1", "risk_band": "low", "sector": "technology",
            "projected_monthly_volume_gbp": 120_000.0}


def test_a_sound_merchant_onboarding_is_approved_by_fast_judgement() -> None:
    reasoning = ("A low-risk technology merchant with a projected card volume of about GBP 120,000 a month "
                 "fits standard terms. A rolling reserve would add cost without a matching risk. Leaving the "
                 "application undecided would delay sound business.")
    outcome, asked = _judge("payments_operations_lead", "Payments Operations Lead",
                            _case("merchant-onboarding-risk", MERCHANT, "SYN-MER-OPTION-ONBOARD-STANDARD", reasoning),
                            next_role=None)
    record = outcome.judgement
    assert (record.decided_by, record.verdict, asked) == ("laya", "approve", 0), record.to_dict()


def test_reasoning_that_mentions_and_rejects_declining_goes_to_the_deep_review() -> None:
    # Measured: "does the text argue for declining?" is unsure (about 0.46) when
    # the text names declining only to reject it, so the case is handed off
    # rather than approved or held on a guess.
    reasoning = ("A low-risk technology merchant with a projected card volume of about GBP 120,000 a month "
                 "fits standard terms. A rolling reserve would add cost without a matching risk. Declining "
                 "would turn away sound business.")
    outcome, asked = _judge("payments_operations_lead", "Payments Operations Lead",
                            _case("merchant-onboarding-risk", MERCHANT, "SYN-MER-OPTION-ONBOARD-STANDARD", reasoning),
                            next_role=None)
    record = outcome.judgement
    assert record.unclear and asked == 1 and record.decided_by == "llm", record.to_dict()


def test_a_merchant_recommendation_that_argues_against_itself_is_held() -> None:
    reasoning = ("The sector carries heavy chargeback exposure and the application should be declined. "
                 "Nevertheless standard terms are offered.")
    outcome, asked = _judge("payments_operations_lead", "Payments Operations Lead",
                            _case("merchant-onboarding-risk", MERCHANT, "SYN-MER-OPTION-ONBOARD-STANDARD", reasoning),
                            next_role=None)
    record = outcome.judgement
    assert any("argues for declining" in c for c in record.concerns) or record.unclear, record.to_dict()
    assert not (record.decided_by == "laya" and record.verdict == "approve"), record.to_dict()


# --- Phase 2: the world notices and reacts --------------------------------------------------

def test_the_screener_flags_scams_and_leaves_ordinary_payments_alone() -> None:
    from verticals.banking.worlds import reference_data
    from verticals.banking.worlds.screening import PATTERN_QUESTION, Screening

    client = LayaClient(LAYA_URL, timeout_s=10.0)

    async def read(reference: str) -> Screening:
        answer = (await client.ask({"payment_reference": reference}, PATTERN_QUESTION)).answers["pattern"]
        return Screening(answer.top, answer.lead, "laya")

    async def run() -> tuple[list[Screening], list[Screening]]:
        ordinary = [await read(r) for r in reference_data.ORDINARY_REFERENCES]
        scams = [await read(r) for r in reference_data.SCAM_REFERENCES]
        return ordinary, scams

    ordinary, scams = asyncio.run(run())
    assert sum(s.flagged for s in ordinary) == 0
    assert sum(s.flagged for s in scams) >= 12


def test_merchant_descriptions_are_read_into_categories() -> None:
    from verticals.banking import merchant_categories as mc

    client = LayaClient(LAYA_URL, timeout_s=10.0)

    async def run() -> list[tuple[str, str]]:
        return [((await mc.categorise(text, client=client)).category, truth) for text, truth in mc.DESCRIPTIONS]

    readings = asyncio.run(run())
    # Measured: 13 of 20 right with a clear lead; the rest read as unclear
    # (medium band) and none is confidently put in a wrong category.
    assert sum(got == truth for got, truth in readings) >= 12
    assert [(got, truth) for got, truth in readings if got not in (truth, "unclear")] == []


def test_customers_are_more_upset_the_worse_the_decision() -> None:
    from verticals.banking.worlds.reactions import DECISION_WORDS, UPSET_QUESTION

    client = LayaClient(LAYA_URL, timeout_s=10.0)

    async def upset(kind: str) -> float:
        state = {"customer": "A personal customer who lost GBP 18,400 to a scam", "decision": DECISION_WORDS[kind]}
        return (await client.ask(state, UPSET_QUESTION)).answers["upset"].score

    async def run() -> list[float]:
        return [await upset(kind) for kind in ("full", "capped", "refused")]

    full, capped, refused = asyncio.run(run())
    assert full < capped < refused
