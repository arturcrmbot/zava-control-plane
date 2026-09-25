# Laya decision layer: agentic thinking without the token bill

**Date:** 2026-09-24
**Status:** Built and verified behind flags. Phase 1 (personas judge) needs `JUDGEMENT_ENABLED=1`, phase 2 (the world notices and reacts) needs `BANKING_WORLD_SCREENING=1`, and phase 3 (the presenter steers) is available whenever the world runs.
**Scope:** a shared platform capability, proved on the banking vertical first.
**Author's evidence:** code read in this worktree, plus 241 live calls to a local Laya server on this Mac.

---

## 1. The idea in one page

Zava is an **org simulator**: nobody sits at a console approving things, so every
decision is made by a persona or an agent. Today most of those decisions are
hardcoded. A persona "decides" by checking an amount against a limit, and cases
arrive on a timer with random facts.

Laya is a small model that runs on this Mac. It picks one option from a short list, answers
yes/no, or rates something on a scale, from short English text, in about 50 ms, at
no token cost. It cannot write text, do maths or move money.

The plan uses Laya as the bank's **fast thinking** and keeps the LLM as its **slow
thinking**:

- **Personas genuinely judge.** Before approving, a persona reads the agent's
  reasoning and the case. It catches contradictions and pushes back for reasons it
  can name. Its character (cautious or pragmatic) changes how it judges.
- **The org moves.** A persona that holds a case, or a claim above its authority,
  hands it to the next persona up. That persona decides within its own authority,
  so the £92,000 story continues instead of ending at "refused".
- **The world notices and reacts** (phase 2). Suspicious payments open
  investigations instead of a timer. Customers and mule controllers react to
  decisions.
- **The presenter can steer it** (phase 3). Type what a customer says about any
  payment and the bank takes it from there, unscripted.
- **The LLM is reserved for the unclear minority,** within an hourly budget. When
  the budget is spent, today's rules decide. Every decision records which of the
  three decided and why.

What never changes: admission rules, the governance kernel and its authority
matrix, typed commands, and anything that computes or moves money.

## 2. Decisions already made (from our conversation)

| Question | Your answer |
|---|---|
| What comes first? | All three (personas, reactive world, presenter steering), phased, with personas first |
| Scope | A shared platform capability that any pack can switch on, proved on banking first |
| When Laya is unsure | An LLM review, or back to the current rules. There is no true human in the loop |
| When a persona holds a case, or it is above their authority | The next persona up takes it and decides within their own authority |
| Build approach | Judgement profiles plus one shared engine |

## 3. What is scripted today (verified)

| # | Where | What actually decides | Evidence |
|---|---|---|---|
| 1 | All six banking persona gates | An authority-limit check on the amount, nothing else. No persona uses personality or precedents | `verticals/banking/personae/*/SKILL.md` `decision_policy` |
| 2 | Fraud gate, "Decide Reimbursement" | Always approves: governance has already passed before the gate is raised | `verticals/banking/fraud_durable.py` (authority checked before the HITL phase) |
| 3 | Fraud gate on a refusal | A £0 refusal passes the same check as "within delegation". The persona can't tell a refusal from a payout | `api/shared/authority.py:91` (deny only when value > limit) |
| 4 | The hero's agent phase | Each of the three seeded claims admits exactly **one** option, so the agent "ranks" one item. The real content is its prose (19.5-20.6 s per session on the tapes) | ran `admit_claim_options` on the real world |
| 5 | Over-delegation story | Ends as "Refused by authority, needs Financial Crime Lead". Nobody picks it up | `fraud_durable.py` denial path; runbook walk at 0:22 |
| 6 | Supporting cases | Opened on a timer with facts from a private random seed, unrelated to the world. E.g. the tape's BMUL-0006 says SYN-BENE-141 holds £15,979 with 4 linked claims; the world has £116,840 and 0 claims | `verticals/banking/spawners.py:27,88-92,113-115` |
| 7 | Supporting admission | Based only on the risk band. Option values are fixed (£45k/£5k/£120k, £25k/£60k/£0) whatever the case | `verticals/banking/supporting_durable.py:124-155,203-210` |
| 8 | Supporting outcomes | Mutate nothing in the world, so decisions have no consequences | `supporting_durable.py` docstring; runbook section 7 |
| 9 | Other packs' gates | Random dice for sick, holiday, timeout, wait, and an "override" that flips the decision to fake human defiance | `persona_responder.py:1058-1137,1204`; e.g. `verticals/agency/domains.py:142-143,170` |
| 10 | Persona "thinking" time | A random 2-8 s sleep when `DEMO_LOUD=1` | `persona_responder.py:1178-1179` |
| 11 | Persona reasons | Templated strings, e.g. "within fraud_decision_manager delegation per matrix rule ... GBP 18400.0" | persona `decision_policy` blocks |

