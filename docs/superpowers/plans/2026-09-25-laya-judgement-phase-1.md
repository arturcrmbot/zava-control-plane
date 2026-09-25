# Laya judgement, phase 0 and 1: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Personas judge each gate with Laya (read, check, judge), hand holds and
over-authority claims to the next persona the governance kernel names, and fall
back to an LLM deep review and then today's rules. Every decision carries its
evidence.

**Architecture:** A shared package `api/server/services/judgement/` (Laya client,
profiles, engine, deep review, evidence), called from `persona_responder._handle_hitl`
after today's `decision_policy`, which stays the ceiling. Banking adds profiles to
three persona SKILL.md files, a facts adapter, and an escalation path in
`fraud_durable.py`. Everything is off unless `JUDGEMENT_ENABLED=1`.

**Tech stack:** Python 3.11, httpx (async), pytest; Laya at `LAYA_URL`
(`POST /v1/systemone`); the LLM through `_get_runtime().run_session`
(`LLM_RUNTIME=fake` in tests); React/vitest for the floor.

**Spec:** `docs/superpowers/specs/2026-09-24-laya-decision-layer.md`

---

## Design decisions made while planning

- **Opt-in is the profile.** A persona is judged when `JUDGEMENT_ENABLED=1` and its
  SKILL.md has a `judgement:` block for the gate's workflow type. No pack-manifest
  field is needed (YAGNI).
- **Profiles are keyed by workflow type** (`judgement.gates.<workflow_type>`), so one
  persona can judge several processes. The Financial Crime Lead judges mule
  dispositions and escalated reimbursements.
- **`min_lead` replaces `min_gap`,** matching the spec's word "lead".
- **Check severity.** A `serious` check whose reading is unclear makes the
  judgement unclear, which triggers a deep review. A `minor` check is raised only
  when its reading is clear. A check applies only when its fact conditions hold.
- **In-flight guard.** The 30 s sweep re-handles open gates. While a judgement is
  running for a gate, a second handling of the same gate is skipped. The guard is
  active only when judgement is enabled.
