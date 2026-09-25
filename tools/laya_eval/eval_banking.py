"""Laya evaluation on realistic Zava Bank cases (the measurements behind the spec).

Facts, thresholds and admission come from the real pack code (fraud_constraints,
reference data, the world model). Laya only gets the fuzzy judgement, phrased in
words, exactly as the skill's design rules require. Every call is logged.

Run against a local Laya server (read-only; no stack, no model quota):

    LAYA_PORT=8766 ~/.copilot/skills/laya/scripts/start.sh &
    LAYA_URL=http://127.0.0.1:8766 .venv/bin/python tools/laya_eval/eval_banking.py
    LAYA_URL=http://127.0.0.1:8766 .venv/bin/python tools/laya_eval/eval_redesign.py

Results land in $LAYA_EVAL_OUT (default: <tmp>/laya-eval).
See docs/superpowers/specs/2026-09-24-laya-decision-layer.md section 4.
"""
from __future__ import annotations

import copy
import json
import os
import pathlib
import random
import statistics
import sys
import tempfile
import time
import urllib.request

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from api.server.world.runtime import SimulationRuntime  # noqa: E402
from verticals.banking.authority import BANKING_AUTHORITY  # noqa: E402
from verticals.banking.fraud_constants import (  # noqa: E402
    FRAUD_SCENARIO_OVER_DELEGATION,
    FRAUD_SCENARIO_STANDARD,
    FRAUD_SCENARIO_VULNERABLE,
)
from verticals.banking.fraud_constraints import admit_claim_options  # noqa: E402
from verticals.banking.worlds import reference_data  # noqa: E402
from verticals.banking.worlds.scenario import ZavaBankWorld  # noqa: E402

URL = os.environ.get("LAYA_URL", "http://127.0.0.1:8765").rstrip("/")
URL = URL if URL.endswith("/v1/systemone") else URL + "/v1/systemone"
OUT = pathlib.Path(os.environ.get("LAYA_EVAL_OUT") or pathlib.Path(tempfile.gettempdir()) / "laya-eval")
OUT.mkdir(parents=True, exist_ok=True)
CALLS: list[dict] = []
THRESHOLD = 0.25  # the skill's starting point; tuned below from the gap distribution


