"""Banking persona judgement: facts adapters, profiles and the escalation path."""
from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from api.server.services.judgement.profiles import DEFAULT_CHARACTER, GateFacts, parse_profile
from api.server.world.runtime import SimulationRuntime
from verticals.banking.fraud_constants import (
    FRAUD_SCENARIO_OVER_DELEGATION,
    FRAUD_SCENARIO_STANDARD,
    FRAUD_SCENARIO_VULNERABLE,
)
from verticals.banking.fraud_constraints import (
    OPTION_REFUSE_CAUTION,
    OPTION_REIMBURSE_CAPPED,
    OPTION_REIMBURSE_FULL,
    admit_claim_options,
)
from verticals.banking.judgement_facts import fraud_gate, merchant_gate, mule_gate
from verticals.banking.worlds.scenario import ZavaBankWorld

PERSONAE = Path(__file__).resolve().parents[3] / "verticals" / "banking" / "personae"
REASONING = "The only admitted option reimburses the customer in full. Not acting would leave the customer uncompensated."


def _observation(scenario: str = FRAUD_SCENARIO_STANDARD) -> dict:
    world = ZavaBankWorld(seed=42, runtime=SimulationRuntime(42))
    world.install()
    world.activate_scenario(scenario)
    return world.current_fraud_observation()


def _fraud_context(observation: dict, option_id: str | None = None, *, allowed: bool = True, **extra) -> dict:
    admitted = [
        {"option_id": r.option.option_id, "value_gbp": r.option.value_gbp, "impact": r.option.impact}
        for r in admit_claim_options(observation) if r.feasible
    ]
    selected = next(o for o in admitted if option_id in (None, o["option_id"]))
    return {
        "workflow_type": "app-fraud-reimbursement",
        "observation": observation,
        "admitted_options": admitted,
        "selected_option": selected,
        "selected_option_id": selected["option_id"],
        "ranking": {"reasoning": REASONING},
        "authority": {"allowed": allowed},
        **extra,
    }


def test_fraud_facts_for_the_standard_claim() -> None:
    facts = fraud_gate(_fraud_context(_observation()))
    assert isinstance(facts, GateFacts)
    assert facts.texts == {"agent_reasoning": REASONING}
    assert facts.facts == {
        "customer_vulnerable": False,
        "recommends_refusal": False,
        "refusal_permitted": False,
        "specific_warning_ignored": False,
    }
    assert facts.recommendation == "Reimburse the customer in full (GBP 18,400)"
    assert "scam of GBP 18,400" in facts.case
    assert "No vulnerability marker is recorded" in facts.case
    assert "within your delegated authority" in facts.case
    assert "Zava Bank's own business clients" in facts.case
    assert facts.prior_concerns == ()


def test_fraud_facts_for_a_vulnerable_claim_and_an_over_authority_claim() -> None:
    vulnerable = fraud_gate(_fraud_context(_observation(FRAUD_SCENARIO_VULNERABLE)))
    assert vulnerable.facts["customer_vulnerable"] is True
    assert "carries a vulnerability marker" in vulnerable.case
    capped = fraud_gate(_fraud_context(_observation(FRAUD_SCENARIO_OVER_DELEGATION), allowed=False))
    assert capped.recommendation == "Reimburse the customer up to the cap (GBP 85,000)"
    assert "above your delegated authority" in capped.case


def test_fraud_facts_when_refusal_is_permitted_and_recommended() -> None:
    observation = copy.deepcopy(_observation())
    observation["claim"]["specific_warning_ignored"] = True
    facts = fraud_gate(_fraud_context(observation, OPTION_REFUSE_CAUTION))
    assert facts.facts["recommends_refusal"] is True and facts.facts["refusal_permitted"] is True
    assert facts.facts["specific_warning_ignored"] is True
    assert facts.recommendation.startswith("Refuse reimbursement under the consumer standard of caution")
    assert "ignored a specific, tailored warning" in facts.case


def test_an_earlier_hold_becomes_prior_concerns() -> None:
    context = _fraud_context(_observation(), held_by=[{
        "persona": "fraud_decision_manager",
        "concerns": ["the agent argues for refusal but recommends paying the customer"],
    }])
    assert fraud_gate(context).prior_concerns == (
        "Fraud decision manager: the agent argues for refusal but recommends paying the customer",
    )


