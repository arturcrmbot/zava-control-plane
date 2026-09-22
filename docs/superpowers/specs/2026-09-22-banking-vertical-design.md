# Zava Bank Vertical Design

**Date:** 2026-09-22
**Status:** Approved Phase Design
**Target:** Synthetic universal bank vertical (`verticals/banking/`)
**Build state:** Hero and supporting processes implemented and proven
end-to-end, including the agent phase and the human gate

## 1. Decision

Design a `banking` vertical modelling **Zava Bank**, a synthetic universal
bank spanning retail and business banking, payments and merchant services,
markets and post-trade, credit and counterparty risk, financial crime and
compliance, client governance, and private banking.

The vertical is informed by operating realities described in public UK
regulatory and industry sources. It does not reproduce any named
institution, and carries no branding, livery or look-and-feel that could
imply endorsement.

The approved portfolio is:

1. **APP Fraud Reimbursement** as the golden hero (world-owned).
2. **Mule Account Investigation** as a continuously-spawned supporting
   process.
3. **Merchant Onboarding Risk** as a continuously-spawned supporting
   process.

## 2. Evidence and synthetic-data boundary

### 2.1 What public sources may establish

- UK payment service providers must decide authorised-push-payment fraud
  reimbursement claims within a fixed window, with a longer stop for
  genuinely complex cases;
- reimbursement is capped per claim, and liability is shared equally
  between the sending and receiving provider;
- refusal rests on a consumer standard of caution set at gross negligence,
  a materially higher bar than ordinary carelessness;
- a customer carrying a vulnerability marker cannot be refused under that
  standard;
- banks monitor counterparty exposure against limits in close to real time
  and escalate excesses through documented authority tiers.

These establish entity families, decision boundaries and KPI categories.
They do not justify copying any named bank's internal procedure, model,
threshold, authority matrix, customer record or policy wording.

### 2.2 What is always synthetic

Bank identity, sort codes, customers, accounts, payments, rails,
beneficiary accounts, claims, corporate clients, counterparties, limits,
exposures, positions, collateral, investigations, authority bands, costs
and every KPI value. Identifiers are unmistakable: `SYN-CLAIM-0031`,
`SYN-BENE-002`, `SYN-CORP-014`, `SYN-CPTY-007`.

### 2.3 Prohibited source use

No confidential or leaked bank procedures, fraud models, limit frameworks,
authority matrices, customer or counterparty records, system names, logos
or branding. No real incident replayed without abstraction.

## 3. Operating model and actor world

### 3.1 Functions

| Function | Owns | Role |
|---|---|---|
| `retail-banking` | Hero + 3 declared | Hero origin |
| `payments` | Merchant onboarding + 2 declared | Rails, receiving providers |
| `financial-crime` | Mule investigation + 2 declared | Beneficiary investigation |
| `credit-risk` | 2 declared | Limits and exposures |
| `markets` | 2 declared | Positions and collateral |
| `client-governance` | 2 declared | Cross-function client decisions |
| `wealth` | 2 declared | Suitability and KYC |

Eighteen domains: three live, fifteen declared placeholders (`stub=True`).
Placeholders give the organisation chart its real reach and are excluded
from the execution-visibility gate. They are never presented as working
processes.

### 3.2 Scale

The world seeds at institution scale rather than diagram scale: 2,400
customers, 2,400 accounts, 3,003 payments, 240 beneficiary accounts, 8
payment service providers, 3 rails, 40 corporate clients, 24 counterparties
with limits and exposures, 120 positions, 24 collateral agreements.

An institution that renders as twelve boxes does not read as an
institution. Seeding is summarised in the journal rather than emitting one
event per record, so scale does not bury causality in setup noise.

### 3.3 Continuous life

Three SimPy loops keep the world moving with no workflow running: payments
settle, rails publish throughput, and a slice of the wholesale book
revalues against its limits on every market tick. Background loops emit
`banking.*` events only. Nothing but the fraud sensor opens an objective.

### 3.4 Human actors and non-delegable authority

| Persona | May decide | Never delegated |
|---|---|---|
| Fraud Decision Manager | Reimburse within GBP 50,000 | Refusing a vulnerable customer |
| Vulnerable Customer Specialist | The vulnerability determination | The determination itself |
| Financial Crime Lead | Mule disposition within GBP 250,000 | Certifying an offence |
| Payments Operations Lead | Merchant onboarding within GBP 120,000 | Waiving scheme rules |
| Credit Risk Officer | Excess within GBP 5,000,000 | Excess above tier |
| Senior Credit Officer | Excess within GBP 50,000,000 | Board risk appetite |