## 4. What Laya can and cannot do here (measured)

Measured on this Mac (MPS GPU) against realistic banking inputs: the real world
model, the real admission code, and the two real LLM reasonings recorded on the
22 Sep tapes. Labels marked *authored* are my judgement of what a careful manager
would say. They test sensitivity, not regulatory correctness. "Lead" means how far
Laya's top answer is ahead of the runner-up (0 is a coin toss, 1 is certain).

### 4.1 Speed

| Call | Server time (median) | Notes |
|---|---|---|
| 1 question, ~110-word state | 47 ms (max 73) | |
| 3 questions, one call | 120 ms | each question re-reads the state |
| 6 questions, one call | 276 ms | |
| First call with a new input shape | 350-490 ms | one-off warm-up |
| All 241 calls | p50 64-104 ms, p95 301 ms, max 491 ms | two runs |
| For comparison: one LLM agent session | 19,500-20,600 ms on the tapes; up to 150 s per attempt | plus quota and rate limits |

### 4.2 Where it works

| Task | Result | Design lesson |
|---|---|---|
| Reading the agent's reasoning with narrow yes/no questions | **31/36 right** (vulnerability mentioned 6/6, recovery 6/6, argues refusal 6/6) | Use narrow, positively phrased questions |
| Persona gate as **read, then check, then judge** | **5/5 labelled cases right, and the ambiguous case held.** It caught the contradiction the broad question missed. Routine approvals led by 0.73-0.80 | Laya reads; code compares with the record; Laya judges |
| The vulnerability pair ("says vulnerable" / "says no marker") on 10 texts (measured while building) | 19/20 right; the one confident error made both answers "yes", so the pair turned it into a hand-off, not a false concern | Pair any question prone to negation |
| Persona character | With one broad question, "cautious" raised the hold probability over "pragmatic" in 10/10 cases. In read-then-judge it did so in 4 of 6 and reversed in 2 | Personality is a real input, but its wording needs calibrating |
| Payment references against described scam patterns | **16/16 right on clear references** (safe account, tax/police demand, unlock fee, guaranteed returns); 9 of them with a clear lead, the other 7 would do nothing | Put the domain knowledge in the options |
| How upset a customer is about a decision (0-3 scale) | Sensible order: full refund 0.27-0.35 < partial 0.69-0.90 < refusal 0.99-1.30 ≈ held 1.15-1.34 | Use the distribution to drive reactions |

### 4.3 Where it must not be trusted

