"""Second pass: redesigned questions for the weak spots found in eval_banking.py.

A2  persona gate as read-then-judge: Laya reads the reasoning with narrow paired questions,
    code compares the answers with the record, and the findings go to the judge question as words.
E2  vulnerability cues as narrow questions (one circumstance each).
F2  payment references against described scam patterns (knowledge in the criteria).
G2  customer reactions as narrow noul / score questions.
C2  ramp evidence in words (does Laya use linked claims when they are phrased as words?).
"""
from __future__ import annotations

import copy
import json
import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import eval_banking as base  # noqa: E402
from eval_banking import CALLS, gap, laya, top  # noqa: E402

READ_Q = {
    "vuln_yes": {"type": "noul", "instructions": "Does the text say the customer is vulnerable or carries a vulnerability marker?"},
    "vuln_absent": {"type": "noul", "instructions": "Does the text say no vulnerability flag or marker is present?"},
    "argues_refusal": {"type": "noul", "instructions": "Does the text argue that the bank should refuse the customer's claim?"},
    "no_action": {"type": "noul", "instructions": "Does the text say what would happen if the bank did nothing?"},
}
JUDGE_Q = {"gate": {
    "type": "choice",
    "instructions": "Given the findings, what should you do with the agent's recommendation?",
    "criteria": {
        "approve": "Approve it now: no concerns were found",
        "hold": "Hold it for a closer look because of the concerns found",
    },
}}
CLEAR = 0.3


def read_reasoning(text, tag):
    ans = laya({"text": text}, READ_Q, f"A2read:{tag}")
    out = {}
    for key, a in ans.items():
        out[key] = {"p": round(a["noul"], 3), "clear": abs(2 * a["noul"] - 1) >= CLEAR, "yes": a["noul"] >= 0.5}
    return out


def findings(obs, recommended_id, reading):
    """Code owns the comparison with the record; Laya only supplied the readings."""
    notes, unclear = [], []
    vulnerable = obs["claim"]["vulnerability_flag"] is True
    vy, va = reading["vuln_yes"], reading["vuln_absent"]
    if vy["clear"] and va["clear"] and vy["yes"] and va["yes"]:
        unclear.append("the reading of what the agent said about vulnerability is self-contradictory")
    elif va["clear"] and va["yes"] and vulnerable:
        notes.append("the agent's reasoning says there is no vulnerability marker, but the record shows one")
    elif vy["clear"] and vy["yes"] and not vulnerable:
        notes.append("the agent's reasoning says the customer is vulnerable, but the record shows no marker")
    elif not (vy["clear"] and va["clear"]):
        unclear.append("unclear what the agent said about vulnerability")
    ar = reading["argues_refusal"]
    if ar["clear"] and ar["yes"] and recommended_id != "SYN-APP-OPTION-REFUSE-CAUTION":
        notes.append("the agent's reasoning argues for refusal but it recommends paying the customer")
    elif not ar["clear"]:
        unclear.append("unclear whether the agent argued for refusal")
    na = reading["no_action"]
    if na["clear"] and not na["yes"]:
        notes.append("the agent's reasoning does not say what happens if the bank does nothing")
    return notes, unclear


def suite_a2():
    std, vul, over = (base.observation(s) for s in (
        base.FRAUD_SCENARIO_STANDARD, base.FRAUD_SCENARIO_VULNERABLE, base.FRAUD_SCENARIO_OVER_DELEGATION))
    warned = copy.deepcopy(std); warned["claim"]["specific_warning_ignored"] = True
    cases = [
        ("A1 standard (real)", std, "SYN-APP-OPTION-REIMBURSE-FULL", base.REAL_REASONING_STANDARD, "approve"),
        ("A2 vulnerable (real)", vul, "SYN-APP-OPTION-REIMBURSE-FULL", base.REAL_REASONING_VULNERABLE, "approve"),
        ("A3 vulnerable, reasoning says no marker", vul, "SYN-APP-OPTION-REIMBURSE-FULL", base.REAL_REASONING_STANDARD, "hold"),
        ("A4 recommends full, argues refusal", std, "SYN-APP-OPTION-REIMBURSE-FULL",
         "The customer was shown a specific warning and proceeded, so a refusal under the standard of caution would be justified; however the option admitted is full reimbursement.", "hold"),
        ("A5 warning ignored, recommends full", warned, "SYN-APP-OPTION-REIMBURSE-FULL",
         "The customer ignored a tailored warning, so refusal is permitted. Reimbursing in full is still preferred: the loss is modest, funds are partly recoverable and the receiving provider shares the cost. Refusing would leave the customer out of pocket.", "ambiguous"),
        ("A9 boilerplate reasoning", std, "SYN-APP-OPTION-REIMBURSE-FULL",
         "After careful consideration of all available information, the recommended option is the most appropriate course of action. It balances the relevant factors and aligns with policy.", "hold"),
    ]
    rows = []
    for name, obs, rec, why, label in cases:
        reading = read_reasoning(why, name)
        notes, unclear = findings(obs, rec, reading)
        verdicts = {}
        for style_name, style in (("cautious", "Cautious: you hold a case whenever any concern is found."),
                                  ("pragmatic", "Pragmatic: you hold a case only for a serious concern.")):
            state = {
                "you_are": "the Fraud Decision Manager at Zava Bank",
                "your_style": style,
                "recommendation": base.OPTION_WORDS[rec].capitalize(),
                "concerns_found": "; ".join(notes) if notes else "No concerns were found in the agent's reasoning.",
            }
            a = laya(state, JUDGE_Q, f"A2judge:{name}:{style_name}")["gate"]
            verdicts[style_name] = {"choice": top(a), "gap": round(gap(a), 3)}
        rows.append({"case": name, "label": label, "reading": {k: v["p"] for k, v in reading.items()},
                     "concerns": notes, "unclear": unclear, "verdicts": verdicts})
    return rows