## 4. Hero: APP Fraud Reimbursement

### 4.1 Phases

1. **Scope Fraud Claim** (`deterministic`) — scope, evidence versions.
2. **Trace Beneficiary Path** (`deterministic`) — follow funds; admit only
   permissible options.
3. **Assess Claim Evidence** (`agent`) — rank admitted options only.
4. **Decide Reimbursement** (`hitl`) — `fraud_decision_manager`.
5. **Execute Reimbursement and Recovery** (`deterministic`) — typed command.
6. **Verify Reimbursement Outcome** (`deterministic`) — evaluation against
   a no-action baseline.

### 4.2 Three outcomes from one engine

The three seeded claims differ only in their evidence. No branch is
scripted:

| Claim | Amount | Admitted | Refusal rejected because |
|---|---|---|---|
| `SYN-CLAIM-0031` | 18,400 | REIMBURSE-FULL | no specific tailored warning evidence |
| `SYN-CLAIM-0032` | 6,750 | REIMBURSE-FULL | **vulnerability marker present** |
| `SYN-CLAIM-0033` | 92,000 | REIMBURSE-CAPPED at 85,000 | no specific tailored warning evidence |

### 4.3 The authority gap

The synthetic reimbursement cap is GBP 85,000; the claims manager's
delegation is GBP 50,000. The gap is deliberate. `SYN-CLAIM-0033` caps to
GBP 85,000, which the real governance kernel refuses for
`fraud_decision_manager` and matches instead to
`AUTH-financial_crime_lead-banking.commit_reimbursement_decision`.

The system does not merely refuse. It names who can authorise it. Verified:

```
standard claim     GBP  18,400.00  allowed=True
vulnerable claim   GBP   6,750.00  allowed=True
capped 92k claim   GBP  85,000.00  allowed=False  rule=AUTH-financial_crime_lead-...
```

### 4.4 Separation of responsibility

Deterministic admission decides what is *permissible*. The agent only ranks
what was already admitted. The governance kernel decides whether the
approver may authorise that value. The human decides. An option the
deterministic layer refuses cannot be rescued by ranking; an option it
admits can still be refused by the authority matrix.

## 5. Supporting processes and autonomy

`mule-account-investigation` and `merchant-onboarding-risk` share one
Durable engine but keep distinct workflow types, orchestrators, typed
commands, personae, authority bands, success events and evidence.

Both run a real **`agent`** phase against their own skill
(`mule-network-analyst`, `merchant-risk-assessor`) and the shared pack tools
`banking_read_case_evidence` and `banking_rank_admitted_case_options`. The
agent ranks only what deterministic admission already permitted, must call
both declared tools, and its output is rejected unless the instrumented tool
evidence, the phase, the option set and the evidence versions all check out.

Real agent work also supplies the elapsed time a case needs, so no simulated
handling delay is used anywhere.

Personae auto-close is scoped to the two supporting roles
(`PERSONA_AUTO_CLOSE=financial_crime_lead,payments_operations_lead`). The
hero's `fraud_decision_manager` gate deliberately stays open for a human:
the bank runs itself, and the one consequential decision waits for a
person.

They exist to make the bank look staffed. Both declare a pack-owned
`spawn_fn`, so the manifest's `ramp_workflow_types` picks them up and the
ramp loop opens new cases every 45 seconds without anyone pressing
anything. The hero is deliberately absent from that list: its objective
comes from a sensor, not a timer.

These processes hold no actor-world records, so the world-mutation node of
the proof chain is recorded as not applicable rather than faked.

## 6. Cross-bank linkage

The mule beneficiary on the standard claim, `SYN-BENE-002`, is held by
`SYN-CORP-014` — the same synthetic corporate client that carries the
wholesale exposure on `SYN-CPTY-007`. A retail fraud claim and a markets
exposure resolve to one client because the entity graph says so, not
because a caption asserts it.

## 7. Visual contract

The pack drives two surfaces.

**Cosmic lens.** Seven functions become seven planets. Banking function
names defeat the existing substring heuristics — `financial-crime` does not
contain `finance`, and `markets`, `payments`, `wealth` and `credit-risk`
match nothing — so every planet resolved to the same `ops` cyan. An exact
function-family map was added ahead of those heuristics, giving seven
distinct hues with no change to any existing vertical.

**Spatial world.** `ui/world-scene.json` uses the neutral scene contract:
10 locations laid out retail-left, rails-centre, wholesale-right so a
cross-bank link is a visibly long edge; 6 actor bindings chosen for
decision-bearing collections rather than raw volume; 8 event mappings.

