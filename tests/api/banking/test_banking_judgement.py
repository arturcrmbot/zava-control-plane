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


# --- Escalation: the org hands work up ------------------------------------------------

from datetime import datetime, timezone  # noqa: E402

from api.shared.vertical_loader import active_runtime  # noqa: E402
from verticals.banking import fraud_durable  # noqa: E402
from verticals.banking.fraud_constants import FRAUD_HITL_EVENT  # noqa: E402


@pytest.fixture
def banking_governance(monkeypatch):
    import importlib

    kernel_module = importlib.import_module("api.server.services.governance.kernel")

    monkeypatch.setenv("ZAVA_VERTICAL", "banking")
    monkeypatch.delenv("ZAVA_WORLD", raising=False)
    active_runtime.cache_clear()
    kernel_module._reset_for_tests()
    yield
    kernel_module._reset_for_tests()
    active_runtime.cache_clear()


def _governance(value: float, *, role: str | None = None) -> dict:
    payload = {"selected_option": {"option_id": OPTION_REIMBURSE_CAPPED, "value_gbp": value}}
    if role:
        payload["role"] = role
    return fraud_durable.fraud_governance_activity(payload)


def test_with_judgement_off_governance_names_nobody_new(banking_governance, monkeypatch) -> None:
    monkeypatch.setenv("JUDGEMENT_ENABLED", "0")
    result = _governance(85_000.0)
    assert result["allowed"] is False
    assert "escalation" not in result and "escalate_to" not in result


def test_governance_names_the_financial_crime_lead_above_the_managers_delegation(
    banking_governance, monkeypatch
) -> None:
    monkeypatch.setenv("JUDGEMENT_ENABLED", "1")
    capped = _governance(85_000.0)
    assert capped["allowed"] is False
    assert capped["escalation"]["role"] == "financial_crime_lead"
    assert capped["escalation"]["allowed"] is True
    assert capped["escalate_to"] == "financial_crime_lead"
    within = _governance(18_400.0)
    assert within["allowed"] is True and "escalation" not in within
    assert within["escalate_to"] == "financial_crime_lead"
    lead = _governance(85_000.0, role="financial_crime_lead")
    assert lead["allowed"] is True and "escalate_to" not in lead
    beyond = _governance(300_000.0)
    assert beyond["allowed"] is False and "escalation" not in beyond


class _Task:
    def __init__(self, name: str, result=None) -> None:
        self.name, self.result, self.cancelled = name, result, False

    def cancel(self) -> None:
        self.cancelled = True


class _GateContext:
    """Enough of DurableOrchestrationContext to run the fraud orchestration through its gate."""

    instance_id = "inst-escalation"
    current_utc_datetime = datetime(2026, 9, 25, tzinfo=timezone.utc)

    def __init__(self, approval: dict, results: dict) -> None:
        self.approval = approval
        self.results = {name: list(values) for name, values in results.items()}
        self.activities: list[tuple[str, dict]] = []
        self.waited_for: str | None = None

    def get_input(self) -> dict:
        return {"workflow_id": "BAPP-escalation"}

    def call_activity(self, name: str, payload: dict):
        self.activities.append((name, payload))
        queue = self.results.get(name)
        return ("result", queue.pop(0) if queue else None)

    def call_activity_with_retry(self, name: str, retry, payload: dict):
        return self.call_activity(name, payload)

    def wait_for_external_event(self, name: str) -> _Task:
        self.waited_for = name
        return _Task("decision", self.approval)

    def create_timer(self, when) -> _Task:
        return _Task("timer")

    def task_any(self, tasks: list):
        return ("any", tasks)


def _drive(context: _GateContext) -> dict:
    orchestration = fraud_durable.fraud_orchestration(context)
    sent = None
    try:
        while True:
            kind, value = orchestration.send(sent)
            sent = value if kind == "result" else value[0]
    except StopIteration as stop:
        return stop.value


_VERSIONS = {"SYN-CLAIM-0033": 2}


def _approval(persona: str, **extra) -> dict:
    return {
        "decision": "approve", "persona": persona, "decision_id": "SYN-APP-DECISION-001",
        "selected_option_id": OPTION_REIMBURSE_CAPPED, "evidence_versions": _VERSIONS, **extra,
    }


def _results(governance: list[dict]) -> dict:
    return {
        "fraud_evidence_activity_trigger": [{
            "story_id": "SYN-STORY-APP-003", "claim_id": "SYN-CLAIM-0033",
            "evidence_versions": _VERSIONS, "observation": {"claim": {"id": "SYN-CLAIM-0033"}},
        }],
        "fraud_trace_activity_trigger": [{
            "admitted_options": [{"option_id": OPTION_REIMBURSE_CAPPED, "value_gbp": 85_000.0}],
            "rejected_options": [], "beneficiary_path": {},
        }],
        "fraud_agent_activity_trigger": [{"ranked_option_ids": [OPTION_REIMBURSE_CAPPED], "reasoning": "Capped."}],
        "fraud_governance_activity_trigger": governance,
        "fraud_command_activity_trigger": [{"status": "decision_ready", "command": {"type": "x"}}],
    }


def _suspended(context: _GateContext) -> dict:
    return next(p["payload"] for name, p in context.activities
                if name == "checkpoint_activity_trigger" and p["kind"] == "suspended")


def _command_payload(context: _GateContext) -> dict | None:
    return next((p for name, p in context.activities if name == "fraud_command_activity_trigger"), None)