CUE_Q = {
    "death": {"type": "noul", "instructions": "Does the customer mention that someone close to them has died?"},
    "illness": {"type": "noul", "instructions": "Does the customer mention an illness, a diagnosis or a stay in hospital?"},
    "confusion": {"type": "noul", "instructions": "Does the customer mention getting confused or forgetful?"},
    "isolation": {"type": "noul", "instructions": "Does the customer mention being lonely or having nobody to talk to?"},
    "money_worries": {"type": "noul", "instructions": "Does the customer mention debts, arrears or being desperate for money?"},
}


def suite_e2():
    rows = []
    for i, (text, _scam, cue) in enumerate(base.STATEMENTS):
        ans = laya({"customer_statement": text}, CUE_Q, f"E2:{i}")
        ps = {k: round(v["noul"], 3) for k, v in ans.items()}
        any_cue = any(p >= 0.5 for p in ps.values())
        rows.append({"i": i, "truth_cue": bool(cue), "any_cue": any_cue, "ok": any_cue == bool(cue), "p": ps})
    return rows


PATTERN_Q = {"pattern": {
    "type": "choice",
    "instructions": "Which description matches this payment reference?",
    "criteria": {
        "safe_account": "Moving money to a safe account to protect it",
        "authority_demand": "Paying a penalty, fine or demand from tax office, police or courts",
        "unlock_fee": "Paying a fee to release money, a parcel, a loan or a prize",
        "high_returns": "Investing for guaranteed or very high returns",
        "ordinary": "An ordinary bill, purchase, wage, gift or subscription",
        "unclear": "None of these clearly fits",
    },
}}


def suite_f2():
    rows = []
    for ref, truth in base.REFERENCES:
        a = laya({"payment_reference": ref}, PATTERN_Q, f"F2:{ref}")["pattern"]
        pick = top(a)
        flagged = pick not in ("ordinary", "unclear")
        rows.append({"ref": ref, "truth": truth, "pick": pick, "gap": round(gap(a), 3),
                     "correct": None if truth is None else flagged == bool(truth)})
    return rows


def suite_g2():
    rows = []
    upset_q = {"upset": {"type": "score", "instructions": "How upset is the customer with this decision?",
                         "criteria": ["Satisfied", "Mildly unhappy", "Upset", "Furious"]},
               "complain": {"type": "noul", "instructions": "Would this customer make a formal complaint about the decision?"}}
    for persona in ("A retired customer who lost their savings to a scam", "A small business owner who lost a supplier payment to a scam"):
        for d in base.DECISIONS:
            a = laya({"customer": persona, "decision": d}, upset_q, f"G2:{persona[:10]}:{d[:20]}")
            rows.append({"customer": persona[:30], "decision": d[:58], "upset_score": round(a["upset"]["score"], 2),
                         "p_complain": round(a["complain"]["noul"], 3)})
    return rows


def suite_c2():
    rows = []
    for band in ("medium", "high"):
        for claims_words, claims in (("one fraud claim", 1), ("six separate fraud claims from different victims", 6)):
            for bal_words in ("almost nothing left in it", "a large balance still in it"):
                case = {"kind": "mule", "risk_band": band}
                state = {"case": f"Receiving account under investigation for money-mule activity, risk band {band}. "
                                 f"It is linked to {claims_words}, with {bal_words}."}
                a = laya(state, base.ramp_question(case), f"C2:{band}:{claims}:{bal_words[:6]}")["rank"]
                rows.append({"band": band, "claims": claims, "balance": bal_words, "pick": top(a), "gap": round(gap(a), 3),
                             "p": {k: round(v, 3) for k, v in a["probabilities"].items()}})
    return rows


def main():
    start = len(CALLS)
    results = {"A2": suite_a2(), "E2": suite_e2(), "F2": suite_f2(), "G2": suite_g2(), "C2": suite_c2()}
    mine = CALLS[start:]
    results["calls"] = len(mine)
    results["server_ms_p50"] = statistics.median(c["server_ms"] for c in mine)
    (base.OUT / "summary2.json").write_text(json.dumps(results, indent=2))
    with (base.OUT / "calls2.jsonl").open("w") as fh:
        for c in mine:
            fh.write(json.dumps(c) + "\n")
    print(json.dumps(results, indent=1)[:12000])
    print(f"results written to {base.OUT}")


if __name__ == "__main__":
    main()