| Task | Result | So |
|---|---|---|
| One broad "approve or hold?" question | Missed the agent contradicting the record. **Approved an amount it was told was above authority** (3/3 wordings). Confidence swung 0.06-0.69 with wording | Never ask it the whole decision in one question |
| Comparing an amount with a limit | 9/12. **The dangerous errors sit just above the limit**: £50,001 and £52,000 judged "within £50,000"; £6,750 was judged outside it | Code owns every number and threshold |
| Negation ("says no marker") | One confident error at p=0.999 | Ask paired questions. If both say yes, treat it as unclear |
| Ranking mule dispositions | Picks follow the risk band only. Six victims plus a large balance still gave "monitor" (0.61) | Keep the LLM for ranking |
| Scam type from the customer's own words | 8/12, with confident errors (police and tax impersonation read as "not a scam") | Advisory only; described patterns needed |
| Vulnerability cues in the customer's words | Caught 2-3 of 4 real cues, with 2 false alarms on "money worries" | Never a determination (the pack forbids it anyway) |
| "Would the customer complain?" yes/no | Flat 0.06-0.18 whatever the decision | Use the upset scale instead |
| The approve/hold verdict weighing a list of concerns (measured while building) | Approved with a lead of 0.5-0.8 in all four phrasings even with "the agent argues for declining" listed | Serious concerns hold by rule; Laya weighs only minor ones, in character |
| "Does the text argue for refusal?" (measured while building) | 3 of 6 confidently wrong in every wording, including a routine reimbursement read as arguing for refusal | Removed from the fraud profiles |
| Wording of the pair and the no-action read, on 11 and 10 texts (measured while building) | "Does the text say there is no vulnerability flag?" 10/11 (was 9/11); "Does the text mention what happens if nothing is done?" 9/10 with no confident errors (was 8/10 with 2) | Measure wording on real texts; keep the variant with the fewest confident errors |
| "Does the text argue for declining?" when the text names declining only to reject it | Unsure (about 0.46), never confidently wrong in 6 texts | Kept as serious: unsure goes to the deep review |

## 5. Principles

1. **Code owns facts, maths, lookups and actions. Laya makes only the fuzzy
   judgement.** It never sees a comparison it would have to compute.
2. **Laya can only move a decision towards caution.** If today's rules would not
   approve, Laya cannot make them approve.
3. **One narrow question per judgement,** phrased positively. Questions prone to
   negation errors are paired.
4. **Act only when the top answer clearly leads** (a minimum lead over the
   runner-up, tuned per question). Otherwise go to the LLM, within budget.
   Otherwise use the rules.
5. **Every decision is evidenced:** who decided (Laya, LLM or rules), each question,
   the probabilities, the gap and threshold, the concerns found, latency and any
   fallback reason.
6. **Off means today.** With the flag off, or Laya down, behaviour is identical to
   now.

**Never changes:** `fraud_constraints.py` admission, supporting admission, the
governance kernel and authority matrix, evidence-version checks, typed commands,
world mutation, and the vulnerability determination.

## 6. Architecture: one shared engine

New platform package `api/server/services/judgement/`:

| Part | Job |
|---|---|
| `laya_client.py` | Async calls to `LAYA_URL` (unset means disabled). 2 s timeout, health check, circuit breaker after repeated failures, one call per decision |
| `profiles.py` | Loads and validates the `judgement:` block in each persona's SKILL.md when personas load, and fails fast on a bad profile |
| `engine.py` | Runs the decision flow below |
| `deep_review.py` | The LLM "slow thinking" path, through the existing provider-neutral runtime (`_get_runtime().run_session`; `LLM_RUNTIME=fake` for tests). The Fleet Manager already runs Copilot sessions inside the API server, so this path is proven there. No tools, JSON verdict, timeout, hourly budget |
| `evidence.py` | The judgement record, stored on the workflow's decisions and emitted as a `persona.judgement` event |

Each pack adds a small **facts adapter** (for banking,
`verticals/banking/judgement_facts.py`). It turns a gate's context into named
facts and texts, e.g. `customer_vulnerable`, `recommends_refusal`,
`agent_reasoning`, `recommendation_words`.

### 6.1 Decision flow at every gate

```
1. ceiling  = today's decision_policy(context)            (unchanged code)
2. if ceiling is not "approve"        -> keep it          (Laya can't upgrade)
3. if no profile / flag off / Laya down -> keep ceiling   (today's behaviour)
4. READ   one Laya call: the profile's narrow questions about the texts
5. CHECK  code compares readings with facts -> concerns in plain words
          paired questions that disagree     -> "unclear"
6. a serious concern      -> hold (by rule: a verified contradiction is never waved through)
   no concerns            -> approve
   only minor concerns    -> JUDGE: one Laya call, character + recommendation + concerns
7. an unclear serious reading, or a minor-concern verdict with a small lead
          -> LLM deep review if budget allows -> approve | hold
          -> otherwise the rules ceiling, recorded as "decided by rules"
8. approve -> today's approval payload, plus rationale and evidence
   hold    -> hand to the next persona up (section 7.2); at the top of the chain,
              the deep review decides: approve, or send the case back to the agent
              with its reasons to re-assess once; a hold after that declines
```