ESCALATED = {
    "allowed": False, "reason": "matched rule requires 'financial_crime_lead'",
    "governing_rule_id": "AUTH-financial_crime_lead-banking.commit_reimbursement_decision",
    "escalate_to": "financial_crime_lead",
    "escalation": {"role": "financial_crime_lead", "allowed": True, "reason": "approver",
                   "governing_rule_id": "AUTH-financial_crime_lead-banking.commit_reimbursement_decision"},
}


def test_an_over_authority_claim_is_decided_by_the_persona_governance_names() -> None:
    context = _GateContext(_approval("financial_crime_lead"), _results([ESCALATED]))
    output = _drive(context)
    suspended = _suspended(context)
    assert suspended["persona"] == "financial_crime_lead"
    assert suspended["external_event"] == FRAUD_HITL_EVENT == context.waited_for
    hitl = suspended["hitl_context"]
    assert hitl["persona"] == "financial_crime_lead" and hitl["escalated_from"] == "fraud_decision_manager"
    assert hitl["authority"]["allowed"] is True and "escalate_to" not in hitl
    assert output["status"] == "decision_ready"
    assert _command_payload(context)["approval"]["persona"] == "financial_crime_lead"


def test_an_over_authority_claim_still_refuses_the_manager() -> None:
    context = _GateContext(_approval("fraud_decision_manager"), _results([ESCALATED]))
    output = _drive(context)
    assert output["status"] == "denied" and "approval persona must be financial_crime_lead" in output["reason"]
    assert _command_payload(context) is None


WITHIN = {"allowed": True, "reason": "approver", "governing_rule_id": "AUTH-fraud_decision_manager-x",
          "escalate_to": "financial_crime_lead"}


def test_a_hold_handed_up_is_rechecked_by_governance_before_the_command() -> None:
    context = _GateContext(_approval("financial_crime_lead"),
                           _results([WITHIN, {"allowed": True, "reason": "approver"}]))
    output = _drive(context)
    governance_calls = [p for name, p in context.activities if name == "fraud_governance_activity_trigger"]
    assert [call.get("role") for call in governance_calls] == [None, "financial_crime_lead"]
    assert _suspended(context)["hitl_context"]["escalate_to"] == "financial_crime_lead"
    assert output["status"] == "decision_ready"


def test_a_hold_handed_up_to_someone_without_authority_is_denied() -> None:
    context = _GateContext(_approval("financial_crime_lead"),
                           _results([WITHIN, {"allowed": False, "reason": "value exceeds spend limit"}]))
    output = _drive(context)
    assert output["status"] == "denied" and "not authorised" in output["reason"]
    assert _command_payload(context) is None


def test_an_approval_from_outside_the_chain_is_denied() -> None:
    context = _GateContext(_approval("payments_operations_lead"), _results([WITHIN]))
    output = _drive(context)
    assert output["status"] == "denied"
    assert "financial_crime_lead or fraud_decision_manager" in output["reason"]


def test_a_judged_decline_carries_the_personas_reason() -> None:
    decline = _approval("financial_crime_lead", decision="reject", decided_by="llm",
                        reason="Deep review: the reasoning contradicts the record.")
    output = _drive(_GateContext(decline, _results([ESCALATED])))
    assert output["status"] == "denied"
    assert output["reasoning"] == (
        "financial crime lead declined to approve: Deep review: the reasoning contradicts the record."
    )


def test_the_command_records_the_persona_who_approved() -> None:
    world = ZavaBankWorld(seed=42, runtime=SimulationRuntime(42))
    world.install()
    world.activate_scenario(FRAUD_SCENARIO_OVER_DELEGATION)
    observation = world.current_fraud_observation()
    result = fraud_durable.fraud_command_activity(
        {
            "workflow_id": "BAPP-escalation",
            "approval": _approval("financial_crime_lead", evidence_versions=observation["evidence_versions"]),
            "hitl_context": {"claim_id": observation["claim"]["id"],
                             "evidence_versions": observation["evidence_versions"],
                             "observation": observation},
        },
        world=world,
    )
    assert result["status"] == "decision_ready"
    assert result["command"]["payload"]["persona"] == "financial_crime_lead"


# --- The drawer shows how each decision was reached -----------------------------------

from types import SimpleNamespace  # noqa: E402

from verticals.banking.detail import workflow_detail  # noqa: E402


def test_governed_decisions_say_who_decided_and_why() -> None:
    judged = {
        "phase": "Decide Reimbursement", "persona_role": "fraud_decision_manager", "verdict": "hold",
        "reason": "Held for a closer look: x.", "decided_by": "laya",
        "judgement": {"concerns": ["x"], "summary": "Held for a closer look: x.", "judge": {"lead": 0.6}},
    }
    plain = {"phase": "Approve Account Disposition", "persona_role": "financial_crime_lead",
             "verdict": "approve", "reason": "within delegation"}
    detail = workflow_detail(SimpleNamespace(payload={"case": {"id": "SYN-MULE-CASE-1"}, "decisions": [judged, plain]},
                                             metadata={}))
    first, second = detail["governedDecisions"]
    assert first == {"phase": "Decide Reimbursement", "persona": "fraud_decision_manager", "verdict": "hold",
                     "reason": "Held for a closer look: x.", "decidedBy": "laya", "concerns": ["x"],
                     "judgementSummary": "Held for a closer look: x.", "lead": 0.6}
    assert second == {"phase": "Approve Account Disposition", "persona": "financial_crime_lead",
                      "verdict": "approve", "reason": "within delegation"}
