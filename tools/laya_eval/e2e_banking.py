"""End-to-end, in process: the real fraud orchestration with judgement on.

Runs ``fraud_orchestration`` step by step with the real activities (world,
admission, governance kernel, reimbursement command) and the real persona
responder deciding each gate with live Laya. Only the ranking agent is
replaced (by authored reasoning), and the deep review uses the fake LLM
runtime unless ``DEEP_REVIEW=real``, which spends one Copilot request per
deep review.

    LAYA_PORT=8766 ~/.copilot/skills/laya/scripts/start.sh &
    LAYA_URL=http://127.0.0.1:8766 ZAVA_VERTICAL=banking \\
        .venv/bin/python tools/laya_eval/e2e_banking.py
"""
from __future__ import annotations

import asyncio
import copy
import importlib
import json
import os
import pathlib
import sys
import time

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

os.environ.setdefault("ZAVA_VERTICAL", "banking")
os.environ.setdefault("PERSONA_AUTO_CLOSE", "*")
os.environ.setdefault("MEMORY_BACKEND", "fallback")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ["JUDGEMENT_ENABLED"] = os.environ.get("JUDGEMENT_ENABLED", "1")
if os.environ.get("DEEP_REVIEW", "fake") != "real":
    os.environ["LLM_RUNTIME"] = "fake"

from api.functions.graphs.executors.agents.runtime_fake import FakeRuntime  # noqa: E402
from api.server.services import persona_responder  # noqa: E402
from api.server.world.runtime import SimulationRuntime  # noqa: E402
from api.shared.events import FleetEvent  # noqa: E402
from api.shared.types import Workflow  # noqa: E402
from verticals.banking import fraud_durable  # noqa: E402
from verticals.banking.fraud_constants import (  # noqa: E402
    FRAUD_SCENARIO_OVER_DELEGATION,
    FRAUD_SCENARIO_STANDARD,
    FRAUD_SCENARIO_VULNERABLE,
)
from verticals.banking.fraud_constraints import OPTION_REFUSE_CAUTION  # noqa: E402
from verticals.banking.worlds.scenario import ZavaBankWorld  # noqa: E402

# FAKE_REVIEW=hold makes the fake deep review hold, which exercises the send-back loop.
FakeRuntime.canned_text = json.dumps(
    {"decision": "hold", "rationale": "The reasoning does not agree with the record. The agent should correct it."}
    if os.environ.get("FAKE_REVIEW") == "hold" else
    {"decision": "approve",
     "rationale": "Set against the record, the recommendation stands: the admitted option is the only one the rules permit."}
)

REASONING = {
    "standard": (
        "The only admitted option reimburses the customer in full, freezes recoverable funds in the beneficiary "
        "account, and raises the receiving provider's liability. No vulnerability flag is present, so no additional "
        "protections apply. Not acting would leave the customer uncompensated and allow proceeds to remain with the "
        "beneficiary."
    ),
    "vulnerable": (
        "The customer is flagged as vulnerable and suffered APP fraud. The admitted option reimburses the customer in "
        "full, freezes recoverable funds in the beneficiary account, and splits liability with the receiving provider. "
        "No-action would leave a vulnerable customer uncompensated; refusal is not possible for a vulnerable customer."
    ),
    "capped": (
        "The claim exceeds the reimbursement cap, so the admitted option reimburses the customer up to the cap, freezes "
        "what remains in the receiving account and raises the receiving provider's share. No vulnerability flag is "
        "present. Doing nothing would leave the customer with the whole loss."
    ),
    "refusal": (
        "The customer ignored a specific, tailored warning about this payee, which meets the consumer standard of "
        "caution. Refusing reimbursement is ranked first; the receiving account is still frozen."
    ),
}


class _Task:
    def __init__(self, name: str, result=None) -> None:
        self.name, self.result = name, result

    def cancel(self) -> None:
        pass