### 6.2 What a profile looks like (fraud decision manager)

```yaml
judgement:
  character: "Thorough: you hold a case whenever the agent's reasoning and the record disagree."
  reads:
    - {id: says_vulnerable,  text: agent_reasoning, ask: "Does the text say the customer is vulnerable or carries a vulnerability marker?"}
    - {id: says_no_marker,   text: agent_reasoning, ask: "Does the text say there is no vulnerability flag?"}
    - {id: covers_no_action, text: agent_reasoning, ask: "Does the text mention what happens if nothing is done?"}
  checks:
    - concern: "the agent's reasoning says there is no vulnerability marker, but the record shows one"
      when: {read: says_no_marker, is: yes, fact: customer_vulnerable, equals: true}
      unless: says_vulnerable          # paired question: both yes means unclear
    - concern: "the agent does not say what happens if the bank does nothing"
      when: {read: covers_no_action, is: no}
    - concern: "the recommendation refuses a fraud victim; refusals always get a second pair of eyes"
      when: {fact: recommends_refusal, equals: true}      # four-eyes policy, deterministic
  decide:
    ask: "Given the findings, what should you do with the agent's recommendation?"
    approve: "Approve it now: no concerns were found"
    hold: "Hold it: the concerns need someone else's judgement"
  min_lead: 0.3
```

Checks use a small fixed vocabulary (`read`/`is`, `fact`/`equals`, `unless`), not
code, so a profile stays declarative and reviewable. `min_lead` is the minimum lead
the verdict needs before the persona acts on it.

### 6.3 Flags

| Setting | Default | Meaning |
|---|---|---|
| `LAYA_URL` | unset | Where Laya listens. Unset means Laya is off |
| `JUDGEMENT_ENABLED` | `0` | Master switch |
| `JUDGEMENT_LLM_BUDGET_PER_HOUR` | 6 | LLM deep reviews allowed per hour. After that, the rules decide |
| `JUDGEMENT_MIN_LEAD` | per gate | Overrides the profile's threshold |
| `JUDGEMENT_GATE_DEADLINE_S` | 180 | Time allowed to judge one gate, hand-ups included; the orchestrator waits 300 s. Deep reviews run one at a time, and one that cannot finish in time is not started (no budget spent), so the rules decide |

A persona opts in by carrying a `judgement:` block for the gate's workflow type
in its SKILL.md. A pack with no such blocks is untouched.

## 7. Phase 1: personas that judge (banking first)

### 7.1 The three banking gates

| Gate | Persona and character | What it reads | Hold means |
|---|---|---|---|
| Decide Reimbursement | Fraud Decision Manager, thorough | Agent reasoning vs record (6.2); refusals always get four eyes | Hand to the Financial Crime Lead |
| Approve Account Disposition | Financial Crime Lead, conservative | Does the reasoning weigh victims' funds, linked claims, no-action? Does it contradict the case? | Top of chain: LLM deep review decides |
| Approve Onboarding Decision | Payments Operations Lead, pragmatic | Does the reasoning address volume, sector, reserve trade-offs? | Top of chain: LLM deep review decides |

The Fraud Decision Manager's gate is decided by the persona too. It no longer waits
for a presenter, consistent with "no true human in the loop". That means adding
`fraud_decision_manager` to `PERSONA_AUTO_CLOSE`, or using `*`. The running
Functions host has only the two supporting leads today.

### 7.2 The org hands work up (your answer on escalation)