## 8. Proof position

Verified:

- the hero completes the full chain: actor world -> sensor -> objective ->
  Durable -> agent (real `claim-evidence-assessor` reasoning with both
  declared tools returning `ok`) -> human gate -> typed command -> world
  mutation -> evaluation `resolved`, with `objective.resolved` closing it out
- world mutation is real: `SYN-CLAIM-0031` reimbursed GBP 18,400 with
  GBP 6,100 recovered and GBP 9,200 raised as the receiving provider's
  half-share; `SYN-CLAIM-0032` reimbursed GBP 6,750 with the vulnerability
  protection upheld; investigations opened against both mule accounts
- the refused claim mutates nothing: `SYN-CLAIM-0033` stays `reported`
- the human path works through the operator surface: resolving the
  exception drives approval, and `packDetail` then exposes the command, its
  four typed actions, and the evaluation's `mutation_records`
- all three live workflow types run a real agent phase and complete end to
  end, each with its own skill and instrumented tool evidence
- the cosmic lens renders it live with **zero console errors**: 15 rockets,
  one travelling, and rockets parked at the `financial_crime_lead` and
  `payments_operations_lead` cities, with the full event vocabulary flowing
  (`workflow.hitl.requested`, `durable.suspended`, `persona.thinking`,
  `persona.decided`, `durable.resumed`, `workflow.resolved`,
  `entity.upserted`, `entity.linked`)

- pack validates; 8 packs discovered; no cross-pack leakage
  (`tests/api/shared` 278 passed, 2 skipped)
- world seeds at scale and ticks continuously
- sensor → objective → Durable → deterministic phases → suspend
- real `check_authority` allows, denies and names the escalation target
- entity projections schema-valid against the live graph; zero reflector
  errors
- ramp loop spawns both supporting processes continuously
- scene served and structurally valid
- the **blocking execution-visibility gate passes**:
  `tools/workflow_visibility_proof.py --vertical banking` returns
  `{"result": "PASS", "sourceMode": "live", "workflowInstances": 4,
  "workflowTypes": 3}`
- recorded walks are committed under `verticals/banking/recordings/` for all
  three live workflow types. The hero walk is a complete trace:
  `workflow.started -> durable.step.* -> durable.executor.invoked x4 ->
  agent.completed -> workflow.hitl.requested -> durable.suspended ->
  durable.resumed -> durable.workflow.completed`

Not yet verified: every gate that requires the model. See §9.

## 9. Runtime selection

The substrate supports three LLM runtimes (`api/functions/graphs/executors/
agents/runtime.py`): `ghcp` (GitHub Copilot, the default and the documented
production path), `aoai` (Azure OpenAI) and `fake`.

`.env` had pinned `LLM_RUNTIME=aoai`, whose `DefaultAzureCredential` was
issuing a token for a tenant that did not own the configured resource:

```
400 — Tenant provided in token does not match resource token
```

This presented as an agent failure but was runtime selection, not pack code
and not a code defect. Setting `LLM_RUNTIME=ghcp` — which authenticates with
the `gh` CLI token already present on the machine — cleared it outright, and
every agent phase now completes with real, instrumented tool evidence.

### Model requests are a metered resource

All three live workflow types do real agent work, so every case the ramp
loop opens spends model requests. Under `ghcp` the Copilot request quota is
finite and shared; running background cases at a high cadence exhausts it
and then starves the hero:

```
Session error: Sorry, you've hit a rate limit that restricts the number of
Copilot model requests you can make within a specific time period.
```

Supporting cadence is therefore set to one case every 90 and 120
demo-seconds. That is a deliberate ceiling, not a throughput target: a
busier screen is available, but only by paying for it somewhere. For a
heavier steady state, move to `aoai` — once its tenant is correct it carries
its own, larger quota — rather than speeding up the ramp on `ghcp`.

The tell that this work is genuine is that it can exhaust a quota at all.
Canned output does not.

## 10. Readiness

All three live workflow types reach terminal state cleanly, including
the hero through its agent phase, its human gate, its typed command, its
world mutation and its evaluation.

Outstanding before **build ready** can be claimed: the two
`docs/VERTICAL-PROOF.md` §3 replay probes (Functions disabled; actor world
disabled) and the §5a live/replay parity pass, which needs the server booted
in replay mode against a recorded tape (`ZAVA_MODE=replay` +
`ZAVA_TAPE_PATH`). Seller review has not started, so **demo ready** is not
claimed either.