class LiveContext:
    """Runs each yielded activity for real, and decides the gate with the responder."""

    current_utc_datetime = __import__("datetime").datetime(2026, 9, 25, tzinfo=__import__("datetime").timezone.utc)

    def __init__(self, workflow_id: str, world: ZavaBankWorld, ranking_for) -> None:
        self.instance_id = f"inst-{workflow_id}"
        self.workflow_id = workflow_id
        self.world = world
        self.ranking_for = ranking_for
        self.approval: dict | None = None
        self.suspended: dict | None = None

    def get_input(self) -> dict:
        return {"workflow_id": self.workflow_id, "type": "app-fraud-reimbursement"}

    def call_activity(self, name: str, payload: dict):
        return ("activity", name, payload)

    def call_activity_with_retry(self, name: str, retry, payload: dict):
        return ("activity", name, payload)

    def wait_for_external_event(self, name: str) -> _Task:
        return _Task("decision", self.approval)

    def create_timer(self, when) -> _Task:
        return _Task("timer")

    def task_any(self, tasks: list):
        return ("any", tasks)

    def run(self, name: str, payload: dict):
        if name == "checkpoint_activity_trigger":
            if payload["kind"] == "suspended":
                self.suspended = payload["payload"]
                self._decide_gate(payload["payload"])
            return None
        if name == "fraud_evidence_activity_trigger":
            return fraud_durable.fraud_evidence_activity(payload, world=self.world)
        if name == "fraud_trace_activity_trigger":
            return fraud_durable.fraud_trace_activity(payload)
        if name == "fraud_agent_activity_trigger":
            return self.ranking_for(payload)
        if name == "fraud_governance_activity_trigger":
            return fraud_durable.fraud_governance_activity(payload)
        if name == "fraud_command_activity_trigger":
            return fraud_durable.fraud_command_activity(payload, world=self.world)
        raise KeyError(name)

    def _decide_gate(self, suspended: dict) -> None:
        async def raise_event(instance_id, event_name, payload):
            self.approval = payload
            return True

        persona_responder.raise_orchestration_event = raise_event
        asyncio.run(persona_responder._handle_hitl(FleetEvent(
            type="workflow.hitl.requested", workflow_id=self.workflow_id,
            persona=suspended["persona"], phase=suspended["phase"],
            external_event=suspended["external_event"], instance_id=self.instance_id,
            context=suspended["context"],
        )))


def drive(context: LiveContext) -> dict:
    orchestration = fraud_durable.fraud_orchestration(context)
    sent = None
    try:
        while True:
            step = orchestration.send(sent)
            if step[0] == "activity":
                sent = context.run(step[1], step[2])
            else:
                decision, timer = step[1]
                sent = decision if context.approval is not None else timer
    except StopIteration as stop:
        return stop.value


def ranking(kind: str, *, prefer_refusal: bool = False, corrected: str | None = None):
    """The stand-in agent. Sent back with a reviewer's reasons, it re-assesses as ``corrected``."""
    def build(payload: dict) -> dict:
        evidence = payload["evidence"]
        ids = [o["option_id"] for o in payload["admitted_options"]]
        sent_back = bool(payload.get("reviewer_feedback"))
        if prefer_refusal and OPTION_REFUSE_CAUTION in ids and not sent_back:
            ids = [OPTION_REFUSE_CAUTION] + [i for i in ids if i != OPTION_REFUSE_CAUTION]
        text = REASONING[corrected if sent_back and corrected else kind]
        return {"phase": "Assess Claim Evidence", "ranked_option_ids": ids, "reasoning": text,
                "evidence_versions": evidence["evidence_versions"], "actor_ids": evidence["actor_ids"],
                "event_ids": evidence["event_ids"]}
    return build


def world_with(scenario: str | None = None) -> ZavaBankWorld:
    world = ZavaBankWorld(seed=42, runtime=SimulationRuntime(42))
    world.install()
    if scenario:
        world.activate_scenario(scenario)
    return world


def refusal_world() -> ZavaBankWorld:
    """Raise generated claims until one admits a refusal (a warned, non-vulnerable customer)."""
    world = world_with()
    for _ in range(40):
        claim = world.fraud_claims[world.raise_claim("any").payload["claim_id"]]
        if claim.specific_warning_ignored and not claim.vulnerability_flag and claim.amount_gbp <= 50_000:
            return world
    raise RuntimeError("no refusal-admitted claim in 40 draws")


def high_value_world() -> ZavaBankWorld:
    world = world_with()
    world.raise_claim("high-value")
    return world


CASES = [
    ("Standard GBP 18,400", lambda: world_with(FRAUD_SCENARIO_STANDARD), ranking("standard")),
    ("Vulnerable GBP 6,750", lambda: world_with(FRAUD_SCENARIO_VULNERABLE), ranking("vulnerable")),
    ("Vulnerable, reasoning says no marker", lambda: world_with(FRAUD_SCENARIO_VULNERABLE), ranking("standard", corrected="vulnerable")),
    ("Over delegation GBP 92,000", lambda: world_with(FRAUD_SCENARIO_OVER_DELEGATION), ranking("capped")),
    ("Generated high-value claim", high_value_world, ranking("capped")),
    ("Generated claim, agent ranks refusal first", refusal_world, ranking("refusal", prefer_refusal=True, corrected="standard")),
]