- **Above authority (the £92,000 story).** Instead of ending, the orchestrator asks
  the governance kernel who can approve the capped £85,000
  (`resolve_approver`, which names the Financial Crime Lead). It re-checks that
  persona's authority, then raises the gate for that persona. The Financial Crime
  Lead judges with its own profile and decides. The kernel stays the only source
  of who may approve. If it names nobody, the claim is refused as today.
- **A hold.** The case goes to the next persona named by the authority row's
  `delegate_to` or the kernel's escalation chain. That persona judges it fresh,
  seeing the first persona's concerns. At the top of the chain, the LLM deep review
  decides: approve, or send the case back to the agent with its reasons. The
  agent re-assesses once and the gate is raised again. A hold after that
  declines. The rules decide if the budget is spent, or if a deep review
  could not finish before the gate's deadline.
- **Code changes this needs:** `fraud_durable.py` must accept the approving persona
  named in the gate context rather than a constant, pass it to the command, and
  re-check governance for that persona. `persona_responder.py` must address
  escalations using `escalate_to`. The world's command gateway already records any
  persona (`verticals/banking/actions/fraud_commands.py`).

### 7.3 What the audience sees

- **On a decided gate:** "Fraud Decision Manager held this: the agent's reasoning
  says there is no vulnerability marker, but the record shows one. Handed to the
  Financial Crime Lead." Plus who decided (fast judgement, deep review or rules)
  and how sure.
- **Thinking time is real.** About 0.1-0.3 s for a fast judgement, 20-60 s for a
  deep review. There is no random sleep on judged gates.
- **In workflow detail:** every question, its probabilities, the threshold and the
  path taken.
- **In other packs:** a persona with a profile skips the random "override" dice.
  Grounded pushback replaces fake defiance. Sick and holiday dice stay; they
  simulate availability, not judgement.

### 7.4 Done when

- The three gates run on judgement with the flag on, and are byte-identical to
  today with it off.
- The contradiction case, the refusal case and the £92,000 case each play out as
  described, end to end, on the local stack.
- Every decision carries its evidence, and the tape records it.

**Size: medium** (engine, profiles, adapter, escalation, UI surfacing, tests).

### 7.5 Verified (25 Sep 2026)

End to end, in process: the real fraud orchestration, real activities (world,
admission, governance kernel, reimbursement command), the real persona responder
and live Laya, with authored agent reasoning (`tools/laya_eval/e2e_banking.py`).

| Case | Trail | Outcome |
|---|---|---|
| Standard GBP 18,400 | fraud manager approves (fast judgement) | reimbursed in full |
| Vulnerable GBP 6,750 | fraud manager approves (fast judgement) | reimbursed in full |
| Vulnerable, reasoning says "no marker" | manager holds (fast) -> crime lead deep review sends it back -> agent re-assesses -> manager approves (fast) | reimbursed in full |
| Over delegation GBP 92,000 | governance names the crime lead -> approves (fast) | reimbursed to the GBP 85,000 cap by the crime lead |
| Generated high-value claim | crime lead approves (fast) | reimbursed to the cap |
| Agent ranks refusal first | manager holds (four eyes) -> crime lead sends it back -> agent re-ranks -> manager approves | reimbursed in full |

Fast judgements took 60-135 ms of Laya time per gate. The real deep review
(gpt-4.1 through Copilot) took 8.5-13.3 s and returned a valid verdict each time.
With `JUDGEMENT_ENABLED=0` the same run is decided exactly as before: the two
high-value claims end "refused by authority", and the refusal of a fraud victim
is approved on its GBP 0 value.

Live golden set (`tests/api/judgement/test_laya_live.py`): 9/9 on repeated runs.

## 8. Phase 2: the world notices and reacts (banking world)

- **Payments carry references.** The seeded world gives every payment a short
  reference: ordinary ones ("Rent October flat 3"), and scam-pattern ones on
  payments into mule accounts ("Safe account transfer as advised by bank"), at a
  set rate.
- **The bank notices.** As payments settle, Laya screens each reference against
  described scam patterns (16/16 in testing). A clear match flags the payment. An
  unclear one does nothing and never spends LLM budget.