def laya(state, questions, tag):
    body = json.dumps({"state": state, "questions": questions}).encode()
    req = urllib.request.Request(URL, body, {"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.load(resp)
    wall = (time.perf_counter() - t0) * 1000
    CALLS.append({
        "tag": tag, "state": state, "questions": questions, "answers": data["answers"],
        "server_ms": data.get("latency_ms"), "wall_ms": round(wall, 1), "usage": data.get("usage"),
    })
    return data["answers"]


def gap(answer):
    if answer.get("type") == "noul" or "noul" in answer and "probabilities" not in answer:
        return abs(2 * answer["noul"] - 1)
    vals = sorted(answer["probabilities"].values(), reverse=True)
    return vals[0] - (vals[1] if len(vals) > 1 else 0.0)


def top(answer):
    if "probabilities" in answer:
        return max(answer["probabilities"], key=answer["probabilities"].get)
    return "yes" if answer["noul"] >= 0.5 else "no"


def gbp(x):
    return f"GBP {x:,.0f}"


# ---------------------------------------------------------------------------
# Real world observations
# ---------------------------------------------------------------------------

def observation(scenario):
    world = ZavaBankWorld(seed=42, runtime=SimulationRuntime(42))
    world.install()
    world.activate_scenario(scenario)
    return copy.deepcopy(world.current_fraud_observation())


# Real recorded LLM reasoning from verticals/banking/recordings (22 Sep 2026).
REAL_REASONING_STANDARD = (
    "The only admitted option reimburses the customer in full, freezes recoverable funds in the "
    "beneficiary account, and raises the receiving provider's liability. This prioritizes customer "
    "harm recovery, maximizes available recovery, and ensures the receiving provider is engaged for "
    "their share. No vulnerability flag is present, so no additional protections apply. Not acting "
    "would leave the customer uncompensated and allow proceeds to remain with the beneficiary. There "
    "is no uncertainty in ranking as only one admitted, feasible option is present."
)
REAL_REASONING_VULNERABLE = (
    "The customer is flagged as vulnerable and suffered APP fraud. The admitted option reimburses the "
    "customer in full, freezes recoverable funds in the beneficiary account, and splits liability with "
    "the receiving provider. This prioritizes customer recovery and harm mitigation, ensures some "
    "recovery from the beneficiary, and holds the receiving provider accountable. No-action would leave "
    "a vulnerable customer uncompensated and undermine trust. There is no uncertainty in the admitted "
    "option; refusal is not possible for a vulnerable customer in this scenario."
)

OPTION_WORDS = {
    "SYN-APP-OPTION-REIMBURSE-FULL": "reimburse the customer in full",
    "SYN-APP-OPTION-REIMBURSE-CAPPED": "reimburse the customer up to the cap",
    "SYN-APP-OPTION-REFUSE-CAUTION": "refuse reimbursement under the consumer standard of caution",
}


def within_authority(role, value):
    # Mirrors api/shared/authority.py:91 (deny only when value > spend_limit_gbp).
    return not (value > BANKING_AUTHORITY[role].spend_limit_gbp)


def fraud_gate_state(obs, recommended_id, reasoning, style=None, render=0):
    """Code turns facts into words; Laya never sees a comparison it must compute."""
    claim, bene = obs["claim"], obs["beneficiary"]
    admitted = [r.option for r in admit_claim_options(obs) if r.feasible]
    rec = next(o for o in admitted if o.option_id == recommended_id)
    inside = within_authority("fraud_decision_manager", rec.value_gbp)
    facts = {
        "claim": f"The customer reports an authorised push payment scam of {gbp(claim['amount_gbp'])}.",
        "customer": (
            "The customer carries a vulnerability marker."
            if claim["vulnerability_flag"] else "No vulnerability marker is recorded for the customer."
        ),
        "warnings": (
            "The customer ignored a specific, tailored warning about this payee."
            if claim["specific_warning_ignored"] else
            ("A general warning was shown; there is no evidence a specific warning was ignored."
             if claim["warning_shown"] else "No warning was shown.")
        ),
        "permitted_options": "The rules permit: " + "; ".join(OPTION_WORDS[o.option_id] for o in admitted) + ".",
        "authority": (
            "The recommended amount is within your delegated authority."
            if inside else "The recommended amount is above your delegated authority."
        ),
        "receiving_account": (
            f"The money went to a {bene['holder_kind']} account rated {bene['risk_band']} risk"
            + (", held by one of Zava Bank's own business clients" if obs.get("corporate_holder") else "")
            + f". {gbp(claim['recoverable_gbp'])} can still be recovered."
        ),
        "agent_recommendation": f"{OPTION_WORDS[recommended_id].capitalize()} ({gbp(rec.value_gbp)}).",
        "agent_reasoning": reasoning,
    }
    if style:
        facts = {"your_style": style, **facts}
    if render == 0:
        return {"role": "You are the Fraud Decision Manager at Zava Bank.", **facts}
    if render == 1:  # one prose paragraph
        return "You are the Fraud Decision Manager at Zava Bank. " + " ".join(facts.values())
    renamed = {  # different keys and order
        "recommendation": facts["agent_recommendation"],
        "why_the_agent_recommends_it": facts["agent_reasoning"],
        "facts": " ".join(v for k, v in facts.items() if k not in ("agent_recommendation", "agent_reasoning")),
        "you_are": "the Fraud Decision Manager at Zava Bank",
    }
    return renamed


GATE_Q = {
    "gate": {
        "type": "choice",
        "instructions": "What should you do with the agent's recommendation?",
        "criteria": {
            "approve": "Approve it now: the case is routine and the evidence is consistent",
            "hold": "Hold it for a closer look: something is inconsistent, unusual or harmful",
        },
    }
}


def suite_a():
    std, vul, over = (observation(s) for s in (
        FRAUD_SCENARIO_STANDARD, FRAUD_SCENARIO_VULNERABLE, FRAUD_SCENARIO_OVER_DELEGATION))
    warned = copy.deepcopy(std); warned["claim"]["specific_warning_ignored"] = True
    big = copy.deepcopy(std); big["claim"]["amount_gbp"] = 48_000.0
    nothing_left = copy.deepcopy(std); nothing_left["claim"]["recoverable_gbp"] = 0.0
    small = copy.deepcopy(vul); small["claim"]["amount_gbp"] = 950.0
    small["claim"]["vulnerability_flag"] = False; small["customer"]["vulnerability_flag"] = False
    routine_48k = REAL_REASONING_STANDARD
    refuse_argument = (
        "The customer was shown a specific warning and proceeded, so a refusal under the standard of "
        "caution would be justified; however the option admitted is full reimbursement."
    )
    full_despite_warning = (
        "The customer ignored a tailored warning, so refusal is permitted. Reimbursing in full is still "
        "preferred: the loss is modest, funds are partly recoverable and the receiving provider shares the "
        "cost. Refusing would leave the customer out of pocket."
    )
    refuse_reasoning = (
        "The customer ignored a specific, tailored warning about this payee, which meets the consumer "
        "standard of caution. Refusing reimbursement is therefore ranked first; the account is still frozen."
    )
    cases = [
        ("A1 standard (real reasoning)", std, "SYN-APP-OPTION-REIMBURSE-FULL", REAL_REASONING_STANDARD, "approve"),
        ("A2 vulnerable (real reasoning)", vul, "SYN-APP-OPTION-REIMBURSE-FULL", REAL_REASONING_VULNERABLE, "approve"),
        ("A3 vulnerable, reasoning says no marker", vul, "SYN-APP-OPTION-REIMBURSE-FULL", REAL_REASONING_STANDARD, "hold"),
        ("A4 recommends full, argues refusal", std, "SYN-APP-OPTION-REIMBURSE-FULL", refuse_argument, "hold"),
        ("A5 warning ignored, recommends full", warned, "SYN-APP-OPTION-REIMBURSE-FULL", full_despite_warning, "ambiguous"),
        ("A6 warning ignored, recommends refusal", warned, "SYN-APP-OPTION-REFUSE-CAUTION", refuse_reasoning, "hold"),
        ("A7 GBP 48,000 routine", big, "SYN-APP-OPTION-REIMBURSE-FULL", routine_48k, "approve"),
        ("A8 capped GBP 85,000 above authority", over, "SYN-APP-OPTION-REIMBURSE-CAPPED", REAL_REASONING_STANDARD, "hold"),
        ("A9 nothing recoverable", nothing_left, "SYN-APP-OPTION-REIMBURSE-FULL", REAL_REASONING_STANDARD, "approve"),
        ("A10 GBP 950 low stakes", small, "SYN-APP-OPTION-REIMBURSE-FULL", REAL_REASONING_STANDARD, "approve"),
    ]
    rows = []
    for name, obs, rec, why, label in cases:
        renders = []
        for render in (0, 1, 2):
            ans = laya(fraud_gate_state(obs, rec, why, render=render), GATE_Q, f"A:{name}:r{render}")["gate"]
            renders.append({"choice": top(ans), "p": ans["probabilities"], "gap": round(gap(ans), 3)})
        styles = {}
        for style_name, style in (
            ("cautious", "Cautious: when anything is uncertain you hold the case for a closer look."),
            ("pragmatic", "Pragmatic: you approve routine, consistent cases quickly."),
        ):
            ans = laya(fraud_gate_state(obs, rec, why, style=style), GATE_Q, f"A:{name}:{style_name}")["gate"]
            styles[style_name] = {"choice": top(ans), "p_hold": round(ans["probabilities"]["hold"], 3)}
        rows.append({"case": name, "label": label, "renders": renders, "styles": styles})
    return rows


# ---------------------------------------------------------------------------
# B. Threshold maths (expected to fail: proves code must own comparisons)
# ---------------------------------------------------------------------------

def suite_b():
    rows = []
    limit = 50_000
    for amount in (950, 6_750, 18_400, 48_000, 49_999, 50_000, 50_001, 52_000, 85_000, 92_000, 120_000, 250_001):
        state = {"claim_amount": gbp(amount), "your_delegated_authority": f"up to {gbp(limit)}"}
        ans = laya(state, {"inside": {"type": "noul", "instructions": "Is the claim amount within your delegated authority?"}}, f"B:{amount}")["inside"]
        truth = amount <= limit
        rows.append({"amount": amount, "truth": truth, "p_yes": round(ans["noul"], 3), "correct": (ans["noul"] >= 0.5) == truth})
    return rows


# ---------------------------------------------------------------------------
# C. Ramp ranking on the ramp's own case shapes (spawners.py draws, seed 1729)
# ---------------------------------------------------------------------------

_RISK_BANDS = ("low", "medium", "medium", "high")
_SECTORS = ("logistics", "wholesale", "construction", "hospitality", "professional-services", "technology")
MULE_OPTIONS = {
    "restrain": ("SYN-MULE-OPTION-RESTRAIN", "Restrain the account and preserve the balance"),
    "monitor": ("SYN-MULE-OPTION-MONITOR", "Keep the account open under enhanced monitoring"),
    "close": ("SYN-MULE-OPTION-CLOSE", "Close the account and return residual funds"),
}
MERCHANT_OPTIONS = {
    "standard": ("SYN-MER-OPTION-ONBOARD-STANDARD", "Onboard on standard terms"),
    "reserve": ("SYN-MER-OPTION-ONBOARD-RESERVE", "Onboard with a rolling reserve held back"),
    "decline": ("SYN-MER-OPTION-DECLINE", "Decline the application"),
}


def admitted_keys(kind, band):
    # Mirrors verticals/banking/supporting_durable.py:203-210.
    keys = list(MULE_OPTIONS if kind == "mule" else MERCHANT_OPTIONS)
    if band == "low":
        keys = [k for k in keys if k not in ("restrain", "close", "decline")]
    if band == "high":
        keys = [k for k in keys if k not in ("monitor", "standard")]
    return keys


def ramp_cases(n=16):
    rng = random.Random(1_729)
    cases = []
    for i in range(n):
        if i % 2 == 0:
            cases.append({
                "kind": "mule", "subject": f"SYN-BENE-{rng.randint(1, 240):03d}",
                "risk_band": rng.choice(_RISK_BANDS), "linked_claims": rng.randint(1, 6),
                "balance": float(rng.randint(1_200, 140_000)),
            })
        else:
            cases.append({
                "kind": "merchant", "risk_band": rng.choice(_RISK_BANDS), "sector": rng.choice(_SECTORS),
                "volume": float(rng.randint(8_000, 900_000)),
            })
    return cases


def ramp_state(case, render=0):
    if case["kind"] == "mule":
        facts = [
            f"Receiving account under investigation for money-mule activity, risk band {case['risk_band']}.",
            f"It is linked to {case['linked_claims']} fraud claim{'s' if case['linked_claims'] != 1 else ''}.",
            f"It holds {gbp(case['balance'])}.",
        ]
    else:
        facts = [
            f"New merchant application, risk band {case['risk_band']}, sector {case['sector']}.",
            f"Projected card volume {gbp(case['volume'])} a month.",
        ]
    if render == 0:
        return {"case": " ".join(facts)}
    return " ".join(reversed(facts))


def ramp_question(case):
    options = MULE_OPTIONS if case["kind"] == "mule" else MERCHANT_OPTIONS
    keys = admitted_keys(case["kind"], case["risk_band"])
    return {"rank": {
        "type": "choice",
        "instructions": "Which permitted disposition is best for this case?" if case["kind"] == "mule"
        else "Which permitted onboarding decision is best for this application?",
        "criteria": {k: options[k][1] for k in keys},
    }}


def suite_c():
    rows = []
    for idx, case in enumerate(ramp_cases()):
        q = ramp_question(case)
        if len(q["rank"]["criteria"]) == 1:
            rows.append({"i": idx, **case, "admitted": list(q["rank"]["criteria"]), "single_option": True})
            continue
        a0 = laya(ramp_state(case, 0), q, f"C:{idx}:r0")["rank"]
        a1 = laya(ramp_state(case, 1), q, f"C:{idx}:r1")["rank"]
        rows.append({
            "i": idx, **case, "admitted": list(q["rank"]["criteria"]), "single_option": False,
            "pick": top(a0), "gap": round(gap(a0), 3), "p": {k: round(v, 3) for k, v in a0["probabilities"].items()},
            "pick_paraphrase": top(a1), "gap_paraphrase": round(gap(a1), 3),
        })
    # Sensitivity: hold band fixed and vary the evidence.
    sens = []
    for band in ("medium", "high"):
        for claims, bal in ((1, 2_000.0), (6, 130_000.0)):
            case = {"kind": "mule", "risk_band": band, "linked_claims": claims, "balance": bal, "subject": "SYN-BENE-TEST"}
            a = laya(ramp_state(case), ramp_question(case), f"C:sens:{band}:{claims}")["rank"]
            sens.append({"band": band, "linked_claims": claims, "balance": bal, "pick": top(a), "gap": round(gap(a), 3),
                         "p": {k: round(v, 3) for k, v in a["probabilities"].items()}})
    return rows, sens


# ---------------------------------------------------------------------------
# D. Reading the agent's reasoning (truth by construction)
# ---------------------------------------------------------------------------

READING_Q = {
    "vuln_yes": {"type": "noul", "instructions": "Does the text say the customer is vulnerable or carries a vulnerability marker?"},
    "vuln_no": {"type": "noul", "instructions": "Does the text say the customer has no vulnerability marker?"},
    "recovery": {"type": "noul", "instructions": "Does the text discuss freezing or recovering money in the receiving account?"},
    "no_action": {"type": "noul", "instructions": "Does the text say what would happen if the bank did nothing?"},
    "refuse": {"type": "noul", "instructions": "Does the text argue that the bank should refuse the customer's claim?"},
    "provider_share": {"type": "noul", "instructions": "Does the text say the receiving provider shares the cost or liability?"},
}
TEXTS = [
    ("D1 real standard", REAL_REASONING_STANDARD, dict(vuln_yes=0, vuln_no=1, recovery=1, no_action=1, refuse=0, provider_share=1)),
    ("D2 real vulnerable", REAL_REASONING_VULNERABLE, dict(vuln_yes=1, vuln_no=0, recovery=1, no_action=1, refuse=0, provider_share=1)),
    ("D3 boilerplate", "After careful consideration of all available information, the recommended option is the most appropriate course of action. It balances the relevant factors and aligns with policy.", dict(vuln_yes=0, vuln_no=0, recovery=0, no_action=0, refuse=0, provider_share=0)),
    ("D4 argues refusal", "The customer was shown a specific, tailored warning about this payee and proceeded anyway. Under the consumer standard of caution the bank should refuse reimbursement, while still freezing what remains in the receiving account.", dict(vuln_yes=0, vuln_no=0, recovery=1, no_action=0, refuse=1, provider_share=0)),
    ("D5 recovery and share only", "Freezing the funds still held in the beneficiary account gives the best chance of recovering the customer's money, and the receiving provider should carry half of the loss.", dict(vuln_yes=0, vuln_no=0, recovery=1, no_action=0, refuse=0, provider_share=1)),
    ("D6 vulnerable, no recovery", "The customer carries a vulnerability marker, so the bank must reimburse in full and cannot refuse under the standard of caution. Doing nothing would leave a vulnerable customer out of pocket.", dict(vuln_yes=1, vuln_no=0, recovery=0, no_action=1, refuse=0, provider_share=0)),
]


def suite_d():
    rows = []
    for name, text, truth in TEXTS:
        ans = laya({"text": text}, READING_Q, f"D:{name}")
        for q, t in truth.items():
            p = ans[q]["noul"]
            rows.append({"text": name, "q": q, "truth": bool(t), "p_yes": round(p, 3), "correct": (p >= 0.5) == bool(t), "gap": round(abs(2 * p - 1), 3)})
    return rows


# ---------------------------------------------------------------------------
# E. The customer's own words: scam type and vulnerability cues (authored truth)
# ---------------------------------------------------------------------------

SCAM_Q = {
    "scam_type": {
        "type": "choice",
        "instructions": "What kind of case does the customer describe?",
        "criteria": {
            "impersonation": "Someone pretending to be the bank, police, tax office or another authority",
            "romance": "A fake romantic partner asking for money",
            "investment": "A fake investment or trading opportunity",
            "purchase": "Paying for goods or services that never arrived",
            "invoice": "A supplier or tradesperson's bank details were changed",
            "advance_fee": "An upfront fee for a loan, prize or refund that never came",
            "not_scam": "Not a scam: a dispute with a real trader or a payment to their own account",
        },
    },
    "vulnerable_cue": {"type": "noul", "instructions": "Does the customer mention circumstances that could make them vulnerable, such as bereavement, illness, confusion, isolation or money worries?"},
}
STATEMENTS = [
    ("Someone rang saying they were from Zava Bank's fraud team. They said my account was compromised and I had to move my savings to a safe account. I sent 18,400 pounds and now the number doesn't work.", "impersonation", 0),
    ("I met Daniel on a dating site eight months ago. He needed money for a hospital bill abroad and promised to pay me back. Since my husband died last year he was the only person I talked to. I have sent him 6,750 pounds.", "romance", 1),
    ("A broker on social media showed me a crypto platform paying 3 percent a week. I moved 92,000 pounds from my business account and now they want a release fee before I can withdraw.", "investment", 0),
    ("I paid 950 pounds for a car I found on a marketplace. The seller asked for a bank transfer instead of using the app and never delivered it.", "purchase", 0),
    ("Our builder emailed to say their bank details had changed, so we paid the 23,500 pound stage payment to the new account. The real builder never got it.", "invoice", 0),
    ("I'm behind on my rent and was desperate. A lender approved me online but I had to pay a 600 pound insurance fee first. After I paid, the company vanished.", "advance_fee", 1),
    ("I paid a kitchen fitter 4,200 pounds. He did fit the kitchen but the work is poor and he won't come back to fix it.", "not_scam", 0),
    ("I moved 3,000 pounds to my own savings account at another bank and I want it reversed.", "not_scam", 0),
    ("A man said he was a police officer investigating my bank and told me not to tell anyone. My daughter says I get confused since my diagnosis. I sent 12,000 pounds.", "impersonation", 1),
    ("I bought two festival tickets from a man on a fan forum for 380 pounds. The tickets never arrived and he blocked me.", "purchase", 0),
    ("I'm just out of hospital after a stroke and wanted to grow my pension. An adviser on the phone put 40,000 pounds into a bond that doesn't exist.", "investment", 1),
    ("I got a text from the tax office saying I owed a penalty and would be arrested. I paid 2,300 pounds through the link.", "impersonation", 0),
]


def suite_e():
    rows = []
    for i, (text, scam, cue) in enumerate(STATEMENTS):
        ans = laya({"customer_statement": text}, SCAM_Q, f"E:{i}")
        st, vc = ans["scam_type"], ans["vulnerable_cue"]
        rows.append({"i": i, "truth_type": scam, "pick": top(st), "gap": round(gap(st), 3), "type_ok": top(st) == scam,
                     "truth_cue": bool(cue), "p_cue": round(vc["noul"], 3), "cue_ok": (vc["noul"] >= 0.5) == bool(cue)})
    return rows


# ---------------------------------------------------------------------------
# F. Screening payment references (authored truth; 'unclear' is not scored)
# ---------------------------------------------------------------------------

REFERENCES = [
    ("Rent October flat 3", 0), ("Council tax September", 0), ("Payroll SEP26 ACME LTD", 0),
    ("Invoice 2291 kitchen units", 0), ("Birthday present for Mia", 0), ("Gym membership", 0),
    ("Car insurance renewal", 0), ("Nursery fees autumn term", 0),
    ("Safe account transfer as advised by bank", 1), ("HMRC penalty urgent payment", 1),
    ("Crypto wallet top up guaranteed returns", 1), ("Release fee to unlock withdrawal", 1),
    ("Customs fee for held parcel", 1), ("Loan insurance fee before payout", 1),
    ("Protect funds police investigation", 1), ("Investment platform deposit 3 percent weekly", 1),
    ("Holiday villa deposit", None), ("Deposit for puppy", None), ("Loan to Daniel", None),
]


def suite_f():
    rows = []
    q = {"scam_sign": {"type": "noul", "instructions": "Does this payment reference suggest the customer is being scammed?"}}
    for ref, truth in REFERENCES:
        ans = laya({"payment_reference": ref}, q, f"F:{ref}")["scam_sign"]
        rows.append({"ref": ref, "truth": truth, "p_yes": round(ans["noul"], 3),
                     "correct": None if truth is None else (ans["noul"] >= 0.5) == bool(truth), "gap": round(abs(2 * ans["noul"] - 1), 3)})
    return rows


# ---------------------------------------------------------------------------
# G. Simulated actors reacting to decisions (no truth: sensitivity + variety)
# ---------------------------------------------------------------------------

REACT_Q = {"react": {
    "type": "choice",
    "instructions": "How does the customer most likely respond to the bank's decision?",
    "criteria": {
        "accepts": "Accepts the outcome and moves on",
        "chases": "Calls or messages to chase an update",
        "complains": "Makes a formal complaint to the bank",
        "ombudsman": "Takes the complaint to the ombudsman",
    },
}}
DECISIONS = [
    "The bank reimbursed the full amount within two days.",
    "The bank is holding the claim for a closer look; a decision is due within five business days.",
    "The bank refused the claim because the customer ignored a specific warning.",
    "The bank reimbursed only part of the claim, up to the reimbursement cap.",
]


def suite_g():
    rows = []
    for persona in ("A retired customer who lost their savings", "A small business owner who lost a supplier payment"):
        for d in DECISIONS:
            ans = laya({"customer": persona, "decision": d}, REACT_Q, f"G:{persona[:12]}:{d[:24]}")["react"]
            rows.append({"customer": persona, "decision": d, "pick": top(ans), "gap": round(gap(ans), 3),
                         "p": {k: round(v, 3) for k, v in ans["probabilities"].items()}})
    fraud_q = {"move": {"type": "choice", "instructions": "What does the person controlling this account most likely do next?",
                        "criteria": {"drain": "Moves the remaining money out quickly", "quiet": "Goes quiet and waits",
                                     "new_account": "Opens a new account elsewhere", "nothing": "Carries on as normal"}}}
    for status in ("The bank has restrained the account; no money can leave it.",
                   "The account is open under enhanced monitoring.",
                   "Nothing has happened to the account yet."):
        ans = laya({"account": "A receiving account used to collect scam payments.", "status": status}, fraud_q, f"G:mule:{status[:20]}")["move"]
        rows.append({"customer": "mule controller", "decision": status, "pick": top(ans), "gap": round(gap(ans), 3),
                     "p": {k: round(v, 3) for k, v in ans["probabilities"].items()}})
    return rows


# ---------------------------------------------------------------------------
# Latency: cold vs warm, one question vs several
# ---------------------------------------------------------------------------

def suite_latency():
    one = {"q": {"type": "noul", "instructions": "Is this routine?"}}
    three = {f"q{i}": {"type": "noul", "instructions": f"Question {i}: is this routine?"} for i in range(3)}
    six = READING_Q
    out = {}
    for name, qs in (("one", one), ("three", three), ("six", six)):
        server = []
        wall = []
        for _ in range(12):
            laya({"text": REAL_REASONING_STANDARD}, qs, f"L:{name}")
            server.append(CALLS[-1]["server_ms"]); wall.append(CALLS[-1]["wall_ms"])
        server_warm, wall_warm = server[2:], wall[2:]
        out[name] = {"first_server_ms": server[0], "p50_server_ms": statistics.median(server_warm),
                     "max_server_ms": max(server_warm), "p50_wall_ms": statistics.median(wall_warm)}
    return out


def main():
    results = {}
    t0 = time.time()
    results["latency"] = suite_latency()
    results["A_persona_gate"] = suite_a()
    results["B_threshold_maths"] = suite_b()
    results["C_ramp_ranking"], results["C_sensitivity"] = suite_c()
    results["D_reasoning_reading"] = suite_d()
    results["E_customer_words"] = suite_e()
    results["F_payment_references"] = suite_f()
    results["G_actor_reactions"] = suite_g()
    results["calls"] = len(CALLS)
    results["elapsed_s"] = round(time.time() - t0, 1)
    all_server = [c["server_ms"] for c in CALLS if c["server_ms"] is not None]
    results["all_calls_server_ms"] = {"p50": statistics.median(all_server), "p95": sorted(all_server)[int(0.95 * len(all_server)) - 1], "max": max(all_server)}
    (OUT / "summary.json").write_text(json.dumps(results, indent=2))
    with (OUT / "calls.jsonl").open("w") as fh:
        for c in CALLS:
            fh.write(json.dumps(c) + "\n")
    print(json.dumps({k: v for k, v in results.items() if k in ("calls", "elapsed_s", "all_calls_server_ms", "latency")}, indent=2))


if __name__ == "__main__":
    main()