def main() -> None:
    app_state = importlib.import_module("api.server.state").app_state
    persona_responder.PERSONA_DEFINITIONS = persona_responder._load_personae()
    judgements: list = []
    app_state.bus.on_any(lambda e: judgements.append(e) if e.type == "persona.judgement" else None)
    rows = []
    for index, (name, make_world, rank) in enumerate(CASES, start=1):
        workflow_id = f"BAPP-E2E-{index}"
        now = time.time()
        app_state.store.upsert_workflow(Workflow(
            id=workflow_id, type="app-fraud-reimbursement", status="awaiting_hitl",
            current_phase="Decide Reimbursement", created_at=now, sla_due_at=now + 3600,
            jurisdiction="SYN-UK-Zava", agency="Zava Bank", payload={}))
        persona_responder._RECENTLY_JUDGED.clear()
        context = LiveContext(workflow_id, make_world(), rank)
        started = time.perf_counter()
        output = drive(context)
        elapsed = (time.perf_counter() - started) * 1000
        decisions = app_state.store.get_workflow(workflow_id).payload.get("decisions") or []
        trail = " -> ".join(
            f"{d['persona_role']}:{d['verdict']}({d.get('decided_by', 'rules')})"
            + (f"[round {d['round']}]" if d.get("round") else "")
            for d in decisions
        ) or "(no gate)"
        command = (output.get("command") or {}).get("payload") or {}
        rows.append({
            "case": name,
            "gate_persona": (context.suspended or {}).get("persona"),
            "trail": trail,
            "outcome": output.get("status"),
            "option": command.get("option_id"),
            "value": command.get("value_gbp"),
            "approved_by": command.get("persona"),
            "reason": (output.get("reason") or "")[:120],
            "ms": round(elapsed),
            "why": [d.get("reason") for d in decisions],
        })
    for row in rows:
        print(json.dumps(row))


if __name__ == "__main__" and not (len(sys.argv) > 1 and sys.argv[1] in ("mule", "calls")):
    main()


# --- Phase 2: the bank notices a mule pattern, decides, and the world changes --------------

MULE_REASONING = (
    "Several customers' payments into this account match scam patterns. Restraining the account preserves "
    "the money still in it for the victims' recovery. Doing nothing would let the controller move the money out."
)


async def step_until_mule_case(world: ZavaBankWorld, limit: int = 400_000):
    """Step the world, letting screening tasks read with Laya, until the mule sensor trips."""
    from verticals.banking.support_constants import MULE_SENSOR_ID

    seen = len(world.runtime.journal)
    for step in range(limit):
        world.runtime.step()
        if step % 25 == 0:
            await asyncio.sleep(0.005)
        journal = world.runtime.journal
        for event in journal[seen:]:
            if event.type == "sensor.tripped" and event.payload.get("sensor_id") == MULE_SENSOR_ID:
                return event
        seen = len(journal)
    raise RuntimeError("the bank noticed no mule pattern")


class LiveCaseContext(LiveContext):
    def __init__(self, workflow_id: str, world: ZavaBankWorld, input_: dict) -> None:
        super().__init__(workflow_id, world, ranking_for=None)
        self._input = input_

    def get_input(self) -> dict:
        return self._input

    def run(self, name: str, payload: dict):
        from verticals.banking import supporting_durable as sd

        if name == "checkpoint_activity_trigger":
            if payload["kind"] == "suspended":
                self.suspended = payload["payload"]
                self._decide_gate(payload["payload"])
            return None
        if name == "case_evidence_activity_trigger":
            return sd.case_evidence_activity(payload)
        if name == "case_agent_activity_trigger":
            evidence = payload["evidence"]
            ids = [o["option_id"] for o in evidence["admitted_options"]]
            ids.sort(key=lambda option: 0 if option.endswith("RESTRAIN") else 1)
            return {"phase": "Analyse Mule Network", "ranked_option_ids": ids, "reasoning": MULE_REASONING,
                    "evidence_versions": evidence["evidence_versions"], "actor_ids": evidence["actor_ids"],
                    "event_ids": evidence["event_ids"]}
        if name == "case_governance_activity_trigger":
            return sd.case_governance_activity(payload)
        if name == "case_command_activity_trigger":
            return sd.case_command_activity(payload)
        raise KeyError(name)


def drive_case(context: LiveCaseContext) -> dict:
    from verticals.banking.supporting_durable import MULE_PROFILE, case_orchestration

    orchestration = case_orchestration(MULE_PROFILE, context)
    sent = None
    try:
        while True:
            step = orchestration.send(sent)
            if step[0] == "activity":
                sent = context.run(step[1], step[2])
            else:
                decision, timer = step[1]
                sent = decision if context.approval is not None else timer
    except StopIteration as stop:
        return stop.value