- **Cases open because of the world.** Code opens a mule investigation when an
  account collects flagged payments from two or more different customers. The rule
  is visible and the facts come from the world. The case then carries the world's
  real risk band, balance and flagged payments, replacing the timer spawner for
  banking.
- **Decisions have consequences.** A restrained account can no longer receive or
  move money. A monitored one may keep collecting scam payments and reopen. The
  mule controller's next move is drawn from Laya's distribution.
- **Customers react.** After a reimbursement decision, the customer's reaction
  (accepts, chases, complains) is drawn with a seeded draw from Laya's upset
  distribution, and appears as world events and a complaints KPI.
- **Merchants describe themselves.** Applications carry a one-line business
  description. Laya picks the business category from described categories. Code
  maps category to risk band, and admission runs as today.

**Size: large** (world data, a screening loop with rate limiting, a mule
command gateway, reactions).

### 8.1 Built and verified (25 Sep 2026), behind `BANKING_WORLD_SCREENING=1`

- **New payments carry references,** screened as they arrive. This is cached per
  reference, and the world never waits: an unseen reference is read on an asyncio
  task.
  - Measured reference lists: 0 of 30 ordinary references flagged; 13 of 18 scam
    references flagged. The five misses stay, as a real screen misses some.
  - If Laya is down, keyword rules screen, and every flag says which read it.
- **Mule cases open when the world notices.** Flagged payments from two or more
  customers into one account trip `sensor:mule_pattern`. The world bridge then
  starts the mule orchestration with the account's real band, balance and flagged
  payments. The mule timer is retired; merchants still arrive on the ramp.
- **Dispositions change the world.** Restrained accounts stop receiving and
  monitored ones keep collecting, then reopen as round 2. A second command for a
  decided case is rejected.
- **Customers react** after a reimbursement: accepts, chases or complains, drawn
  from Laya's upset scale with a seeded stream. The scale is measured monotone:
  full < capped < refused.
- **Merchant applications describe the business.** Laya picks the kind of business
  and a code table sets the band. Measured: 13 of 20 right with a clear lead, none
  confidently wrong. Businesses paid months ahead mostly read as unclear, which maps
  to medium.
- **End to end** (`tools/laya_eval/e2e_banking.py mule`):
  1. The world stepped with the live Laya screener; 12 payments were screened and 5
     flagged.
  2. The sensor tripped for a low-band account with two customers, and the rules
     permitted only monitoring.
  3. The stand-in reasoning argued for restraint, so the Financial Crime Lead held
     it and the deep review decided.
  4. The disposition was applied back to the account.

## 9. Phase 3: the presenter steers live

- **"A customer calls about this payment."** Pick any payment on the rail floor and
  type what the customer says. Laya reads the scam pattern, and code opens a new
  fraud claim on that payment in the world. Today only three seeded claims exist,
  so this needs dynamic claims. The hero workflow then runs end to end on it:
  admission, the agent, persona judgement, escalation. Nobody, including us, knows
  the outcome in advance.
- **"Ask the persona."** A what-if box on a waiting or decided case, e.g. "would you
  still approve if the customer were vulnerable?" The engine re-runs the judgement
  with that fact changed and answers instantly, at no token cost.

**Size: medium to large** (dynamic claims in the world are the main work).

### 9.1 Built and verified (25 Sep 2026)

- **A customer calls** (`POST /api/world/customer-calls`, and the floor's *A customer
  calls about a payment* panel):
  - The presenter picks a recent payment and types what the customer says.
  - Laya reads the kind of scam and any circumstances, which is advisory: 9 of 12
    scam types measured right. Rules read if Laya is down.
  - The world raises a claim on that payment from the record's facts, so the
    vulnerability marker on the record still decides.
  - The customer's words and the reading travel in the evidence the agent reads.
  - Verified live: "bank impersonation" (lead 0.86) with bereavement noted, read in
    0.48 s. The claim was raised on a GBP 8,940 payment, and the fraud manager
    approved it by fast judgement.