- **Escalation follows the same flag.** `fraud_governance_activity` adds
  `escalation` (the kernel's approver, if that persona has authority) and
  `escalate_to` (the authority row's `delegate_to`). It does this only when
  `JUDGEMENT_ENABLED=1`, so with the flag off the orchestration is byte-identical.
- **A top-of-chain hold** goes to the deep review. If the deep review is spent or
  unavailable, the rules decide.
- **A decline from a persona** reaches the orchestrator as `decision: "reject"`. The
  denial reason carries the persona's words.

## File map

| File | Responsibility |
|---|---|
| `api/server/services/judgement/__init__.py` | Public surface: `judgement_enabled()`, re-exports |
| `api/server/services/judgement/laya_client.py` | Async Laya client, answer parsing, lead, circuit breaker |
| `api/server/services/judgement/evidence.py` | `Reading`, `Verdict`, `DeepReviewRecord`, `Judgement` (+ `to_dict`, `summary`) |
| `api/server/services/judgement/profiles.py` | Parse and validate `judgement:` blocks; `GateFacts`; facts-adapter resolution |
| `api/server/services/judgement/deep_review.py` | Hourly budget, LLM prompt, JSON verdict parsing |
| `api/server/services/judgement/engine.py` | `judge_gate()`: ceiling, read, check, judge, deep review, rules |
| `api/server/services/persona_responder.py` | Load profiles; call the engine; guard; skip fake delays and override dice when judged; emit `persona.judgement`; stash evidence; pass concerns up on a hold |
| `verticals/banking/judgement_facts.py` | Facts adapters for the fraud, mule and merchant gates |
| `verticals/banking/personae/{fraud_decision_manager,financial_crime_lead,payments_operations_lead}/SKILL.md` | `personality` and `judgement:` profiles |
| `verticals/banking/fraud_durable.py` | Escalation in governance, gate persona, accepted approvers, approving persona on the command, decline reason |
| `verticals/banking/supporting_durable.py` | Decline reason carries the persona's words |
| `verticals/banking/detail.py` | `governedDecisions` carry `decidedBy`, `concerns`, `judgement` |
| `web/client/routes/BankingWorld.tsx` | Story panel and recent cases show who decided and why |
| `.env.example`, `docs/banking-demo-runbook.md` | Flags and how to start Laya |
| `tools/laya_eval/` | Evaluation harness (moved from the session) |
| `tests/api/judgement/*` | Client, profiles, engine, deep review, live golden set |
| `tests/api/banking/test_banking_judgement.py` | Facts adapters, banking profiles, escalation orchestration |
| `tests/api/server/services/test_persona_responder_judgement.py` | Responder integration |

## Tasks

### Task 1: Laya client
- [ ] Tests `tests/api/judgement/test_laya_client.py` (httpx `MockTransport`, fake clock):
  - parses choice, noul and score answers into `LayaAnswer(kind, probabilities, top, lead, score)`, where noul becomes `{"yes": p, "no": 1-p}` with lead `|2p-1|`
  - posts `{"state", "questions"}` to `<LAYA_URL>/v1/systemone`, and accepts a URL that already ends in `/v1/systemone`
  - HTTP error, timeout or bad JSON raises `LayaUnavailable` and counts a failure
  - three failures open the breaker (`available()` is False, `ask` raises without a request); after the 30 s cool-down it closes; a success resets the count
  - `LAYA_URL` unset: `enabled` is False and `ask` raises
- [ ] Implement `laya_client.py`, with `get_client()` / `reset_client()` singletons.
- [ ] Run `ZAVA_VERTICAL=banking .venv/bin/python -m pytest tests/api/judgement/test_laya_client.py -q -p no:cacheprovider`; expect pass.

### Task 2: Evidence record
- [ ] Tests `tests/api/judgement/test_evidence.py`:
  - `Judgement.to_dict()` is JSON-serialisable and holds persona, gate, `decided_by`, verdict, concerns, unclear, readings (id, question, p_yes, lead, clear), judge verdict (choice, probabilities, lead, threshold), deep review, fallback reason and latency
  - `summary()` produces:
    - approve: "Approved after reading the agent's reasoning: no concerns found."
    - hold: "Held for a closer look: <concerns>."
    - llm: "Deep review: <rationale, 2 sentences>."
    - rules: "Decided by rules: <reason>."
- [ ] Implement `evidence.py` (dataclasses).

### Task 3: Profiles
- [ ] Tests `tests/api/judgement/test_profiles.py`:
  - parses a valid block: character, gates, facts ref `module:function` resolved to a callable, reads, checks (`when` with read/is and/or fact/equals, `unless`, severity), decide, `min_lead`
  - rejects:
    - a check naming an unknown read
    - an `is` other than yes/no
    - a missing decide option
    - `min_lead` outside 0..1
    - a facts ref that isn't importable or is outside `verticals.`/`api.`
    - a duplicate read id
    - more than 8 reads
  - `ProfileError` names the persona and the field
- [ ] Implement `profiles.py` with `GateFacts(texts, facts, recommendation, case, prior_concerns)`.

### Task 4: Deep review
- [ ] Tests `tests/api/judgement/test_deep_review.py`:
  - `Budget(limit=2)` allows two in a rolling hour and refuses the third; the window slides; limit 0 never allows
  - with `FakeRuntime.canned_text = '{"decision":"approve","rationale":"..."}'`, `review()` returns `DeepReviewRecord(decision="approve", rationale, latency_ms)`; the prompt contains the case, the recommendation, the agent reasoning and the concerns
  - fenced or prose-wrapped JSON is parsed; invalid JSON or an unknown decision returns `None` and records the error; a runtime exception returns `None`
- [ ] Implement `deep_review.py`. Use `JUDGEMENT_LLM_BUDGET_PER_HOUR` (default 6), `JUDGEMENT_LLM_MODEL` (default `gpt-4.1`), a 90 s timeout and one session at a time.

### Task 5: Engine
- [ ] Tests `tests/api/judgement/test_engine.py` with a scripted fake client and a fake deep review:
  - flag off, no profile or no gate: the ceiling payload is returned unchanged, with no judgement
  - **caution only**: for each ceiling in (reject, escalate) and each scripted Laya/LLM answer, the outcome is never approve
  - clear approve: the payload equals the ceiling payload plus `decided_by="laya"`, `judgement_summary` and `authority_reason`; `reason` is the summary; `hold` is False
  - contradiction (the reasoning says no marker; the record is vulnerable): a hold with the concern in words
    - not top of chain: the payload is `decision="escalate"`
    - top of chain: the deep review decides (approve → approve with `decided_by="llm"`, hold → `decision="reject"` with the rationale)
  - a serious reading unclear or a small verdict lead sends it to the deep review; with the budget spent, the ceiling applies with `decided_by="rules"` and `fallback_reason`
  - a paired contradiction (`unless` is also a clear yes) is unclear, not a concern
  - a minor unclear reading is ignored
  - `LayaUnavailable` or an adapter exception: the rules decide, with the reason recorded
- [ ] Implement `engine.py`: `async judge_gate(persona_role, profile, context, ceiling_payload, *, next_role, client=None, reviewer=None) -> Outcome(payload, judgement, hold)`.

### Task 6: Banking facts and profiles
- [ ] Tests in `tests/api/banking/test_banking_judgement.py`:
  - `fraud_gate` on a real standard observation with its gate context: the texts include `agent_reasoning`; the facts are `customer_vulnerable=False`, `recommends_refusal=False`; the recommendation reads "Reimburse the customer in full (GBP 18,400)"; the case sentence states vulnerability and authority in words
  - vulnerable and refusal variants set the facts; `held_by` becomes prior concerns
  - `mule_gate` and `merchant_gate` set their facts from the case and the selected option
  - the three banking SKILL.md files load with judgement profiles for their workflow types, and the Financial Crime Lead has both `app-fraud-reimbursement` and `mule-account-investigation`
- [ ] Implement `verticals/banking/judgement_facts.py`, then add `personality` and `judgement` to the three SKILL.md files. Reads and checks come from the measured design (spec 6.2); mule and merchant reads are validated live in Task 11.

### Task 7: Persona responder integration
- [ ] Tests `tests/api/server/services/test_persona_responder_judgement.py` (banking pack, `PERSONA_AUTO_CLOSE=*`, a fake engine client, `raise_orchestration_event` monkeypatched):
  - flag off: the event raised is identical to today's, and there is no `persona.judgement` event
  - flag on with an approving judgement: the raised payload has `decided_by`, the stash has `judgement`, and `persona.judgement` is emitted
  - flag on with a hold from the Fraud Decision Manager and `escalate_to=financial_crime_lead` in the context: the event is raised once, by the Financial Crime Lead, with the original `fraud_decision_manager_decision` event name, and the context the Financial Crime Lead sees carries `held_by`
  - in-flight guard: a second concurrent handling of the same gate does not decide twice
  - `DEMO_LOUD=1` does not sleep on a judged gate
- [ ] Implement it in `persona_responder.py`:
  - `PersonaDefinition.judgement` and `skill_body`
  - load the profiles
  - compute the next role (explicit chain / `escalate_to` / parent, never self)
  - call the engine after `persona.decide`
  - carry `held_by` on the cascade
  - emit the event and stash the decision

### Task 8: Escalation in the fraud orchestration
- [ ] Tests in `tests/api/banking/test_banking_judgement.py` (drive the generator like `_run_to_refusal`):
  - flag off: `fraud_governance_activity` output has no `escalation` or `escalate_to` (governance reads the real kernel), and the refusal stays as today (existing tests unchanged)
  - flag on, £85,000 capped: governance returns `escalation.role == "financial_crime_lead"`; the orchestration raises the gate with `persona="financial_crime_lead"` and `external_event="fraud_decision_manager_decision"`; an approval from `financial_crime_lead` reaches the command activity with that persona
  - flag on, within authority: `escalate_to == "financial_crime_lead"`; an approval from the Financial Crime Lead after a hold is re-checked by governance and accepted; an approval from any other persona is denied
  - a decline (`decision="reject"`) ends with the persona's reason in `reasoning`
- [ ] Implement it in `fraud_durable.py`:
  - `fraud_governance_activity` accepts an optional `role` and adds `escalation`/`escalate_to` behind the flag
  - `_approval_reason` takes `allowed_personas` and names the decline reason
  - the orchestration uses the gate persona, re-checks an escalated approver, and passes the approving persona to `fraud_command_activity`
- [ ] Change `supporting_durable.case_command_activity` so the decline reason carries the persona's words.

### Task 9: Detail and floor
- [ ] Test `tests/api/banking/test_banking_vertical.py`-style: `workflow_detail` `governedDecisions` include `decidedBy`, `concerns` and `judgementSummary` when present, and are unchanged when absent.
- [ ] Vitest `web/client/routes/__tests__/BankingWorld.test.tsx`:
  - a story whose workflow decisions include a hold and an escalated approval renders "Fraud decision manager held it · <concern>" then "Financial crime lead approved · fast judgement"
  - recent cases show who decided
- [ ] Implement it in `detail.py` and `BankingWorld.tsx`.

### Task 10: Flags, docs, harness
- [ ] `.env.example`: `LAYA_URL`, `JUDGEMENT_ENABLED`, `JUDGEMENT_LLM_BUDGET_PER_HOUR`, `JUDGEMENT_MIN_LEAD`, `JUDGEMENT_LLM_MODEL` with comments.
- [ ] Runbook: start Laya, set the flags in both processes, what the audience sees, fallbacks.
- [ ] `tools/laya_eval/`: the harness and redesign scripts, parameterised by `LAYA_URL`.

### Task 11: Live golden set and verification
- [ ] `tests/api/judgement/test_laya_live.py` (skipped unless `LAYA_URL` answers `/health`):
  - reading golden set of at least 30/36
  - fraud gate: standard → approve, contradiction → hold, refusal → hold, through the real engine and the banking profiles
  - mule and merchant profile reads on authored reasoning texts go the right way
- [ ] Start Laya on 8766 and run the live tests. Then run the banking suite, `tests/api/judgement`, the persona responder files one by one, the governance tests and vitest for `BankingWorld`.
- [ ] End to end in process: raise real claims in a `ZavaBankWorld` (standard, vulnerable, high-value, refusal-admitted), build each gate context through the real admission and orchestration steps, and run the real responder with live Laya and a fake LLM. Record the decided_by / verdict / concerns table.
- [ ] Review with the code-review agent; fix; commit.