def _case_context(workflow_type: str, case: dict, option_id: str, value: float) -> dict:
    return {
        "workflow_type": workflow_type,
        "observation": {"case": case},
        "selected_option": {"option_id": option_id, "value_gbp": value},
        "ranking": {"reasoning": "Restraint preserves the victims' funds."},
        "authority": {"allowed": True},
    }


def test_mule_facts() -> None:
    case = {"id": "SYN-MULE-CASE-0001", "risk_band": "medium", "linked_claim_count": 5, "balance_gbp": 42_000.0}
    monitor = mule_gate(_case_context("mule-account-investigation", case, "SYN-MULE-OPTION-MONITOR", 5_000.0))
    assert monitor.facts == {"recommends_monitoring": True, "recommends_closure": False,
                             "monitoring_despite_several_claims": True}
    assert monitor.recommendation == "Keep the account open under enhanced monitoring"
    assert "risk band medium" in monitor.case and "5 fraud claims" in monitor.case and "GBP 42,000" in monitor.case
    restrain = mule_gate(_case_context("mule-account-investigation", {**case, "linked_claim_count": 1},
                                       "SYN-MULE-OPTION-RESTRAIN", 45_000.0))
    assert restrain.facts["monitoring_despite_several_claims"] is False
    assert "1 fraud claim," in restrain.case


def test_merchant_facts() -> None:
    case = {"id": "SYN-MER-CASE-0001", "risk_band": "low", "sector": "technology",
            "projected_monthly_volume_gbp": 642_972.0}
    facts = merchant_gate(_case_context("merchant-onboarding-risk", case, "SYN-MER-OPTION-ONBOARD-STANDARD", 25_000.0))
    assert facts.facts == {"recommends_standard_terms": True, "recommends_decline": False,
                           "standard_terms_for_large_volume": True}
    assert facts.recommendation == "Onboard the merchant on standard terms"
    assert "sector technology" in facts.case and "GBP 642,972 a month" in facts.case


def _frontmatter(role: str) -> dict:
    text = (PERSONAE / role / "SKILL.md").read_text(encoding="utf-8")
    return yaml.safe_load(text.split("---", 2)[1])


@pytest.mark.parametrize(
    ("role", "workflow_types"),
    [
        ("fraud_decision_manager", {"app-fraud-reimbursement"}),
        ("financial_crime_lead", {"app-fraud-reimbursement", "mule-account-investigation"}),
        ("payments_operations_lead", {"merchant-onboarding-risk"}),
    ],
)
def test_banking_personas_carry_valid_judgement_profiles(role: str, workflow_types: set[str]) -> None:
    frontmatter = _frontmatter(role)
    profile = parse_profile(role, frontmatter["judgement"])
    assert set(profile.gates) == workflow_types
    assert profile.character and profile.character != DEFAULT_CHARACTER
    assert set(frontmatter["personality"]) <= {"risk_appetite", "thoroughness", "escalation_style"}
    for gate in profile.gates.values():
        assert gate.reads and gate.decide.approve and gate.decide.hold


def test_refusals_always_raise_a_concern_for_the_fraud_decision_manager() -> None:
    gate = parse_profile("fraud_decision_manager", _frontmatter("fraud_decision_manager")["judgement"]).gate(
        "app-fraud-reimbursement")
    fact_only = [c for c in gate.checks if c.read is None]
    assert any(c.fact == "recommends_refusal" and c.equals is True for c in fact_only)


def test_the_other_personas_are_not_judged() -> None:
    for role in ("vulnerable_customer_specialist", "credit_risk_officer", "senior_credit_officer"):
        assert "judgement" not in _frontmatter(role)


def test_option_words_cover_every_fraud_option() -> None:
    for option_id in (OPTION_REIMBURSE_FULL, OPTION_REIMBURSE_CAPPED, OPTION_REFUSE_CAUTION):
        observation = copy.deepcopy(_observation())
        context = _fraud_context(observation)
        context["selected_option"] = {"option_id": option_id, "value_gbp": 1_000.0}
        assert "(GBP 1,000)" in fraud_gate(context).recommendation