- **Ask the persona** (`POST /api/judgement/what-if`, and the *Ask the …: what if*
  box under the claim story):
  - Change the agent's reasoning or the vulnerability marker, and the persona
    re-judges instantly.
  - It uses the fast judgement only, costs no tokens and changes no state. It says
    when a deep review would decide instead.
  - Verified live: with the marker set, the manager would hold and hand the case up,
    because the reasoning would then contradict the record.
- **`GET /api/judgement/status`** reports whether Laya is up and how many deep reviews
  are left this hour.

## 10. Where Laya will not be used

- **Amounts, limits, caps, bands:** boundary errors (section 4.3).
- **Ranking agent options:** it ignores the evidence and follows the band, so the LLM
  keeps this.
- **The whole approve/refuse decision in one question:** it approved above authority
  and missed contradictions.
- **Vulnerability determination:** the pack forbids it, and recall was 2-3 of 4. Cues
  can only be advisory.
- **Building commands, computing values, mutating the world.**

## 11. Testing and calibration

- **Unit tests with a fake Laya** (no server) for the engine:
  - the caution-only invariant, as a property test over all ceilings
  - the fallback ladder
  - the budget
  - the evidence shape
  - escalation addressing
  - off means identical
- **Golden sets from this evaluation** (the 36 readings, 16 references and the gate
  cases) as an integration test that runs only when Laya is up, and as the tool that
  picks each question's threshold.
- **Before judgement becomes the default:** run 20-50 real cases through both Laya
  and the LLM deep review and compare, as the Laya skill requires.
- **Existing suites stay green:** `tests/api/banking` plus the persona responder and
  governance tests, with the flag off by default.

## 12. Risks

| Risk | Mitigation |
|---|---|
| Confident wrong readings (negation) | Paired questions, positive phrasing, and code-owned facts |
| Confidence depends on wording | Fixed wording per question in the profile; thresholds calibrated on golden sets; golden sets rerun as a regression test |
| The judge step looks like "concerns in, verdict out" | Show the concerns Laya found. That reading is the non-scripted part |
| LLM fallback burns quota | Hourly budget, then rules; the budget shows on screen |
| Laya down or slow | 2 s timeout, circuit breaker, then today's behaviour |
| Screening load in phase 2 | About 40 calls/s capacity; screen at settlement rate with a cap per tick; unclear results are ignored |
| Memory and GPU (about 3 GB) on the demo Mac | Start Laya with `make up`; check before the demo; flag off if needed |
| Tapes and replay | Record judgement events so replay never calls Laya |

## 13. Rollout

| Step | Contents | Size |
|---|---|---|
| 0 | Laya client, evidence record, flags, golden-set harness. No behaviour change | small |
| 1 | Personas judge: engine, three banking profiles, facts adapter, escalation, deep review, UI | medium |
| 2 | World reacts: references, screening, world-noticed mule cases, consequences, customer reactions, merchant descriptions | large |
| 3 | Presenter steers: customer-calls panel with dynamic claims, ask-the-persona | medium to large |

Each step ships behind its flag, with its tests, and is reviewed before the next.

## 14. Decisions on the open questions

1. **Vulnerability cues are advisory only.** They show on the case and go to the
   agent. The record's marker still decides.
2. **LLM budget:** 6 deep reviews an hour. After that, the rules decide and the
   record says so.
3. **The mule timer is retired in banking** once the world opens mule cases
   itself (phase 2).
4. **Deep review rationale** shows on the floor trimmed to two sentences, with the
   full text in workflow detail.

## Appendix A: evaluation inputs and raw results

The harness is in `tools/laya_eval/` (`eval_banking.py`, `eval_redesign.py`); it
logs every call (state, questions, probabilities, latency) to `$LAYA_EVAL_OUT`.
The golden cases also run as `tests/api/judgement/test_laya_live.py` whenever
Laya is up.
Cases: the three seeded claims from the real world; variants built by changing one
claim field and re-running real admission; the two real LLM reasonings from the 22
Sep tapes plus four authored flawed texts; 12 authored customer statements; 19
authored payment references; 16 ramp-shaped cases using the spawners' own random
generator (seed 1729).