def run_mule() -> dict:
    from api.server.world.model import SimulationCommand

    os.environ["BANKING_WORLD_SCREENING"] = "1"
    app_state = importlib.import_module("api.server.state").app_state
    persona_responder.PERSONA_DEFINITIONS = persona_responder._load_personae()
    world = world_with()
    started = time.perf_counter()
    trip = asyncio.run(step_until_mule_case(world))
    noticed_s = time.perf_counter() - started
    state = world.render_state()["screening"]
    bene = trip.payload["beneficiary_id"]
    observation = world.build_observation(trip.to_dict())
    workflow_id = "BMUL-E2E-1"
    now = time.time()
    app_state.store.upsert_workflow(Workflow(
        id=workflow_id, type="mule-account-investigation", status="awaiting_hitl",
        current_phase="Approve Account Disposition", created_at=now, sla_due_at=now + 3600,
        jurisdiction="SYN-UK-Zava", agency="Zava Bank", payload={"observation": observation}))
    context = LiveCaseContext(workflow_id, world, {
        "workflow_id": workflow_id, "type": "mule-account-investigation", "trace_id": trip.trace_id,
        "objective_id": "obj-e2e", "observation": observation})
    output = drive_case(context)
    applied = world.apply_command(SimulationCommand(**output["command"])) if output.get("command") else None
    decisions = app_state.store.get_workflow(workflow_id).payload.get("decisions") or []
    return {
        "noticed_after_s": round(noticed_s, 2),
        "screened": state["payments_screened"], "flagged": state["payments_flagged"],
        "flags": [(f["reference"], f["pattern"], f["screened_by"]) for f in observation["case"]["flagged_payments"]],
        "account": bene, "band": observation["case"]["risk_band"], "customers": observation["case"]["linked_claim_count"],
        "decision": [(d["persona_role"], d["verdict"], d.get("decided_by"), d.get("reason")) for d in decisions],
        "outcome": output.get("status"), "applied": applied.type if applied else None,
        "account_status": world.beneficiaries[bene].status,
    }


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "mule":
    print(json.dumps(run_mule(), indent=1))


# --- Phase 3: a customer calls, the bank decides, and the presenter asks "what if" -----------

CALL = ("Someone rang saying they were from Zava Bank's fraud team. They said my account was compromised and "
        "I had to move my savings to a safe account. Since my husband died last year I look after the money alone.")


def run_calls() -> dict:
    from api.server.routes import judgement as judgement_routes
    from api.server.routes import world as world_routes
    from api.server.services.event_bus import EventBus
    from api.server.world.service import ActorWorldService

    app_state = importlib.import_module("api.server.state").app_state
    persona_responder.PERSONA_DEFINITIONS = persona_responder._load_personae()
    service = ActorWorldService.for_world("banking", seed=42, bus=EventBus())
    app_state.world_service = service
    world = service.scenario
    payment_id = next(p.id for p in world.payments.values()
                      if p.status == "settled" and world.customers[world.accounts[p.from_account_id].customer_id].status == "active"
                      and 5_000 < p.amount_gbp < 9_000)
    started = time.perf_counter()
    call = asyncio.run(world_routes.customer_calls(world_routes.CustomerCall(payment_id=payment_id, statement=CALL)))
    read_ms = (time.perf_counter() - started) * 1000
    claim_id = call["claim_id"]
    observation = world.observation_for_claim(claim_id)

    workflow_id = "BAPP-CALL-1"
    now = time.time()
    app_state.store.upsert_workflow(Workflow(
        id=workflow_id, type="app-fraud-reimbursement", status="awaiting_hitl",
        current_phase="Decide Reimbursement", created_at=now, sla_due_at=now + 3600,
        jurisdiction="SYN-UK-Zava", agency="Zava Bank", payload={}))
    context = LiveContext(workflow_id, world, ranking("standard"))
    output = drive(context)
    record = app_state.store.get_workflow(workflow_id)
    record.payload["hitl_context"] = context.suspended["hitl_context"]
    app_state.store.upsert_workflow(record)
    decisions = record.payload.get("decisions") or []
    what_if = asyncio.run(judgement_routes.what_if(judgement_routes.WhatIf(workflow_id=workflow_id, vulnerable=True)))
    return {
        "reading": call["reading"], "read_ms": round(read_ms),
        "claim": claim_id, "amount": observation["claim"]["amount_gbp"],
        "record_vulnerable": observation["claim"]["vulnerability_flag"],
        "statement_in_evidence": "customer_statement" in context.suspended["hitl_context"]["observation"],
        "decision": [(d["persona_role"], d["verdict"], d.get("decided_by")) for d in decisions],
        "outcome": output.get("status"),
        "what_if_vulnerable": {"decision": what_if.get("decision"), "summary": what_if.get("summary")},
    }


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "calls":
    print(json.dumps(run_calls(), indent=1))
